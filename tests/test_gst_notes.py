import copy
import json
from pathlib import Path
import tempfile
import unittest
from riju import core,gst,tax,history
from riju.storage import Vault
from test_gst import values,OUR,LOCAL


class GstNoteTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state()
        tax.save_rule(self.s,dict(family='GST',key='TEST-GST',effective='2026-04-01',label='Invented rule',rate='18',treatment='Taxable',hsn_sac='999311',applicability='Synthetic tests',source='Invented reference',reviewed=True))
        self.invoice=gst.post(self.s,values())
    def note(self,**extra):
        v=dict(original_document_id=self.invoice['id'],date='2026-05-01',document_type='Credit note',amount='50',reference='CN-1',counter_account='1010',narration='Invented refund',confirmed=True);v.update(extra);return gst.post_note(self.s,v)
    def test_sales_partial_credit_and_later_period_ledger_proof(self):
        n=self.note();self.assertEqual(n['totals']['total'],5900);self.assertEqual(n['rule'],self.invoice['rule'])
        april=gst.summary(self.s,'2026-04-01','2026-04-30');may=gst.summary(self.s,'2026-05-01','2026-05-31')
        self.assertEqual(april['totals']['sales_base'],10000);self.assertEqual(may['totals']['sales_base'],-5000)
        self.assertFalse(any(may['unclassified'].values()));self.assertEqual(core.balances(self.s,'2026-05-31')['1010'],5900)
    def test_debit_note_increases_billing_and_credit_capacity(self):
        self.note(document_type='Debit note',reference='DN-1',amount='20')
        self.note(date='2026-05-02',amount='120')
        r=gst.summary(self.s,'2026-04-01','2026-05-31');self.assertEqual(r['totals']['sales_base'],0);self.assertEqual(r['net_movement'],0)
    def test_overcredit_and_approval_failures_atomic(self):
        for extra in ({'amount':'100.01'},{'confirmed':False},{'date':'2026-04-01'},{'counter_account':'2200'},{'reference':''}):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):self.note(**extra)
            self.assertEqual(before,self.s)
    def test_backdated_credit_cannot_consume_future_credit_capacity(self):
        self.note(date='2026-06-01',amount='80');before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.note(date='2026-05-01',amount='30',reference='CN-BACKDATED')
        self.assertEqual(self.s,before)
    def test_reverse_original_requires_reversing_credit_and_debit_notes(self):
        for kind in ('Credit note','Debit note'):
            with self.subTest(kind=kind):
                before=copy.deepcopy(self.s);n=self.note(document_type=kind)
                with self.assertRaises(ValueError):core.reverse(self.s,self.invoice['voucher_id'],'2026-05-03')
                core.reverse(self.s,n['voucher_id'],'2026-05-03');core.reverse(self.s,self.invoice['voucher_id'],'2026-05-03')
                self.assertEqual(gst.summary(self.s,'2026-04-01','2026-05-31')['net_movement'],0)
                self.s=before
    def test_reversing_note_and_reversal_of_reversal_preserve_signs(self):
        n=self.note();r=core.reverse(self.s,n['voucher_id'],'2026-06-01');core.reverse(self.s,r['id'],'2026-07-01')
        result=gst.summary(self.s,'2026-04-01','2026-07-31');self.assertEqual(result['totals']['sales_base'],5000);self.assertFalse(any(result['unclassified'].values()))
    def test_note_on_cancelled_invoice_and_note_on_note_rejected(self):
        n=self.note()
        with self.assertRaises(ValueError):self.note(original_document_id=n['id'],reference='CN-CHAIN')
        core.reverse(self.s,n['voucher_id'],'2026-05-03');core.reverse(self.s,self.invoice['voucher_id'],'2026-05-03')
        with self.assertRaises(ValueError):self.note(date='2026-05-04',reference='CN-CANCELLED')
    def test_full_credit_releases_exact_remaining_rounding_paise(self):
        tiny=gst.post(self.s,values(reference='TINY',amount='0.03'))
        self.note(original_document_id=tiny['id'],reference='TINY-1',amount='0.01')
        n=self.note(original_document_id=tiny['id'],reference='TINY-2',amount='0.02',date='2026-05-02')
        self.assertEqual(n['totals']['sgst'],1);self.assertEqual(gst._check_family(self.s,tiny['id'])['total'],0)
    def test_purchase_credit_reverses_eligible_tax_or_ineligible_cost(self):
        for itc in ('Eligible','Ineligible'):
            p=gst.post(self.s,values(kind='Purchase',reference='P-'+itc,account='4590',counterparty_gstin=LOCAL,itc=itc))
            n=self.note(original_document_id=p['id'],reference='PC-'+itc,counter_account='2000')
            self.assertEqual(n['itc'],itc)
            if itc=='Eligible':self.assertTrue(any(l['account']=='1200' and l['credit']==450 for l in n['lines']))
            else:self.assertEqual(next(l['credit'] for l in n['lines'] if l['account']=='4590'),5900)
        self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-05-31')['unclassified'].values()))
    def test_original_rate_retained_and_duplicate_note_rejected(self):
        rule=copy.deepcopy(self.invoice['rule']);rule['rate']='12';tax.save_rule(self.s,rule)
        n=self.note();self.assertEqual(n['totals']['cgst'],450)
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.note(reference='cn/1')
        self.assertEqual(before,self.s)
    def test_adjusted_purchase_flags_2b_instead_of_matching_note_as_invoice(self):
        p=gst.post(self.s,values(kind='Purchase',reference='P-1',account='4590',counterparty_gstin=LOCAL,itc='Eligible'))
        raw=('supplier_gstin,invoice,date,taxable,cgst,sgst,igst,itc_available\n'+LOCAL+',P-1,2026-04-02,100,9,9,0,Y\n').encode()
        imp=gst.import_2b(self.s,raw,'2b.csv',OUR,'2026-04');gst.match_2b(self.s,imp['id'],imp['rows'][0]['id'],p['id'])
        n=self.note(original_document_id=p['id']);row=gst.candidates_2b(self.s,imp['id'])[0]
        self.assertIn('adjusted',row['status']);self.assertEqual(len(row['candidates']),1)
        core.reverse(self.s,n['voucher_id'],'2026-06-01');self.assertEqual(gst.candidates_2b(self.s,imp['id'])[0]['status'],'Matched')
    def test_future_original_reversal_blocks_backdated_debit_note(self):
        core.reverse(self.s,self.invoice['voucher_id'],'2026-06-01')
        with self.assertRaises(ValueError):self.note(document_type='Debit note',date='2026-05-01')
    def test_format_six_upgrade_backup_and_signed_exports(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ext=root/'external';ext.mkdir();old=copy.deepcopy(self.s);old['version']=6;old['schema_revision']=6;history.checkpoint(old)
            p=root/'old.json';p.write_text(json.dumps(old));raw=p.read_bytes();v=Vault(p,demo=True);self.s=v.load();self.s['settings']['backup_dir']=str(ext);v.save(self.s)
            self.assertEqual(v.last_upgrade_backup.read_bytes(),raw);self.assertEqual(self.s['version'],15)
            self.note();v.save(self.s);self.assertEqual(v.load(),self.s);before=copy.deepcopy(self.s)
            gst.export_csv(gst.summary(self.s,'2026-04-01','2026-05-31'),root/'gst.csv');text=(root/'gst.csv').read_text(encoding='utf-8-sig')
            self.assertIn('Credit note',text);self.assertIn('TEST-1',text);self.assertIn('-50.00',text);self.assertEqual(before,self.s)

    def test_offsetting_active_notes_still_prevent_original_cancellation(self):
        self.note(document_type='Debit note',reference='DN-1')
        self.note(reference='CN-1')
        with self.assertRaises(ValueError):core.reverse(self.s,self.invoice['voucher_id'],'2026-05-03')

    def test_history_traces_original_invoice_and_note_in_both_directions(self):
        n=self.note();before=copy.deepcopy(self.s)
        for vid in (self.invoice['voucher_id'],n['voucher_id']):
            trace=history.trace_voucher(self.s,vid)
            self.assertEqual({d['id'] for d in trace['gst_context']},{self.invoice['id'],n['id']})
        self.assertEqual(before,self.s)

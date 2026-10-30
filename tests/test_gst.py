import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from openpyxl import Workbook
from riju import core,foundation,gst,tax,history
from riju.storage import Vault

OUR='29ABCDE1234F1Z5';OTHER='32ABCDE1234F1Z5';LOCAL='29ZZZZZ1234Z1Z5'


def values(**extra):
    value=dict(date='2026-04-02',branch='JP',kind='Sale',registration=OUR,place_of_supply='29',counterparty_gstin='',reference='TEST-1',rule_key='TEST-GST',amount='100',inclusive=False,account='4000',counter_account='1010',itc='Not applicable',narration='Synthetic GST test',confirmed=True)
    value.update(extra);return value


class GstTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state()
        tax.save_rule(self.s,dict(family='GST',key='TEST-GST',effective='2026-04-01',label='Invented rule',rate='18',treatment='Taxable',hsn_sac='999311',applicability='Synthetic tests only',source='Invented reference',reviewed=True))
    def purchase(self,**extra):
        v=values(kind='Purchase',reference='P-1',account='4590',counterparty_gstin=LOCAL,itc='Eligible');v.update(extra);return gst.post(self.s,v)
    def raw2b(self,supplier=LOCAL,invoice='P-1',on='2026-04-02',base='100',cgst='9',sgst='9',igst='0',available='Y'):
        return ('supplier_gstin,invoice,date,taxable,cgst,sgst,igst,itc_available\n'+','.join((supplier,invoice,on,base,cgst,sgst,igst,available))+'\n').encode()
    def test_sale_split_and_balanced_ledger_proof(self):
        d=gst.post(self.s,values());self.assertEqual(d['totals'],dict(base=10000,cgst=900,sgst=900,igst=0,total=11800))
        self.assertEqual(core.balances(self.s,'2026-04-30')['1010'],11800)
        r=gst.summary(self.s,'2026-04-01','2026-04-30');self.assertFalse(any(r['unclassified'].values()));self.assertEqual(r['net_movement'],1800)
        core.verify_audit(self.s)
    def test_interstate_sale_and_inclusive_invoice(self):
        d=gst.post(self.s,values(place_of_supply='32',amount='118',inclusive=True))
        self.assertEqual(d['totals']['base'],10000);self.assertEqual(d['totals']['igst'],1800);self.assertEqual(d['totals']['cgst'],0)
    def test_odd_tax_paise_rounding_and_minimum_base(self):
        d=gst.post(self.s,values(amount='0.03'));self.assertEqual(d['totals']['cgst'],0);self.assertEqual(d['totals']['sgst'],1)
        with self.assertRaises(ValueError):gst.plan(self.s,values(amount='0'))
        with self.assertRaises(ValueError):gst.plan(self.s,values(amount='1.005'))
    def test_purchase_uses_supplier_state_not_recipient_state(self):
        d=self.purchase(counterparty_gstin=OTHER);self.assertEqual(d['totals']['igst'],1800);self.assertEqual(d['totals']['cgst'],0)
        self.assertEqual(core.balances(self.s,'2026-04-30')['1220'],1800)
    def test_ineligible_itc_is_cost_not_input_credit(self):
        d=self.purchase(itc='Ineligible');b=core.balances(self.s,'2026-04-30')
        self.assertEqual(b['4590'],11800);self.assertEqual(b['1200'],0)
        self.assertEqual(gst.summary(self.s,'2026-04-01','2026-04-30')['totals']['ineligible_tax'],1800)
    def test_exempt_treatment_retained_without_tax(self):
        tax.save_rule(self.s,dict(family='GST',key='TEST-EXEMPT',effective='2026-04-01',label='Test exemption',rate='0',treatment='Exempt',applicability='Invented test exemption',source='Invented test',reviewed=True))
        d=gst.post(self.s,values(rule_key='TEST-EXEMPT'));self.assertEqual(d['totals']['total'],10000)
        self.assertEqual(gst.summary(self.s,'2026-04-01','2026-04-30')['turnover'][0]['treatment'],'Exempt')
    def test_approval_and_invalid_controls_atomic(self):
        for extra in ({'confirmed':False},{'place_of_supply':''},{'registration':''},{'account':'1200'},{'counter_account':'2200'},{'inclusive':'yes'},{'reference':''}):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):gst.post(self.s,values(**extra))
            self.assertEqual(self.s,before)
    def test_purchase_itc_and_registration_review_guards(self):
        for extra in ({'itc':'Not applicable'},{'counterparty_gstin':''},{'counterparty_gstin':OTHER,'place_of_supply':'32'}):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):self.purchase(**extra)
            self.assertEqual(self.s,before)
        self.s['branches']['JP']['state_code']='32'
        with self.assertRaises(ValueError):gst.post(self.s,values())
    def test_unreviewed_rule_and_zero_rated_workflow_rejected(self):
        for key,rate,treatment,reviewed in [('UNREVIEWED','18','Taxable',False),('EXPORT','0','Zero rated',True)]:
            tax.save_rule(self.s,dict(family='GST',key=key,effective='2026-04-01',label=key,rate=rate,treatment=treatment,reviewed=reviewed,source='Test',applicability='Test'))
            with self.assertRaises(ValueError):gst.post(self.s,values(rule_key=key))
    def test_duplicate_invoice_and_period_lock_do_not_post_partial(self):
        gst.post(self.s,values());before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):gst.post(self.s,values(reference='test/1'))
        self.assertEqual(before,self.s)
        foundation.lock_period(self.s,'2026-04-30');before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):gst.post(self.s,values(reference='NEW'))
        self.assertEqual(before,self.s)
    def test_rule_snapshot_survives_later_correction(self):
        d=gst.post(self.s,values());r=copy.deepcopy(d['rule']);r['rate']='12';tax.save_rule(self.s,r)
        self.assertEqual(gst.summary(self.s,'2026-04-01','2026-04-30')['totals']['output_cgst'],900)
        self.assertEqual(self.s['gst_documents'][0]['rule']['rate'],'18')
    def test_reversal_in_later_period_and_reversal_of_reversal(self):
        d=gst.post(self.s,values());r=core.reverse(self.s,d['voucher_id'],'2026-05-02')
        self.assertEqual(gst.summary(self.s,'2026-04-01','2026-04-30')['totals']['sales_base'],10000)
        self.assertEqual(gst.summary(self.s,'2026-05-01','2026-05-31')['totals']['sales_base'],-10000)
        core.reverse(self.s,r['id'],'2026-06-02')
        all=gst.summary(self.s,'2026-04-01','2026-06-30');self.assertEqual(all['totals']['sales_base'],10000);self.assertFalse(any(all['unclassified'].values()))
    def test_manual_tax_and_openings_disclosed_separately(self):
        core.post(self.s,'2026-04-01','Test opening',[dict(account='1200',branch='JP',debit=10000,credit=0),dict(account='3000',branch='JP',debit=0,credit=10000)],opening=True)
        core.post(self.s,'2026-04-02','Manual input tax',[dict(account='1200',branch='JP',debit=100,credit=0),dict(account='1010',branch='JP',debit=0,credit=100)])
        r=gst.summary(self.s,'2026-04-01','2026-04-30');self.assertEqual(r['opening_balances']['1200'],10000);self.assertEqual(r['unclassified']['1200'],100);self.assertEqual(r['closing_balances']['1200'],10100)
    def test_branch_scope_and_multiple_registrations(self):
        gst.post(self.s,values());gst.post(self.s,values(branch='KM',reference='TEST-2',registration=OTHER,place_of_supply='32'))
        self.assertEqual(len(gst.summary(self.s,'2026-04-01','2026-04-30')['turnover']),2)
        self.assertEqual(len(gst.summary(self.s,'2026-04-01','2026-04-30','JP')['documents']),1)
    def test_2b_import_exact_matching_and_undo_never_post(self):
        d=self.purchase();imp=gst.import_2b(self.s,self.raw2b(),'2b.csv',OUR,'2026-04');before=len(self.s['vouchers'])
        self.assertEqual(gst.candidates_2b(self.s,imp['id'])[0]['candidates'][0]['status'],'Exact')
        m=gst.match_2b(self.s,imp['id'],imp['rows'][0]['id'],d['id']);self.assertEqual(gst.candidates_2b(self.s,imp['id'])[0]['status'],'Matched')
        with self.assertRaises(ValueError):gst.match_2b(self.s,imp['id'],imp['rows'][0]['id'],d['id'])
        gst.unmatch_2b(self.s,m['id'],'Test review');self.assertEqual(len(self.s['vouchers']),before);core.verify_audit(self.s)
    def test_2b_mismatches_and_availability_not_inferred(self):
        d=self.purchase();imp=gst.import_2b(self.s,self.raw2b(cgst='8',sgst='8'),'2b.csv',OUR,'2026-04')
        self.assertEqual(gst.candidates_2b(self.s,imp['id'])[0]['candidates'][0]['status'],'Date/amount mismatch')
        with self.assertRaises(ValueError):gst.match_2b(self.s,imp['id'],imp['rows'][0]['id'],d['id'])
        other=gst.import_2b(self.s,self.raw2b(available='N'),'2b-may.csv',OUR,'2026-05');m=gst.match_2b(self.s,other['id'],other['rows'][0]['id'],d['id'])
        self.assertEqual(m['itc_available'],'N');self.assertEqual(self.s['gst_documents'][0]['itc'],'Eligible')
    def test_2b_invalid_and_duplicate_imports_atomic(self):
        gst.import_2b(self.s,self.raw2b(),'2b.csv',OUR,'2026-04');before=copy.deepcopy(self.s)
        for raw in (self.raw2b(),self.raw2b(base='=1+1'),self.raw2b(invoice='OTHER',base='-100'),self.raw2b(invoice='OTHER',igst='18'),self.raw2b(invoice='OTHER',available='?')):
            with self.assertRaises(ValueError):gst.import_2b(self.s,raw,'bad.csv',OUR,'2026-04')
            self.assertEqual(self.s,before)
    def test_2b_xlsx_import_and_two_way_missing_review(self):
        self.purchase();w=Workbook();ws=w.active;ws.append(['supplier_gstin','invoice','date','taxable','cgst','sgst','igst','itc_available']);ws.append([LOCAL,'NOT-IN-BOOKS','2026-04-03',200,18,18,0,'Y']);out=io.BytesIO();w.save(out);w.close()
        imp=gst.import_2b(self.s,out.getvalue(),'test.xlsx',OUR,'2026-04');r=gst.review_2b(self.s,imp['id'])
        self.assertEqual(r['rows'][0]['status'],'Missing in books');self.assertEqual(len(r['book_invoices_without_2b']),1)
    def test_reversing_a_linked_invoice_flags_review(self):
        d=self.purchase();imp=gst.import_2b(self.s,self.raw2b(),'2b.csv',OUR,'2026-04');gst.match_2b(self.s,imp['id'],imp['rows'][0]['id'],d['id'])
        core.reverse(self.s,d['voucher_id'],'2026-05-01');self.assertIn('reversed',gst.candidates_2b(self.s,imp['id'])[0]['status'])
    def test_format_five_upgrade_and_export_preserve_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ext=root/'external';ext.mkdir();old=copy.deepcopy(self.s);old['version']=5;old['schema_revision']=5
            for key in ('gst_documents','gst_2b_imports','gst_2b_matches'):old.pop(key)
            history.checkpoint(old);p=root/'old.json';p.write_text(json.dumps(old));raw=p.read_bytes();v=Vault(p,demo=True);new=v.load()
            new['settings']['backup_dir']=str(ext);v.save(new);self.assertEqual(v.last_upgrade_backup.read_bytes(),raw)
            gst.post(new,values());v.save(new);self.assertEqual(v.load(),new)
            report=gst.summary(new,'2026-04-01','2026-04-30');before=copy.deepcopy(new);gst.export_report(report,root/'report.json');self.assertEqual(before,new)

    def test_void_unused_2b_retains_history_and_allows_reimport(self):
        d=self.purchase();raw=self.raw2b();item=gst.import_2b(self.s,raw,'2b.csv',OUR,'2026-04');match=gst.match_2b(self.s,item['id'],item['rows'][0]['id'],d['id'])
        with self.assertRaises(ValueError):gst.void_2b(self.s,item['id'],'Wrong period')
        gst.unmatch_2b(self.s,match['id'],'Wrong period');gst.void_2b(self.s,item['id'],'Wrong period')
        with self.assertRaises(ValueError):gst.match_2b(self.s,item['id'],item['rows'][0]['id'],d['id'])
        new=gst.import_2b(self.s,raw,'2b.csv',OUR,'2026-04');self.assertNotEqual(item['id'],new['id']);self.assertEqual(len(self.s['gst_2b_imports']),2);core.verify_audit(self.s)

    def test_2b_multiple_period_link_cannot_reuse_book_invoice(self):
        d=self.purchase();a=gst.import_2b(self.s,self.raw2b(),'a.csv',OUR,'2026-04');gst.match_2b(self.s,a['id'],a['rows'][0]['id'],d['id'])
        b=gst.import_2b(self.s,self.raw2b(),'b.csv',OUR,'2026-05');row=gst.candidates_2b(self.s,b['id'])[0]
        self.assertEqual(row['candidates'][0]['status'],'Already linked elsewhere')
        with self.assertRaises(ValueError):gst.match_2b(self.s,b['id'],b['rows'][0]['id'],d['id'])

    def test_csv_export_proofs_and_formula_safety_are_readonly(self):
        gst.post(self.s,values(reference='=HYPERLINK("bad")'));before=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'gst.csv';gst.export_csv(gst.summary(self.s,'2026-04-01','2026-04-30'),p)
            text=p.read_text(encoding='utf-8-sig');self.assertIn("'=HYPERLINK",text);self.assertIn('118.00',text);self.assertIn('Unclassified/manual movement',text)
        self.assertEqual(before,self.s)

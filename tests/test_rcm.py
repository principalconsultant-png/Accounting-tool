import copy
import json
from pathlib import Path
import tempfile
import unittest
from riju import core,tax,gst,rcm,foundation,history
from riju.storage import Vault
from test_gst import OUR,LOCAL,values


class RcmTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state();tax.save_rule(self.s,dict(family='GST',key='TEST-RCM',effective='2026-04-01',label='Synthetic RCM rate',rate='18',treatment='Taxable',hsn_sac='999311',applicability='Invented tests only',source='Synthetic reference',reviewed=True))
    def purchase(self,**extra):
        v=dict(date='2026-04-02',branch='JP',registration=OUR,reference='RCM-1',narration='Invented RCM purchase',rule_key='TEST-RCM',rcm_basis='Invented applicability test',supplier_name='Test supplier',supplier_gstin='',supplier_state='29',place_of_supply='29',amount='100',account='4590',counter_account='2000',claim_expected=True,confirmed=True);v.update(extra);return rcm.post(self.s,'Purchase',v)
    def deposit(self,**extra):
        v=dict(date='2026-04-03',branch='JP',registration=OUR,reference='CIN-1',narration='Synthetic cash deposit',bank_account='1010',cgst='9',sgst='9',igst='0',confirmed=True);v.update(extra);return rcm.post(self.s,'Deposit',v)
    def action(self,stage,purchase,**extra):
        v=dict(date='2026-04-04' if stage=='Discharge' else '2026-04-05',purchase_id=purchase['id'],reference='UTIL-1' if stage=='Discharge' else 'ITC-1',narration='Reviewed synthetic '+stage,eligibility_reviewed=True,confirmed=True);v.update(extra);return rcm.post(self.s,stage,v)
    def test_complete_stages_and_input_summary_proof(self):
        p=self.purchase();mapping=self.s['gst_rcm_ledgers'];balances=core.balances(self.s,'2026-04-30')
        self.assertEqual(balances['4590'],10000);self.assertEqual(balances[mapping['pending']],1800);self.assertEqual(balances['1200'],0)
        self.deposit();self.action('Discharge',p);self.action('Claim',p)
        b=core.balances(self.s,'2026-04-30');self.assertEqual(b[mapping['pending']],0);self.assertEqual(b[mapping['payable_cgst']],0);self.assertEqual(b['1200'],900)
        report=gst.summary(self.s,'2026-04-01','2026-04-30');self.assertEqual(report['totals']['input_cgst'],900);self.assertFalse(any(report['unclassified'].values()));self.assertFalse(any(rcm.report(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
    def test_deposit_alone_does_not_discharge_or_allow_itc(self):
        p=self.purchase();self.deposit();before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.action('Claim',p)
        self.assertEqual(before,self.s);self.assertEqual(core.balances(self.s,'2026-04-30')[self.s['gst_rcm_ledgers']['payable_cgst']],-900)
    def test_ineligible_tax_is_cost_and_cannot_be_claimed(self):
        p=self.purchase(claim_expected=False);self.assertEqual(core.balances(self.s,'2026-04-30')['4590'],11800)
        self.deposit();self.action('Discharge',p)
        with self.assertRaises(ValueError):self.action('Claim',p)
    def test_cash_components_and_registration_cannot_be_interchanged(self):
        p=self.purchase();self.deposit(cgst='18',sgst='0')
        with self.assertRaises(ValueError):self.action('Discharge',p)
        other=self.purchase(branch='KM',reference='OTHER')
        with self.assertRaises(ValueError):self.action('Discharge',other)
    def test_cash_for_another_registration_in_same_branch_cannot_be_used(self):
        p=self.purchase();self.deposit(registration='32ABCDE1234F1Z5')
        with self.assertRaises(ValueError):self.action('Discharge',p)
    def test_multiple_deposits_can_fund_one_full_discharge(self):
        p=self.purchase();self.deposit(cgst='4',sgst='4');self.deposit(reference='CIN-2',cgst='5',sgst='5');self.action('Discharge',p)
    def test_reverse_dependencies_in_order_and_restore_input_proof(self):
        p=self.purchase();d=self.deposit();settled=self.action('Discharge',p);claim=self.action('Claim',p)
        for v in (p,d,settled):
            with self.assertRaises(ValueError):core.reverse(self.s,v['voucher_id'],'2026-04-06')
        core.reverse(self.s,claim['voucher_id'],'2026-04-06');core.reverse(self.s,settled['voucher_id'],'2026-04-06');core.reverse(self.s,d['voucher_id'],'2026-04-06');core.reverse(self.s,p['voucher_id'],'2026-04-06')
        self.assertEqual(gst.summary(self.s,'2026-04-01','2026-04-30')['totals']['input_cgst'],0);core.verify_audit(self.s)
    def test_duplicates_and_backdated_claim_are_atomic(self):
        p=self.purchase();self.deposit();self.action('Discharge',p)
        for stage,values_ in [('Purchase',{}),('Deposit',{}),('Discharge',{}),('Claim',{'date':'2026-04-03'}),('Claim',{'eligibility_reviewed':False})]:
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):
                if stage=='Purchase':self.purchase()
                elif stage=='Deposit':self.deposit()
                else:self.action(stage,p,**values_)
            self.assertEqual(before,self.s)
        self.action('Claim',p)
        with self.assertRaises(ValueError):self.action('Claim',p)
    def test_backdated_allocation_cannot_spend_future_reserved_cash(self):
        first=self.purchase();second=self.purchase(reference='RCM-2');self.deposit(date='2026-04-03');self.action('Discharge',first,date='2026-04-10')
        with self.assertRaises(ValueError):self.action('Discharge',second,date='2026-04-05')
    def test_interstate_and_supplier_validation(self):
        p=self.purchase(supplier_state='32');self.assertEqual(p['amounts']['igst'],1800)
        with self.assertRaises(ValueError):self.purchase(reference='BAD',supplier_gstin=LOCAL,supplier_state='32')
        with self.assertRaises(ValueError):self.purchase(reference='BAD',supplier_name='')
    def test_preview_is_readonly_and_controls_do_not_reuse_existing_codes(self):
        foundation.save_account(self.s,'1180','Client existing asset','Asset','Other assets');before=copy.deepcopy(self.s)
        values_=dict(date='2026-04-03',branch='JP',registration=OUR,reference='CIN',narration='Test',bank_account='1010',cgst='1')
        result=rcm.prepare(self.s,'Deposit',values_);self.assertEqual(before,self.s);self.assertNotIn('1180',result['control_ledgers'].values())
        self.deposit();code=self.s['gst_rcm_ledgers']['pending']
        with self.assertRaises(ValueError):foundation.save_account(self.s,code,'Pending','Asset','Other assets',active=False)
    def test_unknown_rules_locks_and_approval_do_not_create_masters(self):
        for change in ({'confirmed':False},{'rcm_basis':''},{'rule_key':'MISSING'}):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):self.purchase(**change)
            self.assertEqual(before,self.s)
        foundation.lock_period(self.s,'2026-04-30');before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.purchase()
        self.assertEqual(before,self.s)
    def test_same_registered_invoice_cannot_be_forward_and_reverse_charge(self):
        p=self.purchase(supplier_gstin=LOCAL)
        with self.assertRaises(ValueError):gst.post(self.s,values(rule_key='TEST-RCM',kind='Purchase',account='4590',counterparty_gstin=LOCAL,reference=p['reference'],itc='Eligible'))
    def test_unregistered_suppliers_with_same_invoice_number_are_distinct(self):
        self.purchase(supplier_name='Supplier A');self.purchase(supplier_name='Supplier B')
    def test_format_eight_backup_migration_export_and_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ext=root/'external';ext.mkdir();old=copy.deepcopy(self.s);old['version']=8;old['schema_revision']=8;old.pop('gst_rcm_records');old.pop('gst_rcm_ledgers');history.checkpoint(old)
            p=root/'old.json';p.write_text(json.dumps(old));original=p.read_bytes();v=Vault(p,demo=True);self.s=v.load();self.s['settings']['backup_dir']=str(ext);v.save(self.s);self.assertEqual(v.last_upgrade_backup.read_bytes(),original)
            purchase=self.purchase();self.deposit();self.action('Discharge',purchase);self.action('Claim',purchase);v.save(self.s);self.assertEqual(v.load(),self.s)
            before=copy.deepcopy(self.s);rcm.export(rcm.report(self.s,'2026-04-01','2026-04-30'),root/'rcm.json');self.assertEqual(before,self.s)

    def test_outstanding_and_opening_closing_proof_carry_across_years(self):
        p=self.purchase();report=rcm.report(self.s,'2027-04-01','2028-03-31')
        code=self.s['gst_rcm_ledgers']['payable_cgst'];self.assertEqual(report['opening_balances'][code],-900);self.assertEqual(report['closing_balances'][code],-900);self.assertEqual(report['ledger_movements'][code],0)
        self.assertEqual(report['outstanding'][0]['itc_pending'],1800);self.assertEqual(report['outstanding'][0]['tax_due']['cgst'],900)
    def test_gst_2b_import_cannot_silently_drop_an_rcm_flag(self):
        raw=('supplier_gstin,invoice,date,taxable,cgst,sgst,igst,itc_available,rcm\n'+LOCAL+',P1,2026-04-02,100,9,9,0,Y,Y\n').encode();before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):gst.import_2b(self.s,raw,'rcm.csv',OUR,'2026-04')
        self.assertEqual(before,self.s)

    def test_history_traces_purchase_discharge_and_claim_backlinks(self):
        p=self.purchase();self.deposit();settled=self.action('Discharge',p);claim=self.action('Claim',p)
        self.assertEqual(claim['discharge_voucher_id'],settled['voucher_id']);self.assertEqual(claim['purchase_voucher_id'],p['voucher_id'])
        before=copy.deepcopy(self.s)
        for vid in (p['voucher_id'],settled['voucher_id'],claim['voucher_id']):self.assertEqual(len(history.trace_voucher(self.s,vid)['rcm_context']),3)
        self.assertEqual(before,self.s)

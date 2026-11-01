import copy
from pathlib import Path
import tempfile
import unittest
from riju import core,tax,gst,service_revenue as sr

class ServiceRevenueTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state()
        for key,rate,treatment in [('EX','0','Exempt'),('TX','18','Taxable')]:tax.save_rule(self.s,dict(family='GST',key=key,effective='2026-04-01',label='Synthetic',rate=rate,treatment=treatment,source='Invented test',applicability='Synthetic only',reviewed=True))
    def post(self,kind='Advance',**kw):
        v=dict(date='2026-04-01',reference='A',branch='JP',account='4010',rule_key='EX',amount='1000',payments={'1010':'1000'},basis='Synthetic actual source and tax review',reviewed=True)
        v.update(kw);return sr.post(self.s,kind,v)
    def bad(self,fn):
        old=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):fn()
        self.assertEqual(old,self.s)
    def test_advance_earned_and_refund_no_duplicate_revenue(self):
        a=self.post();self.post('Earn advance',source=a['id'],reference='E',amount='600');self.post('Refund advance',source=a['id'],reference='R',amount='400',payments={'1010':'400'})
        b=core.balances(self.s,'2026-04-30');self.assertEqual(b['2300'],0);self.assertEqual(b['4010'],-60000);self.assertEqual(b['1010'],60000);self.assertTrue(sr.report(self.s,'2026-04-01','2026-04-30')['ready'])
        self.bad(lambda:self.post('Earn advance',source=a['id'],reference='OVER',amount='1'))
    def test_bill_collection_cancellation_refund_shared_patient_control(self):
        a=self.post('Bill',payments={});self.post('Collect bill',source=a['id'],reference='C',amount='600',payments={'1000':'100','1110':'500'})
        self.post('Cancel bill',source=a['id'],reference='X',amount='700',payments={})
        self.bad(lambda:self.post('Collect bill',source=a['id'],reference='OVER',amount='1',payments={'1000':'1'}))
        self.post('Refund bill',source=a['id'],reference='R',amount='300',payments={'1010':'300'})
        self.assertEqual(core.balances(self.s,'2026-04-30')[self.s['patient_control']],0)
        self.bad(lambda:self.post('Refund bill',source=a['id'],reference='OVER2',amount='1',payments={'1010':'1'}))
    def test_taxed_advance_tax_once_at_receipt_then_refund_original_tax(self):
        a=self.post(rule_key='TX',registration='29ABCDE1234F1Z5',place_of_supply='29',payments={'1010':'1180'})
        self.post('Earn advance',source=a['id'],reference='E',amount='590');self.post('Refund advance',source=a['id'],reference='R',amount='590',payments={'1010':'590'})
        b=core.balances(self.s,'2026-04-30');self.assertEqual(b['4010'],-50000);self.assertEqual(b['2300'],0);self.assertEqual(b['2200'],-4500)
        result=gst.summary(self.s,'2026-04-01','2026-04-30');self.assertFalse(any(result['unclassified'].values()));self.assertEqual(result['totals']['sales_base'],50000)
    def test_taxed_bill_cancel_preserves_gst_proof(self):
        b=self.post('Bill',rule_key='TX',registration='29ABCDE1234F1Z5',place_of_supply='29',payments={});self.post('Cancel bill',source=b['id'],reference='X',amount='1180',payments={})
        self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()));self.assertEqual(core.balances(self.s,'2026-04-30')[self.s['patient_control']],0)
    def test_future_earning_blocks_backdated_reuse_and_parent_reversal(self):
        a=self.post();e=self.post('Earn advance',source=a['id'],reference='E',date='2026-06-01');self.bad(lambda:self.post('Refund advance',source=a['id'],reference='R',amount='1',payments={'1010':'1'}));self.bad(lambda:core.reverse(self.s,a['voucher'],'2026-06-02'))
        core.reverse(self.s,e['voucher'],'2026-06-02');core.reverse(self.s,a['voucher'],'2026-06-02');self.assertEqual(sr.remaining(self.s,a,'2026-06-01'),0)
    def test_later_rule_change_requires_tax_correction(self):
        a=self.post();tax.save_rule(self.s,dict(family='GST',key='EX',effective='2026-05-01',label='Changed synthetic',rate='18',treatment='Taxable',source='Test',applicability='Test',reviewed=True))
        self.bad(lambda:self.post('Earn advance',source=a['id'],reference='E',date='2026-05-01'))
    def test_duplicate_wrong_branch_unreviewed_payments_and_lock(self):
        a=self.post();self.bad(lambda:self.post());self.bad(lambda:self.post('Earn advance',source=a['id'],reference='E',branch='VK'));self.bad(lambda:self.post(reference='B',reviewed=False));self.bad(lambda:self.post(reference='B',payments={'1000':'1'}))
        self.s['locked_through']='2026-04-30';self.bad(lambda:self.post(reference='LOCK'))
    def test_direct_resort_earned_receipt_and_readonly_exports(self):
        r=self.post('Direct receipt',account='4040',payments={'1000':'200','1120':'800'});self.assertEqual(core.balances(self.s,'2026-04-30')['4040'],-100000)
        old=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            for kind in ('xlsx','pdf'):sr.export(self.s,'2026-04-01','2026-04-30','JP',Path(d)/('revenue.'+kind),kind)
        self.assertEqual(old,self.s)
    def test_existing_bill_source_link_does_not_repost_or_recount_gst(self):
        v=dict(date='2026-04-01',reference='OLD',branch='JP',account='4010',rule_key='EX',amount='1000',payments={},basis='Reviewed original bill',reviewed=True)
        source=core.post(self.s,'2026-04-01','Old bill',[dict(account=self.s['patient_control'],branch='JP',debit=100000,credit=0),dict(account='4010',branch='JP',debit=0,credit=100000)])
        r=sr.link_existing(self.s,'Bill',v,source['id']);self.assertEqual(len(self.s['vouchers']),1);self.assertEqual(len(self.s['gst_documents']),1);self.assertTrue(sr.report(self.s,'2026-04-01','2026-04-30')['ready'])
        self.post('Collect bill',source=r['id'],reference='C');self.assertEqual(core.balances(self.s,'2026-04-30')[self.s['patient_control']],0)
    def test_refund_precedes_cancellation_is_rejected(self):
        b=self.post('Bill');self.post('Collect bill',source=b['id'],reference='C')
        self.bad(lambda:self.post('Refund bill',source=b['id'],reference='R',amount='1',payments={'1000':'1'}))
    def test_rounding_components_close_to_original_tax_paise(self):
        a=self.post(rule_key='TX',registration='29ABCDE1234F1Z5',place_of_supply='29',amount='0.03',payments={'1000':'0.04'})
        self.post('Refund advance',source=a['id'],reference='R',amount='0.04',payments={'1000':'0.04'})
        self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
    def test_b08_cannot_create_unlinked_notes_for_service_sources(self):
        b=self.post('Bill')
        self.bad(lambda:gst.post_note(self.s,dict(original_document_id=b['gst_document'],date='2026-04-02',document_type='Credit note',reference='X',confirmed=True)))
    def test_earned_receipt_partial_refund_and_tax_proof(self):
        r=self.post('Direct receipt',rule_key='TX',registration='29ABCDE1234F1Z5',place_of_supply='29',payments={'1010':'1180'})
        refund=self.post('Refund earned receipt',source=r['id'],reference='REFUND',amount='590',payments={'1010':'590'})
        self.assertEqual(core.balances(self.s,'2026-04-30')['4010'],-50000);self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
        self.bad(lambda:self.post('Refund earned receipt',source=r['id'],reference='OVER',amount='591',payments={'1010':'591'}));self.bad(lambda:core.reverse(self.s,r['voucher'],'2026-04-02'))
        core.reverse(self.s,refund['voucher'],'2026-04-02');self.assertEqual(core.balances(self.s,'2026-04-30')['4010'],-100000)

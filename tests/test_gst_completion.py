import copy
import json
from pathlib import Path
import tempfile
import unittest
from riju import core,tax,gst,gst_extensions as ext,gst_payments as pay,gst_portal as portal,rcm

OUR='29ABCDE1234F1Z5';SUP='29ZZZZZ1234Z1Z5'
class GstCompletionTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state()
        for key,rate,treatment in [('G18','18','Taxable'),('G5','5','Taxable'),('EX','0','Exempt'),('LUT','0','Zero rated')]:tax.save_rule(self.s,dict(family='GST',key=key,label=key,effective='2026-04-01',rate=rate,treatment=treatment,applicability='Synthetic only',source='Synthetic reviewed',reviewed=True))
    def values(self,**kw):
        v=dict(kind='Sale',date='2026-04-02',branch='JP',registration=OUR,place_of_supply='29',counterparty_gstin='',reference='I1',rule_key='G18',amount='100',account='4000',counter_account='1010',itc='Not applicable',narration='Synthetic GST source',confirmed=True);v.update(kw);return v
    def bad(self,fn):
        old=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):fn()
        self.assertEqual(old,self.s)
    def action(self,kind,**kw):
        v=dict(date='2026-04-03',branch='JP',registration=OUR,reference=kind,narration='Synthetic actual GST evidence',confirmed=True,eligibility_reviewed=True);v.update(kw);return pay.post(self.s,kind,v)
    def purchase(self,**kw):return gst.post(self.s,self.values(kind='Purchase',counterparty_gstin=SUP,account='4590',counter_account='2000',itc='Eligible',**kw))
    def rcmp(self,**kw):
        v=dict(date='2026-04-02',branch='JP',registration=OUR,reference='RCM-P',narration='Synthetic source',rule_key='G18',rcm_basis='Synthetic reviewed RCM',supplier_name='Synthetic supplier',supplier_gstin=SUP,supplier_state='29',place_of_supply='29',amount='100',account='4590',counter_account='2000',claim_expected=True,confirmed=True);v.update(kw);return rcm.post(self.s,'Purchase',v)
    def raction(self,stage,p=None,**kw):
        v=dict(date='2026-04-03',reference=stage,narration='Synthetic actual stage',branch='JP',registration=OUR,confirmed=True,eligibility_reviewed=True,bank_account='1010');v.update(kw)
        if p:v['purchase_id']=p['id']
        return rcm.post(self.s,stage,v)
    def test_mixed_sale_taxable_exempt_numeric_totals_and_notes(self):
        d=ext.post_invoice(self.s,self.values(items=[dict(account='4000',rule_key='G18',amount='100'),dict(account='4010',rule_key='EX',amount='50')]))
        self.assertEqual(d['totals']['total'],16800);self.assertEqual(len(self.s['vouchers']),1);self.assertEqual(len(gst.register(self.s,'2026-04-01','2026-04-30')),1)
        n=gst.post_note(self.s,dict(original_document_id=d['id'],date='2026-04-03',document_type='Credit note',reference='CN1',counter_account='1010',narration='Synthetic cancellation',items=[dict(line_id=d['line_items'][0]['id'],amount='50')],confirmed=True))
        self.assertEqual(n['totals']['total'],5900);self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
        self.bad(lambda:gst.post_note(self.s,dict(original_document_id=d['id'],date='2026-04-03',document_type='Credit note',reference='OVER',counter_account='1010',narration='Too much',items=[dict(line_id=d['line_items'][0]['id'],amount='51')],confirmed=True)))
    def test_mixed_purchase_itc_eligibility_does_not_claim_ineligible_tax(self):
        d=ext.post_invoice(self.s,self.values(kind='Purchase',counterparty_gstin=SUP,counter_account='2000',items=[dict(account='4590',rule_key='G18',amount='100',itc='Eligible'),dict(account='4510',rule_key='G5',amount='100',itc='Ineligible')]))
        summary=gst.summary(self.s,'2026-04-01','2026-04-30');self.assertEqual(summary['totals']['input_cgst'],900);self.assertEqual(summary['totals']['ineligible_tax'],500);self.assertFalse(any(summary['unclassified'].values()))
    def test_export_lut_and_paid_igst_and_sez_require_evidence(self):
        self.bad(lambda:gst.post(self.s,self.values(rule_key='LUT')))
        d=gst.post(self.s,self.values(rule_key='LUT',supply_type='Export under LUT',export_reviewed=True,export_basis='Synthetic LUT and export source',country='US',place_of_supply='96'));self.assertEqual(d['totals']['total'],10000)
        d=gst.post(self.s,self.values(reference='EXPORT-TAX',supply_type='Export with IGST',export_reviewed=True,export_basis='Synthetic tax-paid export',country='US',place_of_supply='96'));self.assertEqual(d['totals']['igst'],1800)
        self.bad(lambda:gst.post(self.s,self.values(reference='SEZ',rule_key='LUT',supply_type='SEZ under LUT',export_reviewed=True,export_basis='Synthetic authorized operations')))
    def test_rcm_partial_discharge_claim_eligibility_and_source_proof(self):
        p=self.rcmp(eligible_percent='50');self.raction('Deposit',cgst='9',sgst='9');self.raction('Discharge',p,cgst='4.5',sgst='4.5');self.raction('Claim',p,cgst='4.5',sgst='4.5')
        pos=rcm.position(self.s,p,'2026-04-30');self.assertEqual(pos['claimed']['cgst'],450);self.assertEqual(rcm.report(self.s,'2026-04-01','2026-04-30')['outstanding'][0]['tax_due']['cgst'],450)
        self.bad(lambda:self.raction('Claim',p,reference='OVER',cgst='0.01'))
        self.raction('Eligibility',p,eligible_percent='100');self.raction('Discharge',p,reference='DIS2',cgst='4.5',sgst='4.5');self.raction('Claim',p,reference='CLAIM2',cgst='4.5',sgst='4.5');self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
    def test_rcm_credit_after_claim_requires_itc_reversal_and_recovers_overpaid_cash(self):
        p=self.rcmp();self.raction('Deposit',cgst='9',sgst='9');self.raction('Discharge',p);self.raction('Claim',p)
        self.bad(lambda:self.raction('Credit note',p,amount='50'))
        self.raction('Reverse ITC',p,cgst='4.5',sgst='4.5');self.raction('Credit note',p,amount='50');self.raction('Restore cash',p,cgst='4.5',sgst='4.5');self.raction('Cash refund',cgst='4.5',sgst='4.5')
        self.assertEqual(rcm.position(self.s,p,'2026-04-30')['tax']['cgst'],450);self.assertFalse(any(rcm.report(self.s,'2026-04-01','2026-04-30')['unclassified'].values()));self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
    def test_forward_cash_itc_utilisation_and_reverse_dependencies(self):
        gst.post(self.s,self.values());p=self.purchase(reference='P');self.action('ITC utilisation',from_component='cgst',to_component='cgst',amount='9');self.action('ITC utilisation',reference='USE-S',from_component='sgst',to_component='sgst',amount='9')
        self.assertEqual(pay.position(self.s,OUR,'JP','2026-04-30')['due']['cgst'],0);self.bad(lambda:core.reverse(self.s,p['voucher_id'],'2026-04-04'));self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
    def test_cash_funding_not_tax_payment_and_scope_reuse_guard(self):
        gst.post(self.s,self.values());self.action('Deposit',cgst='9',sgst='9');self.assertEqual(pay.position(self.s,OUR,'JP','2026-04-30')['due']['cgst'],900)
        self.action('Cash utilisation',cgst='9',sgst='9');self.bad(lambda:self.action('Cash refund',cgst='1'));self.bad(lambda:self.action('Cash utilisation',reference='OTHER-BRANCH',branch='VK',cgst='1'))
    def test_credit_cross_head_and_unfunded_uses_blocked(self):
        gst.post(self.s,self.values());self.purchase(reference='P');self.bad(lambda:self.action('ITC utilisation',from_component='cgst',to_component='sgst',amount='1'));self.bad(lambda:self.action('Cash utilisation',cgst='1'))
    def test_eligibility_reclassification_never_duplicates_purchase(self):
        d=self.purchase();self.action('ITC reclassification',document_id=d['id'],eligible_percent='50');self.assertEqual(core.balances(self.s,'2026-04-30')['4590'],10900);self.assertEqual(pay.position(self.s,OUR,'JP','2026-04-30')['credit']['cgst'],450)
        self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
    def test_portal_forward_and_rcm_sections_are_separated_and_matching_never_claims(self):
        d=self.purchase(reference='P');p=self.rcmp(reference='R')
        data={'data':{'gstin':OUR,'rtnprd':'042026','docdata':{'b2b':[{'ctin':SUP,'inv':[dict(inum='P',dt='02-04-2026',rev='N',itcavl='Y',items=[dict(txval=100,cgst=9,sgst=9,igst=0)]),dict(inum='R',dt='02-04-2026',rev='Y',itcavl='N',items=[dict(txval=100,cgst=9,sgst=9,igst=0)])]}]}}};raw=json.dumps(data).encode();before=len(self.s['vouchers']);imp=portal.import_json(self.s,raw,'portal.json',OUR,'2026-04','JP');self.assertTrue(imp['forward_import']);row=imp['rcm_rows'][0]
        portal.match_rcm(self.s,imp['id'],row['id'],p['id'],'Verified exact original portal source');self.assertEqual(len(self.s['vouchers']),before);self.assertEqual(row['itc_available'],'N');self.bad(lambda:portal.void_import(self.s,imp['id'],'Wrong file'))
        portal.match_rcm(self.s,imp['id'],row['id'],p['id'],'Undo reviewed source',undo=True);portal.void_import(self.s,imp['id'],'Wrong period source')
    def test_portal_unsupported_sections_or_missing_parent_never_silently_dropped(self):
        raw=json.dumps({'data':{'gstin':OUR,'rtnprd':'042026','docdata':{'impg':[{'x':1}]}}}).encode();self.bad(lambda:portal.import_json(self.s,raw,'portal.json',OUR,'2026-04','JP'))
    def test_reviewed_filing_snapshot_and_readonly_excel_pdf(self):
        gst.post(self.s,self.values());review=pay.review_filing(self.s,OUR,'JP','2026-04','Reviewed source proof and tax applicability',True,'Synthetic ARN only');self.assertEqual(review['status'],'Manually acknowledged filed');old=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            for kind in ('xlsx','pdf'):ext.export(self.s,'2026-04-01','2026-04-30','JP',Path(d)/('gst.'+kind),kind)
        self.assertEqual(old,self.s)
    def test_prior_year_tax_opening_source_is_allocated_once_without_new_journal(self):
        v=core.post(self.s,'2024-04-01','Synthetic opening',[dict(account='1200',branch='JP',debit=900,credit=0),dict(account='3000',branch='JP',debit=0,credit=900)],opening=True)
        self.action('Register opening',date='2024-04-01',source_voucher=v['id'],opening_input={'cgst':'9'});self.assertEqual(len(self.s['vouchers']),1);self.assertEqual(pay.position(self.s,OUR,'JP','2026-04-30')['credit']['cgst'],900)
        self.bad(lambda:self.action('Register opening',date='2024-04-01',reference='DUP',source_voucher=v['id'],opening_input={'cgst':'0.01'}))
    def test_cash_transfer_refund_and_future_use_cannot_be_reused(self):
        self.action('Deposit',cgst='10');self.action('Cash transfer',from_component='cgst',to_component='sgst',amount='3');self.action('Cash refund',date='2026-06-01',cgst='7')
        self.bad(lambda:self.action('Cash refund',reference='BACKDATED',cgst='0.01'));self.assertEqual(pay.position(self.s,OUR,'JP','2026-06-01')['cash']['sgst'],300)
    def test_rcm_and_forward_funding_reference_cannot_be_double_counted(self):
        self.action('Deposit',reference='BANK-1',cgst='9');self.bad(lambda:self.raction('Deposit',reference='BANK-1',cgst='9'))
    def test_filing_review_fingerprint_detects_backdated_source_changes(self):
        gst.post(self.s,self.values());review=pay.review_filing(self.s,OUR,'JP','2026-04','Synthetic review',True);self.assertEqual(review['review_fingerprint'],pay.period_fingerprint(self.s,OUR,'JP','2026-04')[0]);gst.post(self.s,self.values(reference='LATE',date='2026-04-10'));self.assertNotEqual(review['review_fingerprint'],pay.period_fingerprint(self.s,OUR,'JP','2026-04')[0])
    def test_multiline_reversal_does_not_restore_overused_line_capacity(self):
        d=ext.post_invoice(self.s,self.values(items=[dict(account='4000',rule_key='G18',amount='100'),dict(account='4010',rule_key='EX',amount='100')]))
        n=gst.post_note(self.s,dict(original_document_id=d['id'],date='2026-04-03',document_type='Credit note',reference='CN',counter_account='1010',narration='Synthetic',items=[dict(line_id=d['line_items'][0]['id'],amount='100')],confirmed=True));self.bad(lambda:core.reverse(self.s,d['voucher_id'],'2026-04-04'));core.reverse(self.s,n['voucher_id'],'2026-04-04');core.reverse(self.s,d['voucher_id'],'2026-04-04')
    def test_used_purchase_credit_note_can_create_reviewed_repayment_liability(self):
        gst.post(self.s,self.values());d=self.purchase(reference='P');self.action('ITC utilisation',from_component='cgst',to_component='cgst',amount='9');self.action('ITC utilisation',reference='SGST',from_component='sgst',to_component='sgst',amount='9')
        values=dict(original_document_id=d['id'],date='2026-04-04',document_type='Credit note',reference='USED-CN',amount='100',counter_account='2000',narration='Synthetic supplier credit after ITC use',confirmed=True)
        self.bad(lambda:gst.post_note(self.s,values));gst.post_note(self.s,dict(values,repay_used_itc=True,repayment_basis='Reviewed actual previously used ITC reversal payable'))
        self.assertEqual(pay.position(self.s,OUR,'JP','2026-04-30')['due']['cgst'],900);self.assertEqual(pay.position(self.s,OUR,'JP','2026-04-30')['credit']['cgst'],0);self.assertFalse(any(gst.summary(self.s,'2026-04-01','2026-04-30')['unclassified'].values()))
    def test_igst_credit_priority_and_effective_policy_snapshot(self):
        gst.post(self.s,self.values());gst.post(self.s,self.values(kind='Purchase',reference='IGST-P',counterparty_gstin='32ZZZZZ1234Z1Z5',account='4590',counter_account='2000',itc='Eligible'))
        self.purchase(reference='CGST-P');self.bad(lambda:self.action('ITC utilisation',from_component='cgst',to_component='cgst',amount='1'))
        record=self.action('ITC utilisation',from_component='igst',to_component='cgst',amount='9');self.assertEqual(record['utilisation_policy']['residual_order'],'Any')
        policy=pay.save_utilisation_policy(self.s,'2026-04-01',True,'SGST then CGST',True,'Reviewed year-specific governing source',True);self.assertEqual(policy['effective'],'2026-04-01')
    def test_historical_credit_order_requires_reviewed_policy(self):
        self.bad(lambda:pay.utilisation_policy(self.s,'2018-04-01','Unknown earlier-year policy'))
        pay.save_utilisation_policy(self.s,'2017-07-01',False,'CGST then SGST',True,'Synthetic explicitly reviewed historical rule source',True);self.assertEqual(pay.utilisation_policy(self.s,'2018-04-01','Test')['residual_order'],'CGST then SGST')
    def test_existing_cash_openings_bind_actual_control_ledgers_without_reposting(self):
        from riju import foundation
        mapping=dict(cgst='1188',sgst='1189',igst='1190')
        for part,code in mapping.items():foundation.save_account(self.s,code,'Synthetic cash '+part,'Asset','Other assets')
        pay.bind_cash_controls(self.s,OUR,mapping,'Reviewed actual opening cash controls',True)
        v=core.post(self.s,'2024-04-01','Electronic cash opening',[dict(account='1188',branch='JP',debit=1000,credit=0),dict(account='1189',branch='JP',debit=2000,credit=0),dict(account='3000',branch='JP',debit=0,credit=3000)],opening=True)
        self.action('Register opening',date='2024-04-01',source_voucher=v['id'],opening_cash={'cgst':'10','sgst':'20'});self.assertEqual(len(self.s['vouchers']),1);self.assertEqual(pay.position(self.s,OUR,'JP','2026-04-30')['cash']['sgst'],2000)
    def test_actual_manual_cash_difference_blocks_filing_review(self):
        self.action('Deposit',cgst='10');code=self.s['gst_cash_ledgers'][OUR]['cgst'];core.post(self.s,'2026-04-04','Manual cash difference',[dict(account=code,branch='JP',debit=100,credit=0),dict(account='1010',branch='JP',debit=0,credit=100)])
        self.bad(lambda:pay.review_filing(self.s,OUR,'JP','2026-04','Cannot hide manual cash',True))

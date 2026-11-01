import copy
import tempfile
from pathlib import Path
import unittest
from riju import core,fx,activity,foundation
from riju.storage import Vault
from riju.sales_import import stage_sales,approve_sales
from test_sales import workbook


def pair(dr='1000',cr='4000',amount=10000,branch='JP'):
    return [dict(account=dr,branch=branch,debit=amount,credit=0),dict(account=cr,branch=branch,debit=0,credit=amount)]


class FxTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state();fx.save_rate(self.s,'2026-06-01','USD','83','Bank advice 1 June')
    def receipt(self,**kwargs):
        args=dict(payment_date='2026-06-01',code='USD',foreign_amount='100',credit_account='4040',reference='PAY-1')
        args.update(kwargs);return fx.post_receipt(self.s,**args)
    def test_exact_date_rate_precision_and_atomic_csv(self):
        for code,amount in [('USD','0'),('USD','NaN'),('USD','83.123456789'),('ABC','83')]:
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):fx.save_rate(self.s,'2026-06-02',code,amount,'Source')
            self.assertEqual(self.s,before)
        with self.assertRaises(ValueError):fx.get_rate(self.s,'2026-06-02','USD')
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):fx.import_rates(self.s,'date,currency,inr_per_unit,source\n2026-06-02,EUR,91,Bank\n2026-06-03,USD,bad,Bank\n')
        self.assertEqual(self.s,before)
        self.assertEqual(len(fx.import_rates(self.s,'date,currency,inr_per_unit,source\n2026-06-02,EUR,91,Bank\n')),1)
    def test_converted_receipt_fee_gain_and_frozen_rate(self):
        v=self.receipt(gross_inr='8320',fees_inr='20')
        b=core.balances(self.s,'2026-06-30','VK')
        self.assertEqual(b['1010'],830000);self.assertEqual(b['4560'],2000);self.assertEqual(b['4040'],-830000)
        self.assertEqual(b[self.s['fx_ledgers']['gain']],-2000)
        original=copy.deepcopy(v)
        fx.save_rate(self.s,'2026-06-01','USD','84','Corrected advice')
        self.assertEqual(v,original);self.assertEqual(v['fx']['rate']['inr_per_unit'],'83')
        self.assertEqual(fx.get_rate(self.s,'2026-06-01','USD')['revision'],2)
        core.verify_audit(self.s)
    def test_duplicate_and_tampered_preview_blocked_atomically(self):
        self.receipt();before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.receipt()
        self.assertEqual(self.s,before)
        plan=fx.receipt_plan(self.s,payment_date='2026-06-01',code='USD',foreign_amount='100',credit_account='2300',reference='PAY-2')
        plan['fx']['inr_minor']+=1
        with self.assertRaises(ValueError):core.post(self.s,plan['date'],plan['narration'],plan['lines'],metadata=plan['metadata'],fx=plan['fx'])
        self.assertEqual(self.s,before)
        with self.assertRaises(ValueError):self.receipt(reference='PAY-3',fees_inr='8300')
        self.assertEqual(self.s,before)
    def test_advance_existing_bill_and_currency_minor_units(self):
        self.receipt(credit_account='2300')
        self.assertEqual(core.balances(self.s,'2026-06-30')['2300'],-830000)
        core.post(self.s,'2026-06-01','Existing resort bill',pair(self.s['patient_control'],'4040',800000,'VK'))
        with self.assertRaises(ValueError):self.receipt(credit_account=self.s['patient_control'],reference='BILL-SETTLE')
        self.receipt(credit_account=self.s['patient_control'],reference='BILL-SETTLE',bill_inr='8000')
        self.assertEqual(core.balances(self.s,'2026-06-30')[self.s['patient_control']],0)
        fx.save_rate(self.s,'2026-06-01','JPY','0.555','Bank')
        v=self.receipt(code='JPY',foreign_amount='1',reference='JPY-1');self.assertEqual(v['fx']['inr_minor'],56)
        with self.assertRaises(ValueError):self.receipt(code='JPY',foreign_amount='1.1',reference='JPY-BAD')
        fx.save_rate(self.s,'2026-06-01','KWD','270.12345678','Bank')
        v=self.receipt(code='KWD',foreign_amount='1.001',reference='KWD-1');self.assertEqual(v['fx']['foreign_amount'],'1.001')
    def test_hold_convert_moving_average_and_reversal(self):
        fx.create_foreign_account(self.s,'1012','USD bank Vaikom','USD')
        self.receipt(mode='held',foreign_account='1012')
        fx.save_rate(self.s,'2026-06-02','USD','85','Bank advice 2 June')
        self.receipt(payment_date='2026-06-02',reference='HOLD-2',mode='held',foreign_account='1012')
        self.assertEqual(fx.holding_balance(self.s,'1012')['inr_minor'],1680000)
        self.assertEqual(fx.holding_balance(self.s,'1012')['foreign_amount'],'200')
        converted=fx.post_conversion(self.s,payment_date='2026-06-03',foreign_account='1012',foreign_amount='50',bank_account='1010',gross_inr='4300',fees_inr='10',reference='CONVERT-1')
        self.assertEqual(converted['fx']['inr_minor'],420000)
        b=fx.holding_balance(self.s,'1012');self.assertEqual((b['foreign_amount'],b['inr_minor']),('150',1260000))
        with self.assertRaises(ValueError):self.receipt(payment_date='2026-06-01',reference='BACKDATE',mode='held',foreign_account='1012')
        core.reverse(self.s,converted['id'],'2026-06-04')
        self.assertEqual(fx.holding_balance(self.s,'1012')['foreign_amount'],'200')
        with self.assertRaises(ValueError):core.post(self.s,'2026-06-05','Untracked foreign cash',pair('1012','4040',100,'VK'))
        with self.assertRaises(ValueError):fx.post_conversion(self.s,payment_date='2026-06-05',foreign_account='1012',foreign_amount='201',bank_account='1010',gross_inr='1',fees_inr='0',reference='TOO-MUCH')
        core.verify_audit(self.s)
    def test_full_conversion_clears_rounding_and_blocks_oversold_reversal(self):
        fx.create_foreign_account(self.s,'1012','USD bank Vaikom','USD');v=self.receipt(mode='held',foreign_account='1012')
        fx.post_conversion(self.s,payment_date='2026-06-02',foreign_account='1012',foreign_amount='100',bank_account='1010',gross_inr='8200',fees_inr='0',reference='FULL')
        b=fx.holding_balance(self.s,'1012');self.assertEqual((b['foreign_amount'],b['inr_minor']),('0',0))
        with self.assertRaises(ValueError):core.reverse(self.s,v['id'],'2026-06-03')
    def test_vault_upgrade_preserves_old_books_and_fx_roundtrip(self):
        self.receipt()
        with tempfile.TemporaryDirectory() as d:
            vault=Vault(Path(d)/'books.json',demo=True);vault.load();vault.save(self.s)
            self.assertEqual(vault.load(),self.s)
            report=activity.report(vault.load());self.assertEqual(report['metrics']['fx_receipts_posted'],1)


class ActivityTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def test_unique_drafts_posting_and_reversal_are_distinct_counts(self):
        d=foundation.save_draft(self.s,'2023-06-01','Receipt',pair())
        foundation.save_draft(self.s,'2023-06-01','Receipt edited',pair(),draft_id=d['id'])
        v=foundation.post_draft(self.s,d['id']);core.reverse(self.s,v['id'],'2023-06-02')
        m=activity.report(self.s)['metrics']
        self.assertEqual(m['saved_drafts_created'],1);self.assertEqual(m['drafts_pending'],0)
        self.assertEqual(m['business_transactions_posted'],1);self.assertEqual(m['journal_vouchers_posted'],2);self.assertEqual(m['journal_vouchers_created'],2)
        self.assertEqual(m['reversals_posted'],1);self.assertEqual(m['journal_lines_posted'],4)
        self.assertEqual(activity.report(self.s,'2023-04-01','2024-03-31',basis='work')['metrics']['journal_vouchers_posted'],0)
        self.assertEqual(activity.report(self.s,'2023-04-01','2024-03-31',basis='book')['metrics']['journal_vouchers_posted'],2)
    def test_imported_rows_not_added_twice_and_legacy_linking(self):
        q=stage_sales(self.s,workbook(),'sales.xlsx','JP');approve_sales(self.s,q['id'])
        m=activity.report(self.s)['metrics']
        self.assertEqual((m['business_transactions_posted'],m['import_rows_processed'],m['journal_vouchers_posted']),(1,1,1))
        with self.assertRaises(ValueError):approve_sales(self.s,q['id'])
        self.assertEqual(activity.report(self.s)['metrics'],m)
        # Legacy source fields can be absent while the original queue/narration still link the row.
        old=copy.deepcopy(self.s)
        for v in old['vouchers']:v.pop('source',None)
        # Rebuild audit legitimately for a synthetic old-format fixture.
        old['audit']=[]
        for v in old['vouchers']:core.add_audit(old,'POST',v)
        legacy=activity.report(old)['metrics'];self.assertEqual(legacy['import_rows_processed'],1)
    def test_opening_source_rows_and_cross_branch_count_entity_once(self):
        text='date,narration,branch,debit_account,credit_account,amount\n2023-04-01,Opening,JP,1010,3000,100\n2023-04-01,Opening,JP,1000,3000,100\n'
        foundation.import_openings(self.s,text)
        transfer=pair('1130','1000',100,'JP')+pair('1000','1130',100,'KM')
        core.post(self.s,'2023-06-01','Interbranch transfer',transfer)
        m=activity.report(self.s)['metrics'];self.assertEqual(m['import_rows_processed'],2);self.assertEqual(m['opening_journals'],1);self.assertEqual(m['business_transactions_posted'],1)
        self.assertEqual(activity.report(self.s,branch='JP')['metrics']['business_transactions_posted'],1)
        self.assertEqual(activity.report(self.s,branch='KM')['metrics']['business_transactions_posted'],1)
    def test_bank_duplicate_attempts_and_anonymous_export(self):
        rows=[dict(date='2026-06-01',narration='Deposit',amount=10000,reference='B-1')]
        self.assertEqual(activity.import_bank_rows(self.s,rows,'JP','bank.csv'),1)
        self.assertEqual(activity.import_bank_rows(self.s,rows,'JP','bank.csv'),0)
        before=copy.deepcopy(self.s);r=activity.report(self.s)
        self.assertEqual(r['metrics']['bank_rows_imported'],1);self.assertEqual(r['metrics']['journal_vouchers_posted'],0)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'stats.csv';activity.export_csv(r,p)
            self.assertNotIn(self.s['settings']['entity'],p.read_text(encoding='utf-8-sig'))
        self.assertEqual(self.s,before)
    def test_india_dates_and_invalid_source(self):
        self.assertEqual(activity.india_day('2026-06-01T20:00:00+00:00'),'2026-06-02')
        self.assertIsNone(activity.india_day('2026-06-01T20:00:00'))
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):core.post(self.s,'2026-06-01','Invalid source',pair(),source={'row_count':999})
        self.assertEqual(self.s,before)

class NewFeatureEdgeTests(unittest.TestCase):
    def test_fx_gain_account_collision_and_reversal_chain(self):
        s=core.empty_state();foundation.save_account(s,'4160','Client custom revenue','Revenue','Other revenue')
        fx.save_rate(s,'2026-06-01','USD','83','Bank')
        args=dict(payment_date='2026-06-01',code='USD',foreign_amount='100',credit_account='4040',reference='FX-CHAIN',gross_inr='8400')
        v=fx.post_receipt(s,**args);self.assertNotEqual(s['fx_ledgers']['gain'],'4160')
        self.assertEqual(next(a['name'] for a in s['accounts'] if a['code']=='4160'),'Client custom revenue')
        reversal=core.reverse(s,v['id'],'2026-06-02');core.reverse(s,reversal['id'],'2026-06-03')
        with self.assertRaises(ValueError):fx.post_receipt(s,**args)
        core.verify_audit(s)
    def test_schema_two_upgrade_backup_and_posted_history(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            old=core.empty_state();core.post(old,'2026-06-01','Legacy sale',pair())
            old.update(version=2,schema_revision=2)
            for key in ('fx_rates','foreign_accounts','fx_ledgers'):old.pop(key,None)
            p=Path(d)/'legacy.json';p.write_text(json.dumps(old));original=p.read_bytes();v=Vault(p,demo=True);new=v.load()
            self.assertTrue(v.migration_pending);self.assertEqual(new['vouchers'],old['vouchers']);self.assertEqual(new['version'],18)
            with self.assertRaises(ValueError):v.save(new)
            external=Path(d)/'external';external.mkdir();new['settings']['backup_dir']=str(external);v.save(new)
            self.assertEqual(v.last_upgrade_backup.read_bytes(),original)
            self.assertEqual(activity.report(v.load())['metrics']['journal_vouchers_posted'],1)
    def test_source_duplicates_blocked_and_legacy_ambiguity_disclosed(self):
        s=core.empty_state();source=dict(kind='journal_csv',document_id='DOC-1',record_id='ROW-1',row_count=1)
        core.post(s,'2026-06-01','Rent',pair('4530','1010'),source=source)
        before=copy.deepcopy(s)
        with self.assertRaises(ValueError):core.post(s,'2026-06-01','Rent',pair('4530','1010'),source=source)
        self.assertEqual(s,before)
        # Ambiguous old records are coverage warnings, never guessed as processed work.
        s=core.empty_state()
        for _ in range(2):core.post(s,'2026-06-01','Rent',pair('4530','1010'))
        s['queue'].append(dict(id='old',status='PROCESSED',rows=[dict(date='2026-06-01',branch='JP',narration='Rent',debit_account='4530',credit_account='1010',amount=10000)]))
        m=activity.report(s)['metrics'];self.assertEqual(m['import_rows_processed'],0);self.assertEqual(m['legacy_rows_unlinked'],1)

class SettlementVolumeTests(unittest.TestCase):
    def test_settlement_not_a_second_business_receipt_and_work_date_coverage(self):
        s=core.empty_state()
        core.post(s,'2026-06-01','UPI sale',pair('1110','4000',10000))
        activity.import_bank_rows(s,[dict(date='2026-06-02',narration='UPI settlement',amount=9800,reference='BANK-1')],'JP','bank.csv')
        bank=s['bank_lines'][0]
        v=core.post(s,'2026-06-02','Settlement BANK-1',[dict(account='1010',branch='JP',debit=9800,credit=0),dict(account='4560',branch='JP',debit=200,credit=0),dict(account='1110',branch='JP',debit=0,credit=10000)])
        bank['status']='MATCHED';s['matches'].append(dict(bank_id=bank['id'],posting=v['id'],vouchers=[s['vouchers'][0]['id']]))
        m=activity.report(s)['metrics']
        self.assertEqual(m['business_transactions_posted'],1);self.assertEqual(m['journal_vouchers_posted'],2)
        self.assertEqual(m['bank_rows_imported'],1);self.assertEqual(m['bank_rows_matched'],1);self.assertEqual(m['settlement_journals'],1)
        today=activity.india_day(s['audit'][-1]['timestamp'])
        self.assertEqual(activity.report(s,today,today)['metrics']['bank_rows_matched'],1)
        s['bank_lines'][0].pop('imported_at')
        self.assertEqual(activity.report(s,today,today)['metrics']['bank_rows_imported'],0)
        self.assertEqual(activity.report(s,today,today)['metrics']['undated_bank_imports'],1)
        self.assertEqual(activity.report(s,'2026-06-01','2026-06-30',basis='book')['metrics']['bank_rows_imported'],1)

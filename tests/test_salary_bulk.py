import copy,csv,io,os,tempfile,unittest
from pathlib import Path
from riju import core,payroll_accounts as payroll,salary_bulk as salary,bulk_import as bulk
from test_bank_reconciliation import pair

def record(**kw):
    r=dict.fromkeys(salary.FIELDS,'');r.update(event='ACCRUAL',month='2026-04',branch='JP',amount='1000',basis='Approved payroll; no deductions');r.update(kw);return r

def source(rows):
    out=io.StringIO();w=csv.writer(out);w.writerow(salary.HEADERS);w.writerows([[r[k] for k in salary.FIELDS] for r in rows]);return out.getvalue().encode()

class SalaryBulkTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state();payroll.setup(self.s,payroll.choices(self.s),'Reviewed roles',True);self.m=self.s['settings']['payroll_ledgers'];core.post(self.s,'2026-04-01','Opening bank',pair('1010','3000',5000000),opening=True)
    def payrow(self,**kw):
        r=record(event='PAYMENT',date='2026-05-05',reference='SYN-PAY1',bank='1010');r.update(kw);return r
    def stage(self,rows):return salary.stage(self.s,source(rows),'salary.csv')
    def approve(self,q):
        for i,r in enumerate(q['rows']):bulk.review_row(self.s,q['id'],i,r['review']=='PENDING','Reviewed payroll and bank')
    def post(self,rows):q=self.stage(rows);self.approve(q);return bulk.approve(self.s,q['id'])
    def test_one_month_multiple_payments_unsorted_sources_correct_dates_reports(self):
        rows=[self.payrow(amount='300',reference='P2',date='2026-05-05'),record(),self.payrow(amount='200',reference='P1',date='2026-05-01'),self.payrow(amount='500',reference='P3',date='2026-05-07')];self.post(rows);self.assertEqual(core.balances(self.s,'2026-05-31')[self.m['salary_payable']],0);self.assertEqual(core.balances(self.s,'2026-05-31')[self.m['salary_expense']],100000);self.assertEqual(core.balances(self.s,'2026-05-31')['1010'],4900000);self.assertEqual([v['date'] for v in self.s['vouchers'][1:]],['2026-04-30','2026-05-01','2026-05-05','2026-05-07']);salary.check(self.s)
        from riju import daily_consolidation
        daily_consolidation.refresh(self.s,'2026-04-30','2026-05-07');data=daily_consolidation.pack(self.s,'2026-04-30','2026-05-07')['rows'];self.assertEqual(data[0][4],100000);self.assertEqual(sum(r[4] for r in data[1:]),0)
    def test_partial_payment_stays_payable(self):
        self.post([record(),self.payrow(amount='700')]);self.assertEqual(core.balances(self.s,'2026-05-31')[self.m['salary_payable']],-30000)
    def test_overpayment_and_payment_before_accrual_roll_back_entire_batch(self):
        for payment in [self.payrow(amount='1001'),self.payrow(date='2026-04-29')]:
            q=self.stage([record(),payment]);self.approve(q);before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):bulk.approve(self.s,q['id'])
            self.assertEqual(before,self.s);bulk.cancel(self.s,q['id'],'Correct source')
    def test_existing_accrual_and_payment_link_no_second_journal(self):
        accrual=core.post(self.s,'2026-04-30','Existing payroll',pair(self.m['salary_expense'],self.m['salary_payable'],100000),metadata={'reference':'ACCR-OLD'});payment=core.post(self.s,'2026-05-05','Existing salary payment',pair(self.m['salary_payable'],'1010',100000),metadata={'reference':'SYN-PAY1','type':'Payment'});before=len(self.s['vouchers']);self.post([record(existing=accrual['id']),self.payrow(existing=payment['id'])]);self.assertEqual(len(self.s['vouchers']),before)
    def test_duplicate_changed_file_month_and_existing_bank_guard(self):
        self.post([record(),self.payrow()]);q=self.stage([record(reference='CHANGED-ACCR',amount='999'),self.payrow(reference='SYN-PAY1')]);self.assertTrue(all(r['review']=='INVALID' for r in q['rows']));self.assertIn('already',q['rows'][0]['error'])
        with self.assertRaises(ValueError):self.stage([record(),self.payrow()])
    def test_invalid_fields_formula_and_infile_duplicate(self):
        q=self.stage([record(basis=''),record(month='bad'),record(),record(reference='OTHER'),self.payrow(date='2026-05-05',amount='=1000')]);self.assertEqual([r['review'] for r in q['rows']],['INVALID','INVALID','PENDING','INVALID','INVALID'])
    def test_accrual_reversal_cannot_orphan_paid_month(self):
        ids=self.post([record(),self.payrow()]);before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):core.reverse(self.s,ids[0],'2026-05-06')
        self.assertEqual(before,self.s);core.reverse(self.s,ids[1],'2026-05-06');core.reverse(self.s,ids[0],'2026-05-06');salary.check(self.s)
    def test_existing_direct_expense_payment_is_not_posted_twice(self):
        core.post(self.s,'2026-04-30','Already expensed payroll',pair(self.m['salary_expense'],'1010',100000),metadata={'reference':'P1','type':'Payment'});q=self.stage([record()]);self.assertEqual(q['rows'][0]['review'],'INVALID');self.assertIn('Direct salary-expense',q['rows'][0]['error'])
    def test_existing_payments_deplete_payable_even_if_not_month_tagged(self):
        self.post([record()]);core.post(self.s,'2026-05-05','Manual payment',pair(self.m['salary_payable'],'1010',100000),metadata={'reference':'OLD'});q=self.stage([self.payrow(reference='NEW')]);self.approve(q);before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):bulk.approve(self.s,q['id'])
        self.assertEqual(before,self.s)
    def test_day_first_dates_and_calendar_errors(self):
        self.assertEqual(salary.entry_date('05/04/26'),'2026-04-05')
        self.assertEqual(salary.entry_date('18/04/2026'),'2026-04-18')
        with self.assertRaises(ValueError):salary.entry_date('31/04/26')
    def test_same_month_early_payments_apply_at_accrual_date(self):
        raw=source([record(),self.payrow(date='05/04/26',amount='600'),self.payrow(date='30/04/26',amount='400',reference='P2')])
        self.assertTrue(salary.has_early_payments(self.s,raw,'salary.csv'))
        q=salary.stage(self.s,raw,'salary.csv',advance_mode=True);self.assertTrue(all(r['review']=='PENDING' for r in q['rows']));self.approve(q);ids=bulk.approve(self.s,q['id']);self.assertEqual(len(ids),4)
        asset=self.s['settings']['salary_advance_ledger'];early=core.balances(self.s,'2026-04-05');self.assertEqual(early[asset],60000);self.assertEqual(early[self.m['salary_expense']],0)
        closing=core.balances(self.s,'2026-04-30');self.assertEqual(closing[asset],0);self.assertEqual(closing[self.m['salary_payable']],0);self.assertEqual(closing[self.m['salary_expense']],100000)
        from riju import business_pulse
        policy=business_pulse.policy(self.s);policy.update(salary_accounts=[self.m['salary_expense']],reviewed=True,basis='Reviewed salary cash outflow mapping');business_pulse.save_policy(self.s,policy)
        pulse=business_pulse.snapshot(self.s,2026,'2026-04-30');salary_row=next(r for r in pulse['rows'] if r['key']=='salary');self.assertEqual(salary_row['values'][0],100000)
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):core.reverse(self.s,bulk._queue(self.s,q['id'])['rows'][1]['voucher'],'2026-05-01')
        self.assertEqual(before,self.s);salary.check(self.s)
    def test_early_overpayment_rejected_atomically(self):
        q=salary.stage(self.s,source([record(),self.payrow(date='05/04/26',amount='1001')]),'salary.csv',advance_mode=True);self.approve(q);before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):bulk.approve(self.s,q['id'])
        self.assertEqual(before,self.s)

    def test_templates_and_persistence(self):
        from riju.storage import Vault
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as root:
            x=Path(root)/'salary.xlsx';salary.template(x,self.s);w=load_workbook(x);self.assertEqual(tuple(c.value for c in w['Salary Journals'][1]),salary.HEADERS);self.assertIn('Units',w.sheetnames);w.close();self.post([record(),self.payrow()]);v=Vault(Path(root)/'book.json',demo=True);v.save(self.s);salary.check(v.load())

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class SalaryBulkDesktopTests(unittest.TestCase):
    def test_journal_studio_salary_upload_review_preview_and_post(self):
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        from unittest.mock import patch
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as root:
            app=App(Vault(Path(root)/'book.json',demo=True))
            try:
                payroll.setup(app.state,payroll.choices(app.state),'Reviewed',True);app.refresh_masters();app.show('Journal studio');app.narration.insert('1.0','Unsaved manual draft stays here');path=Path(root)/'salary.csv';path.write_bytes(source([record(),record(event='PAYMENT',date='05/04/26',reference='GUI-PAY',bank='1010')]))
                with patch('riju.journal_bulk_ui.filedialog.askopenfilename',return_value=str(path)),patch('riju.journal_bulk_ui.messagebox.askyesnocancel',return_value=True):app.journal_bulk_upload(True)
                form=helper.form(app);self.assertFalse(app.state['vouchers'])
                for w in helper.walk(form):
                    if w.winfo_class()=='TCheckbutton':w.invoke()
                helper.press(form,'Approve all valid rows');helper.press(form,'Preview reviewed journals');preview=helper.form(form);self.assertFalse(app.state['vouchers'])
                with patch('riju.journal_bulk_ui.messagebox.showinfo'):helper.press(preview,'Confirm post reviewed JEs')
                self.assertEqual(len(app.state['vouchers']),3);self.assertIn('Unsaved manual draft',app.narration.get('1.0','end'))
            finally:app.destroy()

class GeneralJournalStudioTests(unittest.TestCase):
    def test_existing_general_bulk_salary_journals_link_without_reposting(self):
        case=SalaryBulkTests();case.setUp();s=case.s;m=case.m
        out=io.StringIO();w=csv.writer(out);w.writerow(bulk.FIELDS);w.writerow(['2026-04-30','A','JP','Payroll',m['salary_expense'],m['salary_payable'],'1000','']);w.writerow(['2026-05-05','P','JP','Payment',m['salary_payable'],'1010','1000',''])
        q=bulk.stage(s,out.getvalue().encode(),'general.csv','Journal')
        for i in range(2):bulk.review_row(s,q['id'],i,True,'Reviewed')
        ids=bulk.approve(s,q['id']);before=len(s['vouchers']);q=salary.stage(s,source([record(reference='A',existing=ids[0]),case.payrow(reference='P',existing=ids[1])]),'linked.csv')
        for i in range(2):bulk.review_row(s,q['id'],i,True,'Reviewed source links')
        bulk.approve(s,q['id']);self.assertEqual(len(s['vouchers']),before)
    def test_cancelled_pending_salary_batch_can_be_corrected_and_restaged(self):
        case=SalaryBulkTests();case.setUp();q=case.stage([record(),case.payrow(amount='1001')]);bulk.cancel(case.s,q['id'],'Correct payment total');replacement=case.stage([record(),case.payrow(amount='1000')]);self.assertTrue(all(r['review']=='PENDING' for r in replacement['rows']))

    def test_general_compound_je_template_and_group_post(self):
        from riju.journal_bulk_ui import general_template
        from openpyxl import load_workbook
        s=core.empty_state();out=io.StringIO();w=csv.writer(out);w.writerow(bulk.FIELDS);w.writerow(['2026-04-30','LINE1','JP','Reviewed compound','4590','2000','100','J1']);w.writerow(['2026-04-30','LINE2','JP','Reviewed compound','4530','2000','200','J1']);q=bulk.stage(s,out.getvalue().encode(),'general.csv','Journal')
        for i in range(2):bulk.review_row(s,q['id'],i,True,'Reviewed source')
        self.assertEqual(len(bulk.approve(s,q['id'])),1);self.assertEqual(core.balances(s,'2026-04-30')['2000'],-30000)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'general.xlsx';general_template(path);book=load_workbook(path);self.assertEqual(tuple(c.value for c in book['Journals'][1]),bulk.FIELDS);book.close()

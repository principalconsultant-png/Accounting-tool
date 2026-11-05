import copy,os,tempfile,unittest
from pathlib import Path
from riju import core,foundation,payroll_accounts as p,daily_consolidation as daily,business_pulse as pulse
from test_bank_reconciliation import pair

class PayrollLedgerTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def setup_roles(self):p.setup(self.s,p.choices(self.s),'Reviewed separate payroll ledgers',True);return self.s['settings']['payroll_ledgers']
    def test_five_distinct_ledgers_no_journal_idempotence_and_correct_groups(self):
        mapping=self.setup_roles();self.assertEqual(len(set(mapping.values())),5);self.assertFalse(self.s['vouchers']);before=copy.deepcopy(self.s['accounts']);self.setup_roles();self.assertEqual(before,self.s['accounts'])
        for role,code in mapping.items():self.assertTrue(any(a['code']==code for a in p.eligible(self.s,role)))
        self.assertEqual(next(a['name'] for a in self.s['accounts'] if a['code']=='4520'),'Employee benefits')
    def test_custom_code_conflict_never_renames_or_reuses(self):
        foundation.save_account(self.s,'4521','Existing staff overtime','Expense','Employee benefits');old=copy.deepcopy(next(a for a in self.s['accounts'] if a['code']=='4521'));mapping=self.setup_roles();self.assertNotEqual(mapping['salary_expense'],'4521');self.assertEqual(old,next(a for a in self.s['accounts'] if a['code']=='4521'))
    def test_reuse_existing_salary_master_and_block_shared_or_wrong_kind(self):
        foundation.save_account(self.s,'2310','Salaries payable','Liability','Other liabilities');selection=p.choices(self.s);self.assertEqual(selection['salary_payable'],'2310');self.setup_roles();self.assertEqual(sum(a['code']=='2310' for a in self.s['accounts']),1)
        for changes in (dict(salary_expense='1000'),dict(employer_pf_expense=self.s['settings']['payroll_ledgers']['salary_expense'])):
            choice=dict(p.choices(self.s),**changes);before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):p.setup(self.s,choice,'Reviewed',True)
            self.assertEqual(before,self.s)
    def test_group_and_deletion_references_protected(self):
        code=self.setup_roles()['salary_expense']
        with self.assertRaises(ValueError):foundation.save_account(self.s,code,'Salary','Expense','Finance costs')
        with self.assertRaises(ValueError):foundation.delete_account(self.s,code)
    def test_gross_salary_pf_accrual_and_remittance_reports_no_double_expense(self):
        m=self.setup_roles();core.post(self.s,'2026-04-01','Opening bank',pair('1010','3000',5000000),opening=True)
        core.post(self.s,'2026-04-30','Synthetic approved payroll',[dict(account=m['salary_expense'],branch='JP',debit=1000000,credit=0),dict(account=m['salary_payable'],branch='JP',debit=0,credit=900000),dict(account=m['employee_pf_payable'],branch='JP',debit=0,credit=100000)])
        core.post(self.s,'2026-04-30','Synthetic employer PF',pair(m['employer_pf_expense'],m['employer_pf_payable'],120000));core.post(self.s,'2026-05-05','Net salary payment',pair(m['salary_payable'],'1010',900000));core.post(self.s,'2026-05-15','Combined PF remittance',pair(m['employee_pf_payable'],'1010',100000)+pair(m['employer_pf_payable'],'1010',120000))
        daily.refresh(self.s,'2026-04-30','2026-05-15');rows=daily.pack(self.s,'2026-04-30','2026-05-15')['rows'];self.assertEqual(rows[0][4],1120000);self.assertEqual(sum(r[4] for r in rows[1:]),0);self.assertEqual(rows[-1][-1],3880000)
        policy=pulse.policy(self.s);policy.update(salary_accounts=[m['salary_expense'],m['salary_payable']],reviewed=True,basis='Review salary cash sources');pulse.save_policy(self.s,policy);report=pulse.snapshot(self.s,2026,'2026-05-31');salary=next(r for r in report['rows'] if r['key']=='salary');self.assertEqual(salary['values'][:2],[0,900000]);self.assertTrue(all(core.balances(self.s,'2026-05-31')[m[r]]==0 for r in ('salary_payable','employee_pf_payable','employer_pf_payable')))
    def test_salary_draft_uses_role_and_blocks_pf_or_duplicate_accrual(self):
        m=self.setup_roles();lines=core.parse_transaction('Paid salary INR100 by bank','JP','2026-04-02',self.s);self.assertEqual(lines[0]['account'],m['salary_expense'])
        from riju import offline_language
        result=offline_language.interpret(self.s,'Paid monthly employee payroll INR100 by bank','JP','2026-04-02');self.assertEqual(result['account'],m['salary_expense'])
        with self.assertRaises(ValueError):core.parse_transaction('Paid PF INR100 by bank','JP','2026-04-02',self.s)
        core.post(self.s,'2026-04-02','Salary accrual',pair(m['salary_expense'],m['salary_payable'],10000))
        with self.assertRaises(ValueError):core.parse_transaction('Paid salary INR100 by bank','JP','2026-04-03',self.s)
    def test_setup_confirmation_and_roundtrip(self):
        from riju.storage import Vault
        with self.assertRaises(ValueError):p.setup(self.s,p.choices(self.s),'',False)
        mapping=self.setup_roles()
        with tempfile.TemporaryDirectory() as root:
            v=Vault(Path(root)/'book.json',demo=True);v.save(self.s);self.assertEqual(v.load()['settings']['payroll_ledgers'],mapping)

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class PayrollLedgerDesktopTests(unittest.TestCase):
    def test_setup_preview_no_journal_then_confirm(self):
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        from unittest.mock import patch
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as root:
            app=App(Vault(Path(root)/'b.json',demo=True))
            try:
                app.show('Chart of accounts');app.payroll_ledger_setup();form=helper.form(app)
                for w in helper.walk(form):
                    if w.winfo_class()=='TCheckbutton':w.invoke()
                helper.press(form,'Preview ledger setup');preview=helper.form(form);self.assertNotIn('payroll_ledgers',app.state['settings']);self.assertFalse(app.state['vouchers'])
                with patch('riju.foundation_ui.messagebox.showinfo'):helper.press(preview,'Confirm ledger setup')
                self.assertEqual(len(app.state['settings']['payroll_ledgers']),5);self.assertFalse(app.state['vouchers'])
            finally:app.destroy()

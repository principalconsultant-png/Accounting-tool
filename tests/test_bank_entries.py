import copy,tempfile,unittest,os
from pathlib import Path
from riju import core,foundation,reconciliation as r,bank_entries as b
from test_bank_reconciliation import pair

class BankEntryTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def statement(self,n,scope='ALL'):
        debit,credit=(str(-n),0) if n<0 else (0,str(n))
        st=r.import_statement(self.s,f'date,narration,reference,debit,credit,balance\n2026-04-05,Synthetic entry,ENTRY1,{debit},{credit},{n}\n'.encode(),'bank.csv','1010',scope,'2026-04-01','2026-04-30','0',str(n));return st['row_ids'][0]
    def values(self,category,account,**kw):return dict(category=category,account=account,branch='JP',bank_account='1010',reviewed=True,basis='Synthetic evidence reviewed',**kw)
    def test_emi_split_exact_and_undo(self):
        core.post(self.s,'2026-04-01','Loan opening',pair('1010','2400',100000),opening=True);bid=self.statement(-110)
        result=b.record(self.s,bid,self.values('Loan repayment / EMI','2400',principal='100',interest='9',fees='1',interest_account='4580'));bal=core.balances(self.s,'2026-04-30');self.assertEqual([bal[a] for a in ('2400','4580','4560')],[-90000,900,100]);self.assertFalse(r.outstanding(self.s,'1010')[0]);r.undo_match(self.s,result['match'],'Reviewed undo','2026-04-06');self.assertEqual(core.balances(self.s,'2026-04-30')['2400'],-100000)
    def test_wrong_split_unfunded_principal_and_tax_controls_roll_back(self):
        bid=self.statement(-110);before=copy.deepcopy(self.s)
        for values in [self.values('Loan repayment / EMI','2400',principal='100',interest='10',fees='1'),self.values('Loan repayment / EMI','2400',principal='100',interest='9',fees='1'),self.values('Transfer to another person','2000'),self.values('Transfer to another person','2100')]:
            with self.assertRaises(ValueError):b.record(self.s,bid,values)
            self.assertEqual(before,self.s)
    def test_charges_and_reposting_guard(self):
        bid=self.statement(-10);b.record(self.s,bid,self.values('Bank / SMS / card charges','4560'));self.assertEqual(core.balances(self.s,'2026-04-30')['4560'],1000)
        with self.assertRaises(ValueError):b.record(self.s,bid,self.values('Bank / SMS / card charges','4560'))
    def test_cash_withdrawal_is_transfer_not_expense(self):
        bid=self.statement(-100);b.record(self.s,bid,self.values('Cash withdrawal','1000'));bal=core.balances(self.s,'2026-04-30');self.assertEqual(bal['1000'],10000);self.assertEqual(sum(bal[a['code']] for a in self.s['accounts'] if a['kind']=='Expense'),0)
    def test_cash_deposit_requires_existing_cash(self):
        bid=self.statement(100)
        with self.assertRaises(ValueError):b.record(self.s,bid,self.values('Cash deposit','1000'))
        core.post(self.s,'2026-04-01','Opening cash',pair('1000','3000',10000),opening=True);b.record(self.s,bid,self.values('Cash deposit','1000'));self.assertEqual(core.balances(self.s,'2026-04-30')['1000'],0)
    def test_own_bank_transfer_other_statement_matches_without_repost(self):
        foundation.save_account(self.s,'1015','Second bank','Asset','Cash and bank');bid=self.statement(-100);b.record(self.s,bid,self.values('Own-bank transfer','1015'));self.assertEqual(core.balances(self.s,'2026-04-30')['1015'],10000);self.assertEqual(len(r.outstanding(self.s,'1015')[1]),1)
        st=r.import_statement(self.s,b'date,narration,reference,debit,credit,balance\n2026-04-05,Own transfer,ENTRY1,0,100,100\n','second.csv','1015','ALL','2026-04-01','2026-04-30','0','100');count=len(self.s['vouchers']);r.match_existing(self.s,st['row_ids'],[r.outstanding(self.s,'1015')[1][0]['key']]);self.assertEqual(len(self.s['vouchers']),count)
    def test_loan_received_is_liability_and_loan_given_recovery_is_asset(self):
        bid=self.statement(100);b.record(self.s,bid,self.values('Loan proceeds received','2400'));self.assertEqual(core.balances(self.s,'2026-04-30')['2400'],-10000)
        self.s=core.empty_state();foundation.save_account(self.s,'1190','Loan receivable','Asset','Other assets');core.post(self.s,'2026-04-01','Opening advance',pair('1190','3000',10000),opening=True);bid=self.statement(100);b.record(self.s,bid,self.values('Loan given recovered','1190'));self.assertEqual(core.balances(self.s,'2026-04-30')['1190'],0)
    def test_scope_direction_confirmation_and_existing_reference(self):
        bid=self.statement(-100,'JP');before=copy.deepcopy(self.s)
        for change in (dict(branch='KM'),dict(reviewed=False),dict(category='Cash deposit'),dict(basis='')):
            v=self.values('Cash withdrawal','1000');v.update(change)
            with self.assertRaises(ValueError):b.record(self.s,bid,v)
            self.assertEqual(before,self.s)
        core.post(self.s,'2026-04-05','Existing payment',pair('4590','1010',10000),metadata={'reference':'ENTRY1','type':'Payment'})
        with self.assertRaisesRegex(ValueError,'existing book'):b.record(self.s,bid,self.values('Transfer to another person','4590'))

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class BankEntryDesktopTests(unittest.TestCase):
    def test_guided_charge_preview_and_confirm_from_workspace(self):
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        from unittest.mock import patch
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            app=App(Vault(Path(d)/'b.json',demo=True))
            try:
                st=r.import_statement(app.state,b'date,narration,reference,debit,credit,balance\n2026-04-05,SMS charge,SMS1,10,0,-10\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','0','-10');app.brs_selected_statement=st['id'];app.show('Bank reconciliation');app.open_bank_workbench();app.wb_toggle('bank',st['row_ids'][0]);app.wb_record_entry();app.update();form=next(w for w in app.wb_window.winfo_children() if w.winfo_class()=='Toplevel')
                helper.fill(form,'Accounting treatment','Loan repayment / EMI');app.update();helper.fill(form,'Principal INR','8');helper.fill(form,'Interest INR','2');helper.fill(form,'Accounting treatment','Bank / SMS / card charges');app.update()
                helper.fill(form,'Source / accounting review basis','Bank fee evidence')
                for w in helper.walk(form):
                    if w.winfo_class()=='TCheckbutton':w.invoke()
                helper.press(form,'Preview journal');app.update();self.assertFalse(app.state['vouchers']);preview=next(w for w in form.winfo_children() if w.winfo_class()=='Toplevel')
                with patch('riju.bank_ui.messagebox.showinfo'):helper.press(preview,'Confirm post and match')
                self.assertEqual(core.balances(app.state,'2026-04-30')['4560'],1000);self.assertFalse(r.outstanding(app.state,'1010')[0])
            finally:app.destroy()

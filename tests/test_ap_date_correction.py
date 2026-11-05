import copy,os,tempfile,unittest
from pathlib import Path
from riju import ap,core,reconciliation as bank

class PaymentDateCorrectionTests(unittest.TestCase):
    def setUp(self):
        from test_ap import ApTests
        a=ApTests();a.setUp();self.s=a.s;self.invoice=a.enter(reference='DATE-INV',amount='1000',allocations=[dict(account='4590',amount='1000')],invoice_date='2026-05-22',received_date='2026-05-22',accounting_date='2026-05-22');self.payment=a.pay(self.invoice,date='2026-11-25',reference='SYNTHETIC-AP-DATE-1',items=[dict(invoice=self.invoice['id'],amount='1000')])
    def correct(self,**kw):
        args=dict(s=self.s,key=self.payment['id'],new_date='2026-06-25',basis='Actual bank statement confirms 25 June; November was a typing error',confirmed=True);args.update(kw);return ap.correct_payment_date(**args)
    def test_historical_correction_preserves_reference_no_second_cash_payment(self):
        expense=core.balances(self.s,'2026-12-31')['4590'];before=len(self.s['vouchers']);result=self.correct();self.assertEqual(len(self.s['vouchers']),before+2);self.assertEqual(result['reference'],self.payment['reference']);self.assertEqual(ap.position(self.s,self.invoice,'2026-11-05')['status'],'Paid')
        self.assertEqual(core.balances(self.s,'2026-06-30')['1010'],900000);self.assertEqual(core.balances(self.s,'2026-11-30')['1010'],900000);self.assertEqual(core.balances(self.s,'2026-12-31')['4590'],expense);self.assertEqual(sum(i['amount'] for p in ap.data(self.s)['payments'] for i in p['items'] if p['id']==result['new_payment']),100000);ap.check(self.s)
        with self.assertRaises(ValueError):ap.pay(self.s,dict(date='2026-06-25',reference=self.payment['reference'],bank_account='1010',items=[dict(invoice=self.invoice['id'],amount='1000')],reviewed=True,basis='Cannot bypass duplicate'))
    def test_same_day_preaccrual_crossyear_and_unconfirmed_roll_back(self):
        for changes in (dict(new_date='2026-11-25'),dict(new_date='2026-05-21'),dict(new_date='2025-06-25'),dict(confirmed=False),dict(basis='')):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):self.correct(**changes)
            self.assertEqual(before,self.s)
    def test_locked_actual_period_rolls_back_cancellation(self):
        self.s['locked_through']='2026-06-30';before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.correct()
        self.assertEqual(before,self.s)
    def test_reconciled_payment_requires_undo_before_date_correction(self):
        st=bank.import_statement(self.s,b'date,narration,reference,debit,credit,balance\n2026-11-25,Payment,SYNTHETIC-AP-DATE-1,1000,0,9000\n','wrong-date-bank.csv','1010','ALL','2026-11-01','2026-11-30','10000','9000')
        books=[b for b in bank.outstanding(self.s,'1010')[1] if b['voucher']==self.payment['voucher']];bank.match_existing(self.s,st['row_ids'],[b['key'] for b in books]);before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.correct()
        self.assertEqual(before,self.s)
    def test_repeated_correction_and_protected_roundtrip(self):
        from riju.storage import Vault
        result=self.correct();second=self.correct(key=result['new_payment'],new_date='2026-07-25');self.assertEqual(ap.position(self.s,self.invoice,'2026-06-30')['status'],'Unpaid');self.assertEqual(ap.position(self.s,self.invoice,'2026-07-31')['status'],'Paid')
        with tempfile.TemporaryDirectory() as root:
            v=Vault(Path(root)/'b.json',demo=True);v.save(self.s);loaded=v.load();ap.check(loaded);self.assertTrue(any(a['action']=='AP_PAYMENT_DATE_CORRECTED' for a in loaded['audit']))

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class PaymentDateCorrectionDesktopTests(unittest.TestCase):
    def test_future_payment_shown_preview_no_post_and_actual_date_paid(self):
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        from unittest.mock import patch
        helper=TaxDepreciationDesktopTests();case=PaymentDateCorrectionTests();case.setUp()
        with tempfile.TemporaryDirectory() as root:
            app=App(Vault(Path(root)/'b.json',demo=True))
            try:
                app.state=case.s;app.show('AP Vendor Invoices');app.ap_on.set('2026-11-05');app.refresh_ap();self.assertNotIn(case.payment['id'],app.ap_payments.get_children());app.ap_on.set('2026-11-25');app.refresh_ap();app.ap_payments.selection_set(case.payment['id']);app.ap_correct_payment_date();form=helper.form(app);helper.fill(form,'Correct actual bank payment date','2026-06-25');helper.fill(form,'Bank evidence / correction reason','Bank confirms 25 June')
                for w in helper.walk(form):
                    if w.winfo_class()=='TCheckbutton':w.invoke()
                before=len(app.state['vouchers']);helper.press(form,'Preview payment-date correction');preview=helper.form(app);self.assertEqual(len(app.state['vouchers']),before);helper.press(preview,'Approve AP action');app.ap_on.set('2026-11-05');app.refresh_ap();self.assertEqual(ap.position(app.state,case.invoice,'2026-11-05')['status'],'Paid');self.assertEqual(len(app.state['vouchers']),before+2)
            finally:app.destroy()

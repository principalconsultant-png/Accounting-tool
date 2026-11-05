import copy,csv,io,tempfile,unittest,os
from pathlib import Path
from riju import core,ap,bank_workbench as w,reconciliation as bank,receipt_import as ri,foundation
from test_bank_reconciliation import pair
from test_receipt_import import row as base_salesrow,raw as salesraw

def salesrow(**kw):return base_salesrow(treatment="",**kw)


def paymentraw(rows):
    out=io.StringIO();wr=csv.writer(out);wr.writerow(w.PAYMENT_HEADERS)
    for r in rows:wr.writerow([r.get(k,'') for k in w.PAYMENT_FIELDS])
    return out.getvalue().encode()


class BankWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state();core.post(self.s,'2026-04-01','Opening bank',pair('1010','3000',100000),opening=True)
    def statement(self,body,closing='1000'):
        self.st=bank.import_statement(self.s,('date,narration,reference,debit,credit,balance\n'+body).encode(),'bank.csv','1010','ALL','2026-04-01','2026-04-30','1000',closing);return self.st
    def select(self,kind,doc=None):return w.sources(self.s,'1010','ALL',kind,doc['id'] if doc else None,'2026-04-30')
    def reconcile(self,kind,doc=None,selected=None,**kw):
        return w.reconcile(self.s,'1010',self.st['id'],kind,doc['id'] if doc else None,[b['id'] for b in bank.outstanding(self.s,'1010')[0]],[x['id'] for x in selected or self.select(kind,doc)],'Reviewed synthetic bank and source',**kw)
    def invoice(self,ref='INV-1',amount='100'):
        vendor=next(iter(ap.data(self.s)['vendors']),None) or ap.save_vendor(self.s,dict(name='Synthetic bank vendor',credit_days='30'))
        return ap.enter_invoice(self.s,dict(vendor=vendor['id'],reference=ref,invoice_date='2026-04-02',received_date='2026-04-02',accounting_date='2026-04-02',credit_days='30',due_basis='Receipt date',payment_date='',branch='JP',amount=amount,payable='2000',allocations=[dict(account='4590',amount=amount)],reviewed=True,basis='Reviewed source',tax_treatment='No separate GST/TDS; reviewed'))
    def payment(self,**kw):
        r=dict(vendor_name='Synthetic bank vendor',invoice_number='INV-1',invoice_date='2026-04-02',payment_date='2026-04-05',branch='JP',bank_account='1010',amount='100',payment_reference='UTR-PAY',basis='Actual bank transfer reviewed');r.update(kw);return r
    def sales(self,rows):return w.upload(self.s,salesraw(rows),'sales.csv','Sales receipts')
    def test_sales_upload_is_readonly_reupload_reuses_then_new_sale_settles(self):
        self.statement('2026-04-03,UPI settlement,UTR-1,0,100,1100\n','1100');before=len(self.s['vouchers']);doc=self.sales([salesrow(receipt_date='2026-04-02',receipt_no='SALE-1',consultation='100',cash='',upi='100',total='100')]);self.assertEqual(len(self.s['vouchers']),before);same=self.sales([salesrow(receipt_date='2026-04-02',receipt_no='SALE-1',consultation='100',cash='',upi='100',total='100')]);self.assertEqual(doc['id'],same['id']);result=self.reconcile('Sales receipts',doc);self.assertEqual(result['new_journals'],2);self.assertFalse(bank.outstanding(self.s,'1010')[0]);self.assertEqual(core.balances(self.s,'2026-04-30')['4000'],-10000);self.assertFalse(self.select('Sales receipts',doc));core.verify_audit(self.s)
    def test_many_receipts_mixed_channels_many_deposits_and_fees(self):
        self.statement('2026-04-03,UPI settlement,S1,0,99,1099\n2026-04-04,Card settlement,S2,0,99,1198\n','1198');doc=self.sales([salesrow(receipt_date='2026-04-02',receipt_no='SALE-A',consultation='100',cash='',upi='100',total='100'),salesrow(receipt_date='2026-04-02',receipt_no='SALE-B',consultation='100',cash='',upi='',card='100',total='100')]);result=self.reconcile('Sales receipts',doc,selected=list(reversed(self.select('Sales receipts',doc))),fees_minor=200);self.assertEqual(result['matches'],2);self.assertFalse(bank.outstanding(self.s,'1010')[0]);bal=core.balances(self.s,'2026-04-30');self.assertEqual((bal['1110'],bal['1120'],bal['4560']),(0,0,200))
        bankrows={b['id']:b for b in bank.bank_rows(self.s,'1010')}
        for match in self.s['matches']:
            expected='1110' if 'UPI' in bankrows[match['bank_id']]['narration'] else '1120';self.assertEqual({a['account'] for a in match['clearing_allocations']},{expected})
    def cashrows(self):
        return [salesrow(receipt_date=day,receipt_no='CASH-'+str(i),branch=branch,consultation=amount,cash=amount,upi='',total=amount) for i,(day,branch,amount) in enumerate([('2026-04-01','JP','30'),('2026-04-08','KM','40'),('2026-04-20','KM','42')])]
    def test_fortnightly_cash_deposits_use_multiple_days_and_units(self):
        self.statement('2026-04-10,Cash deposit,D1,0,70,1070\n2026-04-27,Cash deposit,D2,0,42,1112\n','1112');doc=self.sales(self.cashrows());result=self.reconcile('Sales receipts',doc)
        self.assertEqual(result['matches'],2);self.assertEqual(core.balances(self.s,'2026-04-30')['1000'],0);self.assertFalse(bank.outstanding(self.s,'1010')[0]);self.assertEqual(core.balances(self.s,'2026-04-30')['4000'],-11200)
    def test_partial_cash_keeps_balance_for_next_deposit_and_undo(self):
        self.statement('2026-04-10,Cash deposit,D1,0,70,1070\n2026-04-27,Cash deposit,D2,0,30,1100\n','1100');doc=self.sales(self.cashrows());result=self.reconcile('Sales receipts',doc,partial_cash=True)
        self.assertEqual(result['cash_remaining_INR'],'₹12.00');remaining=self.select('Sales receipts',doc);self.assertEqual(sum(x['amount'] for x in remaining),1200);self.assertEqual(core.balances(self.s,'2026-04-30')['1000'],1200);self.assertEqual(core.balances(self.s,'2026-04-30')['4560'],0)
        st=bank.import_statement(self.s,b'date,narration,reference,debit,credit,balance\n2026-04-30,Cash deposit,D3,0,12,1112\n','next.csv','1010','ALL','2026-04-30','2026-04-30','1100','1112');self.st=st;self.reconcile('Sales receipts',doc);self.assertFalse(self.select('Sales receipts',doc));self.assertEqual(core.balances(self.s,'2026-04-30')['4000'],-11200)
        match=self.s['matches'][-1];bank.undo_match(self.s,match['id'],'Reviewed undo','2026-04-30');self.assertEqual(sum(x['amount'] for x in self.select('Sales receipts',doc)),1200);core.verify_audit(self.s)
    def test_cash_shortfall_explains_date_amount_and_rolls_back(self):
        self.statement('2026-04-10,Cash deposit,D1,0,80,1080\n2026-04-27,Cash deposit,D2,0,32,1112\n','1112');doc=self.sales(self.cashrows());before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'2026-04-10.*Shortfall ₹10.00.*Later receipts ₹42.00'):self.reconcile('Sales receipts',doc,partial_cash=True,allow_date_difference=True)
        self.assertEqual(before,self.s)
    def test_partial_cash_cannot_reuse_cash_already_spent(self):
        self.statement('2026-04-10,Cash deposit,D1,0,70,1070\n','1070')
        core.post(self.s,'2026-04-01','Cash receipt',pair('1000','4000',10000),metadata={'type':'Receipt','reference':'SPENT-CASH'})
        core.post(self.s,'2026-04-05','Petty cash already spent',pair('4590','1000',4000))
        before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'dated book balance is ₹60.00.*Shortfall ₹10.00'):self.reconcile('Sales receipts',partial_cash=True)
        self.assertEqual(before,self.s)

    def test_partial_cash_rejects_fees_and_noncash_sources(self):
        self.statement('2026-04-10,Cash deposit,D1,0,70,1070\n','1070');doc=self.sales(self.cashrows());before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'charges zero'):self.reconcile('Sales receipts',doc,partial_cash=True,fees_minor=100)
        self.assertEqual(before,self.s)
        other=self.sales([salesrow(receipt_date='2026-04-01',receipt_no='UPI-PART',consultation='80',cash='',upi='80',total='80')])
        with self.assertRaisesRegex(ValueError,'only cash receipts'):self.reconcile('Sales receipts',other,partial_cash=True)

    def test_existing_sales_no_duplicate_revenue_or_journal(self):
        self.statement('2026-04-03,Direct deposit,B1,0,100,1100\n','1100');row=salesrow(receipt_date='2026-04-03',receipt_no='B1',consultation='100',cash='',upi='',bank='100',total='100');q=ri.stage(self.s,salesraw([row]),'already-sales.csv');ri.review(self.s,q['id'],[0],True,'Reviewed',True);ri.post(self.s,q['id']);doc=self.sales([row]);before=len(self.s['vouchers']);result=self.reconcile('Sales receipts',doc);self.assertEqual(result['new_journals'],0);self.assertEqual(len(self.s['vouchers']),before)
    def test_invoice_report_creates_historical_payment_and_matches(self):
        self.invoice();self.statement('2026-04-05,Synthetic bank vendor,UTR-PAY,100,0,900\n','900');doc=w.upload(self.s,paymentraw([self.payment()]),'payments.csv','Invoice payments');before=len(self.s['vouchers']);result=self.reconcile('Invoice payments',doc);self.assertEqual(result['new_journals'],1);self.assertEqual(len(self.s['vouchers']),before+1);self.assertEqual(self.s['ap']['payments'][0]['date'],'2026-04-05');self.assertEqual(core.balances(self.s,'2026-04-30')['2000'],0);self.assertFalse(bank.outstanding(self.s,'1010')[0])
    def test_many_invoices_one_transfer_and_existing_report_no_duplicate(self):
        self.invoice('INV-1','40');self.invoice('INV-2','60');self.statement('2026-04-05,Supplier combined,UTR-PAY,100,0,900\n','900');doc=w.upload(self.s,paymentraw([self.payment(amount='40'),self.payment(invoice_number='INV-2',amount='60')]),'payments.csv','Invoice payments');result=self.reconcile('Invoice payments',doc);self.assertEqual(len(self.s['ap']['payments']),1);self.assertEqual(result['new_journals'],1);self.assertFalse(self.select('Invoice payments',doc));self.assertFalse(bank.outstanding(self.s,'1010')[0])
    def test_preexisting_invoice_payment_links_without_new_posting(self):
        inv=self.invoice();ap.pay(self.s,dict(date='2026-04-05',reference='UTR-PAY',bank_account='1010',items=[dict(invoice=inv['id'],amount='100')],reviewed=True,basis='Already paid'));self.statement('2026-04-05,Supplier,UTR-PAY,100,0,900\n','900');doc=w.upload(self.s,paymentraw([self.payment()]),'payments.csv','Invoice payments');result=self.reconcile('Invoice payments',doc);self.assertEqual(result['new_journals'],0);self.assertEqual(len(self.s['ap']['payments']),1)
    def test_amount_mismatch_scope_date_and_rollback_do_not_post(self):
        self.invoice();self.statement('2026-04-05,Supplier,UTR-PAY,99,0,901\n','901');doc=w.upload(self.s,paymentraw([self.payment()]),'payments.csv','Invoice payments');before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.reconcile('Invoice payments',doc)
        self.assertEqual(before,self.s)
    def test_wrong_date_existing_payment_is_blocked_not_paid_twice(self):
        inv=self.invoice();ap.pay(self.s,dict(date='2026-11-03',reference='WRONG',bank_account='1010',items=[dict(invoice=inv['id'],amount='100')],reviewed=True,basis='Wrong date source'));self.statement('2026-04-05,Supplier,UTR-PAY,100,0,900\n','900');doc=w.upload(self.s,paymentraw([self.payment()]),'payments.csv','Invoice payments');rows=self.select('Invoice payments',doc);self.assertEqual(rows[0]['status'],'BLOCKED');before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.reconcile('Invoice payments',doc)
        self.assertEqual(before,self.s)
    def test_bad_source_rows_templates_and_pending_sales_are_not_double_posted(self):
        self.statement('2026-04-03,UPI,UTR,0,100,1100\n','1100');r=salesrow(receipt_date='2026-04-02',receipt_no='PENDING',consultation='100',cash='',upi='100',total='100');ri.stage(self.s,salesraw([r]),'pending.csv');doc=self.sales([r]);rows=self.select('Sales receipts',doc);self.assertEqual(rows[0]['status'],'BLOCKED');self.assertIn('batch',rows[0]['error'])
        invalid=w.upload(self.s,paymentraw([self.payment(bank_account='1010 Bank')]),'invalid-bank.csv','Invoice payments');self.assertIn('Bank Ledger',self.select('Invoice payments',invalid)[0]['error'])
        with tempfile.TemporaryDirectory() as d:
            from openpyxl import load_workbook
            for ext in ('xlsx','csv'):w.payment_template(Path(d)/('payment.'+ext))
            wb=load_workbook(Path(d)/'payment.xlsx');self.assertEqual(wb.sheetnames,['Payments','Instructions']);wb.close()

    def test_two_bank_withdrawals_multiple_payment_dates_and_partial_instalments(self):
        inv=self.invoice(amount='100');self.statement('2026-04-05,First transfer,P1,50,0,950\n2026-04-10,Second transfer,P2,50,0,900\n','900');doc=w.upload(self.s,paymentraw([self.payment(amount='50',payment_reference='P1'),self.payment(amount='50',payment_date='2026-04-10',payment_reference='P2')]),'payments.csv','Invoice payments');result=self.reconcile('Invoice payments',doc,selected=list(reversed(self.select('Invoice payments',doc))));self.assertEqual(result['new_journals'],2);self.assertEqual(len(self.s['ap']['payments']),2);self.assertFalse(bank.outstanding(self.s,'1010')[0]);self.assertEqual(ap.position(self.s,inv)['remaining'],0)
        banks={x['id']:x for x in bank.bank_rows(self.s,'1010')};books={x['key']:x for x in bank.book_items(self.s,'1010')}
        for m in self.s['matches']:
            for edge in m['edges']:self.assertEqual(banks[edge['bank_id']]['date'],books[edge['book_key']]['date'])
    def test_mixed_direct_bank_and_clearing_many_to_one(self):
        self.statement('2026-04-03,Combined,B1,0,150,1150\n','1150');doc=self.sales([salesrow(receipt_date='2026-04-03',receipt_no='DIRECT',consultation='50',cash='',upi='',bank='50',total='50'),salesrow(receipt_date='2026-04-02',receipt_no='CLEAR',consultation='100',cash='',upi='100',total='100')]);self.reconcile('Sales receipts',doc);self.assertFalse(bank.outstanding(self.s,'1010')[0]);self.assertEqual(core.balances(self.s,'2026-04-30')['1110'],0)
    def test_reversal_and_late_date_failure_roll_back_receipt_postings(self):
        self.statement('2026-04-03,Early deposit,B1,0,100,1100\n','1100');doc=self.sales([salesrow(receipt_date='2026-04-04',receipt_no='LATE',consultation='100',cash='',upi='100',total='100')]);before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.reconcile('Sales receipts',doc)
        self.assertEqual(before,self.s)
    def test_source_documents_and_match_history_survive_vault_undo(self):
        from riju.storage import Vault
        self.statement('2026-04-03,UPI,B1,0,100,1100\n','1100');doc=self.sales([salesrow(receipt_date='2026-04-02',receipt_no='STABLE',consultation='100',cash='',upi='100',total='100')]);self.reconcile('Sales receipts',doc);m=self.s['matches'][0];bank.undo_match(self.s,m['id'],'Reviewed undo','2026-04-04');self.assertEqual(sum(b['remaining'] for b in bank.outstanding(self.s,'1010')[0]),10000)
        with tempfile.TemporaryDirectory() as d:
            vault=Vault(Path(d)/'book.json',demo=True);vault.save(self.s);loaded=vault.load();self.assertEqual(len(w.documents(loaded)),1);self.assertEqual(self.s,loaded)

    def test_fifty_selected_receipts_post_one_reviewed_import_and_one_settlement(self):
        self.statement('2026-04-03,Batch settlement,B1,0,500,1500\n','1500');doc=self.sales([salesrow(receipt_date='2026-04-02',receipt_no='BATCH-'+str(i),consultation='10',cash='',upi='10',total='10') for i in range(50)]);result=self.reconcile('Sales receipts',doc);self.assertEqual(result['new_journals'],51);self.assertEqual(len([q for q in self.s['queue'] if q.get('kind')=='standard_sales']),1);self.assertFalse(bank.outstanding(self.s,'1010')[0])

    def test_all_statements_view_cannot_cross_match_exclusive_units(self):
        st=bank.import_statement(self.s,b'date,narration,reference,debit,credit,balance\n2026-04-03,JP collection,B1,0,100,1100\n','exclusive.csv','1010','JP','2026-04-01','2026-04-30','1000','1100')
        core.post(self.s,'2026-04-03','KM collection',pair('1010','4000',10000,'KM'),metadata={'type':'Receipt','reference':'B1'})
        rows=w.sources(self.s,'1010','ALL','All book movements');before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):w.reconcile(self.s,'1010',None,'All book movements',None,st['row_ids'],[x['id'] for x in rows],'Review branch scope')
        self.assertEqual(before,self.s)

    def test_invoice_withdrawal_charge_and_undo_reverses_charge_only(self):
        inv=self.invoice();self.statement('2026-04-05,Supplier plus fee,UTR-PAY,101,0,899\n','899');doc=w.upload(self.s,paymentraw([self.payment()]),'payment-fee.csv','Invoice payments')
        result=self.reconcile('Invoice payments',doc,fees_minor=100);self.assertEqual(result['new_journals'],2);self.assertEqual(ap.position(self.s,inv)['remaining'],0);self.assertEqual(core.balances(self.s,'2026-04-30')['4560'],100);self.assertFalse(bank.outstanding(self.s,'1010')[0])
        match=self.s['matches'][-1];self.assertEqual(match['kind'],'adjustment');bank.undo_match(self.s,match['id'],'Charge needs correction','2026-04-06');self.assertEqual(core.balances(self.s,'2026-04-30')['4560'],0);self.assertEqual(len(self.s['ap']['payments']),1)
    def test_existing_gross_deposit_net_charge_matches_without_revenue_repost(self):
        core.post(self.s,'2026-04-03','Gross receipt',pair('1010','4000',10000),metadata={'type':'Receipt','reference':'GROSS'})
        self.statement('2026-04-03,Net receipt,GROSS,0,99,1099\n','1099');before=len(self.s['vouchers']);result=self.reconcile('Sales receipts',fees_minor=100)
        self.assertEqual(result['new_journals'],1);self.assertEqual(len(self.s['vouchers']),before+1);self.assertFalse(bank.outstanding(self.s,'1010')[0]);self.assertEqual(core.balances(self.s,'2026-04-30')['4000'],-10000)
    def test_charge_mismatch_or_wrong_direction_rolls_back(self):
        self.invoice();self.statement('2026-04-05,Supplier,UTR-PAY,99,0,901\n','901');doc=w.upload(self.s,paymentraw([self.payment()]),'payment.csv','Invoice payments');before=copy.deepcopy(self.s)
        for fee in (-100,100):
            with self.assertRaises(ValueError):self.reconcile('Invoice payments',doc,fees_minor=fee)
            self.assertEqual(before,self.s)
    def test_source_channel_uses_structured_account_before_party_text(self):
        self.assertEqual(w.channel(dict(channel='1120',label='UPI company'),'source'),'Card')
        self.assertEqual(w.channel(dict(channel='1110',label='Patient'),'source'),'UPI')
        self.assertEqual(w.channel(dict(narration='UPI SETTLEMENT'),'bank'),'UPI');self.assertEqual(w.channel(dict(narration='TERMINAL 1 CARDS'),'bank'),'Card')


@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class BankWorkbenchDesktopTests(unittest.TestCase):
    def test_side_by_side_upload_check_totals_preview_and_confirm(self):
        from unittest.mock import patch
        from tkinter import ttk
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=App(Vault(root/'book.json',demo=True))
            try:
                core.post(app.state,'2026-04-01','Opening bank',pair('1010','3000',100000),opening=True)
                st=bank.import_statement(app.state,b'date,narration,reference,debit,credit,balance\n2026-04-03,UPI,B1,0,100,1100\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','1000','1100');app.brs_selected_statement=st['id'];app.show('Bank reconciliation')
                self.assertEqual(app.brs_tabs.tab(app.brs_tabs.select(),'text'),'Bank transactions');self.assertNotIn('workbench',app.brs_frames);app.open_bank_workbench();self.assertTrue(app.wb_bank_table.winfo_exists());app.update();self.assertGreater(app.wb_bank_table.master.master.winfo_width(),200);self.assertGreater(app.wb_source_table.master.master.winfo_width(),200);path=root/'sales.csv';path.write_bytes(salesraw([salesrow(receipt_date='2026-04-02',receipt_no='GUI-SALE',consultation='100',cash='',upi='100',total='100')]))
                with patch('riju.bank_workbench_ui.filedialog.askopenfilename',return_value=str(path)),patch('riju.bank_workbench_ui.messagebox.showinfo'):app.wb_upload('Sales receipts')
                app.update();self.assertEqual(len(app.wb_source_rows),1);bankid=next(iter(app.wb_bank_rows));sourceid=next(iter(app.wb_source_rows));app.wb_toggle('bank',bankid);app.wb_toggle('source',sourceid);self.assertEqual(app.wb_bank_table.set(bankid,'Check'),'☑');self.assertIn('DIFFERENCE ₹0.00',app.wb_totals.cget('text'));app.wb_confirm.set(True);app.wb_reconcile();app.update();preview=helper.form(app);self.assertEqual(len(app.state['vouchers']),1)
                with patch('riju.bank_workbench_ui.messagebox.showinfo'):helper.press(preview,'Confirm reconcile')
                app.update();self.assertFalse(app.wb_bank_rows);self.assertEqual(len(app.state['vouchers']),3)
            finally:app.destroy()
    def test_partial_cash_preview_keeps_undeposited_amount(self):
        from unittest.mock import patch
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            app=App(Vault(Path(d)/'book.json',demo=True))
            try:
                core.post(app.state,'2026-04-01','Cash receipts',pair('1000','4000',11200),metadata={'type':'Receipt','reference':'CASH-UI'})
                st=bank.import_statement(app.state,b'date,narration,reference,debit,credit,balance\n2026-04-14,Cash deposit,D1,0,100,100\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','0','100');app.brs_selected_statement=st['id'];app.show('Bank reconciliation');app.open_bank_workbench()
                for key in list(app.wb_bank_rows):app.wb_toggle('bank',key)
                for key in list(app.wb_source_rows):app.wb_toggle('source',key)
                app.wb_partial_cash.set(True);app.wb_update_totals();self.assertIn('cash left undeposited ₹12.00',app.wb_totals.cget('text'));app.wb_confirm.set(True);app.wb_reconcile();preview=helper.form(app);self.assertEqual(len(app.state['vouchers']),1)
                with patch('riju.bank_workbench_ui.messagebox.showinfo'):helper.press(preview,'Confirm reconcile')
                self.assertEqual(core.balances(app.state,'2026-04-30')['1000'],1200);self.assertFalse(app.wb_bank_rows);self.assertEqual(sum(x['amount'] for x in app.wb_source_rows.values()),1200)
            finally:app.destroy()

    def test_checkbox_keyboard_clear_templates_and_stale_preview_blocked(self):
        from unittest.mock import patch
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=App(Vault(root/'book.json',demo=True))
            try:
                core.post(app.state,'2026-04-03','Existing receipt',pair('1010','4000',10000),metadata={'type':'Receipt','reference':'B1'});st=bank.import_statement(app.state,b'date,narration,reference,debit,credit,balance\n2026-04-03,Receipt,B1,0,100,100\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','0','100');app.brs_selected_statement=st['id'];app.show('Bank reconciliation');app.open_bank_workbench();app.update();bid=next(iter(app.wb_bank_rows));key=next(iter(app.wb_source_rows));app.wb_bank_table.selection_set(bid);app.wb_space('bank');app.wb_source_table.selection_set(key);app.wb_space('source');app.wb_clear();self.assertFalse(app.wb_bank_checks);app.wb_toggle('bank',bid);app.wb_toggle('source',key)
                for kind in ('sales','payments'):
                    for ext in ('xlsx','csv'):
                        with patch('riju.bank_workbench_ui.filedialog.asksaveasfilename',return_value=str(root/(kind+'.'+ext))):app.wb_template(kind,ext)
                        self.assertTrue((root/(kind+'.'+ext)).exists())
                app.wb_confirm.set(True);app.wb_reconcile();preview=helper.form(app);core.post(app.state,'2026-04-04','Changed books',pair('4590','1010',100))
                with patch('riju.app.messagebox.showerror') as error:helper.press(preview,'Confirm reconcile')
                self.assertTrue(error.called);self.assertFalse(app.state['matches']);preview.destroy()
            finally:app.destroy()

    def test_separate_navigation_window_large_area_reopen_and_close(self):
        from riju.app import App
        from riju.storage import Vault
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            app=App(Vault(Path(d)/'book.json',demo=True))
            try:
                app.nav_buttons['Reconcile side by side'].invoke();app.update();win=app.wb_window
                self.assertTrue(win.winfo_exists());self.assertEqual(app.current,'Bank reconciliation');self.assertNotIn('workbench',app.brs_frames)
                self.assertGreaterEqual(win.winfo_width()*win.winfo_height(),.75*win.winfo_screenwidth()*win.winfo_screenheight())
                self.assertGreater(app.wb_bank_table.winfo_height(),win.winfo_height()*.45);self.assertGreater(app.wb_source_table.master.master.winfo_width(),200)
                self.assertFalse(app.wb_advanced.winfo_manager());app.wb_options();app.update();self.assertTrue(app.wb_advanced.winfo_manager());app.wb_options();app.open_bank_workbench();self.assertIs(app.wb_window,win)
                app.close_bank_workbench();app.update();self.assertIsNone(app.wb_window);app.refresh_bank_tables();app.open_bank_workbench();app.update();self.assertTrue(app.wb_window.winfo_exists())
            finally:app.destroy()
    def test_standalone_bank_import_uses_own_context_and_survives_navigation(self):
        from unittest.mock import patch
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=App(Vault(root/'book.json',demo=True))
            try:
                foundation.save_account(app.state,'1005','Second synthetic bank','Asset','Cash and bank');app.show('Bank reconciliation');app.open_bank_workbench();app.update();app.wb_bank_account.set('1005 · Second synthetic bank');app.wb_scope.set('JP Nagar');app.wb_reload_context();self.assertEqual(app._bank_account(),'1010');self.assertEqual(app.wb_account(),'1005')
                path=root/'bank.csv';path.write_bytes(b'date,narration,reference,debit,credit,balance\n2026-04-03,Second bank receipt,B1,0,100,100\n')
                with patch('riju.bank_ui.filedialog.askopenfilename',return_value=str(path)):app.wb_import_bank()
                form=helper.form(app)
                for label,value in [('Statement from','2026-04-01'),('Through','2026-04-30'),('Bank opening INR (optional)','0'),('Bank closing INR (optional)','100')]:helper.fill(form,label,value)
                helper.press(form,'Validate & preview rows');app.update();preview=helper.form(app);helper.press(preview,'Approve statement import');app.update();self.assertEqual(app.wb_account(),'1005');self.assertEqual(len(app.wb_bank_rows),1);self.assertEqual(bank.statement(app.state,app.wb_statement_id())['bank_account'],'1005');self.assertEqual(app._bank_account(),'1010')
                app.show('Chart of accounts');app.update();app.wb_refresh();self.assertEqual(len(app.wb_bank_rows),1);app.close_bank_workbench();self.assertEqual(app.current,'Chart of accounts')
            finally:app.destroy()

    def test_independent_header_filters_clear_checks_and_charge_preview(self):
        from unittest.mock import patch
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            app=App(Vault(Path(d)/'book.json',demo=True))
            try:
                st=bank.import_statement(app.state,b'date,narration,reference,debit,credit,balance\n2026-04-03,UPI settlement,U1,0,99,99\n2026-04-04,CARD settlement,C1,0,50,149\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','0','149');app.brs_selected_statement=st['id']
                doc=w.upload(app.state,salesraw([salesrow(receipt_date='2026-04-02',receipt_no='UPI-A',consultation='100',cash='',upi='100',total='100'),salesrow(receipt_date='2026-04-02',receipt_no='CARD-B',consultation='50',cash='',card='50',total='50')]),'sales.csv','Sales receipts')
                app.show('Bank reconciliation');app.open_bank_workbench();app.update();app.wb_prior_doc=doc['id'];app.wb_change_kind();self.assertEqual(len(app.wb_bank_rows),2);self.assertEqual(len(app.wb_source_rows),2)
                app.wb_channels['bank'].set('UPI');self.assertEqual(len(app.wb_bank_rows),1);self.assertEqual(len(app.wb_source_rows),2)
                app.wb_channels['source'].set('UPI');self.assertEqual(len(app.wb_source_rows),1)
                app.wb_filter_dialog('bank','Reference');form=next(w for w in app.wb_window.winfo_children() if w.winfo_class()=='Toplevel')
                import tkinter.ttk as ttk
                entry=next(x for x in form.winfo_children() if isinstance(x,ttk.Entry));entry.insert(0,'missing');helper.press(form,'Apply filter');self.assertFalse(app.wb_bank_rows);self.assertEqual(len(app.wb_source_rows),1)
                app.wb_reset_filters('bank');app.wb_channels['bank'].set('UPI');bid=next(iter(app.wb_bank_rows));sid=next(iter(app.wb_source_rows));app.wb_toggle('bank',bid);app.wb_toggle('source',sid);before=len(app.state['vouchers']);app.wb_use_charge();self.assertEqual(app.wb_fees.get(),'1.00');self.assertEqual(len(app.state['vouchers']),before);self.assertIn('DIFFERENCE ₹0.00',app.wb_totals.cget('text'))
                app.wb_confirm.set(True);app.wb_reconcile();preview=helper.form(app);self.assertEqual(len(app.state['vouchers']),before)
                app.wb_channels['source'].set('All')
                with patch('riju.app.messagebox.showerror') as error:helper.press(preview,'Confirm reconcile')
                self.assertTrue(error.called);self.assertEqual(len(app.state['vouchers']),before);preview.destroy()
                app.wb_channels['source'].set('UPI');app.wb_toggle('bank',bid);app.wb_toggle('source',sid);app.wb_use_charge();app.wb_confirm.set(True);app.wb_reconcile();preview=helper.form(app)
                with patch('riju.bank_workbench_ui.messagebox.showinfo'):helper.press(preview,'Confirm reconcile')
                self.assertEqual(core.balances(app.state,'2026-04-30')['4560'],100);self.assertFalse(app.wb_bank_checks);self.assertEqual(app.wb_fees.get(),'0');self.assertFalse(app.wb_confirm.get())
            finally:app.destroy()

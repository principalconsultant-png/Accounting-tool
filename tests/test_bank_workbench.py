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
                self.assertEqual(app.brs_tabs.tab(app.brs_tabs.select(),'text'),'Reconcile side by side');self.assertTrue(app.wb_bank_table.winfo_exists());app.update();self.assertGreater(app.wb_bank_table.master.master.winfo_width(),200);self.assertGreater(app.wb_source_table.master.master.winfo_width(),200);path=root/'sales.csv';path.write_bytes(salesraw([salesrow(receipt_date='2026-04-02',receipt_no='GUI-SALE',consultation='100',cash='',upi='100',total='100')]))
                with patch('riju.bank_workbench_ui.filedialog.askopenfilename',return_value=str(path)),patch('riju.bank_workbench_ui.messagebox.showinfo'):app.wb_upload('Sales receipts')
                app.update();self.assertEqual(len(app.wb_source_rows),1);bankid=next(iter(app.wb_bank_rows));sourceid=next(iter(app.wb_source_rows));app.wb_toggle('bank',bankid);app.wb_toggle('source',sourceid);self.assertEqual(app.wb_bank_table.set(bankid,'Check'),'☑');self.assertIn('DIFFERENCE ₹0.00',app.wb_totals.cget('text'));app.wb_confirm.set(True);app.wb_reconcile();app.update();preview=helper.form(app);self.assertEqual(len(app.state['vouchers']),1)
                with patch('riju.bank_workbench_ui.messagebox.showinfo'):helper.press(preview,'Confirm reconcile')
                app.update();self.assertFalse(app.wb_bank_rows);self.assertEqual(len(app.state['vouchers']),3)
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
                core.post(app.state,'2026-04-03','Existing receipt',pair('1010','4000',10000),metadata={'type':'Receipt','reference':'B1'});st=bank.import_statement(app.state,b'date,narration,reference,debit,credit,balance\n2026-04-03,Receipt,B1,0,100,100\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','0','100');app.brs_selected_statement=st['id'];app.show('Bank reconciliation');bid=next(iter(app.wb_bank_rows));key=next(iter(app.wb_source_rows));app.wb_bank_table.selection_set(bid);app.wb_space('bank');app.wb_source_table.selection_set(key);app.wb_space('source');app.wb_clear();self.assertFalse(app.wb_bank_checks);app.wb_toggle('bank',bid);app.wb_toggle('source',key)
                for kind in ('sales','payments'):
                    for ext in ('xlsx','csv'):
                        with patch('riju.bank_workbench_ui.filedialog.asksaveasfilename',return_value=str(root/(kind+'.'+ext))):app.wb_template(kind,ext)
                        self.assertTrue((root/(kind+'.'+ext)).exists())
                app.wb_confirm.set(True);app.wb_reconcile();preview=helper.form(app);core.post(app.state,'2026-04-04','Changed books',pair('4590','1010',100))
                with patch('riju.app.messagebox.showerror') as error:helper.press(preview,'Confirm reconcile')
                self.assertTrue(error.called);self.assertFalse(app.state['matches']);preview.destroy()
            finally:app.destroy()

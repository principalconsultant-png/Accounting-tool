import copy
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from riju import core,ap,receipt_import as ri
from riju.date_picker import date_mode
from riju.journal_preview import with_account_names

class RequestedFixTests(unittest.TestCase):
    def test_date_detection_covers_optional_dates_ranges_months_and_lists(self):
        for label in ('Transaction date','From','Through (optional)','As at','Scheduled payment date (blank = due)','Effective from','Completed date','Put-to-use date'):
            self.assertEqual(date_mode(label),'day',label)
        self.assertEqual(date_mode('Statement period YYYY-MM'),'month');self.assertEqual(date_mode('Exceptional working dates (comma-separated YYYY-MM-DD)'),'days')
        for label in ('Credit period calendar days','Date format','Date column','Payment evidence / approval basis','Vendor name'):self.assertIsNone(date_mode(label),label)
    def test_vendor_updates_preserve_invoice_identity_and_history(self):
        from test_ap import ApTests
        helper=ApTests();helper.setUp();invoice=helper.enter();s=helper.s;vid=helper.vendor['id'];original=copy.deepcopy(invoice)
        ap.save_vendor(s,dict(name='Renamed supplier',credit_days='45',reference='UPDATED',active=False),vid)
        self.assertEqual(ap.vendor(s,vid)['credit_days'],45);self.assertEqual(ap.invoice(s,invoice['id']),original)
        with self.assertRaisesRegex(ValueError,'inactive'):helper.enter(reference='INV-NEW')
        with self.assertRaises(ValueError):ap.save_vendor(s,dict(name='Synthetic Vendor',credit_days='0'))
        ap.save_vendor(s,dict(name='Renamed supplier',credit_days='15',active=True),vid);new=helper.enter(reference='INV-NEW');self.assertEqual(new['vendor_name'],'Renamed supplier');self.assertEqual(new['vendor'],vid);core.verify_audit(s)
    def test_reject_duplicate_without_posting_approval_then_post_149_valid_receipts(self):
        from test_receipt_import import row,raw
        s=core.empty_state();rows=[row(receipt_no=str(9800+i)) for i in range(149)];rows.append(row(receipt_no='9891',consultation='12000',treatment='300',cash='12300',upi='',total='12300'));q=ri.stage(s,raw(rows),'149-valid-one-duplicate.csv')
        self.assertEqual(sum(r['validation']=='DUPLICATE' for r in q['rows']),1)
        ri.review(s,q['id'],[149],False,'Duplicate rejected from source review',False);self.assertEqual(q['rows'][149]['review'],'REJECTED')
        with self.assertRaises(ValueError):ri.review(s,q['id'],list(range(149)),True,'Not yet confirmed',False)
        ri.review(s,q['id'],list(range(149)),True,'Source/tax/payment review complete',True);self.assertEqual(ri.post(s,q['id']),149);self.assertEqual(len(s['vouchers']),149)
    def test_account_names_are_display_only(self):
        s=core.empty_state();record=dict(lines=[dict(account='4000',debit=0,credit=10000)]);original=copy.deepcopy(record);preview=with_account_names(s,record);self.assertEqual(preview['lines'][0]['account_name'],'OPD consultation revenue');self.assertEqual(record,original)

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class RequestedFixDesktopTests(unittest.TestCase):
    def test_calendar_leap_day_jump_cancel_month_and_multi_date(self):
        import tkinter as tk
        from riju.date_picker import CalendarPopup
        root=tk.Tk()
        try:
            value=tk.StringVar(value='2026-11-02');popup=CalendarPopup(root,value);popup.jumpyear.set('2028');popup.jumpmonth.set('February');popup.jump();popup.choose(date(2028,2,29));self.assertEqual(value.get(),'2028-02-29')
            popup=CalendarPopup(root,value);popup.move(1);popup.close();self.assertEqual(value.get(),'2028-02-29')
            month=tk.StringVar(value='2026-11');popup=CalendarPopup(root,month,'month');popup.choose(date(2027,1,3));self.assertEqual(month.get(),'2027-01')
            days=tk.StringVar(value='2026-11-01');popup=CalendarPopup(root,days,'days');popup.choose(date(2026,11,2));self.assertEqual(days.get(),'2026-11-01, 2026-11-02')
        finally:root.destroy()
    def test_visible_vendor_master_and_journal_names_with_duplicate_review(self):
        import tkinter as tk
        from tkinter import ttk
        from riju.app import App
        from riju.storage import Vault
        from test_gui import TaxDepreciationDesktopTests
        from test_receipt_import import row,raw
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            app=App(Vault(Path(d)/'book.json',demo=True))
            try:
                self.assertIn('यथार्थः',app.title());app.show('Vendor master');app.ap_vendor();form=helper.form(app);helper.fill(form,'Vendor legal/source name','Visible vendor');helper.press(form,'Save vendor');app.update();key=app.vendor_table.get_children()[0];app.vendor_table.selection_set(key);app.ap_edit_vendor();form=helper.form(app);helper.fill(form,'Vendor legal/source name','Edited visible vendor');helper.fill(form,'Default credit period calendar days','45');helper.press(form,'Save vendor');app.update();self.assertEqual(app.vendor_table.item(key)['values'][1],'Edited visible vendor')
                app.show('Journal studio');entry=next(w for w in helper.walk(app.content) if isinstance(w,ttk.Entry) and hasattr(w,'date_picker'));entry.date_picker.invoke();popup=[w for w in entry.winfo_children() if w.winfo_class()=='Toplevel'][0];popup.choose(date(2026,11,1));self.assertEqual(app.jdate.get(),'2026-11-01')
                q=app.commit(lambda s:ri.stage(s,raw([row(),row()]),'duplicate.csv'));app.show('Sales receipt');app.receipt_import_review(q['id']);form=helper.form(app)
                with patch('riju.receipt_import_ui.simpledialog.askstring',return_value='Duplicate source rejected'):helper.press(form,'Reject flagged rows')
                self.assertEqual(ri._batch(app.state,q['id'])['rows'][1]['review'],'REJECTED');helper.reviewed(form)
                with patch('riju.receipt_import_ui.simpledialog.askstring',return_value='Valid source confirmed'):helper.press(form,'Approve all valid rows')
                helper.press(form,'Preview batch journals');app.update();preview=helper.form(app);table=next(w for w in helper.walk(preview) if isinstance(w,ttk.Treeview));values=[table.item(k)['values'] for k in table.get_children()];self.assertTrue(any('OPD consultation revenue' in row for row in values));helper.press(preview,'Approve sales batch');app.update();self.assertEqual(len(app.state['vouchers']),1);self.assertFalse(any('account_name' in l for l in app.state['vouchers'][0]['lines']))
            finally:app.destroy()

"""Run with a graphical display: DISPLAY=:99 python -m unittest discover -s tests -v."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from riju.storage import Vault

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'A graphical display is required')
class DesktopSmokeTests(unittest.TestCase):
    def test_screens_and_review_post_flow(self):
        from riju.app import App
        with tempfile.TemporaryDirectory() as d:
            app=App(Vault(Path(d)/'demo.json',demo=True))
            try:
                for page in app.pages:
                    app.show(page);app.update()
                app.show('Journal studio');app.update()
                app.jdate.set('2026-04-01')
                app.narration.insert('1.0','Paid ₹5000 rent by bank')
                app.prepare()
                self.assertEqual(len(app.draft),2)
                with patch('riju.app.messagebox.askyesno',return_value=True),patch('riju.app.messagebox.showinfo'):
                    app.post_draft()
                self.assertEqual(len(app.state['vouchers']),1)
                app.show('Financial reports');app.update()
                restored=Vault(Path(d)/'demo.json',demo=True).load()
                self.assertEqual(restored['vouchers'][0]['lines'][0]['debit'],500000)
                for description in ('Medicines purchased from our Pharmacy by Patient Hema R in Cash INR1291', 'Received cash INR1291 from Patient Hema R for Medicines.'):
                    app.show('Journal studio');app.update()
                    app.jdate.set('2026-10-29')
                    app.narration.insert('1.0',description)
                    app.prepare()
                    self.assertEqual([l['account'] for l in app.draft],['1000','4030'])
                    self.assertEqual(app.draft[0]['debit'],129100)
                    with patch('riju.app.messagebox.askyesno',return_value=True),patch('riju.app.messagebox.showinfo'):
                        app.post_draft()
                self.assertEqual(len(app.state['vouchers']),3)
                from test_sales import workbook
                from riju import core
                import tkinter as tk
                def widgets(parent):
                    for w in parent.winfo_children():
                        yield w
                        yield from widgets(w)
                def invoke(label):
                    next(w for w in widgets(app.content) if w.winfo_class()=='TButton' and w.cget('text')==label).invoke()
                app.show('Sales receipt');app.update()
                entries=[w for w in widgets(app.content) if w.winfo_class()=='TEntry']
                self.assertEqual(len(entries),21)
                for field in (entries[2],entries[-4]):field.delete(0,'end');field.insert(0,'100')
                invoke('Prepare compound journal for review')
                self.assertEqual(app.current,'Journal studio')
                self.assertEqual([l['account'] for l in app.draft],['1000','4010'])
                source=Path(d)/'synthetic.xlsx';source.write_bytes(workbook())
                app.show('Import queue');app.update()
                with patch('riju.app.filedialog.askopenfilename',return_value=str(source)),patch('riju.app.messagebox.showinfo'):
                    invoke('Upload daily sales XLSX')
                self.assertEqual(len(app.state['queue']),1)
                tree=next(w for w in widgets(app.content) if w.winfo_class()=='Treeview')
                tree.selection_set(tree.get_children()[0])
                invoke('Review rows');app.update()
                for child in app.winfo_children():
                    if isinstance(child,tk.Toplevel):child.destroy()
                with patch('riju.app.messagebox.askyesno',return_value=True):invoke('Approve & post entire file')
                self.assertEqual(app.state['queue'][0]['status'],'PROCESSED')
                self.assertEqual(len(app.state['vouchers']),4)
                core.verify_audit(app.state)
            finally: app.destroy()

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'A graphical display is required')
class FoundationDesktopTests(unittest.TestCase):
    def buttons(self,widget,text):
        from tkinter import ttk
        for child in widget.winfo_children():
            if isinstance(child,ttk.Button) and child.cget('text')==text:yield child
            yield from self.buttons(child,text)

    def click(self,app,text):
        next(self.buttons(app.content,text)).invoke();app.update()

    def test_optional_entity_branch_ledger_and_saved_draft_roundtrip(self):
        from riju.app import App
        from riju import core
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as directory:
            app=App(Vault(Path(directory)/'demo.json',demo=True))
            errors=[];app.report_callback_exception=lambda *args:errors.append(args)
            try:
                with patch('riju.app.messagebox.showinfo'),patch('riju.foundation_ui.messagebox.showinfo'),patch('riju.app.messagebox.askyesno',return_value=True):
                    app.show('Setup & periods');app.update()
                    app.entity_name.set('Test hospital');self.click(app,'Save entity details')
                    self.assertEqual(app.state['settings']['entity'],'Test hospital')
                    app.entity_fields['tan'].set('BLRA12345B');self.click(app,'Save entity details')
                    self.assertEqual(app.state['settings']['registration']['tan'],'BLRA12345B')
                    app.branch_fields['code'].set('NEW');app.branch_fields['name'].set('New branch');self.click(app,'Save branch')
                    self.assertIn('New branch',app.branch_names)
                    app.setup_year.set('2022');self.click(app,'Add financial year')
                    self.assertEqual(app.year.get(),'2022')
                    app.show('Chart of accounts');app.update()
                    app.ledger_code.set('1011');app.ledger_name.set('Second bank');app.ledger_kind.set('Asset');app.ledger_group.set('Cash and bank')
                    self.click(app,'Save ledger')
                    self.assertTrue(any(a['code']=='1011' for a in app.state['accounts']))
                    app.show('Journal studio');app.update()
                    app.jdate.set('2022-06-01');app.jbranch.set('New branch');app.jreference.set('R-42');app.jtype.set('Receipt')
                    app.narration.insert('1.0','Received cash INR100 for consultation');app.prepare();app.save_current_draft()
                    self.assertFalse(app.state['vouchers']);self.assertEqual(len(app.state['drafts']),1)
                    app.show('Saved drafts');app.update()
                    # Choose the saved draft in its tree, then use the actual desktop edit/post actions.
                    def trees(w):
                        for c in w.winfo_children():
                            if isinstance(c,ttk.Treeview):yield c
                            yield from trees(c)
                    tree=next(trees(app.content));tree.selection_set(tree.get_children()[0]);self.click(app,'Open & edit draft')
                    self.assertEqual(app.jreference.get(),'R-42');self.assertEqual(app.jbranch.get(),'New branch')
                    app.post_draft();self.assertFalse(app.state['drafts']);self.assertEqual(len(app.state['vouchers']),1)
                    self.assertEqual(app.state['vouchers'][0]['lines'][0]['branch'],'NEW')
                    self.assertEqual(app.state['vouchers'][0]['metadata']['reference'],'R-42')
                    app.geometry('1000x680')
                    for page in app.pages:
                        app.show(page);app.update();app.page_canvas.yview_moveto(1);app.update()
                    self.assertFalse(errors,errors)
                    core.verify_audit(app.state)
            finally:app.destroy()

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'A graphical display is required')
class LedgerDesktopTests(unittest.TestCase):
    def test_navigation_account_filters_exports_and_voucher(self):
        from riju.app import App
        from riju import core
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);app=App(Vault(p/'test.json',demo=True))
            errors=[];app.report_callback_exception=lambda *args:errors.append(args)
            try:
                app.commit(lambda s:core.post(s,'2023-04-01','Synthetic opening',[dict(account='1010',branch='JP',debit=100000,credit=0),dict(account='3000',branch='JP',debit=0,credit=100000)],opening=True))
                app.commit(lambda s:core.post(s,'2023-04-02','Consultation receipts',[dict(account='1010',branch='JP',debit=50000,credit=0),dict(account='4000',branch='JP',debit=0,credit=50000)],metadata={'reference':'R-TEST'}))
                self.assertEqual(list(app.pages)[:2],['Overview','Ledger A/c'])
                app.year.set('2023');app.nav_buttons['Ledger A/c'].invoke();app.update()
                self.assertIn('Patient A/C',' '.join(app.ledger_list.get(0,'end')))
                app.ledger_category.set('Bank books');app.update();self.assertIn('1010',app.selected_ledger_codes())
                self.assertIn('1,500.00 Dr',app.ledger_summary.cget('text'))
                transaction=next(item for item in app.ledger_table.get_children() if item in app.ledger_row_vouchers)
                app.ledger_table.selection_set(transaction)
                with patch('riju.ledger_ui.messagebox.showinfo') as info:
                    app.ledger_voucher();self.assertIn('R-TEST',info.call_args.args[1])
                with patch('riju.ledger_ui.filedialog.asksaveasfilename',return_value=str(p/'ledger.xlsx')),patch('riju.ledger_ui.messagebox.showinfo'):
                    app.export_ledgers('xlsx')
                wb=load_workbook(p/'ledger.xlsx');self.assertEqual(wb.sheetnames,['1010']);wb.close()
                with patch('riju.ledger_ui.filedialog.asksaveasfilename',return_value=str(p/'ledger.html')),patch('riju.ledger_ui.webbrowser.open',return_value=True) as browser:
                    app.export_ledgers('html');browser.assert_called_once();self.assertTrue((p/'ledger.html').is_file())
                app.ledger_category.set('All ledgers');app.select_all_ledgers();self.assertEqual(len(app.selected_ledger_pack()['books']),len(app.state['accounts']))
                app.ledger_search.set('does not exist');app.update();self.assertFalse(app.selected_ledger_codes())
                with self.assertRaises(ValueError):app.export_ledgers('pdf')
                app.ledger_search.set('1010');app.ledger_from.set('2024-04-01');app.ledger_to.set('2024-04-30');app.render_ledger()
                self.assertIn('0 lines',app.ledger_summary.cget('text'));self.assertIn('1,500.00 Dr',app.ledger_summary.cget('text'))
                app.branch.set('Kammanahalli');app.show('Ledger A/c');app.ledger_category.set('Bank books');app.update()
                self.assertEqual(app.ledger_from.get(),'2024-04-01')
                self.assertEqual(app.selected_ledger_codes(),['1010'])
                self.assertIn('0.00',app.ledger_summary.cget('text'))
                self.assertFalse(errors,errors)
            finally:app.destroy()

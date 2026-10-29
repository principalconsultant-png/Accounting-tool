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

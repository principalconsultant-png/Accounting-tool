import copy
import csv
import io
from pathlib import Path
import tempfile
import unittest
from openpyxl import load_workbook
from riju import core,ap,vendor_import as v
from riju.storage import Vault


def source(rows):
    out=io.StringIO();writer=csv.writer(out);writer.writerow(v.HEADERS);writer.writerows(rows);return out.getvalue().encode('utf-8-sig')


class VendorImportTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def preview(self,rows):return v.preview(self.s,source(rows),'vendors.csv')
    def test_preview_is_readonly_defaults_save_active_and_inactive(self):
        before=copy.deepcopy(self.s);p=self.preview([['Training Pharma','','0007',''],['Training Inactive',45,'REF','No']]);self.assertEqual(before,self.s);self.assertEqual([r['status'] for r in p['rows']],['NEW','NEW']);created=v.save_selected(self.s,p,[0,1]);self.assertEqual([r['credit_days'] for r in created],[30,45]);self.assertEqual([r['active'] for r in created],[True,False]);self.assertEqual(created[0]['reference'],'0007');self.assertFalse(self.s['vouchers']);self.assertEqual(self.s['audit'][-1]['action'],'AP_VENDOR_BULK_IMPORTED')
    def test_existing_historical_and_in_file_duplicates_never_overwrite(self):
        old=ap.save_vendor(self.s,dict(name='Old Training Supplier',credit_days='10'));ap.save_vendor(self.s,dict(name='Renamed Training Supplier',credit_days='20'),old['id']);before=copy.deepcopy(self.s)
        p=self.preview([['Old Training Supplier',30,'CHANGED','No'],['Renamed Training Supplier',30,'','Yes'],['New Training',30,'','Yes'],['New-Training',45,'','Yes']]);self.assertEqual([r['status'] for r in p['rows']],['DUPLICATE','DUPLICATE','NEW','DUPLICATE']);self.assertEqual(before,self.s)
        v.save_selected(self.s,p,[2]);self.assertEqual(ap.vendor(self.s,old['id'])['credit_days'],20);self.assertEqual(len(self.s['ap']['vendors']),2)
    def test_partial_selection_and_late_duplicate_group_rolls_back(self):
        p=self.preview([['First Training',30,'','Yes'],['Second Training',30,'','Yes']]);ap.save_vendor(self.s,dict(name='Second Training',credit_days='15'));before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):v.save_selected(self.s,p,[0,1])
        self.assertEqual(self.s,before);v.save_selected(self.s,p,[0]);self.assertEqual(len(self.s['ap']['vendors']),2)
        with self.assertRaises(ValueError):v.save_selected(self.s,p,[0])
    def test_invalid_fields_formulas_and_default_only_placeholders(self):
        p=self.preview([['',30,'','Yes'],['Bad days','1.5','','Yes'],['Bad status',30,'','Perhaps'],['=FORMULA',30,'','Yes'],['Negative',-1,'','Yes'],['Too long',3651,'','Yes'],['Missing name',30,'','Yes']]);self.assertEqual(p['ignored'],1);self.assertEqual([r['status'] for r in p['rows']],['INVALID']*5+['NEW']);before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):v.save_selected(self.s,p,[0,5])
        self.assertEqual(before,self.s)
    def test_template_excel_date_free_text_and_vault(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for ext in ('csv','xlsx'):v.template(root/('vendors.'+ext))
            w=load_workbook(root/'vendors.xlsx');self.assertEqual(w.sheetnames,['Vendors','Instructions']);ws=w['Vendors'];self.assertEqual([c.value for c in ws[1]],list(v.HEADERS));ws['A2']='Excel Training';ws['C2']='00012';w.save(root/'filled.xlsx');w.close()
            p=v.preview(self.s,(root/'filled.xlsx').read_bytes(),'filled.xlsx');self.assertEqual(len(p['rows']),1);self.assertEqual(p['ignored'],999);v.save_selected(self.s,p,[0]);vault=Vault(root/'book.json',demo=True);vault.save(self.s);self.assertEqual(vault.load(),self.s)
    def test_headers_extra_cells_and_selection_guards(self):
        with self.assertRaises(ValueError):v.preview(self.s,b'name,unknown\nA,B','bad.csv')
        p=v.preview(self.s,source([['Extra',30,'','Yes','Unexpected']]),'extra.csv');self.assertEqual(p['rows'][0]['status'],'INVALID')
        p=self.preview([['Training',30,'','Yes']])
        for indices in ([],[0,0],[-1],[True]):
            with self.assertRaises(ValueError):v.save_selected(self.s,p,indices)


import os
@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class VendorImportDesktopTests(unittest.TestCase):
    def test_templates_review_mixed_rows_create_and_editable_master(self):
        from unittest.mock import patch
        from riju.app import App
        from test_gui import TaxDepreciationDesktopTests
        from tkinter import ttk
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=App(Vault(root/'book.json',demo=True))
            try:
                app.show('Vendor master')
                for ext in ('xlsx','csv'):
                    with patch('riju.ap_ui.filedialog.asksaveasfilename',return_value=str(root/('vendor-template.'+ext))),patch('riju.ap_ui.messagebox.showinfo'):app.vendor_master_template(ext)
                    self.assertTrue((root/('vendor-template.'+ext)).exists())
                path=root/'vendors.csv';path.write_bytes(source([['Desktop Training',45,'0009','Yes'],['Desktop Training',30,'DUP','No'],['Bad',-1,'','Yes']]))
                with patch('riju.ap_ui.filedialog.askopenfilename',return_value=str(path)):helper.press(app.content,'Upload bulk vendors')
                app.update();form=helper.form(app);table=next(w for w in helper.walk(form) if isinstance(w,ttk.Treeview));self.assertEqual(len(table.get_children()),3);self.assertIn('DUPLICATE',table.item('1')['tags']);self.assertFalse(app.state['ap']['vendors'])
                helper.press(form,'Select all new vendors')
                with patch('riju.ap_ui.messagebox.showinfo'):helper.press(form,'Save selected new vendors')
                app.update();self.assertEqual(len(app.vendor_table.get_children()),1);vendor=app.state['ap']['vendors'][0];self.assertEqual(vendor['reference'],'0009');self.assertFalse(app.state['vouchers']);app.vendor_table.selection_set(vendor['id']);helper.press(app.content,'Edit selected vendor');form=helper.form(app);self.assertIn('Edit AP vendor',form.title());self.assertEqual(len(app.vault.load()['ap']['vendors']),1)
            finally:app.destroy()

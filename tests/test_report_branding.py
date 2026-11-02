import copy
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from openpyxl import load_workbook
from pypdf import PdfReader
from riju import core,foundation,financial_reports as f,report_branding as b
from riju.storage import Vault
from test_financial_reports import pair


class TFormAndLogoTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state()
        core.post(self.s,'2025-04-01','Capital',pair('1010','3000',100000),opening=True)
        core.post(self.s,'2025-05-01','Loss',pair('4530','2000',15000))
        core.post(self.s,'2025-05-02','Depreciation',pair('4570','1050',1000))
    def pack(self,mode='Balance sheet - T form',branch='ALL'):return f.snapshot(self.s,mode,'2025-04-01','2026-03-31',branch)
    def logos(self,root):
        for slot,color in [('client','red'),('axiom','blue')]:
            path=root/(slot+'.png');Image.new('RGB',(240,80),color).save(path);b.set_logo(self.s,slot,path);path.unlink()
    def test_t_form_signed_balances_equivalence_and_branch_scope(self):
        before=copy.deepcopy(self.s);p=self.pack();vertical=self.pack('Balance sheet')
        self.assertEqual(p['rows'][-1],['TOTAL LIABILITIES AND EQUITY',99000,'TOTAL ASSETS',99000])
        self.assertIn(['Unclosed accumulated result',-16000], [r[:2] for r in p['rows']])
        self.assertTrue(any('1050' in r[2] and r[3]==-1000 for r in p['rows']))
        self.assertEqual(p['controls'],vertical['controls']);self.assertEqual(self.pack(branch='KM')['rows'][-1][1::2],[0,0]);self.assertEqual(before,self.s)
    def test_year_close_does_not_duplicate_result(self):
        foundation.close_year(self.s,2025)
        p=self.pack();self.assertEqual(p['rows'][-1][1::2],[99000,99000]);self.assertFalse(any(p['controls'].values()))
    def test_embedded_logos_survive_original_delete_and_vault_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.logos(root);v=Vault(root/'book.json',demo=True);v.save(self.s);loaded=v.load()
            self.assertEqual(b.snapshot(loaded),b.snapshot(self.s));self.assertEqual(len(self.pack()['logos']),2)
            frozen=self.pack();b.remove_logo(self.s,'client');self.assertEqual(len(frozen['logos']),2);self.assertEqual(set(self.pack()['logos']),{'axiom'})
    def test_pdf_logos_every_page_and_excel_media_position(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.logos(root);before=copy.deepcopy(self.s)
            for i in range(60):core.post(self.s,'2025-06-01','Narration '*20,pair('1010','4000',100))
            before=copy.deepcopy(self.s);p=self.pack('General ledger');f.export_pdf(p,root/'gl.pdf');pages=PdfReader(root/'gl.pdf').pages
            self.assertGreater(len(pages),1)
            for page in pages:self.assertEqual(len(page.images),2)
            p=self.pack();f.export_xlsx(p,root/'t.xlsx');f.export_pdf(p,root/'t.pdf')
            wb=load_workbook(root/'t.xlsx');ws=wb.active;self.assertEqual(len(ws._images),2)
            self.assertEqual([im.anchor._from.col for im in ws._images],[0,2]);self.assertEqual(ws['A4'].value,self.s['settings']['entity']);wb.close()
            text=' '.join(p.extract_text() for p in PdfReader(root/'t.pdf').pages);self.assertIn('TOTAL ASSETS',text);self.assertIn('TOTAL LIABILITIES',text)
            f.export_csv(p,root/'t.csv');self.assertIn('CSV is text only', (root/'t.csv').read_text(encoding='utf-8-sig'));self.assertEqual(before,self.s)
    def test_cashflow_and_full_pack_have_logos(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.logos(root);packs=f.report_pack(self.s,'2025-04-01','2026-03-31')
            self.assertTrue(all(len(p['logos'])==2 for p in packs));f.export_pack_xlsx(packs,root/'all.xlsx');f.export_pdf(packs,root/'all.pdf')
            wb=load_workbook(root/'all.xlsx');self.assertTrue(all(len(ws._images)==2 for ws in wb));wb.close()
            self.assertTrue(all(len(page.images)==2 for page in PdfReader(root/'all.pdf').pages))
    def test_invalid_image_or_slot_never_changes_books(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.png';p.write_bytes(b'not an image');before=copy.deepcopy(self.s)
            for slot in ('client','invalid'):
                with self.assertRaises(ValueError):b.set_logo(self.s,slot,p)
            self.assertEqual(before,self.s)


import os
@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class ReportBrandingDesktopTests(unittest.TestCase):
    def test_choose_replace_remove_and_t_form_report(self):
        from unittest.mock import patch
        from riju.app import App
        from test_gui import TaxDepreciationDesktopTests
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'client.png';Image.new('RGB',(240,80),'green').save(path)
            app=App(Vault(root/'book.json',demo=True))
            try:
                app.show('Financial reports');helper.press(app.content,'Report logos');win=helper.form(app)
                with patch('riju.app.filedialog.askopenfilename',return_value=str(path)):
                    helper.press(win,'Choose / replace')
                self.assertIn('client',b.snapshot(app.state));helper.press(win,'Done')
                app.report_mode.set('Balance sheet - T form');app.refresh_financial_report()
                self.assertEqual(app.financial_snapshot['layout'],'t_form');self.assertIn('client',app.financial_snapshot['logos'])
                app.show('Settings & backup');helper.press(app.content,'Report logos — client / AXIOM');win=helper.form(app);helper.press(win,'Remove');self.assertEqual(b.snapshot(app.state),{});helper.press(win,'Done')
                self.assertEqual(app.vault.load()['settings']['report_logos'],{})
            finally:app.destroy()

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
            finally: app.destroy()

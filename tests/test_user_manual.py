import tempfile
import unittest
from pathlib import Path
from pypdf import PdfReader
from scripts.build_user_manual import build_pdf

class UserManualTests(unittest.TestCase):
    def test_full_guide_pdf_contains_workflows_template_and_exercises(self):
        source=Path(__file__).resolve().parents[1]/'docs/USER_TRAINING_GUIDE.md'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'manual.pdf';build_pdf(source,path);doc=PdfReader(path);text=' '.join(' '.join(page.extract_text() for page in doc.pages).split())
            for topic in ('AP Vendor Invoices','Credit period','no_separate_tax','Mark selected invoices paid','Approve all valid rows','Guided training exercises','Suggested training session','10,000'):
                self.assertTrue(topic in text,topic)
            self.assertGreater(len(doc.pages),20);self.assertEqual(len(doc.outline),25)

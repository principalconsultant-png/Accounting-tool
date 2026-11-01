import copy
import tempfile
import unittest
from pathlib import Path
from openpyxl import load_workbook
from pypdf import PdfReader
from riju import core,bank_calendar as cal,reconciliation as r,financial_reports as reports

class CalendarTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def install(self,rev=cal.REVISIONS[-1],bank='Other/private'):return cal.install(self.s,rev,'Reviewed bank source',bank,True)
    def test_revision_amendment_history_and_manual_dates(self):
        self.install(cal.REVISIONS[0]);old=copy.deepcopy(self.s['settings']['bank_reconciliation'])
        self.assertFalse(cal.explain(self.s,'2026-03-31')['working'])
        self.install();self.assertTrue(cal.explain(self.s,'2026-03-31')['working']);self.assertFalse(cal.explain(self.s,'2026-03-30')['working'])
        self.assertEqual(len(self.s['settings']['bank_reconciliation']['calendar_history']),2)
        self.assertEqual(old['calendar_datasets']['2026']['id'],cal.REVISIONS[0])
        r.set_policy(self.s,0,False,'date,name,source\n2026-03-31,Local closure,Actual bank notice\n','2026-03-30')
        self.assertTrue(cal.explain(self.s,'2026-03-30')['working']);self.assertFalse(cal.explain(self.s,'2026-03-31')['working'])
        self.assertEqual(self.s['settings']['bank_reconciliation']['calendar_datasets']['2026']['id'],cal.REVISIONS[-1]);core.verify_audit(self.s)
        with self.assertRaises(ValueError):self.install(cal.REVISIONS[0])
    def test_weekend_city_bank_class_and_year_boundary(self):
        self.install()
        for d in ['2026-03-07','2026-03-21','2026-03-28','2026-09-03','2026-10-18','2026-11-26']:
            # 21 is the sourced Eid holiday; 28 fourth Saturday; 18 Sunday.
            expected=d not in ['2026-03-21','2026-03-28','2026-10-18']
            self.assertEqual(cal.explain(self.s,d)['working'],expected,d)
        self.assertEqual(cal.next_day(self.s,'2026-03-27')['date'],'2026-03-31')
        self.assertFalse(cal.explain(self.s,'2026-09-27')['working']);self.install(bank='Public sector/RRB');self.assertTrue(cal.explain(self.s,'2026-09-27')['working'])
        self.s['holidays'].append('2026-09-27');self.assertFalse(cal.explain(self.s,'2026-09-27')['working'])
        self.assertIn('2027',cal.next_day(self.s,'2026-12-31')['warning'])
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):cal.install(self.s,'unknown','review',confirmed=True)
        with self.assertRaises(ValueError):cal.install(self.s,cal.REVISIONS[-1],'',confirmed=True)
        self.assertEqual(before,self.s)
    def test_existing_match_snapshot_and_exports(self):
        self.install(cal.REVISIONS[0]);self.s['holidays'].append('2026-04-06')
        v=core.post(self.s,'2026-04-02','Receipt',[dict(account='1010',branch='JP',debit=10000,credit=0),dict(account='4000',branch='JP',debit=0,credit=10000)])
        r.import_statement(self.s,b'date,narration,reference,debit,credit,balance\n2026-04-02,Receipt,R1,0,100,100\n','calendar.csv','1010','ALL','2026-04-01','2026-04-30','0','100')
        m=r.match_existing(self.s,[self.s['bank_lines'][0]['id']],[v['id']+':0']);saved=copy.deepcopy(m)
        self.install();self.assertEqual(m,saved);self.assertEqual(m['policy']['manual_holidays'],['2026-04-06'])
        with tempfile.TemporaryDirectory() as tmp:
            pack=cal.snapshot(self.s,'2026-03-27','2026-04-03');x=Path(tmp)/'calendar.xlsx';p=Path(tmp)/'calendar.pdf';reports.export_xlsx(pack,x);reports.export_pdf(pack,p)
            wb=load_workbook(x);self.assertIn('30',str(list(wb.active.values)));wb.close();self.assertIn('Mahavir', ''.join(page.extract_text() for page in PdfReader(p).pages))

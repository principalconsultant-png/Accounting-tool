import tempfile
import unittest
from pathlib import Path
from scripts.build_worked_example import build_example

class WorkedExampleTests(unittest.TestCase):
    def test_guide_scenario_reconciles_sales_ap_bank_and_all_final_reports(self):
        with tempfile.TemporaryDirectory() as d:
            r=build_example(d);self.assertTrue(r['proof']['ready']);self.assertEqual(r['cash_flow']['profit'],100000);self.assertEqual(r['cash_flow']['totals']['Operating'],160000);self.assertEqual(r['cash_flow']['closing'],5160000)
            self.assertEqual(len(r['state']['vouchers']),7)
            for name in ('Worked-Example-Daily-Sales.csv','Worked-Example-Daily-Sales.xlsx','Worked-Example-Bank.csv','Worked-Example-Financial-Reports.xlsx','Worked-Example-Financial-Reports.pdf'):self.assertTrue((Path(d)/name).is_file())

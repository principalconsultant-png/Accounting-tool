import copy
import io
from pathlib import Path
import tempfile
import unittest
from datetime import datetime
from openpyxl import Workbook
from riju import core,bulk_import as bulk,activity,history

HEADER='date,reference,branch,narration,debit_account,credit_account,amount,journal_id\n'
class BulkImportTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def stage(self,rows='2026-04-01,B1,JP,Test expense,4590,2000,100,\n',kind='Expense'):
        return bulk.stage(self.s,(HEADER+rows).encode(),'synthetic.csv',kind)
    def review(self,q,index=0,approved=True):bulk.review_row(self.s,q['id'],index,approved,'Synthetic reviewed source')
    def bad(self,fn):
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):fn()
        self.assertEqual(before,self.s)
    def test_staging_never_posts_approved_batch_posts_once_and_traces(self):
        q=self.stage();self.assertFalse(self.s['vouchers']);self.review(q);ids=bulk.approve(self.s,q['id']);self.assertEqual(len(ids),1);self.assertEqual(core.balances(self.s,'2026-04-30')['4590'],10000)
        self.assertEqual(activity.report(self.s)['metrics']['import_rows_processed'],1);self.assertTrue(history.trace_voucher(self.s,ids[0])['imports']);self.bad(lambda:bulk.approve(self.s,q['id']))
    def test_invalid_row_retained_then_rejected_valid_row_posts(self):
        q=self.stage('2026-04-01,B1,JP,Good,4590,2000,100,\nbad,B2,JP,Bad,4590,2000,1,\n');self.assertEqual(q['rows'][1]['review'],'INVALID');self.review(q);self.bad(lambda:bulk.approve(self.s,q['id']));self.review(q,1,False);bulk.approve(self.s,q['id']);self.assertEqual(len(self.s['vouchers']),1)
    def test_bad_amount_precision_formula_negative_and_expense_classification(self):
        for n in ('1.001','-1','=SUM(1)','NaN'):
            q=self.stage(f'2026-04-01,{n},JP,Invalid,4590,2000,{n},\n');self.assertEqual(q['rows'][0]['review'],'INVALID');bulk.cancel(self.s,q['id'],'Invalid synthetic source')
        q=self.stage('2026-04-01,CAPITAL,JP,Not expense,1030,2000,100,\n');self.assertEqual(q['rows'][0]['review'],'INVALID')
    def test_changed_file_duplicate_reference_even_changed_amount(self):
        q=self.stage();self.review(q);bulk.approve(self.s,q['id']);q2=self.stage('2026-04-01,B1,JP,Changed description,4590,2000,999,\n');self.assertEqual(q2['rows'][0]['review'],'DUPLICATE');self.bad(lambda:self.review(q2))
    def test_duplicate_within_file_is_explicit(self):
        q=self.stage('2026-04-01,B1,JP,A,4590,2000,100,\n2026-04-01,B1,JP,B,4590,2000,200,\n');self.assertEqual(q['rows'][1]['review'],'DUPLICATE')
    def test_branch_and_year_references_isolated(self):
        q=self.stage('2026-04-01,B1,JP,A,4590,2000,100,\n2026-04-01,B1,VK,B,4590,2000,100,\n2025-04-01,B1,JP,C,4590,2000,100,\n');[self.review(q,i) for i in range(3)];bulk.approve(self.s,q['id']);self.assertEqual(len(self.s['vouchers']),3)
    def test_atomic_approval_if_later_row_locked_or_inactive(self):
        q=self.stage('2026-04-01,B1,JP,A,4590,2000,100,\n2026-05-01,B2,JP,B,4590,2000,200,\n');self.review(q,0);self.review(q,1);self.s['locked_through']='2026-04-30';self.bad(lambda:bulk.approve(self.s,q['id']));self.assertFalse(self.s['vouchers'])
    def test_opening_rows_group_once_and_preserve_all_source_counts(self):
        q=self.stage('2024-04-01,O1,JP,Cash opening,1000,3000,100,\n2024-04-01,O2,JP,Bank opening,1010,3000,200,\n',kind='Opening');self.review(q,0);self.review(q,1);bulk.approve(self.s,q['id']);self.assertEqual(len(self.s['vouchers']),1);self.assertTrue(self.s['vouchers'][0]['opening']);self.assertEqual(self.s['vouchers'][0]['source']['row_count'],2)
    def test_compound_journal_cannot_partly_reject(self):
        q=self.stage('2026-04-01,R1,JP,A,4590,2000,100,J1\n2026-04-01,R2,JP,B,4510,2000,200,J1\n',kind='Journal');self.review(q,0);self.review(q,1,False);self.bad(lambda:bulk.approve(self.s,q['id']));self.review(q,1);bulk.approve(self.s,q['id']);self.assertEqual(len(self.s['vouchers']),1)
    def test_petty_cash_requires_cash_counter(self):
        q=self.stage(kind='Petty cash');self.assertEqual(q['rows'][0]['review'],'INVALID');q2=self.stage('2026-04-01,P1,JP,Cash expense,4590,1000,100,\n',kind='Petty cash');self.review(q2);bulk.approve(self.s,q2['id']);self.assertEqual(core.balances(self.s,'2026-04-30')['1000'],-10000)
    def test_cancel_frees_unposted_source_for_corrected_reimport(self):
        q=self.stage();bulk.cancel(self.s,q['id'],'Wrong source');q2=self.stage();self.assertEqual(q2['rows'][0]['review'],'PENDING')
    def test_xlsx_mapping_exact_sheet_and_date_literal(self):
        w=Workbook();ws=w.active;ws.title='Source';ws.append(['Booked','Ref','Unit','Text','DR','CR','INR']);ws.append([datetime(2026,4,1),'XLSX1','JP','Synthetic',4590,2000,100]);buf=io.BytesIO();w.save(buf);w.close();mapping=dict(zip(bulk.FIELDS[:-1],['Booked','Ref','Unit','Text','DR','CR','INR']))
        self.bad(lambda:bulk.stage(self.s,buf.getvalue(),'source.xlsx','Expense',mapping,'BAD'))
        q=bulk.stage(self.s,buf.getvalue(),'source.xlsx','Expense',mapping,'Source');self.review(q);bulk.approve(self.s,q['id']);core.verify_audit(self.s)
    def test_unreviewed_rejected_only_and_readonly_exports(self):
        q=self.stage();self.bad(lambda:bulk.approve(self.s,q['id']));self.review(q,0,False);self.bad(lambda:bulk.approve(self.s,q['id']));old=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            for kind in ('xlsx','pdf'):bulk.export(self.s,q['id'],Path(d)/('review.'+kind),kind)
        self.assertEqual(old,self.s)
    def test_daily_sales_individual_approval_and_rejection(self):
        from test_sales import workbook
        from riju import sales_import
        raw=workbook([dict(revenues={'treatment':100},payments={'cash':100},receipt='R1'),dict(revenues={'treatment':200},payments={'cash':200},receipt='R2')]);q=sales_import.stage_sales(self.s,raw,'sales.xlsx','JP')
        sales_import.review_sales_row(self.s,q['id'],0,True,'Reviewed receipt');self.bad(lambda:sales_import.approve_sales(self.s,q['id']));sales_import.review_sales_row(self.s,q['id'],1,False,'Excluded duplicate source');sales_import.approve_sales(self.s,q['id']);self.assertEqual(len(self.s['vouchers']),1);self.assertEqual(activity.report(self.s)['metrics']['import_rows_processed'],1)

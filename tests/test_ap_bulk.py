import copy
import csv
import io
from pathlib import Path
import tempfile
import time
import unittest
from openpyxl import load_workbook
from pypdf import PdfReader
from riju import core,ap,ap_bulk as b,activity,financial_reports as reports,history
from riju.storage import Vault


def invoice(**kw):
    r=dict(vendor_name='Bulk training vendor',reference='BULK-01',invoice_date='2026-04-01',received_date='2026-04-02',accounting_date='2026-04-02',credit_days='',due_basis='Receipt date',payment_date='',branch='JP',amount='1000',payable='2000',cost_account='1100',basis='Synthetic medicine stock/source review',existing_voucher='');r.update(kw);return r

def raw(rows,legacy=False):
    out=io.StringIO();headers=list(b.HEADERS)
    if legacy:headers[9]='Net amount Payable to Vendor';headers[10]='Tax payables Ledger';headers[11]='New Accural / Cost Asset Ledger';headers=headers[:-1]
    w=csv.writer(out);w.writerow(headers)
    for r in rows:w.writerow([r[k] for k in b.FIELDS[:len(headers)]])
    return out.getvalue().encode()

class ApBulkTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state();self.vendor=ap.save_vendor(self.s,dict(name='Bulk training vendor',credit_days='45'))
    def stage(self,rows):return b.stage(self.s,raw(rows),'bulk-invoices.csv')
    def approve(self,q,indices=None):b.review(self.s,q['id'],indices if indices is not None else [i for i,r in enumerate(q['rows']) if r['validation']=='VALID'],True,'Reviewed supplier invoices and accounting/tax allocation',True)
    def test_upload_no_post_vendor_default_accrual_and_forecast(self):
        q=self.stage([invoice()]);self.assertFalse(self.s['vouchers']);self.assertFalse(self.s['ap']['invoices']);self.assertEqual(q['rows'][0]['values']['credit_days'],'45');self.assertEqual(q['rows'][0]['due_date'],'2026-05-17');self.approve(q);result=b.post(self.s,q['id']);self.assertEqual(result,dict(registered=1,new_accruals=1,linked_existing=0));self.assertEqual(b.batch(self.s,q['id'])['status'],'PROCESSED')
        actual=core.balances(self.s,'2026-04-30');self.assertEqual((actual['1100'],actual['2000'],actual['1010']),(100000,-100000,0));self.assertEqual(ap.forecast(self.s,'2026-04-30','2026-04-30','2026-05-31')[0]['amount'],-100000);self.assertEqual(activity.report(self.s)['metrics']['import_rows_processed'],1)
        with self.assertRaises(ValueError):b.post(self.s,q['id'])
    def test_duplicates_invalid_rejection_without_confirmation_and_atomic_post(self):
        q=self.stage([invoice(),invoice(amount='1200'),invoice(reference='BAD',cost_account='2100')]);self.assertEqual([r['validation'] for r in q['rows']],['VALID','DUPLICATE','INVALID'])
        b.review(self.s,q['id'],[1,2],False,'Duplicate/wrong account rejected',False)
        with self.assertRaises(ValueError):b.review(self.s,q['id'],[0],True,'Not yet source confirmed',False)
        self.approve(q);b.post(self.s,q['id']);self.assertEqual(len(self.s['ap']['invoices']),1);self.assertEqual(len(self.s['vouchers']),1)
        duplicate=self.stage([invoice(amount='900')]);self.assertEqual(duplicate['rows'][0]['validation'],'DUPLICATE')
    def test_missing_vendor_master_revalidation_and_changed_defaults_block(self):
        q=self.stage([invoice(vendor_name='New supplier')]);self.assertEqual(q['rows'][0]['validation'],'INVALID');new=ap.save_vendor(self.s,dict(name='New supplier',credit_days='15'));q=b.revalidate(self.s,q['id']);self.assertEqual(q['rows'][0]['validation'],'VALID');self.approve(q)
        ap.save_vendor(self.s,dict(name='New supplier',credit_days='30'),new['id']);before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'Revalidate'):b.post(self.s,q['id'])
        self.assertEqual(before,self.s);q=b.revalidate(self.s,q['id']);self.assertEqual(q['rows'][0]['review'],'PENDING');self.assertEqual(q['rows'][0]['values']['credit_days'],'30');self.approve(q);b.post(self.s,q['id'])
    def test_queued_and_manual_duplicates_and_period_change_cannot_partially_post(self):
        first=self.stage([invoice()]);second=self.stage([invoice(reference='NEW'),invoice()]);self.assertEqual(second['rows'][1]['validation'],'DUPLICATE');b.cancel(self.s,first['id'],'Unused file cancelled');second=b.revalidate(self.s,second['id']);self.assertTrue(all(r['validation']=='VALID' for r in second['rows']));self.approve(second)
        self.s['locked_through']='2026-04-01';q=b.batch(self.s,second['id']);q['rows'][1]['raw']['accounting_date']='2026-04-01'
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):b.post(self.s,q['id'])
        self.assertEqual(before,self.s);self.assertFalse(self.s['vouchers'])
    def test_existing_source_link_does_not_repost_and_source_capacity_applies(self):
        original=core.post(self.s,'2026-04-02','Reviewed existing tax accrual',[dict(account='1100',branch='JP',debit=100000,credit=0),dict(account='2000',branch='JP',debit=0,credit=100000)])
        q=self.stage([invoice(existing_voucher=original['id'],cost_account='')]);self.approve(q);result=b.post(self.s,q['id']);self.assertEqual(result['linked_existing'],1);self.assertEqual(len(self.s['vouchers']),1);self.assertEqual(len(self.s['ap']['invoices']),1)
        q=self.stage([invoice(reference='EXCEED',amount='1',existing_voucher=original['id'])]);self.assertEqual(q['rows'][0]['validation'],'INVALID')
    def test_customer_headings_and_default_only_rows(self):
        defaults=dict.fromkeys(b.FIELDS,'');defaults.update(credit_days='45',due_basis='Receipt date',payable='2000');q=b.stage(self.s,raw([defaults,invoice()],True),'customer-layout.csv');self.assertEqual(len(q['rows']),1);self.assertEqual(q['ignored_placeholders'],1);self.assertTrue(q['warnings']);self.assertEqual(q['rows'][0]['validation'],'VALID')
    def test_excel_template_lookup_dates_roundtrip_and_literal_formulas(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);b.template(root/'template.xlsx',self.s);w=load_workbook(root/'template.xlsx');self.assertEqual(w.sheetnames,['Invoices','Vendors','Units','Accounts','Instructions']);ws=w['Invoices']
            for col,key in enumerate(b.FIELDS,1):ws.cell(2,col,invoice()[key])
            from datetime import datetime
            ws['C2']=datetime(2026,4,1);ws['D2']=datetime(2026,4,2);ws['E2']=datetime(2026,4,2);w.save(root/'filled.xlsx');w.close();q=b.stage(self.s,(root/'filled.xlsx').read_bytes(),'filled.xlsx');self.assertEqual(q['rows'][0]['validation'],'VALID');self.assertEqual(len(q['rows']),1)
        q=self.stage([invoice(reference='FORMULA',amount='=1000'),invoice(reference='DATES',invoice_date='01/04/2026'),invoice(reference='RATE',credit_days='1.5')]);self.assertTrue(all(r['validation']=='INVALID' for r in q['rows']))
    def test_review_export_and_vault_roundtrip(self):
        q=self.stage([invoice()]);self.approve(q);b.post(self.s,q['id']);self.assertEqual(history.trace_voucher(self.s,self.s['vouchers'][0]['id'])['imports'][0]['kind'],'ap_bulk')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pack=b.snapshot(self.s,q['id']);reports.export_xlsx(pack,root/'review.xlsx');reports.export_pdf(pack,root/'review.pdf');self.assertIn('BULK-01',' '.join(p.extract_text() for p in PdfReader(root/'review.pdf').pages));v=Vault(root/'book.json',demo=True);v.save(self.s);self.assertEqual(v.load(),self.s)
    def test_300_invoice_scale_atomic_shared_engine(self):
        started=time.perf_counter();q=self.stage([invoice(reference='SCALE-'+str(i)) for i in range(300)]);self.approve(q);b.post(self.s,q['id']);self.assertEqual(len(self.s['vouchers']),300);self.assertEqual(len(self.s['ap']['invoices']),300);self.assertEqual(activity.report(self.s)['metrics']['import_rows_processed'],300);self.assertLess(time.perf_counter()-started,15)

    def test_late_manual_duplicate_rolls_back_all_selected_rows(self):
        q=self.stage([invoice(reference='ATOMIC-1'),invoice(reference='ATOMIC-2')]);self.approve(q)
        values,_=b.canonical(self.s,invoice(reference='ATOMIC-2'));ap.enter_invoice(self.s,values);before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'already registered'):b.post(self.s,q['id'])
        self.assertEqual(before,self.s);self.assertEqual(len(self.s['ap']['invoices']),1);self.assertEqual(b.batch(self.s,q['id'])['status'],'PENDING_REVIEW')

    def test_extra_data_retained_as_row_error_without_losing_other_invoices(self):
        lines=raw([invoice(reference='GOOD'),invoice(reference='EXTRA')]).decode().splitlines();lines[-1]+=',unexpected-extra-cell';q=b.stage(self.s,('\n'.join(lines)+'\n').encode(),'extra-cell.csv')
        self.assertEqual([r['validation'] for r in q['rows']],['VALID','INVALID']);self.assertEqual(q['rows'][1]['raw']['_extra_values'],['unexpected-extra-cell']);self.assertFalse(self.s['vouchers'])

    def test_existing_source_cannot_refer_to_simulated_new_row_voucher(self):
        q=self.stage([invoice(reference='REAL-NEW'),invoice(reference='GUESS-LINK',existing_voucher='VCH-2026-00001',cost_account='')]);self.assertEqual([r['validation'] for r in q['rows']],['VALID','INVALID']);self.assertIn('actual books',q['rows'][1]['error']);self.assertFalse(self.s['vouchers'])

    def test_vendor_spelling_reason_suggestion_and_original_fields_survive_failure(self):
        ap.save_vendor(self.s,dict(name='Synthetic Pharma Supplier',credit_days='30'))
        q=self.stage([invoice(vendor_name='Synthetic Pharme Supplier',reference='TYPO-01',amount='16547')]);r=q['rows'][0]
        self.assertEqual(r['validation'],'INVALID');self.assertIn('Synthetic Pharme Supplier',r['error']);self.assertIn('Synthetic Pharma Supplier',r['error']);self.assertIn('cancel the unused batch',r['error'])
        d=b.row_display(self.s,r);self.assertEqual(d['invoice_date'],'2026-04-01');self.assertEqual(d['amount'],1654700);self.assertEqual(d['branch'],'JP');self.assertIn('1100 Medicine inventory',d['cost']);self.assertIn('row(s) 2',b.issue_summary(q));self.assertEqual(len(self.s['ap']['vendors']),2);self.assertFalse(self.s['vouchers'])
        pack=b.snapshot(self.s,q['id']);self.assertEqual(pack['rows'][0][4],r['error']);self.assertEqual(pack['rows'][0][7],1654700)

    def test_invalid_amount_keeps_original_text_without_zero_and_summary_is_bounded(self):
        rows=[invoice(vendor_name='Unknown supplier '+str(i),reference='ISSUE-'+str(i),amount='bad-amount') for i in range(10)]
        q=self.stage(rows);d=b.row_display(self.s,q['rows'][0]);self.assertIsNone(d['amount']);self.assertEqual(d['amount_text'],'bad-amount');self.assertIn('additional issue types',b.issue_summary(q));self.assertEqual(len(b.issue_summary(q).splitlines()),4)

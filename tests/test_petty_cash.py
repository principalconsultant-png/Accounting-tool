import copy,csv,io,tempfile,unittest,os
from pathlib import Path
from datetime import datetime
from openpyxl import Workbook,load_workbook
from riju import core,foundation,petty_cash as p,bulk_import as b,financial_reports as f,cash_flow,activity
from riju.storage import Vault


def entry(**kw):
    v=dict(date='2026-09-01',reference='PC-TEST-1',branch='JP',category='Office',treatment='Expense',account='4590',amount='10',narration='Synthetic office purchase',basis='Reviewed original cash voucher; no separate tax');v.update(kw);return v

def standard(entries):
    out=io.StringIO();w=csv.writer(out);w.writerow(p.HEADERS);w.writerows([[v.get(k,'') for k in p.FIELDS] for v in entries]);return out.getvalue().encode()

def matrix():
    w=Workbook();s=w.active;s.title='Source'
    for row in [[None,'Date',datetime(2026,9,1),datetime(2026,9,2)],[None,'Op.Balance',-5,'=C6'],[None,'Cash Received',10,0],[None,'Total for Day','=C2+C3','=D2+D3'],[None,'Expenses','=C12','=D12'],[None,'Closing Balance','=C4-C5','=D4-D5'],[None,'Expense Details'],[None,'Gas',2,None],[None,'Purchase of Medicines',None,4],[None,'Salary Payble',None,6],[None,'Advance Salary',3,None],[None,'Total','=SUM(C8:C11)','=SUM(D8:D11)'],[None,'Cumulative Expense','=C12','=C13+D12']]:s.append(row)
    out=io.BytesIO();w.save(out);return out.getvalue()


class PettyCashTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state();foundation.save_account(self.s,'1190','Synthetic staff advances','Asset','Other assets');foundation.save_account(self.s,'2310','Synthetic salaries payable','Liability','Other liabilities')
    def stage(self,entries):
        raw=standard(entries);parsed=p.read_source(raw,'cash.csv');return p.stage(self.s,raw,'cash.csv',parsed,confirmed=True)
    def approve(self,q):
        for i,r in enumerate(q['rows']):b.review_row(self.s,q['id'],i,r['review']=='PENDING','Synthetic source review')
    def test_manual_expense_and_funding_balances_and_duplicate_cross_bulk(self):
        top=p.record(self.s,entry(reference='FUND',category='Funding',treatment='Cash top-up',account='1010',amount='100'),True);v=p.record(self.s,entry(),True);bal=core.balances(self.s,'2026-09-30');self.assertEqual((bal['1000'],bal['1010'],bal['4590']),(9000,-10000,1000));self.assertEqual(v['metadata']['type'],'Payment');self.assertEqual(top['metadata']['type'],'Receipt');q=self.stage([entry()]);self.assertEqual(q['rows'][0]['review'],'DUPLICATE');self.assertEqual(activity.report(self.s)['metrics']['import_rows_processed'],0)
        with self.assertRaises(ValueError):p.record(self.s,entry(),True)
    def test_stock_advance_liability_are_not_expenses(self):
        core.post(self.s,'2026-08-31','Reviewed salary accrual',[dict(account='4520',branch='JP',debit=1000,credit=0),dict(account='2310',branch='JP',debit=0,credit=1000)])
        for v in [entry(reference='STOCK',treatment='Stock purchase',account='1100'),entry(reference='ADV',treatment='Staff advance',account='1190'),entry(reference='SAL',treatment='Liability settlement',account='2310')]:p.record(self.s,v,True)
        bal=core.balances(self.s,'2026-09-30');self.assertEqual([bal[c] for c in ('1100','1190','2310','1000')],[1000,1000,0,-3000]);self.assertEqual(next(r[3] for r in f.snapshot(self.s,'Profit and loss','2026-09-01','2026-09-30')['rows'] if r[2]=='Profit / (loss)'),0)
    def test_wrong_treatments_tax_ap_formula_and_missing_review_are_blocked(self):
        for v in [entry(treatment='Expense',account='1100'),entry(treatment='Staff advance',account='4590'),entry(treatment='Stock purchase',account='4500'),entry(treatment='Liability settlement',account='2000'),entry(treatment='Liability settlement',account='2100'),entry(treatment='Cash top-up',account='4000'),entry(account='1000'),entry(basis=''),entry(amount='=10'),entry(amount='-1')]:
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):p.record(self.s,v,True)
            self.assertEqual(before,self.s)
        with self.assertRaises(ValueError):p.record(self.s,entry(),False)
    def test_matrix_source_cells_summary_exclusion_and_atomic_post(self):
        core.post(self.s,'2026-08-31','Reviewed salary accrual',[dict(account='4520',branch='JP',debit=600,credit=0),dict(account='2310',branch='JP',debit=0,credit=600)])
        raw=matrix();parsed=p.read_source(raw,'matrix.xlsx');self.assertEqual(len(parsed['entries']),4);self.assertEqual(sum(int(e['values']['amount']) for e in parsed['entries']),15);self.assertTrue(any('Negative source' in w for w in parsed['warnings']));before=copy.deepcopy(self.s)
        mappings={n:p.defaults(self.s,n) for n in parsed['categories']};mappings['Salary Payble']['account']='2310';mappings['Advance Salary']['account']='1190'
        q=p.stage(self.s,raw,'matrix.xlsx',parsed,'JP','PC-2026-09',mappings,'Reviewed synthetic report and funding separately',True);self.assertEqual(len(self.s['vouchers']),1);self.assertEqual(q['original_digest'],__import__('hashlib').sha256(raw).hexdigest());self.assertEqual(q['rows'][0]['source_cell'],'C8');self.approve(q);b.approve(self.s,q['id']);bal=core.balances(self.s,'2026-09-30');self.assertEqual([bal[c] for c in ('1000','4540','1100','2310','1190')],[-1500,200,400,0,300]);self.assertEqual(len(self.s['vouchers']),5);self.assertEqual(activity.report(self.s)['metrics']['import_rows_processed'],4)
    def test_mixed_rows_reasoned_reject_and_late_lock_rollback(self):
        q=self.stage([entry(),entry(reference='BAD',treatment='Staff advance',account='')]);self.assertEqual([r['review'] for r in q['rows']],['PENDING','INVALID']);self.approve(q);self.s['locked_through']='2026-09-30';before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):b.approve(self.s,q['id'])
        self.assertEqual(before,self.s);self.s['locked_through']='';b.approve(self.s,q['id']);self.assertEqual(len(self.s['vouchers']),1)
    def test_pending_bulk_blocks_manual_and_changed_file_duplicate(self):
        q=self.stage([entry()])
        with self.assertRaises(ValueError):p.record(self.s,entry(),True)
        raw=standard([entry(amount='20')]);parsed=p.read_source(raw,'changed.csv');q2=p.stage(self.s,raw,'changed.csv',parsed,confirmed=True);self.assertEqual(q2['rows'][0]['review'],'DUPLICATE');b.cancel(self.s,q2['id'],'Not reused');self.approve(q);b.approve(self.s,q['id'])
    def test_templates_exports_vault_and_reversal_register(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for ext in ('xlsx','csv'):p.template(root/('petty.'+ext),self.s)
            w=load_workbook(root/'petty.xlsx');self.assertEqual(w.sheetnames,['Expenses','Accounts','Units','Instructions']);w.close();v=p.record(self.s,entry(),True);pack=p.register_pack(self.s,'2026-09-01','2026-09-30');f.export_xlsx(pack,root/'register.xlsx');f.export_pdf(pack,root/'register.pdf');self.assertIn('PC-TEST-1',' '.join(page.extract_text() for page in PdfReader(root/'register.pdf').pages));vault=Vault(root/'book.json',demo=True);vault.save(self.s);self.assertEqual(vault.load(),self.s);core.reverse(self.s,v['id'],'2026-09-02');self.assertEqual(p.register(self.s,'2026-09-01','2026-09-30')[0]['status'],'Reversed')
    def test_standard_formula_extra_cells_and_invalid_header_errors(self):
        q=self.stage([entry(reference='FORMULA',amount='=SUM(1)'),entry(reference='DATE',date='01/09/2026')]);self.assertTrue(all(r['review']=='INVALID' for r in q['rows']))
        with self.assertRaises(ValueError):p.read_source(b'Bad,Headers\nx,y','bad.csv')
        with self.assertRaises(ValueError):p.stage(self.s,standard([entry()]),'x.csv',p.read_source(standard([entry()]),'x.csv'),confirmed=False)
    def test_cash_flow_funding_transfer_and_expense_reconcile(self):
        cash_flow.save_policy(self.s,dict(cash_flow.defaults(self.s),effective='2026-04-01',reviewed=True,note='Reviewed synthetic cash accounts'))
        p.record(self.s,entry(reference='TOP',treatment='Cash top-up',account='1010',amount='100'),True);p.record(self.s,entry(),True)
        report=cash_flow.analyse(self.s,'2026-09-01','2026-09-30');self.assertEqual(report['closing']-report['opening'],-1000);self.assertEqual(report['totals']['Operating'],-1000)

    def test_salary_settlement_requires_dated_accrual_and_combined_capacity(self):
        with self.assertRaisesRegex(ValueError,'credited salary'):p.record(self.s,entry(treatment='Liability settlement',account='2310'),True)
        core.post(self.s,'2026-08-31','Existing accrual',[dict(account='4520',branch='JP',debit=10000,credit=0),dict(account='2310',branch='JP',debit=0,credit=10000)])
        q=self.stage([entry(reference='SAL-A',treatment='Liability settlement',account='2310',amount='80'),entry(reference='SAL-B',treatment='Liability settlement',account='2310',amount='80')]);self.approve(q);before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'credited salary'):b.approve(self.s,q['id'])
        self.assertEqual(before,self.s)

    def test_backdated_salary_payment_cannot_overdraw_later_recorded_settlement(self):
        core.post(self.s,'2026-08-31','Existing accrual',[dict(account='4520',branch='JP',debit=10000,credit=0),dict(account='2310',branch='JP',debit=0,credit=10000)])
        p.record(self.s,entry(date='2026-09-10',reference='SAL-LATER',treatment='Liability settlement',account='2310',amount='80'),True);before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'credited salary'):p.record(self.s,entry(reference='SAL-EARLIER',treatment='Liability settlement',account='2310',amount='80'),True)
        self.assertEqual(before,self.s)


@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class PettyCashDesktopTests(unittest.TestCase):
    def test_manual_named_preview_bulk_review_and_register(self):
        from unittest.mock import patch
        from riju.app import App
        from test_gui import TaxDepreciationDesktopTests
        from tkinter import ttk
        helper=TaxDepreciationDesktopTests()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=App(Vault(root/'book.json',demo=True))
            try:
                app.show('Petty cash');helper.press(app.content,'Record cash expense / top-up');form=helper.form(app)
                for label,value in [('Actual payment / receipt date','2026-09-01'),('Unique cash voucher reference','GUI-PC-1'),('Operating unit','JP'),('Category','Office'),('Counterpart account (code and name)','4590 Administration'),('Cash amount INR','10'),('Description / payee','Synthetic office cash purchase'),('Accounting review basis','Reviewed synthetic cash voucher')]:helper.fill(form,label,value)
                helper.reviewed(form);helper.press(form,'Preview petty cash journal');app.update();preview=helper.form(app);table=next(w for w in helper.walk(preview) if isinstance(w,ttk.Treeview));self.assertTrue(any('Administration' in table.item(k)['values'] for k in table.get_children()));helper.press(preview,'Approve petty cash journal');app.update();self.assertEqual(len(app.state['vouchers']),1)
                for ext in ('xlsx','csv'):
                    with patch('riju.petty_cash_ui.filedialog.asksaveasfilename',return_value=str(root/('template.'+ext))),patch('riju.petty_cash_ui.messagebox.showinfo'):app.petty_cash_template(ext)
                path=root/'cash.csv';path.write_bytes(standard([entry(reference='GUI-BULK'),entry(reference='BAD',account='1100')]))
                with patch('riju.petty_cash_ui.filedialog.askopenfilename',return_value=str(path)):app.petty_cash_upload()
                form=helper.form(app);helper.reviewed(form);helper.press(form,'Stage and review petty cash rows');app.update();form=helper.form(app)
                with patch('riju.petty_cash_ui.simpledialog.askstring',return_value='Invalid stock treatment rejected'):helper.press(form,'Reject flagged rows')
                helper.reviewed(form)
                with patch('riju.petty_cash_ui.simpledialog.askstring',return_value='Cash source and tax reviewed'):helper.press(form,'Approve all valid rows')
                helper.press(form,'Preview cash journals');app.update();preview=helper.form(app);helper.press(preview,'Approve petty cash journal');app.update();self.assertEqual(len(app.state['vouchers']),2);self.assertEqual(len(app.pc_table.get_children()),2)
            finally:app.destroy()

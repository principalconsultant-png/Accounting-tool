import copy,csv,io,tempfile,unittest
from pathlib import Path
from decimal import Decimal
from openpyxl import load_workbook
from pypdf import PdfReader
from riju import core,business_pulse as b
from riju.business_pulse_exports import export_xlsx,export_pdf

class BusinessPulseTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def post(self,month,amount=10000):
        return core.post(self.s,f'2026-{month:02d}-02','Receipt',[{'account':'1000','branch':'JP','debit':amount,'credit':0},{'account':'4000','branch':'JP','debit':0,'credit':amount}],metadata={'type':'Receipt','reference':'R'+str(month)})
    def rows(self,through='2026-07-31',**kw):return {r['key']:r for r in b.snapshot(self.s,2026,through,**kw)['rows']}
    def test_readonly_missing_and_receipt_proxy_arpp(self):
        self.post(4);before=copy.deepcopy(self.s);r=self.rows();self.assertEqual(before,self.s)
        self.assertEqual(r['visits']['values'][0],1);self.assertEqual(r['arpp']['values'][0],10000)
        self.assertIsNone(r['new_patients']['values'][0]);self.assertIsNone(r['salary']['values'][0]);self.assertIsNone(r['revenue']['values'][1]);self.assertIsNone(r['revenue']['values'][4])
        self.assertEqual(b.policy(self.s)['petty_mode'],'All petty-cash disbursements')
    def test_count_observation_zero_scope_partial_and_revision(self):
        self.post(4)
        v=dict(month='2026-04',branch='ALL',visits='',new_patients=0,books_reviewed=True,basis='Monthly register')
        b.save_month(self.s,v);self.assertEqual(self.rows()['new_patients']['values'][0],0)
        self.assertIsNone(self.rows(branch='JP')['new_patients']['values'][0])
        v.update(visits=2,new_patients=1);b.save_month(self.s,v)
        self.assertEqual(self.rows()['arpp']['values'][0],5000)
        self.assertEqual(self.rows('2026-04-15')['visits']['values'][0],1)
        self.assertIsNone(self.rows('2026-04-15')['new_patients']['values'][0]);self.assertEqual(len(self.s['vouchers']),1)
    def test_count_validation_and_confirmed_empty_month(self):
        v=dict(month='2026-05',branch='ALL',visits=0,new_patients=0,books_reviewed=True,basis='Confirmed no activity')
        b.save_month(self.s,v);r=self.rows();self.assertEqual(r['revenue']['values'][1],0);self.assertIsNone(r['arpp']['values'][1])
        for changes in ({'visits':-1},{'new_patients':1},{'basis':''},{'branch':'unknown'},{'month':'2026-13'}):
            with self.assertRaises(ValueError):b.save_month(self.s,dict(v,**changes))
    def test_split_collection_and_bank_settlement_do_not_duplicate_visits(self):
        core.post(self.s,'2026-04-03','Split receipt',[dict(account=a,branch='JP',debit=d,credit=c) for a,d,c in [('1000',2000,0),('1110',3000,0),('1120',5000,0),('4000',0,10000)]])
        core.post(self.s,'2026-04-04','UPI settlement',[dict(account=a,branch='JP',debit=d,credit=c) for a,d,c in [('1010',3000,0),('1110',0,3000)]])
        r=self.rows();self.assertEqual(r['visits']['values'][0],1);self.assertEqual([r[k]['values'][0] for k in ('cash','upi','card')],[2000,3000,5000])
    def test_expanding_quartile_no_lookahead(self):
        for m,n in ((4,10000),(5,20000),(6,15000),(7,30000)):self.post(m,n)
        r=self.rows()['revenue'];self.assertEqual(r['bands'][:4],[-1,-1,-1,0]);self.assertEqual(b.band([4,3,2,1]),3);self.assertEqual(b.band([1,1,1,1]),-1)
        self.post(8,100000);self.assertEqual(self.rows('2026-08-31')['revenue']['bands'][:4],r['bands'][:4])
    def test_mapping_rejects_controls_and_overlap(self):
        p=b.policy(self.s);p.update(reviewed=True,basis='Reviewed')
        for changes in ({'revenue_accounts':['1000']},{'compliance_accounts':['2000']},{'salary_accounts':['2000']},{'salary_accounts':['4530'],'ot_accounts':['4530']}):
            with self.assertRaises(ValueError):b.save_policy(self.s,dict(p,**changes))
    def test_paid_allocation_never_guesses_mixed_withholding(self):
        lines=[dict(account=a,debit=d,credit=c) for a,d,c in [('salary',100,0),('cash',0,90),('tax',0,10)]]
        self.assertEqual(b._paid_component(lines,{'cash'},{'salary'}),(90,False))
        lines.append(dict(account='other',debit=50,credit=0));self.assertEqual(b._paid_component(lines,{'cash'},{'salary'}),(0,True))
    def test_exports_numeric_scaling_template_and_pdf(self):
        self.post(4,1234500)
        with tempfile.TemporaryDirectory() as d:
            x=Path(d)/'pulse.xlsx';pdf=Path(d)/'pulse.pdf';t=Path(d)/'inputs.xlsx'
            pack=b.snapshot(self.s,2026,'2026-07-31',scale='INR thousands');export_xlsx(pack,x);export_pdf(pack,pdf);b.input_template(t)
            w=load_workbook(x);ws=w['Monthly performance'];row=next(r for r in ws if str(r[0].value).startswith('Revenue earned'))
            self.assertEqual(row[1].value,12.345);self.assertEqual(row[1].data_type,'n');self.assertIn('Sources and definitions',w.sheetnames);w.close()
            self.assertIn('Business Pulse',PdfReader(pdf).pages[0].extract_text());w=load_workbook(t);self.assertEqual(tuple(c.value for c in w.active[1]),b.INPUT_HEADERS);w.close()
            self.assertEqual(b.numeric(12345,'ratio','INR lakh'),Decimal('123.45'))
    def test_petty_all_treatments_excludes_funding_and_reverses(self):
        from riju import foundation,petty_cash
        from test_petty_cash import entry
        foundation.save_account(self.s,'1190','Staff advances','Asset','Other assets');foundation.save_account(self.s,'2310','Payroll payable','Liability','Other liabilities')
        core.post(self.s,'2026-04-01','Payroll accrual',[dict(account='4520',branch='JP',debit=1000,credit=0),dict(account='2310',branch='JP',debit=0,credit=1000)])
        for i,(t,a) in enumerate([('Expense','4590'),('Stock purchase','1100'),('Staff advance','1190'),('Liability settlement','2310'),('Cash top-up','1010')]):
            petty_cash.record(self.s,entry(date='2026-04-02',reference='PC'+str(i),treatment=t,account=a),True)
        self.assertEqual(self.rows()['petty']['values'][0],4000)
        core.reverse(self.s,self.s['vouchers'][1]['id'],'2026-05-02');self.assertEqual(self.rows()['petty']['values'][1],-1000)
    def test_ap_partial_payment_counts_once_and_later_reversal(self):
        from test_ap import ApTests
        a=ApTests();a.setUp();inv=a.enter();payment=a.pay(inv,items=[dict(invoice=inv['id'],amount='400')]);a.pay(inv,reference='P2',items=[dict(invoice=inv['id'],amount='600')]);self.s=a.s
        r=self.rows();self.assertEqual(r['invoices']['values'][1],1);self.assertEqual(r['vendor']['values'][1],100000)
        core.reverse(self.s,payment['voucher'],'2026-06-02');r=self.rows();self.assertEqual(r['vendor']['values'][2],-40000);self.assertEqual(r['invoices']['values'][2],0)
    def test_import_zero_duplicate_invalid_and_no_journal(self):
        out=io.StringIO();w=csv.writer(out);w.writerow(b.INPUT_HEADERS);w.writerow(['2026-04','ALL','',0,'Yes','Source checked']);w.writerow(['2026-04','ALL',1,0,'Yes','Duplicate']);w.writerow(['2026-05','ALL',-1,0,'Yes','Invalid'])
        plan=b.preview_inputs(self.s,out.getvalue().encode(),'counts.csv');self.assertEqual([r['status'] for r in plan['rows']],['NEW','INVALID','INVALID']);b.save_inputs(self.s,plan,[0]);self.assertEqual(self.rows()['new_patients']['values'][0],0);self.assertFalse(self.s['vouchers'])
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):b.save_inputs(self.s,plan,[0,1])
        self.assertEqual(before,self.s)

@unittest.skipUnless(__import__('os').environ.get('DISPLAY') or __import__('os').environ.get('RIJU_GUI_TEST'),'Display required')
class BusinessPulseDesktopTests(unittest.TestCase):
    def test_report_opens_large_reuses_window_and_exports(self):
        from riju.app import App
        from riju.storage import Vault
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            app=App(Vault(Path(d)/'demo.json',demo=True))
            try:
                app.show('Financial reports');app.business_pulse();app.update();window=app.pulse_window
                self.assertGreater(window.winfo_width()*window.winfo_height(),app.winfo_screenwidth()*app.winfo_screenheight()*.75)
                app.business_pulse();self.assertIs(app.pulse_window,window);self.assertEqual(len(app.pulse_snapshot['rows']),13)
                for ext in ('xlsx','pdf'):
                    target=Path(d)/('report.'+ext)
                    with patch('riju.business_pulse_ui.filedialog.asksaveasfilename',return_value=str(target)),patch('riju.business_pulse_ui.messagebox.showinfo'):app.pulse_export(ext)
                    self.assertGreater(target.stat().st_size,1000)
                app.pulse_month();app.update();app.pulse_mapping();app.update();self.assertFalse(app.state['vouchers'])
            finally:app.destroy()

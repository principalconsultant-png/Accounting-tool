import copy,tempfile,unittest,os,sqlite3
from pathlib import Path
from riju import core,foundation,daily_consolidation as d,receipt_import as ri,history
from test_bank_reconciliation import pair
from test_receipt_import import row,raw

class DailyDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state();foundation.save_account(self.s,'2310','Salary payable','Liability','Other liabilities');foundation.save_account(self.s,'1190','Staff advance','Asset','Other assets')
        core.post(self.s,'2026-04-01','Opening cash and bank',pair('1000','3000',10000)+pair('1010','3000',20000)+pair('1030','3000',5000)+pair('1040','3000',5000),opening=True)
    def post(self,day,dr,cr,n,**kw):return core.post(self.s,day,'Synthetic activity',pair(dr,cr,n),**kw)
    def rebuild(self,end='2026-04-04'):
        d.refresh(self.s,'2026-04-01',end);return d.pack(self.s,'2026-04-01',end)['rows']
    def test_exact_daily_columns_split_receipt_settlement_and_cash_balance(self):
        q=ri.stage(self.s,raw([row(receipt_date='2026-04-02',receipt_no='D1',consultation='100',treatment='',cash='20',upi='30',card='50',total='100')]),'daily.csv');ri.review(self.s,q['id'],[0],True,'Checked',True);ri.post(self.s,q['id'])
        self.post('2026-04-03','1010','1110',3000);self.post('2026-04-03','1010','1120',5000)
        rows=self.rebuild();self.assertEqual(rows[1],['2026-04-02',10000,1,10000,0,0,32000]);self.assertEqual(rows[2],['2026-04-03',0,0,0,0,0,40000])
        self.assertFalse(d.pack(self.s,'2026-04-01','2026-04-04',section='Source gaps')['rows'])
    def test_salary_and_petty_opex_once_stock_advance_finance_left_out(self):
        self.post('2026-04-02','4520','2310',2000);self.post('2026-04-03','2310','1010',2000)
        for dr,cr,n in [('4590','1000',500),('1190','1000',100),('1100','2000',1000),('4570','1050',100),('4580','1010',200),('4560','1010',10),('4600','1100',200)]:self.post('2026-04-03',dr,cr,n)
        rows=self.rebuild();self.assertEqual(rows[1][4],2000);self.assertEqual(rows[2][4],810)
        excluded=d.pack(self.s,'2026-04-01','2026-04-04',section='What is left out')['rows'];self.assertTrue(any(r[3]=='4580' and 'Finance costs' in r[-1] for r in excluded));self.assertTrue(any(r[3]=='1100' and 'Inventory' in r[-1] for r in excluded))
    def test_capex_additions_reversal_internal_capitalisation_and_disposal(self):
        purchase=self.post('2026-04-02','1020','2000',10000);self.post('2026-04-03','1030','1020',10000);core.reverse(self.s,purchase['id'],'2026-04-04')
        rows=self.rebuild();self.assertEqual([r[5] for r in rows],[0,10000,0,-10000])
    def test_capex_disposal_is_not_negative_addition_and_expense_capitalisation(self):
        self.post('2026-04-02','1010','1030',5000);self.post('2026-04-03','1020','4590',1000)
        core.post(self.s,'2026-04-04','Asset trade-in',pair('1030','1040',1000)+pair('1010','1040',4000))
        rows=self.rebuild();self.assertEqual(rows[1][5],0);self.assertEqual(rows[2][4:6],[-1000,1000]);self.assertEqual(rows[3][5],1000)
    def test_funding_transfers_are_not_revenue_collections_or_patients(self):
        self.post('2026-04-02','1010','2400',5000);self.post('2026-04-02','1000','1010',1000)
        rows=self.rebuild();self.assertEqual(rows[1][1:6],[0,0,0,0,0]);self.assertEqual(rows[1][-1],35000)
    def test_receipt_cancellation_no_fake_patient_and_signed_financial_reversal(self):
        v=self.post('2026-04-02','1000','4000',10000,metadata={'type':'Receipt','reference':'R1'});core.reverse(self.s,v['id'],'2026-04-03');rows=self.rebuild();self.assertEqual(rows[1][1:4],[10000,0,10000]);self.assertEqual(rows[2][1:4],[-10000,0,-10000])
    def test_unit_and_entity_count_multiunit_receipt_once(self):
        core.post(self.s,'2026-04-02','Two-unit receipt',pair('1000','4000',1000,'JP')+pair('1000','4000',2000,'KM'),metadata={'type':'Receipt','reference':'ONE'})
        self.rebuild();self.assertEqual(d.pack(self.s,'2026-04-02','2026-04-02')['rows'][0][2],1);self.assertEqual(d.pack(self.s,'2026-04-02','2026-04-02','JP')['rows'][0][1:4],[1000,1,1000])
    def test_refresh_idempotence_checkpoint_staleness_and_vault_roundtrip(self):
        from riju.storage import Vault
        before=len(self.s['vouchers']);self.rebuild();self.rebuild();self.assertEqual(len(self.s['vouchers']),before)
        history.checkpoint(self.s);db,meta,stale=d.saved(self.s);self.assertFalse(stale);db.close()
        with tempfile.TemporaryDirectory() as root:
            vault=Vault(Path(root)/'book.json',demo=True);vault.save(self.s);loaded=vault.load();self.assertEqual(d.pack(loaded,'2026-04-01','2026-04-04')['rows'],d.pack(self.s,'2026-04-01','2026-04-04')['rows'])
        self.post('2026-04-02','4590','1000',100);self.assertTrue(d.pack(self.s,'2026-04-01','2026-04-04')['stale']);self.rebuild();self.assertFalse(d.pack(self.s,'2026-04-01','2026-04-04')['stale'])
    def test_unposted_receipts_bank_sources_and_pending_queue_reported(self):
        from riju import reconciliation as bank
        ri.stage(self.s,raw([row(receipt_date='2026-04-02',receipt_no='PENDING')]),'pending.csv');bank.import_statement(self.s,b'date,narration,reference,debit,credit,balance\n2026-04-02,Unknown deposit,B1,0,10,10\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','0','10')
        rows=self.rebuild();self.assertEqual(rows[1][1:6],[0,0,0,0,0]);gaps=d.pack(self.s,'2026-04-01','2026-04-04',section='Source gaps')['rows'];self.assertTrue(any('Unmatched bank' in r[0] for r in gaps));self.assertTrue(any(r[0]=='pending.csv' for r in gaps))
    def test_other_payment_receipt_counts_and_tax_refund_collections(self):
        self.post('2026-04-02','1140','4000',10000,metadata={'type':'Receipt','reference':'OTHER'})
        rows=self.rebuild();self.assertEqual(rows[1][1:4],[10000,1,10000]);self.assertEqual(rows[1][-1],30000)
        from test_gst_notes import GstNoteTests
        case=GstNoteTests();case.setUp();case.note();d.refresh(case.s,'2026-04-01','2026-05-02');rows=d.pack(case.s,'2026-04-01','2026-05-02')['rows'];self.assertEqual(rows[1][1:4],[10000,1,11800]);self.assertEqual(rows[30][1:4],[-5000,0,-5900])

    def test_snapshot_readonly_integrity_and_date_guards(self):
        self.rebuild();before=copy.deepcopy(self.s);p=d.pack(self.s,'2026-04-01','2026-04-04');self.assertEqual(before,self.s);self.assertEqual(len(p['columns']),7)
        for args in [('2026-03-31','2026-04-04'),('2026-04-03','2026-04-02')]:
            with self.assertRaises(ValueError):d.pack(self.s,*args)
        self.s['settings'][d.STORE]['sha256']='bad'
        with self.assertRaises(ValueError):d.saved(self.s)

@unittest.skipUnless(os.environ.get('DISPLAY') or os.environ.get('RIJU_GUI_TEST'),'Display required')
class DailyDatabaseDesktopTests(unittest.TestCase):
    def test_build_view_export_and_stale_guard(self):
        from riju.app import App
        from riju.storage import Vault
        from unittest.mock import patch
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as root:
            app=App(Vault(Path(root)/'book.json',demo=True))
            try:
                app.year.set('2026');core.post(app.state,'2026-04-02','Patient receipt',pair('1000','4000',10000),metadata={'type':'Receipt','reference':'R1'});app.show('Financial reports');app.daily_register();app.daily_start.set('2026-04-01');app.daily_end.set('2026-04-03');app.daily_build();app.update();self.assertEqual(len(app.daily_table.get_children()),3);self.assertEqual(app.daily_pack['rows'][1][1:4],[10000,1,10000])
                for kind in ('xlsx','csv','pdf','sqlite'):
                    path=Path(root)/('daily.'+kind)
                    with patch('riju.daily_consolidation_ui.filedialog.asksaveasfilename',return_value=str(path)),patch('riju.daily_consolidation_ui.messagebox.showinfo'):app.daily_export(kind)
                    self.assertGreater(path.stat().st_size,100)
                wb=load_workbook(Path(root)/'daily.xlsx');self.assertIn('What is left out',wb.sheetnames);self.assertTrue(any(r[2].value==1 and r[1].value==100 for r in wb['Daily table'] if len(r)>2));wb.close()
                db=sqlite3.connect(Path(root)/'daily.sqlite');self.assertEqual(db.execute("SELECT sales_units FROM daily_metrics WHERE date='2026-04-02' AND unit='ALL'").fetchone()[0],1);db.close()
                app.daily_section.set('What is left out');app.update();self.assertIn('Reason',app.daily_table['columns']);core.post(app.state,'2026-04-03','New expense',pair('4590','1000',100))
                with self.assertRaises(ValueError):app.daily_export('xlsx')
                self.assertIn('STALE',app.daily_status.cget('text'))
            finally:app.destroy()

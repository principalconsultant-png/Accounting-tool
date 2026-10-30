import copy
import io
from pathlib import Path
import tempfile
import unittest
from datetime import datetime
from openpyxl import Workbook
from pypdf import PdfReader
from riju import core,foundation,reconciliation as r,activity,brs_exports


def pair(dr,cr,n,branch='JP'):
    return [dict(account=dr,branch=branch,debit=n,credit=0),dict(account=cr,branch=branch,debit=0,credit=n)]


class BankTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state();core.post(self.s,'2026-04-01','Initial bank',pair('1010','3000',100000),opening=True)
    def load(self,body,opening='1000',closing='1300',start='2026-04-01',end='2026-04-30',filename='bank.csv',**kwargs):
        raw=('date,narration,reference,debit,credit,balance\n'+body).encode()
        return r.import_statement(self.s,raw,filename,'1010','ALL',start,end,opening,closing,**kwargs)
    def test_statement_matching_proof_and_period_lock(self):
        v=core.post(self.s,'2026-04-02','Consultation',pair('1010','4000',30000),metadata={'reference':'UTR-1'})
        s=self.load('2026-04-02,Patient deposit,UTR-1,0,300,1300\n')
        b=self.s['bank_lines'][0];suggest=r.suggestions(self.s,b['id']);self.assertEqual(suggest[0]['score'],100)
        m=r.match_existing(self.s,[b['id']],[v['id']+':0']);self.assertTrue(r.brs(self.s,s['id'])['ready'])
        r.finalize(self.s,s['id'])
        with self.assertRaises(ValueError):core.post(self.s,'2026-04-03','Backdate',pair('1010','4000',1))
        with self.assertRaises(ValueError):r.undo_match(self.s,m['id'],'Change','2026-04-04')
        r.reopen(self.s,s['id'],'Correct matching')
        r.undo_match(self.s,m['id'],'Correction','2026-04-04')
        self.assertEqual(r.outstanding(self.s,'1010')[0][0]['remaining'],30000)
        self.assertEqual(activity.report(self.s)['metrics']['journal_vouchers_posted'],2)
        core.verify_audit(self.s)
    def test_correct_brs_signs_and_reviewed_adjustments(self):
        core.post(self.s,'2026-04-02','Deposit in transit',pair('1010','4000',20000))
        core.post(self.s,'2026-04-03','Unpresented payment',pair('4530','1010',10000))
        s=self.load('2026-04-04,Direct credit,R1,0,50,1050\n2026-04-05,Bank charge,R2,20,0,1030\n',closing='1030')
        report=r.brs(self.s,s['id']);self.assertEqual(report['variance'],0);self.assertEqual(report['adjusted_bank_balance'],110000)
        self.assertFalse(report['ready'])
        r.adjust(self.s,self.s['bank_lines'][0]['id'],'JP','4000','Reviewed unrecorded receipt')
        r.adjust(self.s,self.s['bank_lines'][1]['id'],'JP','4560','Reviewed bank fee')
        report=r.brs(self.s,s['id']);self.assertTrue(report['ready']);self.assertEqual(report['book_balance'],113000)
        m=activity.report(self.s)['metrics'];self.assertEqual(m['business_transactions_posted'],4);self.assertEqual(m['bank_rows_matched'],2)
    def test_partial_matching_across_statement_cutoffs(self):
        v=core.post(self.s,'2026-04-02','Customer receipt',pair('1010','4000',20000))
        april=self.load('2026-04-03,Part received,P1,0,150,1150\n',closing='1150')
        bank=self.s['bank_lines'][0]
        r.match_existing(self.s,[bank['id']],[v['id']+':0'],15000)
        self.assertEqual(r.brs(self.s,april['id'])['deposits_in_transit'],5000);r.finalize(self.s,april['id'])
        may=self.load('2026-05-02,Remaining,P2,0,50,1200\n',opening='1150',closing='1200',start='2026-05-01',end='2026-05-31',filename='may.csv')
        r.match_existing(self.s,[self.s['bank_lines'][1]['id']],[v['id']+':0'])
        self.assertEqual(r.brs(self.s,april['id'])['deposits_in_transit'],5000)
        self.assertTrue(r.brs(self.s,may['id'])['ready'])
    def test_undo_and_rematch_preserve_earlier_asof_proof(self):
        v=core.post(self.s,'2026-04-02','Receipt',pair('1010','4000',30000))
        s=self.load('2026-04-02,Receipt,R1,0,300,1300\n');bank=self.s['bank_lines'][0]
        m=r.match_existing(self.s,[bank['id']],[v['id']+':0']);r.undo_match(self.s,m['id'],'Re-review','2026-05-02')
        r.match_existing(self.s,[bank['id']],[v['id']+':0'])
        self.assertEqual(r.brs(self.s,s['id'])['unrecorded_bank_credits'],0);self.assertTrue(r.brs(self.s,s['id'])['ready'])
    def test_multi_day_mixed_payment_channels_do_not_reuse_receipts(self):
        v=core.post(self.s,'2026-04-02','Mixed service receipt',[dict(account='1110',branch='JP',debit=10000,credit=0),dict(account='1120',branch='JP',debit=20000,credit=0),dict(account='4000',branch='JP',debit=0,credit=30000)])
        s=self.load('2026-04-03,UPI SETTLEMENT -AII125,U1,0,99,1099\n2026-04-03,TERMINAL 1 CARDS SETTL,C1,0,198,1297\n',closing='1297')
        rows=self.s['bank_lines'];upi=r.clearing_items(self.s,'1110');card=r.clearing_items(self.s,'1120')
        r.settle(self.s,rows[0]['id'],'1110',[upi[0]['key']],100)
        self.assertEqual(r.clearing_items(self.s,'1120')[0]['remaining'],20000)
        r.settle(self.s,rows[1]['id'],'1120',[card[0]['key']],200)
        self.assertTrue(r.brs(self.s,s['id'])['ready'])
        with self.assertRaises(ValueError):core.reverse(self.s,v['id'],'2026-04-04')
        self.assertEqual(activity.report(self.s)['metrics']['settlement_journals'],2)
    def test_shared_multi_branch_settlement_fee_tax_rounding(self):
        core.post(self.s,'2026-04-02','JP UPI',pair('1110','4000',10000,'JP'))
        core.post(self.s,'2026-04-02','KM UPI',pair('1110','4000',10000,'KM'))
        s=self.load('2026-04-03,UPI settlement,U1,0,199.97,1199.97\n',closing='1199.97')
        items=r.clearing_items(self.s,'1110');m=r.settle(self.s,self.s['bank_lines'][0]['id'],'1110',[b['key'] for b in items],3,2,'Intra-state')
        v=next(v for v in self.s['vouchers'] if v['id']==m['posting'])
        for branch in ('JP','KM'):self.assertEqual(sum(l['debit']-l['credit'] for l in v['lines'] if l['branch']==branch),0)
        b=core.balances(self.s,'2026-04-30');self.assertEqual(b['1200'],1);self.assertEqual(b['1210'],1);self.assertEqual(b['1110'],0)
        self.assertTrue(r.brs(self.s,s['id'])['ready'])
    def test_cash_deposit_and_cash_balance_guard(self):
        v=core.post(self.s,'2026-04-02','Cash receipt',pair('1000','4000',10000))
        s=self.load('2026-04-05,CASH DEPOSIT BY SELF,CASH1,0,100,1100\n',closing='1100')
        r.settle(self.s,self.s['bank_lines'][0]['id'],'1000',[v['id']+':0'])
        self.assertEqual(core.balances(self.s,'2026-04-30')['1000'],0);self.assertTrue(r.brs(self.s,s['id'])['ready'])
    def test_partial_gross_settlement_and_undo_owned_journal(self):
        v=core.post(self.s,'2026-04-02','UPI',pair('1110','4000',20000))
        self.load('2026-04-03,UPI net,U1,0,99,1099\n',closing='1099')
        m=r.settle(self.s,self.s['bank_lines'][0]['id'],'1110',[v['id']+':0'],100,partial_gross_minor=10000)
        self.assertEqual(r.clearing_items(self.s,'1110')[0]['remaining'],10000)
        r.undo_match(self.s,m['id'],'Wrong batch','2026-04-04')
        self.assertEqual(core.balances(self.s,'2026-04-30')['1110'],20000)
        self.assertEqual(r.clearing_items(self.s,'1110')[0]['remaining'],20000)
        _,books=r.outstanding(self.s,'1010');self.assertFalse(books)
        core.verify_audit(self.s)
    def test_bank_exception_and_later_book_cutoff(self):
        s=self.load('2026-04-30,Direct credit,R1,0,300,1300\n')
        v=core.post(self.s,'2026-05-01','Recorded next day',pair('1010','4000',30000))
        r.match_existing(self.s,[self.s['bank_lines'][0]['id']],[v['id']+':0'])
        report=r.brs(self.s,s['id']);self.assertTrue(report['ready']);self.assertIn('Timing:',report['banks'][0]['exception'])
    def test_classified_dispute_ready_but_unknown_opening_not_ready(self):
        s=self.load('2026-04-02,Disputed debit,E1,300,0,700\n',closing='700')
        self.assertEqual(r.brs(self.s,s['id'])['variance'],0)
        r.classify_exception(self.s,self.s['bank_lines'][0]['id'],'Bank duplicate debit under dispute')
        self.assertTrue(r.brs(self.s,s['id'])['ready'])
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):r.match_existing(self.s,[self.s['bank_lines'][0]['id']],[])
        self.assertEqual(self.s,before)
        r.remove_exception(self.s,self.s['bank_lines'][0]['id'],'Bank corrected')
        self.assertFalse(r.brs(self.s,s['id'])['ready'])
    def test_legacy_deposit_match_reused_without_reposting(self):
        sale=core.post(self.s,'2026-04-02','UPI',pair('1110','4000',10000))
        activity.import_bank_rows(self.s,[dict(date='2026-04-03',narration='UPI settlement',amount=9800,reference='U1')],'JP','legacy.csv')
        bank=self.s['bank_lines'][0]
        v=core.post(self.s,'2026-04-03','Settlement U1',[dict(account='1010',branch='JP',debit=9800,credit=0),dict(account='4560',branch='JP',debit=200,credit=0),dict(account='1110',branch='JP',debit=0,credit=10000)])
        bank['status']='MATCHED';self.s['matches'].append(dict(account='1110',gross=10000,fee=200,vouchers=[sale['id']],bank_id=bank['id'],posting=v['id']))
        s=self.load('2026-04-03,UPI settlement,U1,0,98,\n',closing='1098')
        self.assertEqual(len(self.s['bank_lines']),1);self.assertEqual(len(self.s['vouchers']),3);self.assertTrue(r.brs(self.s,s['id'])['ready'])
    def test_import_failure_duplicate_and_ambiguous_overlap_are_atomic(self):
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.load('2026-04-02,Receipt,R1,0,300,1200\n')
        self.assertEqual(self.s,before)
        self.load('2026-04-02,Receipt,R1,0,300,1300\n')
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):self.load('2026-04-02,Receipt,R1,0,300,1300\n')
        self.assertEqual(self.s,before)
        # Same physical row reused from a differently named/encoded overlapping file.
        s=self.load('2026-04-02,Receipt,R1,0,300,1300\n\n',filename='overlap.csv')
        self.assertEqual(len(self.s['bank_lines']),1);self.assertEqual(len(s['row_ids']),1)
    def test_empty_period_and_missing_header_balances(self):
        s=self.load('',closing='1000');self.assertTrue(r.brs(self.s,s['id'])['ready'])
        other=core.empty_state()
        s2=r.import_statement(other,b'date,narration,amount,reference\n2026-04-02,Receipt,100,R1\n','other.csv','1010','ALL','2026-04-01','2026-04-30')
        with self.assertRaises(ValueError):r.finalize(other,s2['id'])
        with self.assertRaises(ValueError):r.update_balances(other,s2['id'],'','100')
    def test_csv_xlsx_mapping_header_and_newest_order(self):
        raw=b'Bank statement\ndate,narration,reference,debit,credit,balance\n2026-04-03,Fee,F1,50,0,1250\n2026-04-02,Deposit,R1,0,300,1300\n'
        s=r.import_statement(self.s,raw,'newest.csv','1010','ALL','2026-04-01','2026-04-30','1000','1250',header_row=2,order='Newest first')
        self.assertEqual(len(s['row_ids']),2)
        w=Workbook();ws=w.active;ws.append(['Bank intro']);ws.append(['Txn Date','Details','Debit Amt','Credit Amt','Balance']);ws.append([datetime(2026,5,2),'Fee',50,0,1200]);out=io.BytesIO();w.save(out);w.close()
        s2=r.import_statement(self.s,out.getvalue(),'bank.xlsx','1010','ALL','2026-05-01','2026-05-31','1250','1200',header_row=2,mapping={'date':'Txn Date','narration':'Details','debit':'Debit Amt','credit':'Credit Amt'})
        self.assertEqual(len(s2['row_ids']),1)
    def test_ofx_identity_balance_and_duplicate_fitid(self):
        def ofx(account='1234',second=''):
            return ('OFXHEADER:100\n<OFX><CURDEF>INR<ACCTID>'+account+'<BANKTRANLIST><STMTTRN><DTPOSTED>20260402<TRNAMT>300<FITID>FIT-1<NAME>Receipt</STMTTRN>'+second+'</BANKTRANLIST><LEDGERBAL><BALAMT>1300<DTASOF>20260430</LEDGERBAL></OFX>').encode()
        s=r.import_statement(self.s,ofx(),'bank.ofx','1010','ALL','2026-04-01','2026-04-30','1000','')
        self.assertEqual(s['closing'],130000);self.assertEqual(self.s['bank_lines'][0]['fitid'],'FIT-1')
        with self.assertRaises(ValueError):r.import_statement(self.s,ofx('9999'),'wrong.ofx','1010','ALL','2026-04-01','2026-04-30','1000','')
    def test_calendar_and_nbd_tolerance(self):
        core.post(self.s,'2026-04-10','Friday UPI',pair('1110','4000',10000))
        self.load('2026-04-14,UPI settlement,U1,0,98,1098\n',closing='1098')
        r.set_policy(self.s,0,False,'date,name,source\n2026-04-13,Test holiday,Verified bank list\n')
        self.assertEqual(r.next_business_day(self.s,'2026-04-10'),'2026-04-14')
        self.assertTrue(r.settlement_suggestions(self.s,self.s['bank_lines'][0]['id'],'1110'))
        r.set_policy(self.s,0,False,working_days='2026-04-11')
        self.assertEqual(r.next_business_day(self.s,'2026-04-10'),'2026-04-11')
        self.assertFalse(r.settlement_suggestions(self.s,self.s['bank_lines'][0]['id'],'1110'))
    def test_handover_exports_preserve_books_and_include_proof(self):
        s=self.load('',closing='1000');report=r.brs(self.s,s['id']);before=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);brs_exports.export_pdf(report,p/'brs.pdf');brs_exports.export_csv(report,p/'brs.csv');brs_exports.export_html(report,p/'brs.html')
            self.assertIn('Unexplained difference',PdfReader(p/'brs.pdf').pages[0].extract_text())
            self.assertIn('window.print()', (p/'brs.html').read_text());self.assertIn('1000.00',(p/'brs.csv').read_text(encoding='utf-8-sig'))
        self.assertEqual(self.s,before)

    def test_void_unused_import_retains_history_and_allows_reimport(self):
        s=self.load('2026-04-02,Receipt,R1,0,300,1300\n')
        r.void_statement(self.s,s['id'],'Wrong file selected')
        self.assertEqual(r.bank_rows(self.s,'1010'),[])
        self.assertEqual(activity.report(self.s)['metrics']['bank_rows_imported'],0)
        self.assertFalse(r.brs(self.s,s['id'])['ready'])
        new=self.load('2026-04-02,Receipt,R1,0,300,1300\n')
        self.assertNotEqual(new['id'],s['id']);self.assertEqual(len(r.bank_rows(self.s,'1010')),1)
        self.assertEqual(len(self.s['bank_lines']),2);core.verify_audit(self.s)

    def test_void_shared_overlap_retains_rows_and_rejects_active_matches(self):
        first=self.load('2026-04-02,Receipt,R1,0,300,1300\n')
        second=self.load('2026-04-02,Receipt,R1,0,300,1300\n\n',filename='overlap.csv')
        r.void_statement(self.s,first['id'],'Duplicate period import')
        self.assertEqual(len(r.bank_rows(self.s,'1010')),1)
        v=core.post(self.s,'2026-04-02','Receipt',pair('1010','4000',30000))
        r.match_existing(self.s,second['row_ids'],[v['id']+':0'])
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):r.void_statement(self.s,second['id'],'Mistake')
        self.assertEqual(before,self.s)

    def test_format_three_upgrade_preserves_fx_and_existing_books(self):
        from riju import fx
        fx.save_rate(self.s,'2026-04-02','USD','83.25','Test rate')
        before=copy.deepcopy(self.s)
        self.s['schema_revision']=3;self.s['version']=3
        for key in ('bank_statements','bank_exceptions'):self.s.pop(key)
        self.s['settings'].pop('bank_reconciliation')
        foundation.migrate(self.s)
        self.assertEqual(self.s['version'],10)
        for key in ('vouchers','accounts','fx_rates','foreign_accounts','fx_ledgers'):
            self.assertEqual(self.s[key],before[key])
        core.verify_audit(self.s)

    def test_overdraft_statement_and_other_bank_isolation(self):
        foundation.save_account(self.s,'1011','Other bank','Asset','Cash and bank')
        core.post(self.s,'2026-04-01','Opening overdraft',pair('3000','1011',10000,'KM'),opening=True)
        v=core.post(self.s,'2026-04-02','Overdraft charge',pair('4560','1011',1000))
        raw=b'date,narration,reference,amount\n2026-04-02,Charge,F1,-10\n'
        s=r.import_statement(self.s,raw,'overdraft.csv','1011','ALL','2026-04-01','2026-04-30','-100','-110')
        self.assertEqual(r.bank_rows(self.s,'1010'),[])
        r.match_existing(self.s,s['row_ids'],[v['id']+':1'])
        self.assertTrue(r.brs(self.s,s['id'])['ready'])
        r.finalize(self.s,s['id'])
        core.post(self.s,'2026-04-03','Other bank remains editable',pair('1010','4000',100))

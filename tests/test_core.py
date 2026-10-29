import copy
import os
from pathlib import Path
import tempfile
import unittest
from riju import core
from riju.storage import Vault, protect

class AccountingTests(unittest.TestCase):
    def setUp(self): self.s=core.empty_state()
    def lines(self): return [dict(account='4530',branch='JP',debit=10000,credit=0),dict(account='1010',branch='JP',debit=0,credit=10000)]
    def test_money(self):
        self.assertEqual(core.money('₹1,234.565'),123457)
        for value in ('NaN','Infinity','abc'):
            with self.assertRaises(ValueError):core.money(value)
    def test_fy(self):
        self.assertEqual(core.financial_year('2026-03-31'),2025)
        self.assertEqual(core.financial_year('2026-04-01'),2026)
    def test_post_partition_and_history(self):
        core.post(self.s,'2026-04-01','Rent',self.lines())
        self.assertEqual(core.balances(self.s,'2026-04-30','JP')['4530'],10000)
        self.assertEqual(core.balances(self.s,'2026-04-30','KM')['4530'],0)
        self.assertEqual(sum(core.balances(self.s,'2026-04-30').values()),0)
        core.verify_audit(self.s)
    def test_invalid_lines(self):
        for key,value in [('credit',1),('account','9999'),('branch','KM'),('debit',9999)]:
            lines=self.lines(); lines[0][key]=value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):core.post(self.s,'2026-04-01','Rent',lines)
        self.assertFalse(self.s['vouchers'])
    def test_lock(self):
        self.s['locked_through']='2026-04-30'
        with self.assertRaises(ValueError):core.post(self.s,'2026-04-01','Rent',self.lines())
        core.post(self.s,'2026-05-01','Rent',self.lines())
    def test_reversal(self):
        v=core.post(self.s,'2026-04-01','Rent',self.lines()); before=copy.deepcopy(v)
        core.reverse(self.s,v['id'],'2026-04-02')
        self.assertEqual(v,before)
        self.assertTrue(all(n==0 for n in core.balances(self.s,'2026-04-30').values()))
        with self.assertRaises(ValueError):core.reverse(self.s,v['id'],'2026-04-03')
    def test_opening(self):
        core.post(self.s,'2026-04-01','Opening',[dict(account='1010',branch='JP',debit=10000,credit=0),dict(account='3000',branch='JP',debit=0,credit=10000)],opening=True)
        self.assertEqual(core.balances(self.s,'2026-04-30','JP','2026-04-01')['4530'],0)
    def test_prior_year(self):
        core.post(self.s,'2024-06-01','Earlier rent',self.lines())
        self.assertEqual(core.balances(self.s,'2026-04-30')['4530'],10000)
        self.assertEqual(core.balances(self.s,'2026-04-30','ALL','2026-04-01')['4530'],0)
    def test_tampering(self):
        core.post(self.s,'2026-04-01','Rent',self.lines())
        self.s['audit'][0]['payload']['narration']='tampered'
        with self.assertRaises(ValueError):core.verify_audit(self.s)
    def test_lines_copied(self):
        lines=self.lines(); core.post(self.s,'2026-04-01','Rent',lines); lines[0]['debit']=999
        self.assertEqual(self.s['vouchers'][0]['lines'][0]['debit'],10000)
    def test_parser(self):
        lines=core.parse_transaction('Paid ₹5,000 rent by bank','JP','2026-04-01',self.s)
        self.assertEqual(lines[0]['account'],'4530');self.assertEqual(lines[1]['account'],'1010')
        core.post(self.s,'2026-04-01','Rent',lines)
    def test_parser_clearing(self):
        lines=core.parse_transaction('Received Rs 12000 OPD consultation sales by UPI','KM','2026-04-01',self.s)
        self.assertEqual(lines[0]['account'],'1110');self.assertEqual(lines[1]['account'],'4000')
    def test_parser_ambiguity(self):
        for text in ['Paid ₹5,000 rent with GST by bank','Paid ₹5,000 things by bank','Paid ₹5,000 rent','Paid ₹5,000 rent and salary by bank','Paid ₹5,000 rent by bank and cash','Paid rent by bank','Paid ₹5,000 rent by bank on 2026-04-02']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):core.parse_transaction(text,'JP','2026-04-01',self.s)
    def test_holidays(self):
        self.assertEqual(core.next_business_day('2026-04-10',['2026-04-13']).isoformat(),'2026-04-14')
        self.assertEqual(core.next_business_day('2026-04-03',[]).isoformat(),'2026-04-04')
    def test_settlement(self):
        for day in ('2026-04-09','2026-04-10'):
            core.post(self.s,day,'Sales',core.parse_transaction('Received ₹1000 OPD sales by UPI','JP',day,self.s))
        bank={'date':'2026-04-13','amount':198000}
        match=next(s for s in core.settlement_matches(self.s,bank,'JP') if len(s['vouchers'])==2)
        self.assertEqual(match['fee'],2000)
        self.assertEqual(core.settlement_matches(self.s,bank,'KM'),[])
        self.s['matches'].append(match)
        self.assertEqual(core.settlement_matches(self.s,bank,'JP'),[])
    def test_csv(self):
        rows=core.read_csv('date,narration,branch,debit_account,credit_account,amount\n2026-04-01,Rent,JP,4530,1010,5000\n','journals')
        self.assertEqual(rows[0]['amount'],500000)
        with self.assertRaises(ValueError):core.read_csv('hello,world\na,b','journals')
    def test_asset_estimate(self):
        self.assertEqual(core.depreciation(10000000,500000,60,15),(1900000,1500000))
        with self.assertRaises(ValueError):core.depreciation(100,200,60,15)

class StorageTests(unittest.TestCase):
    def test_roundtrip_and_concurrent_change(self):
        with tempfile.TemporaryDirectory() as d:
            v=Vault(Path(d)/'demo.json',demo=True);s=v.load();v.save(s)
            self.assertEqual(v.load(),s)
            other=Vault(v.path,demo=True);other.load();s['settings']['entity']='Changed';v.save(s)
            with self.assertRaises(ValueError):other.save(core.empty_state())
    def test_backup(self):
        with tempfile.TemporaryDirectory() as d:
            v=Vault(Path(d)/'demo.json',demo=True);s=v.load();v.save(s)
            folder=Path(d)/'external';folder.mkdir();dest=v.backup(folder)
            self.assertEqual(Vault(dest,demo=True).load(),s)
            with self.assertRaises(ValueError):v.backup(Path(d)/'missing')
    @unittest.skipUnless(os.name=='nt','Windows DPAPI requires Windows')
    def test_windows_encryption(self):
        raw=b'sensitive transaction'; encrypted=protect(raw)
        self.assertNotIn(raw,encrypted);self.assertEqual(protect(encrypted,True),raw)
        with tempfile.TemporaryDirectory() as d:
            v=Vault(Path(d)/'books.riju');s=v.load();v.save(s);self.assertEqual(v.load(),s)
            self.assertNotIn(b'ASMAKAM',v.path.read_bytes())

if __name__=='__main__':unittest.main()

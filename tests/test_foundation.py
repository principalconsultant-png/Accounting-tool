import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from riju import core, foundation as f
from riju.storage import Vault
from riju.revenue import receipt_lines


def receipt(branch='JP',amount=10000):
    return [dict(account='1000',branch=branch,debit=amount,credit=0),dict(account='4000',branch=branch,debit=0,credit=amount)]


def opening(branch='JP',amount=10000):
    return [dict(account='1010',branch=branch,debit=amount,credit=0),dict(account='3000',branch=branch,debit=0,credit=amount)]


class FoundationTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()

    def test_optional_registration_can_be_added_later(self):
        f.save_entity(self.s,'Hospital client',{})
        self.assertTrue(all(not v for v in self.s['settings']['registration'].values()))
        f.save_entity(self.s,'Hospital client',{'tan':'BLRA12345B','pan':'ABCDE1234F','state_code':'29','gstin':'29ABCDE1234F1Z5'})
        self.assertEqual(self.s['settings']['registration']['tan'],'BLRA12345B')
        for data in ({'tan':'bad'},{'gstin':'29ABCDE1234F1Z5','state_code':'32'},{'pan':'no'},{'state_code':'99'}):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):f.save_entity(self.s,'Hospital client',data)
            self.assertEqual(self.s,before)

    def test_branch_rename_new_branch_and_history_isolation(self):
        v=core.post(self.s,'2025-06-01','Sale',receipt());original=copy.deepcopy(v)
        f.save_branch(self.s,'JP',dict(self.s['branches']['JP'],name='JP Nagar Hospital'))
        f.save_branch(self.s,'NEW',{'name':'Future branch','beds':'0'})
        core.post(self.s,'2025-06-01','Sale',receipt('NEW'))
        self.assertEqual(self.s['vouchers'][0],original)
        self.assertEqual(core.balances(self.s,'2025-06-30','NEW')['4000'],-10000)
        self.assertEqual(core.balances(self.s,'2025-06-30')['4000'],-20000)
        lines=receipt_lines(self.s,'NEW',{'consultation':10000},{'cash':10000})
        self.assertEqual(lines[0]['branch'],'NEW')
        with self.assertRaises(ValueError):f.save_branch(self.s,'BAD',{'name':'Future branch'})
        f.save_branch(self.s,'NEW',dict(self.s['branches']['NEW'],active=False))
        with self.assertRaises(ValueError):core.post(self.s,'2025-06-02','Sale',receipt('NEW'))
        self.assertEqual(core.balances(self.s,'2025-06-30','NEW')['4000'],-10000)
        core.verify_audit(self.s)

    def test_ledger_classification_range_mapping_and_history(self):
        f.save_account(self.s,'1011','HDFC current','Asset','Cash and bank','Cash equivalent')
        lines=opening();lines[0]['account']='1011'
        v=core.post(self.s,'2024-04-01','Capital',lines);before=copy.deepcopy(v)
        f.save_account(self.s,'1011','HDFC current updated','Asset','Cash and bank','Cash equivalent',False)
        self.assertEqual(self.s['vouchers'][0],before)
        with self.assertRaises(ValueError):core.post(self.s,'2024-04-02','Capital',lines)
        with self.assertRaises(ValueError):f.delete_account(self.s,'1011')
        for args in [('6000','No','Asset','Other assets'),('1011','No','Revenue','Healthcare revenue')]:
            with self.assertRaises(ValueError):f.save_account(self.s,*args)
        with self.assertRaises(ValueError):f.save_account(self.s,'1000','Cash','Asset','Cash and bank',active=False)
        f.save_account(self.s,'4591','Unused expense','Expense','Administration',active=False)
        f.delete_account(self.s,'4591');self.assertFalse(any(a['code']=='4591' for a in self.s['accounts']))
        core.verify_audit(self.s)

    def test_shared_patient_control_no_double_revenue(self):
        patient=self.s['patient_control']
        self.assertEqual(next(a['name'] for a in self.s['accounts'] if a['code']==patient),'Patient A/C')
        billed=receipt();billed[0]['account']=patient
        core.post(self.s,'2025-06-01','Patient bill',billed)
        collected=[dict(account='1000',branch='JP',debit=10000,credit=0),dict(account=patient,branch='JP',debit=0,credit=10000)]
        core.post(self.s,'2025-06-01','Patient collection',collected)
        b=core.balances(self.s,'2025-06-30');self.assertEqual(b[patient],0);self.assertEqual(b['4000'],-10000)

    def test_department_tags_and_balanced_interbranch_transfer(self):
        f.save_departments(self.s,['Pharmacy','Therapy'])
        lines=receipt();lines[1]['cost_center']='Pharmacy'
        core.post(self.s,'2025-06-01','Department receipt',lines)
        with self.assertRaises(ValueError):f.save_departments(self.s,['Therapy'])
        invalid=receipt();invalid[0]['cost_center']='Pharmacy'
        with self.assertRaises(ValueError):core.post(self.s,'2025-06-02','Tagged cash',invalid)
        transfer=[dict(account='1130',branch='JP',debit=10000,credit=0),dict(account='1000',branch='JP',debit=0,credit=10000),
                  dict(account='1000',branch='KM',debit=10000,credit=0),dict(account='1130',branch='KM',debit=0,credit=10000)]
        core.post(self.s,'2025-06-03','Interbranch transfer',transfer,metadata={'type':'Transfer'})
        self.assertEqual(core.balances(self.s,'2025-06-30')['1130'],0)
        self.assertEqual(core.balances(self.s,'2025-06-30','JP')['1130'],10000)
        core.verify_audit(self.s)

    def test_initial_opening_once_and_automatic_carry_forward(self):
        core.post(self.s,'2023-04-01','Initial',opening(),opening=True)
        self.assertEqual(core.balances(self.s,'2025-04-01')['1010'],10000)
        self.assertEqual(core.balances(self.s,'2025-04-30','JP','2025-04-01')['1010'],0)
        for day in ('2023-04-01','2024-04-01'):
            with self.assertRaises(ValueError):core.post(self.s,day,'Duplicate',opening(),opening=True)
        with self.assertRaises(ValueError):core.post(self.s,'2023-04-01','Revenue opening',receipt('KM'),opening=True)
        core.post(self.s,'2023-04-01','Other branch',opening('KM'),opening=True)
        with self.assertRaisesRegex(ValueError,'predates'):core.post(self.s,'2022-06-01','Before initial opening',receipt())

    def test_atomic_opening_import_and_prior_history(self):
        text='date,narration,branch,debit_account,credit_account,amount\n2023-04-01,Initial,JP,1010,3000,100\n2023-04-01,Initial,KM,9999,3000,100\n'
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):f.import_openings(self.s,text)
        self.assertEqual(self.s,before)
        vouchers=f.import_openings(self.s,text.replace('9999','1010'));self.assertEqual(len(vouchers),2)
        self.assertEqual(core.balances(self.s,'2026-04-01')['1010'],20000)
        core.post(self.s,'2022-06-01','Older transaction',receipt('VK'))
        with self.assertRaises(ValueError):core.post(self.s,'2023-04-01','Duplicate carry-forward',opening('VK'),opening=True)

    def test_year_close_retained_earnings_and_comparative_profit(self):
        f.register_year(self.s,2023)
        core.post(self.s,'2023-04-01','Initial',opening(),opening=True)
        core.post(self.s,'2023-06-01','Revenue',receipt(amount=30000))
        core.post(self.s,'2023-06-02','Expense',[dict(account='4530',branch='JP',debit=10000,credit=0),dict(account='1000',branch='JP',debit=0,credit=10000)])
        f.close_year(self.s,2023)
        b=core.balances(self.s,'2024-04-01');self.assertEqual(b['3100'],-20000);self.assertEqual(b['4000'],0);self.assertEqual(b['4530'],0)
        p=core.balances(self.s,'2024-03-31','JP','2023-04-01');self.assertEqual(p['4000'],-30000);self.assertEqual(p['4530'],10000)
        with self.assertRaises(ValueError):core.post(self.s,'2024-03-31','Late sale',receipt())
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):f.close_year(self.s,2023)
        self.assertEqual(self.s,before)
        core.post(self.s,'2024-04-01','New year',receipt())
        core.verify_audit(self.s)

    def test_close_checks_pending_work_and_future_dates(self):
        d=f.save_draft(self.s,'2023-06-01','Unposted',receipt())
        with self.assertRaises(ValueError):f.close_year(self.s,2023)
        f.discard_draft(self.s,d['id'])
        with self.assertRaises(ValueError):f.close_year(self.s,2099)
        f.lock_period(self.s,'2023-03-31')
        with self.assertRaises(ValueError):f.lock_period(self.s,'2022-03-31')

    def test_save_edit_post_draft_is_once_and_atomic(self):
        lines=receipt();lines[0]['debit']=5000
        d=f.save_draft(self.s,'2025-06-01','Patient receipts',lines,{'type':'Receipt','reference':'REC-1'})
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):f.post_draft(self.s,d['id'])
        self.assertEqual(self.s,before)
        f.save_draft(self.s,'2025-06-01','Corrected patient receipts',receipt(),d['metadata'],d['id'])
        v=f.post_draft(self.s,d['id']);self.assertEqual(v['metadata']['reference'],'REC-1')
        self.assertFalse(self.s['drafts'])
        with self.assertRaises(ValueError):f.post_draft(self.s,d['id'])
        core.verify_audit(self.s)

    def test_transfer_advance_refund_and_explicit_reversal(self):
        core.post(self.s,'2025-06-01','Advance',[dict(account='1000',branch='JP',debit=10000,credit=0),dict(account='2300',branch='JP',debit=0,credit=10000)],metadata={'type':'Advance'})
        v=core.post(self.s,'2025-06-02','Refund',[dict(account='2300',branch='JP',debit=10000,credit=0),dict(account='1000',branch='JP',debit=0,credit=10000)],metadata={'type':'Refund'})
        self.assertEqual(core.balances(self.s,'2025-06-02')['2300'],0)
        core.post(self.s,'2025-06-02','Cash to bank',[dict(account='1010',branch='JP',debit=10000,credit=0),dict(account='1000',branch='JP',debit=0,credit=10000)],metadata={'type':'Transfer','bank_account':'1010'})
        with self.assertRaises(ValueError):core.post(self.s,'2025-06-03','Fake reversal',receipt(),reverses=v['id'])
        with self.assertRaises(ValueError):core.reverse(self.s,v['id'],'2025-06-01')
        core.reverse(self.s,v['id'],'2025-06-03');core.verify_audit(self.s)


class UpgradeTests(unittest.TestCase):
    def legacy(self,path):
        state=core.empty_state()
        core.post(state,'2025-06-01','Legacy receipt',receipt())
        for key in ('schema_revision','branches','account_details','financial_years','drafts','patient_control'):state.pop(key,None)
        state['version']=1
        # Simulate an actual v0.3.1 file; its posted payload must stay unchanged.
        path.write_text(json.dumps(state),encoding='utf-8')
        return state

    def test_upgrade_requires_verified_backup_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'legacy.json';old=self.legacy(p);raw=p.read_bytes()
            vault=Vault(p,demo=True);upgraded=vault.load();self.assertTrue(vault.migration_pending)
            self.assertEqual(upgraded['vouchers'],old['vouchers'])
            with self.assertRaisesRegex(ValueError,'external backup'):vault.save(upgraded)
            self.assertEqual(p.read_bytes(),raw)
            external=Path(directory)/'external';external.mkdir();upgraded['settings']['backup_dir']=str(external)
            vault.save(upgraded);self.assertEqual(vault.last_upgrade_backup.read_bytes(),raw)
            self.assertFalse(vault.migration_pending)
            self.assertEqual(vault.load(),upgraded);self.assertFalse(vault.migration_pending)
            self.assertEqual(len(list(external.iterdir())),1)

    def test_unavailable_backup_keeps_original(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'legacy.json';self.legacy(p);before=p.read_bytes();v=Vault(p,demo=True);state=v.load()
            state['settings']['backup_dir']=str(Path(directory)/'disconnected')
            with self.assertRaises(ValueError):v.save(state)
            self.assertEqual(p.read_bytes(),before)

    def test_restore_and_instance_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'demo.json';external=Path(directory)/'external';external.mkdir()
            v=Vault(p,demo=True);s=v.load();s['settings']['backup_dir']=str(external);v.save(s);backup=v.backup(external)
            core.post(s,'2025-06-01','New receipt',receipt());v.save(s)
            restored=v.restore(backup,external);self.assertFalse(restored['vouchers']);core.verify_audit(restored)
            self.assertTrue(any(Vault(p,demo=True).load()['vouchers'] for p in external.glob('*.json')))
            with v.instance_lock():
                child=subprocess.run([sys.executable,'-c',"from riju.storage import Vault; from pathlib import Path; import sys; v=Vault(Path(sys.argv[1]),demo=True); v.instance_lock().__enter__()",str(v.path)],capture_output=True,text=True)
                self.assertNotEqual(child.returncode,0);self.assertIn('another instance',child.stderr)
            with v.instance_lock():pass

    def test_rollback_on_replace_failure(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            v=Vault(Path(directory)/'books.json',demo=True);s=v.load();v.save(s);raw=v.path.read_bytes();s['settings']['entity']='Changed'
            with patch('riju.storage.os.replace',side_effect=OSError('disk error')):
                with self.assertRaises(OSError):v.save(s)
            self.assertEqual(v.path.read_bytes(),raw)
            self.assertFalse(list(Path(directory).glob('.riju-*')))

    def test_future_schema_and_tampered_history_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'demo.json';s=core.empty_state();s['schema_revision']=999;p.write_text(json.dumps(s))
            with self.assertRaises(ValueError):Vault(p,demo=True).load()
            s=core.empty_state();core.post(s,'2025-06-01','Sale',receipt());s['vouchers'][0]['narration']='Tampered';p.write_text(json.dumps(s))
            # Posting audit shares a payload in memory; serialize a true on-disk alteration.
            raw=json.loads(p.read_text());raw['vouchers'][0]['narration']='Another change';p.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):Vault(p,demo=True).load()

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from riju import core,foundation,ap
from riju.storage import Vault

class CleanBookTests(unittest.TestCase):
    def source(self,path):
        s=core.empty_state();foundation.save_entity(s,'TEST DATA TO CLEAR',{});supplier=ap.save_vendor(s,dict(name='Test vendor',credit_days='0'));ap.enter_invoice(s,dict(vendor=supplier['id'],reference='TEST-INV',branch='JP',invoice_date='2026-11-01',received_date='2026-11-01',accounting_date='2026-11-01',credit_days='0',due_basis='Receipt date',amount='100',payable='2000',allocations=[dict(account='4590',amount='100')],tax_treatment='No separate GST/TDS; reviewed',reviewed=True,basis='Test entry'))
        s['budgets']['test']=100;v=Vault(path,demo=True);v.save(s);return v,s
    def test_clear_all_data_preserve_verified_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'backup';folder.mkdir();v,s=self.source(root/'book.json');original=v.path.read_bytes();snapshot=copy.deepcopy(s)
            fresh,backup=v.start_clean_books(folder,'START CLEAN BOOKS');self.assertEqual(backup.read_bytes(),original);self.assertEqual(fresh['vouchers'],[]);self.assertEqual(fresh['ap'],dict(vendors=[],invoices=[],payments=[],schedules=[]));self.assertFalse(fresh['budgets']);self.assertFalse(fresh['queue']);self.assertFalse(fresh['drafts']);self.assertEqual(v.load(),fresh);self.assertNotIn('TEST DATA TO CLEAR',v.path.read_text());self.assertNotIn('Test vendor',v.path.read_text());self.assertEqual(Vault(backup,demo=True).load(),snapshot);core.verify_audit(fresh)
            restored=v.restore(backup,folder);self.assertEqual(restored['vouchers'],snapshot['vouchers']);self.assertEqual(restored['ap'],snapshot['ap'])
    def test_confirmation_and_backup_failures_leave_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);v,s=self.source(root/'book.json');original=v.path.read_bytes();digest=v.last_digest
            for folder,phrase in [(root/'missing','START CLEAN BOOKS'),(root,'START CLEAN BOOKS'),(root,'yes')]:
                with self.assertRaises(ValueError):v.start_clean_books(folder,phrase)
                self.assertEqual(v.path.read_bytes(),original);self.assertEqual(v.last_digest,digest)
            folder=root/'backup';folder.mkdir()
            with patch.object(v,'backup',side_effect=OSError('Unavailable backup')):
                with self.assertRaises(OSError):v.start_clean_books(folder,'START CLEAN BOOKS')
            self.assertEqual(v.path.read_bytes(),original)
    def test_failed_atomic_save_and_stale_session_do_not_clear(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'backup';folder.mkdir();v,s=self.source(root/'book.json');original=v.path.read_bytes()
            with patch('riju.storage.os.replace',side_effect=OSError('Disk full')):
                with self.assertRaises(OSError):v.start_clean_books(folder,'START CLEAN BOOKS')
            self.assertEqual(v.path.read_bytes(),original);self.assertTrue(any(p.read_bytes()==original for p in folder.iterdir()))
            other=Vault(v.path,demo=True);otherstate=other.load();otherstate['settings']['entity']='New saved change';other.save(otherstate);latest=v.path.read_bytes()
            with self.assertRaisesRegex(ValueError,'another instance'):v.start_clean_books(folder,'START CLEAN BOOKS')
            self.assertEqual(v.path.read_bytes(),latest)
    def test_corrupt_ap_source_is_blocked_with_value_error(self):
        from riju.history import verify_saved_state
        s=core.empty_state();s['ap']['invoices'].append(dict(id='BROKEN',voucher='missing',vendor='missing'))
        with self.assertRaisesRegex(ValueError,'AP integrity'):verify_saved_state(s)

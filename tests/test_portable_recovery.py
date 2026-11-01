import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from riju import core,history,portable_storage as ps,storage


def protector(identity):
    prefix=identity.encode()+b':'
    def protect(raw,decrypt=False):
        if decrypt:
            if not raw.startswith(prefix):raise OSError('Synthetic different Windows identity')
            return raw[len(prefix):]
        return prefix+raw
    return protect

class PortableRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.backups=self.root/'external';self.backups.mkdir();self.keys=self.root/'separate-device';self.keys.mkdir();self.patch=patch('riju.storage.protect',protector('PC1'));self.patch.start();self.v=self.vault(self.root/'live'/'books.riju');self.s=self.v.load();self.v.save(self.s)
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def vault(self,path):
        v=storage.Vault(path,demo=True,test_backup_root=self.root);v.demo=False;return v
    def enroll(self):
        key=self.keys/'key.json';self.v.export_recovery_key(key,self.backups);return key
    def test_aes_automatic_unlock_roundtrip_no_password_and_unique_nonces(self):
        raw=self.v.path.read_bytes();self.assertTrue(raw.startswith(ps.MAGIC));self.assertNotIn(self.s['settings']['entity'].encode(),raw);self.assertEqual(self.v.load(),self.s)
        self.v.save(self.s);self.assertNotEqual(raw,self.v.path.read_bytes());self.assertEqual(ps.envelope(raw)['key_id'],ps.envelope(self.v.path.read_bytes())['key_id'])
    def test_recovery_material_unlocks_without_old_windows_and_rewraps(self):
        key=self.enroll();source=self.v.backup(self.backups);original=source.read_bytes()
        with patch('riju.storage.protect',protector('PC2')):
            with self.assertRaises(ValueError):self.vault(source).load()
            replacement=self.vault(self.root/'replacement'/'books.riju');result=replacement.recover_with_key(source,key,self.backups);self.assertEqual(replacement.load(),result);self.assertEqual(result['vouchers'],self.s['vouchers']);self.assertTrue(any(a['action']=='PORTABLE_BACKUP_RECOVERED' for a in result['audit']))
        self.assertEqual(source.read_bytes(),original);self.assertEqual(ps.inspect(original,key)[0],self.s)
    def test_wrong_key_and_tampered_ciphertext_fail_before_replacement(self):
        key=self.enroll();source=self.v.backup(self.backups);raw=source.read_bytes();d=ps.envelope(raw);cipher=bytearray(ps._un64(d['ciphertext']));cipher[-1]^=1;d['ciphertext']=ps._b64(cipher);source.write_bytes(ps.MAGIC+json.dumps(d).encode());before=self.v.path.read_bytes()
        with self.assertRaises(ValueError):self.v.recover_with_key(source,key,self.backups)
        self.assertEqual(self.v.path.read_bytes(),before)
        otherid,otherkey=ps.new_key();wrong=self.keys/'wrong.json';ps.write_key(wrong,otherid,otherkey)
        with self.assertRaises(ValueError):ps.inspect(raw,wrong)
    def test_header_algorithm_key_id_and_nonce_authentication(self):
        raw=self.v.path.read_bytes();key=self.enroll()
        for field,value in [('algorithm','AES-128-GCM'),('key_id',ps.new_key()[0]),('nonce',ps._b64(b'1'*12))]:
            d=ps.envelope(raw);d[field]=value
            with self.assertRaises(ValueError):ps.inspect(ps.MAGIC+json.dumps(d).encode(),key)
    def test_key_export_is_exclusive_and_separate_from_backups(self):
        key=self.enroll();before=key.read_bytes()
        with self.assertRaises(FileExistsError):self.v.export_recovery_key(key,self.backups)
        self.assertEqual(key.read_bytes(),before)
        with self.assertRaises(ValueError):self.v.export_recovery_key(self.backups/'key.json',self.backups)
    def test_legacy_dpapi_upgrade_preserves_original_bytes_before_aes(self):
        legacy=self.root/'legacy'/'books.riju';legacy.parent.mkdir();old=core.empty_state();history.checkpoint(old);raw=storage.MAGIC+protector('PC1')(json.dumps(old).encode());legacy.write_bytes(raw);v=self.vault(legacy);s=v.load();self.assertTrue(v.encryption_upgrade_pending)
        with self.assertRaises(ValueError):v.save(s)
        self.assertEqual(legacy.read_bytes(),raw);s['settings']['backup_dir']=str(self.backups);v.save(s);self.assertEqual(v.last_upgrade_backup.read_bytes(),raw);self.assertTrue(legacy.read_bytes().startswith(ps.MAGIC));self.assertEqual(v.load(),s)
    def test_safety_copy_precedes_replacement_and_source_unchanged(self):
        key=self.enroll();source=self.v.backup(self.backups);old=source.read_bytes();self.s['settings']['entity']='Changed destination';self.v.save(self.s);active=self.v.path.read_bytes();restored=self.v.recover_with_key(source,key,self.backups)
        self.assertNotEqual(restored['settings']['entity'],'Changed destination');self.assertTrue(any(p.read_bytes()==active for p in self.backups.glob('*-safety.riju')));self.assertEqual(source.read_bytes(),old)
    def test_failed_save_preserves_active_file_and_safety_copy(self):
        key=self.enroll();source=self.v.backup(self.backups);before=self.v.path.read_bytes()
        original=storage.os.replace
        def fail_live(src,dest):
            if Path(dest)==self.v.path:raise OSError('Synthetic disconnected write')
            return original(src,dest)
        with patch('riju.storage.os.replace',side_effect=fail_live):
            with self.assertRaises(OSError):self.v.recover_with_key(source,key,self.backups)
        self.assertEqual(self.v.path.read_bytes(),before);self.assertTrue(list(self.backups.glob('*-safety.riju')))
    def test_missing_drive_retries_and_retention_never_prunes_safety_or_key(self):
        key=self.enroll();safety=self.v.backup(self.backups,reason='safety');upgrade=self.v.backup(self.backups,reason='upgrade')
        for i in range(4):self.v.backup(self.backups,keep=2)
        self.assertEqual(len(list(self.backups.glob('*-backup.riju'))),2);self.assertTrue(safety.exists());self.assertTrue(upgrade.exists());self.assertTrue(key.exists())
        disconnected=self.root/'offline';self.backups.rename(disconnected)
        with self.assertRaises(ValueError):self.v.backup(self.backups)
        disconnected.rename(self.backups);self.assertTrue(self.v.backup(self.backups).exists())
    def test_original_format_backup_cannot_be_recovered_without_old_windows(self):
        key=self.enroll()
        with self.assertRaisesRegex(ValueError,'Legacy DPAPI'):ps.inspect(storage.MAGIC+b'legacy',key)
    def test_demo_does_not_export_native_secrets_and_test_scope_is_bounded(self):
        demo=storage.Vault(self.root/'demo.json',demo=True);s=demo.load();demo.save(s)
        with self.assertRaises(ValueError):demo.export_recovery_key(self.keys/'demo.json',self.backups)
        with self.assertRaises(ValueError):self.v.validate_backup_directory(self.root.parent)
    def test_saved_state_integrity_must_pass_even_with_valid_aes_key(self):
        key=self.enroll();tampered=copy.deepcopy(self.s);tampered['settings']['entity']='Tampered';raw=ps.seal(json.dumps(tampered).encode(),self.v._key_id,self.v._data_key,protector('PC1'))
        with self.assertRaises(ValueError):ps.inspect(raw,key)
    def test_no_secret_material_in_book_data_or_history(self):
        key=self.enroll();raw=json.dumps(self.s,sort_keys=True).encode();self.assertNotIn(ps._b64(self.v._data_key).encode(),raw);self.assertNotIn(self.v._data_key,raw)
        recovered,key_id,secret,report=ps.inspect(self.v.path.read_bytes(),key);self.assertTrue(report['passed']);self.assertEqual(key_id,self.v._key_id)

    def test_retention_and_daily_status_do_not_mix_customer_vaults(self):
        from datetime import date
        second=self.vault(self.root/'second'/'books.riju');s=second.load();second.save(s);other=second.backup(self.backups)
        for i in range(3):self.v.backup(self.backups,keep=1)
        self.assertTrue(other.exists());self.assertTrue(self.v.verified_backup_today(self.backups,date.today()));self.assertTrue(second.verified_backup_today(self.backups,date.today()))
        other.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):second.verified_backup_today(self.backups,date.today())
    def test_external_hardware_policy_accepts_usb_and_rejects_internal_network_unknown(self):
        from types import SimpleNamespace
        self.v.test_backup_root=None
        split=lambda value:('D:' if str(self.backups) in value else 'C:','')
        with patch('riju.storage.os',SimpleNamespace(name='nt')),patch('ntpath.splitdrive',side_effect=split),patch.object(storage.ctypes,'WinDLL',create=True) as dll,patch('riju.storage.subprocess.run') as command:
            dll.return_value.GetDriveTypeW.return_value=2;self.assertEqual(self.v.validate_backup_directory(self.backups),self.backups);self.assertFalse(command.called)
            dll.return_value.GetDriveTypeW.return_value=3;command.return_value.stdout='USB\n';self.assertEqual(self.v.validate_backup_directory(self.backups),self.backups)
            command.return_value.stdout='SATA\n'
            with self.assertRaises(ValueError):self.v.validate_backup_directory(self.backups)
            dll.return_value.GetDriveTypeW.return_value=4
            with self.assertRaises(ValueError):self.v.validate_backup_directory(self.backups)
            dll.return_value.GetDriveTypeW.return_value=0
            with self.assertRaises(ValueError):self.v.validate_backup_directory(self.backups)

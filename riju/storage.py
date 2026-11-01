"""Atomic AES-GCM Windows vault, legacy DPAPI migration and portable recovery."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import copy
import subprocess
from contextlib import contextmanager
from .core import empty_state, verify_audit

MAGIC=b'RIJU-DPAPI-1\n'

@contextmanager
def file_lock(path):
    """OS-owned locks release on crashes; never guess from a stale PID file."""
    handle=open(path,'a+b')
    try:
        handle.seek(0,2)
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise ValueError('These books are open or being saved in another instance. Close it and try again.') from None
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    finally:handle.close()

class Blob(ctypes.Structure):
    _fields_=[('length',ctypes.c_uint32),('data',ctypes.POINTER(ctypes.c_ubyte))]

def protect(raw, decrypt=False):
    if os.name!='nt': raise RuntimeError('Windows encryption requires Windows. Use --demo for disposable development data.')
    buf=ctypes.create_string_buffer(raw)
    incoming=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)))
    outgoing=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        fn=crypt.CryptUnprotectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(incoming),None,None,None,None,1,ctypes.byref(outgoing))
    else:
        fn=crypt.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_wchar_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(incoming),'Riju Books',None,None,None,1,ctypes.byref(outgoing))
    if not ok: raise ctypes.WinError(ctypes.get_last_error())
    try: return ctypes.string_at(outgoing.data,outgoing.length)
    finally: kernel.LocalFree(ctypes.cast(outgoing.data,ctypes.c_void_p))

class Vault:
    def __init__(self,path=None,demo=False,test_backup_root=None):
        self.demo=demo
        base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'RijuBooks'
        self.path=Path(path) if path else base/('demo.json' if demo else 'books.riju')
        if os.name!='nt' and not demo: raise RuntimeError('Run on Windows, or use --demo for development only.')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._data_key=None
        self._key_id=None
        self.encryption_upgrade_pending=False
        self.test_backup_root=Path(test_backup_root).resolve() if test_backup_root else None
        if self.test_backup_root and not self.test_backup_root.is_relative_to(Path(tempfile.gettempdir()).resolve()):raise ValueError('Disposable backup tests must stay inside the OS temporary directory.')
        self.last_digest=None
        self.migration_pending=False
        self.last_upgrade_backup=None
    def instance_lock(self):
        return file_lock(str(self.path)+'.instance.lock')
    def load(self):
        if not self.path.exists(): return empty_state()
        raw=self.path.read_bytes()
        self.last_digest=hashlib.sha256(raw).hexdigest()
        if not self.demo:
            from . import portable_storage as portable
            if raw.startswith(portable.MAGIC):
                raw,self._key_id,self._data_key=portable.open_envelope(raw,protect)
            elif raw.startswith(MAGIC):
                raw=protect(raw[len(MAGIC):],True);self.encryption_upgrade_pending=True
            else:raise ValueError('Unknown vault format.')
        state=json.loads(raw)
        if state.get('version') not in (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17): raise ValueError('Unsupported vault version.')
        from .history import verify_saved_state
        verify_saved_state(state)
        before=json.dumps(state,sort_keys=True)
        from .revenue import ensure_accounts
        from .foundation import migrate
        state=migrate(ensure_accounts(state, audit=True))
        self.migration_pending=json.dumps(state,sort_keys=True)!=before
        return state
    def save(self,state):
        with file_lock(str(self.path)+'.write.lock'):
            self._save(state)
    def _save(self,state):
        verify_audit(state)
        if self.path.exists():
            digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
            if digest!=self.last_digest: raise ValueError('Vault changed in another instance. Close and reopen before saving.')
        elif self.last_digest is not None:
            raise ValueError('The loaded vault was removed. Reopen the books before saving.')
        if (self.migration_pending or self.encryption_upgrade_pending) and self.path.exists():
            folder=state['settings'].get('backup_dir')
            if not folder:raise ValueError('Upgrade pending: choose an external backup folder in Settings & backup before saving. Your original books are unchanged.')
            self.last_upgrade_backup=self.backup(folder,reason='upgrade')
        import copy
        from .history import checkpoint
        candidate=copy.deepcopy(state);checkpoint(candidate)
        raw=json.dumps(candidate,ensure_ascii=False,separators=(',',':')).encode()
        if not self.demo:
            from . import portable_storage as portable
            if self._data_key is None:self._key_id,self._data_key=portable.new_key()
            raw=portable.seal(raw,self._key_id,self._data_key,protect)
        fd,name=tempfile.mkstemp(prefix='.riju-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(name,self.path)
            self.last_digest=hashlib.sha256(raw).hexdigest()
            self.migration_pending=False
            self.encryption_upgrade_pending=False
            state['audit']=candidate['audit']
        finally:
            if os.path.exists(name): os.unlink(name)
    def validate_backup_directory(self,directory):
        target=Path(directory)
        if not target.is_dir():raise ValueError('Backup drive/folder is unavailable. Reconnect your external drive.')
        if target.resolve()==self.path.parent.resolve():raise ValueError('Choose a separate backup folder.')
        if self.demo:return target
        if self.test_backup_root:
            if not target.resolve().is_relative_to(self.test_backup_root) or not self.path.resolve().is_relative_to(self.test_backup_root):raise ValueError('Disposable test backup escaped its temporary directory.')
            return target
        if os.name!='nt':raise ValueError('External-drive validation requires Windows.')
        import ntpath
        drive=ntpath.splitdrive(str(target.resolve()))[0]
        if len(drive)!=2 or drive[1]!=':' or not drive[0].isascii() or not drive[0].isalpha() or drive.casefold()==ntpath.splitdrive(str(self.path.resolve()))[0].casefold():raise ValueError('Use a separate external USB/removable drive, not the live-books volume or a network/cloud path.')
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kind=kernel.GetDriveTypeW(ctypes.c_wchar_p(drive+'\\'))
        if kind==2:return target
        if kind!=3:raise ValueError('Use a connected local external drive; network paths are not backup destinations.')
        command="Get-Partition -DriveLetter '"+drive[0]+"' -ErrorAction Stop | Get-Disk | Select-Object -ExpandProperty BusType"
        try:
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=15,check=True)
            if result.stdout.strip().upper() not in ('USB','SD','MMC','1394'):raise ValueError('Selected volume is not identified as an external/removable drive.')
        except (OSError,subprocess.SubprocessError) as e:raise ValueError('Cannot verify external drive hardware; reconnect/select an identifiable USB/removable drive.') from e
        return target

    def backup(self,directory,reason='backup',keep=30):
        target=self.validate_backup_directory(directory)
        if reason not in ('backup','upgrade','safety'):raise ValueError('Invalid backup purpose.')
        if type(keep)!=int or not 1<=keep<=3650:raise ValueError('Keep 1–3650 routine backups.')
        from datetime import datetime
        tag=self._key_id or hashlib.sha256(str(self.path.resolve()).encode()).hexdigest()[:16]
        name='Riju-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-'+tag+'-'+reason+self.path.suffix
        dest=target/name
        fd,temporary=tempfile.mkstemp(prefix='.riju-backup-',dir=target)
        os.close(fd)
        try:
            shutil.copy2(self.path,temporary)
            if Path(temporary).read_bytes()!=self.path.read_bytes():raise IOError('Backup verification failed; books changed or copying failed.')
            os.replace(temporary,dest)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
        if reason=='backup':
            routine=sorted(target.glob('Riju-*-'+tag+'-backup'+self.path.suffix),key=lambda p:p.name,reverse=True)
            for old in routine[keep:]:old.unlink()
        return dest
    def verified_backup_today(self,directory,today):
        target=self.validate_backup_directory(directory)
        tag=self._key_id or hashlib.sha256(str(self.path.resolve()).encode()).hexdigest()[:16]
        existing=sorted(target.glob('Riju-'+today.strftime('%Y%m%d')+'-*-'+tag+'-backup'+self.path.suffix),reverse=True)
        if not existing:return False
        # A partial or subsequently damaged file is not a successful backup.
        raw=existing[0].read_bytes()
        if not self.demo:
            from . import portable_storage as portable
            if raw.startswith(portable.MAGIC):raw,_,_=portable.open_envelope(raw,protect)
            elif raw.startswith(MAGIC):raw=protect(raw[len(MAGIC):],True)
            else:raise ValueError('Backup format/authentication failed.')
        from .history import verify_saved_state,integrity_report
        state=json.loads(raw);verify_saved_state(state)
        if not integrity_report(state)['passed']:raise ValueError('Backup consistency verification failed.')
        return True

    def restore(self,path,backup_directory):
        source=Vault(path,demo=self.demo,test_backup_root=self.test_backup_root)
        restored=source.load()
        # Use the live external-drive selection, not an obsolete backup path.
        prior_backup_folder=restored['settings'].get('backup_dir','')
        restored['settings']['backup_dir']=str(backup_directory)
        safety_copy=None
        with file_lock(str(self.path)+'.write.lock'):
            if self.path.exists():
                if hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.last_digest:
                    raise ValueError('Vault changed in another instance. Reopen before restoring.')
                safety_copy=self.backup(backup_directory,reason='safety')
            else:
                if not Path(backup_directory).is_dir():raise ValueError('External backup folder is unavailable.')
            from .core import add_audit
            add_audit(restored,'BACKUP_RESTORED',{'filename':Path(path).name,'source_digest':source.last_digest,'previous_live_digest':self.last_digest,'safety_copy':safety_copy.name if safety_copy else None,'old_backup_folder':prior_backup_folder,'new_backup_folder':str(backup_directory)})
            old_key,old_id=self._data_key,self._key_id
            if source._data_key:self._data_key,self._key_id=source._data_key,source._key_id
            try:self._save(restored)
            except Exception:self._data_key,self._key_id=old_key,old_id;raise
        return restored


    def export_recovery_key(self,path,backup_directory):
        from . import portable_storage as portable
        if self.demo or not self._data_key or not self.path.exists():raise ValueError('Save native AES-GCM books before exporting their recovery material; demo JSON is not encrypted.')
        target=Path(path);self.validate_backup_directory(target.parent);self.validate_backup_directory(backup_directory)
        if target.parent.resolve()==Path(backup_directory).resolve():raise ValueError('Keep recovery material separately from backup files.')
        if not self.test_backup_root:
            import ntpath
            if ntpath.splitdrive(str(target.resolve()))[0].casefold()==ntpath.splitdrive(str(Path(backup_directory).resolve()))[0].casefold():raise ValueError('Use a different separately held external device for recovery material, not the backup drive.')
        portable.write_key(target,self._key_id,self._data_key)
        # Verify it against the actual saved bytes before declaring success.
        try:portable.inspect(self.path.read_bytes(),target)
        except Exception:target.unlink(missing_ok=True);raise
        return dict(key_id=self._key_id,verified=True)

    def recover_with_key(self,source_path,key_path,backup_directory):
        from . import portable_storage as portable,foundation,history
        if self.demo:raise ValueError('Portable recovery restores encrypted native books, not demo JSON.')
        self.validate_backup_directory(backup_directory)
        source=Path(source_path)
        if source.resolve()==self.path.resolve():raise ValueError('Choose a separate trusted backup; do not recover over its only original copy.')
        raw=source.read_bytes();restored,key_id,key,report=portable.inspect(raw,key_path)
        restored=foundation.migrate(restored)
        # Never reuse an obsolete drive selection from a recovered machine.
        restored['settings']['backup_dir']=str(backup_directory)
        with file_lock(str(self.path)+'.write.lock'):
            if self.path.exists():
                digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
                if self.last_digest is not None and digest!=self.last_digest:raise ValueError('Active books changed. Reopen before restoring.')
                self.last_digest=digest;safety=self.backup(backup_directory,reason='safety')
            else:safety=None
            core_payload=dict(source_digest=hashlib.sha256(raw).hexdigest(),key_id=key_id,safety_copy=safety.name if safety else None,verification='AES-GCM authentication and saved-state/voucher integrity passed')
            from .core import add_audit
            add_audit(restored,'PORTABLE_BACKUP_RECOVERED',core_payload)
            previous=(self._key_id,self._data_key,self.migration_pending,self.encryption_upgrade_pending)
            self._key_id,self._data_key=key_id,key;self.migration_pending=False;self.encryption_upgrade_pending=False
            try:self._save(restored)
            except Exception:
                self._key_id,self._data_key,self.migration_pending,self.encryption_upgrade_pending=previous;raise
        return restored

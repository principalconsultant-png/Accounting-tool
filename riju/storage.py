"""Atomic Windows DPAPI vault. Non-Windows use is explicitly demo-only."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
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
    def __init__(self,path=None,demo=False):
        self.demo=demo
        base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'RijuBooks'
        self.path=Path(path) if path else base/('demo.json' if demo else 'books.riju')
        if os.name!='nt' and not demo: raise RuntimeError('Run on Windows, or use --demo for development only.')
        self.path.parent.mkdir(parents=True,exist_ok=True)
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
            if not raw.startswith(MAGIC): raise ValueError('Unknown vault format.')
            raw=protect(raw[len(MAGIC):],True)
        state=json.loads(raw)
        if state.get('version') not in (1,2,3,4,5,6,7,8,9,10,11,12,13): raise ValueError('Unsupported vault version.')
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
        if self.migration_pending and self.path.exists():
            folder=state['settings'].get('backup_dir')
            if not folder:raise ValueError('Upgrade pending: choose an external backup folder in Settings & backup before saving. Your original books are unchanged.')
            self.last_upgrade_backup=self.backup(folder)
        import copy
        from .history import checkpoint
        candidate=copy.deepcopy(state);checkpoint(candidate)
        raw=json.dumps(candidate,ensure_ascii=False,separators=(',',':')).encode()
        if not self.demo: raw=MAGIC+protect(raw)
        fd,name=tempfile.mkstemp(prefix='.riju-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(name,self.path)
            self.last_digest=hashlib.sha256(raw).hexdigest()
            self.migration_pending=False
            state['audit']=candidate['audit']
        finally:
            if os.path.exists(name): os.unlink(name)
    def backup(self,directory):
        target=Path(directory)
        if not target.is_dir(): raise ValueError('Backup drive/folder is unavailable. Reconnect your external drive.')
        if target.resolve()==self.path.parent.resolve(): raise ValueError('Choose a separate backup folder.')
        from datetime import datetime
        name='Riju-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+self.path.suffix
        dest=target/name
        shutil.copy2(self.path,dest)
        if dest.read_bytes()!=self.path.read_bytes(): raise IOError('Backup verification failed.')
        return dest
    def restore(self,path,backup_directory):
        source=Vault(path,demo=self.demo)
        restored=source.load()
        # Use the live external-drive selection, not an obsolete backup path.
        prior_backup_folder=restored['settings'].get('backup_dir','')
        restored['settings']['backup_dir']=str(backup_directory)
        safety_copy=None
        with file_lock(str(self.path)+'.write.lock'):
            if self.path.exists():
                if hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.last_digest:
                    raise ValueError('Vault changed in another instance. Reopen before restoring.')
                safety_copy=self.backup(backup_directory)
            else:
                if not Path(backup_directory).is_dir():raise ValueError('External backup folder is unavailable.')
            from .core import add_audit
            add_audit(restored,'BACKUP_RESTORED',{'filename':Path(path).name,'source_digest':source.last_digest,'previous_live_digest':self.last_digest,'safety_copy':safety_copy.name if safety_copy else None,'old_backup_folder':prior_backup_folder,'new_backup_folder':str(backup_directory)})
            self._save(restored)
        return restored

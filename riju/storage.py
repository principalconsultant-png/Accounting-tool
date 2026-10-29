"""Atomic Windows DPAPI vault. Non-Windows use is explicitly demo-only."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from .core import empty_state, verify_audit

MAGIC=b'RIJU-DPAPI-1\n'

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
    def load(self):
        if not self.path.exists(): return empty_state()
        raw=self.path.read_bytes()
        self.last_digest=hashlib.sha256(raw).hexdigest()
        if not self.demo:
            if not raw.startswith(MAGIC): raise ValueError('Unknown vault format.')
            raw=protect(raw[len(MAGIC):],True)
        state=json.loads(raw)
        if state.get('version')!=1: raise ValueError('Unsupported vault version.')
        verify_audit(state)
        from .revenue import ensure_accounts
        return ensure_accounts(state, audit=True)
    def save(self,state):
        if self.path.exists():
            digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
            if digest!=self.last_digest: raise ValueError('Vault changed in another instance. Close and reopen before saving.')
        raw=json.dumps(state,ensure_ascii=False,separators=(',',':')).encode()
        if not self.demo: raw=MAGIC+protect(raw)
        fd,name=tempfile.mkstemp(prefix='.riju-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(name,self.path)
            self.last_digest=hashlib.sha256(raw).hexdigest()
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

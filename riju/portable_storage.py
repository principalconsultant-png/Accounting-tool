"""Authenticated portable vault envelope and separately held recovery material.

Data encryption keys never enter the books, history or reports. The live envelope
contains a Windows-protected key for automatic opening; a separately held key
file can decrypt a backup on a replacement machine without the old Windows keys.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'RIJU-AESGCM-2\n'


def _b64(value):return base64.b64encode(value).decode('ascii')
def _un64(value):
    try:return base64.b64decode(value,validate=True)
    except (ValueError,TypeError) as e:raise ValueError('Invalid encrypted-vault encoding.') from e

def new_key():return str(uuid.uuid4()),AESGCM.generate_key(bit_length=256)
def seal(raw,key_id,key,protect):
    nonce=os.urandom(12);aad=MAGIC+key_id.encode('ascii');cipher=AESGCM(key).encrypt(nonce,raw,aad)
    return MAGIC+json.dumps(dict(version=2,algorithm='AES-256-GCM',key_id=key_id,wrapped_key=_b64(protect(key)),nonce=_b64(nonce),ciphertext=_b64(cipher)),sort_keys=True,separators=(',',':')).encode('utf-8')

def envelope(raw):
    try:
        if not raw.startswith(MAGIC):raise ValueError('This backup has no portable AES-GCM envelope. Legacy DPAPI backups require the original Windows account.')
        d=json.loads(raw[len(MAGIC):])
        if d['version']!=2 or d['algorithm']!='AES-256-GCM' or str(uuid.UUID(d['key_id']))!=d['key_id']:raise ValueError('Unsupported authenticated vault header.')
        if len(_un64(d['nonce']))!=12:raise ValueError('Invalid authenticated-vault nonce.')
        return d
    except (KeyError,TypeError,UnicodeError,json.JSONDecodeError) as e:raise ValueError('Invalid authenticated vault header.') from e

def open_envelope(raw,unprotect=None,recovery=None):
    d=envelope(raw)
    try:
        if recovery is not None:
            if recovery['key_id']!=d['key_id']:raise ValueError('Recovery key belongs to different books.')
            key=recovery['key']
        else:key=unprotect(_un64(d['wrapped_key']),True)
        if len(key)!=32:raise ValueError('Invalid recovery/encryption key length.')
        plain=AESGCM(key).decrypt(_un64(d['nonce']),_un64(d['ciphertext']),MAGIC+d['key_id'].encode('ascii'))
        return plain,d['key_id'],key
    except ValueError:raise
    except Exception as e:raise ValueError('Vault authentication/unlocking failed. Use a verified backup and its separately held recovery key; do not overwrite these books.') from e

def write_key(path,key_id,key):
    dest=Path(path)
    payload=dict(format='RIJU-RECOVERY-1',key_id=key_id,key=_b64(key),key_digest=hashlib.sha256(key).hexdigest(),instruction='Keep separately from books and backups. This file grants full access to matching encrypted books. Do not email it or include it in reports/backups.')
    # Exclusive creation prevents accidentally replacing the only older key.
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(payload,f,indent=2);f.flush();os.fsync(f.fileno())
        if read_key(dest)['key']!=key:raise ValueError('Recovery key verification failed.')
    except Exception:
        dest.unlink(missing_ok=True);raise
    return dest

def read_key(path):
    p=Path(path)
    if p.stat().st_size>16384:raise ValueError('Invalid recovery material size.')
    try:
        d=json.loads(p.read_text(encoding='utf-8'));key=_un64(d['key'])
        if d['format']!='RIJU-RECOVERY-1' or len(key)!=32 or hashlib.sha256(key).hexdigest()!=d['key_digest']:raise ValueError('Recovery key validation failed.')
        return dict(key_id=d['key_id'],key=key)
    except (KeyError,TypeError,UnicodeError,json.JSONDecodeError) as e:raise ValueError('Invalid recovery material.') from e


def inspect(raw,keypath):
    from .history import verify_saved_state,integrity_report
    plain,key_id,key=open_envelope(raw,recovery=read_key(keypath));state=json.loads(plain)
    if not verify_saved_state(state):raise ValueError('Portable backup has no authenticated saved-state checkpoint.')
    report=integrity_report(state)
    if not report['passed']:raise ValueError('Recovered books failed consistency review: '+'; '.join(report['errors']))
    return state,key_id,key,report

"""No-password portable backup enrollment, verification and recovery."""
import hashlib
from pathlib import Path
from tkinter import filedialog,messagebox
from . import core,history,portable_storage

class RecoveryUI:
    def recovery_controls(self):
        self.note('Native books use AES-256-GCM with a Windows-protected key for automatic opening. Export a separately held recovery key to another external device and verify a backup before relying on replacement-PC recovery. The key grants full access to matching books; keep it offline and separate from backups. No app password is required. Demo JSON remains unencrypted.')
        marker=self.state['settings'].get('recovery_key_id')
        self.note('Recovery enrollment: '+('key exported/verified for '+marker if marker else 'NOT ENROLLED — export and separately retain recovery material before live rollout.'))
        bar=self.bar();self.button(bar,'Export recovery key',self.export_portable_key,True);self.button(bar,'Verify portable backup + key',self.verify_portable_backup);self.button(bar,'Restore using recovery key',self.restore_portable_backup)

    def export_portable_key(self):
        folder=self.state['settings'].get('backup_dir')
        if not folder:raise ValueError('Choose a verified external backup folder first.')
        path=filedialog.asksaveasfilename(parent=self,title='Save recovery material on a DIFFERENT separately held external device',initialfile='Riju-recovery-key.json',defaultextension='.json')
        if not path:return
        # First native save creates/upgrades the AES envelope with the original backup safeguard.
        self.vault.save(self.state)
        result=self.vault.export_recovery_key(path,folder)
        def record(s):
            s['settings']['recovery_key_id']=result['key_id'];s['settings']['recovery_verified_at']=history.datetime.now(history.INDIA).isoformat();core.add_audit(s,'RECOVERY_KEY_EXPORTED',dict(key_id=result['key_id'],verified=True))
        self.commit(record);self.show('Settings & backup');messagebox.showinfo('Recovery material verified','Keep the exported recovery material separately from the books and backup drive. It grants access to matching encrypted books. Verify an actual external backup next.',parent=self)

    def _portable_selection(self):
        source=filedialog.askopenfilename(parent=self,title='Select trusted AES-GCM backup',filetypes=[('Encrypted Riju books','*.riju')])
        if not source:return None
        key=filedialog.askopenfilename(parent=self,title='Select separately held recovery material',filetypes=[('Riju recovery material','*.json')])
        return (source,key) if key else None

    def verify_portable_backup(self):
        selected=self._portable_selection()
        if not selected:return
        source,key=selected;raw=Path(source).read_bytes();state,key_id,secret,report=portable_storage.inspect(raw,key)
        del secret
        def record(s):core.add_audit(s,'RECOVERY_DRILL_VERIFIED',dict(source_digest=hashlib.sha256(raw).hexdigest(),key_id=key_id,passed=True,vouchers=report['vouchers_checked']))
        self.commit(record);messagebox.showinfo('Portable verification passed','AES-GCM authentication and book integrity passed using only backup plus recovery material. Source backup is unchanged. Entity: '+state['settings']['entity']+'\nVouchers: '+str(report['vouchers_checked']),parent=self)

    def restore_portable_backup(self):
        selected=self._portable_selection()
        if not selected:return
        source,key=selected;restored,key_id,secret,report=portable_storage.inspect(Path(source).read_bytes(),key);del secret
        if not messagebox.askyesno('Review portable recovery','Restore '+restored['settings']['entity']+' from '+Path(source).name+'?\nAuthentication and integrity passed. The active file will first be safety-copied to your external backup folder. The source backup and recovery key are preserved.',parent=self):return
        folder=self.state['settings'].get('backup_dir')
        if not folder:folder=filedialog.askdirectory(parent=self,title='External drive folder for safety backup')
        if not folder:return
        self.state=self.vault.recover_with_key(source,key,folder);self.refresh_masters();self.show('Overview')

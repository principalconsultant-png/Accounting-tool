"""Packaged executable readiness check; operates only in a disposable directory."""
import io
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime
from . import APP_VERSION,core,foundation
from .revenue import MODES
from .sales_import import stage_sales,approve_sales
from .storage import Vault

def run(output):
    result={'version':APP_VERSION,'passed':False,'platform':os.name}
    try:
        from openpyxl import Workbook
        w=Workbook();s=w.active
        for col,(_,label,*_) in enumerate(MODES,8):s.cell(4,col,label)
        for col,label in enumerate(('Sub total','Card','UPI','Cash','Other source','Total'),23):s.cell(4,col,label)
        s.cell(5,1,1);s.cell(5,2,datetime(2026,6,1));s.cell(5,6,'TEST-INVOICE');s.cell(5,7,'TEST-RECEIPT')
        for col in range(8,23):s.cell(5,col,100)
        s.cell(5,23,1500);s.cell(5,24,500);s.cell(5,25,500);s.cell(5,26,500);s.cell(5,27,0);s.cell(5,28,1500)
        raw=io.BytesIO();w.save(raw);w.close()
        with tempfile.TemporaryDirectory() as directory:
            v=Vault(Path(directory)/'check.riju');state=v.load()
            q=stage_sales(state,raw.getvalue(),'synthetic.xlsx','JP');approve_sales(state,q['id'])
            v.save(state);loaded=v.load();core.verify_audit(loaded)
            if state!=loaded or len(loaded['vouchers'])!=1:raise ValueError('Vault round-trip mismatch')
            if sum(core.balances(loaded,'2026-06-30').values())!=0:raise ValueError('Unbalanced report')
            folder=Path(directory)/'external';folder.mkdir();dest=v.backup(folder)
            if Vault(dest).load()!=loaded:raise ValueError('Backup restore mismatch')
            foundation.save_entity(loaded,'Synthetic hospital',{})
            foundation.save_branch(loaded,'NEW',{'name':'Synthetic branch','beds':0})
            foundation.save_account(loaded,'1011','Synthetic bank','Asset','Cash and bank')
            lines=[dict(account='1011',branch='NEW',debit=10000,credit=0),dict(account='3000',branch='NEW',debit=0,credit=10000)]
            draft=foundation.save_draft(loaded,'2024-04-01','Synthetic opening',lines,{'type':'Journal'},opening=True)
            foundation.post_draft(loaded,draft['id']);v.save(loaded)
            if v.load()!=loaded:raise ValueError('Foundation vault round-trip mismatch')
            # A real previous-format encrypted vault must be preserved before migration.
            from .storage import MAGIC,protect
            legacy=core.empty_state();legacy['version']=1
            for key in ('schema_revision','branches','account_details','financial_years','drafts','patient_control'):legacy.pop(key,None)
            old=Vault(Path(directory)/'legacy.riju')
            original=MAGIC+protect(json.dumps(legacy).encode());old.path.write_bytes(original)
            upgraded=old.load();upgraded['settings']['backup_dir']=str(folder);old.save(upgraded)
            if old.last_upgrade_backup.read_bytes()!=original:raise ValueError('Upgrade backup differs from original vault')
            if old.load()!=upgraded:raise ValueError('Upgrade round-trip mismatch')
            result['foundation_checks_passed']=True
            result.update(passed=True,revenue_modes=len(MODES),posted_vouchers=1,windows_vault_backup_roundtrip=True)
    except Exception as error:
        result['error']=str(error)
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result['passed']

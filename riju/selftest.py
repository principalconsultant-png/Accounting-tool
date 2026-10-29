"""Packaged executable readiness check; operates only in a disposable directory."""
import io
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime
from . import APP_VERSION,core
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
            result.update(passed=True,revenue_modes=len(MODES),posted_vouchers=1,windows_vault_backup_roundtrip=True)
    except Exception as error:
        result['error']=str(error)
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result['passed']

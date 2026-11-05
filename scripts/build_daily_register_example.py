"""Synthetic daily register and relational database, no client figures."""
from pathlib import Path
from riju import core,foundation,daily_consolidation as d,financial_reports as reports

def build(out):
    from openpyxl import Workbook
    out=Path(out);out.mkdir(parents=True,exist_ok=True);s=core.empty_state();s['settings']['entity']='TRAINING EXAMPLE — SYNTHETIC DAILY REGISTER';foundation.save_account(s,'2310','Salary payable','Liability','Other liabilities');foundation.save_account(s,'1190','Staff advance','Asset','Other assets')
    def pair(dr,cr,n):return [dict(account=dr,branch='JP',debit=n,credit=0),dict(account=cr,branch='JP',debit=0,credit=n)]
    def post(day,dr,cr,n,**kw):return core.post(s,day,'Synthetic training only',pair(dr,cr,n),**kw)
    core.post(s,'2026-04-01','Synthetic opening',pair('1000','3000',100000)+pair('1010','3000',500000),opening=True)
    for day,n in [('2026-04-02',120000),('2026-04-03',150000),('2026-04-04',90000)]:post(day,'1110','4000',n,metadata={'type':'Receipt','reference':'SYNTHETIC-'+day})
    post('2026-04-02','4520','2310',80000);post('2026-04-03','2310','1010',80000);post('2026-04-03','4590','1000',5000);post('2026-04-03','1190','1000',2000);post('2026-04-03','1100','2000',30000);post('2026-04-04','1030','2000',100000);post('2026-04-04','1010','1110',360000);post('2026-04-04','4580','1010',1000)
    d.refresh(s,'2026-04-01','2026-04-05');wb=Workbook();wb.remove(wb.active)
    for section in ('Daily table','What is left out','Source gaps','Source drilldown'):reports._worksheet(wb,d.pack(s,'2026-04-01','2026-04-05',section=section),section)
    wb.save(out/'Yathartha-Daily-Business-Register-Sample.xlsx');wb.close();reports.export_pdf(d.pack(s,'2026-04-01','2026-04-05'),out/'Yathartha-Daily-Business-Register-Sample.pdf');db,meta,stale=d.saved(s)
    try:(out/'Yathartha-Daily-Business-Register-Sample.sqlite').write_bytes(db.serialize())
    finally:db.close()

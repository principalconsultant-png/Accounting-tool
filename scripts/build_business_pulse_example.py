"""Build a clearly labelled, wholly synthetic monthly report for training."""
from pathlib import Path
from riju import core,foundation,business_pulse as b
from riju.business_pulse_exports import export_xlsx,export_pdf

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);s=core.empty_state();s['settings']['entity']='TRAINING EXAMPLE — SYNTHETIC FIGURES'
    foundation.save_account(s,'4521','Staff overtime','Expense','Employee benefits')
    policy=b.policy(s);policy.update(salary_accounts=['4520'],ot_accounts=['4521'],compliance_accounts=['4590'],reviewed=True,basis='Synthetic training mappings only');b.save_policy(s,policy)
    def post(day,dr,cr,n):return core.post(s,day,'Synthetic training entry',[dict(account=dr,branch='JP',debit=n,credit=0),dict(account=cr,branch='JP',debit=0,credit=n)])
    from riju import petty_cash
    for i,m in enumerate(range(4,11)):
        for j in range(12+i*2):post(f'2026-{m:02d}-{j%26+1:02d}',['1000','1110','1120'][j%3],'4000',(1800+i*90+(j%4)*120)*100)
        post(f'2026-{m:02d}-28','4520','1010',(14000+i*600)*100);post(f'2026-{m:02d}-28','4521','1010',(500+(i%3)*150)*100);post(f'2026-{m:02d}-28','4590','1010',(900+(i%4)*200)*100)
        petty_cash.record(s,dict(date=f'2026-{m:02d}-28',reference='TRAIN-PC-'+str(m),branch='JP',category='Office',treatment='Expense',account='4590',amount=str(300+i*35),narration='Synthetic petty purchase',basis='Synthetic training only'),True)
        b.save_month(s,dict(month=f'2026-{m:02d}',branch='ALL',visits='',new_patients=3+i,books_reviewed=True,basis='Synthetic training month, not client data'))
    pack=b.snapshot(s,2026,'2026-10-31');export_xlsx(pack,out/'Yathartha-Business-Pulse-Sample.xlsx');export_pdf(pack,out/'Yathartha-Business-Pulse-Sample.pdf')

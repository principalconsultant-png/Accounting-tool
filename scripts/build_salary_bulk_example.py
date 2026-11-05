"""Synthetic two-month payroll source and reconciled posting example."""
from pathlib import Path
import csv,io
from riju import core,payroll_accounts,salary_bulk,bulk_import,financial_reports

def build(out):
    from openpyxl import load_workbook
    out=Path(out);out.mkdir(parents=True,exist_ok=True);s=core.empty_state();s['settings']['entity']='TRAINING ONLY — SYNTHETIC SALARY JOURNALS';payroll_accounts.setup(s,payroll_accounts.choices(s),'Synthetic payroll roles',True)
    core.post(s,'2026-04-01','Synthetic opening bank',[dict(account='1010',branch='JP',debit=10000000,credit=0),dict(account='3000',branch='JP',debit=0,credit=10000000)],opening=True)
    rows=[['ACCRUAL','2026-04','JP','','TRAINING-ACCR-APR','','30000','','','Synthetic April payroll; no deductions'],['PAYMENT','2026-04','JP','2026-05-05','TRAINING-APR-P1','1010','10000','','Training batch A','Synthetic bank evidence'],['PAYMENT','2026-04','JP','2026-05-06','TRAINING-APR-P2','1010','20000','','Training batch B','Synthetic bank evidence'],['ACCRUAL','2026-05','JP','','TRAINING-ACCR-MAY','','40000','','','Synthetic May payroll; no deductions'],['PAYMENT','2026-05','JP','2026-06-05','TRAINING-MAY-P1','1010','15000','','Training batch A','Synthetic bank evidence'],['PAYMENT','2026-05','JP','2026-06-06','TRAINING-MAY-P2','1010','25000','','Training batch B','Synthetic bank evidence']]
    path=out/'Yathartha-Salary-Journals-Worked-Example.xlsx';salary_bulk.template(path,s);w=load_workbook(path);ws=w['Salary Journals']
    for number,row in enumerate(rows,2):
        for col,value in enumerate(row,1):ws.cell(number,col,value)
    w['Instructions'].cell(1,1,'TRAINING ONLY: synthetic entries, not client payroll. Do not upload unchanged into live books. Two accruals total70,000; four payments total70,000; salary payable0 after6 June. Opening bank100,000 leaves30,000.');w.save(path);w.close()
    raw=io.StringIO();writer=csv.writer(raw);writer.writerow(salary_bulk.HEADERS);writer.writerows(rows);q=salary_bulk.stage(s,raw.getvalue().encode(),'synthetic-salary.csv')
    for i in range(len(rows)):bulk_import.review_row(s,q['id'],i,True,'Synthetic source reviewed')
    bulk_import.approve(s,q['id']);m=s['settings']['payroll_ledgers'];balances=core.balances(s,'2026-06-30');assert balances[m['salary_expense']]==7000000 and balances[m['salary_payable']]==0 and balances['1010']==3000000
    financial_reports.export_xlsx(financial_reports.snapshot(s,'General ledger','2026-04-01','2026-06-30'),out/'Yathartha-Salary-Journals-Worked-Example-Ledger.xlsx')

"""Reviewed, collision-safe salary and PF ledgers; never reclassifies old postings."""
import copy
from . import core,foundation,ap

ROLES=(
 ('salary_expense','4521','Salaries and wages','Expense','Employee benefits'),
 ('employer_pf_expense','4522','Employer PF contributions','Expense','Employee benefits'),
 ('salary_payable','2310','Salaries payable','Liability','Other liabilities'),
 ('employee_pf_payable','2311','Employee PF deductions payable','Liability','Other liabilities'),
 ('employer_pf_payable','2312','Employer PF contributions payable','Liability','Other liabilities'))

def eligible(s,role):
    _,_,_,kind,group=next(r for r in ROLES if r[0]==role)
    return [a for a in s['accounts'] if a['kind']==kind and s['account_details'][a['code']]['group']==group and s['account_details'][a['code']].get('active',True)]

def choices(s):
    mapping=s['settings'].get('payroll_ledgers',{});result={}
    for role,preferred,name,kind,group in ROLES:
        if role in mapping:result[role]=mapping[role]
        else:
            matches=[a['code'] for a in eligible(s,role) if a['name'].casefold()==name.casefold()]
            result[role]=matches[0] if len(matches)==1 else 'NEW'
    return result

def plan(s,selection=None):
    selection=choices(s) if selection is None else selection
    if set(selection)!={r[0] for r in ROLES}:raise ValueError('Review all five salary/PF ledger roles.')
    used={a['code'] for a in s['accounts']};selected=set();rows=[]
    for role,preferred,name,kind,group in ROLES:
        code=selection[role];create=code=='NEW'
        if create:
            candidates=[preferred,*map(str,range(4900,5000) if kind=='Expense' else range(2390,2400)),*map(str,range(4500,5000) if kind=='Expense' else range(2301,2400))]
            code=next((c for c in candidates if c not in used and c not in selected),None)
            if not code:raise ValueError('No free payroll ledger code remains; review your chart of accounts.')
        else:
            account=next((a for a in eligible(s,role) if a['code']==code),None)
            if not account:raise ValueError('Select an active '+kind+' / '+group+' ledger for '+name+'.')
            name=account['name']
        if code in selected:raise ValueError('Salary, employer PF and each payable need separate ledger accounts.')
        selected.add(code);rows.append(dict(role=role,code=code,name=name,kind=kind,group=group,create=create))
    return rows

@ap.atomic
def setup(s,selection,basis,confirmed=False):
    if not confirmed or not str(basis).strip():raise ValueError('Confirm the separate ledger roles and enter the setup review basis.')
    rows=plan(s,selection)
    for r in rows:
        if r['create']:foundation.save_account(s,r['code'],r['name'],r['kind'],r['group'],'Operating',True,'Reviewed payroll role: '+r['name']+'. PF amounts come from approved payroll, not an assumed rate.')
    s['settings']['payroll_ledgers']={r['role']:r['code'] for r in rows};core.add_audit(s,'PAYROLL_LEDGERS_CONFIGURED',dict(ledgers=rows,basis=str(basis).strip(),coverage='Account setup only; no entries or historical reclassification'))
    return rows

def salary_ledger(s,branch=None,on=None):
    mapping=s['settings'].get('payroll_ledgers',{})
    if not mapping:return '4520'
    code=mapping.get('salary_expense')
    if code not in {a['code'] for a in eligible(s,'salary_expense')}:raise ValueError('Review the configured active salary expense ledger in salary/PF setup.')
    payable=mapping.get('salary_payable')
    if branch and on and payable and core.balances(s,on,branch).get(payable,0)<0:raise ValueError('A salary payable is already recorded. Review payroll and settle the correct liability using manual journal lines instead of expensing salary again.')
    return code

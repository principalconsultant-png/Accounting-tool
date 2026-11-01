"""Source-linked revenue, advances, bills, collections and cancellations.

One shared Patient A/C; optional package/receipt references are not patient
subledgers or ageing. Effective-dated GST treatment is reviewed per service.
"""
import copy
from functools import wraps
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import uuid
from . import core, foundation, gst, tax, fixed_assets as fa, history

KINDS=('Advance','Direct receipt','Bill','Earn advance','Refund advance','Collect bill','Cancel bill','Refund bill')


def records(s):return s.get('service_revenue',[])
def atomic(fn):
    @wraps(fn)
    def run(s,*a,**k):
        c=copy.deepcopy(s);r=fn(c,*a,**k);check(c);s.clear();s.update(c);return copy.deepcopy(r)
    return run

def get(s,key):
    r=next((r for r in records(s) if r['id']==key),None)
    if not r:raise ValueError('Select a service source record.')
    return r

def active(s,r,on='9999-12-31',reversal=None):
    n=fa.family(s,r['voucher'],on)
    if reversal and reversal[1]<=on:
        root,sign=gst._roots(s)[reversal[0]]
        if root==r['voucher']:n-=sign
    return r['date']<=on and n==1

def children(s,r,on='9999-12-31',reversal=None):return [x for x in records(s) if x.get('source')==r['id'] and active(s,x,on,reversal)]
def remaining(s,r,on='9999-12-31'):return r['totals']['total']-sum(x['totals']['total'] for x in children(s,r,on) if x['kind'] in ('Earn advance','Refund advance','Cancel bill')) if active(s,r,on) else 0

def _payments(s,values,unit,n,debit):
    lines=[]
    for code,value in values.items():
        amount=core.money(value)
        a=next((a for a in s['accounts'] if a['code']==code),None)
        if not a or a['kind']!='Asset' or s['account_details'][code]['group'] not in ('Cash and bank','Payment clearing') or code in s.get('foreign_accounts',{}) or amount<0:raise ValueError('Select INR cash/bank/payment clearing and nonnegative actual payment amounts.')
        if amount:lines.append(dict(account=code,branch=unit,debit=amount if debit else 0,credit=0 if debit else amount))
    if sum(l['debit']+l['credit'] for l in lines)!=n:raise ValueError('Split payments must equal the gross receipt/refund.')
    return lines

def _line(code,unit,n,dr):return dict(account=code,branch=unit,debit=n if dr else 0,credit=0 if dr else n)

def _allocated(s,source,n,kinds,on):
    used=[x for x in children(s,source,on) if x['kind'] in kinds];prior=sum(x['totals']['total'] for x in used);total=source['totals']['total']
    if n<=0 or n+prior>total:raise ValueError('Amount exceeds the remaining source capacity.')
    # Cumulative component rounding gives the exact final original tax paise.
    result={'total':n};previous={k:sum(x['totals'][k] for x in used) for k in ('cgst','sgst','igst')}
    for k in previous:
        target=int((Decimal(source['totals'][k])*(prior+n)/total).quantize(Decimal(1),rounding=ROUND_HALF_UP))
        result[k]=target-previous[k]
    result['base']=n-sum(result[k] for k in previous)
    if any(v<0 for v in result.values()):raise ValueError('Source rounding requires reviewing a larger remaining allocation.')
    return result

def _gst_record(s,r,original=None):
    d=dict(id=str(uuid.uuid4()),kind='Sale',date=r['date'],branch=r['branch'],registration=r['registration'],place_of_supply=r['place_of_supply'],counterparty_gstin='',reference=r['reference'],rule=copy.deepcopy(r['rule']),account='2300' if r['kind']=='Advance' else r['account'],counter_account=r.get('counter',s['patient_control']),inclusive=r.get('inclusive',True),itc='Not applicable',narration=r['basis'],totals=copy.deepcopy(r['totals']),lines=copy.deepcopy(r['lines']),voucher_id=r['voucher'],document_type='Invoice',service_revenue_id=r['id'],revenue_stage=r['kind'])
    if original:
        d.update(document_type='Credit note',document_sign=-1,original_document_id=original['id'],original_voucher_id=original['voucher_id'],original_reference=original['reference'])
    s['gst_documents'].append(d);r['gst_document']=d['id']


@atomic
def post(s,kind,v):
    if kind not in KINDS or v.get('reviewed') is not True or not str(v.get('basis','')).strip():raise ValueError('Select the service action and review the actual service, source and tax basis.')
    on=tax.day(v.get('date',''));ref=str(v.get('reference','')).strip();unit=v.get('branch');basis=v['basis'].strip()
    if not ref or unit not in foundation.branches(s,True):raise ValueError('Enter reference and active operating unit.')
    if any(r['branch']==unit and core.financial_year(r['date'])==core.financial_year(on) and gst._reference(r['reference'])==gst._reference(ref) for r in records(s)):raise ValueError('This service reference already exists in this branch/year; use an explicit correction reference.')
    r=dict(id=str(uuid.uuid4()),kind=kind,date=on,branch=unit,reference=ref,basis=basis,package=str(v.get('package','')).strip(),source=v.get('source',''))
    if any(d['kind']=='Sale' and d['branch']==unit and core.financial_year(d['date'])==core.financial_year(on) and gst._reference(d['reference'])==gst._reference(ref) for d in s['gst_documents']):raise ValueError('This reference already belongs to a GST sale source; link the existing service source instead of reposting.')
    original=None;source=None;lines=[]
    if kind in ('Advance','Direct receipt','Bill'):
        account=v.get('account','');fa._ledger(s,account,'Revenue')
        rule=tax.resolve_rule(s,v.get('rule_key',''),on)
        if rule['family']!='GST' or not rule['reviewed'] or rule['party_category']!='Any' or rule['treatment']=='Zero rated':raise ValueError('Use a reviewed domestic GST service rule; export/SEZ is outside this workflow.')
        if rule['ledger_codes'] and account not in rule['ledger_codes']:raise ValueError('This service ledger is not covered by the selected rule.')
        registration=v.get('registration','').strip().upper();pos=v.get('place_of_supply','')
        if rule['treatment']=='Taxable':
            planned=gst.plan(s,dict(kind='Sale',date=on,branch=unit,reference=ref,registration=registration,place_of_supply=pos,amount=v.get('amount'),inclusive=v.get('inclusive',False),rule_key=rule['key'],account=account,counter_account=s['patient_control'],narration=basis))
            totals=planned['totals']
        else:
            if Decimal(rule['rate'])!=0:raise ValueError('Non-taxable/exempt service rules must have a reviewed zero rate.')
            if registration:gst._gstin(registration)
            n=core.money(v.get('amount',''))
            if n<=0:raise ValueError('Enter a positive service amount.')
            totals=dict(base=n,cgst=0,sgst=0,igst=0,total=n)
        r.update(account=account,rule=copy.deepcopy(rule),registration=registration,place_of_supply=pos,totals=totals,inclusive=v.get('inclusive',False))
        lines=[_line(s['patient_control'],unit,totals['total'],True)] if kind=='Bill' else _payments(s,v.get('payments',{}),unit,totals['total'],True)
        lines.append(_line('2300' if kind=='Advance' else account,unit,totals['base'],False))
        lines.extend(_line(code,unit,totals[key],False) for code,key in zip(gst.OUTPUT,('cgst','sgst','igst')) if totals[key])
    else:
        source=get(s,v.get('source',''))
        if source['branch']!=unit or on<source['date'] or not active(s,source,on):raise ValueError('Use the same branch and an active original source on/before this date.')
        expected='Advance' if kind in ('Earn advance','Refund advance') else 'Bill'
        if source['kind']!=expected:raise ValueError('This action requires an original '+expected+' source.')
        n=core.money(v.get('amount',''))
        totals=_allocated(s,source,n,('Earn advance','Refund advance') if expected=='Advance' else ('Cancel bill',) if kind=='Cancel bill' else ('Collect bill',) if kind=='Collect bill' else ('Refund bill',),on)
        if kind in ('Collect bill','Refund bill'):totals=dict(base=n,cgst=0,sgst=0,igst=0,total=n)
        r.update(account=source['account'],rule=copy.deepcopy(source['rule']),registration=source['registration'],place_of_supply=source['place_of_supply'],totals=totals,package=source['package'])
        original=next((d for d in s['gst_documents'] if d['id']==source.get('gst_document')),None)
        if kind=='Earn advance':
            current=tax.resolve_rule(s,source['rule']['key'],on)
            if any(current[k]!=source['rule'][k] for k in ('rate','treatment','hsn_sac')):raise ValueError('Service tax treatment changed since the advance. Review/correct the advance tax before earning; no historical rate is silently replaced.')
            lines=[_line('2300',unit,totals['base'],True),_line(source['account'],unit,totals['base'],False)]
        elif kind in ('Refund advance','Cancel bill'):
            lines=[_line('2300' if expected=='Advance' else source['account'],unit,totals['base'],True)]
            lines.extend(_line(code,unit,totals[key],True) for code,key in zip(gst.OUTPUT,('cgst','sgst','igst')) if totals[key])
            lines+=_payments(s,v.get('payments',{}),unit,n,False) if kind=='Refund advance' else [_line(s['patient_control'],unit,n,False)]
        else:
            lines=_payments(s,v.get('payments',{}),unit,n,kind=='Collect bill')+[_line(s['patient_control'],unit,n,kind=='Refund bill')]
    r['lines']=lines;r['voucher']=core.post(s,on,kind+' '+ref+': '+basis,lines,metadata={'reference':ref})['id']
    records(s).append(r)
    has_tax=any(r['totals'][k] for k in ('cgst','sgst','igst'))
    if kind in ('Bill','Direct receipt') or kind=='Advance' and has_tax or kind=='Earn advance' and not original:_gst_record(s,r)
    elif kind in ('Refund advance','Cancel bill') and original:_gst_record(s,r,original)
    core.add_audit(s,'SERVICE_REVENUE_RECORDED',copy.deepcopy(r));return r


def check(s,reversal=None):
    rs=records(s)
    if not rs:return
    roots=gst._roots(s);relevant={r['voucher'] for r in rs}
    if reversal and roots[reversal[0]][0] not in relevant:return
    days={r['date'] for r in rs}|{v['date'] for v in s['vouchers'] if roots[v['id']][0] in relevant}
    if reversal:days.add(reversal[1])
    for on in sorted(days):
        for source in rs:
            if source['kind'] not in ('Advance','Bill'):continue
            cs=children(s,source,on,reversal)
            if cs and not active(s,source,on,reversal):raise ValueError('Reverse dependent earning, refund, cancellation or collection before the source.')
            used=lambda kinds:sum(x['totals']['total'] for x in cs if x['kind'] in kinds)
            n=source['totals']['total'];spent=used(('Earn advance','Refund advance')) if source['kind']=='Advance' else used(('Cancel bill',))
            collected=used(('Collect bill',));refunded=used(('Refund bill',))
            if spent>n or collected>n or refunded>max(0,collected+spent-n):raise ValueError('Source capacity would be exceeded, including future allocations.')
            # Collections cannot be posted after a cancellation has reduced the unpaid amount.
            ordered=sorted(cs,key=lambda x:(x['date'],rs.index(x)));balance=n;paid=returned=0
            for x in ordered:
                k=x['kind'];amount=x['totals']['total']
                if k=='Cancel bill':balance-=amount
                elif k=='Collect bill':
                    if amount>max(0,balance-paid+returned):raise ValueError('Collect only the bill balance outstanding at that date.')
                    paid+=amount
                elif k=='Refund bill':returned+=amount


def validate_reversal(s,vid,on):check(s,(vid,on))


def report(s,start,end,branch='ALL'):
    tax.day(start);tax.day(end)
    if start>end or branch!='ALL' and branch not in foundation.branches(s):raise ValueError('Select a valid period/unit.')
    rows=[];expected={};proof=[]
    for r in records(s):
        if r['date']>end or branch not in ('ALL',r['branch']):continue
        islive=active(s,r,end)
        if islive:
            for l in r['lines']:
                if l['account'] in ('2300',s['patient_control']):expected[(r['branch'],l['account'])]=expected.get((r['branch'],l['account']),0)+l['debit']-l['credit']
        rows.append([r['date'],r['reference'],r['kind'],r['branch'],r['package'],r['id'],r['source'],r['account'],r['totals']['base'] if islive else 0,r['totals']['total'] if islive else 0,remaining(s,r,end) if r['kind']=='Advance' else '',r['voucher'],'Active' if islive else 'Reversed',r['rule']['key'],r['basis'],(r['totals']['total']-sum(x['totals']['total']*(1 if x['kind'] in ('Cancel bill','Collect bill') else -1 if x['kind']=='Refund bill' else 0) for x in children(s,r,end))) if r['kind']=='Bill' and islive else None])
    for unit in foundation.branches(s):
        if branch not in ('ALL',unit):continue
        balances=core.balances(s,end,unit)
        for code in ('2300',s['patient_control']):
            n=expected.get((unit,code),0);proof.append([unit,code,n,balances[code],balances[code]-n])
    return dict(start=start,end=end,branch=branch,rows=rows,proof=proof,ready=not any(r[-1] for r in proof))


def export(s,start,end,branch,path,kind):
    from . import financial_reports as fr
    r=report(s,start,end,branch);base=dict(entity=s['settings']['entity'],registration=copy.deepcopy(s['settings']['registration']),start=start,end=end,branch=branch,scope='All operating units' if branch=='ALL' else foundation.branches(s)[branch],prepared=datetime.now(history.INDIA).isoformat(),currency='INR',status='Reconciled' if r['ready'] else 'DRAFT: unallocated shared-control movements',controls={},note='Cumulative source positions as at '+end+'. Shared Patient A/C and advance control; no patient subledger or ageing. GST working base includes taxed service advances; accounting revenue is recognized only when earned. Actual tax applicability, service completion and cancellation documents require review.')
    rows=[[None if v=='' and i==10 else v for i,v in enumerate(row)] for row in r['rows']]
    packs=[dict(base,mode='Service revenue sources',columns=['Date','Reference','Action','Unit','Package ref','Source ID','Parent ID','Revenue account','Base INR','Gross INR','Unearned gross INR','Voucher','Status','GST rule','Basis','Bill outstanding Dr/(Cr) INR'],money_columns=[8,9,10,15],rows=rows),dict(base,mode='Revenue control reconciliation',columns=['Unit','Control','Source Dr/(Cr) INR','Ledger Dr/(Cr) INR','Difference INR'],money_columns=[2,3,4],rows=r['proof'])]
    if kind=='xlsx':fr.export_pack_xlsx(packs,path)
    elif kind=='pdf':fr.export_pdf(packs,path)
    else:raise ValueError('Choose Excel or PDF.')


@atomic
def link_existing(s,kind,values,voucher_id):
    if kind not in ('Advance','Bill','Direct receipt'):raise ValueError('Link an original advance, bill or earned receipt.')
    old=next((v for v in s['vouchers'] if v['id']==voucher_id and not v.get('reverses') and not v.get('closing')),None)
    if not old or fa.family(s,voucher_id)!=1 or old['date']!=values.get('date'):raise ValueError('Select a live original voucher on its exact source date.')
    if any(r['voucher']==voucher_id for r in records(s)):raise ValueError('This source is already registered.')
    simulated=copy.deepcopy(s);simulated['gst_documents']=[d for d in simulated['gst_documents'] if d['voucher_id']!=voucher_id];r=post(simulated,kind,values)
    def totals(lines):
        result={}
        for l in lines:
            key=(l['account'],l['branch']);result[key]=result.get(key,0)+l['debit']-l['credit']
        return {k:v for k,v in result.items() if v}
    if totals(old['lines'])!=totals(r['lines']):raise ValueError('Reviewed source lines must match the original voucher exactly; do not invent or duplicate opening balances.')
    r['voucher']=voucher_id;r['linked_existing']=True
    original_docs=[d for d in s['gst_documents'] if d['voucher_id']==voucher_id]
    proposed=[d for d in simulated['gst_documents'] if d.get('service_revenue_id')==r['id']]
    if original_docs:
        if len(original_docs)!=1 or not proposed or original_docs[0]['totals']!=r['totals'] or original_docs[0]['kind']!='Sale':raise ValueError('Existing GST source does not agree with this service review.')
        d=original_docs[0];d['service_revenue_id']=r['id'];r['gst_document']=d['id']
    else:
        for d in proposed:d['voucher_id']=voucher_id;s['gst_documents'].append(d)
    records(s).append(r);core.add_audit(s,'SERVICE_EXISTING_SOURCE_LINKED',copy.deepcopy(r));return r

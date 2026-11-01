"""Vendor invoices, accruals, dated settlement allocation and payment planning."""
import copy
from functools import wraps
from datetime import date,timedelta,datetime
import re
import uuid
from . import core,foundation,gst,tds,history


def data(s):return s.get('ap',dict(vendors=[],invoices=[],payments=[],schedules=[]))
def uid():return str(uuid.uuid4())
def day(value):
    if date.fromisoformat(value).isoformat()!=value:raise ValueError('Use an actual YYYY-MM-DD date.')
    return value
def positive(value):
    from .sales_import import amount
    n=amount(value,'Amount')
    if n<=0:raise ValueError('Enter a positive INR amount.')
    return n
def norm(value):return re.sub(r'[^a-z0-9]','',str(value).casefold())
def reviewed(v):
    if v.get('reviewed') is not True or not str(v.get('basis','')).strip():raise ValueError('Review the source, tax treatment, posting and payment evidence, and enter a basis.')
def atomic(fn):
    @wraps(fn)
    def call(s,*args,**kwargs):
        core.verify_audit(s);c=copy.deepcopy(s);c.setdefault('ap',dict(vendors=[],invoices=[],payments=[],schedules=[]));r=fn(c,*args,**kwargs);check(c);s.clear();s.update(c);return copy.deepcopy(r)
    return call

def vendor(s,key):
    v=next((v for v in data(s)['vendors'] if v['id']==key),None)
    if not v:raise ValueError('Select a saved vendor.')
    return v

def invoice(s,key):
    v=next((v for v in data(s)['invoices'] if v['id']==key),None)
    if not v:raise ValueError('Select a saved AP invoice.')
    return v

def credit_days(value):
    try:n=int(str(value))
    except ValueError:raise ValueError('Credit period must be whole calendar days.') from None
    if str(n)!=str(value).strip() or not 0<=n<=3650:raise ValueError('Credit period must be 0–3650 whole calendar days.')
    return n

@atomic
def save_vendor(s,values):
    name=str(values.get('name','')).strip();days=credit_days(values.get('credit_days','0'))
    if not name or not norm(name):raise ValueError('Enter the vendor legal/source name.')
    if any(norm(v['name'])==norm(name) for v in data(s)['vendors']):raise ValueError('This vendor is already present; use the existing vendor to prevent duplicate invoices.')
    v=dict(id=uid(),name=name,credit_days=days,reference=str(values.get('reference','')).strip());data(s)['vendors'].append(v);core.add_audit(s,'AP_VENDOR_CREATED',v);return v


def position(s,r,on='9999-12-31',net=None):
    net=tds._net(s,on) if net is None else net
    amount=r['amount']*net.get(r['voucher'],0)
    paid=sum(i['amount']*net.get(p['voucher'],0) for p in data(s)['payments'] for i in p['items'] if i['invoice']==r['id'])
    return dict(amount=amount,paid=paid,remaining=amount-paid,status='Cancelled' if amount==0 else 'Paid' if paid==amount else 'Part paid' if paid else 'Unpaid')


def schedule(s,r,on='9999-12-31'):
    rows=[(x['effective'],i,x) for i,x in enumerate(data(s)['schedules']) if x['invoice']==r['id'] and x['effective']<=on]
    return max(rows,key=lambda p:p[:2])[2]['payment_date'] if rows else r['payment_date']

@atomic
def enter_invoice(s,v):
    reviewed(v);supplier=vendor(s,v['vendor']);branch=v['branch'];ref=str(v.get('reference','')).strip()
    if branch not in foundation.branches(s,True) or not ref or not norm(ref):raise ValueError('Select an active unit and enter the vendor invoice number.')
    invdate=day(v['invoice_date']);received=day(v['received_date']);posted=day(v['accounting_date']);days=credit_days(v['credit_days'])
    if invdate>received:raise ValueError('Invoice receipt cannot precede its invoice date.')
    if posted<invdate:raise ValueError('Accounting date cannot precede the invoice date.')
    if v.get('due_basis') not in ('Invoice date','Receipt date'):raise ValueError('Review whether credit days start at invoice date or receipt date.')
    due=(date.fromisoformat(invdate if v['due_basis']=='Invoice date' else received)+timedelta(days=days)).isoformat();planned=day(v.get('payment_date') or due)
    amount=positive(v['amount']);payable=v.get('payable','2000');accounts={a['code']:a for a in s['accounts']}
    if payable not in accounts or accounts[payable]['kind']!='Liability' or s['account_details'][payable]['group']!='Trade payables' or not s['account_details'][payable]['active']:raise ValueError('Select an active Trade payables liability ledger.')
    if any(r['vendor']==supplier['id'] and norm(r['reference'])==norm(ref) and core.financial_year(r['invoice_date'])==core.financial_year(invdate) for r in data(s)['invoices']):raise ValueError('Vendor invoice number already registered in this fiscal year, including cancelled invoices. Review the original instead of entering twice.')
    source=v.get('existing_voucher','').strip();allocations=[]
    if source:
        original=next((x for x in s['vouchers'] if x['id']==source),None)
        if not original or original.get('reverses') or original.get('closing') or original.get('opening') or original['date']!=posted or tds._net(s).get(source)!=1:raise ValueError('Link an active original accrual voucher on the exact accounting date, without reposting it.')
        capacity=-sum(l['debit']-l['credit'] for l in original['lines'] if l['account']==payable and l['branch']==branch)
        used=sum(r['amount'] for r in data(s)['invoices'] if r['voucher']==source and r['payable']==payable and r['branch']==branch)
        if amount>capacity-used:raise ValueError('Invoice allocation exceeds the unregistered vendor-payable credit of this existing source.')
        if any(s['account_details'][l['account']]['group']=='Cash and bank' for l in original['lines']):raise ValueError('An already-paid source cannot be registered as an unpaid AP accrual. Link an unpaid accrual, then record settlement.')
    else:
        if posted<received:raise ValueError('For a new receipt accrual use receipt date or a later reviewed accounting date. Earlier accrued sources can be linked explicitly.')
        if v.get('tax_treatment')!='No separate GST/TDS; reviewed':raise ValueError('For GST/TDS or CWIP accruals, create/review the source in its dedicated workflow, then link that existing voucher here once. No tax was guessed.')
        for i in v.get('allocations',[]):
            code=i.get('account');n=positive(i.get('amount'))
            if code not in accounts or accounts[code]['kind'] not in ('Asset','Expense') or s['account_details'][code]['group'] in ('Cash and bank','Payment clearing','Patient control','GST input','CWIP','Accumulated depreciation') or code in ('1130',) or not s['account_details'][code]['active']:raise ValueError('New AP allocation must be an active genuine cost/asset ledger. GST, CWIP and special controls require their source workflow.')
            allocations.append(dict(account=code,branch=branch,debit=n,credit=0))
        if sum(l['debit'] for l in allocations)!=amount:raise ValueError('Cost allocations must equal the net amount payable; review all gross/tax components before posting.')
        source=core.post(s,posted,'Vendor invoice '+ref+' | '+supplier['name'],allocations+[dict(account=payable,branch=branch,debit=0,credit=amount)],metadata={'type':'Journal','reference':ref,'payee':supplier['name']})['id']
    r=dict(id=uid(),vendor=supplier['id'],vendor_name=supplier['name'],reference=ref,invoice_date=invdate,received_date=received,accounting_date=posted,credit_days=days,due_basis=v['due_basis'],due_date=due,payment_date=planned,branch=branch,amount=amount,payable=payable,voucher=source,mode='Linked source' if v.get('existing_voucher') else 'New accrual',basis=v['basis'].strip(),allocations=allocations)
    data(s)['invoices'].append(r);core.add_audit(s,'AP_INVOICE_REGISTERED',r);return r

@atomic
def extend(s,key,effective,payment_date,reason,confirmed=False):
    r=invoice(s,key);day(effective);day(payment_date)
    if not confirmed or not reason.strip():raise ValueError('Review and record the agreed payment extension reason.')
    if effective<max([r['accounting_date']]+[x['effective'] for x in data(s)['schedules'] if x['invoice']==key]):raise ValueError('Extension history must be chronological and on/after the accrual date.')
    if position(s,r,effective)['remaining']<=0:raise ValueError('Only an outstanding invoice can be extended.')
    if payment_date<=schedule(s,r,effective) or payment_date<effective:raise ValueError('Choose a later scheduled payment date, on/after the extension effective date.')
    row=dict(id=uid(),invoice=key,effective=effective,old_date=schedule(s,r,effective),payment_date=payment_date,reason=reason.strip());data(s)['schedules'].append(row);core.add_audit(s,'AP_PAYMENT_DATE_EXTENDED',row);return row

@atomic
def pay(s,v):
    reviewed(v);on=day(v['date']);ref=str(v.get('reference','')).strip();bank=v['bank_account'];items=v.get('items',[])
    if not ref or not items or len({i['invoice'] for i in items})!=len(items):raise ValueError('Select unique invoice(s) and enter the actual bank/payment reference.')
    if s['account_details'].get(bank,{}).get('group')!='Cash and bank' or bank in s.get('foreign_accounts',{}) or not s['account_details'][bank]['active']:raise ValueError('Choose an active INR cash/bank ledger; collection clearing and foreign-currency accounts are not payment sources.')
    if any(norm(p['reference'])==norm(ref) and p['bank_account']==bank and core.financial_year(p['date'])==core.financial_year(on) for p in data(s)['payments']):raise ValueError('This payment reference is already recorded for this bank/fiscal year. Review the existing payment or use a new correction reference.')
    lines=[];clean=[];units=set()
    for item in items:
        r=invoice(s,item['invoice']);n=positive(item['amount']);units.add(r['branch'])
        if n>position(s,r,on)['remaining'] or on<r['accounting_date']:raise ValueError('Payment exceeds the dated outstanding invoice or precedes accrual.')
        if r['branch'] not in foundation.branches(s,True):raise ValueError('Reactivate the invoice unit before payment.')
        lines.append(dict(account=r['payable'],branch=r['branch'],debit=n,credit=0));clean.append(dict(invoice=r['id'],amount=n))
    if len(units)!=1:raise ValueError('Select invoices from one operating unit per payment. Record actual inter-branch funding separately.')
    total=sum(i['amount'] for i in clean);unit=next(iter(units));lines.append(dict(account=bank,branch=unit,debit=0,credit=total))
    row=dict(id=uid(),date=on,reference=ref,bank_account=bank,branch=unit,items=clean,basis=v['basis'].strip())
    existing=str(v.get('existing_voucher','')).strip()
    if existing:
        original=next((x for x in s['vouchers'] if x['id']==existing),None)
        def totals(lines):
            result={}
            for l in lines:k=(l['account'],l['branch']);result[k]=result.get(k,0)+l['debit']-l['credit']
            return {k:n for k,n in result.items() if n}
        if not original or original.get('reverses') or original.get('opening') or original.get('closing') or original['date']!=on or tds._net(s).get(existing)!=1 or totals(original['lines'])!=totals(lines):raise ValueError('Existing payment must exactly match the selected invoice allocations, date, cash/bank and unit.')
        if any(p['voucher']==existing for p in data(s)['payments']):raise ValueError('This existing payment is already allocated in AP.')
        row['voucher']=existing;row['mode']='Linked existing payment'
    else:
        row['voucher']=core.post(s,on,'AP payment '+ref,lines,metadata={'type':'Payment','reference':ref,'bank_account':bank,'payee':'; '.join(sorted({invoice(s,i['invoice'])['vendor_name'] for i in clean}))})['id'];row['mode']='New payment'
    data(s)['payments'].append(row);core.add_audit(s,'AP_INVOICES_PAID',row);return row


def check(s,reversal=None):
    d=data(s);byid={v['id']:v for v in s['vouchers']};roots=gst._roots(s)
    invoices=d['invoices'];payments=d['payments'];byinvoice={r['id']:r for r in invoices}
    if len(byinvoice)!=len(invoices):raise ValueError('Duplicate AP invoice identity.')
    capacities={};invoice_roots={};payment_roots={}
    for r in invoices:
        if r['voucher'] not in byid or byid[r['voucher']].get('reverses') or r['vendor'] not in {v['id'] for v in d['vendors']}:raise ValueError('AP invoice source/vendor is missing or is a reversal.')
        if type(r['amount'])!=int or r['amount']<=0:raise ValueError('Invalid AP invoice amount.')
        k=(r['voucher'],r['branch'],r['payable']);capacities[k]=capacities.get(k,0)+r['amount'];invoice_roots.setdefault(r['voucher'],[]).append(r)
    for (vid,unit,code),n in capacities.items():
        if n>-sum(l['debit']-l['credit'] for l in byid[vid]['lines'] if l['account']==code and l['branch']==unit):raise ValueError('AP source allocations exceed original payable credit.')
    for p in payments:
        if p['voucher'] not in byid or byid[p['voucher']].get('reverses'):raise ValueError('AP payment source is missing.')
        for i in p['items']:
            if i['invoice'] not in byinvoice or type(i['amount'])!=int or i['amount']<=0:raise ValueError('AP payment references an invalid invoice/amount.')
        payment_roots.setdefault(p['voucher'],[]).append(p)
    relevant=set(invoice_roots)|set(payment_roots);events={}
    for v in s['vouchers']:
        root,sign=roots[v['id']]
        if root in relevant:events.setdefault(v['date'],[]).append((root,sign))
    if reversal:
        root,sign=roots[reversal[0]]
        if root in relevant:events.setdefault(reversal[1],[]).append((root,-sign))
    outstanding={k:0 for k in byinvoice};paid={k:0 for k in byinvoice}
    for on,changes in sorted(events.items()):
        touched=set()
        for root,delta in changes:
            for r in invoice_roots.get(root,[]):outstanding[r['id']]+=r['amount']*delta;touched.add(r['id'])
            for p in payment_roots.get(root,[]):
                for i in p['items']:outstanding[i['invoice']]-=i['amount']*delta;paid[i['invoice']]+=i['amount']*delta;touched.add(i['invoice'])
        if any(outstanding[k]<0 or paid[k]<0 for k in touched):raise ValueError('AP allocations exceed dated source capacity, including future/reversed payments. Reverse dependent payments before cancelling an invoice.')
    return True


def validate_reversal(s,vid,on):
    if data(s)['invoices']:check(s,(vid,on))


def register(s,on,branch='ALL'):
    core.verify_audit(s);day(on)
    if branch!='ALL' and branch not in foundation.branches(s):raise ValueError('Select a valid unit.')
    net=tds._net(s,on);rows=[]
    for r in data(s)['invoices']:
        if r['accounting_date']>on or branch!='ALL' and r['branch']!=branch:continue
        x=position(s,r,on,net);scheduled=schedule(s,r,on);rows.append(dict(r,**x,scheduled_date=scheduled,overdue=x['remaining']>0 and scheduled<=on))
    return rows


def forecast(s,asof,start,end,branch='ALL'):
    day(asof);day(start);day(end)
    if start>end or start<asof:raise ValueError('Forecast starts on/after its as-of date; end must not precede start.')
    rows=[]
    for r in register(s,asof,branch):
        if r['remaining']<=0:continue
        bucket=max(r['scheduled_date'],start)
        if bucket<=end:rows.append(dict(invoice=r['id'],vendor=r['vendor_name'],reference=r['reference'],branch=r['branch'],due_date=r['due_date'],scheduled_date=r['scheduled_date'],forecast_date=bucket,amount=-r['remaining'],status='Overdue / carried into start' if r['scheduled_date']<start else 'Scheduled',voucher=r['voucher']))
    return rows


def snapshots(s,start,end,branch='ALL'):
    from . import financial_reports as f
    base=f.snapshot(s,'Trial balance',start,end,branch);rows=register(s,end,branch);packs=[]
    def add(mode,columns,money,content,controls={}):
        p=copy.deepcopy(base);p.update(mode=mode,columns=columns,money_columns=money,rows=content,controls=controls,note='AP source register as at '+end+'. Actual payment vouchers settle liabilities; scheduled dates are planning only. Tax/source journals must be reviewed before linking. Unregistered payable differences stay visible.');packs.append(p)
    add('AP vendor invoice register',['ID','Vendor','Invoice','Unit','Invoice date','Receipt date','Accrual date','Credit days','Contractual due','Scheduled payment','Payable INR','Paid INR','Outstanding INR','Status','Accrual voucher'],[10,11,12],[[r['id'],r['vendor_name'],r['reference'],r['branch'],r['invoice_date'],r['received_date'],r['accounting_date'],r['credit_days'],r['due_date'],r['scheduled_date'],r['amount'],r['paid'],r['remaining'],r['status'],r['voucher']] for r in rows])
    paymentrows=[];net=tds._net(s,end)
    for p in data(s)['payments']:
        if start<=p['date']<=end and (branch=='ALL' or p['branch']==branch):
            for i in p['items']:paymentrows.append([p['date'],p['reference'],invoice(s,i['invoice'])['vendor_name'],invoice(s,i['invoice'])['reference'],p['branch'],p['bank_account'],i['amount']*net.get(p['voucher'],0),p['voucher'],'Active' if net.get(p['voucher'])==1 else 'Reversed',p['basis']])
    add('AP payment history',['Date','Payment reference','Vendor','Invoice','Unit','Cash bank','Paid INR','Voucher','Status','Evidence'],[6],paymentrows)
    expected={};proof=[]
    for r in rows:k=(r['branch'],r['payable']);expected[k]=expected.get(k,0)+r['remaining']
    for unit in foundation.branches(s):
        if branch!='ALL' and unit!=branch:continue
        balances=core.balances(s,end,unit)
        for a in s['accounts']:
            if s['account_details'][a['code']]['group']=='Trade payables':
                n=expected.get((unit,a['code']),0);actual=-balances[a['code']];proof.append([unit,a['code'],n,actual,actual-n])
    add('AP payable reconciliation',['Unit','Payable ledger','Registered outstanding INR','Ledger credit INR','Unregistered difference INR'],[2,3,4],proof,{'Absolute unregistered difference':sum(abs(r[-1]) for r in proof)})
    add('AP payment schedule history',['Vendor','Invoice','Effective','Old payment date','Extended to','Reason'],[],[[invoice(s,x['invoice'])['vendor_name'],invoice(s,x['invoice'])['reference'],x['effective'],x['old_date'],x['payment_date'],x['reason']] for x in data(s)['schedules'] if x['effective']<=end and (branch=='ALL' or invoice(s,x['invoice'])['branch']==branch)])
    return packs


def forecast_snapshot(s,asof,start,end,branch='ALL'):
    from . import financial_reports as f
    rows=forecast(s,asof,start,end,branch);p=f.snapshot(s,'Trial balance',start,end,branch)
    p.update(mode='AP scheduled cash outflow',columns=['Vendor','Invoice','Unit','Contractual due','Scheduled date','Forecast bucket','Forecast outflow INR','Status','Accrual voucher'],money_columns=[6],rows=[[r['vendor'],r['reference'],r['branch'],r['due_date'],r['scheduled_date'],r['forecast_date'],r['amount'],r['status'],r['voucher']] for r in rows],controls={'Total scheduled AP outflow':sum(r['amount'] for r in rows)},note='PLANNING ONLY. Outstanding registered AP at '+asof+'; overdue amounts carried into forecast start. Existing actual cash-flow statements exclude this schedule. No assumed receipts, unregistered bills or automatic bank payments. Future-dated payments after as-of remain due in this as-of plan until their actual accounting date.')
    p['rows'].append(['TOTAL','','','','','',sum(r['amount'] for r in rows),'Planning only',''])
    return p


def payment_flows(s,vid,policy,branch,sign):
    """Use reviewed source categories when provable; ambiguous linked sources stay Review."""
    payment=next((p for p in data(s)['payments'] if p['voucher']==vid and (branch=='ALL' or p['branch']==branch)),None)
    if not payment:return None
    result=[]
    for item in payment['items']:
        r=invoice(s,item['invoice']);weights={}
        if r['allocations']:
            for l in r['allocations']:
                category=policy['mapping'].get(l['account'],'Review');weights[category]=weights.get(category,0)+l['debit']
        else:
            v=next(v for v in s['vouchers'] if v['id']==r['voucher'])
            cats={policy['mapping'].get(l['account'],'Review') for l in v['lines'] if l['branch']==r['branch'] and l['account']!=r['payable']}
            if len(cats)!=1:return None
            weights[next(iter(cats))]=r['amount']
        if 'Review' in weights:return None
        total=sum(weights.values());split={c:item['amount']*n//total for c,n in weights.items()};left=item['amount']-sum(split.values())
        for c in sorted(weights,key=lambda c:(-(item['amount']*weights[c]%total),c))[:left]:split[c]+=1
        result.extend(dict(category=c,amount=-n*sign,label='AP '+r['vendor_name']+' / '+r['reference']) for c,n in split.items() if n)
    return result

@atomic
def cancel_invoice(s,key,on,reason,confirmed=False):
    r=invoice(s,key)
    if not confirmed or not reason.strip():raise ValueError('Review invoice cancellation and enter the source reason.')
    if sum(x['voucher']==r['voucher'] for x in data(s)['invoices'])!=1:raise ValueError('This accrual supports multiple registered invoices. Use the original source correction workflow; cancelling one row cannot reverse the whole shared source.')
    v=core.reverse(s,r['voucher'],day(on));core.add_audit(s,'AP_INVOICE_CANCELLED',dict(invoice=key,voucher=v['id'],reason=reason.strip()));return v

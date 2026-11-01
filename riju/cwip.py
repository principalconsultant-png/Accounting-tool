"""Reviewed project CWIP, source allocations, retention and commissioning.

Project amounts are integer paise. Budgets are optional planning figures; no
legal capitalization, tax eligibility or operating date is inferred.
"""
import copy
from functools import wraps
import json
from pathlib import Path
import uuid
from datetime import datetime
from . import core, foundation, fixed_assets as fa, gst, tds, history

CATEGORIES=('Civil','MEP','Architecture','Landscaping','Compliance')


def data(state):
    return state.get('cwip',{'projects':[], 'costs':[], 'events':[]})


def atomic(fn):
    @wraps(fn)
    def run(state,*args,**kwargs):
        candidate=copy.deepcopy(state)
        result=fn(candidate,*args,**kwargs)
        check(candidate)
        state.clear();state.update(candidate)
        return copy.deepcopy(result)
    return run


def review(basis,reviewed):
    if reviewed is not True or not str(basis).strip():raise ValueError('Review supporting sources and enter a capitalization/accounting basis.')
    return str(basis).strip()


def project(state,pid):
    p=next((p for p in data(state)['projects'] if p['id']==pid),None)
    if p is None:raise ValueError('Select a CWIP project.')
    return p


def cost(state,cid):
    c=next((c for c in data(state)['costs'] if c['id']==cid),None)
    if c is None:raise ValueError('Select a project cost source.')
    return c


def live(state,record,on='9999-12-31'):
    return record['date']<=on and fa.family(state,record['voucher'],on)==1


def ledger(state,code,kind,group=None):
    fa._ledger(state,code,kind,group)
    if not state['account_details'][code]['active']:raise ValueError('Select an active ledger.')


def _new_ledger(state,name,kind,group):
    lo,hi=foundation.KINDS[kind];used={a['code'] for a in state['accounts']}
    code=next((str(i) for i in range(lo,hi+1) if str(i) not in used),None)
    if code is None:raise ValueError('No unused account code available for this project.')
    foundation.save_account(state,code,name,kind,group,'Investing')
    return code


@atomic
def save_project(state,key,name,branch='VK',basis='',reviewed=False,ledgers=None,retention=None):
    basis=review(basis,reviewed);key=str(key).strip();name=str(name).strip()
    if not key or not name or branch not in foundation.branches(state,True):raise ValueError('Enter project key, name and active unit.')
    if any(p['key'].casefold()==key.casefold() for p in data(state)['projects']):raise ValueError('Project keys must be unique.')
    requested=ledgers or {}
    if set(requested)-set(CATEGORIES):raise ValueError('Unknown project ledger category.')
    used={code for other in data(state)['projects'] for code in [*other['ledgers'].values(),other['retention']]}
    mapping={}
    for category in CATEGORIES:
        code=requested.get(category) or _new_ledger(state,key+' / '+category+' CWIP','Asset','CWIP')
        ledger(state,code,'Asset','CWIP')
        if code in used or code in mapping.values():raise ValueError('Each category/project requires a separate CWIP ledger; historical accounts cannot be shared.')
        mapping[category]=code
    retention=retention or _new_ledger(state,key+' / retention','Liability','Retention')
    ledger(state,retention,'Liability','Retention')
    if retention in used:raise ValueError('Retention control already belongs to another project.')
    p=dict(id=str(uuid.uuid4()),key=key,name=name,branch=branch,basis=basis,ledgers=mapping,retention=retention,plans=[])
    data(state)['projects'].append(p);core.add_audit(state,'CWIP_PROJECT_CREATED',copy.deepcopy(p));return p


@atomic
def save_plan(state,pid,effective,budgets,milestones,basis,reviewed=False,name=None):
    p=project(state,pid);fa.day(effective);basis=review(basis,reviewed)
    if set(budgets)-set(CATEGORIES):raise ValueError('Unknown budget category.')
    parsed={k:None if budgets.get(k) in ('',None) else core.money(budgets[k]) for k in CATEGORIES}
    if any(v is not None and v<0 for v in parsed.values()):raise ValueError('Budgets cannot be negative; blank means unknown.')
    rows=[];keys=set()
    for m in milestones:
        key=str(m.get('key','')).strip();title=str(m.get('name','')).strip();due=fa.day(m.get('due',''));actual=m.get('completed','')
        if actual:fa.day(actual)
        if not key or not title or key.casefold() in keys:raise ValueError('Milestones need unique keys, names and target dates.')
        keys.add(key.casefold());rows.append(dict(key=key,name=title,due=due,completed=actual))
    if name is not None and not str(name).strip():raise ValueError('Project name is required.')
    r=dict(id=str(uuid.uuid4()),effective=effective,budgets=parsed,milestones=rows,basis=basis,name=str(name).strip() if name is not None else p['name'])
    p['plans'].append(r);core.add_audit(state,'CWIP_PLAN_REVISED',dict(project=pid,revision=copy.deepcopy(r)));return r


def plan(p,on):
    choices=[(r['effective'],i,r) for i,r in enumerate(p['plans']) if r['effective']<=on]
    return copy.deepcopy(max(choices,key=lambda x:x[:2])[2]) if choices else dict(budgets=dict.fromkeys(CATEGORIES),milestones=[],basis='Not supplied',name=p['name'])


def _source(state,vid):
    v=next((v for v in state['vouchers'] if v['id']==vid and not v.get('reverses') and not v.get('closing')),None)
    if not v or fa.family(state,vid)!=1:raise ValueError('Choose an active original source voucher.')
    return v


def _remaining(state,c,on='9999-12-31'):
    if not live(state,c,on):return 0
    used=sum(item['amount'] for e in data(state)['events'] if e['kind'] in ('Commission','Expense reclassification') and live(state,e,on) for item in e['items'] if item['cost']==c['id'])
    return c['capital']-used


@atomic
def record_cost(state,pid,values):
    p=project(state,pid);v=values;basis=review(v.get('basis',''),v.get('reviewed'));category=v.get('category');ref=str(v.get('reference','')).strip();on=fa.day(v.get('date',''))
    if category not in CATEGORIES or not ref:raise ValueError('Select a category and enter the supplier/source reference.')
    party=str(v.get('party','')).strip()
    if not party:raise ValueError('Enter a supplier/payee reference; individual supplier ledgers are optional.')
    if any(c['reference'].casefold()==ref.casefold() and c['party'].casefold()==party.casefold() and c['project']==pid and core.financial_year(c['date'])==core.financial_year(on) for c in data(state)['costs']):raise ValueError('Duplicate supplier/reference/project/year; use an explicit correction reference.')
    gross=core.money(v.get('gross',''));capital=core.money(v.get('capital',''));retention=core.money(v.get('retention','0'))
    if gross<=0 or not 0<=capital<=gross or not 0<=retention<=gross:raise ValueError('Enter positive gross, eligible capital within gross and valid retention.')
    expense=v.get('expense','4590');payable=v.get('payable','2000');cwip=p['ledgers'][category];unit=p['branch']
    ledger(state,cwip,'Asset','CWIP');ledger(state,payable,'Liability','Trade payables')
    if capital<gross:
        ledger(state,expense,'Expense')
        if state['account_details'][expense]['group'] in ('Depreciation','Income tax'):raise ValueError('Use a genuine operating/hospital expense ledger.')
    lines=[]
    if capital:lines.append(dict(account=cwip,branch=unit,debit=capital,credit=0))
    if gross>capital:lines.append(dict(account=expense,branch=unit,debit=gross-capital,credit=0))
    lines.append(dict(account=payable,branch=unit,debit=0,credit=gross))
    mode=v.get('mode','Post cost')
    if mode=='Post cost':
        source=core.post(state,on,'Project '+p['key']+' / '+ref+': '+basis,lines,metadata={'reference':ref})['id']
    elif mode=='Link existing':
        source=v.get('source','');sv=_source(state,source)
        if sv['date']!=on:raise ValueError('Use the original source date for linked costs.')
        # Allocate each debit and the payable credit once, across projects and categories.
        for code,required,credit in [(cwip,capital,False),(expense,gross-capital,False)]:
            if not required:continue
            capacity=sum((l['credit']-l['debit'] if credit else l['debit']-l['credit']) for l in sv['lines'] if l['branch']==unit and l['account']==code)
            used=sum((c['gross'] if credit else c['capital'] if c['cwip']==code else c['gross']-c['capital'] if c['expense']==code else 0) for c in data(state)['costs'] if c['voucher']==source and c['branch']==unit and (not credit or c['payable']==code))
            if required+used>capacity:raise ValueError('Cost exceeds unused source debit/payable capacity.')
    else:raise ValueError('Choose Post cost or Link existing.')
    c=dict(id=str(uuid.uuid4()),project=pid,category=category,reference=ref,party=party,date=on,gross=gross,capital=capital,expense=expense,payable=payable,cwip=cwip,branch=unit,voucher=source,basis=basis,mode=mode)
    data(state)['costs'].append(c)
    if retention:
        ledger(state,p['retention'],'Liability','Retention')
        rv=core.post(state,on,'Retention '+ref,fa._pair(payable,p['retention'],retention,unit))
        data(state)['events'].append(dict(id=str(uuid.uuid4()),kind='Retention held',date=on,project=pid,voucher=rv['id'],cost=c['id'],amount=retention,basis=basis,items=[]))
    core.add_audit(state,'CWIP_COST_REVIEWED',copy.deepcopy(c));return c


@atomic
def deduct_tds(state,cid,values):
    c=cost(state,cid);review(values.get('review_reason',''),values.get('confirmed'))
    v=dict(values,branch=c['branch'],source_voucher=c['voucher'],counter_account=c['payable'],gross=format_money(c['gross']),reference=values.get('reference') or c['reference'],account=c['cwip'])
    if fa.day(v.get('date',''))<c['date']:raise ValueError('TDS cannot precede its cost source.')
    if any(r.get('cwip_cost')==cid for r in state['tds_records'] if tds.active(state,r)):raise ValueError('This cost already has an active TDS treatment.')
    # B09 owns actual rate/threshold snapshots, challans and allocation controls.
    kind=values.get('kind','Existing payable')
    if kind not in ('Existing payable','Register existing deduction'):raise ValueError('Choose a new payable deduction or registration of an existing deduction.')
    if kind=='Register existing deduction':
        v['source_voucher']=values.get('tds_source') or c['voucher']
        if any(r.get('voucher_id')==v['source_voucher'] and r['kind']!='Challan' and tds.active(state,r) for r in state['tds_records']):raise ValueError('This source is already a B09 deduction. Link that existing deduction; do not register it twice.')
    r=tds.post(state,kind,v)
    next(r0 for r0 in state['tds_records'] if r0['id']==r['id'])['cwip_cost']=cid
    core.add_audit(state,'CWIP_TDS_LINKED',dict(cost=cid,tds=r['id'],voucher=r['voucher_id']));return r


@atomic
def link_tds(state,cid,record_id,basis,reviewed=False):
    c=cost(state,cid);basis=review(basis,reviewed)
    r=next((r for r in state['tds_records'] if r['id']==record_id and r['kind']!='Challan'),None)
    if not r or not tds.active(state,r) or r['branch']!=c['branch'] or r['gross']!=c['gross'] or c['voucher'] not in (r.get('voucher_id'),r.get('source_voucher')):raise ValueError('Select the active B09 deduction for this exact source, unit and gross cost.')
    if r.get('cwip_cost') or any(other.get('cwip_cost')==cid and tds.active(state,other) for other in state['tds_records']):raise ValueError('The deduction or cost is already linked; do not register tax twice.')
    r['cwip_cost']=cid;core.add_audit(state,'CWIP_EXISTING_TDS_LINKED',dict(cost=cid,tds=record_id,basis=basis));return r


def format_money(n):return str(n//100)+'.'+str(n%100).zfill(2)


def retained(state,c,on='9999-12-31'):
    return sum((1 if e['kind']=='Retention held' else -1)*e['amount'] for e in data(state)['events'] if e.get('cost')==c['id'] and e['kind'].startswith('Retention') and live(state,e,on))


@atomic
def link_retention(state,cid,source,amount,basis,reviewed=False):
    c=cost(state,cid);p=project(state,c['project']);basis=review(basis,reviewed);sv=_source(state,source);n=core.money(amount)
    if sv['date']<c['date'] or n<=0:raise ValueError('Link positive existing retention on/after the cost source date.')
    capacity=sum(l['credit']-l['debit'] for l in sv['lines'] if l['account']==p['retention'] and l['branch']==c['branch'])
    used=sum(e['amount'] for e in data(state)['events'] if e['kind']=='Retention held' and e['voucher']==source and project(state,e['project'])['retention']==p['retention'])
    if used+n>capacity:raise ValueError('Existing retention credit capacity is already allocated or insufficient.')
    e=dict(id=str(uuid.uuid4()),kind='Retention held',mode='Link existing',project=p['id'],cost=cid,date=sv['date'],amount=n,voucher=source,basis=basis,items=[])
    data(state)['events'].append(e);core.add_audit(state,'CWIP_RETENTION_LINKED',copy.deepcopy(e));return e


@atomic
def settle_retention(state,cid,on,amount,counter,basis,reviewed=False):
    c=cost(state,cid);p=project(state,c['project']);fa.day(on);basis=review(basis,reviewed);n=core.money(amount)
    _alignment(state,on,c['branch'])
    if on<c['date'] or not live(state,c,on) or n<=0 or n>retained(state,c,on):raise ValueError('Release/pay only positive, dated outstanding retention on a live cost.')
    details=state['account_details'].get(counter,{})
    if counter!=c['payable'] and details.get('group')!='Cash and bank':raise ValueError('Release to original supplier payable or pay through INR cash/bank.')
    ledger(state,p['retention'],'Liability','Retention')
    v=core.post(state,on,'Retention release/payment '+c['reference']+': '+basis,fa._pair(p['retention'],counter,n,c['branch']))
    e=dict(id=str(uuid.uuid4()),kind='Retention released',project=p['id'],cost=cid,date=on,amount=n,counter=counter,voucher=v['id'],basis=basis,items=[])
    data(state)['events'].append(e);core.add_audit(state,'CWIP_RETENTION_SETTLED',copy.deepcopy(e));return e


@atomic
def expense_remaining(state,cid,on,amount,expense,basis,reviewed=False):
    c=cost(state,cid);fa.day(on);basis=review(basis,reviewed);n=core.money(amount);ledger(state,expense,'Expense')
    if state['account_details'][expense]['group'] in ('Depreciation','Income tax'):raise ValueError('Select an operating cost expense.')
    if on<c['date'] or n<=0 or n>_remaining(state,c,on):raise ValueError('Expense only the remaining eligible CWIP on/after the cost date.')
    _alignment(state,on,c['branch'])
    v=core.post(state,on,'CWIP expensed '+c['reference']+': '+basis,fa._pair(expense,c['cwip'],n,c['branch']))
    e=dict(id=str(uuid.uuid4()),kind='Expense reclassification',project=c['project'],date=on,voucher=v['id'],basis=basis,items=[dict(cost=cid,amount=n)],expense=expense)
    data(state)['events'].append(e);core.add_audit(state,'CWIP_RECLASSIFIED',copy.deepcopy(e));return e


@atomic
def commission(state,pid,on,allocations,asset_values,basis,reviewed=False):
    p=project(state,pid);fa.day(on);basis=review(basis,reviewed)
    if not allocations:raise ValueError('Select cost sources and positive allocation amounts.')
    _alignment(state,on,p['branch']);items=[];credits={}
    for cid,value in allocations.items():
        c=cost(state,cid);n=core.money(value)
        if c['project']!=pid or c['date']>on or n<=0 or n>_remaining(state,c,on):raise ValueError('Commission only available dated CWIP from this project.')
        items.append(dict(cost=cid,amount=n));credits[c['cwip']]=credits.get(c['cwip'],0)+n
    total=sum(i['amount'] for i in items);ppe=asset_values.get('ppe','1030');ledger(state,ppe,'Asset','PPE')
    put=fa.day(asset_values.get('put_to_use',on))
    if put<on:raise ValueError('Put-to-use cannot precede this commissioning transfer. Use the actual ready-for-use date for commissioning.')
    lines=[dict(account=ppe,branch=p['branch'],debit=total,credit=0)]+[dict(account=code,branch=p['branch'],debit=0,credit=n) for code,n in credits.items()]
    voucher=core.post(state,on,'Commission '+p['key']+': '+basis,lines)
    values=dict(asset_values,mode='Link existing',branch=p['branch'],acquired=on,baseline=on,cost=format_money(total),opening_accum='0',cost_voucher=voucher['id'],reviewed=reviewed,basis=basis,put_to_use=put)
    a=fa.register(state,values)
    e=dict(id=str(uuid.uuid4()),kind='Commission',project=pid,date=on,voucher=voucher['id'],asset=a['id'],basis=basis,items=items)
    data(state)['events'].append(e);core.add_audit(state,'CWIP_COMMISSIONED',copy.deepcopy(e));return e


def check(state,reversal=None):
    """Check capacity at every source/event/reversal date, including future uses."""
    d=data(state)
    if not d['costs']:return
    roots=gst._roots(state);relevant={r['voucher'] for r in d['costs']+d['events']}
    relevant|={r['voucher_id'] for r in state.get('tds_records',[]) if r.get('voucher_id') and (r.get('cwip_cost') or r.get('source_voucher') in relevant)}
    if reversal and roots.get(reversal[0],(None,0))[0] not in relevant:return
    def islive(record,on):
        n=fa.family(state,record['voucher'],on)
        if reversal and reversal[1]<=on and roots[reversal[0]][0]==record['voucher']:n-=roots[reversal[0]][1]
        return record['date']<=on and n==1
    dates={r['date'] for r in d['costs']+d['events']}|{v['date'] for v in state['vouchers'] if roots[v['id']][0] in relevant}
    dates|={r['date'] for r in state.get('tds_records',[]) if r.get('source_voucher') in {c['voucher'] for c in d['costs']}}
    if reversal:dates.add(reversal[1])
    for on in sorted(dates):
        net=tds._net(state,on,reversal)
        for source in {c['voucher'] for c in d['costs']}:
            cs=[c for c in d['costs'] if c['voucher']==source]
            for unit,code in {(c['branch'],c['payable']) for c in cs}:
                held=sum(e['amount'] for e in d['events'] if e['kind']=='Retention held' and e.get('mode')!='Link existing' and islive(e,on) and e['cost'] in {c['id'] for c in cs if c['branch']==unit and c['payable']==code})
                withheld=sum(r['withheld'] for r in state.get('tds_records',[]) if r.get('source_voucher')==source and r.get('counter_account')==code and r['branch']==unit and r['kind']!='Register existing deduction' and tds.active(state,r,on,net))
                original=next(v for v in state['vouchers'] if v['id']==source)
                capacity=sum(l['credit']-l['debit'] for l in original['lines'] if l['branch']==unit and l['account']==code)
                if held+withheld>capacity:raise ValueError('Retention plus B09 deductions exceeds source payable capacity.')
        for c in d['costs']:
            used=held=released=withheld=0
            for e in d['events']:
                if not islive(e,on):continue
                if e['kind'] in ('Commission','Expense reclassification'):used+=sum(i['amount'] for i in e['items'] if i['cost']==c['id'])
                elif e.get('cost')==c['id']:
                    if e['kind']=='Retention held':held+=e['amount']
                    else:released+=e['amount']
            for r in state.get('tds_records',[]):
                if r.get('cwip_cost')==c['id'] and tds.active(state,r,on,net):withheld+=r['withheld']
            if used>c['capital'] or released>held or held+withheld>c['gross']:raise ValueError('CWIP source/retention/TDS capacity would be exceeded, including future allocations.')
            if not islive(c,on) and (used or held or withheld):raise ValueError('Reverse dependent commissioning, reclassification, retention and TDS before reversing the cost source.')


def validate_reversal(state,voucher_id,on):check(state,(voucher_id,on))


def _alignment(state,on,branch):
    if any(row[-1] for row in report(state,on,on,branch)['proof']):raise ValueError('Reconcile CWIP/retention to project sources before transferring or expensing costs.')


def report(state,start,end,branch='ALL'):
    core.verify_audit(state);fa.day(start);fa.day(end)
    if start>end or branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Choose valid CWIP report dates and scope.')
    d=data(state);cost_rows=[];summary=[];proof=[];milestones=[];sources=[];expected={};issues=[]
    for p in d['projects']:
        if branch!='ALL' and branch!=p['branch']:continue
        pp=plan(p,end);unit=p['branch']
        for category in CATEGORIES:
            cs=[c for c in d['costs'] if c['project']==p['id'] and c['category']==category and live(state,c,end)]
            gross=sum(c['gross'] for c in cs);capital=sum(c['capital'] for c in cs);remaining=sum(_remaining(state,c,end) for c in cs);budget=pp['budgets'][category]
            expensed=sum(i['amount'] for e in d['events'] if e['kind']=='Expense reclassification' and live(state,e,end) for i in e['items'] if i['cost'] in {c['id'] for c in cs})
            summary.append([p['key'],pp['name'],unit,category,budget,gross,capital,capital-remaining-expensed,expensed,gross-capital+expensed,remaining,None if budget is None else budget-gross])
            expected[(unit,p['ledgers'][category])]=remaining
        expected[(unit,p['retention'])]=-sum(retained(state,c,end) for c in d['costs'] if c['project']==p['id'])
        milestones.extend([p['key'],m['key'],m['name'],m['due'],m['completed'] if m['completed'] and m['completed']<=end else '',pp['basis']] for m in pp['milestones'])
        for c in d['costs']:
            if c['project']!=p['id'] or c['date']>end:continue
            active=live(state,c,end);capital=c['capital'] if active else 0
            withheld=sum(r['withheld'] for r in state.get('tds_records',[]) if r.get('cwip_cost')==c['id'] and tds.active(state,r,end))
            cost_rows.append([p['key'],c['id'],c['reference'],c['party'],c['category'],c['date'],c['gross'] if active else 0,capital,c['gross']-capital if active else 0,_remaining(state,c,end),retained(state,c,end),withheld,c['voucher'],'Active' if active else 'Reversed',c['basis']])
        for code in [*p['ledgers'].values(),p['retention']]:
            actual=core.balances(state,end,unit)[code];n=expected[(unit,code)]
            proof.append([p['key'],unit,code,n,actual,actual-n])
    # Include all unallocated legacy/manual CWIP and retention, including non-project accounts.
    for unit in foundation.branches(state):
        if branch!='ALL' and branch!=unit:continue
        balances=core.balances(state,end,unit)
        for a in state['accounts']:
            if state['account_details'][a['code']]['group'] in ('CWIP','Retention') and (unit,a['code']) not in expected and balances[a['code']]:proof.append(['Unallocated',unit,a['code'],0,balances[a['code']],balances[a['code']]])
    for e in d['events']:
        p=project(state,e['project'])
        if e['date']<=end and (branch=='ALL' or p['branch']==branch):sources.append([p['key'],e['date'],e['kind'],e['voucher'],e.get('asset',''),sum(i['amount'] for i in e['items']) if e['items'] else e['amount'],'Active' if live(state,e,end) else 'Reversed',e['basis']])
    if any(row[-1] for row in proof):issues.append('Unallocated/manual CWIP or retention ledger differences remain.')
    return dict(start=start,end=end,branch=branch,summary=summary,costs=cost_rows,proof=proof,milestones=milestones,events=sources,issues=issues,ready=not issues)


def snapshots(state,start,end,branch='ALL'):
    r=report(state,start,end,branch)
    base=dict(entity=state['settings']['entity'],registration=copy.deepcopy(state['settings']['registration']),start=start,end=end,branch=branch,scope='All operating units' if branch=='ALL' else foundation.branches(state)[branch],prepared=datetime.now(history.INDIA).isoformat(),currency='INR',status='Reconciled working' if r['ready'] else 'DRAFT / differences',controls={},note='Cumulative project positions as at '+end+'. Blank budgets are unknown, not zero. Costs/retention/commissioning follow source vouchers and dated reversals. TDS challan payments and eligibility use the separate B09 workflow. Capitalization, actual ready-for-use date and asset life require client review. '+'; '.join(r['issues']))
    specs=[('Project category costs',['Project','Name','Unit','Category','Budget INR','Gross cost INR','Reviewed capital INR','Commissioned INR','Reclassified expense INR','Total operating expense INR','CWIP remaining INR','Budget less gross INR'],list(range(4,12)),r['summary']),('Project source costs',['Project','Cost ID','Source ref','Supplier','Category','Date','Gross INR','Capital INR','Operating expense INR','Remaining CWIP INR','Retention INR','TDS INR','Voucher','Status','Review basis'],list(range(6,12)),r['costs']),('CWIP ledger reconciliation',['Project','Unit','Ledger','Source Dr/(Cr) INR','Ledger Dr/(Cr) INR','Difference INR'],[3,4,5],r['proof']),('Project milestones',['Project','Key','Milestone','Target date','Completed date','Review basis'],[],r['milestones']),('Commission and retention history',['Project','Date','Action','Voucher','Book asset ID','Amount INR','Status','Basis'],[5],r['events'])]
    return [dict(copy.deepcopy(base),mode=mode,columns=cols,money_columns=money,rows=rows,controls={'Absolute ledger differences':sum(abs(row[-1]) for row in r['proof'])} if mode=='CWIP ledger reconciliation' else {}) for mode,cols,money,rows in specs]


def export(state,start,end,branch,path,kind):
    from . import financial_reports as fr
    packs=snapshots(state,start,end,branch)
    if kind=='xlsx':fr.export_pack_xlsx(packs,path)
    elif kind=='pdf':fr.export_pdf(packs,path)
    elif kind=='json':Path(path).write_text(json.dumps(dict(report=report(state,start,end,branch),sources=data(state)),ensure_ascii=False,indent=2),encoding='utf-8')
    else:raise ValueError('Choose Excel, PDF or JSON.')

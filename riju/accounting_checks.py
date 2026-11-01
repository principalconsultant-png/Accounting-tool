"""Editable review alerts and read-only, ledger-grounded offline questions."""
import copy
import hashlib
import json
import re
import uuid
from collections import defaultdict
from datetime import date
from . import core,foundation,financial_reports as f,tds,tax,cwip,local_model

FIELDS=('cash_payment','cumulative_tds_base','unusual_posting','clearing_days')


def save_policy(state,values):
    if not values.get('confirmed') or not str(values.get('basis','')).strip():raise ValueError('Review alert thresholds and record their source/basis. They are prompts, not legal conclusions.')
    effective=values['effective']
    if date.fromisoformat(effective).isoformat()!=effective:raise ValueError('Use a valid effective date.')
    thresholds={}
    for key in FIELDS:
        v=values.get(key)
        if v in ('',None):thresholds[key]=None;continue
        n=int(v) if key=='clearing_days' else core.money(v)
        if n<0 or key=='clearing_days' and str(n)!=str(v).strip():raise ValueError('Use nonnegative INR thresholds and whole ageing days, or blank to disable.')
        thresholds[key]=n
    row=dict(id=str(uuid.uuid4()),effective=effective,basis=values['basis'].strip(),thresholds=thresholds)
    state.setdefault('accounting_check_policies',[]).append(row);core.add_audit(state,'ACCOUNTING_CHECK_POLICY_REVIEWED',copy.deepcopy(row));return row


def policy(state,on):
    rows=[(p['effective'],i,p) for i,p in enumerate(state.get('accounting_check_policies',[])) if p['effective']<=on]
    return copy.deepcopy(max(rows,key=lambda p:p[:2])[2]) if rows else dict(id='UNREVIEWED',effective='',basis='No reviewed thresholds: monetary/ageing threshold alerts disabled.',thresholds=dict.fromkeys(FIELDS))


def fingerprint(state):
    data={k:state.get(k) for k in ('vouchers','accounts','account_details','tds_records','tds_allocations','tax_config','cwip','matches','accounting_check_policies')}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def _scope(state,start,end,branch):
    core.verify_audit(state)
    if date.fromisoformat(start).isoformat()!=start or date.fromisoformat(end).isoformat()!=end or start>end:raise ValueError('Select a valid reporting period.')
    if branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Select a valid operating unit.')


def run(state,start,end,branch='ALL'):
    _scope(state,start,end,branch);p=policy(state,end);threshold=p['thresholds'];alerts=[]
    def add(rule,severity,unit,on,amount,message,sources):
        sources=sorted(set(str(x) for x in sources));seed=[rule,unit,on,amount,message,sources,p['id']];key=hashlib.sha256(json.dumps(seed,sort_keys=True).encode()).hexdigest()
        review=next((r for r in reversed(state.get('accounting_check_reviews',[])) if r['check_id']==key),None)
        alerts.append(dict(id=key,rule=rule,severity=severity,branch=unit,date=on,amount=amount,message=message,sources=sources,policy=p['id'],basis=p['basis'],status=review['status'] if review else 'Open',review_note=review['note'] if review else ''))
    vouchers=[v for v in state['vouchers'] if start<=v['date']<=end and not v.get('opening') and not v.get('closing') and (branch=='ALL' or any(l['branch']==branch for l in v['lines']))]
    net=tds._net(state,end)
    live=[v for v in vouchers if not v.get('reverses') and net.get(v['id'])==1]
    cash=defaultdict(lambda:dict(amount=0,ids=[]));bases=defaultdict(lambda:dict(amount=0,ids=[]));refs=defaultdict(list)
    for v in live:
        meta=v.get('metadata',{});party=re.sub(r'\s+',' ',meta.get('payee','').strip().casefold())

        units={l['branch'] for l in v['lines'] if branch=='ALL' or l['branch']==branch}
        for unit in units:
            lines=[l for l in v['lines'] if l['branch']==unit];value=sum(l['debit'] for l in lines)
            cashout=sum(l['credit']-l['debit'] for l in lines if l['account']=='1000')
            if cashout>0:
                k=('Entity' if branch=='ALL' else unit,v['date'],party or 'Unidentified payee');cash[k]['amount']+=cashout;cash[k]['ids'].append(v['id'])
            if threshold['unusual_posting'] is not None and value>=threshold['unusual_posting']:add('Large posting','Review',unit,v['date'],value,'Posting meets the reviewed size threshold; verify source, classification and approval.',[v['id']])
            if party:
                for l in lines:
                    if l['account'] in ('4510','4530') and l['debit']>0:
                        key=(unit,core.financial_year(v['date']),party,l['account']);bases[key]['amount']+=l['debit'];bases[key]['ids'].append(v['id'])
    # Cumulative expense candidates use the whole fiscal year, not just the report month.
    if threshold['cumulative_tds_base'] is not None:
        bases=defaultdict(lambda:dict(amount=0,ids=[]))
        for v in state['vouchers']:
            if v['date']>end or v.get('opening') or v.get('closing') or v.get('reverses') or net.get(v['id'])!=1:continue
            party=v.get('metadata',{}).get('payee','').strip().casefold()
            if not party:continue
            for l in v['lines']:
                if l['account'] in ('4510','4530') and l['debit']>0 and (branch=='ALL' or l['branch']==branch):
                    k=(l['branch'],core.financial_year(v['date']),party,l['account']);bases[k]['amount']+=l['debit'];bases[k]['ids'].append(v['id'])
        for (unit,year,party,account),x in bases.items():
            if core.fy_bounds(year)[1]<start:continue
            if x['amount']>=threshold['cumulative_tds_base']:add('Potential cumulative TDS source','Review',unit,end,x['amount'],f'FY {year} booked {account} for {party} meets the reviewed alert threshold. This is expense total, not a verified legal TDS base; verify PAN, section, GST exclusions and registered deductions.',x['ids'])
    for (unit,on,party),x in cash.items():
        if threshold['cash_payment'] is not None and x['amount']>=threshold['cash_payment']:add('Cash-payment review','Review',unit,on,x['amount'],'Daily cash outflow for '+party+' meets the reviewed threshold. Verify actual payee, purpose and applicable exceptions; no legal violation is asserted.',x['ids'])
    for v in state['vouchers']:
        if v['date']>end or v.get('opening') or v.get('closing') or v.get('reverses') or net.get(v['id'])!=1:continue
        meta=v.get('metadata',{});ref=re.sub(r'[^a-z0-9]','',meta.get('reference','').casefold())
        if ref:refs[(meta.get('payee','').strip().casefold(),ref,core.financial_year(v['date']))].append(v)
    for (_,reference,year),vs in refs.items():
        if len(vs)>1 and any(start<=v['date']<=end and (branch=='ALL' or any(l['branch']==branch for l in v['lines'])) for v in vs):add('Potential duplicate source','Review',branch,max(v['date'] for v in vs),sum(sum(l['debit'] for l in v['lines']) for v in vs),'Repeated party/reference within fiscal year '+str(year)+': '+reference+'. Verify genuine split/payment stages before correction.',[v['id'] for v in vs])
    # Exact source-free duplicates are review candidates, never auto-deleted.
    signatures=defaultdict(list)
    for v in live:
        if not v.get('metadata',{}).get('reference'):
            key=json.dumps([v['date'],v['narration'].strip().casefold(),sorted((l['account'],l['branch'],l['debit'],l['credit']) for l in v['lines'])]);signatures[key].append(v)
    for vs in signatures.values():
        if len(vs)>1:add('Potential repeated journal','Review',branch,vs[0]['date'],sum(l['debit'] for l in vs[0]['lines']),'Same date, narration and ledger amounts recur; review source documents before deciding whether duplicate.',[v['id'] for v in vs])
    # Use B09's effective source snapshots and PAN-level aggregation, including other units.
    groups=set()
    for r in state.get('tds_records',[]):
        if r['kind'] in ('Challan','Adjustment') or r['date']>end or branch!='ALL' and r['branch']!=branch or not tds.active(state,r,end,net):continue
        on=min(end,core.fy_bounds(r['year'])[1])
        if on<start:continue
        try:
            party=tax.resolve_party(state,r['party_id'],on);key=(r['section'],r['group'],party['registration']['pan'] or r['party_id'],r['year'])
            if key in groups:continue
            groups.add(key);a=tds.assess(state,r['rule'],party,on,posted_through=on)
            if a['due']>0:add('Cumulative TDS shortfall','Review','Entity',on,a['due'],'B09 reviewed-source target exceeds registered withholding; verify source timing and exceptions before a catch-up adjustment. PAN aggregation includes all units.',a['source_records'])
        except ValueError as error:add('TDS configuration/source review','Review',r['branch'],on,0,str(error),[r['id']])
    project=cwip.report(state,start,end,branch)
    for row in project['proof']:
        if row[-1]:add('CWIP classification/reconciliation','Review',row[1],end,row[-1],'Project '+row[0]+' ledger '+row[2]+' differs from reviewed source position. Investigate manual capitalization/retention.',[row[2],* [v['id'] for v in state['vouchers'] if v['date']<=end and any(l['account']==row[2] and l['branch']==row[1] for l in v['lines'])]])
    for row in project['summary']:
        if row[4] is not None and row[11]<0:add('Project budget overrun','Review',row[2],end,-row[11],row[0]+' / '+row[3]+' actual gross exceeds the reviewed category budget.',[row[0]])
    for row in project['milestones']:
        if row[3] and row[3]<end and not row[4]:add('Project milestone overdue','Review',branch,end,0,row[0]+' / '+row[2]+' target '+row[3]+' lacks a recorded completion. Review ready-for-use and commissioning evidence.',[row[0],row[1]])
    for unit in foundation.branches(state):
        if branch!='ALL' and unit!=branch:continue
        b=core.balances(state,end,unit)
        if b['1000']<0:add('Negative cash','Review',unit,end,b['1000'],'Cash ledger is credit/negative at report end; verify receipts, dates and cash/bank classification.',[v['id'] for v in state['vouchers'] if v['date']<=end and any(l['account']=='1000' and l['branch']==unit for l in v['lines'])])
        if threshold['clearing_days'] is not None:
            from . import reconciliation
            historical=copy.deepcopy(state);historical['vouchers']=[v for v in historical['vouchers'] if v['date']<=end]
            ids={v['id'] for v in historical['vouchers']};banks={b['id']:b for b in state['bank_lines']}
            historical['matches']=[dict(m,status='ACTIVE') for m in historical['matches'] if reconciliation.active(m,end) and (not m.get('posting') or m['posting'] in ids) and banks.get(m.get('bank_id'),{}).get('date','9999')<=end]
            for account in ('1110','1120'):
                for item in reconciliation.clearing_items(historical,account,unit,end):
                    days=(date.fromisoformat(end)-date.fromisoformat(item['date'])).days
                    if days>=threshold['clearing_days']:add('Aged collection clearing','Review',unit,end,item['remaining'],f'{account}: {days} calendar days outstanding; verify provider settlement and fees.',[item['voucher'],item['key']])
    return dict(start=start,end=end,branch=branch,policy=p,alerts=alerts,fingerprint=fingerprint(state),note='Review prompts only. Thresholds do not determine legal liability. Corrections use normal reviewed source workflows; checks never post or alter journals.')


def review(state,result,check_id,status,note):
    if result['fingerprint']!=fingerprint(state):raise ValueError('Books or check policy changed; refresh checks before recording a review.')
    if status not in ('Investigating','Explained','Action required') or not note.strip():raise ValueError('Record a review status and supporting explanation.')
    if not any(a['id']==check_id for a in run(state,result['start'],result['end'],result['branch'])['alerts']):raise ValueError('Select an actual current finding.')
    row=dict(id=str(uuid.uuid4()),check_id=check_id,status=status,note=note.strip());state.setdefault('accounting_check_reviews',[]).append(row);core.add_audit(state,'ACCOUNTING_CHECK_REVIEWED',copy.deepcopy(row));return row


def snapshots(state,start,end,branch='ALL'):
    r=run(state,start,end,branch);p=f.snapshot(state,'Trial balance',start,end,branch);p.update(mode='Accounting review checks',columns=['Rule','Unit','Date','INR','Status','Finding','Source references','Review evidence'],money_columns=[3],rows=[[a['rule'],a['branch'],a['date'],a['amount'],a['status'],a['message'],'; '.join(a['sources']),a['review_note']] for a in r['alerts']],controls={},note=r['note']+' Policy '+r['policy']['id']+' | '+r['policy']['basis']);return p


def answer(state,question,start,end,branch='ALL'):
    _scope(state,start,end,branch);q=question.lower().strip()
    if not q or len(q)>1000:raise ValueError('Ask one short, read-only ledger question.')
    if re.search(r'\b(post|delete|change|adjust|reverse|send|pay|paid|predict|forecast|should|legal|avoid)\b',q):raise ValueError('Ask about posted balances, booked revenue/expenses, profit or source vouchers. Payment allocation, actions, predictions and legal advice are outside read-only questions.')
    if re.search(r'\b(today|yesterday|tomorrow|last month|this month|next month)\b',q) or re.search(r'\d{4}-\d{2}-\d{2}',q):raise ValueError('Set the explicit From/Through selectors for the question period; relative or embedded dates are not silently inferred.')
    if re.search(r'\b(payments?|receipts?|spent|spend|cash flow|why)\b',q) and not re.search(r'\b(compare|comparative|difference|decreased|increased|changed)\b',q):raise ValueError('Ask a posted balance, booked expense/revenue or comparative P&L question. Allocated payments/receipts and causal explanations need their source reports.')
    named={code for code,name in foundation.branches(state).items() if re.search(r'(?<!\w)'+re.escape(name.casefold())+r'(?!\w)',q) or re.search(r'\b(?:unit|branch|at)\s+'+re.escape(code)+r'\b',q,re.I)}
    if len(named)>1:raise ValueError('Choose one unit or All in the scope selector.')
    if named:branch=next(iter(named))
    p=f.snapshot(state,'Trial balance',start,end,branch);p.update(mode='Offline ledger answer',controls={},note='Posted ledger facts only; not a generated legal or causal conclusion. Scope/date are explicit. Source rows are the complete arithmetic trace. Question: '+question)
    accounts={a['code']:a for a in state['accounts']};code_matches={c for c in accounts if re.search(r'\b'+re.escape(c)+r'\b',q)}
    numeric=q
    for code in code_matches:numeric=re.sub(r'\b'+code+r'\b','',numeric)
    if re.search(r'\d',numeric):raise ValueError('Set dates in the period selectors; only current ledger codes are accepted as numbers in a question.')
    names={a['code'] for a in state['accounts'] if re.search(r'(?<!\w)'+re.escape(a['name'].lower())+r'(?!\w)',q)}
    generic_bank=bool(re.search(r'\bbank balance\b',q))
    matches=code_matches or (set() if generic_bank else names)
    if len(matches)>1:raise ValueError('Name one account code; several ledgers match the question.')
    if 'cwip' in q or 'commissioning' in q:
        packs=cwip.snapshots(state,start,end,branch);return dict(summary='CWIP remaining, source allocations and reconciliation are in the attached source working.',commentary='Review differences and ready-for-use evidence before commissioning; this is a review prompt.',packs=packs)
    comparative=bool(re.search(r'\b(compare|comparative|difference|decreased|increased|changed)\b',q))
    if re.search(r'\b(top|largest)\b',q) and not re.search(r'\b(expenses?|costs?)\b',q):raise ValueError('Ranking currently supports booked expenses; specify top expenses.')
    if comparative and not re.search(r'\b(profit|revenue|income|expenses?|p&l)\b',q):raise ValueError('Comparison currently supports P&L. Use comparative financial reports for balance comparisons.')
    if re.search(r'\b(top|largest)\b',q) or comparative:
        mode='Comparative P&L' if comparative else 'Profit and loss';p=f.snapshot(state,mode,start,end,branch)
        if not comparative:p['rows']=sorted([r for r in p['rows'] if r[1]=='Expense' and r[0]],key=lambda r:-r[3]);p['note']+=' Ranked booked expense ledgers, all values retained; no causal explanation is inferred.'
        p['mode']='Offline comparison' if comparative else 'Ranked booked expenses'
        trace=_trace(state,{a['code'] for a in state['accounts'] if a['kind'] in ('Expense','Revenue')},start,end,branch,False,1)
        currenttrace=_tracepack(state,trace,start,end,branch);currenttrace['mode']='Current period source trace';packs=[p,currenttrace]
        if comparative:
            ps,pe=f.previous_year(start),f.previous_year(end);pt=_tracepack(state,_trace(state,{a['code'] for a in state['accounts'] if a['kind'] in ('Expense','Revenue')},ps,pe,branch,False,1),ps,pe,branch);pt['mode']='Comparative source trace';packs.append(pt)
        return dict(summary='Ledger comparison shows recorded differences, without inferring their cause.' if comparative else 'Booked expense ledgers ranked by recorded period amount.',commentary='Interpretation: investigate source vouchers and classification for large changes. This is a review suggestion, separate from posted facts.',packs=packs)
    balance='balance' in q or 'payable' in q or 'outstanding' in q
    if matches:selected=set(matches);label=next(iter(matches))+' '+accounts[next(iter(matches))]['name'];sign=-1 if accounts[next(iter(matches))]['kind'] in ('Liability','Equity','Revenue') else 1
    elif 'profit' in q:selected={a['code'] for a in state['accounts'] if a['kind'] in ('Revenue','Expense')};label='Profit / loss';sign=-1;balance=False
    elif 'revenue' in q or 'income' in q:selected={a['code'] for a in state['accounts'] if a['kind']=='Revenue'};label='Booked revenue';sign=-1;balance=False
    elif 'cash' in q:selected={'1000'};label='Cash';sign=1;balance=True
    elif 'bank' in q:selected={a['code'] for a in state['accounts'] if state['account_details'][a['code']]['group']=='Cash and bank' and a['code']!='1000'};label='Configured cash/bank ledgers excluding main cash (1000)';sign=1;balance=True
    elif 'upi' in q:selected={'1110'};label='UPI collection clearing';sign=1;balance=True
    elif 'tds' in q:selected={a['code'] for a in state['accounts'] if state['account_details'][a['code']]['group']=='TDS payable'};label='TDS payable ledger position';sign=-1;balance=True
    else:
        topic=local_model.predict(re.sub(r'\b(expenses?|total|booked|incurred)\b','',q))['intent'];selected={topic} if topic in accounts and accounts[topic]['kind']=='Expense' else set()
        if selected:label=accounts[topic]['name'];sign=1;balance=False
        elif re.search(r'\b(?:total expenses?|expenses? summary|all expenses?)\b',q) or q in ('expenses','expense','what are the expenses','what is the expense'):selected={a['code'] for a in state['accounts'] if a['kind']=='Expense'};label='Booked expenses';sign=1;balance=False
        else:raise ValueError('Supported: cash/bank/UPI or account-code balance, booked revenue/expenses/profit, ranked expenses, comparative P&L and CWIP sources. Rephrase or use a report.')
    trace=_trace(state,selected,start,end,branch,balance,sign);amount=sum(r[-1] for r in trace)
    summary=label+(' as at '+end if balance else ' from '+start+' through '+end)+': '+core.rupees(amount)+' | '+('All operating units' if branch=='ALL' else foundation.branches(state)[branch])+'. '+('Positive is the account normal balance; negative is the opposite side.' if matches else 'Based only on posted ledger entries.')
    p=_tracepack(state,trace,start,end,branch);p['note']=summary+' '+p['note'];return dict(summary=summary,amount=amount,commentary='Review suggestion: reconcile source documents and unexplained balances; ledger totals alone do not establish payment allocation, tax eligibility or legal conclusions.',packs=[p])


def _trace(state,selected,start,end,branch,balance,sign):
    rows=[]
    for v in sorted(state['vouchers'],key=lambda v:v['date']):
        if v['date']>end or not balance and (v['date']<start or v.get('opening') or v.get('closing')):continue
        for i,l in enumerate(v['lines']):
            if l['account'] in selected and (branch=='ALL' or l['branch']==branch):rows.append([v['date'],v['id'],str(i),l['branch'],l['account'],v['narration'],l['debit'],l['credit'],sign*(l['debit']-l['credit'])])
    return rows


def _tracepack(state,trace,start,end,branch):
    p=f.snapshot(state,'Trial balance',start,end,branch);p.update(mode='Question ledger source trace',columns=['Date','Voucher','Line','Unit','Account','Narration','Debit INR','Credit INR','Answer effect INR'],money_columns=[6,7,8],rows=trace,controls={},note='Answer effect is the explicit signed ledger arithmetic, including dated reversals. Balance questions include all posted history through the selected end; period questions exclude opening and closing entries. Voucher IDs and zero-based line numbers identify each source.');return p

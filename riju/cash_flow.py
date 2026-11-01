"""Reviewed cash definitions, direct cash flows and ledger-derived indirect bridge."""
import copy
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import uuid
import json
from pathlib import Path
from . import core,foundation,gst,tax

CATEGORIES=('Operating','Investing','Financing','Exchange effects','Review')
DIRECT='Cash flow - direct';INDIRECT='Cash flow - indirect';FORECAST='Cash flow - AP forecast'


def defaults(state):
    cash=[];mapping={};noncash=[]
    operating_groups={'Payment clearing','Patient control','Inventory','GST input','Trade payables','Patient advances','TDS payable','GST output'}
    for a in state['accounts']:
        code=a['code'];details=state['account_details'][code];group=details['group'];explicit=details.get('cash_flow','Review')
        if a['kind'] in ('Asset','Liability') and (group=='Cash and bank' or explicit=='Cash equivalent'):cash.append(code)
        if group=='Depreciation':noncash.append(code)
        if explicit in CATEGORIES and explicit!='Review':category=explicit
        elif code=='1130':category='Financing'
        elif a['kind'] in ('Revenue','Expense') or group in operating_groups or code in state.get('gst_rcm_ledgers',{}).values():category='Operating'
        elif group in ('PPE','CWIP','Accumulated depreciation'):category='Investing'
        elif a['kind']=='Equity' or group=='Borrowings' or code=='1130':category='Financing'
        else:category='Review'
        mapping[code]=category
    return dict(cash_accounts=sorted(cash),mapping=mapping,noncash_accounts=noncash)


def save_policy(state,values):
    effective=tax.day(values.get('effective',''));codes=values.get('cash_accounts',[]);mapping=copy.deepcopy(values.get('mapping',{}));note=str(values.get('note','')).strip();reviewed=values.get('reviewed',False)
    accounts={a['code']:a for a in state['accounts']}
    if not isinstance(codes,list) or not codes or len(codes)!=len(set(codes)):raise ValueError('Select unique cash/equivalent ledger codes.')
    for code in codes:
        if code not in accounts or accounts[code]['kind'] not in ('Asset','Liability') or state['account_details'][code]['group']!='Cash and bank' and state['account_details'][code].get('cash_flow')!='Cash equivalent':raise ValueError('Cash ledgers must be cash/bank or explicitly marked Cash equivalent in account masters.')
    if any(code not in accounts or category not in CATEGORIES for code,category in mapping.items()):raise ValueError('Use valid ledger codes and Operating/Investing/Financing/Exchange effects/Review categories.')
    if any(a['kind'] not in ('Revenue','Expense') for a in accounts.values() if a['code'] in values.get('noncash_accounts',[])):raise ValueError('Noncash profit-adjustment accounts must be revenue/expense ledgers.')
    if any(c not in accounts for c in values.get('noncash_accounts',[])):raise ValueError('Unknown noncash adjustment account.')
    if type(reviewed)!=bool or reviewed and not note:raise ValueError('Enter the reviewed cash-definition/classification basis before marking this policy reviewed.')
    r=dict(id=str(uuid.uuid4()),effective=effective,cash_accounts=sorted(codes),mapping=mapping,noncash_accounts=sorted(set(values.get('noncash_accounts',[]))),note=note,reviewed=reviewed)
    state['cash_flow_policies'].append(r);core.add_audit(state,'CASH_FLOW_POLICY_SAVED',copy.deepcopy(r));return r


def policy(state,end):
    eligible=[p for p in state.get('cash_flow_policies',[]) if p['effective']<=end]
    return copy.deepcopy(max(enumerate(eligible),key=lambda p:(p[1]['effective'],p[0]))[1]) if eligible else dict(defaults(state),id=None,effective='',note='Unreviewed standard proposals',reviewed=False)


def _scope_lines(v,branch):return [l for l in v['lines'] if branch=='ALL' or l['branch']==branch]


def _internal_transfer(lines,cash):
    raw=[l for l in lines if l['account'] not in cash]
    if not raw:return True
    return all(l['account']=='1130' for l in raw) and sum(l['debit']-l['credit'] for l in raw)==0


def _mixed_controls(state,p,end,branch):
    # Generic settlement accounts can carry capital/financing as well as operating items.
    groups={'Trade payables','Other liabilities','Patient control','Payment clearing','Other assets','GST input','TDS payable','GST output','Patient advances','Retention'}
    generic={a['code'] for a in state['accounts'] if state['account_details'][a['code']]['group'] in groups and p['mapping'].get(a['code'],'Review') in ('Operating','Review')}
    batches=[]
    for v in state['vouchers']:
        if v['date']>end or v.get('opening') or v.get('closing'):continue
        units={l['branch'] for l in _scope_lines(v,branch)}
        for unit in units:
            codes={l['account'] for l in v['lines'] if l['branch']==unit and l['account'] not in p['cash_accounts']}
            batches.append((unit,codes))
    mixed=set();changed=True
    while changed:
        changed=False
        for unit,codes in batches:
            if any(p['mapping'].get(c) in ('Investing','Financing','Exchange effects') or (unit,c) in mixed for c in codes):
                before=len(mixed);mixed.update((unit,c) for c in codes if c in generic);changed|=len(mixed)!=before
    return mixed


def save_allocation(state,policy_id,voucher_id,branch,lines,reason,gross_reviewed=False):
    p=next((p for p in state['cash_flow_policies'] if p['id']==policy_id),None);root=gst._roots(state).get(voucher_id)
    if not p or not p['reviewed'] or not root or root[0]!=voucher_id or branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Choose a saved policy, original voucher and valid reporting scope.')
    v=next(v for v in state['vouchers'] if v['id']==voucher_id)
    if v.get('opening') or not reason.strip():raise ValueError('Opening balances are not flows; other reviewed classifications need a reason/source.')
    cash=[l for l in _scope_lines(v,branch) if l['account'] in p['cash_accounts']];net=sum(l['debit']-l['credit'] for l in cash)
    if not cash:raise ValueError('This voucher contains no selected cash ledger.')
    clean=[]
    for item in lines:
        category=item.get('category');text=str(item.get('amount','')).strip();negative=text.startswith('-');n=Decimal(tax.decimal_text(text[1:] if negative else text));amount=int(n*100)*(-1 if negative else 1)
        if category not in CATEGORIES[:-1]:raise ValueError('Choose Operating, Investing, Financing or Exchange effects.')
        if amount:clean.append(dict(category=category,amount=amount,label=str(item.get('label','')).strip() or category))
    if net==0 and _internal_transfer(_scope_lines(v,branch),set(p['cash_accounts'])) and clean:raise ValueError('Internal cash transfers are excluded from external receipts/payments.')
    if sum(i['amount'] for i in clean)!=net:raise ValueError('Reviewed flow lines must sum exactly to the original cash movement.')
    if type(gross_reviewed)!=bool:raise ValueError('Gross review status must be yes or no.')
    if not gross_reviewed and (sum(i['amount'] for i in clean if i['amount']>0)>sum(l['debit'] for l in cash) or -sum(i['amount'] for i in clean if i['amount']<0)>sum(l['credit'] for l in cash)):raise ValueError('Gross flows exceed recorded cash legs; independently review supporting gross receipts/payments and explicitly confirm before allocation.')
    r=dict(id=str(uuid.uuid4()),policy_id=policy_id,voucher_id=voucher_id,branch=branch,lines=clean,reason=reason.strip(),gross_reviewed=gross_reviewed)
    state['cash_flow_allocations'].append(r);core.add_audit(state,'CASH_FLOW_ALLOCATION_SAVED',copy.deepcopy(r));return r


def analyse(state,start,end,branch='ALL'):
    core.verify_audit(state);tax.day(start);tax.day(end)
    if start>end or branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Select a valid reporting range and unit.')
    p=policy(state,end);cash=set(p['cash_accounts']);accounts={a['code']:a for a in state['accounts']};roots=gst._roots(state);by_id={v['id']:v for v in state['vouchers']}
    mixed_controls=_mixed_controls(state,p,end,branch)
    opening=closing=introduced=profit=special=0;flows=[];issues=[];noncash_support=[];bs={category:{} for category in CATEGORIES};profit_adjustments={}
    for v in state['vouchers']:
        lines=_scope_lines(v,branch);cash_lines=[l for l in lines if l['account'] in cash];delta=sum(l['debit']-l['credit'] for l in cash_lines)
        if v['date']<=end:closing+=delta
        if v['date']<start or v.get('opening') and v['date']==start:opening+=delta;continue
        if v['date']>end:continue
        if v.get('opening'):introduced+=delta;continue
        # Normal year-end transfers have no cash and must not duplicate earnings.
        if v.get('closing') and not cash_lines:continue
        others={}
        for l in lines:
            if l['account'] not in cash:others[l['account']]=others.get(l['account'],0)+l['debit']-l['credit']
        others={code:n for code,n in others.items() if n};root_id,sign=roots[v['id']];root=by_id[root_id];local=[];reasons=[]
        pl={code:n for code,n in others.items() if accounts[code]['kind'] in ('Revenue','Expense')}
        if v.get('closing'):special-=sum(pl.values())
        else:profit-=sum(pl.values())
        local_bs={c:n for c,n in others.items() if c not in pl}
        removed={};flagged={c:n for c,n in pl.items() if c in p['noncash_accounts']}
        if not cash_lines and flagged:
            # Separate provable noncash P&L adjustments without double-counting their BS counterpart.
            counterpart=local_bs
            if all(state['account_details'][c]['group']=='Depreciation' for c in flagged):counterpart={c:n for c,n in local_bs.items() if state['account_details'][c]['group']=='Accumulated depreciation'}
            if sum(counterpart.values())==-sum(flagged.values()):
                removed=counterpart
                for c,n in flagged.items():profit_adjustments[c]=profit_adjustments.get(c,0)+n
        for code,n in local_bs.items():
            category=p['mapping'].get(code,'Review');bs[category][code]=bs[category].get(code,0)+n-removed.get(code,0)
            if category=='Review':issues.append(dict(voucher=v['id'],root_voucher=root_id,branch=branch,reason='Unreviewed balance-sheet mapping: '+code,cash_movement=delta))
        if not cash_lines:
            if others:noncash_support.append(dict(voucher=v['id'],date=v['date'],branch=branch,lines=copy.deepcopy(lines),reason='No selected cash movement; excluded from direct cash flows.'))
            continue
        reviewed=next((a for a in reversed(state.get('cash_flow_allocations',[])) if a['policy_id']==p['id'] and a['voucher_id']==root_id and a['branch']==branch),None)
        if not reviewed and len({l['branch'] for l in root['lines']})==1:
            unit=root['lines'][0]['branch']
            reviewed=next((a for a in reversed(state.get('cash_flow_allocations',[])) if a['policy_id']==p['id'] and a['voucher_id']==root_id and a['branch'] in ('ALL',unit)),None)
        from . import ap
        apflows=ap.payment_flows(state,root_id,p,branch,sign)
        if reviewed:
            local=[dict(a,amount=a['amount']*sign) for a in reviewed['lines']]
            if sum(a['amount'] for a in local)!=delta:reasons.append('Saved allocation no longer agrees with this cash definition.')
        elif not others and delta==0 and _internal_transfer(lines,cash):continue  # Includes entity-wide inter-unit cash transfers.
        elif root.get('fx',{}).get('kind')=='conversion' and {root['fx']['inputs']['foreign_account'],root['fx']['inputs']['bank_account']}.issubset(cash):
            packet=root['fx'];effect=(packet['gross_inr_minor']-packet['inr_minor'])*sign;fee=-packet['fees_inr_minor']*sign
            if effect:local.append(dict(category='Exchange effects',amount=effect,label='Exchange effect on conversion of held currency'))
            if fee:local.append(dict(category=p['mapping'].get('4560','Review'),amount=fee,label='Conversion fees'))
        elif apflows is not None:local=apflows
        elif any((l['branch'],l['account']) in mixed_controls for l in lines if l['account'] not in cash):reasons.append('Shared control carries investing/financing items; review actual settlement nature.')
        elif delta and not v.get('closing'):
            categories={p['mapping'].get(c,'Review') for c in others}
            if len(categories)==1 and 'Review' not in categories:local=[dict(category=next(iter(categories)),amount=delta,label='Net cash receipt' if delta>0 else 'Net cash payment')]
            elif all((-n)*delta>0 for n in others.values()) and 'Review' not in categories:
                local=[dict(category=p['mapping'][c],amount=-n,label=accounts[c]['name']) for c,n in others.items()]
            else:reasons.append('Mixed/unknown classifications require reviewed cash allocation.')
        else:reasons.append('Composite zero-net or closing cash voucher requires review.')
        if not reasons and sum(a['amount'] for a in local)!=delta:reasons.append('Cash allocation does not reconcile.')
        if reasons:
            local=[dict(category='Review',amount=delta,label='Unclassified cash movement')];issues.append(dict(voucher=v['id'],root_voucher=root_id,branch=branch,reason=' '.join(reasons),cash_movement=delta))
        for a in local:
            if a['category']=='Review' and not reasons:issues.append(dict(voucher=v['id'],root_voucher=root_id,branch=branch,reason='Unreviewed cash classification',cash_movement=a['amount']))
            flows.append(dict(a,voucher=v['id'],root_voucher=root_id,date=v['date'],branch=branch,reference=v.get('metadata',{}).get('reference',''),review_id=reviewed['id'] if reviewed else None))
        if others and any(p['mapping'].get(c) in ('Investing','Financing') for c in others):noncash_support.append(dict(voucher=v['id'],date=v['date'],branch=branch,lines=copy.deepcopy(lines),reason='Non-operating balances and cash shown separately; review any noncash investing/financing component.'))
    totals={category:sum(f['amount'] for f in flows if f['category']==category) for category in CATEGORIES}
    working={code:-n for code,n in bs['Operating'].items()}
    adjustments={'Investing BS/cash reclassification (incl. capital creditors)':-sum(bs['Investing'].values())-totals['Investing'],'Financing BS/cash reclassification':-sum(bs['Financing'].values())-totals['Financing'],'Exchange effects removed from operating result':-totals['Exchange effects'],'Unreviewed BS/cash adjustments':-sum(bs['Review'].values())-totals['Review'],'Other exchange-classified BS movements':-sum(bs['Exchange effects'].values()),'Cash-bearing year-close transfers':special}
    indirect=profit+sum(profit_adjustments.values())+sum(working.values())+sum(adjustments.values())
    cash_difference=closing-opening-introduced-sum(totals.values());bridge=indirect-totals['Operating']
    ready=p['reviewed'] and not issues and not introduced and cash_difference==0 and bridge==0
    return dict(entity=state['settings']['entity'],registration=copy.deepcopy(state['settings']['registration']),start=start,end=end,branch=branch,scope='All operating units' if branch=='ALL' else foundation.branches(state)[branch],policy=p,opening=opening,closing=closing,introduced=introduced,profit=profit,flows=flows,totals=totals,noncash_profit=profit_adjustments,working_capital=working,adjustments=adjustments,indirect_operating=indirect,issues=issues,noncash_support=noncash_support,cash_difference=cash_difference,indirect_difference=bridge,ready=ready)


def snapshot(state,mode,start,end,branch='ALL'):
    if mode==FORECAST:
        from . import ap
        pack=ap.forecast_snapshot(state,start,start,end,branch);pack['mode']=FORECAST;return pack
    result=analyse(state,start,end,branch);rows=[]
    if mode==DIRECT:
        for category in CATEGORIES:
            positive=sum(f['amount'] for f in result['flows'] if f['category']==category and f['amount']>0);negative=sum(f['amount'] for f in result['flows'] if f['category']==category and f['amount']<0)
            rows.extend([[category,'Receipts / increases',positive],[category,'Payments / decreases',negative],[category,'Net '+category.lower(),result['totals'][category]]])
    elif mode==INDIRECT:
        rows.append(['Operating','Profit / (loss) before cash-flow adjustments',result['profit']])
        names={a['code']:a['name'] for a in state['accounts']}
        rows.extend([['Noncash P&L',code+' '+names[code],n] for code,n in result['noncash_profit'].items()])
        rows.extend([['Operating balance changes',code+' '+names[code],n] for code,n in result['working_capital'].items()])
        rows.extend([['Noncash / reclassification',label,n] for label,n in result['adjustments'].items()])
        rows.append(['Operating','Net operating cash — indirect',result['indirect_operating']])
        rows.extend([[category,'Net '+category.lower(),result['totals'][category]] for category in CATEGORIES if category!='Operating'])
    else:raise ValueError('Choose direct or indirect cash flow.')
    rows.extend([['Cash proof','Opening cash/equivalents',result['opening']],['Cash proof','Opening balances introduced during period',result['introduced']],['Cash proof','Net movement including exchange effects',sum(result['totals'].values())],['Cash proof','Closing cash/equivalents',result['closing']]])
    status='REVIEWED — arithmetic proofs passed' if result['ready'] else 'DRAFT — policy, mapping or cash-flow review incomplete'
    return dict(entity=result['entity'],registration=result['registration'],mode=mode,start=start,end=end,branch=branch,scope=result['scope'],prepared=datetime.now(timezone(timedelta(hours=5,minutes=30))).isoformat(timespec='seconds'),currency='INR',columns=['Category','Cash-flow item','Amount INR'],money_columns=[2],rows=rows,controls={'Cash reconciliation difference':result['cash_difference'],'Direct/indirect operating difference':result['indirect_difference']},status=status,note=status+'. Report-wide policy as at period end is applied consistently to the whole period. Net bank-level receipts/payments are shown unless reviewed gross allocations are supplied. Operating balance changes can include noncash items; full voucher support is retained. Inter-unit cash transfers are excluded at entity scope. This is a working statement; actual cash-equivalent/overdraft/interest classification and final Ind AS 7 presentation require accountant review.',cash_flow=result)


def support_snapshot(state,start,end,branch='ALL'):
    result=analyse(state,start,end,branch);pack=snapshot(state,DIRECT,start,end,branch)
    pack.update(mode='Cash-flow voucher support',columns=['Date','Voucher','Reference','Category','Description','Amount INR','Review ID'],money_columns=[5],rows=[[f['date'],f['voucher'],f['reference'],f['category'],f['label'],f['amount'],f['review_id'] or 'Automatic under policy'] for f in result['flows']])
    return pack


def noncash_snapshot(state,start,end,branch='ALL'):
    pack=snapshot(state,DIRECT,start,end,branch);result=pack['cash_flow'];names={a['code']:a['name'] for a in state['accounts']};rows=[]
    for record in result['noncash_support']:
        for line in record['lines']:
            code=line['account'];category='Cash/equivalent' if code in result['policy']['cash_accounts'] else result['policy']['mapping'].get(code,'Review')
            rows.append([record['date'],record['voucher'],foundation.branches(state)[line['branch']],code+' '+names[code],category,line['debit'],line['credit'],record['reason']])
    pack.update(mode='Noncash and mixed voucher notes',columns=['Date','Voucher','Unit','Ledger','Classification','Debit INR','Credit INR','Source note'],money_columns=[5,6],rows=rows)
    return pack


def policy_snapshot(state,start,end,branch='ALL'):
    pack=snapshot(state,DIRECT,start,end,branch);p=pack['cash_flow']['policy'];rows=[]
    for a in state['accounts']:
        code=a['code'];rows.append([code,a['name'],'Yes' if code in p['cash_accounts'] else 'No',p['mapping'].get(code,'Review'),'Yes' if code in p['noncash_accounts'] else 'No'])
    pack.update(mode='Cash-flow classification policy',columns=['Code','Ledger','Included in cash','Category','Noncash P&L adjustment'],money_columns=[],rows=rows,note=pack['note']+' Policy ID: '+str(p['id'])+' | Effective: '+p['effective']+' | Basis: '+p['note'])
    return pack


def branch_snapshot(state,start,end):
    names=foundation.branches(state);entity=analyse(state,start,end,'ALL');units={code:analyse(state,start,end,code) for code in names};pack=snapshot(state,DIRECT,start,end,'ALL');rows=[]
    for key,label in [('opening','Opening cash'),('introduced','Balance introductions'),('closing','Closing cash')]:
        values=[units[c][key] for c in names];rows.append([label,*values,sum(values),entity[key],entity[key]-sum(values)])
    for category in CATEGORIES:
        values=[units[c]['totals'][category] for c in names];rows.append([category,*values,sum(values),entity['totals'][category],entity['totals'][category]-sum(values)])
    pack.update(mode='Cash-flow branch reconciliation',columns=['Measure',*names.values(),'Sum units','Entity','Reclass / difference'],money_columns=list(range(1,len(names)+4)),rows=rows,controls={'Opening cash difference':rows[0][-1],'Closing cash difference':rows[2][-1]},note=pack['note']+' Branch funding and cross-unit settlement can reclassify financing to investing/operating at entity scope; categories need not sum without these eliminations. Cash opening/closing must sum. Branch statements retain their own review requirements.')
    return pack


def export(state,start,end,branch,path,kind):
    from . import financial_reports
    packs=[snapshot(state,mode,start,end,branch) for mode in (DIRECT,INDIRECT)]+[support_snapshot(state,start,end,branch),noncash_snapshot(state,start,end,branch),policy_snapshot(state,start,end,branch)]
    if branch=='ALL':packs.append(branch_snapshot(state,start,end))
    from . import ap
    forecastend=(datetime.fromisoformat(end).date()+timedelta(days=90)).isoformat()
    packs.append(ap.forecast_snapshot(state,end,end,forecastend,branch))
    for p in packs:p['prepared']=packs[0]['prepared']
    if kind=='xlsx':financial_reports.export_pack_xlsx(packs,path)
    elif kind=='pdf':financial_reports.export_pdf(packs,path)
    elif kind=='json':Path(path).write_text(json.dumps(dict(packs[0]['cash_flow'],ap_forecast=dict(asof=end,start=end,end=forecastend,rows=ap.forecast(state,end,end,forecastend,branch))),ensure_ascii=False,indent=2),encoding='utf-8')
    else:raise ValueError('Choose Excel, PDF or JSON.')

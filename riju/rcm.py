"""Reviewed domestic RCM: accrual, electronic-cash deposit, discharge and ITC."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import uuid
from . import core,foundation,gst,tax

PARTS=('cgst','sgst','igst')


def _masters(state):
    mapping=state['gst_rcm_ledgers']
    for key,label,kind,group,start,end in [
        ('pending','RCM tax pending ITC review','Asset','Other assets',1180,1199),
        *[(f'cash_{p}','GST electronic cash — '+p.upper(),'Asset','Other assets',1180,1199) for p in PARTS],
        *[(f'payable_{p}','GST RCM payable — '+p.upper(),'Liability','Other liabilities',2230,2299) for p in PARTS]]:
        if key in mapping:continue
        used={a['code'] for a in state['accounts']};code=next((str(n) for n in range(start,end+1) if str(n) not in used),None)
        if code is None:raise ValueError('No free control-ledger code; free an unused code in the RCM range first.')
        foundation.save_account(state,code,label,kind,group);mapping[key]=code
    return mapping


def _context(state,values):
    on=tax.day(values.get('date',''));branch=values.get('branch');registration=gst._gstin(values.get('registration',''))
    if branch not in foundation.branches(state,True):raise ValueError('Select an active operating unit.')
    unit=state['branches'][branch];entity=state['settings']['registration'].get('gstin','')
    if unit.get('gstin') and unit['gstin']!=registration or unit.get('state_code') and unit['state_code']!=registration[:2]:raise ValueError('RCM registration differs from this branch registration/state.')
    if not unit.get('gstin') and entity and entity!=registration:raise ValueError('Configure the branch GSTIN before using a different registration.')
    reference=str(values.get('reference','')).strip();narration=str(values.get('narration','')).strip()
    if not reference or not narration:raise ValueError('Enter the supporting reference and narration/review reason.')
    return dict(date=on,branch=branch,registration=registration,reference=reference,narration=narration)


def _purchase(state,values):
    original=next((r for r in state['gst_rcm_records'] if r['id']==values.get('purchase_id') and r['stage']=='Purchase'),None)
    if original is None:raise ValueError('Select an RCM purchase first.')
    return original


def _money(value):return int(Decimal(tax.decimal_text(value or '0'))*100)


def _plan(state,stage,values):
    mapping=_masters(state)
    if stage in ('Discharge','Claim'):
        purchase=_purchase(state,values);ctx=_context(state,dict(values,branch=purchase['branch'],registration=purchase['registration']))
        if ctx['date']<purchase['date']:raise ValueError('The action cannot predate its RCM purchase.')
    else:ctx=_context(state,values)
    r=dict(ctx,id=str(uuid.uuid4()),stage=stage,lines=[])
    def add(code,amount,debit):
        if amount:r['lines'].append(dict(account=code,branch=r['branch'],debit=amount if debit else 0,credit=0 if debit else amount))
    if stage=='Purchase':
        rule=tax.resolve_rule(state,values.get('rule_key',''),r['date']);basis=str(values.get('rcm_basis','')).strip()
        if rule['family']!='GST' or rule['treatment']!='Taxable' or not rule['reviewed'] or not basis:raise ValueError('Select a reviewed taxable GST rule and record the verified RCM applicability basis.')
        supplier=gst._gstin(values.get('supplier_gstin',''),True);supplier_name=str(values.get('supplier_name','')).strip();identity=supplier or gst._reference(supplier_name)
        if not identity:raise ValueError('Enter the unregistered supplier name; a blank GSTIN does not identify the supplier.')
        supplier_state=str(values.get('supplier_state','')).strip();pos=str(values.get('place_of_supply','')).strip()
        for value in (supplier_state,pos):foundation.optional_registration({'state_code':value})
        if not supplier_state or not pos or supplier and supplier[:2]!=supplier_state or supplier==r['registration']:raise ValueError('Enter reviewed supplier/place-of-supply states; supplier GSTIN must agree when present. Self-transfers need separate review.')
        if rule['party_category']!='Any':raise ValueError('Party-specific rule applicability needs separate review.')
        expected=values.get('claim_expected')
        if type(expected)!=bool:raise ValueError('Explicitly choose whether ITC is expected after payment and review.')
        amounts=gst.split(rule,values.get('amount',''),False,supplier_state==pos)
        if not sum(amounts[p] for p in PARTS):raise ValueError('RCM tax rounds to zero; review the amount/rate.')
        if expected and supplier_state==pos and pos!=r['registration'][:2]:raise ValueError('Out-of-state intra-state tax needs separate ITC review.')
        accounts={a['code']:a for a in state['accounts']};cost=values.get('account');counter=values.get('counter_account')
        if cost not in accounts or accounts[cost]['kind'] not in ('Expense','Asset') or state['account_details'][cost]['group'] not in ('PPE','Inventory','CWIP','Medical costs','Professional fees','Employee benefits','Administration','Finance costs','Other expenses'):raise ValueError('Select a genuine expense, inventory, CWIP or PPE cost ledger.')
        if counter not in accounts or counter==cost or state['account_details'][counter]['group'] not in ('Cash and bank','Trade payables','Other liabilities') or counter in state.get('foreign_accounts',{}):raise ValueError('Select an INR supplier payment/payable control ledger.')
        if rule['ledger_codes'] and cost not in rule['ledger_codes']:raise ValueError('The cost ledger is not linked to this rule.')
        if any(x['stage']=='Purchase' and x['registration']==r['registration'] and x.get('supplier_identity',x.get('supplier_gstin'))==identity and gst._reference(x['reference'])==gst._reference(r['reference']) and core.financial_year(x['date'])==core.financial_year(r['date']) for x in state['gst_rcm_records']):raise ValueError('This RCM purchase reference already exists for the supplier/registration/year.')
        if supplier and any(d['kind']=='Purchase' and d['registration']==r['registration'] and d['counterparty_gstin']==supplier and gst._reference(d['reference'])==gst._reference(r['reference']) and core.financial_year(d['date'])==core.financial_year(r['date']) for d in state.get('gst_documents',[])):raise ValueError('This supplier invoice is already recorded in the forward-charge GST workflow.')
        r.update(rule=rule,rcm_basis=basis,supplier_gstin=supplier,supplier_name=supplier_name,supplier_identity=identity,supplier_state=supplier_state,place_of_supply=pos,claim_expected=expected,account=cost,counter_account=counter,amounts=amounts)
        add(cost,amounts['base'] if expected else amounts['total'],True);add(counter,amounts['base'],False)
        if expected:add(mapping['pending'],sum(amounts[p] for p in PARTS),True)
        for p in PARTS:add(mapping['payable_'+p],amounts[p],False)
    elif stage=='Deposit':
        amounts={p:_money(values.get(p,'')) for p in PARTS};bank=values.get('bank_account')
        if not sum(amounts.values()):raise ValueError('Enter a positive component allocation for the electronic-cash deposit.')
        from .reconciliation import bank_accounts
        if bank not in {a['code'] for a in bank_accounts(state)}:raise ValueError('Select an INR bank ledger for the actual deposit.')
        if any(x['stage']=='Deposit' and x['registration']==r['registration'] and gst._reference(x['reference'])==gst._reference(r['reference']) for x in state['gst_rcm_records']):raise ValueError('This deposit/challan reference already exists for the registration.')
        r.update(amounts=amounts,bank_account=bank)
        for p in PARTS:add(mapping['cash_'+p],amounts[p],True)
        add(bank,sum(amounts.values()),False)
    elif stage in ('Discharge','Claim'):
        amounts={p:purchase['amounts'][p] for p in PARTS};r.update(purchase_id=purchase['id'],purchase_voucher_id=purchase['voucher_id'],amounts=amounts)
        if stage=='Discharge':
            # This records actual electronic cash utilisation, not a mere bank challan deposit.
            for p in PARTS:add(mapping['payable_'+p],amounts[p],True);add(mapping['cash_'+p],amounts[p],False)
            balances=core.balances(state,r['date'],r['branch'])
            if any(balances[mapping['cash_'+p]]<amounts[p] for p in PARTS):raise ValueError('Electronic-cash books do not cover this discharge; record the actual cash deposit first.')
        else:
            if not purchase['claim_expected'] or values.get('eligibility_reviewed') is not True:raise ValueError('ITC was not expected, or eligibility/payment conditions have not been explicitly reviewed.')
            r['eligibility_reviewed']=True
            balances=core.balances(state,r['date'],r['branch'])
            if balances[mapping['pending']]<sum(amounts.values()):raise ValueError('The pending-ITC ledger does not cover this claim; reconcile manual entries first.')
            for code,p in zip(gst.INPUT,PARTS):add(code,amounts[p],True)
            add(mapping['pending'],sum(amounts.values()),False)
    else:raise ValueError('Choose Purchase, Deposit, Discharge or Claim.')
    _check(state,proposed=r)
    if stage=='Claim':
        roots=gst._roots(state);net={}
        for v in state['vouchers']:
            if v['date']<=r['date']:
                root,sign=roots[v['id']];net[root]=net.get(root,0)+sign
        discharge=next(x for x in state['gst_rcm_records'] if x['stage']=='Discharge' and x['purchase_id']==r['purchase_id'] and net.get(x['voucher_id'],0))
        r['discharge_id']=discharge['id'];r['discharge_voucher_id']=discharge['voucher_id']
    return r


def _check(state,proposed=None,reversal=None):
    records={r['id']:r for r in state.get('gst_rcm_records',[])};by_voucher={r['voucher_id']:r for r in records.values()};roots=gst._roots(state);days={}
    for v in state['vouchers']:
        root,sign=roots[v['id']];r=by_voucher.get(root)
        if r:
            bucket=days.setdefault(v['date'],{});bucket[r['id']]=bucket.get(r['id'],0)+sign
    if proposed:records[proposed['id']]=proposed;days.setdefault(proposed['date'],{})[proposed['id']]=1
    if reversal:
        vid,on=reversal
        if vid not in roots:return
        root,sign=roots[vid];r=by_voucher.get(root)
        if r:
            bucket=days.setdefault(on,{});bucket[r['id']]=bucket.get(r['id'],0)-sign
    active={}
    for on,changes in sorted(days.items()):
        for key,n in changes.items():active[key]=active.get(key,0)+n
        cash={};actions={}
        for key,n in active.items():
            if n not in (0,1):raise ValueError('Invalid RCM reversal chain.')
            if not n:continue
            r=records[key]
            if r['stage'] in ('Discharge','Claim'):
                parent=records[r['purchase_id']]
                if not active.get(parent['id']):raise ValueError('Reverse dependent RCM claims/discharges before the purchase.')
                k=(r['purchase_id'],r['stage']);actions[k]=actions.get(k,0)+1
                if actions[k]>1:raise ValueError('This RCM purchase already has an active '+r['stage'].lower()+'. Full-document actions cannot be duplicated.')
            if r['stage'] in ('Deposit','Discharge'):
                k=(r['branch'],r['registration']);amounts=cash.setdefault(k,{p:0 for p in PARTS})
                for p in PARTS:amounts[p]+=r['amounts'][p]*(1 if r['stage']=='Deposit' else -1)
        if any(n<0 for amounts in cash.values() for n in amounts.values()):raise ValueError('RCM electronic cash would be insufficient on '+on+'. Review prior/future discharge allocations.')
        for key,n in active.items():
            if n and records[key]['stage']=='Claim' and not actions.get((records[key]['purchase_id'],'Discharge')):raise ValueError('ITC requires an active cash discharge first; reverse the claim before its discharge.')


def prepare(state,stage,values):
    candidate=copy.deepcopy(state);record=_plan(candidate,stage,values)
    core.post(candidate,record['date'],record['narration'],record['lines'],metadata={'type':'Adjustment','reference':record['reference']})
    return dict(record=record,control_ledgers=copy.deepcopy(candidate['gst_rcm_ledgers']),new_accounts=[a for a in candidate['accounts'] if a['code'] not in {x['code'] for x in state['accounts']}],scope='Reviewed domestic RCM working entry. A deposit is not liability discharge; ITC requires actual cash utilisation and separate eligibility review.')


def post(state,stage,values):
    if values.get('confirmed') is not True:raise ValueError('Review the RCM applicability, source documents and journal before approval.')
    candidate=copy.deepcopy(state);record=_plan(candidate,stage,values)
    voucher=core.post(candidate,record['date'],record['narration'],record['lines'],metadata={'type':'Adjustment','reference':record['reference']})
    record['voucher_id']=voucher['id'];candidate['gst_rcm_records'].append(record);core.add_audit(candidate,'GST_RCM_POSTED',copy.deepcopy(record))
    state.clear();state.update(candidate);return copy.deepcopy(record)


def validate_reversal(state,voucher_id,on):_check(state,reversal=(voucher_id,on))


def movements(state,start,through,branch='ALL'):
    tax.day(start);tax.day(through)
    if start>through:raise ValueError('Start follows end date.')
    roots=gst._roots(state);by_voucher={r['voucher_id']:r for r in state.get('gst_rcm_records',[])};result=[]
    for v in state['vouchers']:
        root,sign=roots[v['id']];r=by_voucher.get(root)
        if r and start<=v['date']<=through and (branch=='ALL' or branch==r['branch']):result.append(dict(copy.deepcopy(r),movement_date=v['date'],movement_voucher=v['id'],sign=sign))
    return result


def report(state,start,through,branch='ALL'):
    rows=movements(state,start,through,branch);codes=set(state.get('gst_rcm_ledgers',{}).values());expected={c:0 for c in codes};actual={c:0 for c in codes}
    for r in rows:
        for l in r['lines']:
            if l['account'] in expected:expected[l['account']]+=(l['debit']-l['credit'])*r['sign']
    for v in state['vouchers']:
        if start<=v['date']<=through:
            for l in v['lines']:
                if l['account'] in actual and (branch=='ALL' or l['branch']==branch):actual[l['account']]+=l['debit']-l['credit']
    from datetime import date,timedelta
    opening=core.balances(state,(date.fromisoformat(start)-timedelta(days=1)).isoformat(),branch);closing=core.balances(state,through,branch)
    roots=gst._roots(state);net={}
    for v in state['vouchers']:
        if v['date']<=through:
            root,sign=roots[v['id']];net[root]=net.get(root,0)+sign
    active=[r for r in state.get('gst_rcm_records',[]) if net.get(r['voucher_id'],0) and (branch=='ALL' or r['branch']==branch)]
    discharged={r['purchase_id'] for r in active if r['stage']=='Discharge'};claimed={r['purchase_id'] for r in active if r['stage']=='Claim'}
    outstanding=[dict(purchase_id=r['id'],reference=r['reference'],registration=r['registration'],branch=r['branch'],tax_due={p:0 if r['id'] in discharged else r['amounts'][p] for p in PARTS},itc_pending=0 if not r['claim_expected'] or r['id'] in claimed else sum(r['amounts'][p] for p in PARTS)) for r in active if r['stage']=='Purchase']
    return dict(entity=state['settings']['entity'],start=start,through=through,branch=branch,records=rows,opening_balances={c:opening[c] for c in codes},closing_balances={c:closing[c] for c in codes},outstanding=outstanding,control_ledgers=copy.deepcopy(state.get('gst_rcm_ledgers',{})),ledger_movements=actual,unclassified={k:actual[k]-expected[k] for k in actual},scope='RCM accrual, cash deposits, actual cash discharges and separately reviewed ITC. Full-document discharge/claim only; filing/legal eligibility and supplier payment reconciliation are separate.')


def export(report,path):Path(path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

"""Reviewed resident-payee TDS bookkeeping, cumulative assessment and challans."""
import copy
from decimal import Decimal,ROUND_HALF_UP
from datetime import datetime,timezone,timedelta
import uuid
import re
import json
from pathlib import Path
from . import core,foundation,tax,gst,ledgers,financial_reports


METHODS=('Whole eligible base','Excess over annual threshold','Current transaction only')


def minor(value):return int(Decimal(tax.decimal_text(value or '0'))*100)


def _net(state,on=None,reversal=None):
    roots=gst._roots(state);result={}
    for v in state['vouchers']:
        if on and v['date']>on:continue
        root,sign=roots[v['id']];result[root]=result.get(root,0)+sign
    if reversal and (not on or reversal[1]<=on):
        root,sign=roots.get(reversal[0],(None,0));result[root]=result.get(root,0)-sign
    return result


def active(state,record,on=None,net=None):
    if on and record['date']>on:return False
    if record.get('void_date') and (not on or record['void_date']<=on):return False
    return (net if net is not None else _net(state,on)).get(record.get('voucher_id'),0)==1 if record.get('voucher_id') else True


def _control(state,section,requested=None):
    mapping=state['tds_ledgers']
    if requested:
        account=next((a for a in state['accounts'] if a['code']==requested and a['kind']=='Liability'),None)
        if not account or state['account_details'][requested]['group']!='TDS payable':raise ValueError('Select a liability ledger grouped as TDS payable.')
        if section in mapping and mapping[section]!=requested:raise ValueError('This section already uses another historical control ledger; retain it and reconcile manual balances.')
        mapping[section]=requested
    if section in mapping:return mapping[section]
    base={'194J':'2100','194C':'2110','194I':'2120'}.get(section)
    existing=next((a for a in state['accounts'] if a['code']==base and a['kind']=='Liability' and a['name']=='TDS payable — '+section),None)
    if existing and state['account_details'][base]['group']=='TDS payable':code=base
    else:
        used={a['code'] for a in state['accounts']};code=next((str(n) for n in range(2130,2200) if str(n) not in used),None)
        if code is None:raise ValueError('No free TDS control code in 2130–2199.')
        foundation.save_account(state,code,'TDS payable — '+section,'Liability','TDS payable')
    mapping[section]=code;return code


def _party_ids(state,party,on):
    ids={party['party_id']};pan=party['registration']['pan']
    if pan:
        for pid in {p['party_id'] for p in tax.parties(state)}:
            try:p=tax.resolve_party(state,pid,on)
            except ValueError:continue
            if p['registration']['pan']==pan:ids.add(pid)
    return ids


def _group(rule):return rule.get('threshold_group') or rule['section']


def _tax(base,rule):
    value=Decimal(base)*Decimal(rule['rate'])/100
    quantum=Decimal('100') if rule.get('tds_rounding','Paise')=='Whole rupee' else Decimal('1')
    return int((value/quantum).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*quantum)


def assess(state,rule,party,on,base=0,posted_through=None):
    ids=_party_ids(state,party,on);year=core.financial_year(on);posted_through=posted_through or on;net=_net(state,posted_through)
    prior=[r for r in state['tds_records'] if r['kind']!='Challan' and r['section']==rule['section'] and r['group']==_group(rule) and r['year']==year and r['party_id'] in ids and r.get('tax_date',r['date'])<=on and active(state,r,posted_through,net)]
    entries=[r for r in prior if r['kind']!='Adjustment']
    if base:entries.append(dict(base=base,rule=rule,mode='Automatic',date=on,_new=True))
    aggregate=sum(r['base'] for r in entries);withheld=sum(r['withheld'] for r in prior)
    target=sum(r.get('manual_target',0) for r in prior if r['kind']=='Adjustment' and r['mode']=='Reviewed manual');running=0
    for entry in sorted(enumerate(entries),key=lambda p:(p[1].get('tax_date',p[1]['date']),p[0])):
        r=entry[1];b=r['base'];rr=r.get('rule',rule);running+=b
        if r.get('kind')=='Opening' or r.get('mode')=='Reviewed manual':target+=r.get('manual_target',r['withheld']);continue
        threshold=lambda key:minor(rr.get(key)) if rr.get(key) is not None else None
        single=threshold('single_threshold');annual=threshold('annual_threshold');basis=rr['threshold_basis'];compare=lambda x,y:x>=y if rr.get('threshold_trigger','Exceeds')=='At least' else x>y
        if rr['treatment']=='Not applicable':continue
        if basis=='Review required':raise ValueError('Configure the threshold basis before automatic TDS assessment.')
        if basis in ('Per payment','Either threshold') and single is None or basis in ('Financial-year aggregate','Either threshold') and annual is None:raise ValueError('Required threshold is unknown; blank is not zero.')
        hit=(basis in ('Per payment','Either threshold') and compare(b,single)) or (basis in ('Financial-year aggregate','Either threshold') and compare(aggregate,annual))
        if not hit:continue
        method=rr.get('deduction_method','Whole eligible base')
        if method=='Excess over annual threshold':
            if annual is None:raise ValueError('Excess-base assessment requires a known annual threshold.')
            eligible=max(0,running-annual)-max(0,running-b-annual)
        elif method=='Current transaction only':
            if not r.get('_new'):
                target+=r.get('tax_target',r['withheld']);continue
            eligible=b
        else:eligible=b
        target+=_tax(eligible,rr)
    return dict(base_before=aggregate-base,base_after=aggregate,withheld_before=withheld,target=target,due=target-withheld,source_records=[r['id'] for r in prior],party_ids=sorted(ids),year=year)


def _base_context(state,values):
    on=tax.day(values.get('date',''));branch=values.get('branch');reference=str(values.get('reference','')).strip()
    if branch not in foundation.branches(state,True) or not reference:raise ValueError('Select an active unit and a source reference.')
    return dict(id=str(uuid.uuid4()),date=on,branch=branch,reference=reference,narration=str(values.get('narration','')).strip())


def _deduction(state,kind,values):
    r=_base_context(state,values);point=tax.day(values.get('tax_date') or r['date'])
    if point>r['date']:raise ValueError('The tax-point date cannot follow the posting date.')
    rule=tax.resolve_rule(state,values.get('rule_key',''),point);party=tax.resolve_party(state,values.get('party_id',''),point);mode=values.get('mode','Automatic')
    if rule['family']!='TDS' or not rule['reviewed'] or not party['active']:raise ValueError('Select an active party and a reviewed TDS rule effective on the tax-point date.')
    if mode not in ('Automatic','Reviewed manual'):raise ValueError('Choose Automatic or Reviewed manual.')
    if mode=='Automatic' and (party['category']=='Unknown' or not party['registration']['pan']):raise ValueError('Automatic deduction requires known party category/PAN. Record reviewed exception rules or a manual amount/reason; no special rate is guessed.')
    if rule['party_category']!='Any' and rule['party_category']!=party['category']:raise ValueError('Party category does not match this TDS rule.')
    if values.get('resident_reviewed') is not True:raise ValueError('Confirm resident-payee/section applicability; nonresident withholding needs its own reviewed treatment.')
    reason=str(values.get('review_reason','')).strip()
    if not r['narration']:raise ValueError('Enter the journal/source narration.')
    base=minor(values.get('base'));gross=minor(values.get('gross'))
    if kind=='Adjustment':base=gross=0
    elif base<=0 or gross<base:raise ValueError('Enter a positive deduction base and gross amount at least equal to the base. Exclude GST from the base only when legally appropriate.')
    if any(x['kind']!='Challan' and x.get('party_id') in _party_ids(state,party,point) and x['section']==rule['section'] and gst._reference(x['reference'])==gst._reference(r['reference']) and x['year']==core.financial_year(point) for x in state['tds_records']):raise ValueError('This party/section/reference/year already exists; use an explicit correction reference.')
    if mode=='Reviewed manual':
        if not reason:raise ValueError('Enter the verified reason/source for a manual deduction amount.')
        withheld=minor(values.get('manual_tax'));assessment=dict(due=withheld,target=None,scope='Reviewed manual amount; no automatic exception/certificate/non-PAN determination.')
    else:
        assessment=assess(state,rule,party,point,base,r['date']);withheld=max(0,assessment['due'])
    manual_target=minor(values['manual_target']) if mode=='Reviewed manual' and str(values.get('manual_target','')).strip() else withheld
    if kind!='Adjustment' and manual_target>gross:raise ValueError('The reviewed target for this source base cannot exceed its gross amount; use a separate catch-up source when needed.')
    if kind=='Adjustment' and withheld<=0:raise ValueError('No positive catch-up is due. Use a dated reversal/correction for over-deduction.')
    if kind!='Adjustment' and withheld>gross:raise ValueError('Catch-up exceeds this gross amount; use a separate catch-up deduction against the payable instead.')
    accounts={a['code']:a for a in state['accounts']};counter=values.get('counter_account','');cost=values.get('account','')
    allowed=('Trade payables','Other liabilities') if kind in ('Existing payable','Adjustment') else ('Trade payables','Other liabilities','Cash and bank')
    if counter not in accounts or state['account_details'][counter]['group'] not in allowed or counter in state.get('foreign_accounts',{}):raise ValueError('Select an appropriate INR payment/payable control; existing-payable and catch-up deductions require a payable ledger.')
    if kind=='Expense':
        if cost not in accounts or accounts[cost]['kind'] not in ('Asset','Expense') or state['account_details'][cost]['group'] in ('Cash and bank','GST input','Payment clearing','Patient control','TDS payable') or cost in state.get('gst_rcm_ledgers',{}).values():raise ValueError('Select the genuine expense/inventory/PPE/CWIP cost ledger.')
        if rule['ledger_codes'] and cost not in rule['ledger_codes']:raise ValueError('The cost account is not linked to this rule.')
    source_voucher=values.get('source_voucher','')
    if kind=='Existing payable':
        source=next((v for v in state['vouchers'] if v['id']==source_voucher),None)
        if not source or source['date']>r['date'] or _net(state,r['date']).get(source_voucher,0)!=1:raise ValueError('Choose an active original expense/payable voucher on or before the tax date.')
        capacity=sum(l['credit']-l['debit'] for l in source['lines'] if l['branch']==r['branch'] and l['account']==counter)
        used=sum(x['gross'] for x in state['tds_records'] if x.get('source_voucher')==source_voucher and active(state,x,r['date']))
        if used+gross>capacity:raise ValueError('Linked gross exceeds the unrecorded portion of the source payable voucher.')
    ledger=_control(state,rule['section'],values.get('tds_account',''));
    if kind=='Register existing deduction':
        source=next((v for v in state['vouchers'] if v['id']==source_voucher),None)
        if not source or source['date']>r['date'] or _net(state,r['date']).get(source_voucher,0)!=1 or withheld<=0:raise ValueError('Select an active existing TDS-credit voucher and a positive actual deduction.')
        credit=sum(l['credit']-l['debit'] for l in source['lines'] if l['branch']==r['branch'] and l['account']==ledger)
        used=sum(x['withheld'] for x in state['tds_records'] if x['kind']=='Register existing deduction' and x.get('source_voucher')==source_voucher and x['branch']==r['branch'] and x['tds_account']==ledger and active(state,x,r['date']))
        if used+withheld>credit:raise ValueError('Registered tax exceeds the unregistered TDS credit in this source voucher.')
    r.update(kind=kind,rule=rule,party=party,party_id=party['party_id'],section=rule['section'],group=_group(rule),year=core.financial_year(point),tax_date=point,base=base,tax_target=_tax(base,rule) if withheld else 0,gross=gross,withheld=withheld,manual_target=manual_target,mode=mode,review_reason=reason,resident_reviewed=True,account=cost,counter_account=counter,source_voucher=source_voucher,tds_account=ledger,assessment=assessment,lines=[])
    def line(code,n,debit):
        if n:r['lines'].append(dict(account=code,branch=r['branch'],debit=n if debit else 0,credit=0 if debit else n))
    if kind=='Expense':line(cost,gross,True);line(counter,gross-withheld,False)
    elif kind!='Register existing deduction':line(counter,withheld,True)
    if kind!='Register existing deduction':line(ledger,withheld,False)
    return r


def _challan(state,values):
    r=_base_context(state,values);bank=values.get('bank_account','');from .reconciliation import bank_accounts
    if bank not in {a['code'] for a in bank_accounts(state)}:raise ValueError('Select an INR bank ledger.')
    if not r['narration'] or not values.get('rows'):raise ValueError('Enter the payment narration and section/unit/year allocations.')
    if any(x['kind']=='Challan' and gst._reference(x['reference'])==gst._reference(r['reference']) for x in state['tds_records']):raise ValueError('This challan/payment reference already exists.')
    rows=[];lines=[];total=0
    for source in values['rows']:
        section=str(source.get('section','')).strip().upper();branch=source.get('branch');year=int(source.get('year',0));amount=minor(source.get('tax'))
        if not re.fullmatch(r'[0-9]{3}[A-Z]{0,3}',section) or branch not in foundation.branches(state,True) or year<1900 or year>9998 or amount<=0:raise ValueError('Each tax row needs a valid section, unit, financial-year start and positive tax amount.')
        code=_control(state,section);rows.append(dict(section=section,branch=branch,year=year,tax=amount,tds_account=code));lines.extend([dict(account=code,branch=branch,debit=amount,credit=0),dict(account=bank,branch=branch,debit=0,credit=amount)]);total+=amount
    charges=minor(values.get('interest'))+minor(values.get('fee'))
    if charges:
        code=values.get('charge_account');a=next((a for a in state['accounts'] if a['code']==code),None)
        if not a or a['kind']!='Expense':raise ValueError('Select a separate expense account for interest/late fees.')
        lines.extend([dict(account=code,branch=r['branch'],debit=charges,credit=0),dict(account=bank,branch=r['branch'],debit=0,credit=charges)])
    r.update(kind='Challan',rows=rows,bank_account=bank,interest=minor(values.get('interest')),fee=minor(values.get('fee')),charge_account=values.get('charge_account',''),total=total+charges,lines=lines)
    return r


def prepare(state,kind,values):
    candidate=copy.deepcopy(state)
    if kind not in ('Expense','Existing payable','Register existing deduction','Adjustment','Challan'):raise ValueError('Choose a supported TDS action.')
    r=_challan(candidate,values) if kind=='Challan' else _deduction(candidate,kind,values)
    if r['lines']:core.post(candidate,r['date'],r['narration'],r['lines'],metadata={'type':'Adjustment','reference':r['reference']})
    return r


def post(state,kind,values):
    if values.get('confirmed') is not True:raise ValueError('Review the tax point, section, base, rate, thresholds and journal before approval.')
    candidate=copy.deepcopy(state)
    if kind not in ('Expense','Existing payable','Register existing deduction','Adjustment','Challan'):raise ValueError('Choose a supported TDS action.')
    r=_challan(candidate,values) if kind=='Challan' else _deduction(candidate,kind,values)
    r['voucher_id']=core.post(candidate,r['date'],r['narration'],r['lines'],metadata={'type':'Adjustment','reference':r['reference']})['id'] if r['lines'] else None
    candidate['tds_records'].append(r);core.add_audit(candidate,'TDS_RECORDED',copy.deepcopy(r));_check(candidate)
    state.clear();state.update(candidate);return copy.deepcopy(r)


def _allocation_active(a,on):return a['date']<=on and (not a.get('undo_date') or a['undo_date']>on)


def _check(state,reversal=None):
    by_id={r['id']:r for r in state.get('tds_records',[])}
    if not by_id:return
    roots=gst._roots(state);relevant={r.get(k) for r in by_id.values() for k in ('voucher_id','source_voucher') if r.get(k)}
    if reversal and roots.get(reversal[0],(None,0))[0] not in relevant:return
    dates={r['date'] for r in by_id.values()}
    dates|={v['date'] for v in state['vouchers'] if roots[v['id']][0] in relevant};dates|={a[k] for a in state.get('tds_allocations',[]) for k in ('date','undo_date') if a.get(k)}
    dates|={r['void_date'] for r in by_id.values() if r.get('void_date')}
    if reversal:dates.add(reversal[1])
    for on in sorted(dates):
        net=_net(state,on,reversal);doc_used={};row_used={}
        for a in state.get('tds_allocations',[]):
            if not _allocation_active(a,on):continue
            doc=by_id[a['document_id']];payment=by_id[a['payment_id']]
            if not active(state,doc,on,net) or not active(state,payment,on,net):raise ValueError('Undo dated challan allocations before reversing/voiding a linked deduction or payment.')
            row=payment['rows'][a['row_index']]
            if (doc['section'],doc['branch'],doc['year'])!=(row['section'],row['branch'],row['year']):raise ValueError('Challan allocation section, unit and financial year must match the deduction.')
            doc_used[doc['id']]=doc_used.get(doc['id'],0)+a['amount'];key=(payment['id'],a['row_index']);row_used[key]=row_used.get(key,0)+a['amount']
            if doc_used[doc['id']]>doc['withheld'] or row_used[key]>row['tax']:raise ValueError('Challan allocation exceeds the remaining deduction or payment tax. Interest/fees cannot settle TDS.')
        source_used={}
        for r in by_id.values():
            if active(state,r,on,net) and r.get('source_voucher'):
                key=(r['source_voucher'],r['branch'],r['tds_account'] if r['kind']=='Register existing deduction' else r['counter_account']);source_used[key]=source_used.get(key,0)+(r['withheld'] if r['kind']=='Register existing deduction' else r['gross'])
                v=next(v for v in state['vouchers'] if v['id']==key[0]);capacity=sum(l['credit']-l['debit'] for l in v['lines'] if l['branch']==key[1] and l['account']==key[2])
                if source_used[key]>capacity:raise ValueError('Source payable gross would be reused by backdated/future TDS records.')
            if active(state,r,on,net) and r.get('source_voucher') and net.get(r['source_voucher'],0)!=1:raise ValueError('Reverse/void the TDS treatment before reversing its source payable voucher.')


def allocate(state,document_id,payment_id,row_index,amount,on):
    tax.day(on);n=minor(amount)
    if n<=0:raise ValueError('Allocate a positive tax amount.')
    candidate=copy.deepcopy(state);records={r['id']:r for r in candidate['tds_records']};d=records[document_id];p=records[payment_id]
    if d['kind']=='Challan' or p['kind']!='Challan' or type(row_index)!=int or not 0<=row_index<len(p['rows']):raise ValueError('Choose a deduction and valid challan tax row.')
    if on<max(d['date'],p['date']):raise ValueError('Allocation cannot predate its deduction/payment.')
    a=dict(id=str(uuid.uuid4()),document_id=document_id,payment_id=payment_id,row_index=row_index,amount=n,date=on);candidate['tds_allocations'].append(a);_check(candidate);core.add_audit(candidate,'TDS_CHALLAN_ALLOCATED',copy.deepcopy(a));state.clear();state.update(candidate);return a


def unallocate(state,allocation_id,on,reason):
    tax.day(on)
    if not reason.strip():raise ValueError('Enter the undo reason.')
    a=next(x for x in state['tds_allocations'] if x['id']==allocation_id)
    if a.get('undo_date') or on<a['date']:raise ValueError('This allocation is already undone, or the date predates it.')
    a['undo_date']=on;core.add_audit(state,'TDS_ALLOCATION_UNDONE',dict(copy.deepcopy(a),reason=reason))


def void_record(state,record_id,on,reason):
    tax.day(on);candidate=copy.deepcopy(state);r=next(r for r in candidate['tds_records'] if r['id']==record_id)
    if r.get('voucher_id') or r.get('void_date') or on<r['date'] or not reason.strip():raise ValueError('Only a live zero-journal tax record can be voided with a valid date/reason. Reverse financial vouchers instead.')
    r['void_date']=on;_check(candidate);core.add_audit(candidate,'TDS_RECORD_VOIDED',dict(copy.deepcopy(r),reason=reason));state.clear();state.update(candidate)


def challan_details(state,payment_id,values):
    if not any(r['id']==payment_id and r['kind']=='Challan' for r in state['tds_records']):raise ValueError('Challan not found.')
    import re
    bsr=str(values.get('bsr','')).strip();serial=str(values.get('serial','')).strip();deposit=str(values.get('deposit_date','')).strip()
    if bsr and not re.fullmatch(r'\d{7}',bsr) or serial and not re.fullmatch(r'\d{5}',serial):raise ValueError('BSR needs 7 digits and challan serial 5 digits; leave unknown details blank.')
    if deposit:tax.day(deposit)
    verified=values.get('verified',False)
    if type(verified)!=bool or verified and not (bsr and serial and deposit):raise ValueError('Complete the CIN details before marking the challan reviewed.')
    latest={x['payment_id']:x for x in state['tds_challan_details']}
    if verified and any(x['payment_id']!=payment_id and x.get('verified') and (x['bsr'],x['serial'],x['deposit_date'])==(bsr,serial,deposit) for x in latest.values()):raise ValueError('This CIN already identifies another challan.')
    r=dict(id=str(uuid.uuid4()),payment_id=payment_id,bsr=bsr,serial=serial,deposit_date=deposit,verified=verified,reference=str(values.get('reference','')).strip());state['tds_challan_details'].append(r);core.add_audit(state,'TDS_CHALLAN_DETAILS_SAVED',copy.deepcopy(r));return r


def report(state,start,end,branch='ALL'):
    tax.day(start);tax.day(end)
    if start>end:raise ValueError('Start follows end date.')
    if branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Select a valid report unit.')
    net=_net(state,end);roots=gst._roots(state);rows=[];outstanding=[];totals={};money=[7,8,10,11,12]
    def make_row(r,on,sign,allocated):
        return [r['reference'],on,r['party']['name'],r['party']['registration']['pan'] or 'Unknown',r['section'],foundation.branches(state)[r['branch']],str(r['year']),r['base']*sign,r['gross']*sign,r['rule']['rate'],r['withheld']*sign,allocated,r['withheld']*sign-allocated,r['mode']+(' / reversal' if sign<0 else ''),r.get('tax_date',r['date'])]
    for r in state['tds_records']:
        if r['kind']=='Challan' or branch!='ALL' and r['branch']!=branch:continue
        is_active=active(state,r,end,net);allocated=sum(a['amount'] for a in state['tds_allocations'] if a['document_id']==r['id'] and _allocation_active(a,end)) if is_active else 0
        if is_active and r['withheld']>allocated:outstanding.append(make_row(r,r['date'],1,allocated))
        if r.get('voucher_id'):
            events=[(v['date'],roots[v['id']][1],v['id']) for v in state['vouchers'] if roots[v['id']][0]==r['voucher_id'] and v['date']<=end]
        else:
            events=[(r['date'],1,r['id'])]+([(r['void_date'],-1,'void')] if r.get('void_date') else [])
        positive=[event for event in events if event[1]>0 and event[0]<=end]
        last_positive=positive[-1][2] if positive else None
        for on,sign,vid in events:
            if not start<=on<=end:continue
            paid=allocated if is_active and vid==last_positive else 0;rows.append(make_row(r,on,sign,paid));t=totals.setdefault(r['section'],[0,0,0]);t[0]+=r['base']*sign;t[1]+=r['withheld']*sign;t[2]+=paid
    codes=set(state['tds_ledgers'].values())|{a['code'] for a in state['accounts'] if state['account_details'][a['code']]['group']=='TDS payable'};books=ledgers.ledger_pack(state,sorted(codes),start,end,branch)['books'] if codes else [];expected={c:0 for c in codes}
    roots=gst._roots(state)
    for r in state['tds_records']:
        if not r.get('voucher_id'):continue
        for v in state['vouchers']:
            root,sign=roots[v['id']]
            if root==r['voucher_id'] and start<=v['date']<=end:
                for l in r['lines']:
                    if l['account'] in expected and (branch=='ALL' or l['branch']==branch):expected[l['account']]+=(l['debit']-l['credit'])*sign
    for r in state['tds_records']:
        if r['kind']=='Register existing deduction' and active(state,r,end,net):
            source=next(v for v in state['vouchers'] if v['id']==r['source_voucher'])
            if start<=source['date']<=end and not (source.get('opening') and source['date']==start) and (branch=='ALL' or branch==r['branch']):expected[r['tds_account']]-=r['withheld']
    controls={b['code']+' unclassified/manual movement':b['debit']-b['credit']-expected[b['code']] for b in books}
    pack=dict(entity=state['settings']['entity'],registration=copy.deepcopy(state['settings']['registration']),mode='TDS deductions and allocations',start=start,end=end,branch=branch,scope='All operating units' if branch=='ALL' else foundation.branches(state)[branch],prepared=datetime.now(timezone(timedelta(hours=5,minutes=30))).isoformat(timespec='seconds'),currency='INR',columns=['Reference','Posting date','Payee','PAN','Section','Unit','Tax FY start','Tax base','Gross','Rule rate %','Deducted','Allocated paid tax','Unallocated deduction','Method','Tax-point date'],money_columns=money,rows=rows,controls=controls,note='Reviewed TDS bookkeeping working report; no filing, certificate validation or government CIN verification. Unknown PAN/TAN and manual exceptions require review. Section/FY aggregation spans all units of this entity.')
    challans=[]
    for r in state['tds_records']:
        if r['kind']!='Challan' or not active(state,r,end,net):continue
        detail=next((d for d in reversed(state['tds_challan_details']) if d['payment_id']==r['id']),{})
        for index,line in enumerate(r['rows']):
            if branch!='ALL' and line['branch']!=branch:continue
            used=sum(a['amount'] for a in state['tds_allocations'] if a['payment_id']==r['id'] and a['row_index']==index and _allocation_active(a,end))
            challans.append([r['reference'],r['date'],line['section'],str(line['year']),foundation.branches(state)[line['branch']],line['tax'],used,line['tax']-used,'Reviewed' if detail.get('verified') else 'CIN pending review',0,0,detail.get('bsr',''),detail.get('serial',''),detail.get('deposit_date','')])
        if (r['interest'] or r['fee']) and (branch=='ALL' or r['branch']==branch):challans.append([r['reference'],r['date'],'Charges only','—',foundation.branches(state)[r['branch']],0,0,0,'Not allocable tax',r['interest'],r['fee'],detail.get('bsr',''),detail.get('serial',''),detail.get('deposit_date','')])
    payment_pack=copy.deepcopy(pack);payment_pack.update(mode='TDS challan reconciliation',columns=['Payment','Date','Section','Tax FY start','Unit','Tax paid','Allocated','Unallocated tax credit','CIN status','Payment interest','Payment fee','BSR code','Challan serial','Deposit date'],rows=challans,money_columns=[5,6,7,9,10],note=pack['note']+' Includes all active challans through the report end, including earlier periods. Interest/fees are excluded from allocable tax.')
    outstanding_pack=copy.deepcopy(pack);outstanding_pack.update(mode='TDS outstanding as at report end',rows=outstanding)
    section_pack=copy.deepcopy(pack);section_pack.update(mode='TDS section summary',columns=['Section','Tax base','Deducted','Allocated','Unallocated deduction'],money_columns=[1,2,3,4],rows=[[k,v[0],v[1],v[2],v[1]-v[2]] for k,v in sorted(totals.items())])
    proof_pack=copy.deepcopy(pack);proof_pack.update(mode='TDS control ledger proof',columns=['Code','Ledger','Opening Dr positive','Period debits','Period credits','Closing Dr positive','Unclassified/manual'],money_columns=[2,3,4,5,6],rows=[[b['code'],b['name'],b['opening'],b['debit'],b['credit'],b['closing'],b['debit']-b['credit']-expected[b['code']]] for b in books])
    return dict(deductions=pack,challans=payment_pack,outstanding=outstanding_pack,section_report=section_pack,proof_report=proof_pack,sections={k:dict(base=v[0],deducted=v[1],allocated=v[2]) for k,v in totals.items()},ledger_proofs=[dict(code=b['code'],opening=b['opening'],movement=b['debit']-b['credit'],closing=b['closing']) for b in books],allocations=copy.deepcopy(state['tds_allocations']),records=copy.deepcopy(state['tds_records']))


def export(state,start,end,branch,path,kind):
    result=report(state,start,end,branch);packs=[result[k] for k in ('deductions','challans','outstanding','section_report','proof_report')]
    for p in packs:p['prepared']=packs[0]['prepared']
    if kind=='xlsx':financial_reports.export_pack_xlsx(packs,path)
    elif kind=='pdf':financial_reports.export_pdf(packs,path)
    elif kind=='json':Path(path).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    else:raise ValueError('Choose Excel, PDF or JSON.')


def validate_reversal(state,voucher_id,on):_check(state,(voucher_id,on))

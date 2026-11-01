"""Registration/unit-isolated GST cash, credit utilisation and filing review."""
import copy
from functools import wraps
import hashlib
import json
from datetime import date,datetime,timedelta
import uuid
from . import core,foundation,gst,tax,rcm,fixed_assets as fa,history

PARTS=rcm.PARTS


def actions(s):return s.get('gst_actions',[])
def atomic(fn):
    @wraps(fn)
    def run(s,*args,**kwargs):
        c=copy.deepcopy(s);r=fn(c,*args,**kwargs);check(c);s.clear();s.update(c);return copy.deepcopy(r)
    return run

def context(s,v):return rcm._context(s,v)
def control(s,registration):
    key=registration
    mapping=s['gst_cash_ledgers'].setdefault(key,{})
    for part in PARTS:
        if part in mapping:continue
        used={a['code'] for a in s['accounts']};code=next((str(i) for i in range(1000,2000) if str(i) not in used),None)
        if not code:raise ValueError('No available GST cash control code.')
        foundation.save_account(s,code,registration+' electronic cash '+part.upper(),'Asset','Other assets');mapping[part]=code
    return mapping

def islive(s,r,on,reversal=None):
    n=fa.family(s,r['voucher_id'],on)
    if reversal and reversal[1]<=on:
        root,sign=gst._roots(s)[reversal[0]]
        if root==r['voucher_id']:n-=sign
    return r['date']<=on and n==1

def position(s,registration,branch,on,reversal=None,net=None):
    if net is None:
        roots=gst._roots(s);net={}
        for v in s['vouchers']:
            if v['date']<=on:
                root,sign=roots[v['id']];net[root]=net.get(root,0)+sign
        if reversal and reversal[1]<=on:
            root,sign=roots[reversal[0]];net[root]=net.get(root,0)-sign
    live=lambda r:r['date']<=on and net.get(r['voucher_id'],0)==1
    cash=dict.fromkeys(PARTS,0);credit=dict.fromkeys(PARTS,0);due=dict.fromkeys(PARTS,0);mapping=s.get('gst_cash_ledgers',{}).get(registration,{})
    for d in s['gst_documents']:
        if d['registration']!=registration or d['branch']!=branch or not live(d):continue
        sign=d.get('document_sign',1)
        for item in d.get('line_items') or [d]:
            for p in PARTS:
                if d['kind']=='Sale':due[p]+=item['totals'][p]*sign
                elif item['itc']=='Eligible':credit[p]+=item['totals'][p]*sign
    for r in s.get('gst_rcm_records',[]):
        if r['registration']!=registration or r['branch']!=branch or not live(r):continue
        for p,code in zip(PARTS,gst.INPUT):credit[p]+=sum(l['debit']-l['credit'] for l in r['lines'] if l['account']==code)
    for r in actions(s):
        if r['registration']!=registration or r['branch']!=branch or not live(r):continue
        for p,input_code,output_code in zip(PARTS,gst.INPUT,gst.OUTPUT):
            credit[p]+=sum(l['debit']-l['credit'] for l in r['lines'] if l['account']==input_code)
            due[p]+=sum(l['credit']-l['debit'] for l in r['lines'] if l['account']==output_code)
            if p in mapping:cash[p]+=sum(l['debit']-l['credit'] for l in r['lines'] if l['account']==mapping[p])
    return dict(cash=cash,credit=credit,due=due)


@atomic
def post(s,kind,v):
    if v.get('confirmed') is not True or v.get('eligibility_reviewed') is not True:raise ValueError('Review the actual portal/cash/credit source, legal eligibility/order and complete journal.')
    ctx=context(s,v);reg=ctx['registration'];unit=ctx['branch'];on=ctx['date'];mapping=control(s,reg);pos=position(s,reg,unit,on)
    if any(r['registration']==reg and gst._reference(r['reference'])==gst._reference(ctx['reference']) for r in actions(s)):raise ValueError('This GST payment/action reference already exists.')
    if kind=='Deposit' and any(r['stage']=='Deposit' and r['registration']==reg and gst._reference(r['reference'])==gst._reference(ctx['reference']) for r in s['gst_rcm_records']):raise ValueError('This bank funding reference is already recorded for RCM; do not deposit it twice.')
    r=dict(ctx,id=str(uuid.uuid4()),kind=kind,lines=[],eligibility_reviewed=True)
    def add(code,n,dr):
        if n:r['lines'].append(dict(account=code,branch=unit,debit=n if dr else 0,credit=0 if dr else n))
    if kind=='Register opening':
        source=next((x for x in s['vouchers'] if x['id']==v.get('source_voucher') and x.get('opening')),None)
        if not source or source['date']!=on or fa.family(s,source['id'])!=1:raise ValueError('Select an active initial opening voucher on its actual date.')
        for source_field,codes,dr in [('opening_input',gst.INPUT,True),('opening_output',gst.OUTPUT,False),('opening_cash',[mapping[p] for p in PARTS],True)]:
            amounts=v.get(source_field,{})
            for p,code in zip(PARTS,codes):
                n=rcm._money(amounts.get(p,'0'))
                capacity=sum((l['debit']-l['credit'] if dr else l['credit']-l['debit']) for l in source['lines'] if l['branch']==unit and l['account']==code)
                used=sum(l['debit']+l['credit'] for r0 in actions(s) if r0['kind']=='Register opening' and r0['voucher_id']==source['id'] for l in r0['lines'] if l['branch']==unit and l['account']==code)
                if n+used>capacity:raise ValueError('Opening allocation exceeds unused actual tax-source capacity.')
                add(code,n,dr)
        if not r['lines']:raise ValueError('Allocate positive actual opening tax balances.')
        r['voucher_id']=source['id'];actions(s).append(r);core.add_audit(s,'GST_OPENING_SOURCE_LINKED',copy.deepcopy(r));return r
    elif kind in ('Deposit','Cash refund','Cash utilisation'):
        amounts={p:rcm._money(v.get(p,'0')) for p in PARTS}
        if not any(amounts.values()):raise ValueError('Enter actual positive component amounts.')
        bank=v.get('bank_account','1010')
        if kind!='Cash utilisation' and (s['account_details'].get(bank,{}).get('group')!='Cash and bank' or bank in s.get('foreign_accounts',{})):raise ValueError('Select the actual INR bank ledger.')
        for p,code in zip(PARTS,gst.OUTPUT):
            n=amounts[p]
            if kind!='Deposit' and n>pos['cash'][p]:raise ValueError('Actual dated electronic cash is insufficient.')
            if kind=='Cash utilisation' and n>pos['due'][p]:raise ValueError('Amount exceeds classified tax due for this registration/unit.')
            add(mapping[p],n,kind=='Deposit')
            if kind=='Cash utilisation':add(code,n,True)
        if kind!='Cash utilisation':add(bank,sum(amounts.values()),kind=='Cash refund')
        r['amounts']=amounts
    elif kind in ('ITC utilisation','Cash transfer'):
        source=v.get('from_component');target=v.get('to_component');n=rcm._money(v.get('amount'))
        if source not in PARTS or target not in PARTS or n<=0:raise ValueError('Select components and a positive amount.')
        if kind=='Cash transfer':
            if source==target or n>pos['cash'][source]:raise ValueError('Use distinct cash components and available source cash.')
            add(mapping[source],n,False);add(mapping[target],n,True)
        else:
            if (source,target) in (('cgst','sgst'),('sgst','cgst')):raise ValueError('CGST and SGST credit cannot cross-utilise.')
            if n>pos['credit'][source] or n>pos['due'][target]:raise ValueError('Use available reviewed credit and actual component tax due.')
            policy=utilisation_policy(s,on,r['narration']);r['utilisation_policy']=policy
            if policy['igst_first'] and source!='igst' and pos['credit']['igst']>0 or source=='igst' and target!='igst' and pos['due']['igst']>0:raise ValueError('Exhaust available IGST credit against IGST before the reviewed other-head allocation.')
            if source=='igst' and target in ('cgst','sgst'):
                first='cgst' if policy['residual_order']=='CGST then SGST' else 'sgst' if policy['residual_order']=='SGST then CGST' else None
                if first and target!=first and pos['due'][first]>0:raise ValueError('Follow the reviewed effective-year residual IGST credit order.')
            if policy['own_head_first'] and source in ('cgst','sgst') and target=='igst' and pos['due'][source]>0:raise ValueError('Use the source head against its own liability first.')
            add(gst.INPUT[PARTS.index(source)],n,False);add(gst.OUTPUT[PARTS.index(target)],n,True)
        r.update(from_component=source,to_component=target,amount=n)
    elif kind=='ITC reclassification':
        doc=next((d for d in s['gst_documents'] if d['id']==v.get('document_id') and d['kind']=='Purchase' and not d.get('original_document_id')),None)
        if not doc or doc['registration']!=reg or doc['branch']!=unit or not islive(s,doc,on):raise ValueError('Select an active purchase in this exact registration/unit.')
        rows=doc.get('line_items') or [dict(doc,id=doc['id'])];item=next((x for x in rows if x['id']==v.get('line_id',doc['id'])),None)
        if not item:raise ValueError('Select a source line for mixed eligibility.')
        percent=rcm.Decimal(tax.decimal_text(v.get('eligible_percent'),percent=True));delta={};source_id=item['id']
        family=[d for d in s['gst_documents'] if d['id']==doc['id'] or d.get('original_document_id')==doc['id']]
        available={p:sum(x['totals'][p]*d.get('document_sign',1) for d in family if islive(s,d,on) for x in d.get('line_items') or [dict(d,id=d['id'])] if x['id']==source_id or not d.get('line_items')) for p in PARTS}
        for p,code in zip(PARTS,gst.INPUT):
            current=available[p] if item['itc']=='Eligible' else 0
            current+=sum(r0.get('credit_delta',{}).get(p,0) for r0 in actions(s) if r0.get('source_line')==source_id and islive(s,r0,on))
            desired=int((rcm.Decimal(available[p])*percent/100).quantize(rcm.Decimal(1),rounding=rcm.ROUND_HALF_UP));delta[p]=desired-current
            if delta[p]<0 and -delta[p]>pos['credit'][p]:raise ValueError('Reverse dependent utilisation before removing already-used credit.')
            add(code,abs(delta[p]),delta[p]>0);add(item['account'],abs(delta[p]),delta[p]<0)
        if not any(delta.values()):raise ValueError('No actual eligibility change to post.')
        r.update(document_id=doc['id'],source_line=source_id,credit_delta=delta,eligible_percent=str(percent))
    else:raise ValueError('Choose a supported actual GST cash/credit action.')
    actual=core.balances(s,on,unit)
    for code in gst.INPUT:
        credit_amount=sum(l['credit']-l['debit'] for l in r['lines'] if l['account']==code)
        if credit_amount>max(0,actual[code]):raise ValueError('GST input books do not cover this credit use; reconcile manual movements first.')
    for code in mapping.values():
        spend=sum(l['credit']-l['debit'] for l in r['lines'] if l['account']==code)
        if spend>max(0,actual[code]):raise ValueError('Electronic cash books do not cover this actual use.')
    r['voucher_id']=core.post(s,on,r['narration'],r['lines'],metadata={'reference':r['reference']})['id'];actions(s).append(r);core.add_audit(s,'GST_CASH_CREDIT_RECORDED',copy.deepcopy(r));return r


def check(s,reversal=None):
    if not actions(s):return
    roots=gst._roots(s);dates={v['date'] for v in s['vouchers']}
    if reversal:dates.add(reversal[1])
    changes={}
    for v in s['vouchers']:
        root,sign=roots[v['id']];changes.setdefault(v['date'],[]).append((root,sign))
    if reversal:
        root,sign=roots[reversal[0]];changes.setdefault(reversal[1],[]).append((root,-sign))
    net={}
    for on in sorted(dates):
        for root,sign in changes.get(on,[]):net[root]=net.get(root,0)+sign
        for reg,branch in {(r['registration'],r['branch']) for r in actions(s)}:
            p=position(s,reg,branch,on,net=net)
            for r in actions(s):
                if r.get('document_id') and r['date']<=on and net.get(r['voucher_id'],0)==1:
                    doc=next(d for d in s['gst_documents'] if d['id']==r['document_id'])
                    if net.get(doc['voucher_id'],0)!=1:raise ValueError('Reverse eligibility reclassification before its original purchase.')
            if any(n<0 for group in ('cash','credit') for n in p[group].values()):raise ValueError('GST source cash or credit capacity would be negative on '+on+'. Review dependent/future allocations first.')
    for r in actions(s):
        if r.get('document_id'):
            doc=next(d for d in s['gst_documents'] if d['id']==r['document_id'])
            if islive(s,r,'9999-12-31',reversal) and not islive(s,doc,'9999-12-31',reversal):raise ValueError('Reverse eligibility reclassifications before their source purchase.')


def period_fingerprint(s,registration,branch,period):
    start=tax.day(period+'-01');next_month=fa.add_months(start,1);end=(next_month-timedelta(days=1)).isoformat()
    relevant_vouchers=[v for v in s['vouchers'] if v['date']<=end and any(l['branch']==branch for l in v['lines'])]
    payload=dict(vouchers=relevant_vouchers,documents=[d for d in s['gst_documents'] if d['registration']==registration and d['date']<=end],actions=[r for r in actions(s) if r['registration']==registration and r['branch']==branch and r['date']<=end],rcm=[r for r in s['gst_rcm_records'] if r['registration']==registration and r['branch']==branch and r['date']<=end],matches=s['gst_2b_matches'])
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),start,end


def review_filing(s,registration,branch,period,basis,reviewed=False,acknowledgement=''):
    registration=gst._gstin(registration)
    if reviewed is not True or not str(basis).strip() or branch not in foundation.branches(s):raise ValueError('Review the actual registration, period, source proof, eligibility and filing preparation basis.')
    fingerprint,start,end=period_fingerprint(s,registration,branch,period)
    if end>=date.today().isoformat():raise ValueError('Review an ended tax period, not a future/incomplete month.')
    actual=core.balances(s,end,branch);mapping=s.get('gst_cash_ledgers',{}).get(registration,{})
    if any(actual[code]!=position(s,registration,branch,end)['cash'][p] for p,code in mapping.items()):raise ValueError('Reconcile actual electronic cash to tagged sources before filing preparation.')
    snapshot=dict(summary=gst.summary(s,start,end,branch),position=position(s,registration,branch,end),rcm=rcm.report(s,start,end,branch))
    snapshot['registration_documents']=[d for d in snapshot['summary']['documents'] if d['registration']==registration]
    snapshot['proof_scope']='Tax/control ledger proof is branch-wide for shared tax ledgers; registration_documents and position are the selected registration only.'
    if any(snapshot['summary']['unclassified'].values()) or any(snapshot['rcm']['unclassified'].values()):raise ValueError('Resolve unclassified tax/RCM movements before final filing preparation.')
    r=dict(id=str(uuid.uuid4()),registration=registration,branch=branch,period=period,review_fingerprint=fingerprint,basis=str(basis).strip(),acknowledgement=str(acknowledgement).strip(),status='Manually acknowledged filed' if str(acknowledgement).strip() else 'Reviewed preparation',snapshot=snapshot)
    s['gst_filing_reviews'].append(r);core.add_audit(s,'GST_FILING_REVIEWED',dict(id=r['id'],registration=registration,branch=branch,period=period,basis=r['basis'],acknowledgement=r['acknowledgement']));return copy.deepcopy(r)


@atomic
def bind_cash_controls(s,registration,ledgers,basis,reviewed=False):
    registration=gst._gstin(registration)
    if reviewed is not True or not str(basis).strip() or set(ledgers)!=set(PARTS) or len(set(ledgers.values()))!=3:raise ValueError('Review distinct actual electronic cash component ledgers and source basis.')
    if registration in s['gst_cash_ledgers']:raise ValueError('Historical component mapping cannot be replaced; retain and reconcile its sources.')
    used={code for mapping in s['gst_cash_ledgers'].values() for code in mapping.values()}|set(s.get('gst_rcm_ledgers',{}).values())
    for code in ledgers.values():
        fa._ledger(s,code,'Asset','Other assets')
        if code in used or not s['account_details'][code]['active']:raise ValueError('Cash controls cannot be inactive or shared with another source pool.')
    s['gst_cash_ledgers'][registration]=copy.deepcopy(ledgers);core.add_audit(s,'GST_CASH_CONTROLS_BOUND',dict(registration=registration,ledgers=copy.deepcopy(ledgers),basis=str(basis).strip()));return ledgers


def apply_used_itc_repayment(s,note,values):
    if note['kind']!='Purchase' or note.get('document_sign',1)>=0:return note
    pos=position(s,note['registration'],note['branch'],note['date']);needed={p:max(0,sum(l['credit']-l['debit'] for l in note['lines'] if l['account']==code)-pos['credit'][p]) for p,code in zip(PARTS,gst.INPUT)}
    if not any(needed.values()):return note
    if values.get('repay_used_itc') is not True or not str(values.get('repayment_basis','')).strip():raise ValueError('Purchase-note ITC has already been used. Explicitly review conversion of the used reversal into GST payable with repayment basis; do not silently create negative available credit.')
    lines=[]
    for p,dr,cr in zip(PARTS,gst.INPUT,gst.OUTPUT):
        n=needed[p]
        if n:lines.extend([dict(account=dr,branch=note['branch'],debit=n,credit=0),dict(account=cr,branch=note['branch'],debit=0,credit=n)])
    note['lines'].extend(lines);note['used_itc_repayment']=dict(amounts=needed,lines=lines,basis=str(values['repayment_basis']).strip());return note


def save_utilisation_policy(s,effective,igst_first,residual_order,own_head_first,basis,reviewed=False):
    tax.day(effective)
    if type(igst_first)!=bool or type(own_head_first)!=bool or residual_order not in ('Any','CGST then SGST','SGST then CGST') or reviewed is not True or not str(basis).strip():raise ValueError('Review the effective-year credit order, priority choices and governing source.')
    r=dict(id=str(uuid.uuid4()),effective=effective,igst_first=igst_first,residual_order=residual_order,own_head_first=own_head_first,basis=str(basis).strip(),reviewed=True);s['gst_utilisation_policies'].append(r);core.add_audit(s,'GST_UTILISATION_POLICY_REVISED',copy.deepcopy(r));return copy.deepcopy(r)


def utilisation_policy(s,on,basis):
    choices=[(r['effective'],i,r) for i,r in enumerate(s.get('gst_utilisation_policies',[])) if r['effective']<=on]
    if choices:return copy.deepcopy(max(choices,key=lambda x:x[:2])[2])
    if on<'2019-03-29':raise ValueError('Configure and review the historical effective-dated GST credit order before using earlier-year ITC.')
    return dict(id='PER-ACTION-REVIEW-88A',effective='2019-03-29',igst_first=True,residual_order='Any',own_head_first=True,basis=basis,reviewed=True,source='Rule 88A / CBIC Circular 98/17/2019-GST; verify governing-year applicability. https://gstcouncil.gov.in/node/4817')

"""Reviewed Companies Act book SLM subledger; tax depreciation is separate."""
import copy
import calendar
import uuid
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
import json
from . import core,foundation,reconciliation as amounts,gst

# Reference proposals only: exact asset classification, exemptions, shifts and overrides require review.
CLASSES={
 'Manual / specific Schedule II category':None,
 'General plant and machinery — reference':180,
 'Furniture and fittings — reference':120,
 'Office equipment — reference':60,
 'Computers / end-user devices — reference':36,
 'Servers and networks — reference':72,
 'RCC buildings (other than factory) — reference':720,
 'Other buildings (other than factory) — reference':360,
 'Land — non-depreciable':0}
REFERENCE='Companies Act 2013, Schedule II, Part C. Reference category proposals; verify actual category, year, shifts and technical assessment.'


def day(value):
    if not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value:raise ValueError('Use YYYY-MM-DD for asset dates.')
    return value


def add_months(value,months):
    d=date.fromisoformat(value);n=d.year*12+d.month-1+months;y,m=divmod(n,12);return date(y,m+1,min(d.day,calendar.monthrange(y,m+1)[1]))


def _round(n):return int((Decimal(n.numerator)/Decimal(n.denominator)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def _months(start,stop):
    d=date.fromisoformat(start);result=Fraction(0)
    while d<stop:
        next_month=add_months(d.replace(day=1).isoformat(),1);end=min(stop,next_month)
        result+=Fraction((end-d).days,calendar.monthrange(d.year,d.month)[1]);d=end
    return result


def family(state,voucher_id,through='9999-12-31'):
    roots=gst._roots(state)
    return sum(sign for v in state['vouchers'] if v['date']<=through for root,sign in [roots[v['id']]] if root==voucher_id)


def asset(state,asset_id):
    a=next((a for a in state.get('book_assets',[]) if a['id']==asset_id),None)
    if a is None:raise ValueError('Select a registered book asset.')
    return a


def present(state,a,through):return a['baseline']<=through and family(state,a['cost_voucher'],through)==1


def events(state,a,through='9999-12-31'):
    return [e for e in state.get('fixed_asset_events',[]) if any(i['asset_id']==a['id'] for i in e['items']) and family(state,e['voucher'],through)==1]


def accumulated(state,a,through):
    return a['opening_accum']+sum(i['depreciation'] for e in events(state,a,through) for i in e['items'] if i['asset_id']==a['id'])


def disposed(state,a,through):return any(e['kind']=='Disposal' for e in events(state,a,through))


def branch_at(state,a,through):
    unit=a['branch']
    for e in events(state,a,through):
        if e['kind']=='Transfer':unit=e['to_branch']
    return unit


def policy(a,through):
    choices=[p for p in a['estimates'] if p.get('active',True) and p['effective']<=through]
    return copy.deepcopy(choices[-1]) if choices else None


def target(a,through):
    p=policy(a,through)
    if not p:return a['opening_accum']
    base=p['base_accum'];pool=max(0,a['cost']-base-p['residual'])
    if not pool or through<p['start']:return base
    expiry=add_months(p['start'],p['months'])
    if date.fromisoformat(through)>=expiry-timedelta(days=1):return base+pool
    stop=date.fromisoformat(through)+timedelta(days=1);units=_months(p['start'],stop)
    for usage in a.get('shift_usage',[]):
        if not usage['active']:continue
        lo=max(p['start'],usage['start']);hi=min(stop,date.fromisoformat(usage['end'])+timedelta(days=1))
        if date.fromisoformat(lo)<hi:units+=(Fraction(usage['factor'])-1)*_months(lo,hi)
    return base+min(pool,_round(Fraction(pool,p['months'])*units))


def _ledger(state,code,kind,group=None):
    a=next((a for a in state['accounts'] if a['code']==code),None)
    if not a or a['kind']!=kind or group and state['account_details'][code]['group']!=group:raise ValueError('Choose a '+(group or kind)+' ledger for '+str(code)+'.')


def _policy(cost,base,start,months,residual,basis,reviewed):
    if type(months)!=int or not 0<=months<=1200:raise ValueError('Useful/remaining life must be 0–1200 whole months.')
    if residual<0 or residual>cost-base:raise ValueError('Residual must be between zero and the remaining carrying amount.')
    if cost-base>residual and not months:raise ValueError('Depreciable assets require positive remaining life.')
    if reviewed is not True or not str(basis).strip():raise ValueError('Review the Schedule II classification, life, residual, shifts and accounting basis before saving.')
    return dict(id=str(uuid.uuid4()),effective=start,start=start,months=months,residual=residual,base_accum=base,basis=str(basis).strip(),reviewed=True,active=True,method='SLM monthly; actual calendar-day partial months; terminal residual cap')


def _source_capacity(state,voucher_id,code,branch,credit=False):
    v=next((v for v in state['vouchers'] if v['id']==voucher_id and not v.get('reverses')),None)
    if not v or family(state,voucher_id)!=1:raise ValueError('Select a live original acquisition/opening voucher.')
    n=sum((l['credit']-l['debit'] if credit else l['debit']-l['credit']) for l in v['lines'] if l['account']==code and l['branch']==branch)
    used=sum(a['opening_accum'] if credit else a['cost'] for a in state.get('book_assets',[]) if a['accum_voucher' if credit else 'cost_voucher']==voucher_id and a['accum' if credit else 'ppe']==code and a['branch']==branch)
    return v,n-used


def register(state,values):
    candidate=copy.deepcopy(state);a=_register(candidate,values);state.clear();state.update(candidate);return copy.deepcopy(a)


def _register(state,v):
    ref=str(v.get('reference','')).strip();name=str(v.get('name','')).strip();basis=str(v.get('basis','')).strip();branch=v.get('branch');category=v.get('category','Manual / specific Schedule II category')
    if not ref or not name or any(a['reference'].casefold()==ref.casefold() for a in state['book_assets']):raise ValueError('Enter a unique asset reference and asset name.')
    if branch not in foundation.branches(state,True) or category not in CLASSES:raise ValueError('Select an active operating unit and asset category.')
    acquired=day(v.get('acquired',''));put=day(v.get('put_to_use',''));baseline=day(v.get('baseline',acquired))
    if put<acquired or baseline<acquired:raise ValueError('Put-to-use and book baseline cannot precede acquisition.')
    cost=amounts.amount(v.get('cost'));opening=amounts.amount(v.get('opening_accum','0'));residual=amounts.amount(v.get('residual','0'))
    if cost<=0 or opening<0 or opening>cost:raise ValueError('Enter positive cost and valid opening accumulated depreciation.')
    if opening and put>baseline:raise ValueError('Opening depreciation cannot precede the asset put-to-use date.')
    months=int(v.get('months',0));p=_policy(cost,opening,max(put,baseline),months,residual,basis,v.get('reviewed'))
    suggested=CLASSES[category]
    if (suggested is not None and months!=suggested or category!='Land — non-depreciable' and residual*100>cost*5 or opening) and not str(v.get('override_basis','')).strip():raise ValueError('Document technical/override or opening remaining-life basis for changed reference life, residual above 5%, or opening depreciation.')
    if category=='Land — non-depreciable' and (months or residual!=cost or opening):raise ValueError('Land must have zero life, residual equal cost and no depreciation.')
    p.update(category=category,reference_source=REFERENCE,override_basis=str(v.get('override_basis','')).strip())
    ppe=v.get('ppe','1030');accum=v.get('accum','1050');expense=v.get('expense','4570')
    _ledger(state,ppe,'Asset','PPE');_ledger(state,accum,'Asset','Accumulated depreciation');_ledger(state,expense,'Expense','Depreciation')
    mode=v.get('mode','Link existing');source=v.get('cost_voucher','');accum_source=v.get('accum_voucher','') or source
    if mode=='Post purchase':
        if opening or baseline!=acquired:raise ValueError('New purchases have zero opening depreciation and acquisition-date baseline; link existing opening journals for prior assets.')
        counter=v.get('counter','2000');_ledger_any(state,counter)
        if next(a['kind'] for a in state['accounts'] if a['code']==counter) not in ('Asset','Liability','Equity'):raise ValueError('A purchase counter must be a balance-sheet ledger.')
        if counter in (ppe,accum,expense) or state['account_details'][counter]['group'] in ('PPE','Accumulated depreciation'):raise ValueError('Choose a separate purchase counter ledger.')
        voucher=core.post(state,acquired,'Asset acquisition '+ref+': '+name,_pair(ppe,counter,cost,branch),metadata={'reference':ref});source=voucher['id'];accum_source=''
    elif mode=='Link existing':
        voucher,capacity=_source_capacity(state,source,ppe,branch)
        if voucher['date']!=baseline or capacity<cost:raise ValueError('Cost must fit unused source PPE debit capacity on the book baseline date.')
        if opening:
            av,capacity=_source_capacity(state,accum_source,accum,branch,True)
            if av['date']!=baseline or capacity<opening:raise ValueError('Opening depreciation must fit unused source accumulated-depreciation credit capacity on the baseline date.')
        else:accum_source=''
    else:raise ValueError('Choose Post purchase or Link existing.')
    legacy=v.get('legacy_index')
    if legacy not in (None,''):
        legacy=int(legacy)
        if not 0<=legacy<len(state['assets']) or any(a.get('legacy_index')==legacy for a in state['book_assets']):raise ValueError('Select an unused legacy calculator row index.')
    else:legacy=None
    a=dict(id=str(uuid.uuid4()),reference=ref,name=name,branch=branch,category=category,acquired=acquired,put_to_use=put,baseline=baseline,cost=cost,opening_accum=opening,ppe=ppe,accum=accum,expense=expense,cost_voucher=source,accum_voucher=accum_source,mode=mode,legacy_index=legacy,estimates=[p],shift_usage=[])
    state['book_assets'].append(a);core.add_audit(state,'BOOK_ASSET_REGISTERED',copy.deepcopy(a));return a


def _ledger_any(state,code):
    if code not in {a['code'] for a in state['accounts']}:raise ValueError('Unknown counter ledger.')


def _pair(dr,cr,n,branch):return [dict(account=dr,branch=branch,debit=n,credit=0),dict(account=cr,branch=branch,debit=0,credit=n)]


def _latest(state,a,on):
    ids={e['voucher'] for e in state['fixed_asset_events'] if any(i['asset_id']==a['id'] for i in e['items'])}|{a['cost_voucher'],a['accum_voucher']}
    roots=gst._roots(state)
    if any(v['date']>on and roots[v['id']][0] in ids for v in state['vouchers']) or any(p['active'] and p['effective']>on for p in a['estimates'][1:]):raise ValueError('Asset history has later records. Process chronologically or reverse/withdraw later dependencies first.')
    if not present(state,a,on) or disposed(state,a,on) or a['accum_voucher'] and family(state,a['accum_voucher'],on)!=1:raise ValueError('Asset is not live, is disposed, or its opening source is reversed.')


def _due(state,a,through,posting):
    _latest(state,a,posting)
    if through<a['baseline']:return 0
    if any(e.get('through',e['date'])>through for e in events(state,a,posting)):raise ValueError('Later depreciation coverage exists; do not post an earlier schedule over it.')
    n=target(a,through)-accumulated(state,a,posting)
    if n<0:raise ValueError('Posted depreciation exceeds this target. Review/reverse later postings or estimates.')
    return n


def link_prior_depreciation(state,asset_id,voucher_id,amount,through,basis,reviewed=False):
    a=asset(state,asset_id);through=day(through);n=amounts.amount(amount)
    source=next((v for v in state['vouchers'] if v['id']==voucher_id and not v.get('reverses') and not v.get('opening') and not v.get('closing')),None)
    if not source or family(state,voucher_id)!=1 or through>source['date'] or reviewed is not True or not str(basis).strip() or n<=0:raise ValueError('Review an active original depreciation journal, positive amount, coverage and source basis.')
    if not present(state,a,source['date']) or disposed(state,a,source['date']):raise ValueError('The asset must be live at the original depreciation journal date.')
    unit=branch_at(state,a,source['date'])
    if through<a['baseline']:raise ValueError('Prior depreciation coverage precedes this book baseline.')
    dr=sum(l['debit']-l['credit'] for l in source['lines'] if l['branch']==unit and l['account']==a['expense']);cr=sum(l['credit']-l['debit'] for l in source['lines'] if l['branch']==unit and l['account']==a['accum'])
    used_dr=used_cr=0
    for e in state['fixed_asset_events']:
        if e['voucher']!=voucher_id:continue
        for item in e['items']:
            other=asset(state,item['asset_id'])
            if item['branch']==unit:
                if other['expense']==a['expense']:used_dr+=item['depreciation']
                if other['accum']==a['accum']:used_cr+=item['depreciation']
    if n>min(dr-used_dr,cr-used_cr):raise ValueError('Amount exceeds unused source expense-debit/accumulated-credit capacity; do not register the same depreciation twice.')
    e=dict(id=str(uuid.uuid4()),kind='Prior depreciation',date=source['date'],through=through,items=[dict(asset_id=asset_id,depreciation=n,branch=unit)],voucher=voucher_id,basis=str(basis).strip())
    state['fixed_asset_events'].append(e);core.add_audit(state,'BOOK_ASSET_PRIOR_DEPRECIATION_LINKED',copy.deepcopy(e));return copy.deepcopy(e)


def _event(state,kind,on,through,items,lines,**extra):
    combined={}
    for l in lines:
        key=(l['branch'],l['account']);combined[key]=combined.get(key,0)+l['debit']-l['credit']
    cleaned=[dict(branch=b,account=c,debit=max(n,0),credit=max(-n,0)) for (b,c),n in combined.items() if n]
    event_id=str(uuid.uuid4());voucher=core.post(state,on,'Book assets '+kind+' through '+through,cleaned,metadata={'reference':event_id})
    e=dict(id=event_id,kind=kind,date=on,through=through,items=items,voucher=voucher['id'],**extra);state['fixed_asset_events'].append(e);core.add_audit(state,'BOOK_ASSET_'+kind.upper(),copy.deepcopy(e));return e


def post_depreciation(state,through,posting_date=None,branch='ALL'):
    through=day(through);on=day(posting_date or through)
    if on<through or branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Choose valid coverage, posting date and operating unit.')
    _check_alignment(state,on,branch)
    candidate=copy.deepcopy(state);items=[];lines=[]
    for a in candidate['book_assets']:
        if not present(candidate,a,on) or disposed(candidate,a,on) or branch!='ALL' and branch_at(candidate,a,on)!=branch:continue
        n=_due(candidate,a,through,on)
        if n:
            unit=branch_at(candidate,a,on);items.append(dict(asset_id=a['id'],depreciation=n,branch=unit));lines+=_pair(a['expense'],a['accum'],n,unit)
    if not items:raise ValueError('No unposted book depreciation for this scope/coverage.')
    e=_event(candidate,'Depreciation',on,through,items,lines);state.clear();state.update(candidate);return copy.deepcopy(e)


def revise_estimate(state,asset_id,effective,months,residual,basis,reviewed=False):
    a=asset(state,asset_id);effective=day(effective);_latest(state,a,effective)
    if effective<=max(p['effective'] for p in a['estimates'] if p['active']):raise ValueError('Use a later prospective estimate date.')
    _check_alignment(state,effective,branch_at(state,a,effective))
    previous=(date.fromisoformat(effective)-timedelta(days=1)).isoformat()
    if _due(state,a,previous,effective):raise ValueError('Post depreciation through the day before the estimate first.')
    p=_policy(a['cost'],accumulated(state,a,effective),effective,months,amounts.amount(residual),basis,reviewed)
    a['estimates'].append(p);core.add_audit(state,'BOOK_ASSET_ESTIMATE_REVISED',dict(asset_id=asset_id,policy=copy.deepcopy(p)));return copy.deepcopy(p)


def withdraw_estimate(state,asset_id,reason):
    a=asset(state,asset_id);choices=[p for p in a['estimates'][1:] if p['active']]
    if not choices or not str(reason).strip():raise ValueError('Select a revised estimate and supply a withdrawal reason.')
    p=choices[-1]
    if any(e['date']>=p['effective'] for e in events(state,a)):raise ValueError('Reverse dependent asset postings before withdrawing this estimate.')
    p['active']=False;core.add_audit(state,'BOOK_ASSET_ESTIMATE_WITHDRAWN',dict(asset_id=asset_id,policy_id=p['id'],reason=str(reason).strip()))


def _shift_editable(state,a,start):
    if any(e['through']>=start for e in events(state,a)) or any(p['active'] and p['effective']>start for p in a['estimates'][1:]):raise ValueError('Reverse covered asset postings and withdraw dependent estimates before changing shift usage.')


def save_shift_usage(state,asset_id,start,end,factor,basis,eligible=False):
    a=asset(state,asset_id);start=day(start);end=day(end);factor=str(factor)
    if start>end or start<max(a['put_to_use'],a['baseline']) or factor not in ('1.5','2'):raise ValueError('Use valid post-commissioning dates and double (1.5) or triple (2) shift factor.')
    if eligible is not True or not str(basis).strip() or a['category']=='Land — non-depreciable':raise ValueError('Verify this asset is eligible for extra-shift depreciation (not NESD) and retain its source basis.')
    _shift_editable(state,a,start)
    if any(u['active'] and max(start,u['start'])<=min(end,u['end']) for u in a.get('shift_usage',[])):raise ValueError('Extra-shift usage dates cannot overlap.')
    u=dict(id=str(uuid.uuid4()),start=start,end=end,factor=factor,basis=str(basis).strip(),eligible_reviewed=True,active=True)
    a.setdefault('shift_usage',[]).append(u);core.add_audit(state,'BOOK_ASSET_SHIFT_USAGE_SAVED',dict(asset_id=asset_id,usage=copy.deepcopy(u)));return copy.deepcopy(u)


def withdraw_shift_usage(state,asset_id,reason):
    a=asset(state,asset_id);uses=[u for u in a.get('shift_usage',[]) if u['active']]
    if not uses or not str(reason).strip():raise ValueError('Select an asset with reviewed shift usage and enter a withdrawal reason.')
    u=uses[-1];_shift_editable(state,a,u['start']);u['active']=False;core.add_audit(state,'BOOK_ASSET_SHIFT_USAGE_WITHDRAWN',dict(asset_id=asset_id,usage_id=u['id'],reason=str(reason).strip()))


def transfer(state,asset_id,on,to_branch,basis,reviewed=False):
    on=day(on);candidate=copy.deepcopy(state);a=asset(candidate,asset_id);_latest(candidate,a,on);old=branch_at(candidate,a,on)
    if reviewed is not True or not str(basis).strip() or to_branch not in foundation.branches(candidate,True) or to_branch==old:raise ValueError('Review the transfer basis and select a different active unit.')
    _check_alignment(candidate,on,old);_check_alignment(candidate,on,to_branch)
    through=(date.fromisoformat(on)-timedelta(days=1)).isoformat();n=_due(candidate,a,through,on);acc=accumulated(candidate,a,on)+n;net=a['cost']-acc
    lines=_pair(a['expense'],a['accum'],n,old) if n else []
    lines += [dict(account=a['ppe'],branch=old,debit=0,credit=a['cost']),dict(account=a['ppe'],branch=to_branch,debit=a['cost'],credit=0)]
    if acc:lines += [dict(account=a['accum'],branch=old,debit=acc,credit=0),dict(account=a['accum'],branch=to_branch,debit=0,credit=acc)]
    if net:lines += [dict(account='1130',branch=old,debit=net,credit=0),dict(account='1130',branch=to_branch,debit=0,credit=net)]
    e=_event(candidate,'Transfer',on,through,[dict(asset_id=asset_id,depreciation=n,branch=old)],lines,to_branch=to_branch,from_branch=old,basis=str(basis).strip())
    state.clear();state.update(candidate);return copy.deepcopy(e)


def disposal_ledgers(state):
    codes=state['asset_ledgers']
    for key,name,kind,group,lo,hi in [('gain','Gain on disposal of PPE','Revenue','Other revenue',4400,4499),('loss','Loss on disposal of PPE','Expense','Other expenses',4900,4999)]:
        if key not in codes:
            used={a['code'] for a in state['accounts']};code=next((str(i) for i in range(lo,hi+1) if str(i) not in used),None)
            if code is None:raise ValueError('No free disposal '+key+' ledger code.')
            foundation.save_account(state,code,name,kind,group,cash_flow='Investing');codes[key]=code
        _ledger(state,codes[key],kind)
    return codes


def dispose(state,asset_id,on,proceeds,counter,gain,loss,basis,reviewed=False):
    on=day(on);candidate=copy.deepcopy(state);a=asset(candidate,asset_id);_latest(candidate,a,on);unit=branch_at(candidate,a,on)
    _check_alignment(candidate,on,unit)
    money=amounts.amount(proceeds)
    if reviewed is not True or not str(basis).strip() or money<0:raise ValueError('Review disposal date, proceeds excluding separately accounted taxes, and source basis.')
    if not gain or not loss:
        defaults=disposal_ledgers(candidate);gain=gain or defaults['gain'];loss=loss or defaults['loss']
    _ledger_any(candidate,counter);_ledger(candidate,gain,'Revenue');_ledger(candidate,loss,'Expense')
    if next(a['kind'] for a in candidate['accounts'] if a['code']==counter)!='Asset' or candidate['account_details'][counter]['group'] in ('PPE','Accumulated depreciation','CWIP'):raise ValueError('Use a bank/cash or receivable ledger for disposal proceeds.')
    if counter in (a['ppe'],a['accum'],a['expense']) or gain==loss or loss==a['expense']:raise ValueError('Use separate disposal proceeds, gain and loss ledgers.')
    n=_due(candidate,a,on,on);acc=accumulated(candidate,a,on)+n;nbv=a['cost']-acc;difference=money-nbv
    lines=_pair(a['expense'],a['accum'],n,unit) if n else []
    lines.append(dict(account=a['ppe'],branch=unit,debit=0,credit=a['cost']))
    if acc:lines.append(dict(account=a['accum'],branch=unit,debit=acc,credit=0))
    if money:lines.append(dict(account=counter,branch=unit,debit=money,credit=0))
    if difference:lines.append(dict(account=gain if difference>0 else loss,branch=unit,debit=max(-difference,0),credit=max(difference,0)))
    e=_event(candidate,'Disposal',on,on,[dict(asset_id=asset_id,depreciation=n,branch=unit)],lines,proceeds=money,accumulated=acc,net_book_value=nbv,gain_loss=difference,basis=str(basis).strip())
    state.clear();state.update(candidate);return copy.deepcopy(e)


def validate_reversal(state,voucher_id,on):
    roots=gst._roots(state);root=roots.get(voucher_id,(voucher_id,1))[0]
    for a in state.get('book_assets',[]):
        own=[e for e in state['fixed_asset_events'] if e['voucher']==root and any(i['asset_id']==a['id'] for i in e['items'])]
        if root not in (a['cost_voucher'],a['accum_voucher']) and not own:continue
        own_index=state['fixed_asset_events'].index(own[0]) if own else -1
        later=[e for idx,e in enumerate(state['fixed_asset_events']) if idx>own_index and any(i['asset_id']==a['id'] for i in e['items']) and e['voucher']!=root and family(state,e['voucher'])==1]
        limit=own[0]['through'] if own else a['baseline']
        if later or any(p['active'] and p['effective']>limit for p in a['estimates'][1:]):raise ValueError('Reverse later asset postings and withdraw dependent estimate revisions before reversing this asset source.')
        if any(v['date']>on and roots[v['id']][0]==root for v in state['vouchers']):raise ValueError('Asset reversals must follow their source history chronologically.')


def report(state,start,end,branch='ALL'):
    core.verify_audit(state);day(start);day(end)
    if start>end or branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Choose valid asset report dates and scope.')
    register_rows=[];schedule=[];issues=[];expected={};detail=[];shifts=[]
    for a in state['book_assets']:
        if a['baseline']>end:continue
        live=present(state,a,end);retired=disposed(state,a,end);unit=branch_at(state,a,end)
        in_scope=branch=='ALL' or unit==branch
        actual=accumulated(state,a,end);expected_depn=target(a,end)
        if retired:
            disposal=next(e for e in events(state,a,end) if e['kind']=='Disposal');expected_depn=target(a,disposal['date'])
        opening_ok=not a['accum_voucher'] or family(state,a['accum_voucher'],end)==1
        status='Source reversed' if not live else 'Disposed' if retired else 'Ready' if opening_ok and actual==expected_depn else 'Review / unposted depreciation'
        if in_scope and live and (not opening_ok or actual!=expected_depn):issues.append(a['reference']+': '+status)
        if live and not retired:
            expected[(unit,a['ppe'])]=expected.get((unit,a['ppe']),0)+a['cost'];expected[(unit,a['accum'])]=expected.get((unit,a['accum']),0)-actual
        if in_scope:register_rows.append([a['reference'],a['name'],unit,a['ppe'],a['cost'],actual if live else 0,a['cost']-actual if live and not retired else 0,expected_depn if live else 0,expected_depn-actual if live else 0,status])
        if in_scope:
            for usage in a.get('shift_usage',[]):shifts.append([a['reference'],usage['start'],usage['end'],usage['factor'],'Active' if usage['active'] else 'Withdrawn',usage['basis']])
        p=policy(a,end) or a['estimates'][0]
        if in_scope:detail.append([a['reference'],a['category'],a['acquired'],a['put_to_use'],a['baseline'],p['months'],p['residual'],a['cost_voucher'],a['accum_voucher'],p['basis'],p.get('override_basis',''),p['id']])
        d=date.fromisoformat(start).replace(day=1)
        roots=gst._roots(state)
        while d<=date.fromisoformat(end):
            lo=max(start,d.isoformat(),a['baseline']);hi=min(end,(add_months(d.isoformat(),1)-timedelta(days=1)).isoformat())
            if lo<=hi:
                by_unit={}
                boundaries=[lo,*sorted({e['date'] for e in events(state,a,hi) if e['kind']=='Transfer' and lo<e['date']<=hi}),(date.fromisoformat(hi)+timedelta(days=1)).isoformat()]
                if live:
                    for begin,stop in zip(boundaries,boundaries[1:]):
                        last=(date.fromisoformat(stop)-timedelta(days=1)).isoformat()
                        if retired:last=min(last,disposal['date'])
                        if last<begin:continue
                        owner=branch_at(state,a,last);before=(date.fromisoformat(begin)-timedelta(days=1)).isoformat()
                        change=target(a,last)-max(a['opening_accum'],target(a,before));by_unit.setdefault(owner,[0,0])[0]+=change
                for e in state['fixed_asset_events']:
                    for i in e['items']:
                        if i['asset_id']!=a['id']:continue
                        signed=sum(sign for v in state['vouchers'] if lo<=v['date']<=hi for root,sign in [roots[v['id']]] if root==e['voucher'])
                        if signed and i['depreciation']:by_unit.setdefault(i['branch'],[0,0])[1]+=signed*i['depreciation']
                for owner,(planned,posted) in by_unit.items():
                    if branch=='ALL' or branch==owner:schedule.append([a['reference'],owner,lo,hi,planned,posted,planned-posted])
            d=add_months(d.isoformat(),1)
    proof=[]
    for unit in foundation.branches(state):
        if branch!='ALL' and branch!=unit:continue
        balances=core.balances(state,end,unit)
        for a in state['accounts']:
            if state['account_details'][a['code']]['group'] not in ('PPE','Accumulated depreciation'):continue
            n=expected.get((unit,a['code']),0);actual=balances[a['code']]
            proof.append([unit,a['code'],a['name'],n,actual,actual-n])
    unmapped=[i for i in range(len(state['assets'])) if (branch=='ALL' or state['assets'][i]['branch']==branch) and i not in {a.get('legacy_index') for a in state['book_assets']}]
    if unmapped:issues.append('Legacy calculator rows require source-linked review: '+', '.join(map(str,unmapped)))
    if any(r[-1] for r in proof):issues.append('PPE/accumulated-depreciation ledger reconciliation differences remain.')
    return dict(start=start,end=end,branch=branch,register=register_rows,schedule=schedule,proof=proof,policies=detail,issues=issues,ready=not issues,legacy_indices=unmapped,shift_usage=shifts)


def snapshots(state,start,end,branch='ALL'):
    r=report(state,start,end,branch);status='REVIEWED / RECONCILED' if r['ready'] else 'DRAFT — REVIEW REQUIRED'
    base=dict(entity=state['settings']['entity'],registration=copy.deepcopy(state['settings']['registration']),start=start,end=end,branch=branch,scope='All operating units' if branch=='ALL' else foundation.branches(state)[branch],prepared=datetime.now(timezone(timedelta(hours=5,minutes=30))).isoformat(),currency='INR',status=status,controls={},note=status+'. Monthly SLM with actual-day partial months and final residual cap. Schedule charges follow asset ownership; posted charges follow journal dates, so catch-up or dated reversals can create timing differences. Register sources are linked, not duplicated. Book depreciation is separate from Income Tax blocks. Review actual Schedule II category/life/residual, extra-shift applicability and technical justification; disposal proceeds exclude taxes accounted separately. '+('; '.join(r['issues']) or 'Ledger balances and posted depreciation agree with reviewed register.'))
    specs=[('Fixed asset register',['Reference','Asset','Unit','PPE ledger','Original cost INR','Lifetime book depreciation INR','Closing NBV INR','Target depreciation INR','Unposted INR','Status'],list(range(4,9)),r['register']),('Monthly book depreciation',['Reference','Unit','From','Through','Expected charge INR','Posted charge INR','Expected less posted INR'],list(range(4,7)),r['schedule']),('PPE ledger reconciliation',['Unit','Ledger','Name','Register Dr/(Cr) INR','Ledger Dr/(Cr) INR','Difference INR'],[3,4,5],r['proof']),('Asset estimate and source basis',['Reference','Category','Acquired','Put to use','Baseline','Remaining months','Residual INR','Cost voucher','Opening accumulated voucher','Reviewed basis','Override/opening basis','Estimate ID'],[6],r['policies']),('Reviewed extra-shift usage',['Reference','From','Through','SLM multiplier','Status','Eligibility/source basis'],[],r['shift_usage'])]
    return [dict(copy.deepcopy(base),mode=mode,columns=columns,money_columns=money,rows=rows,controls={'Absolute ledger differences':sum(abs(row[-1]) for row in r['proof'])} if mode=='PPE ledger reconciliation' else {}) for mode,columns,money,rows in specs]


def export(state,start,end,branch,path,kind):
    from . import financial_reports
    packs=snapshots(state,start,end,branch)
    if kind=='xlsx':financial_reports.export_pack_xlsx(packs,path)
    elif kind=='pdf':financial_reports.export_pdf(packs,path)
    elif kind=='json':Path(path).write_text(json.dumps(dict(report=report(state,start,end,branch),assets=state['book_assets'],events=state['fixed_asset_events']),ensure_ascii=False,indent=2),encoding='utf-8')
    else:raise ValueError('Choose Excel, PDF or JSON.')


def _check_alignment(state,on,branch):
    result=report(state,on,on,branch)
    if any(row[-1] for row in result['proof']):raise ValueError('Reconcile the PPE/accumulated-depreciation register to the ledgers before posting asset movements; unregistered or manual movements remain.')

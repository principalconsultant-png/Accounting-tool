"""Entity-level Income Tax WDV blocks, reviewed facts and frozen annual carry forwards.
No tax working calculation posts to the book ledger.
"""
import copy
import hashlib
import json
import uuid
from datetime import date,datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from . import core,foundation,fixed_assets as book,history,reconciliation as money

REFERENCES={'General plant — review category':'15','Furniture/fittings — reference':'10','Computers/software — reference':'40','Non-residential buildings — reference':'10','Residential buildings — reference':'5','Eligible intangibles excluding goodwill — reference':'25'}
SOURCE='Legacy Income-tax Act 1961 sections 32, 43(6), 50 and Appendix I references. Proposals only; retain the governing Act/rules for the selected FY/AY, category, regime and eligibility.'


def data(state):return state['tax_depreciation']
def _id():return str(uuid.uuid4())
def today():return datetime.now(history.INDIA).date().isoformat()
def year(value):
    if type(value) not in (int,str):raise ValueError('Enter a financial-year start year.')
    y=int(value)
    if not 1900<=y<=9998:raise ValueError('Use a financial-year start year from 1900 to 9998.')
    return y

def block(state,key):
    b=next((b for b in data(state)['blocks'] if b['id']==key and b['active']),None)
    if b is None:raise ValueError('Select an active tax block.')
    return b


def _open(state,y):
    if any(r['status']=='FINAL' and r['year']>=y for r in data(state)['reviews']):raise ValueError('Reopen this tax year and later finalized tax years before changing its source facts.')


def _basis(text,reviewed):
    if reviewed is not True or not str(text).strip():raise ValueError('Review the tax category, source, year/regime and eligibility and retain the supporting basis.')
    return str(text).strip()


def _allocations(state,values):
    units=foundation.branches(state);result={u:dict(wdv=0,count=0) for u in units}
    for u,v in values.items():
        if u not in units:raise ValueError('Unknown opening-allocation operating unit.')
        n=money.amount(v.get('wdv','0'));count=v.get('count',0)
        if type(count)!=int or count<0 or n<0 or n and not count:raise ValueError('Enter nonnegative WDV and whole asset/control counts; positive WDV requires assets.')
        result[u]=dict(wdv=n,count=count)
    return result


def save_block(state,key,name,start_year,allocations,basis,reviewed=False):
    y=year(start_year);_open(state,y);basis=_basis(basis,reviewed);key=str(key).strip();name=str(name).strip()
    if not key or not name or any(b['active'] and b['key'].casefold()==key.casefold() for b in data(state)['blocks']):raise ValueError('Enter a unique block key and name; same-rate statutory categories may use separate reviewed blocks.')
    b=dict(id=_id(),key=key,name=name,start_year=y,active=True,openings=[dict(id=_id(),allocations=_allocations(state,allocations),basis=basis)])
    data(state)['blocks'].append(b);core.add_audit(state,'TAX_BLOCK_CREATED',copy.deepcopy(b));return copy.deepcopy(b)


def revise_opening(state,block_id,allocations,basis,reviewed=False):
    b=block(state,block_id);_open(state,b['start_year']);p=dict(id=_id(),allocations=_allocations(state,allocations),basis=_basis(basis,reviewed))
    b['openings'].append(p);core.add_audit(state,'TAX_BLOCK_OPENING_REVISED',dict(block_id=block_id,opening=copy.deepcopy(p)));return copy.deepcopy(p)


def save_rule(state,block_id,effective_year,rate,basis,reviewed=False,additional_rate='0',additional_enabled=False,threshold=180,short_factor='0.5',rounding='Paise'):
    block(state,block_id);y=year(effective_year);_open(state,y);basis=_basis(basis,reviewed)
    r=Decimal(str(rate));ar=Decimal(str(additional_rate));factor=Decimal(str(short_factor))
    if not all(n.is_finite() for n in (r,ar,factor)) or not 0<r<=100 or not 0<=ar<=100 or not 0<factor<=1 or type(threshold)!=int or not 1<=threshold<=366 or rounding not in ('Paise','Whole rupee') or type(additional_enabled)!=bool:raise ValueError('Review valid WDV/additional rates, short-use threshold/factor and rounding.')
    p=dict(id=_id(),block_id=block_id,effective_year=y,rate=str(r),additional_rate=str(ar),additional_enabled=additional_enabled,threshold=threshold,short_factor=str(factor),rounding=rounding,basis=basis,reviewed=True,source=SOURCE)
    data(state)['rules'].append(p);core.add_audit(state,'TAX_DEPRECIATION_RULE_SAVED',copy.deepcopy(p));return copy.deepcopy(p)


def _rule(state,b,y):
    candidates=[r for r in data(state)['rules'] if r['block_id']==b['id'] and r['effective_year']<=y]
    return copy.deepcopy(max(enumerate(candidates),key=lambda p:(p[1]['effective_year'],p[0]))[1]) if candidates else None


def add_asset(state,block_id,reference,branch,acquired,cost,basis,reviewed=False,put_to_use='',book_asset_id='',additional_eligible=False,additional_basis=''):
    b=block(state,block_id);acquired=book.day(acquired);_open(state,core.financial_year(acquired));basis=_basis(basis,reviewed);n=money.amount(cost);reference=str(reference).strip()
    if branch not in foundation.branches(state) or n<=0 or not reference or any(a['active'] and a['reference'].casefold()==reference.casefold() for a in data(state)['additions']):raise ValueError('Enter a unique tax addition reference, unit and positive actual tax cost (one asset/component per record).')
    if type(additional_eligible)!=bool or additional_eligible and not str(additional_basis).strip():raise ValueError('Additional depreciation requires an explicit eligibility/new-plant/regime basis; hospital assets do not qualify automatically.')
    source=None
    if book_asset_id:
        a=book.asset(state,book_asset_id)
        if any(t['active'] and t.get('book_asset_id')==book_asset_id for t in data(state)['additions']):raise ValueError('This book asset already has a live tax addition; do not count it twice.')
        source=copy.deepcopy(a)
        if a['acquired']!=acquired:raise ValueError('Linked acquisition date must agree with the book asset. Explain tax-cost adjustments in the reviewed basis.')
    a=dict(id=_id(),block_id=block_id,reference=reference,branch=branch,acquired=acquired,cost=n,basis=basis,active=True,book_asset_id=book_asset_id,book_source=source,additional_eligible=additional_eligible,additional_basis=str(additional_basis).strip())
    # Validate all dates before changing any state.
    if put_to_use:
        book.day(put_to_use)
        if put_to_use<acquired or core.financial_year(put_to_use)<b['start_year']:raise ValueError('First use must follow acquisition and fall in or after the opening tax year. Previously used assets belong in opening WDV.')
        _open(state,core.financial_year(put_to_use))
    data(state)['additions'].append(a)
    if put_to_use:data(state)['uses'].append(dict(id=_id(),addition_id=a['id'],date=put_to_use,basis=basis,active=True))
    core.add_audit(state,'TAX_ASSET_ADDED',dict(asset=copy.deepcopy(a),first_use=[copy.deepcopy(u) for u in data(state)['uses'] if u['addition_id']==a['id']]));return copy.deepcopy(a)


def commission(state,addition_id,on,basis,reviewed=False):
    a=_addition(state,addition_id);on=book.day(on);_open(state,core.financial_year(on));basis=_basis(basis,reviewed)
    if on<a['acquired'] or core.financial_year(on)<block(state,a['block_id'])['start_year'] or _use(state,a):raise ValueError('Use one reviewed first-use date after acquisition and the opening tax year.')
    if any(d['active'] and d['addition_id']==a['id'] and d['date']<on for d in data(state)['disposals']):raise ValueError('An asset sold before commissioning cannot subsequently be put to use.')
    u=dict(id=_id(),addition_id=addition_id,date=on,basis=basis,active=True);data(state)['uses'].append(u);core.add_audit(state,'TAX_ASSET_COMMISSIONED',copy.deepcopy(u));return copy.deepcopy(u)


def _addition(state,key):
    a=next((a for a in data(state)['additions'] if a['id']==key and a['active']),None)
    if a is None:raise ValueError('Select a live tax addition.')
    return a

def _use(state,a):return next((u['date'] for u in data(state)['uses'] if u['active'] and u['addition_id']==a['id']),None)


def dispose(state,block_id,reference,branch,on,consideration,expenses,basis,reviewed=False,addition_id='',count=1):
    b=block(state,block_id);on=book.day(on);y=core.financial_year(on);_open(state,y);basis=_basis(basis,reviewed);reference=str(reference).strip();n=money.amount(consideration);x=money.amount(expenses)
    if y<b['start_year'] or n<0 or x<0 or type(count)!=int or count<=0 or branch not in foundation.branches(state) or not reference or any(d['active'] and d['reference'].casefold()==reference.casefold() for d in data(state)['disposals']):raise ValueError('Enter a unique disposal reference, valid unit/date, nonnegative moneys payable/transfer expenses and positive whole count.')
    if addition_id:
        a=_addition(state,addition_id)
        if a['block_id']!=block_id or on<a['acquired'] or count!=1 or branch!=a['branch'] or any(d['active'] and d['addition_id']==addition_id for d in data(state)['disposals']):raise ValueError('A referenced addition can be disposed once, in its original tax attribution unit, after acquisition, with count one.')
    d=dict(id=_id(),block_id=block_id,reference=reference,branch=branch,date=on,consideration=n,expenses=x,basis=basis,addition_id=addition_id,count=count,active=True)
    candidate=copy.deepcopy(state);data(candidate)['disposals'].append(d);result=calculate(candidate,y)
    item=next(r for r in result['blocks'] if r['id']==block_id)
    if item['count_error']:raise ValueError('Disposals exceed the available block/control asset count for this unit.')
    data(state)['disposals'].append(d);core.add_audit(state,'TAX_ASSET_DISPOSAL_RECORDED',copy.deepcopy(d));return copy.deepcopy(d)


def additional_claim(state,addition_id,claim_year,amount,carry,basis,reviewed=False):
    a=_addition(state,addition_id);y=year(claim_year);_open(state,y);basis=_basis(basis,reviewed);n=money.amount(amount);c=money.amount(carry)
    if min(n,c)<0 or not a['additional_eligible']:raise ValueError('Review a specifically eligible asset and nonnegative claim/deferred amounts.')
    report=calculate(state,y);owner=next(r for r in report['blocks'] if r['id']==a['block_id'])
    if (n or c) and (not owner['continued'] or not owner['allowance_supported'] or not owner['rule']['additional_enabled']):raise ValueError('A ceased block or disallowed additional-depreciation regime cannot have a positive claim/carry.')
    row=next((r for b in report['blocks'] for r in b['additional_rows'] if r['addition_id']==addition_id),None)
    if row is None or n>row['maximum_claim'] or c>row['maximum_carry']:raise ValueError('Claim/deferred amounts exceed the source entitlement or belong to another year.')
    record=dict(id=_id(),addition_id=addition_id,year=y,amount=n,carry=c,basis=basis,active=True)
    for old in data(state)['claims']:
        if old['addition_id']==addition_id and old['year']==y:old['active']=False
    data(state)['claims'].append(record);core.add_audit(state,'TAX_ADDITIONAL_CLAIM_REVIEWED',copy.deepcopy(record));return copy.deepcopy(record)


def void_record(state,kind,record_id,reason):
    if kind not in ('additions','uses','disposals','claims') or not str(reason).strip():raise ValueError('Select a source kind and record ID and give a reason.')
    r=next((r for r in data(state)[kind] if r['id']==record_id and r['active']),None)
    if not r:raise ValueError('Select an active tax source record.')
    y=r['year'] if kind=='claims' else core.financial_year(r['acquired'] if kind=='additions' else r['date']);_open(state,y)
    if kind=='additions':
        if any(d['active'] and d['addition_id']==record_id for d in data(state)['disposals']) or any(c['active'] and c['addition_id']==record_id for c in data(state)['claims']):raise ValueError('Void dependent disposal/claim records first.')
        for use in data(state)['uses']:
            if use['addition_id']==record_id:use['active']=False
    r['active']=False;core.add_audit(state,'TAX_DEPRECIATION_SOURCE_VOIDED',dict(kind=kind,id=record_id,reason=str(reason).strip()))


def _rounded(value,rule):
    quantum=100 if rule['rounding']=='Whole rupee' else 1
    return int((Decimal(value)/quantum).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*quantum


def allocate(total,weights):
    positive={k:max(0,v) for k,v in weights.items()};den=sum(positive.values());result={k:0 for k in weights}
    if not total:return result
    if not den:raise ValueError('No positive management-allocation weights.')
    for k,w in positive.items():result[k]=total*w//den
    for k in sorted(weights,key=lambda k:(-(total*positive[k]%den),k))[:total-sum(result.values())]:result[k]+=1
    return result


def _block_year(state,b,y,opening,counts,incoming):
    start,end=core.fy_bounds(y);rule=_rule(state,b,y);issues=[];units=foundation.branches(state);full={u:0 for u in units};short={u:0 for u in units};sales_full={u:0 for u in units};sales_short={u:0 for u in units};opening_counts=dict(counts);opening_removed={u:0 for u in foundation.branches(state)};counts=dict(counts);facts=[];pending=[];source_rows=[];additional=[];carry_out={};realizations=expenses=0
    if rule is None:
        issues.append('Missing reviewed effective-year tax rule.');rule=dict(id=None,rate='0',additional_rate='0',additional_enabled=False,threshold=180,short_factor='0.5',rounding='Paise',basis='Missing rule',source=SOURCE)
    additions=[a for a in data(state)['additions'] if a['active'] and a['block_id']==b['id'] and a['acquired']<=end]
    disposals=[d for d in data(state)['disposals'] if d['active'] and d['block_id']==b['id'] and start<=d['date']<=end]
    for a in additions:
        use=_use(state,a);sale=next((d for d in data(state)['disposals'] if d['active'] and d['addition_id']==a['id'] and d['date']<=end),None)
        if core.financial_year(a['acquired'])==y or use and core.financial_year(use)==y or not sale and (not use or use>end):
            source_rows.append(['Tax addition / actual-cost source',a['reference'],a['branch'],a['acquired'],a['cost'],0,(a['book_source']['reference']+' / '+a['book_source']['cost_voucher']) if a['book_source'] else 'Manual tax source',a['basis']])
        if a['book_source'] and a['book_source']['baseline']<=end and book.family(state,a['book_source']['cost_voucher'],end)!=1:issues.append(a['reference']+': linked book acquisition is reversed; review the tax basis.')
        if not use or use>end or sale and sale['date']<use:
            if not sale:pending.append([a['reference'],a['branch'],a['acquired'],use or 'Not commissioned',a['cost'],'Excluded until actual first use'])
            if sale and start<=sale['date']<=end:pending.append([a['reference'],a['branch'],a['acquired'],sale['date'],a['cost'],'Sold before use: outside this depreciable block; separate capital result review'])
            continue
        uy=core.financial_year(use)
        if uy<b['start_year']:issues.append(a['reference']+': use predates opening tax year; include it in opening WDV instead.');continue
        if uy!=y:continue
        days=(date.fromisoformat(min(end,sale['date'] if sale else end))-date.fromisoformat(use)).days+1
        half=a['acquired']>=start and days<rule['threshold'];cohort=short if half else full;cohort[a['branch']]+=a['cost'];counts[a['branch']]+=1
        facts.append([a['reference'],a['branch'],a['acquired'],use,days,'Short-use' if half else 'Full rate',a['cost']])
        if a['additional_eligible']:
            entitlement=_rounded(Decimal(a['cost'])*Decimal(rule['additional_rate'])/100,rule);factor=Decimal(rule['short_factor']) if half else Decimal(1)
            maximum=_rounded(Decimal(entitlement)*factor,rule);deferred=entitlement-maximum
            additional.append(dict(addition_id=a['id'],reference=a['reference'],branch=a['branch'],maximum_claim=maximum,maximum_carry=deferred,proposal=maximum if not sale and rule['additional_enabled'] else 0,carry_proposal=deferred if not sale and rule['additional_enabled'] else 0,needs_review=bool(sale) or not rule['additional_enabled'],basis=a['additional_basis']))
    for source in incoming.values():
        a=_addition(state,source['addition_id']);sale=next((d for d in data(state)['disposals'] if d['active'] and d['addition_id']==a['id'] and d['date']<=end),None)
        additional.append(dict(addition_id=a['id'],reference=a['reference'],branch=source['branch'],maximum_claim=source['amount'],maximum_carry=0,proposal=source['amount'] if rule['additional_enabled'] and not sale else 0,carry_proposal=0,needs_review=bool(sale) or not rule['additional_enabled'],basis='Frozen FY '+str(source.get('origin_year',y-1))+' rule '+str(source.get('origin_rule_id','legacy'))+' deferred entitlement'))
    for d in disposals:
        source_rows.append(['Disposal source (gross, expenses separate)',d['reference'],d['branch'],d['date'],d['consideration'],d['expenses'],_addition(state,d['addition_id'])['reference'] if d['addition_id'] else 'Opening assets: count '+str(d['count']),d['basis']])
        half=False
        if d['addition_id']:
            a=_addition(state,d['addition_id']);use=_use(state,a)
            if not use or use>d['date']:continue
            half=core.financial_year(use)==y and a['acquired']>=start and (date.fromisoformat(d['date'])-date.fromisoformat(use)).days+1<rule['threshold']
        if not d['addition_id'] or core.financial_year(_use(state,a))<y:opening_removed[d['branch']]+=d['count']
        counts[d['branch']]-=d['count'];(sales_short if half else sales_full)[d['branch']]+=d['consideration'];realizations+=d['consideration'];expenses+=d['expenses']
    count_error=any(n<0 for n in counts.values()) or any(opening_removed[u]>opening_counts[u] for u in units)
    if count_error:issues.append('Negative block/control asset counts: disposal source allocations require correction.')
    base=sum(opening.values())+sum(full.values())+sum(short.values());remaining=max(0,base-realizations);continued=sum(counts.values())>0
    # Offset each realization against its actual full/short cohort, then net negative pools.
    status_review=copy.deepcopy(next((r for r in reversed(data(state)['status_reviews']) if r['block_id']==b['id'] and r['year']==y),None))
    unused={u:sum(row[4] for row in pending if row[1]==u and row[-1].startswith('Excluded')) for u in units}
    allowance_supported=True
    if status_review:
        continued=status_review['status']!='Ceased; unused costs excluded';allowance_supported=status_review['status']!='Continuing; no current allowance'
        if not continued and sum(counts.values())>0 or continued and sum(counts.values())<=0 and not sum(unused.values()):issues.append('Reviewed block status conflicts with remaining asset/control counts; correct source counts.')
        source_rows.append(['Block status / allowance review',status_review['id'],'ALL',start,0,0,status_review['status'],status_review['basis']])
    elif not continued and sum(unused.values()) and base+realizations:issues.append('Unused assets remain when in-use assets cease: explicitly review statutory block status and allowance before finalizing.')
    f=sum(opening.values())+sum(full.values())-sum(sales_full.values());h=sum(short.values())-sum(sales_short.values())
    eligible_full=max(0,f+min(0,h));eligible_short=max(0,h+min(0,f));normal_full=_rounded(Decimal(eligible_full)*Decimal(rule['rate'])/100,rule) if continued and allowance_supported else 0;normal_short=_rounded(Decimal(eligible_short)*Decimal(rule['rate'])/100*Decimal(rule['short_factor']),rule) if continued and allowance_supported else 0
    normal_full=min(eligible_full,normal_full);normal_short=min(eligible_short,normal_short)
    normal=min(remaining,normal_full+normal_short);claims={u:0 for u in units}
    for row in additional:
        override=next((c for c in reversed(data(state)['claims']) if c['active'] and c['year']==y and c['addition_id']==row['addition_id']),None)
        if not allowance_supported:row.update(proposal=0,carry_proposal=0,needs_review=True)
        claimed=override['amount'] if override else row['proposal'] if continued else 0;deferred=override['carry'] if override else row['carry_proposal'] if continued else 0
        if claimed>row['maximum_claim'] or deferred>row['maximum_carry']:issues.append(row['reference']+': additional claim exceeds current entitlement.')
        if (claimed or deferred) and (not rule['additional_enabled'] or not allowance_supported):issues.append(row['reference']+': additional claim conflicts with the reviewed regime/current-allowance status.')
        if not continued and (claimed or deferred):issues.append(row['reference']+': no additional allowance/carry on a ceased block.')
        if (row['needs_review'] or not continued) and override is None:issues.append(row['reference']+': review additional claim/forfeiture explicitly for disposal, cessation or regime.')
        row.update(claim=claimed,carry=deferred,review='Explicit reviewed override' if override else 'Eligible proposal',claim_basis=override['basis'] if override else row['basis']);claims[row['branch']]+=claimed
        if deferred:carry_out[row['addition_id']]=dict(addition_id=row['addition_id'],branch=row['branch'],amount=deferred,origin_year=y,origin_rule_id=rule['id'])
    additional_total=min(max(0,remaining-normal),sum(claims.values())) if continued else 0
    if sum(claims.values())!=additional_total:issues.append('Additional claim exceeds remaining tax basis; explicitly review reduced claims before finalizing.')
    gain=max(0,realizations-expenses-base);loss=max(0,base+expenses-realizations) if not continued and base+realizations+expenses else 0
    closing=remaining-normal-additional_total if continued else 0
    weights={u:max(0,opening[u]+full[u]+short[u]-sales_full[u]-sales_short[u]) if counts[u]>0 else 0 for u in units}
    if not sum(weights.values()):weights={u:max(0,counts[u]) for u in units}
    if not sum(weights.values()):weights=unused
    closing_units=allocate(closing,weights);normal_units=allocate(normal,weights) if normal else {u:0 for u in units};add_units=allocate(additional_total,claims) if additional_total else {u:0 for u in units}
    branches=[]
    for u in units:
        sale=sales_full[u]+sales_short[u];bridge=closing_units[u]-(opening[u]+full[u]+short[u]-sale-normal_units[u]-add_units[u])
        branches.append([b['key'],u,opening[u],full[u],short[u],sale,bridge,normal_units[u],add_units[u],closing_units[u],counts[u]])
    return dict(id=b['id'],key=b['key'],name=b['name'],year=y,rule=rule,opening=sum(opening.values()),full=sum(full.values()),short=sum(short.values()),realizations=realizations,transfer_expenses=expenses,eligible_full=eligible_full,eligible_short=eligible_short,normal_full=normal_full,normal_short=normal_short,normal=normal,additional=additional_total,closing=closing,gain=gain,loss=loss,continued=continued,allowance_supported=allowance_supported,status_review=status_review,counts=counts,count_error=count_error,closing_units=closing_units,carry=carry_out,branches=branches,facts=facts,pending=pending,source_rows=source_rows,additional_rows=additional,issues=issues,proof=closing-(remaining-normal-additional_total if continued else 0))


def calculate(state,requested_year):
    core.verify_audit(state);y=year(requested_year)
    frozen=next((r for r in reversed(data(state)['reviews']) if r['year']==y and r['status']=='FINAL'),None)
    if frozen:return dict(copy.deepcopy(frozen['report']),finalized_review_id=frozen['id'])
    blocks=[];issues=[]
    for b in data(state)['blocks']:
        if not b['active'] or b['start_year']>y:continue
        opening={u:v['wdv'] for u,v in b['openings'][-1]['allocations'].items()};counts={u:v['count'] for u,v in b['openings'][-1]['allocations'].items()};incoming={};unfinalized=[]
        for n in range(b['start_year'],y+1):
            for u in foundation.branches(state):opening.setdefault(u,0);counts.setdefault(u,0)
            result=_block_year(state,b,n,opening,counts,incoming)
            previous=next((r for r in reversed(data(state)['reviews']) if r['status']=='FINAL' and r['year']==n-1),None)
            result['opening_source']=copy.deepcopy(b['openings'][-1]) if n==b['start_year'] else dict(id=previous['id'] if previous else 'Provisional',basis='Carry from FY '+str(n-1)+' / '+(previous['basis'] if previous else 'Prior year not finalized'))
            if n==y:break
            seal=next((r for r in reversed(data(state)['reviews']) if r['status']=='FINAL' and r['year']==n),None)
            if seal:
                frozen=next((r for r in seal['report']['blocks'] if r['id']==b['id']),None)
                if frozen is None:issues.append(b['key']+': block missing in finalized opening carry.');unfinalized.append(n)
                else:result=frozen
            else:unfinalized.append(n)
            opening=copy.deepcopy(result['closing_units']);counts=copy.deepcopy(result['counts']);incoming=copy.deepcopy(result['carry'])
        if unfinalized:result['issues'].append('Prior tax years are provisional; finalize carry forwards first: '+', '.join(map(str,unfinalized)))
        blocks.append(result);issues += [b['key']+': '+s for s in result['issues']]
    if not blocks:issues.append('No active tax blocks/opening balances for this financial year.')
    return dict(year=y,start=core.fy_bounds(y)[0],end=core.fy_bounds(y)[1],blocks=blocks,issues=issues,ready=not issues,provisional=core.fy_bounds(y)[1]>today(),normal=sum(b['normal'] for b in blocks),additional=sum(b['additional'] for b in blocks),closing=sum(b['closing'] for b in blocks),capital_gain=sum(b['gain'] for b in blocks),capital_loss=sum(b['loss'] for b in blocks))


def finalize(state,requested_year,basis,reviewed=False):
    y=year(requested_year);_open(state,y);basis=_basis(basis,reviewed);r=calculate(state,y)
    if not r['ready'] or r['provisional']:raise ValueError('Finish the tax year, resolve all draft issues and finalize prior carry forwards before freezing this year.')
    review=dict(id=_id(),year=y,status='FINAL',basis=basis,report=copy.deepcopy(r),digest=hashlib.sha256(history.encoded(r)).hexdigest());data(state)['reviews'].append(review);core.add_audit(state,'TAX_DEPRECIATION_YEAR_FINALIZED',copy.deepcopy(review));return copy.deepcopy(review)


def reopen(state,requested_year,reason):
    y=year(requested_year)
    if not str(reason).strip() or any(r['status']=='FINAL' and r['year']>y for r in data(state)['reviews']):raise ValueError('Give a reason and reopen later finalized tax years first.')
    r=next((r for r in reversed(data(state)['reviews']) if r['status']=='FINAL' and r['year']==y),None)
    if r is None:raise ValueError('Select a finalized tax year.')
    r['status']='REOPENED';core.add_audit(state,'TAX_DEPRECIATION_YEAR_REOPENED',dict(id=r['id'],year=y,reason=str(reason).strip()))


def validate_reversal(state,voucher_id,on):
    root=book.gst._roots(state).get(voucher_id,(voucher_id,1))[0]
    if any(a['active'] and a['book_source'] and a['book_source']['cost_voucher']==root for a in state.get('tax_depreciation',{}).get('additions',[])):_open(state,core.financial_year(on))


def snapshots(state,requested_year,branch='ALL'):
    r=calculate(state,requested_year);units=foundation.branches(state)
    if branch!='ALL' and branch not in units:raise ValueError('Choose a valid tax management-allocation scope.')
    status='FINALIZED WORKING' if r.get('finalized_review_id') else 'DRAFT / PROVISIONAL' if r['issues'] or r['provisional'] else 'REVIEWED WORKING'
    note=status+'. Entity statutory tax blocks; unit amounts are management allocations by positive net basis (fallback remaining asset/control counts), not separate taxable entities. Disposal realizations offset their actual full/short cohort, then excess offsets the other cohort. Transfer expenses affect section-50 capital results, not gross WDV reductions. Negative unit movements are bridged explicitly; book transfers do not create tax disposals. Rates, first-use and additional eligibility require reviewed year/regime sources. No journal is posted. '+('; '.join(r['issues']) or 'Annual figures reconcile; client tax review remains required.')
    base=dict(entity=state['settings']['entity'],registration=copy.deepcopy(state['settings']['registration']),start=r['start'],end=r['end'],branch=branch,scope='Entity tax blocks and all unit allocations' if branch=='ALL' else units[branch]+' management allocation; entity tax block summary retained',prepared=datetime.now(history.INDIA).isoformat(timespec='seconds'),currency='INR',status=status,note=note,controls={})
    summary=[];branches=[];facts=[];pending=[];additional=[];rules=[];sources=[]
    for b in r['blocks']:
        summary.append([b['key'],b['name'],b['opening'],b['full'],b['short'],b['realizations'],b['normal'],b['additional'],b['closing'],b['gain'],b['loss'],'Continuing' if b['continued'] else 'Ceased / empty'])
        branches.extend(row for row in b['branches'] if branch=='ALL' or row[1]==branch)
        facts.extend([[b['key'],*row] for row in b['facts'] if branch=='ALL' or row[1]==branch]);pending.extend([[b['key'],*row] for row in b['pending'] if branch=='ALL' or row[1]==branch])
        additional.extend([[b['key'],row['reference'],row['branch'],row['maximum_claim'],row['maximum_carry'],row['claim'],row['carry'],row['review'],row['claim_basis']] for row in b['additional_rows'] if branch=='ALL' or row['branch']==branch])
        sources.extend([[b['key'],*row] for row in b['source_rows'] if branch=='ALL' or row[2] in (branch,'ALL')])
        sources.extend([[b['key'],'Opening WDV source',b['opening_source']['id'],row[1],r['start'],row[2],0,'Original opening / frozen prior-year carry',b['opening_source']['basis']] for row in b['branches'] if branch=='ALL' or row[1]==branch])
        p=b['rule'];rules.append([b['key'],p['id'] or 'Missing',p['rate'],p['threshold'],p['short_factor'],p['additional_enabled'],p['additional_rate'],p['rounding'],p['basis'],p['source']])
    specs=[('Entity tax WDV blocks',['Block','Name','Opening WDV INR','Full-rate additions INR','Short-use additions INR','Gross realizations INR','Normal depreciation INR','Additional depreciation INR','Closing WDV INR','Depreciable-block gain INR','Depreciable-block loss INR','Block status'],list(range(2,11)),summary),('Tax unit allocation bridge',['Block','Unit','Opening WDV INR','Full additions INR','Short additions INR','Gross realizations INR','Pooling/capital adjustment INR','Normal depreciation INR','Additional depreciation INR','Closing WDV INR','Remaining control count'],list(range(2,10)),branches),('Tax additions and first use',['Block','Asset reference','Unit','Acquired','First use','Days actually used','Cohort','Actual tax cost INR'],[7],facts),('Tax unused and excluded assets',['Block','Asset reference','Unit','Acquired','Use / disposal date','Actual cost INR','Tax pool treatment'],[5],pending),('Additional depreciation review',['Block','Asset reference','Unit','Maximum claim INR','Maximum deferred INR','Reviewed claim INR','Next-year deferred INR','Status','Eligibility / source basis'],[3,4,5,6],additional),('Tax rates and annual policy',['Block','Rule revision','WDV rate %','Short-use days','Short-use factor','Additional allowed','Additional rate %','Rounding','Reviewed year/regime basis','Reference source'],[],rules),('Tax opening and transaction basis',['Block','Source kind','Reference / revision','Unit','Source date','Tax cost / gross INR','Transfer expenses INR','Related asset / source','Reviewed basis'],[5,6],sources)]
    return [dict(copy.deepcopy(base),mode=mode,columns=cols,money_columns=money_columns,rows=rows,controls={'Entity minus allocated closing WDV':r['closing']-sum(row[9] for b in r['blocks'] for row in b['branches'])} if mode=='Tax unit allocation bridge' else {}) for mode,cols,money_columns,rows in specs]


def export(state,requested_year,branch,path,kind):
    from . import financial_reports
    packs=snapshots(state,requested_year,branch)
    if kind=='xlsx':financial_reports.export_pack_xlsx(packs,path)
    elif kind=='pdf':financial_reports.export_pdf(packs,path)
    elif kind=='json':
        from pathlib import Path
        Path(path).write_text(json.dumps(calculate(state,requested_year),ensure_ascii=False,indent=2),encoding='utf-8')
    else:raise ValueError('Choose Excel, PDF or JSON.')


def deactivate_block(state,block_id,reason):
    b=block(state,block_id);_open(state,b['start_year'])
    if not str(reason).strip() or any(a['active'] and a['block_id']==block_id for a in data(state)['additions']) or any(d['active'] and d['block_id']==block_id for d in data(state)['disposals']):raise ValueError('Give a reason and void dependent live tax facts before deactivating an unused block.')
    b['active']=False;core.add_audit(state,'TAX_BLOCK_DEACTIVATED',dict(id=block_id,reason=str(reason).strip()))


def review_block_status(state,block_id,requested_year,status,basis,reviewed=False):
    b=block(state,block_id);y=year(requested_year);_open(state,y);basis=_basis(basis,reviewed)
    if y<b['start_year'] or status not in ('Ceased; unused costs excluded','Continuing; allowance supported','Continuing; no current allowance'):raise ValueError('Select a valid block-year status and current-allowance treatment.')
    r=dict(id=_id(),block_id=block_id,year=y,status=status,basis=basis);data(state)['status_reviews'].append(r);core.add_audit(state,'TAX_BLOCK_STATUS_REVIEWED',copy.deepcopy(r));return copy.deepcopy(r)

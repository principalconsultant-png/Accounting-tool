"""Reviewed statement presentation, disclosures and current-tax working papers."""
import copy
import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from . import core,foundation,financial_reports as f

FRAMEWORKS=('Schedule III Division I (AS)','Schedule III Division II (Ind AS)','Other reviewed presentation')
SOURCE='https://www.mca.gov.in/Ministry/pdf/ScheduleIIIAmendmentNotification_24032021.pdf'
DISCLOSURES=('Entity and applicable framework','Basis and accounting policies','Share capital and promoters','Borrowings and security','Trade payable ageing and MSME','Trade receivable ageing','PPE and intangible movements','CWIP ageing and completion','Revenue and other income','Employee benefits and related parties','Commitments and contingencies','Tax current and deferred','Ratios and explanations','Title deeds and revaluation','Loans and advances to specified persons','Benami and struck-off companies','Charges and wilful defaulter','Utilisation of borrowed funds and intermediaries','Undisclosed income CSR and crypto','Subsequent events and going concern','Ind AS OCI equity changes and financial instruments')
SECTIONS={
 'Asset':('Non-current assets: PPE','Non-current assets: CWIP','Non-current assets: financial assets','Non-current assets: other','Current assets: inventories','Current assets: trade receivables','Current assets: cash and equivalents','Current assets: other financial assets','Current assets: current tax assets','Current assets: other'),
 'Liability':('Non-current liabilities: borrowings','Non-current liabilities: provisions','Non-current liabilities: deferred tax','Non-current liabilities: other','Current liabilities: borrowings','Current liabilities: trade payables','Current liabilities: provisions','Current liabilities: current tax','Current liabilities: other'),
 'Equity':('Equity: capital','Equity: other equity'),
 'Revenue':('Revenue from operations','Other income'),
 'Expense':('Cost of materials and purchases','Employee benefits expense','Finance costs','Depreciation and amortisation','Other expenses','Current tax expense','Deferred tax expense','OCI expense')}


def proposal(state):
    result={}
    for a in state['accounts']:
        group=state['account_details'].get(a['code'],{}).get('group','');kind=a['kind']
        if kind=='Asset':section={'PPE':SECTIONS[kind][0],'Accumulated depreciation':SECTIONS[kind][0],'CWIP':SECTIONS[kind][1],'Cash and bank':SECTIONS[kind][6],'Inventory':SECTIONS[kind][4],'Patient control':SECTIONS[kind][5],'Payment clearing':SECTIONS[kind][7]}.get(group,SECTIONS[kind][-1])
        elif kind=='Liability':section={'Trade payables':SECTIONS[kind][5],'Borrowings':SECTIONS[kind][0]}.get(group,SECTIONS[kind][-1])
        elif kind=='Equity':section=SECTIONS[kind][0] if group=='Capital' else SECTIONS[kind][1]
        elif kind=='Revenue':section=SECTIONS[kind][1] if group=='Other revenue' else SECTIONS[kind][0]
        else:section={'Medical costs':SECTIONS[kind][0],'Employee benefits':SECTIONS[kind][1],'Finance costs':SECTIONS[kind][2],'Depreciation':SECTIONS[kind][3],'Income tax':SECTIONS[kind][5]}.get(group,SECTIONS[kind][4])
        result[a['code']]=dict(section=section,note='N-'+a['code'],basis='Proposed from ledger group; verify maturity, nature and applicable standard')
    return result


def save_policy(state,values):
    if not values.get('confirmed') or not str(values.get('basis','')).strip():raise ValueError('Review legal applicability, mappings and source basis explicitly.')
    framework=values['framework']
    if framework not in FRAMEWORKS:raise ValueError('Select Division I, Division II or another reviewed framework; NBFC Division III is not supported.')
    start,end=values['start'],values['end']
    if date.fromisoformat(start).isoformat()!=start or date.fromisoformat(end).isoformat()!=end or start>end:raise ValueError('Review statement period dates.')
    mappings=copy.deepcopy(values['mappings']);accounts={a['code']:a for a in state['accounts']}
    if set(mappings)!=set(accounts):raise ValueError('Map every current ledger exactly once, including zero-balance controls.')
    for code,m in mappings.items():
        if m.get('section') not in SECTIONS[accounts[code]['kind']] or not m.get('note','').strip() or not m.get('basis','').strip():raise ValueError('Each ledger requires a valid kind-specific section, note reference and classification basis: '+code)
        if m['section']=='OCI expense' and framework!=FRAMEWORKS[1]:raise ValueError('OCI requires reviewed Division II presentation.')
    notes=copy.deepcopy(values.get('disclosures',{}))
    for title,n in notes.items():
        if title not in DISCLOSURES or n.get('status') not in ('Reviewed','Not applicable','Pending') or not n.get('text','').strip():raise ValueError('Disclosures need a known title, status and supporting text.')
    clearing=values.get('clearing_accounts',['1130'])
    if not clearing or any(c not in accounts or accounts[c]['kind']!='Asset' for c in clearing):raise ValueError('Review actual inter-branch clearing asset ledgers.')
    row=dict(id=str(uuid.uuid4()),framework=framework,start=start,end=end,basis=values['basis'].strip(),mappings=mappings,disclosures=notes,clearing_accounts=sorted(set(clearing)),source=SOURCE)
    state.setdefault('statement_policies',[]).append(row);core.add_audit(state,'STATEMENT_POLICY_REVIEWED',copy.deepcopy(row));return row


def policy(state,start,end):
    matches=[p for p in state.get('statement_policies',[]) if p['start']==start and p['end']==end]
    if not matches:raise ValueError('Save a reviewed presentation policy for this exact reporting period first.')
    p=matches[-1]
    if set(p['mappings'])!={a['code'] for a in state['accounts']}:raise ValueError('Ledger masters changed; review the statement mappings again.')
    for a in state['accounts']:
        if p['mappings'][a['code']]['section'] not in SECTIONS[a['kind']]:raise ValueError('Ledger kind changed; re-review statement mapping.')
    return p


def _pack(state,start,end,branch,mode,columns,money,rows,controls,note):
    p=f.snapshot(state,'Trial balance',start,end,branch);p.update(mode=mode,columns=columns,money_columns=money,rows=rows,controls=controls,note=note);return p


def report_pack(state,start,end,branch='ALL'):
    p=policy(state,start,end);core.verify_audit(state);names=foundation.branches(state);priorstart,priorend=f.previous_year(start),f.previous_year(end)
    closing=core.balances(state,end,branch);prior=core.balances(state,priorend,branch);movement=core.balances(state,end,branch,start);oldmovement=core.balances(state,priorend,branch,priorstart)
    pending=[t for t in DISCLOSURES if p['disclosures'].get(t,{}).get('status','Pending')=='Pending' and (t!=DISCLOSURES[-1] or p['framework']==FRAMEWORKS[1])]
    note='Reviewed presentation working pack | '+p['framework']+' | policy '+p['id']+' | '+p['basis']+'. Notes require entity evidence; statutory certification is not inferred. Pending disclosures: '+(', '.join(pending) or 'none')
    packs=[]
    def add(mode,cols,money,rows,controls={}):
        x=_pack(state,start,end,branch,mode,cols,money,rows,controls,note);x['comparison']=dict(start=priorstart,end=priorend);x['policy_id']=p['id'];packs.append(x);return x
    for pl in (False,True):
        rows=[];totals={};ledgerrows=[]
        for a in state['accounts']:
            if (a['kind'] in ('Revenue','Expense'))!=pl:continue
            m=p['mappings'][a['code']];sign=-1 if a['kind'] in ('Liability','Equity','Revenue') else 1
            now=(movement if pl else closing)[a['code']]*sign;old=(oldmovement if pl else prior)[a['code']]*sign
            totals.setdefault(m['section'],[0,0]);totals[m['section']][0]+=now;totals[m['section']][1]+=old
            ledgerrows.append([m['section'],m['note'],a['code']+' '+a['name'],now,old,now-old])
        for section,values in totals.items():rows.append([section,'','Section total',*values,values[0]-values[1]]);rows.extend(x for x in ledgerrows if x[0]==section)
        if pl:
            revenue=[-sum(b[a['code']] for a in state['accounts'] if a['kind']=='Revenue') for b in (movement,oldmovement)]
            expenses=[sum(b[a['code']] for a in state['accounts'] if a['kind']=='Expense') for b in (movement,oldmovement)]
            taxes=[sum(b[a['code']] for a in state['accounts'] if p['mappings'][a['code']]['section'] in ('Current tax expense','Deferred tax expense')) for b in (movement,oldmovement)]
            oci=[sum(b[a['code']] for a in state['accounts'] if p['mappings'][a['code']]['section']=='OCI expense') for b in (movement,oldmovement)]
            for title,vals in [('Profit before tax',[revenue[i]-expenses[i]+taxes[i]+oci[i] for i in (0,1)]),('Profit after tax',[revenue[i]-expenses[i]+oci[i] for i in (0,1)]),('Total comprehensive result',[revenue[i]-expenses[i] for i in (0,1)])]:rows.append(['Result','',title,*vals,vals[0]-vals[1]])
            controls={}
        else:
            earnings=[-sum(b[a['code']] for a in state['accounts'] if a['kind'] in ('Revenue','Expense')) for b in (closing,prior)]
            rows.append(['Equity: other equity','Result','Unclosed accumulated result',*earnings,earnings[0]-earnings[1]])
            assets=[sum(b[a['code']] for a in state['accounts'] if a['kind']=='Asset') for b in (closing,prior)];others=[-sum(b[a['code']] for a in state['accounts'] if a['kind'] in ('Liability','Equity'))+earnings[i] for i,b in enumerate((closing,prior))]
            for title,vals in [('Total assets',assets),('Total equity and liabilities',others)]:rows.append(['Total','',title,*vals,vals[0]-vals[1]])
            controls={'Current balance sheet difference':assets[0]-others[0],'Comparative balance sheet difference':assets[1]-others[1]}
        add('Presented profit and loss' if pl else 'Presented balance sheet',['Section','Note','Ledger / total','Current INR','Comparative INR','Change INR'],[3,4,5],rows,controls)
    add('Classification and note trace',['Code','Ledger','Section','Note','Review basis'],[],[[a['code'],a['name'],p['mappings'][a['code']]['section'],p['mappings'][a['code']]['note'],p['mappings'][a['code']]['basis']] for a in state['accounts']])
    add('Disclosure review',['Disclosure','Status','Evidence / reviewed explanation'],[],[[t,p['disclosures'].get(t,{}).get('status','Pending'),p['disclosures'].get(t,{}).get('text','Awaiting evidence')] for t in DISCLOSURES])
    units={u:core.balances(state,end,u) for u in names};rows=[];unreconciled=0
    for c in p['clearing_accounts']:
        dr=sum(max(b[c],0) for b in units.values());cr=sum(max(-b[c],0) for b in units.values());net=dr-cr;unreconciled+=abs(net)
        for u in names:rows.append([c,u,units[u][c],0,0,units[u][c]])
        rows.append([c,'Entity proof',net,dr if not net else 0,cr if not net else 0,net])
    add('Inter-branch reconciliation',['Account','Unit / proof','Book balance INR','Eliminate Dr INR','Eliminate Cr INR','Residual INR'],[2,3,4,5],rows,{'Unreconciled inter-branch clearing':unreconciled})
    packs[-1].update(branch='ALL',scope='All operating units')
    matrix=f.snapshot(state,'Branch matrix',start,end);matrix['note']=note+' Branch columns retain gross clearing. Only equal opposite balances eliminate at entity presentation; residuals remain visible.';packs.append(matrix)
    # Equity movements include closed earnings exactly once, with source ledger trace.
    from datetime import timedelta
    openedbooks=core.balances(state,(date.fromisoformat(start)-timedelta(days=1)).isoformat(),branch)
    rows=[]
    for a in state['accounts']:
        if a['kind']=='Equity':
            opened=openedbooks[a['code']];rows.append([a['code'],a['name'],-opened,-closing[a['code']]+opened,-closing[a['code']]])
    openearn=-sum(openedbooks[a['code']] for a in state['accounts'] if a['kind'] in ('Revenue','Expense'));closeearn=-sum(closing[a['code']] for a in state['accounts'] if a['kind'] in ('Revenue','Expense'));rows.append(['Result','Unclosed accumulated result',openearn,closeearn-openearn,closeearn])
    add('Changes in equity working',['Code','Ledger / result','Opening INR','Period movement INR','Closing INR'],[2,3,4],rows)
    ratio_rows=[]
    def aggregate(b,prefix,sign=1):return sign*sum(b[a['code']] for a in state['accounts'] if p['mappings'][a['code']]['section'].startswith(prefix))
    for title,prefix1,prefix2,sign1,sign2 in [('Current ratio','Current assets:','Current liabilities:',1,-1),('Debt to equity','Non-current liabilities: borrowings','Equity:',-1,-1)]:
        values=[];trace=[]
        for b in (closing,prior):
            numerator=aggregate(b,prefix1,sign1);denominator=aggregate(b,prefix2,sign2)
            if title=='Debt to equity':
                numerator+=aggregate(b,'Current liabilities: borrowings',-1);denominator-=sum(b[a['code']] for a in state['accounts'] if a['kind'] in ('Revenue','Expense'))
            values.append(str((Decimal(numerator)/Decimal(denominator)).quantize(Decimal('.0001'))) if denominator>0 else 'Review: zero/negative denominator');trace.append(f'{numerator} paise / {denominator} paise')
        ratio_rows.append([title,*values,'; comparative: '.join(trace)])
    add('Ratios working',['Ratio','Current times','Comparative times','Ledger calculation trace'],[],ratio_rows)
    packs[-1]['note']+=' Ratios follow reviewed section mapping; other required ratios and variation explanations remain in disclosure evidence. Debt means mapped current/noncurrent borrowings; equity includes unclosed results.'
    for x in packs:x['status']='Review required' if pending or unreconciled or any(x['controls'].values()) else 'Prepared for accountant review';x['prepared']=packs[0]['prepared']
    return packs


def fingerprint(state):return hashlib.sha256(json.dumps([state['vouchers'],state.get('statement_policies',[]),state['accounts']],sort_keys=True).encode()).hexdigest()


def tax_estimate(state,values):
    start,end=values['start'],values['end'];p=policy(state,start,end);branch=values['branch']
    if branch not in foundation.branches(state,True):raise ValueError('Select one active unit for an actual provision journal.')
    m=core.balances(state,end,branch,start)
    if not values.get('confirmed') or not str(values.get('basis','')).strip():raise ValueError('Review effective tax assumptions, applicability, deductions and losses; no statutory rate is assumed.')
    def amount(key):
        n=core.money(values.get(key,'0'))
        if n<0:raise ValueError('Tax adjustments must be nonnegative; select the correct additions/deductions field.')
        return n
    pbt=-sum(m[a['code']] for a in state['accounts'] if a['kind'] in ('Revenue','Expense'))+sum(m[a['code']] for a in state['accounts'] if p['mappings'][a['code']]['section'] in ('Current tax expense','Deferred tax expense','OCI expense'))
    add,deduct,loss=amount('additions'),amount('deductions'),amount('losses');before=max(0,pbt+add-deduct)
    if loss>before:raise ValueError('Reviewed loss utilisation cannot exceed positive adjusted income.')
    rates=[]
    for key in ('rate','surcharge','cess'):
        x=Decimal(str(values.get(key,'')))
        if not x.is_finite() or not 0<=x<=100:raise ValueError('Enter reviewed finite tax percentages from 0 to 100.')
        rates.append(x)
    rnd=lambda x:int(x.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    taxable=before-loss;base=rnd(Decimal(taxable)*rates[0]/100);surcharge=rnd(Decimal(base)*rates[1]/100);cess=rnd(Decimal(base+surcharge)*rates[2]/100);target=base+surcharge+cess
    expense=values['expense_account'];payable=values['payable_account'];accounts={a['code']:a for a in state['accounts']}
    if expense not in accounts or p['mappings'][expense]['section']!='Current tax expense' or payable not in accounts or accounts[payable]['kind']!='Liability' or p['mappings'][payable]['section']!='Current liabilities: current tax':raise ValueError('Select reviewed current-tax expense and current-tax liability ledgers.')
    booked=sum(m[a['code']] for a in state['accounts'] if p['mappings'][a['code']]['section']=='Current tax expense');delta=target-booked
    lines=[]
    if delta:
        lines=[dict(account=expense,branch=branch,debit=max(delta,0),credit=max(-delta,0)),dict(account=payable,branch=branch,debit=max(-delta,0),credit=max(delta,0))]
    return dict(pbt=pbt,additions=add,deductions=deduct,losses=loss,taxable=taxable,base=base,surcharge=surcharge,cess=cess,target=target,booked=booked,delta=delta,lines=lines,fingerprint=fingerprint(state),values=copy.deepcopy(values),policy=p['id'])


def post_tax(state,preview):
    if preview['fingerprint']!=fingerprint(state):raise ValueError('Books or mappings changed; calculate and review tax again.')
    actual=tax_estimate(state,preview['values'])
    if actual!=preview:raise ValueError('Tax preview changed; re-review.')
    if not actual['lines']:raise ValueError('Current tax provision already equals the reviewed target; nothing to post.')
    v=core.post(state,actual['values']['end'],'Reviewed current-tax provision: '+actual['values']['basis'],actual['lines'],metadata={'type':'Adjustment','source':json.dumps({'current_tax_provision':{k:v for k,v in actual.items() if k!='fingerprint'}},sort_keys=True)})
    return v


def tax_pack(state,preview):
    v=preview['values'];rows=[[key,preview[key]] for key in ('pbt','additions','deductions','losses','taxable','base','surcharge','cess','target','booked','delta')]
    return _pack(state,v['start'],v['end'],v['branch'],'Current tax provision working',['Calculation','INR'],[1],rows,{},'Reviewed assumptions: '+v['basis']+' | rate '+str(v['rate'])+' surcharge '+str(v['surcharge'])+' cess '+str(v['cess'])+' | Current tax only; deferred tax, MAT/AMT and legal eligibility require separate evidenced review. Existing booked expense is deducted to avoid duplicate provisioning.')

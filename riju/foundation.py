"""Bookkeeping masters, periods and reviewed drafts. No network or AI calls."""
import copy
import re
import uuid
from datetime import date

SCHEMA = 10
KINDS = {'Asset':(1000,1999),'Liability':(2000,2999),'Equity':(3000,3999),
         'Revenue':(4000,4499),'Expense':(4500,4999)}
GROUPS = {
 'Asset':('Cash and bank','Payment clearing','Patient control','Inventory','PPE','CWIP','Accumulated depreciation','GST input','Other assets'),
 'Liability':('Trade payables','Patient advances','TDS payable','GST output','Retention','Borrowings','Other liabilities'),
 'Equity':('Capital','Retained earnings','Other equity'),
 'Revenue':('Healthcare revenue','Pharmacy revenue','Resort revenue','Other revenue'),
 'Expense':('Medical costs','Professional fees','Employee benefits','Administration','Finance costs','Depreciation','Income tax','Other expenses')}
CASH_FLOW = ('Operating','Investing','Financing','Cash equivalent','Review')
VOUCHER_TYPES = ('Journal','Receipt','Payment','Transfer','Adjustment','Advance','Refund')

def branches(state, active_only=False):
    records=state.get('branches')
    if records is None:
        from .core import BRANCHES
        return dict(BRANCHES)
    return {k:v['name'] for k,v in records.items() if not active_only or v.get('active',True)}

def default_group(account):
    c=account['code'];kind=account['kind']
    lookup={'1000':'Cash and bank','1010':'Cash and bank','1020':'CWIP','1030':'PPE','1040':'PPE',
      '1050':'Accumulated depreciation','1100':'Inventory','1110':'Payment clearing','1120':'Payment clearing',
      '1130':'Payment clearing','1140':'Payment clearing','1200':'GST input','1210':'GST input','1220':'GST input',
      '2000':'Trade payables','2010':'Retention','2300':'Patient advances','2400':'Borrowings',
      '3000':'Capital','3100':'Retained earnings','4030':'Pharmacy revenue','4040':'Resort revenue',
      '4500':'Medical costs','4510':'Professional fees','4520':'Employee benefits','4570':'Depreciation',
      '4580':'Finance costs','4600':'Medical costs','4610':'Income tax'}
    if c in lookup and lookup[c] in GROUPS[kind]:return lookup[c]
    if kind=='Liability' and c.startswith('21'):return 'TDS payable'
    if kind=='Liability' and c.startswith('22'):return 'GST output'
    return {'Asset':'Other assets','Liability':'Other liabilities','Equity':'Other equity',
            'Revenue':'Healthcare revenue','Expense':'Administration'}[kind]

def migrate(state):
    """Idempotent in-memory migration; the vault backs up before persisting it."""
    from .core import add_audit,BRANCHES
    if state.get('schema_revision',1)>SCHEMA:raise ValueError('These books need a newer version of Riju Books.')
    if state.get('schema_revision',1)==SCHEMA and state.get('version')==10:return state
    settings=state['settings']
    settings.setdefault('departments',['Pharmacy','Therapy rooms','Inpatient diet kitchen','Outpatient consultations','Central administration'])
    state.setdefault('branches',{code:{'name':name,'city':'','state':'','state_code':'','gstin':'',
        'active':True,'beds':settings.get('beds',{}).get(code,0),
        'status':'Under construction' if code=='VK' else 'Operational','opening_date':''}
        for code,name in BRANCHES.items()})
    settings.setdefault('registration',dict.fromkeys(('address','city','state','state_code','pan','tan','cin','gstin'),''))
    state.setdefault('account_details',{})
    for a in state['accounts']:
        state['account_details'].setdefault(a['code'],{'active':True,'group':default_group(a),'cash_flow':'Review','description':''})
    # Never silently reuse a client-created account code for Patient A/C.
    if 'patient_control' not in state:
        used={a['code'] for a in state['accounts']}
        code=next((str(n) for n in range(1150,1200) if str(n) not in used),None)
        if not code:raise ValueError('No available patient-control account code.')
        state['accounts'].append({'code':code,'name':'Patient A/C','kind':'Asset'})
        state['account_details'][code]={'active':True,'group':'Patient control','cash_flow':'Operating','description':'Shared patient billing/collections control; no individual patient ledgers.'}
        state['patient_control']=code
    state.setdefault('financial_years',{})
    state.setdefault('drafts',[])
    state.setdefault('fx_rates',[])
    state.setdefault('foreign_accounts',{})
    state.setdefault('fx_ledgers',{})
    state.setdefault('bank_statements',[])
    state.setdefault('bank_exceptions',{})
    settings.setdefault('bank_reconciliation',{'tolerance':1,'use_value_date':False,'working_days':[],'holiday_sources':[]})
    state['schema_revision']=SCHEMA
    state.setdefault('tax_config',{'rules':[],'parties':[]})
    for key in ('gst_documents','gst_2b_imports','gst_2b_matches'):state.setdefault(key,[])
    state.setdefault('gst_rcm_records',[])
    state.setdefault('gst_rcm_ledgers',{})
    for key in ('tds_records','tds_allocations','tds_challan_details'):state.setdefault(key,[])
    state.setdefault('tds_ledgers',{})
    state['version']=10
    state['accounts'].sort(key=lambda a:a['code'])
    add_audit(state,'SCHEMA_UPGRADED',{'to':SCHEMA})
    return state

def optional_registration(values):
    """Unknown details remain blank. Validate format only, not legal registration."""
    out={k:str(values.get(k,'')).strip() for k in ('address','city','state','state_code','pan','tan','cin','gstin')}
    patterns={'pan':r'[A-Z]{5}[0-9]{4}[A-Z]','tan':r'[A-Z]{4}[0-9]{5}[A-Z]',
              'gstin':r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]',
              'cin':r'[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}'}
    for k,p in patterns.items():
        out[k]=out[k].upper()
        if out[k] and not re.fullmatch(p,out[k]):raise ValueError(f'{k.upper()}: invalid format; leave blank if not available.')
    if out['state_code'] and (not re.fullmatch(r'\d{2}',out['state_code']) or not 1<=int(out['state_code'])<=38):
        raise ValueError('State code must be a two-digit Indian state/UT code, or blank.')
    if out['gstin']:
        if not 1<=int(out['gstin'][:2])<=38:raise ValueError('GSTIN state code is invalid.')
        if out['state_code'] and out['gstin'][:2]!=out['state_code']:raise ValueError('GSTIN and state code differ.')
        if out['pan'] and out['gstin'][2:12]!=out['pan']:raise ValueError('GSTIN and PAN differ.')
    return out

def save_entity(state,name,values):
    from .core import add_audit
    if not name.strip():raise ValueError('Legal entity name is required; registration numbers may be blank.')
    registration=optional_registration(values)
    old={'name':state['settings']['entity'],'registration':copy.deepcopy(state['settings']['registration'])}
    state['settings'].update(entity=name.strip(),registration=registration)
    add_audit(state,'ENTITY_UPDATED',{'old':old,'new':{'name':name.strip(),'registration':registration}})

def save_departments(state,labels):
    from .core import add_audit
    labels=[str(x).strip() for x in labels if str(x).strip()]
    if len(set(x.casefold() for x in labels))!=len(labels):raise ValueError('Department names must be unique.')
    used={l.get('cost_center') for v in state['vouchers'] for l in v['lines'] if l.get('cost_center')}
    if not used.issubset(labels):raise ValueError('Departments used in posted history cannot be removed or renamed.')
    old=state['settings']['departments'];state['settings']['departments']=labels
    add_audit(state,'DEPARTMENTS_UPDATED',{'old':old,'new':labels})


def save_branch(state,code,values):
    from .core import add_audit
    code=code.strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_-]{1,9}',code) or code=='ALL':raise ValueError('Use a unique branch code of 2–10 letters/digits, starting with a letter.')
    name=str(values.get('name','')).strip()
    if not name or name=='All operating units':raise ValueError('Enter a branch name.')
    if any(k!=code and v['name'].casefold()==name.casefold() for k,v in state['branches'].items()):raise ValueError('Branch names must be unique.')
    registration=optional_registration(values)
    try:beds=int(values.get('beds',0))
    except (TypeError,ValueError):raise ValueError('Beds must be a non-negative whole number.') from None
    if beds<0:raise ValueError('Beds cannot be negative.')
    opening=values.get('opening_date','').strip()
    if opening:date.fromisoformat(opening)
    status=values.get('status','Operational')
    if status not in ('Operational','Under construction','Closed'):raise ValueError('Choose a valid operating status.')
    active=bool(values.get('active',True))
    if not active and not any(k!=code and v.get('active',True) for k,v in state['branches'].items()):raise ValueError('Keep at least one branch active.')
    item={'name':name,'city':registration['city'],'state':registration['state'],'state_code':registration['state_code'],
          'gstin':registration['gstin'],'beds':beds,'opening_date':opening,'active':active,'status':status}
    old=copy.deepcopy(state['branches'].get(code))
    state['branches'][code]=item
    add_audit(state,'BRANCH_UPDATED',{'code':code,'old':old,'new':item})

def save_account(state,code,name,kind,group,cash_flow='Review',active=True,description=''):
    from .core import add_audit
    if kind not in KINDS or not re.fullmatch(r'\d{4}',code):raise ValueError('Select a classification and four-digit account code.')
    lo,hi=KINDS[kind]
    if not lo<=int(code)<=hi:raise ValueError(f'{kind} codes must be between {lo} and {hi}.')
    if code in state.get('foreign_accounts',{}) and group!='Cash and bank':raise ValueError('A designated foreign-currency bank/cash account must retain its Cash and bank group.')
    if not name.strip() or group not in GROUPS[kind] or cash_flow not in CASH_FLOW:raise ValueError('Enter ledger name and valid report/cash-flow groups.')
    existing=next((a for a in state['accounts'] if a['code']==code),None)
    if existing and existing['kind']!=kind:raise ValueError('Existing ledger classification cannot change. Create a new ledger instead.')
    protected={'1000','1010','1020','1050','1100','1110','1120','1130','2300','3100',state['patient_control'],*state['revenue_mode_accounts'].values(),*state.get('foreign_accounts',{}),*state.get('gst_rcm_ledgers',{}).values(),*state.get('tds_ledgers',{}).values()}
    if not active and code in protected:raise ValueError('This control ledger is required. It may be renamed but not deactivated.')
    old={'account':copy.deepcopy(existing),'details':copy.deepcopy(state['account_details'].get(code))}
    item={'code':code,'name':name.strip(),'kind':kind}
    if existing:state['accounts'].remove(existing)
    state['accounts'].append(item);state['accounts'].sort(key=lambda a:a['code'])
    details={'active':bool(active),'group':group,'cash_flow':cash_flow,'description':description.strip()}
    state['account_details'][code]=details
    add_audit(state,'LEDGER_UPDATED',{'old':old,'new':{'account':item,'details':details}})

def delete_account(state,code):
    """Only unused, inactive, non-control ledgers can be deleted."""
    from .core import add_audit
    details=state['account_details'].get(code,{})
    if details.get('active',True):raise ValueError('Deactivate the ledger before deleting it.')
    if any(l['account']==code for v in state['vouchers'] for l in v['lines']):raise ValueError('A ledger used in posted history cannot be deleted.')
    if any(l['account']==code for d in state['drafts'] for l in d['lines']):raise ValueError('A draft references this ledger.')
    if any(code in (r.get('debit_account'),r.get('credit_account')) for q in state['queue'] for r in q['rows']):raise ValueError('An import references this ledger.')
    if any(code in r.get('ledger_codes',[]) for r in state.get('tax_config',{}).get('rules',[])):raise ValueError('A historical tax rule references this ledger; it cannot be deleted.')
    item=next(a for a in state['accounts'] if a['code']==code)
    state['accounts'].remove(item);state['account_details'].pop(code,None)
    add_audit(state,'LEDGER_DELETED',{'account':item,'details':details})

def register_year(state,year):
    from .core import add_audit
    year=int(year)
    if not 1900<=year<=9998:raise ValueError('Financial year must start between 1900 and 9998.')
    if str(year) not in state['financial_years']:
        state['financial_years'][str(year)]={'closed':False}
        add_audit(state,'FINANCIAL_YEAR_ADDED',{'year':year})
    return year

def lock_period(state,through):
    from .core import add_audit
    if through:date.fromisoformat(through)
    if through<state['locked_through']:raise ValueError('A period lock cannot be moved backwards.')
    old=state['locked_through'];state['locked_through']=through
    add_audit(state,'PERIOD_LOCKED',{'old':old,'new':through})

def opening_lines(state,day,lines):
    """One initial balance voucher per branch; carry-forwards are automatic."""
    kinds={a['code']:a['kind'] for a in state['accounts']}
    affected={l['branch'] for l in lines}
    if day[5:]!='04-01':raise ValueError('Opening balances must be dated 1 April.')
    if any(kinds.get(l['account']) in ('Revenue','Expense') for l in lines):raise ValueError('Opening balances use assets, liabilities and equity only; put prior-year results in retained earnings.')
    for v in state['vouchers']:
        if not affected.intersection(l['branch'] for l in v['lines']):continue
        if v.get('opening'):raise ValueError('This branch already has initial opening balances. Use an adjustment, not another opening.')
        if v['date']<day:raise ValueError('Earlier transactions already carry forward. Do not add a second opening balance.')

def import_openings(state,text):
    """CSV rows are grouped into balanced branch vouchers and approved atomically."""
    from . import core
    import hashlib
    digest=hashlib.sha256(text.encode()).hexdigest()
    rows=core.read_csv(text,'journals');candidate=copy.deepcopy(state);groups={};counts={}
    for row in rows:
        key=(row['date'],row['branch']);counts[key]=counts.get(key,0)+1;groups.setdefault(key,[]).extend([
          dict(account=row['debit_account'],branch=row['branch'],debit=row['amount'],credit=0),
          dict(account=row['credit_account'],branch=row['branch'],debit=0,credit=row['amount'])])
    vouchers=[]
    for (day,branch),lines in sorted(groups.items()):
        vouchers.append(core.post(candidate,day,'Imported opening balances',lines,opening=True,source={'kind':'opening_csv','document_id':digest,'record_id':day+'-'+branch,'row_count':counts[(day,branch)]}))
    state.clear();state.update(candidate)
    return vouchers

def close_year(state,year):
    """Close income/expenses into retained earnings per branch, then lock."""
    from . import core
    year=int(year)
    if not 1900<=year<=9998:raise ValueError('Invalid financial year.')
    if state['financial_years'].get(str(year),{}).get('closed'):raise ValueError('This financial year is already closed.')
    start,end=core.fy_bounds(year)
    if date.fromisoformat(end)>=date.today():raise ValueError('Close a financial year only after its end date.')
    if state['locked_through'] and end<=state['locked_through']:raise ValueError('This year is already locked.')
    if any(d['date']<=end for d in state['drafts']):raise ValueError('Resolve saved drafts through year-end before closing.')
    if any(q['status']=='PENDING_REVIEW' and any(r['date']<=end for r in q['rows']) for q in state['queue']):raise ValueError('Resolve pending imports through year-end before closing.')
    candidate=copy.deepcopy(state);register_year(candidate,year)
    for branch in branches(candidate):
        b=core.balances(candidate,end,branch);lines=[]
        for a in candidate['accounts']:
            amount=b[a['code']]
            if a['kind'] in ('Revenue','Expense') and amount:
                lines.append(dict(account=a['code'],branch=branch,debit=max(-amount,0),credit=max(amount,0)))
        delta=sum(l['debit']-l['credit'] for l in lines)
        if delta:lines.append(dict(account='3100',branch=branch,debit=max(-delta,0),credit=max(delta,0)))
        if lines:core.post(candidate,end,f'Year-end close FY {year}–{year+1}',lines,closing=True)
    candidate['financial_years'][str(year)]['closed']=True
    lock_period(candidate,end)
    core.add_audit(candidate,'YEAR_CLOSED',{'year':year})
    state.clear();state.update(candidate)

def save_draft(state,day,narration,lines,metadata=None,draft_id=None,opening=False):
    from . import core
    date.fromisoformat(day)
    if not narration.strip():raise ValueError('Enter a narration before saving the draft.')
    # Drafts may be unbalanced, but must reference actual ledgers/branches.
    codes={a['code'] for a in state['accounts']}
    for l in lines:
        if l['account'] not in codes or l['branch'] not in branches(state):raise ValueError('Draft references an unknown account or branch.')
        if any(type(l[k])!=int or l[k]<0 for k in ('debit','credit')):raise ValueError('Draft amounts must be non-negative integer paise.')
    old=next((d for d in state['drafts'] if d['id']==draft_id),None)
    if draft_id and old is None:raise ValueError('Saved draft no longer exists.')
    d={'id':draft_id or str(uuid.uuid4()),'date':day,'narration':narration.strip(),'lines':copy.deepcopy(lines),
       'metadata':clean_metadata(metadata),'opening':bool(opening)}
    if old:state['drafts'].remove(old)
    state['drafts'].append(d);core.add_audit(state,'DRAFT_SAVED',{'id':d['id'],'old':old,'new':d})
    return d

def clean_metadata(metadata):
    metadata=metadata or {}
    allowed={'type','reference','payee','bank_account','source'}
    if set(metadata)-allowed:raise ValueError('Unknown voucher metadata field.')
    out={k:str(v).strip() for k,v in metadata.items()}
    if out.get('type','Journal') not in VOUCHER_TYPES:raise ValueError('Unknown voucher type.')
    return out

def discard_draft(state,draft_id):
    from .core import add_audit
    item=next((d for d in state['drafts'] if d['id']==draft_id),None)
    if not item:raise ValueError('Saved draft not found.')
    state['drafts'].remove(item);add_audit(state,'DRAFT_DISCARDED',{'old':item})

def post_draft(state,draft_id):
    from .core import post
    candidate=copy.deepcopy(state)
    d=next((d for d in candidate['drafts'] if d['id']==draft_id),None)
    if d is None:raise ValueError('Saved draft not found or already posted.')
    voucher=post(candidate,d['date'],d['narration'],d['lines'],opening=d['opening'],metadata=d['metadata'])
    from .core import add_audit
    add_audit(candidate,'DRAFT_POSTED',{'draft_id':draft_id,'voucher_id':voucher['id']})
    discard_draft(candidate,draft_id)
    state.clear();state.update(candidate)
    return voucher

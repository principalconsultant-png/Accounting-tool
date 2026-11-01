from __future__ import annotations
import calendar
import copy
import csv
import hashlib
import io
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

BRANCHES = {'JP': 'JP Nagar', 'KM': 'Kammanahalli', 'VK': 'Vaikom'}
# Classification is explicit: account numbers alone do not control reports.
ACCOUNTS = [
 ('1000','Cash','Asset'), ('1010','Bank','Asset'),
 ('1020','Vaikom resort CWIP','Asset'), ('1030','Medical equipment','Asset'),
 ('1040','Furniture and fixtures','Asset'), ('1050','Accumulated depreciation','Asset'),
 ('1100','Medicine inventory','Asset'), ('1110','UPI settlement clearing','Asset'),
 ('1120','Card settlement clearing','Asset'), ('1130','Inter-branch clearing','Asset'),
 ('1200','Input CGST','Asset'), ('1210','Input SGST','Asset'), ('1220','Input IGST','Asset'),
 ('2000','Trade payables','Liability'), ('2010','Contractor retention','Liability'),
 ('2100','TDS payable — 194J','Liability'), ('2110','TDS payable — 194C','Liability'),
 ('2120','TDS payable — 194I','Liability'), ('2200','Output CGST','Liability'),
 ('2210','Output SGST','Liability'), ('2220','Output IGST','Liability'),
 ('2300','Patient/package advances','Liability'), ('2400','Bank loans','Liability'),
 ('3000','Capital','Equity'), ('3100','Retained earnings','Equity'),
 ('4000','OPD consultation revenue','Revenue'), ('4010','Therapy revenue','Revenue'),
 ('4020','IPD room revenue','Revenue'), ('4030','Pharmacy sales','Revenue'),
 ('4040','Resort service revenue','Revenue'), ('4500','Medical consumables','Expense'),
 ('4510','Doctor professional fees','Expense'), ('4520','Employee benefits','Expense'),
 ('4530','Rent','Expense'), ('4540','Utilities','Expense'), ('4550','Repairs and maintenance','Expense'),
 ('4560','Bank and payment processing charges','Expense'), ('4570','Depreciation','Expense'),
 ('4580','Finance costs','Expense'), ('4590','Administration','Expense'),
 ('4600','Medicine cost of sales','Expense'), ('4610','Income tax expense','Expense')]

def money(value):
    try:
        n = Decimal(str(value).replace(',','').replace('₹','').strip())
        if not n.is_finite(): raise ValueError('Amount must be finite.')
        return int((n * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        raise ValueError('Enter a valid rupee amount.') from None

def rupees(paise):
    return f'₹{paise/100:,.2f}'

def financial_year(day):
    d = date.fromisoformat(day)
    return d.year if d.month >= 4 else d.year-1

def fy_bounds(year):
    return f'{year}-04-01', f'{year+1}-03-31'

def empty_state():
    state = {'version':1, 'accounts':[dict(code=c,name=n,kind=k) for c,n,k in ACCOUNTS],
            'vouchers':[], 'audit':[], 'locked_through':'', 'holidays':[], 'bank_lines':[],
            'matches':[], 'queue':[], 'assets':[], 'budgets':{},
            'settings':{'entity':'ASMAKAM — legal name pending', 'backup_dir':'',
                        'beds':{'JP':8,'KM':8,'VK':0},
                        'tax_rules':[{'section':'194J','rate':'10','effective':'2026-04-01'},
                                     {'section':'194C','rate':'2','effective':'2026-04-01'},
                                     {'section':'194I','rate':'10','effective':'2026-04-01'}],
                        'gst_rates':'0,5,12,18,28', 'tax_reviewed':False}}
    from .revenue import ensure_accounts
    from .foundation import migrate
    return migrate(ensure_accounts(state))

def add_audit(state, action, payload):
    previous = state['audit'][-1]['hash'] if state['audit'] else '0'*64
    record = {'sequence':len(state['audit'])+1, 'action':action, 'payload':copy.deepcopy(payload), 'previous':previous}
    from datetime import datetime, timezone
    import getpass
    try:record['actor']=getpass.getuser()
    except (OSError,KeyError):record['actor']='Local user (unavailable)'
    record['timestamp'] = datetime.now(timezone.utc).isoformat()
    record['hash'] = hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    state['audit'].append(record)

def verify_audit(state):
    prev = '0'*64
    for sequence,item in enumerate(state['audit'],1):
        if type(item.get('sequence'))!=int or item['sequence']!=sequence:raise ValueError('Change history sequence check failed. Restore a trusted backup.')
        raw = {k:v for k,v in item.items() if k!='hash'}
        if item['previous'] != prev or hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=item['hash']:
            raise ValueError('Change history integrity check failed. Restore a trusted backup.')
        prev=item['hash']
    posted=[item['payload'] for item in state['audit'] if item['action']=='POST']
    if posted != state['vouchers']:
        raise ValueError('Voucher records differ from the recorded change history.')

def post(state, day, narration, lines, opening=False, reverses=None, metadata=None, closing=False, fx=None, source=None):
    from .foundation import branches,opening_lines,clean_metadata
    date.fromisoformat(day)
    if date.fromisoformat(day).isoformat()!=day:raise ValueError('Use YYYY-MM-DD for the transaction date.')
    metadata=clean_metadata(metadata)
    if state.get('financial_years',{}).get(str(financial_year(day)),{}).get('closed'):
        raise ValueError('This financial year is closed.')
    if state['locked_through'] and day <= state['locked_through']:
        raise ValueError('This date is in a locked period.')
    if not narration.strip(): raise ValueError('A narration is required.')
    if len(lines)<2: raise ValueError('At least two lines are required.')
    codes={a['code'] for a in state['accounts']}
    kinds={a['code']:a['kind'] for a in state['accounts']}
    for line in lines:
        if line['account'] not in codes: raise ValueError('Unknown ledger account.')
        if line['branch'] not in branches(state): raise ValueError('Every line requires a valid operating unit.')
        if not reverses and not closing:
            if line['branch'] not in branches(state,active_only=True):raise ValueError('This branch is inactive. Reactivate it before posting.')
            if not state.get('account_details',{}).get(line['account'],{}).get('active',True):raise ValueError('This ledger is inactive. Reactivate it before posting.')
        department=line.get('cost_center')
        if department and (department not in state['settings'].get('departments',[]) or kinds[line['account']] not in ('Revenue','Expense')):
            raise ValueError('Department tags apply only to revenue/expense lines and must match the configured list.')
        dr,cr=line['debit'],line['credit']
        if type(dr)!=int or type(cr)!=int or dr<0 or cr<0 or (dr>0)==(cr>0):
            raise ValueError('Each line needs one positive debit or credit, in paise.')
    if sum(l['debit']-l['credit'] for l in lines)!=0: raise ValueError('Debits and credits do not balance.')
    for branch in branches(state):
        if sum(l['debit']-l['credit'] for l in lines if l['branch']==branch):
            raise ValueError('Each branch must balance. Use inter-branch clearing accounts.')
    if opening:opening_lines(state,day,lines)
    if not opening:
        affected={l['branch'] for l in lines}
        if any(v.get('opening') and day<v['date'] and affected.intersection(l['branch'] for l in v['lines']) for v in state['vouchers']):
            raise ValueError('Transaction predates this branch\'s initial opening balances. Use the correct starting year.')
    if opening and (reverses or closing):raise ValueError('An opening cannot also be a reversal or year-end close.')
    if closing and day[5:]!='03-31':raise ValueError('Year-end closing entries must be dated 31 March.')
    if metadata.get('bank_account'):
        bank=metadata['bank_account']
        if state.get('account_details',{}).get(bank,{}).get('group')!='Cash and bank':raise ValueError('Select a cash/bank ledger for the bank reference.')
        if not any(l['account']==bank for l in lines):raise ValueError('Selected cash/bank ledger is absent from the journal lines.')
    from .reconciliation import validate_post as validate_bank_post
    validate_bank_post(state,day,lines,reverses)
    if fx is not None:
        from .fx import validate_post
        if not isinstance(fx,dict):raise ValueError('Invalid FX record.')
        validate_post(state,fx,day,narration.strip(),lines,metadata,reverses)
    elif any(l['account'] in state.get('foreign_accounts',{}) for l in lines):
        raise ValueError('Use FX receipts/conversion for a designated foreign-currency account; foreign units must be recorded.')
    if source is not None:
        from .activity import validate_source
        source=validate_source(source)
        if any(v.get('source',{}).get('kind')==source['kind'] and v['source'].get('document_id')==source['document_id'] and v['source'].get('record_id')==source['record_id'] for v in state['vouchers']):raise ValueError('This source record is already posted.')
    if reverses:
        from .gst import validate_reversal as validate_gst_reversal
        validate_gst_reversal(state,reverses,day)
        from .gst_extensions import check_lines
        check_lines(state,reversal=(reverses,day))
        from .rcm import validate_reversal as validate_rcm_reversal
        validate_rcm_reversal(state,reverses,day)
        from .gst_payments import check as check_gst_payments
        check_gst_payments(state,reversal=(reverses,day))
        from .tds import validate_reversal as validate_tds_reversal
        validate_tds_reversal(state,reverses,day)
        from .fixed_assets import validate_reversal as validate_asset_reversal
        validate_asset_reversal(state,reverses,day)
        from .tax_depreciation import validate_reversal as validate_tax_asset_reversal
        validate_tax_asset_reversal(state,reverses,day)
        from .service_revenue import validate_reversal as validate_revenue_reversal
        validate_revenue_reversal(state,reverses,day)
        from .cwip import validate_reversal as validate_cwip_reversal
        validate_cwip_reversal(state,reverses,day)
        original=next((v for v in state['vouchers'] if v['id']==reverses),None)
        if original is None:raise ValueError('Original voucher not found.')
        if original.get('fx') and fx is None:raise ValueError('An FX reversal must preserve its original currency link.')
        if original.get('closing'):raise ValueError('Year-end closing entries cannot be reversed individually.')
        if day<original['date']:raise ValueError('A reversal cannot precede the original voucher.')
        expected=[dict(l,debit=l['credit'],credit=l['debit']) for l in original['lines']]
        if lines!=expected:raise ValueError('A reversal must exactly reverse the original journal lines.')
        if any(v.get('reverses')==reverses for v in state['vouchers']): raise ValueError('Voucher already reversed.')
    import copy
    v={'id':f'VCH-{financial_year(day)}-{len(state["vouchers"])+1:05}', 'date':day,
       'narration':narration.strip(), 'lines':copy.deepcopy(lines), 'opening':opening,'reverses':reverses}
    if metadata:v['metadata']=metadata
    if closing:v['closing']=True
    if fx is not None:v['fx']=copy.deepcopy(fx)
    if source is not None:v['source']=copy.deepcopy(source)
    add_audit(state,'POST',v)
    state['vouchers'].append(v)
    return v

def reverse(state, voucher_id, day):
    v=next(v for v in state['vouchers'] if v['id']==voucher_id)
    return post(state,day,'Reversal of '+voucher_id+': '+v['narration'],
                [dict(l,debit=l['credit'],credit=l['debit']) for l in v['lines']], reverses=voucher_id,
                fx={'kind':'reversal','original':voucher_id} if v.get('fx') else None)

def display_narration(voucher,state):
    if not voucher.get('fx'):return voucher['narration']
    from .fx import summary
    return voucher['narration']+'\n'+summary(voucher,state)


def balances(state, end, branch='ALL', start=None):
    out={a['code']:0 for a in state['accounts']}
    for v in state['vouchers']:
        if v['date']>end or (start and (v['date']<start or v.get('opening') or v.get('closing'))): continue
        for l in v['lines']:
            if branch=='ALL' or branch==l['branch']: out[l['account']]+=l['debit']-l['credit']
    return out

def parse_transaction(text, branch, day, state):
    """Conservative, explainable templates. Never infer taxes or a missing payment method."""
    lower=text.lower()
    if not text.strip(): raise ValueError('Describe the transaction first.')
    if re.search(r'\b(not|never|cancel|cancelled|reverse|reversed|reversal|unpaid|pending|will|tomorrow|yesterday|lakh|lakhs|crore|crores|thousand)\b',lower):
        raise ValueError('This description contains timing, negation, reversal or amount units needing manual review. Use an explicit date and numeric rupee amount.')
    if any(w in lower for w in ('gst','tds','tax','retention','advance','refund','inclusive','net of','credit purchase')):
        raise ValueError('Tax, advances, refunds and deductions require manual lines in this version. No entry was guessed.')
    amounts=re.findall(r'(?:₹\s*|rs\.?\s*|inr\s*)(\d[\d,]*(?:\.\d{1,2})?)(?![\d.])',lower)
    if len(amounts)!=1: raise ValueError('Specify exactly one gross amount with ₹, Rs or INR. Example: Paid ₹5,000 rent by bank.')
    amount=money(amounts[0])
    if amount<=0: raise ValueError('Amount must be positive.')
    methods=[]
    for word,code in [('cash','1000'),('bank','1010'),('upi','1110'),('card','1120')]:
        if re.search(r'\b'+word+r'\b',lower): methods.append(code)
    if len(set(methods))!=1: raise ValueError('Specify one payment method: cash, bank, UPI or card.')
    payment=methods[0]
    if re.search(r'\b(on credit|credit sale|returned|returns|exchange|exchanged|outstanding)\b',lower):
        raise ValueError('Credit, returns and exchanges require manual review. No cash receipt was assumed.')
    from .revenue import match_modes
    service_modes=match_modes(lower)
    pharmacy=bool(re.search(r'\b(pharmacy|medicines?)\b',lower))
    # A patient's purchase is the hospital's sale. Direction must be resolved
    # from the actor, not just the word "purchased" or "paid".
    customer=r'(?:patient|customer)'
    customer_purchase=bool(service_modes) and any(re.search(pattern,lower) for pattern in (
        rf'\b{customer}\b[^.;!?]*?\b(?:purchased|purchases|bought|buys|paid|pays)\b',
        rf'\b(?:purchased|bought|paid)\b[^.;!?]*?\bby\s+(?:(?:a|the)\s+)?{customer}\b',
        rf'\bpayment\s+from\s+(?:(?:a|the)\s+)?{customer}\b',
        rf'\bsold\b[^.;!?]*?\bto\s+(?:(?:a|the)\s+)?{customer}\b',
    ))
    supplier_context=bool(re.search(r'\b(supplier|vendor|wholesaler|distributor)\b',lower))
    hospital_purchase=bool(re.search(r'\b(?:we|hospital|our pharmacy)\s+(?:paid|purchased|bought)\b',lower))
    received=bool(re.search(r'\b(received|collected|receipt|sales|sale|sold)\b',lower))
    paid=bool(re.search(r'\b(paid|purchased|bought|payment)\b',lower))
    if received and not re.search(r'\b(paid|purchased|bought)\b',lower):
        paid=False
    if pharmacy and re.search(r'\b(?:doctor|physician)\s+(?:fees?|payments?)\b',lower):
        raise ValueError('Medicine sales and doctor fees need separate account lines. Split the amounts before posting.')
    if customer_purchase:
        if supplier_context or hospital_purchase:
            raise ValueError('The description mixes customer receipts and hospital purchases. Enter these separately.')
        received,paid=True,False
    elif pharmacy and supplier_context:
        # Receiving medicine stock from a supplier is not receiving sale proceeds.
        raise ValueError('Medicine purchases from suppliers require manual inventory/purchase account selection.')
    if received==paid: raise ValueError('Specify whether money was paid or received, and whether the buyer is the patient or the hospital.')
    rules=([('4040',r'\bresort\b')] if received else [('4510',r'\b(doctor|physician)\b'),('4530',r'\brent\b'),
            ('4540',r'\b(electricity|utilities|water bill)\b'),('4550',r'\b(repair|repairs)\b'),
            ('4520',r'\b(salary|salaries|wages)\b'),('4560',r'\b(bank charges|processing fee)\b'),
            ('1030',r'\bmedical equipment\b'),('1040',r'\bfurniture\b')])
    choices=[code for code,pattern in rules if re.search(pattern,lower)]
    if received:
        choices += [state['revenue_mode_accounts'][key] for key in service_modes]
    if len(choices)!=1: raise ValueError('Account classification is ambiguous or unsupported. Select the accounts manually.')
    if not received and payment in ('1110','1120'): raise ValueError('UPI/card clearing templates apply to sales receipts only. Select a bank for expenses.')
    if choices[0]=='4040' and branch!='VK': raise ValueError('Resort revenue requires Vaikom. Confirm the operating unit.')
    dates=re.findall(r'\b\d{4}-\d{2}-\d{2}\b',text)
    if len(dates)>1: raise ValueError('Multiple dates found. Select the transaction date manually.')
    if dates:
        date.fromisoformat(dates[0])
        if dates[0]!=day: raise ValueError('The date in your description differs from the selected date.')
    debit,credit=(payment,choices[0]) if received else (choices[0],payment)
    return [dict(account=debit,branch=branch,debit=amount,credit=0),dict(account=credit,branch=branch,debit=0,credit=amount)]

def is_business_day(d, holidays):
    return d.weekday()!=6 and not (d.weekday()==5 and (d.day-1)//7+1 in (2,4)) and d.isoformat() not in holidays

def next_business_day(day,holidays):
    d=date.fromisoformat(day)+timedelta(days=1)
    while not is_business_day(d,holidays): d+=timedelta(days=1)
    return d

def settlement_matches(state, bank, branch, tolerance=1):
    """Suggest contiguous daily clearing batches; approval remains manual."""
    if tolerance not in (0,1): raise ValueError('Tolerance must be 0 or 1 business day.')
    used={x for m in state['matches'] if m.get('status','ACTIVE')=='ACTIVE' for x in m.get('vouchers',[])}
    results=[]
    for code in ('1110','1120'):
        eligible=[]
        for v in sorted(state['vouchers'],key=lambda v:v['date']):
            net=sum(l['debit']-l['credit'] for l in v['lines'] if l['branch']==branch and l['account']==code)
            if net>0 and v['id'] not in used and v['date']<=bank['date']: eligible.append((v,net))
        for i in range(len(eligible)):
            total=0
            for j in range(i,min(i+31,len(eligible))):
                v,amount=eligible[j]; total+=amount
                from .bank_calendar import next_day
                expected=date.fromisoformat(next_day(state,v['date'])['date']); latest=expected
                for _ in range(tolerance): latest=date.fromisoformat(next_day(state,latest.isoformat())['date'])
                if not expected.isoformat()<=bank['date']<=latest.isoformat(): continue
                fee=total-bank['amount']
                # Fee is a proposal, never an automatic journal. Limit noise to 5%.
                if 0<=fee<=total//20:
                    results.append({'account':code,'gross':total,'fee':fee,'vouchers':[x[0]['id'] for x in eligible[i:j+1]]})
    return results

def read_csv(text, kind):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required=({'date','narration','branch','debit_account','credit_account','amount'} if kind=='journals' else {'date','narration','amount','reference'})
    if not required.issubset(set(reader.fieldnames or [])): raise ValueError('CSV headers required: '+', '.join(sorted(required)))
    rows=[]
    for number,row in enumerate(reader,2):
        try:
            date.fromisoformat(row['date']); amount=money(row['amount'])
            if amount<=0: raise ValueError('Amount must be positive.')
            row['amount']=amount
            row['source_row']=number
            rows.append(row)
        except ValueError as e: raise ValueError(f'Row {number}: {e}') from e
    if not rows: raise ValueError('The CSV contains no transactions.')
    return rows

def depreciation(cost, residual, life_months, annual_wdv_rate, months=12):
    if cost<0 or residual<0 or residual>cost or life_months<=0 or not 0<=annual_wdv_rate<=100 or months<0:
        raise ValueError('Check cost, residual value, life and tax rate.')
    book=min(cost-residual,int((Decimal(cost-residual)*months/Decimal(life_months)).quantize(Decimal(1),rounding=ROUND_HALF_UP)))
    tax=int((Decimal(cost)*Decimal(str(annual_wdv_rate))/100).quantize(Decimal(1),rounding=ROUND_HALF_UP))
    return book,tax

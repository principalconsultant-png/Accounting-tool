"""Auditable monthly management metrics; ledger-derived figures and explicit count inputs."""
import copy,csv,io,math,uuid
from collections import defaultdict
from calendar import monthrange
from datetime import date,datetime
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from pathlib import Path
from . import core,foundation,ap,gst,history,bulk_import,report_branding

TITLE='Business Pulse — Monthly Performance'
PALETTE=('#063B64','#78A9BE','#F8D4BD','#E78870')
INK='#17354C';MISSING='#E7EBF0';NEUTRAL='#EDF3F8'
METRICS=(
 ('Revenue & collections','revenue','Revenue earned','money'),
 ('Revenue & collections','cash','Cash collections','money'),
 ('Revenue & collections','upi','UPI collections','money'),
 ('Revenue & collections','card','Card collections','money'),
 ('Patients & value','visits','Patient visits · receipt proxy','count'),
 ('Patients & value','new_patients','New patients','count'),
 ('Patients & value','arpp','ARPP · revenue per visit','ratio'),
 ('People & operating outflows','salary','Salary disbursed','money'),
 ('People & operating outflows','ot','Staff overtime payments','money'),
 ('People & operating outflows','petty','Petty cash expenses','money'),
 ('People & operating outflows','compliance','Compliance costs','money'),
 ('Vendor payments','invoices','Invoices paid · incl. part-paid','count'),
 ('Vendor payments','vendor','Total vendor payments','money'))
INPUT_FIELDS=('month','branch','visits','new_patients','books_reviewed','basis')
INPUT_HEADERS=('Month YYYY-MM','Operating Unit','Patient Visits Override (optional)','New Patients','Books Reviewed','Source / Review Basis')


def policy(s):
    revenue=[a['code'] for a in s['accounts'] if a['kind']=='Revenue']
    return copy.deepcopy(s['settings'].get('business_pulse',dict(revenue_accounts=revenue,salary_accounts=[],ot_accounts=[],compliance_accounts=[],petty_mode='All petty-cash disbursements',reviewed=False,basis='')))


@ap.atomic
def save_policy(s,values):
    p={k:copy.deepcopy(values.get(k,[])) for k in ('revenue_accounts','salary_accounts','ot_accounts','compliance_accounts')};accounts={a['code']:a for a in s['accounts']}
    for field,codes in p.items():
        if not isinstance(codes,list) or len(set(codes))!=len(codes):raise ValueError('Choose unique ledger codes for each metric.')
        for code in codes:
            if code not in accounts:raise ValueError('Unknown metric ledger '+str(code))
            kind=accounts[code]['kind'];group=s['account_details'][code]['group']
            if field=='revenue_accounts' and kind!='Revenue':raise ValueError('Revenue mappings must use revenue ledgers.')
            if field=='compliance_accounts' and kind!='Expense':raise ValueError('Compliance costs must use genuine expense ledgers, not tax remittance/payable accounts.')
            if field in ('salary_accounts','ot_accounts') and not (kind=='Expense' or kind=='Liability' and group=='Other liabilities'):raise ValueError('Salary/overtime paid mappings use their expense or payroll Other liabilities ledgers, never bank/AP/tax controls.')
    if not p['revenue_accounts']:raise ValueError('Select at least one revenue ledger.')
    if set(p['salary_accounts'])&set(p['ot_accounts']):raise ValueError('Salary and overtime accounts must be separate; a shared ledger cannot identify the split reliably.')
    mode=values.get('petty_mode','All petty-cash disbursements')
    if mode not in ('Operating expenses only','All petty-cash disbursements'):raise ValueError('Choose the petty-cash definition.')
    if values.get('reviewed') is not True or not str(values.get('basis','')).strip():raise ValueError('Confirm the metric mappings and enter their review basis.')
    p.update(petty_mode=mode,reviewed=True,basis=values['basis'].strip());s['settings']['business_pulse']=p;core.add_audit(s,'BUSINESS_PULSE_POLICY_SAVED',p);return p


def _count(value):
    if value in (None,''):return None
    try:n=Decimal(str(value).strip())
    except InvalidOperation:raise ValueError('Patient counts must be whole nonnegative numbers; blank means unavailable.') from None
    if not n.is_finite() or n!=n.to_integral_value() or not 0<=n<=1000000000:raise ValueError('Patient counts must be whole nonnegative numbers.')
    return int(n)


def input_values(s,v):
    month=str(v.get('month','')).strip()
    try:
        if date.fromisoformat(month+'-01').strftime('%Y-%m')!=month:raise ValueError()
    except ValueError:raise ValueError('Reporting month must be YYYY-MM.') from None
    branch=str(v.get('branch','')).strip()
    if branch!='ALL' and branch not in foundation.branches(s):raise ValueError('Use ALL for entity counts or a saved operating-unit code.')
    visits=_count(v.get('visits',''));new=_count(v.get('new_patients',''));review=v.get('books_reviewed',False)
    if isinstance(review,str):
        if review.strip().casefold() not in ('yes','no',''):raise ValueError('Books Reviewed must be Yes or No.')
        review=review.strip().casefold()=='yes'
    if type(review)!=bool:raise ValueError('Books Reviewed must be Yes or No.')
    if visits is not None and new is not None and new>visits:raise ValueError('New patients cannot exceed an explicitly supplied actual visit count.')
    basis=str(v.get('basis','')).strip()
    if not basis:raise ValueError('Enter the source/review basis for this month and unit.')
    return dict(month=month,branch=branch,visits=visits,new_patients=new,books_reviewed=review,basis=basis)


def observations(s):
    result={}
    for a in s['audit']:
        if a['action']=='BUSINESS_PULSE_MONTH_SAVED':v=a['payload'];result[v['month'],v['branch']]=copy.deepcopy(v)
    return result


@ap.atomic
def save_month(s,values):
    v=input_values(s,values);core.add_audit(s,'BUSINESS_PULSE_MONTH_SAVED',v);return v


def preview_inputs(s,raw,filename):
    sheet='Monthly Inputs';headers,rows,label=bulk_import._read(raw,filename,sheet)
    if set(headers)!=set(INPUT_HEADERS):raise ValueError('Use the standard Business Pulse monthly-input template headings.')
    result=[];seen=set();old=observations(s)
    for number,row in enumerate(rows,2):
        if not any(v not in (None,'') for v in row):continue
        rawrow={key:row[headers.index(h)] if headers.index(h)<len(row) else '' for key,h in zip(INPUT_FIELDS,INPUT_HEADERS)};record=dict(source_row=number,raw={k:'' if v is None else str(v) for k,v in rawrow.items()},error='',status='NEW')
        try:
            if len(row)>len(headers) and any(v not in (None,'') for v in row[len(headers):]):raise ValueError('Extra cells beyond the template headings.')
            if any(str(v).startswith('=') for v in rawrow.values()):raise ValueError('Use literal monthly counts, not formulas.')
            if isinstance(rawrow['month'],(date,datetime)):rawrow['month']=rawrow['month'].strftime('%Y-%m')
            v=input_values(s,rawrow);key=v['month'],v['branch']
            if key in seen:raise ValueError('Duplicate month/unit in this file; provide one reviewed record.')
            seen.add(key);record.update(values=v,status='UPDATE' if key in old else 'NEW')
        except (ValueError,TypeError) as e:record.update(status='INVALID',error=str(e))
        result.append(record)
    if not result:raise ValueError('No monthly observations found.')
    import hashlib
    return dict(filename=Path(filename).name,digest=hashlib.sha256(raw).hexdigest(),rows=result)


@ap.atomic
def save_inputs(s,plan,indices):
    if not indices or len(set(indices))!=len(indices) or any(type(i)!=int or not 0<=i<len(plan['rows']) for i in indices):raise ValueError('Select reviewed new/update rows.')
    for i in indices:
        r=plan['rows'][i]
        if r['status']=='INVALID':raise ValueError('Correct invalid monthly-input rows before saving.')
        v=input_values(s,r['values']);core.add_audit(s,'BUSINESS_PULSE_MONTH_SAVED',v)
    core.add_audit(s,'BUSINESS_PULSE_INPUTS_IMPORTED',dict(filename=plan['filename'],sha256=plan['digest'],source_rows=[plan['rows'][i]['source_row'] for i in indices]));return len(indices)


def month_keys(year):return [f'{year if m>=4 else year+1}-{m:02d}' for m in (*range(4,13),1,2,3)]


def _paid_component(lines,cash_accounts,mapped):
    out=sum(l['credit']-l['debit'] for l in lines if l['account'] in cash_accounts)
    if out<=0:return 0,False
    positives={}
    for l in lines:
        if l['account'] not in cash_accounts:positives[l['account']]=positives.get(l['account'],0)+l['debit']-l['credit']
    positives={k:v for k,v in positives.items() if v>0};total=sum(positives.values());target=sum(v for k,v in positives.items() if k in mapped)
    if not target:return 0,False
    if target==total:return out,False
    if total==out:return target,False
    return 0,True


def snapshot(s,year,through,branch='ALL',scale='INR'):
    core.verify_audit(s);year=int(year);months=month_keys(year);start=months[0]+'-01';end=f'{year+1}-03-31';through=ap.day(through)
    if not start<=through<=end:raise ValueError('Through date must fall within the selected April–March financial year.')
    if branch!='ALL' and branch not in foundation.branches(s):raise ValueError('Select a saved operating unit.')
    if scale not in ('INR','INR thousands','INR lakh'):raise ValueError('Choose a supported display unit.')
    p=policy(s);obs=observations(s);roots=gst._roots(s);byid={v['id']:v for v in s['vouchers']};cash_accounts={a['code'] for a in s['accounts'] if s['account_details'][a['code']]['group']=='Cash and bank' and a['code'] not in s.get('foreign_accounts',{})}
    revenue=set(p['revenue_accounts']);business=revenue|{s['patient_control'],'2300'};channels={'cash':'1000','upi':'1110','card':'1120'}
    values={key:[None]*12 for _,key,_,_ in METRICS};coverage=[];details=[];warnings=[];data=defaultdict(lambda:defaultdict(int));trace=defaultdict(lambda:defaultdict(list));active_month=set();ambiguous=set()
    petty={a['payload']['voucher']:a['payload']['entry'] for a in s['audit'] if a['action']=='PETTY_CASH_RECORDED'}
    for q in s['queue']:
        if q.get('petty_cash') or q.get('kind')=='bulk' and q.get('type')=='Petty cash':
            for r in q['rows']:
                if r.get('voucher'):petty[r['voucher']]=r if r.get('petty_treatment') else dict(r,petty_treatment='Expense',petty_account=r.get('debit_account',''))
    payments={r['voucher']:r for r in ap.data(s)['payments']};invoices={r['id']:r for r in ap.data(s)['invoices']};paid=defaultdict(lambda:defaultdict(int))
    for v in s['vouchers']:
        if not start<=v['date']<=through:continue
        root,sign=roots[v['id']];original=byid[root]
        if original.get('opening') or original.get('closing'):continue
        lines=[l for l in v['lines'] if branch=='ALL' or l['branch']==branch]
        if not lines:continue
        month=v['date'][:7];active_month.add(month);data[month]['revenue']+=sum(l['credit']-l['debit'] for l in lines if l['account'] in revenue)
        if any(l['account'] in revenue for l in lines):trace[month]['revenue'].append(v['id'])
        original_lines=[l for l in original['lines'] if branch=='ALL' or l['branch']==branch]
        receipt_like=(any(l['credit'] and l['account'] in business for l in original_lines) and any(l['debit'] and l['account'] in set(channels.values())|cash_accounts for l in original_lines)) or (any(l['debit'] and l['account'] in business for l in original_lines) and any(l['credit'] and l['account'] in set(channels.values())|cash_accounts for l in original_lines))
        if receipt_like:
            for key,code in channels.items():
                amount=sum(l['debit']-l['credit'] for l in lines if l['account']==code);data[month][key]+=amount
                if amount:trace[month][key].append(v['id'])
        for metric in ('salary','ot'):
            mapped=set(p[metric+'_accounts'])
            if mapped:
                part,bad=_paid_component(original_lines,cash_accounts,mapped);data[month][metric]+=part*sign
                if bad:ambiguous.add((month,metric));warnings.append(v['id']+': '+metric+' cash/noncash split cannot be inferred; post reviewed separate allocations/ledgers.')
                if part:trace[month][metric].append(v['id'])
        codes=set(p['compliance_accounts']);part=sum(l['debit']-l['credit'] for l in lines if l['account'] in codes);data[month]['compliance']+=part
        if part:trace[month]['compliance'].append(v['id'])
        if root in petty:
            r=petty[root];treatment=r.get('petty_treatment');part=r['amount'] if treatment!='Cash top-up' and (p['petty_mode']=='All petty-cash disbursements' or treatment=='Expense') else 0
            if p['petty_mode']=='Operating expenses only' and r.get('petty_account') in set(p['salary_accounts'])|set(p['ot_accounts']):part=0
            data[month]['petty']+=part*sign
            if part:trace[month]['petty'].append(v['id'])
        if root in payments:
            pay=payments[root]
            for item in pay['items']:
                inv=invoices[item['invoice']]
                if branch=='ALL' or inv['branch']==branch:paid[month][inv['id']]+=item['amount']*sign;data[month]['vendor']+=item['amount']*sign
            trace[month]['vendor'].append(v['id'])
    # Count receipt source records once, irrespective of payment splits or later bank settlements.
    proxy=defaultdict(int);receipt_net=defaultdict(int)
    for event in s['vouchers']:
        root,sign=roots[event['id']];original=byid[root];m=original['date'][:7]
        cutoff=min(through,m+'-'+str(monthrange(int(m[:4]),int(m[5:]))[1]))
        if event['date']<=cutoff:receipt_net[root]+=sign
    for original in s['vouchers']:
        if original.get('reverses') or original.get('opening') or original.get('closing') or not start<=original['date']<=through:continue
        lines=[l for l in original['lines'] if branch=='ALL' or l['branch']==branch]
        if not lines:continue
        is_receipt=original.get('source',{}).get('kind')=='daily_sales' or any(l['credit'] and l['account'] in business for l in lines) and any(l['debit'] and l['account'] in set(channels.values())|cash_accounts for l in lines)
        if not is_receipt:continue
        month=original['date'][:7];net=receipt_net[original['id']]
        if net>0:proxy[month]+=original.get('source',{}).get('row_count',1);trace[month]['visits'].append(original['id'])
    for i,month in enumerate(months):
        observation=obs.get((month,branch));inperiod=month<=through[:7];partial=month==through[:7] and int(through[-2:])<monthrange(int(month[:4]),int(month[5:]))[1]
        if partial and observation:observation=None
        hasdata=month in active_month or bool(observation and observation['books_reviewed']);reviewed=bool(observation and observation['books_reviewed']);coverage.append('Future' if not inperiod else 'Month-to-date' if partial and hasdata else 'Reviewed' if reviewed else 'Provisional' if hasdata else 'No posted data')
        if not inperiod:continue
        if hasdata:
            for key in ('revenue','cash','upi','card','petty','vendor'):values[key][i]=data[month][key]
            values['invoices'][i]=sum(amount>0 for amount in paid[month].values())
            for key in ('salary','ot','compliance'):
                if p[key+'_accounts'] and (month,key) not in ambiguous:values[key][i]=data[month][key]
        if observation and observation['visits'] is not None:values['visits'][i]=observation['visits'];visit_source='Reviewed visit input'
        elif hasdata:values['visits'][i]=proxy[month];visit_source='Receipt count proxy'
        else:visit_source='No visit data'
        values['new_patients'][i]=observation['new_patients'] if observation else None
        visits=values['visits'][i]
        if visits and values['revenue'][i] is not None:values['arpp'][i]=int((Decimal(values['revenue'][i])/visits).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        if observation and observation['new_patients'] is not None and visits is not None and observation['new_patients']>visits:warnings.append(month+': new patients exceed the receipt-based visit proxy; review missing/free receipts or supply actual visits.')
        for _,key,label,unit in METRICS:details.append(dict(month=month,metric=label,value=values[key][i],unit='count' if unit=='count' else 'INR',source=visit_source if key in ('visits','arpp') else 'Monthly registration input' if key=='new_patients' else 'Posted ledger / source records',vouchers=sorted(set(trace[month].get('visits' if key=='arpp' else key,[]))),review_basis=observation['basis'] if observation else '',coverage=coverage[i]))
    rows=[]
    for group,key,label,unit in METRICS:
        if key=='petty' and p['petty_mode']=='All petty-cash disbursements':label='Petty cash disbursements'
        rows.append(dict(group=group,key=key,label=label,unit=unit,values=values[key],bands=[band(values[key][:i+1]) if values[key][i] is not None else None for i in range(12)]))
    missing=[key for key in ('salary','ot','compliance') if not p[key+'_accounts']]
    if missing:warnings.insert(0,'Configure dedicated ledger mappings for: '+', '.join(missing)+'. Unmapped metrics are N/A, not zero.')
    return dict(title=TITLE,entity=s['settings']['entity'],year=year,start=start,through=through,scope='All operating units' if branch=='ALL' else foundation.branches(s)[branch],branch=branch,months=months,rows=rows,coverage=coverage,policy=p,details=details,warnings=list(dict.fromkeys(warnings)),logos=report_branding.snapshot(s),registration=copy.deepcopy(s['settings']['registration']),scale=scale,prepared=datetime.now(history.INDIA).isoformat(timespec='seconds'),note='Receipt counts are a patient-visit proxy, not unique patients. ARPP = selected earned revenue / visits. New patients require supplied counts. Collections exclude funding and bank settlements and may differ from earned revenue. Salary/OT are actual cash/bank disbursements; compliance is mapped expense. Vendor counts include part-paid invoices once per month; reversals affect their posting month. Petty cash includes all non-top-up disbursements by default and can overlap salary/vendor classifications; rows are not an additive expense total. Colours show relative levels, not good/bad performance. Provisional/no-data months are identified; monthly completeness requires review.')


def band(history):
    xs=[v for v in history if v is not None]
    if len(xs)<4 or min(xs)==max(xs):return -1
    current=xs[-1];rank=(sum(x<current for x in xs)+Decimal('.5')*sum(x==current for x in xs))/len(xs)
    return 0 if rank>=Decimal('.75') else 1 if rank>=Decimal('.5') else 2 if rank>=Decimal('.25') else 3


def numeric(value,unit,scale='INR'):
    if value is None:return None
    if unit=='count':return value
    divisor=100*(1000 if scale=='INR thousands' and unit=='money' else 100000 if scale=='INR lakh' and unit=='money' else 1)
    return Decimal(value)/divisor


def display(value,unit,scale='INR'):
    number=numeric(value,unit,scale)
    if number is None:return 'N/A'
    return f'{number:,.0f}' if unit=='count' else f'{number:,.2f}'


def colour(b):return MISSING if b is None else NEUTRAL if b==-1 else PALETTE[b]


def input_template(path):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open('w',newline='',encoding='utf-8-sig') as f:csv.writer(f).writerow(INPUT_HEADERS)
        return
    if path.suffix.lower()!='.xlsx':raise ValueError('Save monthly-input template as XLSX or CSV.')
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    w=Workbook();ws=w.active;ws.title='Monthly Inputs';ws.append(INPUT_HEADERS);ws.freeze_panes='C2'
    for c in ws[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor=PALETTE[0][1:]);c.alignment=Alignment(wrap_text=True)
    for col in 'ABCDEF':ws.column_dimensions[col].width=32 if col!='F' else 75
    ws.row_dimensions[1].height=38
    guide=w.create_sheet('Instructions')
    for text in ['One record per month and unit. Month YYYY-MM; unit ALL for entity counts or an exact saved unit code.','Visits override is optional. Blank uses posted receipt counts as the approved patient-visit proxy; supplying actual visits replaces the proxy for that month/scope.','New patients must come from a registration/operational report. Blank means unavailable; 0 means a confirmed zero. Patient names/receipt numbers do not identify new patients.','Books Reviewed: Yes/No. Yes is an explicit completeness review; no-posting months otherwise remain N/A.','Source / Review Basis is required. Counts must be nonnegative whole numbers. New patients cannot exceed an explicitly supplied actual visit count.','ALL and branch observations are separate; no implicit summation/deduplication of patient counts across units.','Imports preview NEW/UPDATE/INVALID rows. Saving updates the month/unit observation with an audit revision and no financial journal. Blank observations replace previous values with unavailable.','Salary/OT/compliance figures are ledger-derived, not entered as unsupported overrides. Review mappings in Business Pulse.','No sample patient or client data is included.']:
        guide.append([text]);guide.cell(guide.max_row,1).alignment=Alignment(wrap_text=True);guide.row_dimensions[guide.max_row].height=38
    guide.column_dimensions['A'].width=125;w.save(path);w.close()

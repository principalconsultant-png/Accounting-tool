"""Monthly salary accrual and dated payment import, without inferred deductions."""
import copy,csv,hashlib,io
from collections import defaultdict
from calendar import monthrange
from datetime import date
from pathlib import Path
from . import core,foundation,ap,bulk_import as bulk,gst,payroll_accounts

FIELDS=('event','month','branch','date','reference','bank','amount','existing','payee','basis')
HEADERS=('Entry Type','Salary Month YYYY-MM','Operating Unit','Entry Date','Reference','Bank Ledger','Amount INR','Existing Voucher (optional)','Payee (optional)','Accounting Review Basis')

def mapping(s):
    m=s['settings'].get('payroll_ledgers',{})
    for role in ('salary_expense','salary_payable'):
        if m.get(role) not in {a['code'] for a in payroll_accounts.eligible(s,role)}:raise ValueError('First configure active salary expense and salary payable in Chart of accounts → Set up salary & PF ledgers.')
    return {r:m[r] for r in ('salary_expense','salary_payable')}

def _totals(lines):
    result=defaultdict(int)
    for l in lines:result[l['account'],l['branch']]+=l['debit']-l['credit']
    return {k:v for k,v in result.items() if v}

def facts(s):return [(q,r) for q in s['queue'] if q.get('salary_journal') for r in q['rows'] if r.get('voucher')]

def validate_row(s,r):
    m=mapping(s)
    if r['debit_account']!=(m['salary_expense'] if r['event']=='ACCRUAL' else m['salary_payable']) or r['credit_account']!=(m['salary_payable'] if r['event']=='ACCRUAL' else r['bank']):raise ValueError('Salary ledger roles changed or source accounts differ. Restage with the reviewed salary roles.')
    if r['event'] not in ('ACCRUAL','PAYMENT'):raise ValueError('Entry Type must be ACCRUAL or PAYMENT.')
    if r['branch'] not in foundation.branches(s,True):raise ValueError('Use a saved active operating-unit code.')
    ap.day(r['date'])
    if not r['basis'].strip():raise ValueError('Accounting Review Basis is required.')
    if r['amount']<=0:raise ValueError('Salary amount must be positive.')
    if r['event']=='ACCRUAL' and r['date'][:7]!=r['month']:raise ValueError('Accrual date must fall in its earned Salary Month.')
    if r['event']=='PAYMENT' and (not r['reference'].strip() or s['account_details'].get(r['bank'],{}).get('group')!='Cash and bank' or r['bank'] in s.get('foreign_accounts',{}) or not s['account_details'][r['bank']].get('active',False)):raise ValueError('Payment requires the actual transfer reference and active INR cash/bank ledger code.')
    if r['existing']:
        v=next((v for v in s['vouchers'] if v['id']==r['existing']),None)
        from . import tds
        if not v or v.get('opening') or v.get('closing') or v.get('reverses') or tds._net(s).get(v['id'])!=1 or v['date']!=r['date'] or _totals(v['lines'])!=_totals(bulk._lines(r)):raise ValueError('Existing voucher must exactly match the accrual/payment date, unit, accounts and amount; direct salary-expense bank payments need review/reclassification before this accrual/settlement workflow.')
        if r['event']=='PAYMENT' and v.get('metadata',{}).get('reference') and ap.norm(v['metadata']['reference'])!=ap.norm(r['reference']):raise ValueError('Existing payment reference differs from the source. Use its actual bank reference.')
        if any(pr.get('voucher')==v['id'] for q,pr in facts(s)):raise ValueError('This existing voucher is already registered to a salary source.')
    else:
        from . import tds
        if r['event']=='ACCRUAL' and any(pr['event']=='ACCRUAL' and pr['month']==r['month'] and pr['branch']==r['branch'] and tds._net(s).get(pr['voucher'])==1 for q,pr in facts(s)):raise ValueError('This month/unit already has a registered salary accrual. Upload only its remaining payments or review/correct the original accrual.')
        net=tds._net(s)
        for v in s['vouchers']:
            if v.get('reverses') or v.get('opening') or v.get('closing') or net.get(v['id'])!=1:continue
            if r['event']=='ACCRUAL' and v['date'][:7]==r['month'] and any(l['account']==m['salary_expense'] and l['branch']==r['branch'] and l['debit'] for l in v['lines']) and any(l['credit'] and s['account_details'][l['account']]['group']=='Cash and bank' for l in v['lines']):raise ValueError('Direct salary-expense/bank posting already exists: '+v['id']+'. Review/reclassify it before adding a monthly accrual; do not expense payroll twice.')
            if r['event']=='ACCRUAL' and v['date'][:7]==r['month'] and _totals(v['lines'])==_totals(bulk._lines(r)):raise ValueError('A matching monthly accrual already exists: '+v['id']+'. Fill Existing Voucher and its actual accrual date to link instead of posting again.')
            if r['event']=='PAYMENT' and core.financial_year(v['date'])==core.financial_year(r['date']) and ap.norm(v.get('metadata',{}).get('reference',''))==ap.norm(r['reference']) and any(l['account']==r['bank'] and l['credit'] and l['branch']==r['branch'] for l in v['lines']):raise ValueError('A bank payment with this reference already exists: '+v['id']+'. Link its exact voucher or correct the original; do not post twice.')

def check(s,reversal=None):
    roots=gst._roots(s);byroot={};events=defaultdict(list)
    for q,r in facts(s):
        if r['voucher'] in byroot:raise ValueError('Salary voucher registered more than once.')
        byroot[r['voucher']]=r
    for v in s['vouchers']:
        root,sign=roots[v['id']]
        if root in byroot:events[v['date']].append((byroot[root],sign))
    if reversal:
        root,sign=roots[reversal[0]]
        if root in byroot:events[reversal[1]].append((byroot[root],-sign))
    balance=defaultdict(int);accruals=defaultdict(int)
    for day,changes in sorted(events.items()):
        for r,sign in changes:
            key=r['month'],r['branch'];balance[key]+=r['amount']*sign*(1 if r['event']=='ACCRUAL' else -1)
            if r['event']=='ACCRUAL':accruals[key]+=sign
        bad=next((key for key,n in balance.items() if n<0),None)
        if bad:raise ValueError('Salary '+bad[0]+' / '+bad[1]+' at '+day+': payments exceed the dated accrual. Include/link the accrual first; reverse dependent payments before reversing it.')
        bad=next((key for key,n in accruals.items() if n not in (0,1)),None)
        if bad:raise ValueError('Salary '+bad[0]+' / '+bad[1]+': only one active total accrual is allowed. Review the existing monthly accrual.')
    return True

@ap.atomic
def stage(s,raw,filename):
    m=mapping(s);headers,source,sheet=bulk._read(raw,filename,'Salary Journals')
    if headers!=list(HEADERS):raise ValueError('Use the exact standard salary template headings and Salary Journals sheet.')
    digest=hashlib.sha256(raw).hexdigest()
    if any(q.get('salary_journal') and q['digest']==digest and q['status']!='CANCELLED' for q in s['queue']):raise ValueError('This salary file is already staged or processed. Open its saved batch.')
    q=dict(id=ap.uid(),kind='bulk',type='Journal',salary_journal=True,salary_mapping=m,digest=digest,filename=Path(filename).name,mapping={},sheet=sheet,headers=headers,rows=[],status='PENDING_REVIEW');seen=set();month_seen=set();linked=set()
    for number,values in enumerate(source,2):
        if not any(v not in (None,'') for v in values):continue
        original={f:values[i] if i<len(values) else '' for i,f in enumerate(FIELDS)}
        r=dict(salary_source=True,source_row=number,sheet=sheet,review='PENDING',reason='',error='',raw=copy.deepcopy(original),journal_id='')
        try:
            if any(isinstance(v,str) and v.lstrip().startswith('=') for v in values):raise ValueError('Use literal salary values, not formulas.')
            if len(values)>len(FIELDS) and any(v not in (None,'') for v in values[len(FIELDS):]):raise ValueError('Extra values beyond template headings.')
            r.update({k:'' if v is None else str(v).strip() for k,v in original.items()});r['event']=r['event'].upper();month=r['month']
            if date.fromisoformat(month+'-01').strftime('%Y-%m')!=month:raise ValueError('Salary Month must be YYYY-MM.')
            if hasattr(original['date'],'isoformat'):r['date']=original['date'].isoformat()[:10]
            if r['event']=='ACCRUAL':
                r['date']=r['date'] or month+'-'+str(monthrange(int(month[:4]),int(month[5:]))[1]);r['reference']=r['reference'] or 'SAL-ACCR-'+month+'-'+r['branch'];r['debit_account']=m['salary_expense'];r['credit_account']=m['salary_payable'];r['bank']=''
            else:r['debit_account']=m['salary_payable'];r['credit_account']=r['bank']
            r['amount']=ap.positive(r['amount']);r['narration']='Salary '+r['event'].lower()+' for '+month+' | '+r['payee']+' | '+r['basis'];r['key']=bulk._identity(r)
            validate_row(s,r)
            if r['key'] in seen or (not r['existing'] and r['key'] in bulk._known(s)):raise ValueError('Salary date/unit/reference is already queued or repeated.')
            seen.add(r['key'])
            if r['existing']:
                if r['existing'] in linked:raise ValueError('An existing voucher appears twice in this file.')
                linked.add(r['existing'])
            if r['event']=='ACCRUAL':
                key=r['month'],r['branch']
                if key in month_seen:raise ValueError('Provide one total accrual per month/unit, not one accrual per employee.')
                month_seen.add(key)
            bulk._validate(s,'Journal',r)
        except (ValueError,KeyError,TypeError) as error:r.update(review='INVALID',error=str(error))
        q['rows'].append(r)
    if not q['rows']:raise ValueError('No salary source rows found.')
    s['queue'].append(q);core.add_audit(s,'SALARY_JOURNAL_STAGED',dict(batch=q['id'],filename=q['filename'],digest=digest,rows=len(q['rows'])));return q

@ap.atomic
def post(s,qid):
    q=bulk._queue(s,qid)
    if not q.get('salary_journal') or q['status']!='PENDING_REVIEW':raise ValueError('Select a pending salary batch.')
    if q['salary_mapping']!=mapping(s):raise ValueError('Salary ledger roles changed. Cancel/restage this batch for fresh review.')
    if any(r['review'] not in ('APPROVED','REJECTED') for r in q['rows']):raise ValueError('Approve or explicitly reject every salary source row first.')
    rows=[r for r in q['rows'] if r['review']=='APPROVED']
    if not rows:raise ValueError('No approved salary rows selected.')
    for r in sorted(rows,key=lambda r:(r['date'],r['event']!='ACCRUAL',r['source_row'])):
        try:validate_row(s,r)
        except ValueError as error:raise ValueError('Salary source row '+str(r['source_row'])+': '+str(error)) from None
        if not r['existing'] and r['key'] in bulk._known(s,qid):raise ValueError('This source identity was registered in another batch after review.')
        if r['existing']:r['voucher']=r['existing']
        else:
            if r['event']=='PAYMENT':
                dates={r['date'],*[v['date'] for v in s['vouchers'] if v['date']>=r['date']]}
                if any(core.balances(s,on,r['branch'])[r['debit_account']]>-r['amount'] for on in dates):raise ValueError('Salary source row '+str(r['source_row'])+' ('+r['month']+' / '+r['branch']+'): salary payable does not support payment on '+r['date']+' or after later settlements. Link already-posted payments and review existing payroll before posting again.')
            v=core.post(s,r['date'],r['narration'],bulk._lines(r),metadata=dict(type='Payment' if r['event']=='PAYMENT' else 'Journal',reference=r['reference'],payee=r['payee'],**({'bank_account':r['bank']} if r['event']=='PAYMENT' else {})),source=dict(kind='bulk_import',document_id=qid,record_id=r['key'],row_count=1));r['voucher']=v['id']
        check(s)
    q['status']='PROCESSED';core.add_audit(s,'SALARY_JOURNAL_POSTED',dict(batch=qid,vouchers=[r['voucher'] for r in rows],new_journals=sum(not r['existing'] for r in rows),linked=sum(bool(r['existing']) for r in rows)));return [r['voucher'] for r in rows]

def template(path,s=None):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(HEADERS)
        return
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    w=Workbook();ws=w.active;ws.title='Salary Journals';ws.append(HEADERS);ws.freeze_panes='D2';ws.auto_filter.ref='A1:J1001'
    for c in ws[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='154C8A');c.alignment=Alignment(wrap_text=True)
    for col in 'ABCDEFGHIJ':ws.column_dimensions[col].width=28 if col!='J' else 70
    ws.row_dimensions[1].height=40
    for row in ws.iter_rows(min_row=2,max_row=1001):
        for col in (1,2,4,5,7):row[col].number_format='@'
    help=w.create_sheet('Instructions')
    for text in ['One ACCRUAL row per earned month/unit, Amount INR = reviewed monthly salary total. Multiple PAYMENT rows are allowed for actual bank transfers.', 'Entry Type ACCRUAL or PAYMENT. Salary Month YYYY-MM; exact active unit code. ACCRUAL date blank defaults to month end, or supply a reviewed earned-period date in that month.', 'PAYMENT: actual date, bank ledger code, full transfer reference and amount; payee optional. Preserve references as text. Do not merge different dates/withdrawals into a fictitious monthly bank payment.', 'This simple template assumes no PF/other deduction allocation. Complex gross/net payroll uses reviewed compound manual/general bulk JEs. PF is never inferred.', 'Salary and salary-payable accounts come from reviewed Chart of accounts salary/PF setup; no employee-level details are required for the monthly accrual.', 'One accrual does not imply it was fully paid. Payments must follow an existing dated accrual and cannot exceed the earned month/unit amount or actual payable capacity. Unpaid amounts stay payable.', 'If an accrual/payment is already posted, provide its exact Existing Voucher and actual date to link without another JE. Direct salary-expense/bank payments require review/reclassification before entering an accrual plus settlement.', 'Upload only stages rows. Review invalid/duplicate reasons, approve/reject, preview all proposed journals and confirm. Posting is atomic. Do not change references or monthly identifiers to bypass existing records.', 'Accrual reference blank gets SAL-ACCR-YYYY-MM-UNIT. Actual payment reference required. Accounting Review Basis required on every row. No formulas.', 'Use All book movements in bank reconciliation to match salary payment JEs; uploading does not import bank statements or automatically reconcile them.']:
        help.append([text]);help.cell(help.max_row,1).alignment=Alignment(wrap_text=True);help.row_dimensions[help.max_row].height=40
    help.column_dimensions['A'].width=125
    if s:
        units=w.create_sheet('Units');units.append(['Code','Operating unit'])
        for code,name in foundation.branches(s,True).items():units.append([code,name])
        lookup=w.create_sheet('Ledger lookup');lookup.append(['Code','Ledger','Kind','Group'])
        for a in s['accounts']:lookup.append([a['code'],a['name'],a['kind'],s['account_details'][a['code']]['group']])
    for sheet in w:
        for row in sheet:
            for c in row:
                if isinstance(c.value,str):c.data_type='s'
    w.save(path);w.close()

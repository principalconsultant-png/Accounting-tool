"""Cash disbursements, funding and reviewed report imports using shared journals."""
import copy,csv,hashlib,io
from datetime import date,datetime
from pathlib import Path
from . import ap,bulk_import as bulk,core,foundation,financial_reports as reports,tds

TREATMENTS=('Expense','Stock purchase','Staff advance','Liability settlement','Cash top-up')
FIELDS=('date','reference','branch','category','treatment','account','amount','narration','basis')
HEADERS=('Date','Voucher Reference','Operating Unit','Category','Treatment','Counterpart Ledger','Amount INR','Description','Accounting Review Basis')
ALIASES={ap.norm(k):k for k in FIELDS};ALIASES.update({ap.norm(h):k for h,k in zip(HEADERS,FIELDS)})

def text(v):return v.isoformat()[:10] if isinstance(v,(date,datetime)) else '' if v is None else str(int(v)) if isinstance(v,float) and v.is_integer() else str(v).strip()

def defaults(s,label):
    n=ap.norm(label);saved=s['settings'].get('petty_cash_mapping',{}).get(label)
    if saved:return copy.deepcopy(saved)
    if n in ('salarypayble','salarypayable'):return dict(treatment='Liability settlement',account='')
    if n in ('advancesalary','salaryadvance'):return dict(treatment='Staff advance',account='')
    if n in ('purchaseofmedicines','medicinepurchase'):return dict(treatment='Stock purchase',account='1100')
    account='4500' if n in ('treatmentexpenses','surgicals','purchaseofconsumables') else '4540' if n in ('gas','watercharges','electricitycharges','telephonecharges') else '4550' if n=='repairsmaintenance' else '4520' if n=='staffwelfareexp' else '4530' if n=='rentstaff' else '4590'
    return dict(treatment='Expense',account=account)


def validate(s,r):
    treatment=r.get('petty_treatment');account=r.get('petty_account','');basis=r.get('petty_basis','')
    if treatment not in TREATMENTS:raise ValueError('Select Expense, Stock purchase, Staff advance, Liability settlement or Cash top-up.')
    if not basis.strip():raise ValueError('Accounting Review Basis is required; review cash evidence, category and any GST/TDS treatment.')
    if type(r.get('amount'))!=int or r['amount']<=0:raise ValueError('Cash amount must be positive; refunds/negative cells require separate reviewed correction.')
    a=next((a for a in s['accounts'] if a['code']==account),None);d=s['account_details'].get(account,{})
    if not a or not d.get('active',True):raise ValueError('Choose an active counterpart ledger; create a suitable account in Chart of accounts if missing.')
    group=d.get('group');kind=a['kind']
    if account in s.get('foreign_accounts',{}):raise ValueError('Use the FX conversion workflow for foreign-currency funding; petty cash entries are INR only.')
    if treatment=='Expense' and kind!='Expense':raise ValueError('Expense treatment requires an expense ledger.')
    if treatment=='Stock purchase' and (kind!='Asset' or group!='Inventory'):raise ValueError('Stock purchase requires an Inventory asset ledger, not an expense.')
    if treatment=='Staff advance' and (kind!='Asset' or group!='Other assets'):raise ValueError('Staff advance needs an Other assets ledger; create a staff-advance account first.')
    if treatment=='Liability settlement' and (kind!='Liability' or group!='Other liabilities'):raise ValueError('Salary/liability settlement needs an Other liabilities ledger and an existing reviewed accrual. Use AP for vendor invoice payments and dedicated tax pages for GST/TDS.')
    if treatment=='Liability settlement':
        dates={r['date']} | {v['date'] for v in s['vouchers'] if v['date']>=r['date'] and any(l['account']==account and l['branch']==r['branch'] for l in v['lines'])}
        if any(core.balances(s,on,r['branch'])[account]>-r['amount'] for on in dates):raise ValueError('Settlement exceeds the credited salary/liability balance on the payment date or after a later recorded settlement. Review its existing accrual/opening first; do not expense the payment twice.')
    if treatment=='Cash top-up' and not (kind=='Asset' and group=='Cash and bank' or kind=='Liability' and group in ('Borrowings','Other liabilities') or kind=='Equity'):
        raise ValueError('Cash top-up needs the genuine bank/cash, funding liability or equity source; never a revenue or expense ledger.')
    if account=='1000':raise ValueError('Counterpart cannot be the same 1000 Cash ledger.')
    if s['account_details'].get('1000',{}).get('group')!='Cash and bank' or not s['account_details']['1000'].get('active',True):raise ValueError('Activate 1000 Cash as a Cash and bank ledger.')
    expected=('1000',account) if treatment=='Cash top-up' else (account,'1000')
    if (r['debit_account'],r['credit_account'])!=expected:raise ValueError('Cash lines differ from the reviewed treatment. Correct and reimport.')


def resolved(s,v):
    if any(str(x).startswith('=') for x in v.values()):raise ValueError('Use literal transaction values, not formulas.')
    r=dict(date=ap.day(text(v.get('date',''))),reference=text(v.get('reference','')),branch=text(v.get('branch','')),narration=text(v.get('narration','')),amount=ap.positive(text(v.get('amount',''))),petty_category=text(v.get('category','')),petty_treatment=text(v.get('treatment','')),petty_account=text(v.get('account','')),petty_basis=text(v.get('basis','')),journal_id='')
    if not r['reference'] or not r['narration'] or not r['petty_category']:raise ValueError('Date, reference, category and description are required.')
    if r['branch'] not in foundation.branches(s,True):raise ValueError('Select an active operating unit.')
    r.update(debit_account='1000' if r['petty_treatment']=='Cash top-up' else r['petty_account'],credit_account=r['petty_account'] if r['petty_treatment']=='Cash top-up' else '1000');validate(s,r);return r


@ap.atomic
def record(s,v,confirmed=False):
    if not confirmed:raise ValueError('Confirm cash/source/accounting and tax review before posting.')
    r=resolved(s,v);key=bulk._identity(r)
    if key in bulk._known(s):raise ValueError('This unit/date/reference is already recorded or queued; review its original instead of paying twice.')
    voucher=core.post(s,r['date'],r['narration'],bulk._lines(r),metadata=dict(type='Receipt' if r['petty_treatment']=='Cash top-up' else 'Payment',reference=r['reference']))
    core.add_audit(s,'PETTY_CASH_RECORDED',dict(entry=r,voucher=voucher['id'],key=key));return voucher


def read_source(raw,filename,sheet=None):
    """Read standard rows or the submitted category-by-date matrix, without posting."""
    if len(raw)>25*1024*1024:raise ValueError('Import exceeds 25 MB.')
    if Path(filename).suffix.lower()=='.csv':
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))));label='CSV'
    elif Path(filename).suffix.lower()=='.xlsx':
        from openpyxl import load_workbook
        from zipfile import ZipFile
        with ZipFile(io.BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('Expanded workbook exceeds 100 MB.')
        w=load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
        try:
            name=sheet or ('Expenses' if 'Expenses' in w.sheetnames else w.sheetnames[0] if len(w.sheetnames)==1 else None)
            if name not in w.sheetnames:raise ValueError('Use Expenses sheet or a one-sheet workbook; otherwise choose an exact worksheet.')
            ws=w[name]
            if ws.max_row>50001 or ws.max_column>366:raise ValueError('Petty cash import exceeds 50000 rows / 366 columns.')
            rows=list(ws.values);label=name
        finally:w.close()
    else:raise ValueError('Upload XLSX or CSV; old XLS must be saved as XLSX first.')
    if not rows or len(rows)>50001:raise ValueError('Empty or oversized petty cash file.')
    headers=[text(v) for v in rows[0]]
    if all(ALIASES.get(ap.norm(h)) for h in headers):
        mapped=[ALIASES[ap.norm(h)] for h in headers]
        if len(mapped)!=len(set(mapped)) or set(mapped)!=set(FIELDS):raise ValueError('Use all nine unique standard petty cash headings.')
        entries=[]
        for number,row in enumerate(rows[1:],2):
            if not any(text(v) for v in row):continue
            entry={key:text(row[i]) if i<len(row) else '' for i,key in enumerate(mapped)}
            if any(text(v) for v in row[len(headers):]):entry['extra_values']='Extra values beyond template headings'
            entries.append(dict(values=entry,source_row=number,source_cell='',category=entry.get('category','')))
        if not entries:raise ValueError('No petty cash entries found.')
        return dict(layout='standard',sheet=label,entries=entries,warnings=[],categories=[])
    # Matrix: the Date header anchors the category column; totals/summary formulas never become entries.
    anchor=next(((i,j) for i,row in enumerate(rows[:20]) for j,c in enumerate(row) if ap.norm(c)=='date'),None)
    if anchor is None:raise ValueError('Use the standard petty cash template or a Date/category matrix matching the supplied report.')
    hr,lc=anchor;datecols={}
    for j,value in enumerate(rows[hr]):
        try:
            day=text(value);ap.day(day);datecols[j]=day
        except (ValueError,TypeError):pass
    if not datecols:raise ValueError('Matrix dates must be real Excel dates or YYYY-MM-DD text.')
    getlabel=lambda row: text(row[lc]) if lc<len(row) else ''
    detail=next((i for i in range(hr+1,len(rows)) if ap.norm(getlabel(rows[i]))=='expensedetails'),None)
    end=next((i for i in range((detail or hr)+1,len(rows)) if ap.norm(getlabel(rows[i]))=='total'),None)
    if detail is None or end is None:raise ValueError('Matrix must contain Expense Details followed by Total. Summary rows are never treated as expenses.')
    entries=[];categories=[];daily={d:0 for d in datecols.values()};warnings=[]
    from openpyxl.utils import get_column_letter
    for i in range(detail+1,end):
        category=getlabel(rows[i])
        for j,day in datecols.items():
            value=rows[i][j] if j<len(rows[i]) else None
            if value in (None,'',0,'0'):continue
            if not category:raise ValueError('Expense category missing at row '+str(i+1))
            if category not in categories:categories.append(category)
            entries.append(dict(values=dict(date=day,category=category,amount=text(value),narration=category),source_row=i+1,source_cell=get_column_letter(j+1)+str(i+1),category=category))
            try:daily[day]+=ap.positive(text(value))
            except ValueError:warnings.append('Invalid amount at '+get_column_letter(j+1)+str(i+1)+': review the flagged source row.')
        for j,value in enumerate(rows[i]):
            if j>lc and j not in datecols and value not in (None,'',0,'0'):raise ValueError('Nonzero expense outside a dated column at '+get_column_letter(j+1)+str(i+1))
    if not entries:raise ValueError('No nonzero category/date expenses found.')
    warnings.append('Matrix import includes category/date cash outflows only. Opening, Cash Received, totals, running balances and cumulative formulas are not posted. Review funding separately to avoid duplicating daily cash sales or bank withdrawals.')
    openingrow=next((i for i in range(hr+1,detail) if ap.norm(getlabel(rows[i])) in ('opbalance','openingbalance')),None)
    cashrow=next((i for i in range(hr+1,detail) if ap.norm(getlabel(rows[i]))=='cashreceived'),None)
    firstcol=min(datecols);opening=rows[openingrow][firstcol] if openingrow is not None else None
    if opening is not None and not str(opening).startswith('='):
        try:
            running=core.money(str(opening));minimum=running;received=0
            for j,day in datecols.items():
                cash=rows[cashrow][j] if cashrow is not None and j<len(rows[cashrow]) else 0
                cash=core.money(text(cash) or '0');received+=cash;running+=cash-daily[day];minimum=min(minimum,running)
            warnings.append('Source cash control (not posted): opening '+core.rupees(core.money(str(opening)))+', cash received '+core.rupees(received)+', outflows '+core.rupees(sum(daily.values()))+', calculated closing '+core.rupees(running)+'.')
            if minimum<0:warnings.append('Negative source cash balance detected. Physical cash cannot be negative: review opening/funding and staff-funded items before finalising. No balancing or opening journal is inserted.')
        except ValueError:warnings.append('Source cash-control formulas/amounts could not be checked; review the original cash book. No cached formula result is assumed.')
    return dict(layout='matrix',sheet=label,entries=entries,categories=categories,warnings=warnings)


@ap.atomic
def stage(s,raw,filename,parsed,branch='',prefix='',mapping=None,basis='',confirmed=False):
    if not confirmed:raise ValueError('Confirm source categories, ledger mapping, period and no duplicate cash/GST/TDS posting before importing.')
    if parsed!=read_source(raw,filename,parsed['sheet'] if parsed['sheet']!='CSV' else None):raise ValueError('Source preview changed; read and review the file again.')
    if parsed['layout']=='matrix' and (branch not in foundation.branches(s,True) or not prefix.strip() or not basis.strip()):raise ValueError('Matrix import needs an active unit, stable report reference and accounting review basis.')
    out=io.StringIO();writer=csv.writer(out);writer.writerow([*bulk.FIELDS,'petty_category','petty_treatment','petty_account','petty_basis','petty_error']);orig=[]
    for item in parsed['entries']:
        v=dict(item['values']);error=''
        if parsed['layout']=='matrix':
            m=(mapping or {}).get(v['category'],{});v.update(branch=branch,reference=prefix.strip()+'-'+v['date']+'-'+ap.norm(v['category']),treatment=m.get('treatment',''),account=m.get('account',''),basis=basis.strip())
        account=v.get('account','');treatment=v.get('treatment','');dr,cr=('1000',account) if treatment=='Cash top-up' else (account,'1000')
        try:
            if v.get('extra_values'):raise ValueError(v['extra_values'])
            resolved(s,v)
        except (ValueError,TypeError) as e:error=str(e)
        writer.writerow([v.get('date',''),v.get('reference',''),v.get('branch',''),v.get('narration',''),dr,cr,v.get('amount',''),'',v.get('category',''),treatment,account,v.get('basis',''),error]);orig.append(item)
    result=bulk.stage(s,out.getvalue().encode('utf-8-sig'),Path(filename).stem+'.csv','Journal');q=bulk._queue(s,result['id']);q.update(filename=Path(filename).name,petty_cash=True,original_digest=hashlib.sha256(raw).hexdigest(),original_sheet=parsed['sheet'],petty_layout=parsed['layout'],warnings=parsed['warnings'])
    for r,item in zip(q['rows'],orig):
        for k in ('petty_category','petty_treatment','petty_account','petty_basis'):r[k]=r['raw'].get(k,'')
        r['source_row']=item['source_row'];r['source_cell']=item['source_cell'];r['source_values']=copy.deepcopy(item['values'])
        if r['raw'].get('petty_error'):r.update(review='INVALID',error=r['raw']['petty_error'])
    if parsed['layout']=='matrix':s['settings']['petty_cash_mapping']=copy.deepcopy(mapping or {})
    core.add_audit(s,'PETTY_CASH_STAGED',dict(id=q['id'],filename=q['filename'],sha256=q['original_digest'],sheet=q['original_sheet'],layout=parsed['layout'],rows=len(q['rows'])));return copy.deepcopy(q)


def register(s,start,end,branch='ALL'):
    net=tds._net(s,end);rows=[]
    entries=[(a['payload']['entry'],a['payload']['voucher']) for a in s['audit'] if a['action']=='PETTY_CASH_RECORDED']
    entries += [(r,r['voucher']) for q in s['queue'] if q.get('petty_cash') for r in q['rows'] if r.get('voucher')]
    for r,vid in entries:
        if start<=r['date']<=end and (branch=='ALL' or r['branch']==branch):rows.append(dict(r,voucher=vid,status='Posted' if net.get(vid,0)==1 else 'Reversed'))
    return sorted(rows,key=lambda r:(r['date'],r['reference']))


def register_pack(s,start,end,branch='ALL'):
    p=reports.snapshot(s,'Trial balance',start,end,branch);names={a['code']:a['name'] for a in s['accounts']};rows=register(s,start,end,branch)
    p.update(mode='Petty cash register',columns=['Date','Reference','Unit','Category','Treatment','Counterpart','INR','Voucher','Status'],money_columns=[6],rows=[[r['date'],r['reference'],r['branch'],r['petty_category'],r['petty_treatment'],r['petty_account']+' '+names.get(r['petty_account'],''),r['amount'],r['voucher'],r['status']] for r in rows],controls={},note='1000 Cash: genuine expenses debit P&L; stock and staff advances debit assets; salary settlements debit an existing liability. Funding receipts are not expenses/income. All cash movements feed the bank/cash definition in cash-flow reports; only actual bank withdrawals are matched to bank statements. No automatic GST/TDS or opening entries.');return p


def review_pack(s,key):
    q=bulk._queue(s,key);dates=[]
    for r in q['rows']:
        try:dates.append(ap.day(str(r.get('date',''))))
        except ValueError:pass
    start=min(dates or ['1900-01-01']);end=max(dates or [start]);p=reports.snapshot(s,'Trial balance',start,end);names={a['code']:a['name'] for a in s['accounts']};rows=[]
    for r in q['rows']:
        account=r.get('petty_account','');reason=(r['error'] or r['reason'])+' | Basis: '+r.get('petty_basis','')
        if type(r.get('amount'))!=int:reason+=' | Entered amount: '+str(r.get('amount',''))
        rows.append([(r.get('source_cell') or str(r['source_row']))+' / '+str(r.get('date','')),r.get('branch','')+' / '+r.get('reference',''),r.get('petty_category','')+' / '+r.get('petty_treatment',''),account+' '+names.get(account,''),r.get('amount') if type(r.get('amount'))==int else None,r['review'],reason,r.get('voucher','')])
    p.update(mode='Petty cash import review',columns=['Source / date','Unit / reference','Category / treatment','Counterpart ledger','Amount INR','Review','Reason / basis','Voucher'],money_columns=[4],rows=rows,controls={},status=q['status'],note=q['filename']+' | Source SHA256 '+q.get('original_digest',q['digest'])+' | Worksheet '+q.get('original_sheet','CSV')+'. Only explicitly approved rows post. Original source fields/cells and decisions remain in the saved batch. Funding/openings/summary formula rows from a matrix never post automatically.');return p


def template(path,state=None):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(HEADERS)
        return
    if path.suffix.lower()!='.xlsx':raise ValueError('Save petty cash template as XLSX or CSV.')
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    w=Workbook();ws=w.active;ws.title='Expenses';ws.append(HEADERS);ws.freeze_panes='A2';ws.auto_filter.ref='A1:I1001'
    for c in ws[1]:c.font=Font(bold=True,color='154C8A');c.fill=PatternFill('solid',fgColor='E8F0FC');c.alignment=Alignment(wrap_text=True)
    ws.row_dimensions[1].height=34
    for col in 'ABCDEFGHI':ws.column_dimensions[col].width=28 if col not in 'HI' else 55
    for row in range(2,1002):ws.cell(row,1).number_format='yyyy-mm-dd';ws.cell(row,2).number_format='@';ws.cell(row,6).number_format='@';ws.cell(row,7).number_format='#,##0.00'
    dv=DataValidation(type='list',formula1='"'+','.join(TREATMENTS)+'"');dv.showErrorMessage=True;ws.add_data_validation(dv);dv.add('E2:E1001')
    accounts=w.create_sheet('Accounts');accounts.append(['Code','Name','Kind','Group']);s=state if state is not None else core.empty_state()
    for a in s['accounts']:accounts.append([a['code'],a['name'],a['kind'],s['account_details'][a['code']]['group']])
    units=w.create_sheet('Units');units.append(['Code','Name'])
    for code,name in foundation.branches(s,True).items():units.append([code,name])
    help=w.create_sheet('Instructions');help.append(['Topic','Instruction'])
    for row in [('Rows','One actual cash transaction/category/date per row. All nine columns required. Reference must be stable and unique per unit/date; do not use new references to bypass duplicates.'),('Expense','Counterpart = reviewed expense account; credit 1000 Cash.'),('Stock purchase','Counterpart must be Inventory asset (1100 for medicine stock). Not an immediate P&L expense.'),('Staff advance','Create/select an Other assets ledger. Never book the advance as salary expense.'),('Liability settlement','Select an Other liabilities ledger for an existing salary accrual. AP vendor payments and tax settlements must use their dedicated modules.'),('Cash top-up','Debit 1000 Cash; counterpart is the actual bank/cash, funding liability or equity source. Not sales or expenses. Do not duplicate cash sales receipts or a withdrawal already booked.'),('Review basis','Required evidence for cash source, date, category and accounting/GST/TDS treatment. No automatic GST/TDS entries.'),('Report matrix','Original category-by-date XLSX can be uploaded directly. Map nonzero categories before staging. Opening, Cash Received and total/formula summaries are excluded and never posted automatically.'),('Dates','Use true Excel dates or YYYY-MM-DD. Put actual historical payment date, not date of data entry.'),('Review','Stage never posts. Approve valid rows and reject flagged rows with a reason; inspect named journals before final approval. Correct mapping/source: cancel unused batch and reupload. Keep source/reference stable.'),('Cash control','Set opening cash through reviewed setup/opening journals. Review negative physical cash and reconcile funding separately. Public template contains no client data.')]:help.append(row)
    help.column_dimensions['A'].width=28;help.column_dimensions['B'].width=120
    for row in help:
        for c in row:c.alignment=Alignment(wrap_text=True,vertical='top')
        help.row_dimensions[row[0].row].height=44
    w.save(path);w.close()

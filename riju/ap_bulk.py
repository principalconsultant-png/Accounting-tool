"""Source-preserving reviewed vendor-invoice CSV/XLSX batch registration."""
import copy
import csv
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import hashlib
import json
from pathlib import Path
import uuid
from . import ap,core,foundation,bulk_import,financial_reports as reports

FIELDS=('vendor_name','reference','invoice_date','received_date','accounting_date','credit_days','due_basis','payment_date','branch','amount','payable','cost_account','basis','existing_voucher')
HEADERS=('Vendor Name','Vendor Invoice Number','Invoice Date','Invoice Received Date','Accrual Accounting Date','Credit Period Calendar Days','Credit Period Starts At','Scheduled Payment Date','Operating Unit','Net Amount Payable to Vendor INR','Trade Payables Ledger','New Accrual / Cost Asset Ledger','Accounting Review Basis','Existing GST/TDS/CWIP Accrual Voucher (optional)')
ALIASES={ap.norm(h):key for key,h in zip(FIELDS,HEADERS)}
ALIASES.update({ap.norm(k):k for k in FIELDS})
ALIASES.update({'netamountpayabletovendor':'amount','taxpayablesledger':'payable','newaccuralcostassetledger':'cost_account','newaccrualcostassetledger':'cost_account','newaccrualcostassetledgeroptional':'cost_account','existinggsttdscwipaccrualvoucher':'existing_voucher','creditperiodcalendarday':'credit_days','accountingreviewbasis':'basis','sourcetaxaccountingreviewbasis':'basis'})


def batch(s,key):
    q=next((q for q in s['queue'] if q['id']==key and q.get('kind')=='ap_bulk'),None)
    if not q:raise ValueError('Select an AP bulk invoice batch.')
    return q

def _identity(values):return (values['vendor'],ap.norm(values['reference']),core.financial_year(values['invoice_date']))
def _known(s,exclude=None):return {_identity(r['values']) for q in s['queue'] if q.get('kind')=='ap_bulk' and q['id']!=exclude and q['status']!='CANCELLED' for r in q['rows'] if r['validation']=='VALID' and r['review']!='REJECTED'}

def _string(value):
    if value is None:return ''
    if isinstance(value,(datetime,date)):return value.isoformat()[:10]
    if isinstance(value,float) and value.is_integer():return str(int(value))
    return str(value).strip()

def canonical(s,raw):
    if raw.get('_extra_values'):raise ValueError('Source row contains extra values beyond the standard headings; correct the source row before approval.')
    if any(str(v).startswith('=') for v in raw.values()):raise ValueError('Use literal source values, not spreadsheet formulas.')
    candidates=[v for v in ap.data(s)['vendors'] if ap.norm(raw['vendor_name']) in {ap.norm(n) for n in [v['name'],*v.get('previous_names',[])]}]
    if len(candidates)!=1:raise ValueError('Vendor Name must match one saved vendor. Add/correct it in Vendor master, then Revalidate this batch.')
    vendor=candidates[0]
    if not vendor.get('active',True):raise ValueError('Vendor is inactive; review Vendor master, then revalidate.')
    values={key:_string(raw.get(key,'')) for key in FIELDS};values['vendor']=vendor['id'];values.pop('vendor_name')
    if values['existing_voucher'] and not any(v['id']==values['existing_voucher'] for v in s['vouchers']):raise ValueError('Existing accrual voucher must already exist in the actual books; it cannot refer to a new row in this upload.')
    if not values['reference']:raise ValueError('Vendor Invoice Number is required.')
    for key in ('invoice_date','received_date','accounting_date','payment_date'):
        if key=='payment_date' and not values[key]:continue
        try:ap.day(values[key])
        except ValueError:raise ValueError(HEADERS[FIELDS.index(key)]+' requires an actual Excel date or YYYY-MM-DD.') from None
    if not values['branch']:raise ValueError('Operating Unit is required; use an active unit code or exact name.')
    if not values['existing_voucher'] and not values['cost_account']:raise ValueError('New Accrual / Cost Asset Ledger is required for a new invoice; choose its genuine cost/asset code.')
    days=values['credit_days'] or str(vendor['credit_days'])
    try:n=Decimal(days)
    except InvalidOperation:raise ValueError('Credit period needs whole calendar days, or blank for the vendor default.') from None
    if not n.is_finite() or n!=n.to_integral_value():raise ValueError('Credit period needs whole calendar days.')
    values['credit_days']=str(ap.credit_days(str(int(n))))
    due=values['due_basis'].casefold().strip();values['due_basis']={'receipt date':'Receipt date','invoice date':'Invoice date','':'Receipt date'}.get(due,values['due_basis'])
    unit=values['branch'];units=foundation.branches(s,True)
    if unit.upper() in units:unit=unit.upper()
    else:
        matches=[code for code,name in units.items() if name.casefold()==unit.casefold()]
        if len(matches)==1:unit=matches[0]
    values['branch']=unit;values['payable']=values['payable'] or '2000';values['reviewed']=True;values['tax_treatment']='No separate GST/TDS; reviewed'
    if not values['basis']:raise ValueError('Accounting Review Basis is required for each invoice; enter the source/accounting/tax review evidence.')
    values['allocations']=[] if values['existing_voucher'] else [dict(account=values['cost_account'],amount=values['amount'])]
    values.pop('cost_account');return values,vendor['name']


def _sheet(raw,filename,sheet):
    if Path(filename).suffix.lower()!='.xlsx':return ''
    if sheet:return sheet
    from zipfile import ZipFile
    import io
    from openpyxl import load_workbook
    if len(raw)>25*1024*1024:raise ValueError('Invoice upload exceeds 25 MB.')
    with ZipFile(io.BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('Expanded workbook exceeds 100 MB.')
    w=load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
    try:
        if 'Invoices' in w.sheetnames:return 'Invoices'
        if len(w.sheetnames)==1:return w.sheetnames[0]
        raise ValueError('Use the template Invoices sheet, or specify an exact worksheet when this workbook has multiple sheets.')
    finally:w.close()


def _validate_rows(s,records,exclude=None):
    probe=copy.deepcopy(s);seen=_known(s,exclude);result=[]
    for source in records:
        r=dict(source_row=source['source_row'],raw=copy.deepcopy(source['raw']),validation='VALID',review='PENDING',reason='',error='')
        counts=(len(probe['vouchers']),len(probe['audit']),len(ap.data(probe)['invoices']))
        try:
            values,name=canonical(s,r['raw']);r.update(values=values,vendor_name=name,date=values['accounting_date'],branch=values['branch'],reference=values['reference'],amount=ap.positive(values['amount']))
            identity=_identity(values)
            if identity in seen:r.update(validation='DUPLICATE',error='Vendor/invoice/fiscal-year identity is already queued in another row/batch.')
            else:
                # Isolated probe only. Undo all of this engine's append-only changes
                # on a failed row; the active book is never mutated by validation.
                created=ap.enter_invoice.__wrapped__(probe,values);ap.check(probe);r.update(due_date=created['due_date'],payment_date=created['payment_date']);seen.add(identity)
        except (ValueError,KeyError,TypeError) as error:
            del probe['vouchers'][counts[0]:];del probe['audit'][counts[1]:];del ap.data(probe)['invoices'][counts[2]:]
            r.update(validation='DUPLICATE' if 'already registered' in str(error) else 'INVALID',error=str(error))
        result.append(r)
    return result


def stage(s,raw,filename,sheet=None):
    core.verify_audit(s);digest=hashlib.sha256(raw).hexdigest()
    if any(q.get('kind')=='ap_bulk' and q['digest']==digest and q['status']!='CANCELLED' for q in s['queue']):raise ValueError('This exact invoice file is already queued; review/revalidate its batch instead of uploading it twice.')
    headers,source,label=bulk_import._read(raw,filename,_sheet(raw,filename,sheet));mapping={};warnings=[]
    for h in headers:
        key=ALIASES.get(ap.norm(h))
        if not key or key in mapping:raise ValueError('Use unique standard invoice template headings. Unknown/duplicate heading: '+h)
        mapping[key]=h
        if ap.norm(h)=='taxpayablesledger':warnings.append('Source heading Tax payables ledger is treated as Trade payables (vendor liability), not a GST/TDS liability. Actual ledger group is validated.')
    if set(FIELDS)-{'existing_voucher'}-set(mapping):raise ValueError('Missing invoice template columns: '+', '.join(key for key in FIELDS[:-1] if key not in mapping))
    records=[];skipped=0
    for number,row in enumerate(source,2):
        values={key:_string(row[headers.index(h)]) if headers.index(h)<len(row) else '' for key,h in mapping.items()};values.setdefault('existing_voucher','')
        extra=[_string(v) for v in row[len(headers):]]
        if any(extra):values['_extra_values']=extra
        if not any(extra) and not any(values.get(k) for k in FIELDS if k not in ('credit_days','due_basis','payable')):skipped+=1;continue
        records.append(dict(source_row=number,raw=values))
    if not records:raise ValueError('No actual invoice rows found. Default-only credit/payable rows are placeholders and do not post.')
    rows=_validate_rows(s,records);q=dict(id=str(uuid.uuid4()),kind='ap_bulk',status='PENDING_REVIEW',filename=Path(filename).name,digest=digest,sheet=label,headers=headers,header_mapping=mapping,rows=rows,warnings=warnings,ignored_placeholders=skipped,format_version=1)
    s['queue'].append(q);core.add_audit(s,'AP_BULK_STAGED',dict(id=q['id'],filename=q['filename'],digest=digest,rows=len(rows),valid=sum(r['validation']=='VALID' for r in rows),ignored_placeholders=skipped));return copy.deepcopy(q)


def review(s,key,indices,approved,reason,confirmed=False):
    q=batch(s,key)
    if q['status']!='PENDING_REVIEW' or type(approved)!=bool or not reason.strip():raise ValueError('Review a pending AP batch and enter an approval/rejection reason.')
    if approved and not confirmed:raise ValueError('Confirm vendor/source/accounting/tax review before approving invoice rows. Rejection does not need that checkbox.')
    if not indices or len(indices)!=len(set(indices)) or any(type(i)!=int or not 0<=i<len(q['rows']) for i in indices):raise ValueError('Select actual invoice rows.')
    if approved and any(q['rows'][i]['validation']!='VALID' for i in indices):raise ValueError('Invalid/duplicate invoices cannot be approved. Reject/correct the source, or fix the master and Revalidate.')
    for i in indices:q['rows'][i].update(review='APPROVED' if approved else 'REJECTED',reason=reason.strip())
    core.add_audit(s,'AP_BULK_REVIEWED',dict(batch=key,indices=indices,approved=approved,reason=reason.strip()))


def revalidate(s,key):
    q=batch(s,key)
    if q['status']!='PENDING_REVIEW':raise ValueError('Only pending batches can be revalidated.')
    rows=_validate_rows(s,q['rows'],key)
    for old,new in zip(q['rows'],rows):
        if old['review']=='REJECTED':new.update(review='REJECTED',reason=old['reason'])
    q['rows']=rows;core.add_audit(s,'AP_BULK_REVALIDATED',dict(batch=key,scope='Previous approvals cleared for fresh source review; explicit rejections retained.'));return copy.deepcopy(q)


def cancel(s,key,reason):
    q=batch(s,key)
    if q['status']!='PENDING_REVIEW' or not reason.strip():raise ValueError('Cancel an unused pending batch with a reason.')
    q['status']='CANCELLED';core.add_audit(s,'AP_BULK_CANCELLED',dict(batch=key,reason=reason.strip()))


def post(s,key):
    core.verify_audit(s);c=copy.deepcopy(s);q=batch(c,key)
    if q['status']!='PENDING_REVIEW':raise ValueError('Only a pending AP batch can post; processed/cancelled files cannot post again.')
    if any(r['review'] not in ('APPROVED','REJECTED') for r in q['rows']):raise ValueError('Approve all valid invoice rows and reject all flagged rows before preview/posting.')
    selected=[r for r in q['rows'] if r['review']=='APPROVED']
    if not selected:raise ValueError('No approved invoice rows to register.')
    other=_known(c,key);entries=[]
    for r in selected:
        values,name=canonical(c,r['raw'])
        if r['validation']!='VALID' or values!=r['values'] or name!=r['vendor_name']:raise ValueError('Vendor/source defaults changed since review. Revalidate the batch and approve fresh values.')
        if _identity(values) in other:raise ValueError('An approved invoice is reserved by another batch. Revalidate and review the duplicate.')
        values['source']=dict(kind='ap_invoice_import',document_id=key,record_id=str(r['source_row']),row_count=1);entries.append(values)
    invoices=ap.enter_invoice_batch(c,entries)
    q=batch(c,key);selected=[r for r in q['rows'] if r['review']=='APPROVED']
    for r,invoice in zip(selected,invoices):r['invoice_id']=invoice['id'];r['voucher']=invoice['voucher'];r['mode']=invoice['mode']
    q['status']='PROCESSED';q['registered_count']=len(invoices);q['new_accrual_count']=sum(r['mode']=='New accrual' for r in selected)
    core.add_audit(c,'AP_BULK_POSTED',dict(id=key,registered=len(invoices),new_accruals=q['new_accrual_count'],linked_existing=len(invoices)-q['new_accrual_count'],rejected=len(q['rows'])-len(invoices)));s.clear();s.update(c)
    result=dict(registered=len(invoices),new_accruals=q['new_accrual_count'],linked_existing=len(invoices)-q['new_accrual_count'])
    linked={r['voucher'] for r in selected if r['mode']=='Linked source'}
    if linked:result['linked_source_journals']=[copy.deepcopy(v) for v in c['vouchers'] if v['id'] in linked]
    return result


def snapshot(s,key):
    q=batch(s,key);dates=[r['date'] for r in q['rows'] if r.get('date')];start=min(dates or ['1900-01-01']);end=max(dates or [start]);p=reports.snapshot(s,'Trial balance',start,end)
    rows=[]
    for r in q['rows']:
        v=r.get('values',{});cost=next((i['account'] for i in v.get('allocations',[])),v.get('existing_voucher',''));name=next((a['name'] for a in s['accounts'] if a['code']==cost),'Existing source' if v.get('existing_voucher') else '')
        rows.append([r['source_row'],r.get('vendor_name',r['raw'].get('vendor_name','')),r.get('reference',r['raw'].get('reference','')),r.get('branch',''),r.get('date',''),r.get('amount',0),v.get('payable',''),cost+' '+name,r['validation'],r['review'],r['error']+' '+r['reason'],r.get('voucher','')])
    p.update(mode='AP bulk invoice review',columns=['Source row','Vendor','Invoice','Unit','Accrual date','Payable INR','AP ledger','Cost ledger / existing source','Validation','Decision','Error / reason','Voucher'],money_columns=[5],rows=rows,controls={},note=q['filename']+' | '+q['status']+' | SHA256 '+q['digest']+'. Upload/review does not post. Approved invoices create the same accrual or existing-source link as Enter invoice; no automatic payment. Rejected rows remain in history.');return p


def template(path,state=None):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(HEADERS)
        return
    if path.suffix.lower()!='.xlsx':raise ValueError('Save the AP invoice template as XLSX or CSV.')
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.workbook.defined_name import DefinedName
    s=state if state is not None else core.empty_state();wb=Workbook();ws=wb.active;ws.title='Invoices';ws.append(list(HEADERS));ws.freeze_panes='C2';ws.auto_filter.ref='A1:N1001'
    for c in ws[1]:c.font=Font(bold=True,color='154C8A');c.fill=PatternFill('solid',fgColor='E8F0FC');c.alignment=Alignment(wrap_text=True,vertical='center')
    ws.row_dimensions[1].height=48
    for i in range(1,15):ws.column_dimensions[get_column_letter(i)].width=28 if i in (1,13,14) else 22
    for row in range(2,1002):
        ws.cell(row,7,'Receipt date');ws.cell(row,11,'2000')
        for col in (3,4,5,8):ws.cell(row,col).number_format='yyyy-mm-dd'
        for col in (2,11,12,14):ws.cell(row,col).number_format='@'
        ws.cell(row,10).number_format='#,##0.00'
    vendors=wb.create_sheet('Vendors');vendors.append(['Vendor ID','Vendor Name','Default credit days','Reference'])
    for v in ap.data(s)['vendors']:
        if v.get('active',True):vendors.append([v['id'],v['name'],v['credit_days'],v['reference']])
    units=wb.create_sheet('Units');units.append(['Code','Unit name'])
    for code,name in foundation.branches(s,True).items():units.append([code,name])
    accounts=wb.create_sheet('Accounts');accounts.append(['Code','Ledger name','Kind','Group'])
    for a in s['accounts']:
        if s['account_details'][a['code']].get('active',True):accounts.append([a['code'],a['name'],a['kind'],s['account_details'][a['code']]['group']])
    for name,sheet,column,col in [('APVendorNames',vendors,'B','A'),('APUnitCodes',units,'A','I'),('APAccountCodes',accounts,'A','L')]:
        wb.defined_names.add(DefinedName(name,attr_text=f"'{sheet.title}'!${column}$2:${column}${max(2,sheet.max_row)}"));dv=DataValidation(type='list',formula1='='+name,allow_blank=True);ws.add_data_validation(dv);dv.add(f'{col}2:{col}1001')
    basis=DataValidation(type='list',formula1='"Receipt date,Invoice date"',allow_blank=True);ws.add_data_validation(basis);basis.add('G2:G1001')
    credit=DataValidation(type='whole',operator='between',formula1=0,formula2=3650,allow_blank=True);credit.error='Use 0–3650 whole calendar days or blank for the vendor default.';credit.showErrorMessage=True;ws.add_data_validation(credit);credit.add('F2:F1001')
    guide=wb.create_sheet('Instructions')
    notes=['AP bulk invoice template v1 — one invoice per row; no sample invoices are preloaded.','Fill the same fields as Enter invoice. The optional existing-source voucher column supports reviewed GST/TDS/CWIP accrual links without reposting.','Use saved vendor names, active unit codes/names, literal values and ISO YYYY-MM-DD or real Excel dates. Add missing vendors to Vendor master before posting.','Blank credit days uses the vendor default at validation; Receipt date is the default credit basis; blank scheduled date uses contractual due; payable defaults to 2000.','Rows containing only default credit/basis/payable cells are ignored placeholders, not invoices. Cost/asset ledger is deliberately blank: select the correct account, e.g. 1100 Medicine inventory.','Trade Payables Ledger is the vendor liability, not tax payable. GST/TDS liability accounts are not accepted as vendor payables.','Accounting Review Basis is required per invoice. New simple accruals need reviewed no-separate-GST/TDS treatment; special sources must be posted correctly first and linked once.','Upload bulk invoices on AP → select file → review errors/duplicates → reject flagged rows → confirm source review → approve valid rows → preview named journals → approve AP action.','Upload/review does not post. Invoices are registered atomically: a failed selected row prevents partial posting. No payment is made by uploading invoices.','Revalidate after master/source corrections; approvals clear for fresh review while explicit rejections remain. A corrected source file should be uploaded as a new revision.','The app checks existing/manual/cancelled invoices and other queued AP batches per vendor/invoice fiscal year. Do not change IDs to bypass a duplicate.','Vendors/Units/Accounts sheets are lookup snapshots from the book when exported locally. The public blank template has no customer vendor data.']
    for text in notes:guide.append([text]);guide.cell(guide.max_row,1).alignment=Alignment(wrap_text=True);guide.row_dimensions[guide.max_row].height=44
    guide.column_dimensions['A'].width=125
    for sheet in (vendors,units,accounts):
        sheet.freeze_panes='A2'
        for col in range(1,sheet.max_column+1):sheet.column_dimensions[get_column_letter(col)].width=34
        for c in sheet[1]:c.font=Font(bold=True)
        for row in sheet.iter_rows():
            for c in row:
                if isinstance(c.value,str):c.data_type='s'
    wb.save(path);wb.close()

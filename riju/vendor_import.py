"""Reviewed, create-only vendor master CSV/XLSX import. Never posts journals."""
import copy
import csv
from decimal import Decimal,InvalidOperation
import hashlib
from pathlib import Path
from . import ap,ap_bulk,bulk_import,core

FIELDS=('name','credit_days','reference','active')
HEADERS=('Vendor Name','Default Credit Period Calendar Days','Vendor Code / Source Reference','Active')
ALIASES={ap.norm(h):key for h,key in zip(HEADERS,FIELDS)}
ALIASES.update({ap.norm(k):k for k in FIELDS})
ALIASES.update({'vendorlegalsourcename':'name','defaultcreditdays':'credit_days','creditperiodcalendardays':'credit_days','optionalvendorcodesourcereference':'reference','vendorreference':'reference'})


def values(raw):
    if raw.get('_extra'):raise ValueError('Extra cells beyond the template headings; correct the source file.')
    if any(str(v).startswith('=') for v in raw.values()):raise ValueError('Use literal vendor fields, not spreadsheet formulas.')
    days=raw.get('credit_days','').strip() or '30'
    try:n=Decimal(days)
    except InvalidOperation:raise ValueError('Credit days must be whole calendar days from 0 to 3650.') from None
    if not n.is_finite() or n!=n.to_integral_value():raise ValueError('Credit days must be whole calendar days from 0 to 3650.')
    days=ap.credit_days(str(int(n)));active=raw.get('active','').strip().casefold() or 'yes'
    if active not in ('yes','no'):raise ValueError('Active must be Yes or No; blank defaults to Yes.')
    return dict(name=raw.get('name','').strip(),credit_days=str(days),reference=raw.get('reference','').strip(),active=active=='yes')


def preview(s,raw,filename):
    core.verify_audit(s)
    sheet=''
    if Path(filename).suffix.lower()=='.xlsx':
        from openpyxl import load_workbook
        from zipfile import ZipFile
        import io
        if len(raw)>25*1024*1024:raise ValueError('Import exceeds 25 MB.')
        with ZipFile(io.BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('Expanded workbook exceeds 100 MB.')
        w=load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
        try:
            if 'Vendors' in w.sheetnames:sheet='Vendors'
            elif len(w.sheetnames)==1:sheet=w.sheetnames[0]
            else:raise ValueError('Use the standard Vendors sheet or a workbook with one worksheet.')
        finally:w.close()
    headers,records,label=bulk_import._read(raw,filename,sheet);mapping={}
    for i,h in enumerate(headers):
        key=ALIASES.get(ap.norm(h))
        if not key or key in mapping:raise ValueError('Use unique standard vendor headings. Unknown/duplicate heading: '+str(h))
        mapping[key]=i
    if set(FIELDS)-set(mapping):raise ValueError('Missing vendor template columns: '+', '.join(k for k in FIELDS if k not in mapping))
    probe=copy.deepcopy(s);rows=[];ignored=0
    for number,row in enumerate(records,2):
        source={k:ap_bulk._string(row[i]) if i<len(row) else '' for k,i in mapping.items()}
        if any(ap_bulk._string(v) for v in row[len(headers):]):source['_extra']=True
        if not source.get('_extra') and not source['name'] and not source['reference']:ignored+=1;continue
        result=dict(source_row=number,raw=source,status='NEW',error='')
        try:
            v=values(source);result['values']=v
            ap.save_vendor.__wrapped__(probe,v)
        except ValueError as error:
            result.update(status='DUPLICATE' if 'already belongs' in str(error) else 'INVALID',error=str(error))
        rows.append(result)
    if not rows:raise ValueError('No vendor rows found. Fill Vendor Name; default-only template rows are ignored.')
    return dict(filename=Path(filename).name,digest=hashlib.sha256(raw).hexdigest(),sheet=label,headers=headers,rows=rows,ignored=ignored)


@ap.atomic
def save_selected(s,plan,indices):
    if not indices or len(set(indices))!=len(indices) or any(type(i)!=int or not 0<=i<len(plan['rows']) for i in indices):raise ValueError('Select one or more new vendor rows.')
    selected=[plan['rows'][i] for i in indices];created=[]
    for row in selected:
        if row['status']!='NEW':raise ValueError('Select only NEW rows. Existing/duplicate vendors are never overwritten; correct invalid rows in the file.')
        v=values(row['raw'])
        if v!=row['values']:raise ValueError('Source values changed after review; upload and review again.')
        created.append(ap.save_vendor.__wrapped__(s,v))
    core.add_audit(s,'AP_VENDOR_BULK_IMPORTED',dict(filename=plan['filename'],sha256=plan['digest'],sheet=plan['sheet'],source_rows=[r['source_row'] for r in selected],vendor_ids=[v['id'] for v in created],count=len(created)))
    return created


def template(path):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(HEADERS)
        return
    if path.suffix.lower()!='.xlsx':raise ValueError('Save the vendor template as XLSX or CSV.')
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    w=Workbook();ws=w.active;ws.title='Vendors';ws.append(HEADERS)
    for c in ws[1]:c.font=Font(bold=True,color='154C8A');c.fill=PatternFill('solid',fgColor='E8F0FC');c.alignment=Alignment(wrap_text=True)
    ws.row_dimensions[1].height=34
    for col,width in [('A',42),('B',32),('C',44),('D',18)]:ws.column_dimensions[col].width=width
    for row in range(2,1002):ws.cell(row,2,30);ws.cell(row,4,'Yes');ws.cell(row,3).number_format='@'
    ws.freeze_panes='A2';ws.auto_filter.ref='A1:D1001'
    dv=DataValidation(type='whole',operator='between',formula1=0,formula2=3650);dv.errorTitle='Whole calendar days';dv.error='Use 0 to 3650 whole days.';dv.showErrorMessage=True;dv.errorStyle='stop';ws.add_data_validation(dv);dv.add('B2:B1001')
    dv=DataValidation(type='list',formula1='"Yes,No"');dv.showErrorMessage=True;dv.errorStyle='stop';ws.add_data_validation(dv);dv.add('D2:D1001')
    help=w.create_sheet('Instructions');help.append(['Field / step','Instruction'])
    for row in [('Vendor Name','Required. Use the exact legal/source spelling used on invoices. Do not add spelling variants of an existing vendor.'),('Default Credit Period Calendar Days','Whole days 0–3650. Blank defaults to 30; 0 means immediate terms.'),('Vendor Code / Source Reference','Optional text. Format as text before entry to preserve leading zeroes.'),('Active','Yes or No. Blank defaults to Yes. No creates an inactive master, not eligible for new invoices.'),('Upload','Vendor master > Upload bulk vendors. CSV UTF-8 or XLSX; use Vendors worksheet. Literal values only, no formulas.'),('Review','NEW may be selected/saved. DUPLICATE includes existing names, historical aliases and earlier rows in this file. INVALID shows its correction reason. No changes happen until Save selected new vendors.'),('Existing masters','Create-only import: never overwrites existing names, credit terms, references or active status. Use Edit selected vendor for updates.'),('After save','Saved vendors appear immediately in Vendor master and invoice pickers. No invoices, balances or journals are created.'),('Partial files','Select all new vendors or select individual NEW rows. Flagged rows remain unsaved; correct the source and upload again. Already-saved vendors then appear as duplicates.'),('Privacy','Blank public template contains no client masters. Default-only rows are ignored.')]:help.append(row)
    help.column_dimensions['A'].width=37;help.column_dimensions['B'].width=110
    for row in help:
        for c in row:c.alignment=Alignment(wrap_text=True,vertical='top')
        help.row_dimensions[row[0].row].height=42
    w.save(path);w.close()

"""Reviewed domestic GST journals and offline 2B working reconciliation."""
import copy
import csv
from decimal import Decimal,ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import uuid
from . import core,foundation,tax

INPUT=('1200','1210','1220');OUTPUT=('2200','2210','2220')


def paise(value):
    text=tax.decimal_text(value)
    amount=int(Decimal(text)*100)
    if amount<=0:raise ValueError('Enter a positive INR amount.')
    return amount


def split(rule,amount,inclusive,intra):
    rate=Decimal(rule['rate']);given=paise(amount)
    base=int((Decimal(given)*100/(100+rate)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if inclusive else given
    total=given if inclusive else base+int((Decimal(base)*rate/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    value=total-base
    if base<=0:raise ValueError('The taxable/base amount must be positive after rounding.')
    return dict(base=base,cgst=value//2 if intra else 0,sgst=value-value//2 if intra else 0,igst=0 if intra else value,total=total)


def _gstin(value,optional=False):
    result=foundation.optional_registration({'gstin':value})['gstin']
    if not result and not optional:raise ValueError('Enter the GST registration used for this transaction.')
    return result


def plan(state,values):
    on=tax.day(values.get('date',''));branch=values.get('branch');kind=values.get('kind')
    if branch not in foundation.branches(state,True) or kind not in ('Sale','Purchase'):raise ValueError('Select an active branch and Sale/Purchase.')
    if type(values.get('inclusive',False))!=bool:raise ValueError('Choose inclusive or exclusive explicitly.')
    rule=tax.resolve_rule(state,values.get('rule_key',''),on)
    if rule['family']!='GST' or not rule['reviewed']:raise ValueError('Select a reviewed GST rule effective on the invoice date.')
    if rule['treatment']=='Zero rated':raise ValueError('Export/SEZ zero-rated documents require a separately reviewed workflow. Use a manual reviewed journal for now.')
    if rule['party_category']!='Any':raise ValueError('Party-specific applicability requires a separate reviewed workflow; use a general GST rule only when verified appropriate.')
    origin=_gstin(values.get('registration',''));unit=state['branches'][branch]
    if unit.get('gstin') and unit['gstin']!=origin:raise ValueError('The GSTIN differs from the configured branch registration.')
    if unit.get('state_code') and unit['state_code']!=origin[:2]:raise ValueError('The supplying/receiving GST registration state differs from this branch.')
    configured=state['settings'].get('registration',{}).get('gstin','')
    if not unit.get('gstin') and configured and configured!=origin:raise ValueError('Configure the branch GSTIN before using a registration different from the entity GSTIN.')
    pos=str(values.get('place_of_supply','')).strip()
    if not re.fullmatch(r'\d{2}',pos) or not 1<=int(pos)<=38:raise ValueError('Enter the reviewed Indian place-of-supply state code.')
    supplier=_gstin(values.get('counterparty_gstin',''),True);reference=str(values.get('reference','')).strip()
    if not reference:raise ValueError('Enter the invoice/reference number.')
    if supplier==origin:raise ValueError('Self-invoices and transfers within the same GST registration require separate review.')
    account=values.get('account');counter=values.get('counter_account');accounts={a['code']:a for a in state['accounts']}
    if account not in accounts or counter not in accounts or account==counter:raise ValueError('Select distinct valid revenue/cost and payment/control ledgers.')
    if kind=='Sale' and accounts[account]['kind']!='Revenue':raise ValueError('Sales require a revenue ledger.')
    if kind=='Purchase' and (accounts[account]['kind'] not in ('Expense','Asset') or account in INPUT or state['account_details'][account]['group'] in ('Cash and bank','Payment clearing','Patient control')):raise ValueError('Select a genuine purchase cost/PPE/inventory ledger.')
    if counter in INPUT+OUTPUT or accounts[counter]['kind'] not in ('Asset','Liability') or counter in state.get('foreign_accounts',{}):raise ValueError('Select an INR cash/bank or suitable receivable/payable control ledger.')
    counter_group=state['account_details'][counter]['group']
    allowed=('Cash and bank','Payment clearing','Patient control','Other assets') if kind=='Sale' else ('Cash and bank','Payment clearing','Trade payables','Other liabilities')
    if counter_group not in allowed:raise ValueError('Use an appropriate INR payment, receivable or payable control ledger.')
    if rule['ledger_codes'] and account not in rule['ledger_codes']:raise ValueError('The revenue/cost account is not linked to this rule.')
    itc=values.get('itc','Not applicable')
    if kind=='Purchase' and itc not in ('Eligible','Ineligible'):raise ValueError('Explicitly review purchase ITC as eligible or ineligible.')
    if kind=='Sale' and itc!='Not applicable':raise ValueError('ITC choice applies only to purchases.')
    if kind=='Purchase' and itc=='Eligible' and (not supplier or rule['treatment']!='Taxable'):raise ValueError('Eligible ITC requires a supplier GSTIN and a taxable purchase; no eligibility is inferred.')
    if kind=='Purchase' and rule['treatment']=='Taxable' and not supplier:raise ValueError('A taxable purchase needs the supplier GSTIN from its tax invoice. RCM/unregistered-supplier cases require separate review.')
    intra=(supplier[:2]==pos) if kind=='Purchase' and supplier else origin[:2]==pos
    if kind=='Purchase' and itc=='Eligible' and intra and pos!=origin[:2]:raise ValueError('Intra-state tax charged outside this registration state needs separate eligibility review; select ineligible or correct the invoice.')
    totals=split(rule,values.get('amount',''),values.get('inclusive',False),intra)
    narration=str(values.get('narration','')).strip()
    if not narration:raise ValueError('Enter the transaction narration.')
    if any(d['kind']==kind and d['registration']==origin and d['counterparty_gstin']==supplier and re.sub(r'[^A-Z0-9]','',d['reference'].upper())==re.sub(r'[^A-Z0-9]','',reference.upper()) and core.financial_year(d['date'])==core.financial_year(on) for d in state.get('gst_documents',[])):raise ValueError('This invoice reference already exists for that registration/counterparty/year. Use a new explicit correction reference after reversal.')
    if kind=='Purchase' and supplier and any(r['stage']=='Purchase' and r['registration']==origin and r.get('supplier_gstin')==supplier and _reference(r['reference'])==_reference(reference) and core.financial_year(r['date'])==core.financial_year(on) for r in state.get('gst_rcm_records',[])):raise ValueError('This supplier invoice is already recorded in the RCM workflow.')
    lines=[]
    def add(code,amount,debit):
        if amount:lines.append(dict(account=code,branch=branch,debit=amount if debit else 0,credit=0 if debit else amount))
    if kind=='Sale':
        add(counter,totals['total'],True);add(account,totals['base'],False)
        for code,key in zip(OUTPUT,('cgst','sgst','igst')):add(code,totals[key],False)
    else:
        eligible=itc=='Eligible';add(account,totals['base'] if eligible else totals['total'],True)
        if eligible:
            for code,key in zip(INPUT,('cgst','sgst','igst')):add(code,totals[key],True)
        add(counter,totals['total'],False)
    return dict(id=str(uuid.uuid4()),kind=kind,date=on,branch=branch,registration=origin,place_of_supply=pos,counterparty_gstin=supplier,reference=reference,rule=rule,account=account,counter_account=counter,inclusive=values.get('inclusive',False),itc=itc,narration=narration,totals=totals,lines=lines,rounding='Half-up to paise; an odd split paise is allocated to SGST. Review against the actual invoice before posting.')


def post(state,values):
    if values.get('confirmed') is not True:raise ValueError('Review the invoice, place of supply, tax rounding and ITC eligibility before approval.')
    candidate=copy.deepcopy(state);doc=plan(candidate,values)
    v=core.post(candidate,doc['date'],doc['narration'],doc['lines'],metadata={'type':'Receipt' if doc['kind']=='Sale' else 'Payment','reference':doc['reference']})
    doc['voucher_id']=v['id'];candidate['gst_documents'].append(doc);core.add_audit(candidate,'GST_DOCUMENT_POSTED',copy.deepcopy(doc))
    state.clear();state.update(candidate);return copy.deepcopy(doc)


def _roots(state):
    by_id={v['id']:v for v in state['vouchers']};result={}
    for v in state['vouchers']:
        current=v;sign=1;seen=set()
        while current.get('reverses'):
            if current['id'] in seen or current['reverses'] not in by_id:raise ValueError('Invalid journal reversal chain.')
            seen.add(current['id']);current=by_id[current['reverses']];sign=-sign
        result[v['id']]=(current['id'],sign)
    return result


def register(state,start,through,branch='ALL'):
    tax.day(start);tax.day(through)
    if start>through:raise ValueError('Start date follows end date.')
    roots=_roots(state);documents={d['voucher_id']:d for d in state.get('gst_documents',[])};result=[]
    for v in state['vouchers']:
        root,sign=roots[v['id']];doc=documents.get(root)
        if not doc or not start<=v['date']<=through or branch!='ALL' and doc['branch']!=branch:continue
        sign*=doc.get('document_sign',1)
        result.append(dict(copy.deepcopy(doc),movement_voucher=v['id'],movement_date=v['date'],sign=sign,totals={k:n*sign for k,n in doc['totals'].items()}))
    return result


def summary(state,start,through,branch='ALL'):
    rows=register(state,start,through,branch);totals={k:0 for k in ('sales_base','purchases_base','ineligible_tax','input_cgst','input_sgst','input_igst','output_cgst','output_sgst','output_igst')}
    classified={code:0 for code in INPUT+OUTPUT};turnover={}
    for d in rows:
        t=d['totals'];sale=d['kind']=='Sale';totals['sales_base' if sale else 'purchases_base']+=t['base']
        key=(d['registration'],d['kind'],d['rule']['treatment']);turnover[key]=turnover.get(key,0)+t['base']
        if not sale and d['itc']=='Ineligible':totals['ineligible_tax']+=t['cgst']+t['sgst']+t['igst'];continue
        for code,part in zip(OUTPUT if sale else INPUT,('cgst','sgst','igst')):
            totals[('output_' if sale else 'input_')+part]+=t[part];classified[code]+=t[part]
    from . import rcm
    for record in rcm.movements(state,start,through,branch):
        if record['stage']=='Claim':
            for code,part in zip(INPUT,('cgst','sgst','igst')):
                amount=record['amounts'][part]*record['sign'];totals['input_'+part]+=amount;classified[code]+=amount
    actual={code:0 for code in INPUT+OUTPUT};opening={code:0 for code in actual}
    for v in state['vouchers']:
        for l in v['lines']:
            if l['account'] not in actual or branch!='ALL' and l['branch']!=branch:continue
            amount=(l['debit']-l['credit'])*(1 if l['account'] in INPUT else -1)
            if v['date']<start or v.get('opening') and v['date']<=through:opening[l['account']]+=amount
            elif start<=v['date']<=through:actual[l['account']]+=amount
    return dict(entity=state['settings']['entity'],start=start,through=through,branch=branch,totals=totals,opening_balances=opening,closing_balances={k:opening[k]+actual[k] for k in actual},ledger_movements=actual,unclassified={k:actual[k]-classified[k] for k in actual},net_movement=sum(actual[k] for k in OUTPUT)-sum(actual[k] for k in INPUT),turnover=[dict(registration=k[0],kind=k[1],treatment=k[2],base=v) for k,v in sorted(turnover.items())],documents=rows,scope='Working GST movements; invoice bases exclude RCM purchases, input totals include separately reviewed RCM claims. Not a return or tax-payment computation. Input credit remains subject to reviewed legal eligibility and 2B checks. Separate registrations must be reviewed separately; no automatic ITC utilisation/offset is performed.')


def _document_type(value):
    text=str(value or 'Invoice').strip().casefold()
    types={'invoice':'Invoice','credit note':'Credit note','debit note':'Debit note'}
    if text not in types:raise ValueError('2B document_type must be Invoice, Credit note or Debit note.')
    return types[text]


def _reference(value):return re.sub('[^A-Z0-9]','',str(value).upper())


def _net_documents(state):
    net={}
    for root,sign in _roots(state).values():net[root]=net.get(root,0)+sign
    return net


def import_2b(state,raw,filename,registration,period):
    registration=_gstin(registration)
    if not re.fullmatch(r'\d{4}-\d{2}',period):raise ValueError('Enter the 2B period as YYYY-MM.')
    tax.day(period+'-01');digest=hashlib.sha256(raw).hexdigest()
    if any(x.get('status','OPEN')!='VOID' and x['digest']==digest and x['registration']==registration and x['period']==period for x in state['gst_2b_imports']):raise ValueError('This 2B file is already imported for this registration/period.')
    if len(raw)>20*1024*1024:raise ValueError('2B import must be at most 20 MB.')
    suffix=Path(filename).suffix.lower()
    if suffix=='.csv':rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    elif suffix=='.xlsx':
        from openpyxl import load_workbook
        w=load_workbook(io.BytesIO(raw),read_only=True,data_only=False)
        try:
            if len(w.worksheets)!=1:raise ValueError('Use a single-sheet normalized 2B workbook.')
            records=iter(w.active.values);headers=next(records,());rows=[dict(zip(headers,r)) for r in records if any(v is not None for v in r)]
        finally:w.close()
    else:raise ValueError('Use normalized CSV or XLSX with the supplied 2B template.')
    required={'supplier_gstin','invoice','date','taxable','cgst','sgst','igst','itc_available'}
    if not rows or len(rows)>50000 or any(not required.issubset(r) for r in rows):raise ValueError('2B needs 1–50,000 invoice rows with template headers.')
    clean=[];seen=set();existing={(x['registration'],x['period'],r['supplier_gstin'],r.get('document_type','Invoice'),r['invoice'].upper(),r['date']) for x in state['gst_2b_imports'] if x.get('status','OPEN')!='VOID' for r in x['rows']}
    for row in rows:
        if any(str(row.get(key) or '').strip().casefold() not in ('','n','no','false','0') for key in ('reverse_charge','rcm')):raise ValueError('RCM source sections require separate reconciliation; the normalized 2B matcher covers forward-charge documents only.')
        supplier=_gstin(row['supplier_gstin']);reference=str(row['invoice'] or '').strip();on=tax.day(str(row['date'])[:10]);available=str(row['itc_available'] or '').strip().upper()
        if not reference or available not in ('Y','N'):raise ValueError('Each 2B row needs an invoice and ITC availability Y or N.')
        document_type=_document_type(row.get('document_type'))
        original_reference=str(row.get('original_invoice') or '').strip();original_date=str(row.get('original_date') or '')[:10]
        if document_type!='Invoice':
            if not original_reference:raise ValueError('A 2B note needs its original invoice reference for explicit linkage.')
            tax.day(original_date)
            if original_date>on:raise ValueError('The original invoice date cannot follow its note date.')
        elif original_reference or original_date:raise ValueError('Original-invoice fields belong on credit/debit notes only.')
        amounts={key:int(Decimal(tax.decimal_text(row[key] or '0'))*100) for key in ('taxable','cgst','sgst','igst')}
        if amounts['taxable']<=0 or amounts['igst'] and (amounts['cgst'] or amounts['sgst']):raise ValueError('Use positive absolute document amounts with a consistent tax split. Document type controls the sign; RCM/imports require separate review.')
        identity=(registration,period,supplier,document_type,reference.upper(),on)
        if identity in seen or identity in existing:raise ValueError('Duplicate supplier invoice/date in the selected 2B period.')
        seen.add(identity);clean.append(dict(id=str(uuid.uuid4()),supplier_gstin=supplier,invoice=reference,date=on,document_type=document_type,original_invoice=original_reference,original_date=original_date,itc_available=available,**amounts))
    item=dict(id=str(uuid.uuid4()),status='OPEN',registration=registration,period=period,filename=Path(filename).name,digest=digest,rows=clean)
    state['gst_2b_imports'].append(item);core.add_audit(state,'GST_2B_IMPORTED',copy.deepcopy(item));return copy.deepcopy(item)


def candidates_2b(state,import_id):
    item=next(x for x in state['gst_2b_imports'] if x['id']==import_id);out=[]
    used_docs={m['document_id'] for m in state['gst_2b_matches'] if m.get('active',True)}
    used_rows={m['row_id'] for m in state['gst_2b_matches'] if m.get('active',True)}
    net=_net_documents(state)
    notes={}
    for d in state['gst_documents']:
        if d.get('original_document_id') and net.get(d['voucher_id'],0):notes.setdefault(d['original_document_id'],[]).append(d)
    uncovered={original for original,docs in notes.items() if any(d['id'] not in used_docs for d in docs)}
    by_id={d['id']:d for d in state['gst_documents']}
    for row in item['rows']:
        own={m['document_id'] for m in state['gst_2b_matches'] if m['row_id']==row['id'] and m.get('active',True)};matches=[]
        row_type=row.get('document_type','Invoice')
        for doc in state['gst_documents']:
            if doc['kind']!='Purchase' or doc['registration']!=item['registration'] or doc.get('document_type','Invoice')!=row_type:continue
            if doc['counterparty_gstin']!=row['supplier_gstin'] or _reference(doc['reference'])!=_reference(row['invoice']):continue
            exact=doc['date']==row['date'] and all(doc['totals'][k]==row[k] for k in ('cgst','sgst','igst')) and doc['totals']['base']==row['taxable']
            original=by_id.get(doc.get('original_document_id'))
            link_ok=row_type=='Invoice' or original and _reference(original['reference'])==_reference(row.get('original_invoice','')) and original['date']==row.get('original_date')
            status=('Reversed - review' if not net.get(doc['voucher_id'],0) else
                'Adjusted by GST note - review' if doc['id'] in uncovered else
                'Already linked elsewhere' if doc['id'] in used_docs and doc['id'] not in own else
                'Original invoice mismatch' if not link_ok else 'Exact' if exact else 'Date/amount mismatch')
            matches.append(dict(document_id=doc['id'],voucher_id=doc['voucher_id'],document_type=row_type,original_invoice=original['reference'] if original else '',status=status,itc=doc['itc']))
        status='Review candidates' if matches else 'Missing in books'
        if row['id'] in used_rows:
            linked=[c for c in matches if c['document_id'] in own]
            status=('Linked document missing - review' if not linked else
                'Linked voucher reversed - undo/review' if any(c['status']=='Reversed - review' for c in linked) else
                'Linked invoice adjusted - review' if any(c['status']=='Adjusted by GST note - review' for c in linked) else
                'Linked document changed - review' if any(c['status']!='Exact' for c in linked) else 'Matched')
        out.append(dict(row=copy.deepcopy(row),status=status,candidates=matches))
    return out


def match_2b(state,import_id,row_id,document_id):
    if next(x for x in state['gst_2b_imports'] if x['id']==import_id).get('status')=='VOID':raise ValueError('This 2B import was voided.')
    candidate=next(x for x in candidates_2b(state,import_id) if x['row']['id']==row_id)
    chosen=next((x for x in candidate['candidates'] if x['document_id']==document_id),None)
    if any(m['row_id']==row_id and m.get('active',True) for m in state['gst_2b_matches']) or not chosen or chosen['status']!='Exact':raise ValueError('Only reviewed exact invoice/date/tax/base matches can be linked. Resolve mismatches first.')
    record=dict(id=str(uuid.uuid4()),import_id=import_id,row_id=row_id,document_id=document_id,active=True,document_type=candidate['row'].get('document_type','Invoice'),itc_available=candidate['row']['itc_available'])
    state['gst_2b_matches'].append(record);core.add_audit(state,'GST_2B_MATCHED',copy.deepcopy(record));return record


def unmatch_2b(state,match_id,reason):
    if not reason.strip():raise ValueError('Enter an undo reason.')
    m=next(x for x in state['gst_2b_matches'] if x['id']==match_id)
    if not m.get('active',True):raise ValueError('This 2B match is already undone.')
    m['active']=False;core.add_audit(state,'GST_2B_UNMATCHED',dict(copy.deepcopy(m),reason=reason))


def export_report(report,path):Path(path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


def review_2b(state,import_id):
    item=next(x for x in state['gst_2b_imports'] if x['id']==import_id);rows=candidates_2b(state,import_id)
    key=lambda d,supplier,ref,on:(d,supplier,_reference(ref),on)
    keys={key(r.get('document_type','Invoice'),r['supplier_gstin'],r['invoice'],r['date']) for r in item['rows']}
    net=_net_documents(state)
    missing=[copy.deepcopy(d) for d in state['gst_documents'] if d['kind']=='Purchase' and d['registration']==item['registration'] and d['date'].startswith(item['period']) and net.get(d['voucher_id'],0) and key(d.get('document_type','Invoice'),d['counterparty_gstin'],d['reference'],d['date']) not in keys]
    totals={k:0 for k in ('taxable','cgst','sgst','igst')};linked=copy.deepcopy(totals);unavailable=copy.deepcopy(totals)
    for entry in rows:
        row=entry['row'];sign=-1 if row.get('document_type')=='Credit note' else 1
        for k in totals:
            totals[k]+=row[k]*sign
            if entry['status']=='Matched':linked[k]+=row[k]*sign
            if row['itc_available']=='N':unavailable[k]+=row[k]*sign
    return dict(registration=item['registration'],period=item['period'],filename=item['filename'],digest=item['digest'],status=item.get('status','OPEN'),rows=rows,book_documents_without_2b=missing,book_invoices_without_2b=[d for d in missing if not d.get('original_document_id')],statement_signed_totals=totals,matched_signed_totals=linked,unavailable_signed_totals=unavailable,scope='Signed source document amounts: credit notes negative; invoices/debit notes positive. Missing-book checks cover this statement; missing-2B checks cover book documents dated in its period. Other periods and legal ITC treatment need separate review; links are not claims.')


def export_csv(report,path):
    def safe(value):
        text=str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
    def number(n):return format(Decimal(n)/100,'.2f')
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['Entity',safe(report['entity'])]);writer.writerow(['Period',report['start'],report['through'],'Branch',safe(report['branch'])]);writer.writerow([report['scope']])
        writer.writerow(['Ledger','Opening signed INR','Movement signed INR','Closing signed INR','Unclassified/manual movement INR'])
        for code in INPUT+OUTPUT:writer.writerow([code,number(report['opening_balances'][code]),number(report['ledger_movements'][code]),number(report['closing_balances'][code]),number(report['unclassified'][code])])
        writer.writerow([]);writer.writerow(['Voucher','Movement date','Invoice date','Kind','Document type','Original invoice','Registration','Counterparty GSTIN','Invoice','Treatment','Rule version','ITC','Base INR','CGST INR','SGST INR','IGST INR','Total INR'])
        for d in report['documents']:
            writer.writerow([safe(x) for x in (d['movement_voucher'],d['movement_date'],d['date'],d['kind'],d.get('document_type','Invoice'),d.get('original_reference',''),d['registration'],d['counterparty_gstin'],d['reference'],d['rule']['treatment'],d['rule']['id'],d['itc'])]+[number(d['totals'][k]) for k in ('base','cgst','sgst','igst','total')])


def void_2b(state,import_id,reason):
    if not reason.strip():raise ValueError('Enter a cancellation reason.')
    item=next(x for x in state['gst_2b_imports'] if x['id']==import_id)
    if item.get('status')=='VOID':raise ValueError('This 2B import was already voided.')
    if any(m['import_id']==import_id and m.get('active',True) for m in state['gst_2b_matches']):raise ValueError('Undo all active links before cancelling this import.')
    item['status']='VOID';item['void_reason']=reason;core.add_audit(state,'GST_2B_VOIDED',{'id':import_id,'reason':reason})


def _family_events(state,original_id):
    roots=_roots(state);family={d['voucher_id']:d for d in state['gst_documents'] if d['id']==original_id or d.get('original_document_id')==original_id};events=[]
    for v in state['vouchers']:
        root,sign=roots[v['id']];d=family.get(root)
        if d:events.append((v['date'],{k:n*sign*d.get('document_sign',1) for k,n in d['totals'].items()}))
    return events


def _check_family(state,original_id,extra=None,through=None,extra_original_delta=0,extra_note=None):
    events=_family_events(state,original_id)
    if extra:events.append(extra)
    days={}
    for on,totals in events:
        if through and on>through:continue
        values=days.setdefault(on,{k:0 for k in ('base','cgst','sgst','igst','total')})
        for k,n in totals.items():values[k]+=n
    original=next(d for d in state['gst_documents'] if d['id']==original_id)
    roots=_roots(state);original_days={}
    for v in state['vouchers']:
        root,sign=roots[v['id']]
        if root==original['voucher_id']:original_days[v['date']]=original_days.get(v['date'],0)+sign
    if extra and extra_original_delta:original_days[extra[0]]=original_days.get(extra[0],0)+extra_original_delta
    note_roots={d['voucher_id'] for d in state['gst_documents'] if d.get('original_document_id')==original_id};note_days={}
    for v in state['vouchers']:
        root,sign=roots[v['id']]
        if root in note_roots:
            bucket=note_days.setdefault(v['date'],{});bucket[root]=bucket.get(root,0)+sign
    if extra and extra_note:
        bucket=note_days.setdefault(extra[0],{});bucket[extra_note[0]]=bucket.get(extra_note[0],0)+extra_note[1]
    original_net=0;active_notes={}
    balance={k:0 for k in ('base','cgst','sgst','igst','total')}
    for on,values in sorted(days.items()):
        original_net+=original_days.get(on,0)
        for key,n in note_days.get(on,{}).items():active_notes[key]=active_notes.get(key,0)+n
        if original_net!=1 and any(active_notes.values()):raise ValueError('Reverse all dependent notes before cancelling the original invoice, even when their amounts offset.')
        for k,n in values.items():balance[k]+=n
        if original_net!=1 and any(balance.values()):raise ValueError('Active notes cannot outlive a cancelled original invoice. Reverse dependent notes first.')
        if any(n<0 for n in balance.values()):raise ValueError('This correction would over-credit the invoice or its tax components on '+on+'. Review later notes and reversals first.')
    return balance


def plan_note(state,values):
    original=next((d for d in state['gst_documents'] if d['id']==values.get('original_document_id')),None)
    if original is None or original.get('original_document_id'):raise ValueError('Select an original GST invoice; notes must link directly to it.')
    on=tax.day(values.get('date',''));note_type=values.get('document_type')
    if on<original['date'] or note_type not in ('Credit note','Debit note'):raise ValueError('Choose a credit/debit note dated on or after the original invoice.')
    roots=_roots(state);original_net=sum(sign for v in state['vouchers'] if v['date']<=on for root,sign in [roots[v['id']]] if root==original['voucher_id'])
    if original_net!=1:raise ValueError('The original invoice is reversed on the note date; restore or replace it before adding a note.')
    reference=str(values.get('reference','')).strip();narration=str(values.get('narration','')).strip();counter=values.get('counter_account','')
    if not reference or not narration:raise ValueError('Enter a unique note reference and a reason/narration.')
    normalize=lambda x:re.sub('[^A-Z0-9]','',x.upper())
    if any(d['registration']==original['registration'] and d['counterparty_gstin']==original['counterparty_gstin'] and d['kind']==original['kind'] and normalize(d['reference'])==normalize(reference) and core.financial_year(d['date'])==core.financial_year(on) for d in state['gst_documents']):raise ValueError('This document reference already exists in that registration/counterparty/year.')
    if counter not in {a['code'] for a in state['accounts']} or counter in INPUT+OUTPUT or counter==original['account'] or counter in state.get('foreign_accounts',{}):raise ValueError('Select a valid INR refund/receivable/payable control ledger.')
    group=state['account_details'][counter]['group']
    if group not in ('Cash and bank','Payment clearing','Patient control','Trade payables','Patient advances','Other assets','Other liabilities'):raise ValueError('Select a genuine refund or balance-adjustment control ledger.')
    totals=split(original['rule'],values.get('amount',''),False,original['totals']['igst']==0)
    sign=-1 if note_type=='Credit note' else 1
    if sign<0:
        available=_check_family(state,original['id'],through=on)
        if totals['base']==available['base']:
            totals=copy.deepcopy(available)  # Release exact remaining tax paise on a full credit.
        if totals['base']>available['base']:raise ValueError('Credit exceeds the invoice balance after existing notes/reversals.')
    _check_family(state,original['id'],(on,{k:n*sign for k,n in totals.items()}),extra_note=('proposed-note',1))
    lines=[]
    def add(account,amount,debit):
        if amount:lines.append(dict(account=account,branch=original['branch'],debit=amount if debit else 0,credit=0 if debit else amount))
    sale=original['kind']=='Sale';eligible=original['itc']=='Eligible'
    add(original['account'],totals['base'] if sale or eligible else totals['total'],(not sale) if sign>0 else sale)
    if sale or eligible:
        for code,key in zip(OUTPUT if sale else INPUT,('cgst','sgst','igst')):add(code,totals[key],(not sale) if sign>0 else sale)
    add(counter,totals['total'],sale if sign>0 else not sale)
    result=copy.deepcopy(original);result.update(id=str(uuid.uuid4()),original_document_id=original['id'],original_voucher_id=original['voucher_id'],original_reference=original['reference'],document_type=note_type,document_sign=sign,date=on,reference=reference,counter_account=counter,narration=narration,totals=totals,lines=lines,inclusive=False,rounding='Original rate/treatment retained. Full credit releases exact remaining tax paise; compare with the actual note. GST time-limit, commercial-only adjustments and return eligibility require separate review.')
    result.pop('voucher_id',None);return result


def post_note(state,values):
    if values.get('confirmed') is not True:raise ValueError('Review the note, original invoice, refund/control ledger and tax treatment before approval.')
    candidate=copy.deepcopy(state);note=plan_note(candidate,values)
    voucher=core.post(candidate,note['date'],note['narration'],note['lines'],metadata={'type':'Adjustment','reference':note['reference']})
    note['voucher_id']=voucher['id'];candidate['gst_documents'].append(note);core.add_audit(candidate,'GST_NOTE_POSTED',copy.deepcopy(note))
    state.clear();state.update(candidate);return copy.deepcopy(note)


def validate_reversal(state,voucher_id,on):
    roots=_roots(state)
    if voucher_id not in roots:return
    root,sign=roots[voucher_id]
    doc=next((d for d in state.get('gst_documents',[]) if d['voucher_id']==root),None)
    if doc:
        family=doc.get('original_document_id',doc['id'])
        _check_family(state,family,(on,{k:-sign*doc.get('document_sign',1)*n for k,n in doc['totals'].items()}),extra_original_delta=-sign if not doc.get('original_document_id') else 0,extra_note=(root,-sign) if doc.get('original_document_id') else None)


def export_2b_csv(report,path):
    def safe(value):
        text=str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
    def number(n):return format(Decimal(n)/100,'.2f')
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['Registration',report['registration'],'Period',report['period'],'Import status',report['status']]);writer.writerow(['Source',safe(report['filename']),'SHA-256',report['digest']]);writer.writerow([report['scope']])
        writer.writerow(['Signed totals INR','Taxable','CGST','SGST','IGST'])
        for key,label in [('statement_signed_totals','Source documents'),('matched_signed_totals','Matched documents'),('unavailable_signed_totals','Source availability N')]:writer.writerow([label]+[number(report[key][k]) for k in ('taxable','cgst','sgst','igst')])
        writer.writerow([]);writer.writerow(['Supplier GSTIN','Document type','Document reference','Date','Original invoice','Original date','Signed taxable INR','Signed CGST INR','Signed SGST INR','Signed IGST INR','Source ITC available','Review status','Book candidate / reason'])
        for entry in report['rows']:
            r=entry['row'];sign=-1 if r.get('document_type')=='Credit note' else 1
            writer.writerow([safe(x) for x in (r['supplier_gstin'],r.get('document_type','Invoice'),r['invoice'],r['date'],r.get('original_invoice',''),r.get('original_date',''))]+[number(r[k]*sign) for k in ('taxable','cgst','sgst','igst')]+[r['itc_available'],safe(entry['status']),safe('; '.join(c['voucher_id']+' / '+c['status'] for c in entry['candidates']))])
        writer.writerow([]);writer.writerow(['Book documents absent from imported statement','Type','Reference','Date','Supplier','Signed base INR','Signed CGST INR','Signed SGST INR','Signed IGST INR'])
        for d in report['book_documents_without_2b']:writer.writerow([safe(x) for x in (d['voucher_id'],d.get('document_type','Invoice'),d['reference'],d['date'],d['counterparty_gstin'])]+[number(d['totals'][k]*d.get('document_sign',1)) for k in ('base','cgst','sgst','igst')])

"""Strict offline GSTR-2B JSON b2b/cdnr adapter and separate RCM matching.

Unsupported nonempty sections/cess/ambiguous note parents require source review;
no section is silently ignored or converted into an ITC claim.
"""
import copy
import csv
from datetime import datetime
import hashlib
import io
import json
import uuid
from . import core,gst,tax,rcm,fixed_assets as fa


def normalize(raw,registration,period,original_links=None):
    if len(raw)>20*1024*1024:raise ValueError('Portal JSON exceeds 20 MB.')
    original_links=original_links or {};payload=json.loads(raw);data=payload.get('data',payload)
    if data.get('gstin')!=registration or data.get('rtnprd')!=period[5:7]+period[:4]:raise ValueError('Portal GSTIN/return period differs from the selected registration/period.')
    sections=data.get('docdata')
    if not isinstance(sections,dict):raise ValueError('Supported portal schema requires data.docdata b2b/cdnr sections.')
    if any(value for key,value in sections.items() if key not in ('b2b','cdnr')):raise ValueError('Unsupported nonempty portal sections require separate reviewed normalization; none were silently skipped.')
    rows=[]
    for section,parents in sections.items():
        for parent in parents:
            supplier=gst._gstin(parent.get('ctin',''))
            for doc in parent.get('inv' if section=='b2b' else 'nt',[]):
                note=section=='cdnr';reference=str(doc.get('ntnum',doc.get('nt_num','')) if note else doc.get('inum','')).strip();raw_date=doc.get('nt_dt',doc.get('dt','')) if note else doc.get('dt','')
                on=datetime.strptime(raw_date,'%d-%m-%Y').date().isoformat();items=doc.get('items',[])
                if not reference or not items:raise ValueError('Portal documents need actual references, dates and nonempty item tax amounts.')
                totals=dict.fromkeys(('taxable','cgst','sgst','igst'),0)
                for item in items:
                    if rcm._money(item.get('cess','0')):raise ValueError('Cess requires a separately reviewed supported source; it cannot be dropped.')
                    for dest,source in [('taxable','txval'),('cgst','cgst'),('sgst','sgst'),('igst','igst')]:totals[dest]+=rcm._money(item.get(source,'0'))
                available=str(doc.get('itcavl',doc.get('itc_avl',''))).upper();reverse=str(doc.get('rev','N')).upper()
                if available not in ('Y','N') or reverse not in ('Y','N'):raise ValueError('Portal ITC availability/RCM flags must be explicit Y/N.')
                kind='Invoice' if not note else 'Credit note' if doc.get('typ',doc.get('ntty'))=='C' else 'Debit note' if doc.get('typ',doc.get('ntty'))=='D' else None
                if kind is None:raise ValueError('Unknown portal note type.')
                linked=original_links.get(supplier+'|'+reference,{})
                if note and not linked:raise ValueError('Independently link original invoice/date for portal notes; the adapter does not guess a missing parent.')
                rows.append(dict(supplier_gstin=supplier,invoice=reference,date=on,itc_available=available,document_type=kind,original_invoice=linked.get('invoice',''),original_date=linked.get('date',''),reverse_charge=reverse,**{k:format(rcm.Decimal(v)/100,'.2f') for k,v in totals.items()}))
    if not rows or len(rows)>50000:raise ValueError('Portal import requires 1–50000 supported documents.')
    return rows


def import_json(s,raw,filename,registration,period,branch,original_links=None):
    from .foundation import branches
    registration=gst._gstin(registration);tax.day(period+'-01')
    if branch not in branches(s,True):raise ValueError('Select the receiving operating unit for source reconciliation.')
    digest=hashlib.sha256(raw).hexdigest()
    if any(x['digest']==digest and x['registration']==registration and x.get('status')!='VOID' for x in s['gst_portal_imports']):raise ValueError('This raw portal file is already staged.')
    rows=normalize(raw,registration,period,original_links)
    known={(x['registration'],x['period'],r['supplier_gstin'],r['document_type'],gst._reference(r['invoice']),r['date']) for x in s['gst_portal_imports'] if x.get('status')!='VOID' for r in x['rcm_rows']}
    for row in rows:
        identity=(registration,period,row['supplier_gstin'],row['document_type'],gst._reference(row['invoice']),row['date'])
        if identity in known:raise ValueError('Duplicate portal source identity in the same registration/period.')
        known.add(identity)
    c=copy.deepcopy(s);forward=[r for r in rows if r['reverse_charge']=='N'];rcm_rows=[dict(r,id=str(uuid.uuid4()),match=None) for r in rows if r['reverse_charge']=='Y'];import_id=None
    if forward:
        out=io.StringIO();fields=list(forward[0]);w=csv.DictWriter(out,fieldnames=fields);w.writeheader();w.writerows(forward);import_id=gst.import_2b(c,out.getvalue().encode(),filename+'.normalized.csv',registration,period)['id']
    item=dict(id=str(uuid.uuid4()),digest=digest,filename=filename,registration=registration,period=period,branch=branch,forward_import=import_id,rcm_rows=rcm_rows,original_links=copy.deepcopy(original_links or {}),schema='GSTR-2B data.docdata b2b/cdnr; strict supported sections')
    c['gst_portal_imports'].append(item);core.add_audit(c,'GST_PORTAL_SOURCE_IMPORTED',copy.deepcopy(item));s.clear();s.update(c);return copy.deepcopy(item)


def rcm_candidates(s,item,row):
    result=[]
    for r in s['gst_rcm_records']:
        expected='Purchase' if row['document_type']=='Invoice' else row['document_type']
        if r['stage']!=expected or r['registration']!=item['registration'] or r['branch']!=item['branch']:continue
        parent=r if expected=='Purchase' else next(p for p in s['gst_rcm_records'] if p['id']==r['purchase_id'])
        if parent.get('supplier_gstin')!=row['supplier_gstin'] or gst._reference(r['reference'])!=gst._reference(row['invoice']):continue
        exact=r['date']==row['date'] and abs(r['amounts']['base'])==rcm._money(row['taxable']) and all(abs(r['amounts'][p])==rcm._money(row[p]) for p in rcm.PARTS)
        if expected!='Purchase':exact=exact and gst._reference(parent['reference'])==gst._reference(row['original_invoice']) and parent['date']==row['original_date']
        result.append(dict(record_id=r['id'],voucher=r['voucher_id'],status='Exact' if exact and fa.family(s,r['voucher_id'])==1 else 'Mismatch or reversed'))
    return result


def match_rcm(s,import_id,row_id,record_id,reason,undo=False):
    item=next(x for x in s['gst_portal_imports'] if x['id']==import_id);row=next(r for r in item['rcm_rows'] if r['id']==row_id)
    if not str(reason).strip():raise ValueError('Enter exact-source match/undo basis.')
    if undo:
        if not row['match']:raise ValueError('This RCM source has no match.')
        before=row['match'];row['match']=None
    else:
        candidates=rcm_candidates(s,item,row)
        if not any(c['record_id']==record_id and c['status']=='Exact' for c in candidates):raise ValueError('Only exact live registration/unit/supplier/reference/date/base/tax source matches can be linked.')
        if row['match'] or any(r['match'] and r['match']['record_id']==record_id for x in s['gst_portal_imports'] for r in x['rcm_rows']):raise ValueError('The source row or book document is already linked.')
        before=None;row['match']=dict(record_id=record_id,reason=str(reason).strip())
    core.add_audit(s,'RCM_PORTAL_SOURCE_MATCHED' if not undo else 'RCM_PORTAL_MATCH_UNDONE',dict(import_id=import_id,row_id=row_id,before=before,after=copy.deepcopy(row['match']),reason=reason))


def void_import(s,import_id,reason):
    c=copy.deepcopy(s);item=next(x for x in c['gst_portal_imports'] if x['id']==import_id)
    if item.get('status')=='VOID' or not str(reason).strip() or any(r['match'] for r in item['rcm_rows']):raise ValueError('Undo all source matches before voiding an unused portal import with a reason.')
    if item['forward_import']:gst.void_2b(c,item['forward_import'],reason)
    item['status']='VOID';core.add_audit(c,'GST_PORTAL_IMPORT_VOIDED',dict(id=import_id,reason=str(reason).strip()));s.clear();s.update(c)

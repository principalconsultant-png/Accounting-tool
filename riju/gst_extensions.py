"""Reviewed mixed-rate/export invoices and source-line GST corrections."""
import copy
from datetime import datetime
import uuid
from . import core,foundation,gst,tax,fixed_assets as fa,history


def plan_invoice(s,v):
    rows=v.get('items',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=200:raise ValueError('Provide 1–200 reviewed invoice lines.')
    planned=[]
    for row in rows:
        d=gst.plan(s,dict(v,**row));d['line_id']=str(uuid.uuid4());planned.append(d)
    first=planned[0];lines=[];totals=dict.fromkeys(('base','cgst','sgst','igst','total'),0)
    for d in planned:
        if (d['kind'],d['registration'],d['counterparty_gstin'],d['branch'],d['counter_account'])!=(first['kind'],first['registration'],first['counterparty_gstin'],first['branch'],first['counter_account']):raise ValueError('One invoice must retain its kind, unit, registration, counterparty and settlement ledger.')
        lines.extend(d['lines'])
        for k in totals:totals[k]+=d['totals'][k]
    result=copy.deepcopy(first);result.update(id=str(uuid.uuid4()),line_items=[dict(id=d['line_id'],account=d['account'],rule=d['rule'],itc=d['itc'],totals=d['totals'],description=str(row.get('description',''))) for d,row in zip(planned,rows)],totals=totals,lines=lines)
    if len({d['rule']['id'] for d in planned})>1:result['rule']=dict(first['rule'],treatment='Mixed; see source lines')
    if len({d['itc'] for d in planned})>1:result['itc']='Mixed; see source lines'
    result['account']=first['account'] if len({d['account'] for d in planned})==1 else 'Multiple; see lines'
    return result


def post_invoice(s,v):
    if v.get('confirmed') is not True:raise ValueError('Review all invoice lines, supply classification, actual evidence and the complete journal.')
    candidate=copy.deepcopy(s);doc=plan_invoice(candidate,v);doc['voucher_id']=core.post(candidate,doc['date'],doc['narration'],doc['lines'],metadata={'reference':doc['reference']})['id'];candidate['gst_documents'].append(doc)
    from .gst_payments import check
    check(candidate)
    core.add_audit(candidate,'GST_MULTILINE_POSTED',copy.deepcopy(doc));s.clear();s.update(candidate);return copy.deepcopy(doc)


def line_positions(s,original,on='9999-12-31',reversal=None,proposed=None,net=None):
    roots=gst._roots(s)
    if net is None:
        net={}
        for v in s['vouchers']:
            if v['date']<=on:
                root,sign=roots[v['id']];net[root]=net.get(root,0)+sign
    positions={row['id']:dict.fromkeys(row['totals'],0) for row in original['line_items']}
    docs=[d for d in s['gst_documents'] if d['id']==original['id'] or d.get('original_document_id')==original['id']]
    if proposed:docs.append(proposed)
    for d in docs:
        n=net.get(d['voucher_id'],0) if d.get('voucher_id') else int(d['date']<=on)
        if reversal and d.get('voucher_id') and reversal[1]<=on and roots[reversal[0]][0]==d['voucher_id']:n-=roots[reversal[0]][1]
        for item in d['line_items']:
            for k,v in item['totals'].items():positions[item['id']][k]+=v*n*d.get('document_sign',1)
    return positions


def check_lines(s,proposed=None,reversal=None):
    roots=gst._roots(s);affected=None
    if proposed:affected=proposed.get('original_document_id',proposed['id'])
    if reversal:
        root=roots[reversal[0]][0];doc=next((d for d in s['gst_documents'] if d['voucher_id']==root),None)
        if not doc:return
        affected=doc.get('original_document_id',doc['id'])
    for original in s['gst_documents']:
        if original.get('original_document_id') or not original.get('line_items') or affected and original['id']!=affected:continue
        relevant={d['voucher_id'] for d in s['gst_documents'] if d['id']==original['id'] or d.get('original_document_id')==original['id']};events={}
        for v in s['vouchers']:
            root,sign=roots[v['id']]
            if root in relevant:events.setdefault(v['date'],[]).append((root,sign))
        if proposed:events.setdefault(proposed['date'],[])
        if reversal:events.setdefault(reversal[1],[])
        net={}
        for on in sorted(events):
            for root,sign in events[on]:net[root]=net.get(root,0)+sign
            if any(n<0 for values in line_positions(s,original,on,reversal,proposed,net).values() for n in values.values()):raise ValueError('GST source-line correction exceeds dated remaining base/tax capacity; review later notes and reversals.')


def plan_note(s,v):
    original=next((d for d in s['gst_documents'] if d['id']==v.get('original_document_id') and not d.get('original_document_id')),None)
    if not original or not original.get('line_items') or fa.family(s,original['voucher_id'],v.get('date',''))!=1:raise ValueError('Select an active original multi-line invoice.')
    on=tax.day(v.get('date',''));kind=v.get('document_type');ref=str(v.get('reference','')).strip();basis=str(v.get('narration','')).strip();counter=v.get('counter_account')
    if on<original['date'] or kind not in ('Credit note','Debit note') or not ref or not basis:raise ValueError('Enter actual note type, dated source reference and reviewed basis.')
    if any(d['registration']==original['registration'] and d['kind']==original['kind'] and d['counterparty_gstin']==original['counterparty_gstin'] and gst._reference(d['reference'])==gst._reference(ref) and core.financial_year(d['date'])==core.financial_year(on) for d in s['gst_documents']):raise ValueError('Duplicate note reference in this registration/counterparty/year.')
    if s['account_details'].get(counter,{}).get('group') not in ('Cash and bank','Payment clearing','Patient control','Trade payables','Patient advances','Other assets','Other liabilities') or counter in s.get('foreign_accounts',{}):raise ValueError('Choose the actual INR refund/control ledger.')
    requested=v.get('items',[])
    if not requested:raise ValueError('Allocate the note base to explicit original line IDs; mixed rates cannot use one guessed rate.')
    available=line_positions(s,original,on);source={i['id']:i for i in original['line_items']};seen=set();items=[];lines=[];totals=dict.fromkeys(original['totals'],0);sign=-1 if kind=='Credit note' else 1;sale=original['kind']=='Sale'
    def add(code,n,dr):
        if n:lines.append(dict(account=code,branch=original['branch'],debit=n if dr else 0,credit=0 if dr else n))
    for value in requested:
        key=value.get('line_id')
        if key not in source or key in seen:raise ValueError('Select distinct original source line IDs.')
        seen.add(key);item=copy.deepcopy(source[key]);amounts=gst.split(item['rule'],value.get('amount'),False,item['totals']['igst']==0)
        if sign<0 and amounts['base']==available[key]['base']:amounts=copy.deepcopy(available[key])
        item['totals']=amounts;items.append(item);eligible=item['itc']=='Eligible'
        add(item['account'],amounts['base'] if sale or eligible else amounts['total'],not sale if sign>0 else sale)
        if sale or eligible:
            for code,k in zip(gst.OUTPUT if sale else gst.INPUT,('cgst','sgst','igst')):add(code,amounts[k],not sale if sign>0 else sale)
        for k in totals:totals[k]+=amounts[k]
    add(counter,totals['total'],sale if sign>0 else not sale)
    result=copy.deepcopy(original);result.update(id=str(uuid.uuid4()),date=on,reference=ref,narration=basis,document_type=kind,document_sign=sign,original_document_id=original['id'],original_voucher_id=original['voucher_id'],original_reference=original['reference'],counter_account=counter,line_items=items,totals=totals,lines=lines);result.pop('voucher_id',None)
    gst._check_family(s,original['id'],(on,{k:n*sign for k,n in totals.items()}),extra_note=('proposed',1));check_lines(s,proposed=result);return result


def export(s,start,end,branch,path,kind):
    from . import financial_reports as fr,rcm
    summary=gst.summary(s,start,end,branch);base=dict(entity=s['settings']['entity'],registration=copy.deepcopy(s['settings']['registration']),start=start,end=end,branch=branch,scope='All operating units' if branch=='ALL' else foundation.branches(s)[branch],prepared=datetime.now(history.INDIA).isoformat(),currency='INR',status='Working / source review required',controls={},note='GST bookkeeping working; separate registrations and actual eligibility/source/filing need review. Taxed service advances follow their tax point and are not automatically financial revenue. Mixed invoice lines retain original rates/treatments. Manual/unclassified tax movements remain visible.')
    rows=[]
    for d in summary['documents']:
        for item in d.get('line_items') or [dict(id='',account=d['account'],rule=d['rule'],itc=d['itc'],totals={k:n*d['sign'] for k,n in d['totals'].items()})]:
            n=d['sign'] if d.get('line_items') else 1;rows.append([d['movement_date'],d['movement_voucher'],d['kind'],d['registration'],d['reference'],d.get('supply_type','Domestic'),item['id'],item['account'],item['rule']['key'],item['rule']['treatment'],item['itc'],*[item['totals'][k]*n for k in ('base','cgst','sgst','igst','total')]])
    proof=[[c,summary['opening_balances'][c],summary['ledger_movements'][c],summary['closing_balances'][c],summary['unclassified'][c]] for c in gst.INPUT+gst.OUTPUT]
    rr=rcm.report(s,start,end,branch);rcm_rows=[[r['reference'],r['registration'],r['branch'],*[r['tax_due'][p] for p in rcm.PARTS],r['itc_pending']] for r in rr['outstanding']]
    packs=[dict(base,mode='GST invoice and source lines',columns=['Date','Voucher','Kind','GSTIN','Reference','Supply type','Line ID','Account','Rule','Treatment','ITC','Base INR','CGST INR','SGST INR','IGST INR','Gross INR'],money_columns=list(range(11,16)),rows=rows),dict(base,mode='GST tax control proof',columns=['Ledger','Opening INR','Movement INR','Closing INR','Unclassified INR'],money_columns=[1,2,3,4],rows=proof),dict(base,mode='RCM outstanding and ITC',columns=['Invoice','Registration','Unit','CGST due/(overpaid) INR','SGST due/(overpaid) INR','IGST due/(overpaid) INR','Pending ITC INR'],money_columns=[3,4,5,6],rows=rcm_rows)]
    packs.append(dict(base,mode='RCM stage source journals',columns=['Date','Stage','Voucher','Reference','Registration','Unit','Base INR','CGST INR','SGST INR','IGST INR'],money_columns=[6,7,8,9],rows=[[r['movement_date'],r['stage'],r['movement_voucher'],r['reference'],r['registration'],r['branch'],r['amounts'].get('base',0)*r['sign'],*[r['amounts'][p]*r['sign'] for p in ('cgst','sgst','igst')]] for r in rr['records']]))
    packs.append(dict(base,mode='RCM control ledger proof',columns=['Ledger','Opening INR','Movement INR','Closing INR','Unclassified INR'],money_columns=[1,2,3,4],rows=[[c,rr['opening_balances'][c],rr['ledger_movements'][c],rr['closing_balances'][c],rr['unclassified'][c]] for c in sorted(rr['control_ledgers'].values())]))
    from . import gst_payments as pay,gst_portal as portal
    scopes={(d['registration'],d['branch']) for d in s['gst_documents']}|{(r['registration'],r['branch']) for r in pay.actions(s)};cash_rows=[];action_rows=[]
    for reg,unit in sorted(scopes):
        if branch not in ('ALL',unit):continue
        pos=pay.position(s,reg,unit,end);balances=core.balances(s,end,unit)
        for part in pay.PARTS:
            code=s.get('gst_cash_ledgers',{}).get(reg,{}).get(part,'');actual=balances.get(code,0);cash_rows.append([reg,unit,part,pos['due'][part],pos['credit'][part],pos['cash'][part],code,actual,actual-pos['cash'][part]])
    for r in pay.actions(s):
        if r['date']<=end and branch in ('ALL',r['branch']):action_rows.append([r['date'],r['kind'],r['registration'],r['branch'],r['reference'],r['voucher_id'],r['narration']])
    packs.append(dict(base,mode='GST cash and credit positions',columns=['Registration','Unit','Component','Tax due/(overpaid) INR','Input credit INR','Tagged cash INR','Cash ledger','Actual cash INR','Unclassified cash INR'],money_columns=[3,4,5,7,8],rows=cash_rows))
    packs.append(dict(base,mode='GST actual payment source history',columns=['Date','Action','Registration','Unit','Reference','Voucher','Reviewed basis'],money_columns=[],rows=action_rows))
    portal_rows=[]
    for item in s['gst_portal_imports']:
        if branch not in ('ALL',item['branch']):continue
        for row in item['rcm_rows']:portal_rows.append([item['registration'],item['period'],item['filename'],row['supplier_gstin'],row['document_type'],row['invoice'],row['date'],row['itc_available'],row['match']['record_id'] if row['match'] else 'Not linked',item.get('status','OPEN')])
    packs.append(dict(base,mode='RCM portal source reconciliation',columns=['Registration','Period','Source file','Supplier','Type','Reference','Date','Source availability','Linked RCM record','Import status'],money_columns=[],rows=portal_rows))
    filing_rows=[]
    for r in s['gst_filing_reviews']:
        if branch not in ('ALL',r['branch']):continue
        current=pay.period_fingerprint(s,r['registration'],r['branch'],r['period'])[0];filing_rows.append([r['registration'],r['branch'],r['period'],r['status'],'Current' if current==r['review_fingerprint'] else 'STALE source changed',r['acknowledgement'],r['basis']])
    packs.append(dict(base,mode='GST filing preparation history',columns=['Registration','Unit','Period','State','Snapshot check','Manual acknowledgement','Review basis'],money_columns=[],rows=filing_rows))
    if kind=='xlsx':fr.export_pack_xlsx(packs,path)
    elif kind=='pdf':fr.export_pdf(packs,path)
    else:raise ValueError('Choose Excel or PDF.')

"""Read-only history, source tracing and saved-state integrity checkpoints."""
import copy
import csv
from datetime import datetime, timedelta, timezone, date
import hashlib
import json
from pathlib import Path
from . import core

INDIA=timezone(timedelta(hours=5,minutes=30))


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def fingerprints(state):
    return {key:hashlib.sha256(encoded(value)).hexdigest() for key,value in sorted(state.items()) if key!='audit'}


def verify_saved_state(state):
    """Called before migration; older books honestly have no state checkpoint."""
    core.verify_audit(state)
    try:
        from . import ap
        ap.check(state)
    except (ValueError,KeyError,TypeError) as e:errors.append('AP integrity: '+str(e))
    checkpoints=[r for r in state['audit'] if r['action']=='STATE_CHECKPOINT']
    if not checkpoints:return False
    latest=checkpoints[-1]
    if latest is not state['audit'][-1] or latest['payload'].get('sections')!=fingerprints(state):
        raise ValueError('Saved books integrity check failed. Keep this file and restore a verified external backup.')
    return True


def checkpoint(state):
    sections=fingerprints(state)
    if state['audit'] and state['audit'][-1]['action']=='STATE_CHECKPOINT' and state['audit'][-1]['payload'].get('sections')==sections:return
    core.add_audit(state,'STATE_CHECKPOINT',{'sections':sections,'coverage':'Saved book data excluding the hash-chained history itself'})


def differences(before,after,path=''):
    """Full values for added/removed fields; lists preserve exact order and content."""
    if before==after:return []
    if isinstance(before,dict) and isinstance(after,dict):
        rows=[]
        for key in sorted(before.keys()|after.keys()):
            part=path+'/'+str(key).replace('~','~0').replace('/','~1')
            if key not in before:rows.append({'path':part,'change':'added','after':copy.deepcopy(after[key])})
            elif key not in after:rows.append({'path':part,'change':'removed','before':copy.deepcopy(before[key])})
            else:rows.extend(differences(before[key],after[key],part))
        return rows
    return [{'path':path,'change':'updated','before':copy.deepcopy(before),'after':copy.deepcopy(after)}]


def record_changes(before,after,context):
    # Posted vouchers already have immutable full POST payloads; avoid duplicating them.
    excluded={'audit','vouchers'}
    changes=differences({k:v for k,v in before.items() if k not in excluded},{k:v for k,v in after.items() if k not in excluded})
    if changes:core.add_audit(after,'CHANGE_SET',{'screen':context,'changes':changes})


def india_time(value):
    parsed=datetime.fromisoformat(value)
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(INDIA).isoformat(timespec='seconds')


def summary(record):
    p=record['payload'];action=record['action']
    if action=='POST':return p['id']+' · '+p['date']+' · '+p['narration']
    if action=='CHANGE_SET':return p.get('screen','')+' · '+', '.join(x['path'] for x in p['changes'])
    if action=='STATE_CHECKPOINT':return 'Saved-book verification checkpoint'
    if action=='DRAFT_POSTED':return 'Draft '+p['draft_id']+' → '+p['voucher_id']
    if 'old' in p or 'new' in p:return action.replace('_',' ').capitalize()+' · before/after details available'
    return action.replace('_',' ').capitalize()+' · '+str(p.get('id',p.get('bank_id',p.get('filename',p.get('code','')))))


def entries(state,start='',through='',action='All actions',query='',include_checkpoints=False):
    for value in (start,through):
        if value:date.fromisoformat(value)
    if start and through and start>through:raise ValueError('History start must not follow its end date.')
    rows=[];needle=query.casefold().strip()
    for r in reversed(state['audit']):
        if not include_checkpoints and r['action']=='STATE_CHECKPOINT':continue
        day=india_time(r['timestamp'])[:10]
        if (start and day<start) or (through and day>through) or (action!='All actions' and r['action']!=action):continue
        if needle and needle not in json.dumps(r,ensure_ascii=False).casefold():continue
        rows.append(dict(sequence=r['sequence'],timestamp_india=india_time(r['timestamp']),timestamp_utc=r['timestamp'],actor=r.get('actor','Not recorded (legacy)'),action=r['action'],summary=summary(r),hash=r['hash'],previous=r['previous'],payload=copy.deepcopy(r['payload'])))
    return rows



def detail_text(record):
    parts=[f"Event {record['sequence']} · {record['summary']}",
        'User: '+record['actor'], 'Time India: '+record['timestamp_india'],
        'Time UTC: '+record['timestamp_utc'], 'Action: '+record['action']]
    p=record['payload']
    for change in p.get('changes',[]):
        parts+=['', 'Field: '+change['path']+' ('+change['change']+')',
            'Before: '+json.dumps(change.get('before','Field not present'),ensure_ascii=False,indent=2),
            'After: '+json.dumps(change.get('after','Field not present'),ensure_ascii=False,indent=2)]
    if 'old' in p or 'new' in p:
        parts+=['', 'Before: '+json.dumps(p.get('old','Not recorded'),ensure_ascii=False,indent=2),
            'After: '+json.dumps(p.get('new','Not recorded'),ensure_ascii=False,indent=2)]
    parts+=['', 'Full recorded event details:', json.dumps(record,ensure_ascii=False,indent=2)]
    return '\n'.join(parts)


def trace_voucher(state,voucher_id):
    v=next((v for v in state['vouchers'] if v['id']==voucher_id),None)
    if v is None:raise ValueError('Voucher not found.')
    source=v.get('source');imports=[]
    if source:
        imports=[copy.deepcopy(q) for q in state['queue'] if q['id']==source['document_id']]
    draft_links=[copy.deepcopy(r['payload']) for r in state['audit'] if r['action']=='DRAFT_POSTED' and r['payload']['voucher_id']==voucher_id]
    matches=[]
    from . import reconciliation as bank
    for m in state['matches']:
        linked=voucher_id in m.get('vouchers',[]) or m.get('posting')==voucher_id or any(e['book_key'].rsplit(':',1)[0]==voucher_id for e in bank._edges(state,m))
        if linked:
            ids=set(m.get('bank_ids',[]))|({m['bank_id']} if m.get('bank_id') else set())
            matches.append({'match':copy.deepcopy(m),'bank_rows':[copy.deepcopy(b) for b in state['bank_lines'] if b['id'] in ids]})
    related={voucher_id}|{x['id'] for x in state['vouchers'] if x.get('reverses')==voucher_id}|({v['reverses']} if v.get('reverses') else set())
    events=[copy.deepcopy(r) for r in state['audit'] if any(i in json.dumps(r['payload'],ensure_ascii=False) for i in related)]
    tax_docs=state.get('gst_documents',[])
    gst_ids={d['id'] for d in tax_docs if d['voucher_id'] in related}
    gst_ids|={d['original_document_id'] for d in tax_docs if d['id'] in gst_ids and d.get('original_document_id')}
    gst_context=[copy.deepcopy(d) for d in tax_docs if d['id'] in gst_ids or d.get('original_document_id') in gst_ids]
    rcm_records=state.get('gst_rcm_records',[])
    rcm_ids={r['id'] for r in rcm_records if r['voucher_id'] in related}
    rcm_ids|={r['purchase_id'] for r in rcm_records if r['id'] in rcm_ids and r.get('purchase_id')}
    rcm_context=[copy.deepcopy(r) for r in rcm_records if r['id'] in rcm_ids or r.get('purchase_id') in rcm_ids]
    tds_records=state.get('tds_records',[])
    tds_ids={r['id'] for r in tds_records if r.get('voucher_id') in related or r.get('source_voucher') in related}
    tds_links=[copy.deepcopy(a) for a in state.get('tds_allocations',[]) if a['document_id'] in tds_ids or a['payment_id'] in tds_ids]
    tds_ids|={a[k] for a in tds_links for k in ('document_id','payment_id')}
    tds_context=[copy.deepcopy(r) for r in tds_records if r['id'] in tds_ids]
    from . import cwip
    projects=cwip.data(state)
    cwip_costs={c['id'] for c in projects['costs'] if c['voucher'] in related}
    linked_events=[e for e in projects['events'] if e['voucher'] in related]
    cwip_costs|={i['cost'] for e in linked_events for i in e['items']}|{e['cost'] for e in linked_events if e.get('cost')}
    cwip_costs|={r['cwip_cost'] for r in tds_context if r.get('cwip_cost')}
    cwip_context=dict(costs=[copy.deepcopy(c) for c in projects['costs'] if c['id'] in cwip_costs],events=[copy.deepcopy(e) for e in projects['events'] if e in linked_events or e.get('cost') in cwip_costs or any(i['cost'] in cwip_costs for i in e['items'])])
    from . import ap
    apinvoices=[r for r in ap.data(state)['invoices'] if r['voucher'] in related or any(p['voucher'] in related and any(i['invoice']==r['id'] for i in p['items']) for p in ap.data(state)['payments'])]
    ap_context=dict(invoices=copy.deepcopy(apinvoices),payments=[copy.deepcopy(p) for p in ap.data(state)['payments'] if p['voucher'] in related or any(i['invoice'] in {r['id'] for r in apinvoices} for i in p['items'])])
    return dict(ap_context=ap_context,cwip_context=cwip_context,voucher=copy.deepcopy(v),gst_context=gst_context,rcm_context=rcm_context,tds_context=tds_context,tds_allocations=tds_links,original=next((copy.deepcopy(x) for x in state['vouchers'] if x['id']==v.get('reverses')),None),reversals=[copy.deepcopy(x) for x in state['vouchers'] if x.get('reverses')==voucher_id],source=copy.deepcopy(source),imports=imports,drafts=draft_links,matches=matches,events=events,coverage='Explicit source/draft links are shown where recorded. Older unlinked entries are not attributed by guessing.')


def integrity_report(state):
    errors=[];warnings=[]
    try:core.verify_audit(state)
    except (ValueError,KeyError,TypeError) as e:errors.append(str(e))
    accounts={a['code'] for a in state['accounts']};branches=set(state.get('branches',core.BRANCHES));ids=set();sources=set()
    for v in state['vouchers']:
        vid=v.get('id','(missing ID)')
        if vid in ids:errors.append('Duplicate voucher ID: '+vid)
        ids.add(vid);branch_totals={};total=0
        try:
            date.fromisoformat(v['date'])
            for line in v['lines']:
                dr,cr=line['debit'],line['credit']
                if type(dr)!=int or type(cr)!=int or dr<0 or cr<0 or (dr>0)==(cr>0):raise ValueError('Invalid debit/credit amount')
                if line['account'] not in accounts or line['branch'] not in branches:raise ValueError('Unknown ledger or branch')
                total+=dr-cr;branch_totals[line['branch']]=branch_totals.get(line['branch'],0)+dr-cr
            if len(v['lines'])<2 or total or any(branch_totals.values()):raise ValueError('Journal or branch is unbalanced')
            if v.get('source'):
                source=v['source'];key=tuple(source[k] for k in ('kind','document_id','record_id'))
                if key in sources:raise ValueError('Duplicate posted source link')
                sources.add(key)
        except (ValueError,KeyError,TypeError) as e:errors.append(vid+': '+str(e))
    for v in state['vouchers']:
        if v.get('reverses'):
            original=next((x for x in state['vouchers'] if x['id']==v['reverses']),None)
            if original is None or v['date']<original['date'] or v['lines']!=[dict(l,debit=l['credit'],credit=l['debit']) for l in original['lines']]:errors.append(v['id']+': invalid reversal link')
    # Inspect live allocation references even when no saved checkpoint exists yet.
    try:
        from . import reconciliation as bank
        bank_used,book_used=bank.used_allocations(state)
        physical={b['id']:b for a in bank.bank_accounts(state) for b in bank.bank_rows(state,a['code'])}
        books={b['key']:b for a in bank.bank_accounts(state) for b in bank.book_items(state,a['code'])}
        if len({b['id'] for b in state['bank_lines']})!=len(state['bank_lines']):errors.append('Duplicate bank transaction ID')
        for key,used in bank_used.items():
            row=physical.get(key)
            if row is None or used*row['amount']<0 or abs(used)>abs(row['amount']):errors.append('Invalid bank allocation: '+key)
        for key,used in book_used.items():
            row=books.get(key)
            if row is None or used*row['amount']<0 or abs(used)>abs(row['amount']):errors.append('Invalid book allocation: '+key)
        for statement in state.get('bank_statements',[]):
            if statement['status']!='VOID' and any(i not in physical for i in statement['row_ids']):errors.append('Statement references a missing bank row: '+statement['id'])
    except (ValueError,KeyError,TypeError) as e:errors.append('Bank integrity: '+str(e))
    try:
        from . import cwip
        cwip.check(state)
    except (ValueError,KeyError,TypeError) as e:errors.append('CWIP integrity: '+str(e))
    try:
        from . import ap
        ap.check(state)
    except (ValueError,KeyError,TypeError) as e:errors.append('AP integrity: '+str(e))
    checkpoints=[r for r in state['audit'] if r['action']=='STATE_CHECKPOINT']
    if checkpoints and state['audit'][-1]['action']=='STATE_CHECKPOINT':
        try:verify_saved_state(state)
        except ValueError as e:errors.append(str(e))
    else:warnings.append('No current saved-state checkpoint. The next successful save establishes one; earlier master history cannot be reconstructed.')
    if any('actor' not in r for r in state['audit']):warnings.append('Legacy events do not identify a user. Their recorded timestamps remain unchanged.')
    return {'passed':not errors,'errors':errors,'warnings':warnings,'checked_at_india':datetime.now(INDIA).isoformat(timespec='seconds'),'vouchers_checked':len(state['vouchers']),'events_checked':len(state['audit']),'latest_checkpoint_sequence':checkpoints[-1]['sequence'] if checkpoints else None,'scope':'Local consistency checks; no statutory certification or protection against an attacker rewriting both books and history.'}


def export_rows(rows,path,kind='csv'):
    if kind=='json':Path(path).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');return
    if kind!='csv':raise ValueError('Choose CSV or JSON.')
    def safe(value):
        text=str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['Sequence','Time India','Time UTC','User','Action','Summary','Before / after and event details (JSON)','Hash','Previous hash'])
        for r in rows:writer.writerow([safe(r[k]) for k in ('sequence','timestamp_india','timestamp_utc','actor','action','summary')]+[safe(json.dumps(r['payload'],ensure_ascii=False)),r['hash'],r['previous']])

"""Work-volume statistics derived from durable posted/audited records, never clicks."""
import copy
import csv
import hashlib
import json
from datetime import date,datetime,timezone,timedelta
from . import core,foundation

INDIA=timezone(timedelta(hours=5,minutes=30))
DEFINITIONS={
 'business_transactions_posted':'Posted voucher records excluding initial openings, year-end closes, reversals and bank-settlement journals. One compound voucher is one record, not one record per line or per patient.',
 'journal_vouchers_created':'Permanent vouchers are created atomically when posted; therefore permanent vouchers created and posted have the same count. Unposted saved drafts are shown separately.',
 'journal_vouchers_posted':'All successful unique posted vouchers, including reversals, openings, year-end closes and settlements.',
 'journal_lines_posted':'Debit/credit lines within posted vouchers; these are not additional transactions.',
 'saved_drafts_created':'Unique saved draft IDs created in the selected period; editing the same draft does not create another draft.',
 'drafts_pending':'Saved drafts currently awaiting posting within the selected scope/period.',
 'import_rows_processed':'Distinct source rows linked to successful postings. This is a breakdown of work already represented by journal vouchers, not an additional total to add to posted transactions.',
 'import_files_processed':'Distinct import documents with linked posted rows in scope/period.',
 'import_rows_pending':'Rows currently in the review queue; not completed work.',
 'bank_rows_imported':'Distinct bank-statement records imported; not all are posted transactions.',
 'bank_rows_matched':'Distinct bank rows reconciled; a settlement journal is counted once in journal vouchers, not again as a business receipt.',
 'reversals_posted':'Reversal vouchers posted in the selected period; original completed work remains in gross work-volume counts.',
 'opening_journals':'Initial-opening vouchers, reported separately from ordinary business transactions.',
 'closing_journals':'Year-end closing journals, reported separately.',
 'settlement_journals':'Bank settlement journals, reported separately from business receipts.',
 'fx_receipts_posted':'Foreign-currency receipt vouchers; included in business transactions, not an additional total.',
 'fx_conversions_posted':'Foreign-holding conversion vouchers; included in business transactions.',
 'legacy_rows_unlinked':'Processed queue rows for which no unambiguous remaining posted-voucher link was found. Excluded from processed-row totals rather than inventing work.',
 'undated_bank_imports':'Legacy bank records without an import timestamp; included for all-time/book-date reports but excluded from work-date period reports.'}
LABELS={k:k.replace('_',' ').capitalize() for k in DEFINITIONS}


def validate_source(value):
    if not isinstance(value,dict) or set(value)!={'kind','document_id','record_id','row_count'}:raise ValueError('Invalid import source link.')
    if value['kind'] not in ('daily_sales','journal_csv','opening_csv'):raise ValueError('Unknown import source kind.')
    if any(not isinstance(value[k],str) or not value[k].strip() for k in ('document_id','record_id')):raise ValueError('Import document/row IDs are required.')
    if type(value['row_count'])!=int or value['row_count']<=0:raise ValueError('Source row count must be a positive integer.')
    return dict(value)


def india_day(timestamp):
    if not timestamp:return None
    try:
        d=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
        if d.tzinfo is None:return None
        return d.astimezone(INDIA).date().isoformat()
    except (ValueError,TypeError):return None


def import_bank_rows(state,rows,branch,filename):
    if branch not in foundation.branches(state,active_only=True):raise ValueError('Select an active branch.')
    candidate=copy.deepcopy(state);new=[];now=datetime.now(timezone.utc).isoformat()
    for row in rows:
        if date.fromisoformat(row['date']).isoformat()!=row['date'] or type(row['amount'])!=int or row['amount']<=0:raise ValueError('Bank rows require YYYY-MM-DD and positive integer paise.')
        key=hashlib.sha256(json.dumps([branch,row['date'],row['reference'],row['narration'],row['amount']],sort_keys=True).encode()).hexdigest()[:20]
        if not any(b['id']==key for b in candidate['bank_lines']):
            from .reconciliation import _editable_bank
            _editable_bank(candidate,[dict(row,bank_account='1010',branch=branch)])
            candidate['bank_lines'].append(dict(row,id=key,branch=branch,status='UNMATCHED',imported_at=now));new.append(key)
    core.add_audit(candidate,'BANK_IMPORT',{'filename':filename,'rows':len(new),'branch':branch,'bank_ids':new})
    state.clear();state.update(candidate)
    return len(new)


def _import_links(state):
    """Use new explicit links and reconstruct legacy queue links without rewriting books."""
    records=[];used=set();modern_docs=set()
    for v in state['vouchers']:
        if v.get('source'):
            s=validate_source(v['source']);modern_docs.add((s['kind'],s['document_id']))
            key=(s['kind'],s['document_id'],s['record_id'])
            if key not in used:records.append((v,s));used.add(key)
    assigned={v['id'] for v,s in records};unlinked=[]
    for q in state['queue']:
        if q['status']!='PROCESSED':continue
        kind='daily_sales' if q.get('kind')=='daily_sales' else 'journal_csv'
        if (kind,q['id']) in modern_docs:continue
        for n,r in enumerate(q['rows']):
            if kind=='daily_sales':
                narration=f"Daily sales {r['date']} · Receipt {r['receipt'] or '—'} · Invoice {r['invoice'] or '—'} · {q['filename']} / {r['sheet']} row {r['source_row']}"
                def matches(v):return v['narration']==narration and v['date']==r['date'] and any(l['branch']==r['branch'] for l in v['lines'])
            else:
                expected=[dict(account=r['debit_account'],branch=r['branch'],debit=r['amount'],credit=0),dict(account=r['credit_account'],branch=r['branch'],debit=0,credit=r['amount'])]
                def matches(v):return v['date']==r['date'] and v['narration']==r['narration'].strip() and v['lines']==expected
            candidates=[v for v in state['vouchers'] if v['id'] not in assigned and not v.get('reverses') and matches(v)]
            found=candidates[0] if len(candidates)==1 else None
            if found:
                assigned.add(found['id']);records.append((found,dict(kind=kind,document_id=q['id'],record_id=str(r.get('key',n)),row_count=1)))
            else:unlinked.append(r)
    return records,unlinked


def report(state,start=None,end=None,branch='ALL',basis='work'):
    core.verify_audit(state)
    if branch!='ALL' and branch not in foundation.branches(state):raise ValueError('Unknown branch.')
    if basis not in ('work','book'):raise ValueError('Choose work performed dates or book transaction dates.')
    if (start is None)!=(end is None):raise ValueError('Both dates are required for a period report.')
    if start is not None:
        if date.fromisoformat(start).isoformat()!=start or date.fromisoformat(end).isoformat()!=end or start>end:raise ValueError('Enter a valid From/Through range.')
    def in_dates(day):return start is None or (day is not None and start<=day<=end)
    def in_branch(v):return branch=='ALL' or any(l['branch']==branch for l in v['lines'])
    post_dates={a['payload']['id']:india_day(a.get('timestamp')) for a in state['audit'] if a['action']=='POST'}
    selected=[v for v in state['vouchers'] if in_branch(v) and in_dates(v['date'] if basis=='book' else post_dates.get(v['id']))]
    settlements={m['posting'] for m in state['matches'] if m.get('posting') and m.get('kind','settlement')=='settlement'}
    normal=[v for v in selected if not (v.get('opening') or v.get('closing') or v.get('reverses') or v['id'] in settlements)]
    metrics={k:0 for k in DEFINITIONS}
    metrics.update(business_transactions_posted=len(normal),journal_vouchers_created=len(selected),journal_vouchers_posted=len(selected),journal_lines_posted=sum(len(v['lines']) for v in selected),
       reversals_posted=sum(bool(v.get('reverses')) for v in selected),opening_journals=sum(bool(v.get('opening')) for v in selected),closing_journals=sum(bool(v.get('closing')) for v in selected),settlement_journals=sum(v['id'] in settlements for v in selected),
       fx_receipts_posted=sum(v.get('fx',{}).get('kind')=='receipt' for v in selected),fx_conversions_posted=sum(v.get('fx',{}).get('kind')=='conversion' for v in selected))
    first_drafts={}
    for a in state['audit']:
        if a['action']=='DRAFT_SAVED':
            d=a['payload']['new'];first_drafts.setdefault(d['id'],(d,india_day(a.get('timestamp'))))
    metrics['saved_drafts_created']=sum(in_branch(d) and in_dates(d['date'] if basis=='book' else dt) for d,dt in first_drafts.values())
    metrics['drafts_pending']=sum(in_branch(d) and in_dates(d['date'] if basis=='book' else first_drafts.get(d['id'],(None,None))[1]) for d in state.get('drafts',[]))
    ids={v['id'] for v in selected};links,unlinked=_import_links(state)
    seen=set();docs=set()
    for v,s in links:
        key=(s['kind'],s['document_id'],s['record_id'])
        if v['id'] in ids and key not in seen:metrics['import_rows_processed']+=s['row_count'];seen.add(key);docs.add((s['kind'],s['document_id']))
    metrics['import_files_processed']=len(docs)
    metrics['legacy_rows_unlinked']=sum((branch=='ALL' or r.get('branch')==branch) and (start is None or basis=='work' or in_dates(r['date'])) for r in unlinked)
    stage_dates={}
    for a in state['audit']:
        if a['action']=='SALES_REPORT_STAGED':stage_dates[a['payload']['id']]=india_day(a.get('timestamp'))
        elif a['action']=='IMPORT_STAGED':stage_dates[a['payload']['digest'][:12]]=india_day(a.get('timestamp'))
    for q in state['queue']:
        if q['status']=='PENDING_REVIEW':
            metrics['import_rows_pending']+=sum((branch=='ALL' or r.get('branch')==branch) and in_dates(r['date'] if basis=='book' else stage_dates.get(q['id'])) for r in q['rows'])
    match_dates={}
    match_branches={}
    for m in state['matches']:
        if m.get('status','ACTIVE')!='ACTIVE':continue
        for bank_id in m.get('bank_ids',[m.get('bank_id')]):
            if bank_id:
                match_dates[bank_id]=india_day(m.get('created_at')) or post_dates.get(m.get('posting'))
                match_branches.setdefault(bank_id,set()).update(m.get('branches',[]))
    for b in state['bank_lines']:
        if b.get('void'):continue
        if branch!='ALL' and b['branch']!=branch and not (b['branch']=='ALL' and branch in match_branches.get(b['id'],set())):continue
        imported=india_day(b.get('imported_at'))
        if not imported:metrics['undated_bank_imports']+=1
        if in_dates(b['date'] if basis=='book' else imported):metrics['bank_rows_imported']+=1
        if b.get('status')=='MATCHED' and in_dates(b['date'] if basis=='book' else match_dates.get(b['id'])):metrics['bank_rows_matched']+=1
    return dict(entity=state['settings']['entity'],scope='All operating units' if branch=='ALL' else foundation.branches(state)[branch],start=start,end=end,basis=basis,
      prepared=datetime.now(INDIA).isoformat(timespec='seconds'),metrics=metrics,definitions=dict(DEFINITIONS),
      note='Counts belong to this customer vault. Branch figures can overlap for cross-branch journals and shared bank records; do not add them to obtain an entity total. Import/bank/draft figures overlap journal activity and must not be summed into one inflated total. Undated/unlinked coverage warnings are scope-wide, not additional completed work.')


def export_csv(result,path,include_client=False):
    from .ledgers import safe_csv
    with open(path,'w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.writer(stream)
        writer.writerow(['Work volume summary',safe_csv(result['entity']) if include_client else 'Client name omitted'])
        writer.writerow(['Scope',safe_csv(result['scope']) if include_client else 'Selected client scope'])
        writer.writerow(['Period',result['start'] or 'All time',result['end'] or 'All time','Date basis',result['basis'],'Work-date timezone','Asia/Kolkata'])
        writer.writerow(['Prepared',result['prepared']]);writer.writerow(['Metric','Count','Definition'])
        for key,value in result['metrics'].items():writer.writerow([LABELS[key],value,result['definitions'][key]])
        writer.writerow(['Counting rules',result['note']])

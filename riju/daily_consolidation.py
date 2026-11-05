"""Rebuildable SQLite management database, stored inside the protected book."""
import base64,copy,hashlib,json,sqlite3,zlib
from collections import defaultdict
from datetime import date,timedelta
from . import core,foundation,gst,history,report_branding

TITLE='Daily Business Register'
STORE='daily_consolidation_store'
HEADERS=('Date','Revenue INR','Sales Units / patients','Collections INR','Opex INR','Capex INR','Cash Balance INR')
MONEY=(1,3,4,5,6)
SCHEMA=1

def fingerprint(s):
    facts={k:v for k,v in s.items() if k not in ('audit','settings')}
    facts['settings']={k:v for k,v in s['settings'].items() if k!=STORE}
    facts['audit']=[dict(action=a['action'],payload=a['payload']) for a in s['audit'] if a['action'] not in ('CHANGE_SET','STATE_CHECKPOINT') and not a['action'].startswith('DAILY_CONSOLIDATION_')]
    return hashlib.sha256(json.dumps(facts,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def definitions(s):
    details=s['account_details']
    return dict(revenue=[a['code'] for a in s['accounts'] if a['kind']=='Revenue'],
        patient_revenue=[a['code'] for a in s['accounts'] if a['kind']=='Revenue' and details[a['code']]['group'] in ('Healthcare revenue','Pharmacy revenue','Resort revenue')],
        opex=[a['code'] for a in s['accounts'] if a['kind']=='Expense' and details[a['code']]['group'] not in ('Finance costs','Income tax')],
        capex=[a['code'] for a in s['accounts'] if a['kind']=='Asset' and details[a['code']]['group'] in ('PPE','CWIP')],
        cash=[a['code'] for a in s['accounts'] if details[a['code']]['group']=='Cash and bank'],
        note='Revenue and Opex are booked amounts excluding opening/year-close families. Opex includes salary expense and petty-cash expense once, including depreciation and cost of sales; excludes finance costs and income tax. Stock, advances and salary/payable settlements are not expensed again. Capex is booked PPE/CWIP additions net purchase reversals, excluding internal capitalisation and disposals; not a cash-spend measure. Collections are net customer receipts (including tax/advances and recorded other-payment clearing), excluding bank settlements, funding and internal transfers. Patient counts are active customer sales-receipt entries as of Through; not unique patients. Cash Balance is cash plus banks, excludes unbanked UPI/card clearing; foreign cash uses recorded INR carrying amounts. The columns are not a cash-flow bridge. Zero activity does not certify complete books.')

def build(s,start,end):
    core.verify_audit(s);first=date.fromisoformat(start);last=date.fromisoformat(end)
    if start> end or (last-first).days>3660:raise ValueError('Choose a valid range of at most ten years.')
    d=definitions(s);roots=gst._roots(s);byid={v['id']:v for v in s['vouchers']};account={a['code']:a for a in s['accounts']};cash=set(d['cash']);channels=cash|{'1110','1120','1130','1140'};business=set(d['patient_revenue'])|{s['patient_control'],'2300'};opex=set(d['opex']);capex=set(d['capex']);revenue=set(d['revenue'])
    db=sqlite3.connect(':memory:');db.executescript('''
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE ledger_lines(voucher TEXT,line INTEGER,date TEXT,unit TEXT,account TEXT,ledger TEXT,debit_paise INTEGER,credit_paise INTEGER,root_voucher TEXT,PRIMARY KEY(voucher,line));
    CREATE TABLE contributions(voucher TEXT,line INTEGER,metric TEXT,amount INTEGER,reason TEXT,PRIMARY KEY(voucher,line,metric));
    CREATE TABLE receipt_sources(receipt_key TEXT,date TEXT,unit TEXT,units INTEGER,voucher TEXT,basis TEXT,PRIMARY KEY(receipt_key,unit));
    CREATE TABLE exclusions(date TEXT,unit TEXT,voucher TEXT,account TEXT,amount_paise INTEGER,reason TEXT);
    CREATE TABLE source_coverage(source TEXT,date TEXT,unit TEXT,reference TEXT,amount_paise INTEGER,reason TEXT);
    CREATE TABLE daily_metrics(date TEXT,unit TEXT,revenue_paise INTEGER,sales_units INTEGER,collections_paise INTEGER,opex_paise INTEGER,capex_paise INTEGER,cash_balance_paise INTEGER,coverage TEXT,PRIMARY KEY(date,unit));
    CREATE INDEX ledger_date_unit ON ledger_lines(date,unit);
    CREATE INDEX exclusions_date ON exclusions(date,unit);
    ''')
    def exclusion(v,l,amount,reason):db.execute('INSERT INTO exclusions VALUES(?,?,?,?,?,?)',(v['date'],l['branch'],v['id'],l['account'],amount,reason))
    service={r['voucher']:r['kind'] for r in s.get('service_revenue',[]) } if isinstance(s.get('service_revenue',[]),list) else {}
    # Service source shape can be a dictionary in older books; audited records are stable.
    for a in s['audit']:
        if a['action']=='SERVICE_REVENUE_RECORDED':service[a['payload']['voucher']]=a['payload']['kind']
    gst_sales={r['voucher_id'] for r in s.get('gst_documents',[]) if r.get('kind')=='Sale' and r.get('voucher_id')}
    net=defaultdict(int)
    for v in s['vouchers']:
        if v['date']<=end:net[roots[v['id']][0]]+=roots[v['id']][1]
    for v in s['vouchers']:
        if v['date']>end:continue
        root,sign=roots[v['id']];original=byid[root];special=original.get('opening') or original.get('closing');orig=original['lines']
        paid=any(l['debit'] and l['account'] in channels for l in orig);refunded=any(l['credit'] and l['account'] in channels for l in orig)
        patient_credit=any(l['credit'] and l['account'] in business for l in orig);patient_debit=any(l['debit'] and l['account'] in business for l in orig)
        known=original.get('source',{}).get('kind')=='daily_sales' or service.get(root) in ('Advance','Direct receipt','Collect bill','Refund advance','Refund earned receipt','Refund bill') or original.get('metadata',{}).get('type') in ('Receipt','Refund')
        countable=known
        known=known or root in gst_sales
        customer=not special and known and (paid and patient_credit or refunded and patient_debit)
        purchase=sum(l['debit']-l['credit'] for l in orig if l['account'] in capex)!=0
        orig_debits={(l['branch'],l['account']) for l in orig if l['account'] in capex and l['debit']}
        for i,l in enumerate(v['lines']):
            code=l['account'];delta=l['debit']-l['credit'];db.execute('INSERT INTO ledger_lines VALUES(?,?,?,?,?,?,?,?,?)',(v['id'],i,v['date'],l['branch'],code,account[code]['name'],l['debit'],l['credit'],root))
            metrics=[]
            if code in cash:metrics.append(('cash',delta,'Recorded cash/bank movement, including opening balances'))
            if not special:
                if code in revenue:metrics.append(('revenue',-delta,'Earned revenue, excluding output tax'))
                if code in opex:metrics.append(('opex',delta,'Booked operating expense; includes salary and petty-cash expense'))
                if customer and code in channels:metrics.append(('collections',delta,'Customer receipt/refund; excludes subsequent settlement'))
                if code in capex and purchase and (l['branch'],code) in orig_debits and (l['debit'] if sign>0 else l['credit']):metrics.append(('capex',delta,'Capital asset addition / acquisition reversal'))
            for metric,amount,reason in metrics:db.execute('INSERT INTO contributions VALUES(?,?,?,?,?)',(v['id'],i,metric,amount,reason))
            if start<=v['date']<=end and not any(m[0] in ('revenue','opex','capex','collections') for m in metrics):
                group=s['account_details'][code]['group']
                reason='Opening/year-close family: excluded from daily operating activity' if special else 'Inventory asset: not Opex until consumed/sold' if group=='Inventory' else 'Finance costs / income tax: outside operating expense definition' if account[code]['kind']=='Expense' else 'Internal capitalisation, disposal or capital reclassification: not a new acquisition' if code in capex else 'Cash/bank leg affects Cash Balance; not a second expense or customer collection' if code in cash else 'Unbanked payment clearing: outside Cash Balance; settlement is not new revenue' if group=='Payment clearing' else 'Balance-sheet/control movement (loan principal, payable, tax, advance or equity): not fresh Revenue/Opex/Capex'
                exclusion(v,l,delta,reason)
        # One active receipt entry, irrespective of payment splits or settlement reports.
        if v['id']==root and not special and countable and customer and paid and patient_credit and net[root]>0 and start<=v['date']<=end:
            units=int(original.get('source',{}).get('row_count',1))
            for unit in sorted({l['branch'] for l in orig if l['account'] in channels and l['debit']}):db.execute('INSERT INTO receipt_sources VALUES(?,?,?,?,?,?)',(root,v['date'],unit,units,root,'Posted receipt-entry proxy; cancellation assessed as of Through'))
    # Source gaps remain explicit; importing bank/reports never creates accounting facts here.
    from . import reconciliation,bank_workbench
    for a in reconciliation.bank_accounts(s):
        for b in reconciliation.outstanding(s,a['code'])[0]:
            if start<=b['date']<=end:db.execute('INSERT INTO source_coverage VALUES(?,?,?,?,?,?)',('Unmatched bank statement',b['date'],b['branch'],b['reference'],b['remaining'],'Unmatched bank row; its entry may already be posted. Match existing books first; no extra financial fact is inferred from narration'))
    seen=set()
    for doc in bank_workbench.documents(s):
        for a in reconciliation.bank_accounts(s):
            for x in bank_workbench.sources(s,a['code'],'ALL',doc['kind'],doc['id'],end):
                if x['kind'] not in ('new_sale','new_payment','error') and x['status']!='BLOCKED':continue
                key=tuple(x.get('docrow',(doc['id'],x['id'])))
                if key in seen:continue
                seen.add(key)
                if not x['date'] or start<=x['date']<=end:db.execute('INSERT INTO source_coverage VALUES(?,?,?,?,?,?)',(doc['filename'],x['date'],x['branch'],x['reference'],x['amount'],x['error'] or 'Uploaded source awaiting posting; excluded from financial metrics'))
    for q in s['queue']:
        rejected=sum(r.get('review')=='REJECTED' for r in q.get('rows',[]))
        if rejected or q.get('status')=='CANCELLED':db.execute('INSERT INTO source_coverage VALUES(?,?,?,?,?,?)',(q.get('filename','Import queue'),'','ALL',q['id'],0,str(rejected)+' rejected rows; batch '+q.get('status','')+' — excluded, never added to metrics'))
        if q.get('status') in ('PROCESSED','POSTED','CANCELLED'):continue
        unposted=[r for r in q.get('rows',[]) if not r.get('voucher') and r.get('review') not in ('POSTED','REJECTED')]
        if unposted:db.execute('INSERT INTO source_coverage VALUES(?,?,?,?,?,?)',(q.get('filename','Import queue'),'', 'ALL',q['id'],0,str(len(unposted))+' import rows without a linked voucher; review import status, not additional patient counts'))
    daily=defaultdict(lambda:defaultdict(int));balances=defaultdict(int);active=set()
    for day,unit,metric,value in db.execute('SELECT l.date,l.unit,c.metric,SUM(c.amount) FROM contributions c JOIN ledger_lines l ON l.voucher=c.voucher AND l.line=c.line GROUP BY l.date,l.unit,c.metric'):
        if day<start and metric=='cash':balances[unit]+=value
        elif day>=start:daily[day,unit][metric]+=value
    for day,unit in db.execute('SELECT DISTINCT date,unit FROM ledger_lines WHERE date>=?',(start,)):active.add((day,unit))
    counts=defaultdict(int);entity_counts=defaultdict(int)
    for key,day,unit,units in db.execute('SELECT receipt_key,date,unit,units FROM receipt_sources'):counts[day,unit]+=units
    for day,n in db.execute('SELECT date,SUM(units) FROM (SELECT date,receipt_key,MAX(units) units FROM receipt_sources GROUP BY date,receipt_key) GROUP BY date'):entity_counts[day]=n
    days=[];day=first;units=list(foundation.branches(s))
    while day<=last:
        text=day.isoformat();days.append(text);totals=defaultdict(int)
        for unit in units:
            values=daily[text,unit];balances[unit]+=values['cash'];values['patients']=counts[text,unit];values['balance']=balances[unit]
            db.execute('INSERT INTO daily_metrics VALUES(?,?,?,?,?,?,?,?,?)',(text,unit,values['revenue'],values['patients'],values['collections'],values['opex'],values['capex'],values['balance'],'Posted activity — completeness not certified' if (text,unit) in active else 'No posted activity — completeness not certified'))
            for k in ('revenue','collections','opex','capex','balance'):totals[k]+=values[k]
        db.execute('INSERT INTO daily_metrics VALUES(?,?,?,?,?,?,?,?,?)',(text,'ALL',totals['revenue'],entity_counts[text],totals['collections'],totals['opex'],totals['capex'],totals['balance'],'Posted activity — completeness not certified' if any((text,u) in active for u in units) else 'No posted activity — completeness not certified'))
        day+=timedelta(days=1)
    meta=dict(schema=SCHEMA,start=start,end=end,source_digest=fingerprint(s),definitions=d,prepared=__import__('datetime').datetime.now(history.INDIA).isoformat(timespec='seconds'),entity=s['settings']['entity'])
    for k,v in meta.items():db.execute('INSERT INTO metadata VALUES(?,?)',(k,json.dumps(v,ensure_ascii=False)))
    db.commit();return db,meta

def refresh(s,start,end):
    db,meta=build(s,start,end)
    try:raw=db.serialize()
    finally:db.close()
    s['settings'][STORE]=dict(metadata=meta,database=base64.b64encode(zlib.compress(raw,6)).decode(),encoding='sqlite-zlib-base64',sha256=hashlib.sha256(raw).hexdigest())
    core.add_audit(s,'DAILY_CONSOLIDATION_REFRESHED',dict(start=start,end=end,source_digest=meta['source_digest'],database_sha256=s['settings'][STORE]['sha256']))
    return meta

def saved(s):
    core.verify_audit(s);store=s['settings'].get(STORE)
    if not store:raise ValueError('Build / refresh the daily database first.')
    raw=base64.b64decode(store['database'],validate=True)
    if store.get('encoding')=='sqlite-zlib-base64':raw=zlib.decompress(raw)
    if hashlib.sha256(raw).hexdigest()!=store['sha256']:raise ValueError('Daily database checksum differs. Rebuild from verified books.')
    db=sqlite3.connect(':memory:');db.deserialize(raw);db.execute('PRAGMA trusted_schema=OFF')
    return db,copy.deepcopy(store['metadata']),store['metadata']['source_digest']!=fingerprint(s)

def pack(s,start,end,unit='ALL',section='Daily table'):
    if unit!='ALL' and unit not in foundation.branches(s):raise ValueError('Select a saved unit.')
    db,meta,stale=saved(s)
    try:
        if start>end or start<meta['start'] or end>meta['end']:raise ValueError('Choose dates inside the saved database range, or rebuild a wider range.')
        result=dict(entity=s['settings']['entity'],registration=copy.deepcopy(s['settings'].get('registration',{})),mode=TITLE+' — '+section,start=start,end=end,branch=unit,scope='All operating units' if unit=='ALL' else foundation.branches(s)[unit],prepared=meta['prepared'],currency='INR',logos=report_branding.snapshot(s),controls={},note=('STALE — rebuild before relying on these figures. ' if stale else '')+meta['definitions']['note'],stale=stale)
        if section=='Daily table':
            result.update(columns=list(HEADERS),money_columns=list(MONEY),rows=[list(r) for r in db.execute('SELECT date,revenue_paise,sales_units,collections_paise,opex_paise,capex_paise,cash_balance_paise FROM daily_metrics WHERE date BETWEEN ? AND ? AND unit=? ORDER BY date',(start,end,unit))])
            sums=[sum(r[i] for r in result['rows']) for i in range(1,6)];result['controls']={'Revenue INR':sums[0],'Collections INR':sums[2],'Opex INR':sums[3],'Capex INR':sums[4],'Closing Cash Balance INR':result['rows'][-1][-1] if result['rows'] else 0};result['sales_units_total']=sums[1];result['note']+=' Sales Units total in this range: '+str(sums[1])+'.' 
        elif section=='What is left out':
            sql='SELECT date,unit,voucher,account,amount_paise,reason FROM exclusions WHERE date BETWEEN ? AND ?';args=[start,end]
            if unit!='ALL':sql+=' AND unit=?';args.append(unit)
            result.update(columns=['Date','Unit','Voucher','Account','Signed INR','Reason'],money_columns=[4],rows=[list(r) for r in db.execute(sql+' ORDER BY date,voucher,account',args)])
        elif section=='Source gaps':
            sql="SELECT source,date,unit,reference,amount_paise,reason FROM source_coverage WHERE (date='' OR date BETWEEN ? AND ?)";args=[start,end]
            if unit!='ALL':sql+=" AND unit IN (?, 'ALL')";args.append(unit)
            result.update(columns=['Source','Date','Unit','Reference','INR (informational)','Reason'],money_columns=[4],rows=[list(r) for r in db.execute(sql,args)])
        elif section=='Source drilldown':
            sql='SELECT l.date,l.unit,l.voucher,l.account,l.ledger,c.metric,c.amount,c.reason FROM ledger_lines l JOIN contributions c ON c.voucher=l.voucher AND c.line=l.line WHERE l.date BETWEEN ? AND ?';args=[start,end]
            if unit!='ALL':sql+=' AND l.unit=?';args.append(unit)
            result.update(columns=['Date','Unit','Voucher','Account','Ledger','Metric','INR','Basis'],money_columns=[6],rows=[list(r) for r in db.execute(sql+' ORDER BY l.date,l.voucher,l.line,c.metric',args)])
        else:raise ValueError('Choose a daily database section.')
        return result
    finally:db.close()

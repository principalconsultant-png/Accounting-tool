"""Read-only source uploads and atomic selected bank/source reconciliation."""
import copy,csv,io,hashlib,uuid
from collections import defaultdict
from datetime import date,datetime
from pathlib import Path
from . import ap,ap_bulk,bulk_import,core,foundation,receipt_import as receipts,reconciliation as bank

PAYMENT_FIELDS=('vendor_name','invoice_number','invoice_date','payment_date','branch','bank_account','amount','payment_reference','basis')
PAYMENT_HEADERS=('Vendor Name','Invoice Number','Invoice Date','Actual Payment Date','Operating Unit','Bank Ledger','Paid Amount INR','Transfer Reference','Accounting Review Basis')


def documents(s,kind=None):return [a['payload'] for a in s['audit'] if a['action']=='BANK_SOURCE_REPORT_UPLOADED' and (not kind or a['payload']['kind']==kind)]
def document(s,key):
    d=next((d for d in documents(s) if d['id']==key),None)
    if not d:raise ValueError('Choose an uploaded source report.')
    return d


def payment_values(raw):
    if any(str(v).startswith('=') for v in raw.values()):raise ValueError('Use literal payment values, not formulas.')
    v={k:ap_bulk._string(raw.get(k,'')) for k in PAYMENT_FIELDS}
    for k in ('invoice_date','payment_date'):ap.day(v[k])
    if not all(v[k] for k in ('vendor_name','invoice_number','branch','bank_account','payment_reference')):raise ValueError('Vendor, invoice, unit, bank account and actual transfer reference are required.')
    v['amount']=ap.positive(v['amount']);return v


@ap.atomic
def upload(s,raw,filename,kind):
    if kind not in ('Sales receipts','Invoice payments'):raise ValueError('Choose sales or invoice payment report.')
    digest=hashlib.sha256(raw).hexdigest();prior=next((d for d in documents(s,kind) if d['digest']==digest),None)
    if prior:return copy.deepcopy(prior)
    sheet='Receipts' if kind=='Sales receipts' else 'Payments';headers,rows,label=bulk_import._read(raw,filename,sheet);mapping={}
    if kind=='Sales receipts':
        if set(headers)!=set(receipts.HEADERS):raise ValueError('Use the standard Sales receipt report template (Receipts sheet); preserve all headings.')
    else:
        aliases={ap.norm(h):k for h,k in zip(PAYMENT_HEADERS,PAYMENT_FIELDS)};aliases.update({ap.norm(k):k for k in PAYMENT_FIELDS})
        for i,h in enumerate(headers):
            key=aliases.get(ap.norm(h))
            if not key or key in mapping:raise ValueError('Use unique standard invoice payment headings: '+h)
            mapping[key]=i
        if set(mapping)!=set(PAYMENT_FIELDS):raise ValueError('Use all nine invoice payment template columns.')
    parsed=[];seen=set()
    for num,row in enumerate(rows,2):
        if not any(v not in (None,'') for v in row):continue
        source={h:ap_bulk._string(row[i]) if i<len(row) else '' for i,h in enumerate(headers)};result=dict(source_row=num,raw=source,error='')
        try:
            if len(row)>len(headers) and any(v not in (None,'') for v in row[len(headers):]):raise ValueError('Extra source cells beyond the headings.')
            if kind=='Sales receipts':
                r=receipts._parse(s,dict(zip(headers,list(row)+[None]*len(headers))),num);identity=receipts.identity(r)
            else:
                r=payment_values({k:row[i] if i<len(row) else '' for k,i in mapping.items()})
                if r['bank_account'] not in {a['code'] for a in bank.bank_accounts(s)}:raise ValueError('Bank Ledger must be an active INR bank account code (for example 1010), not its name. Correct the source account or activate the bank ledger.')
                identity=(ap.norm(r['vendor_name']),ap.norm(r['invoice_number']),core.financial_year(r['invoice_date']),r['payment_date'],r['branch'],r['bank_account'],ap.norm(r['payment_reference']))
            if identity in seen:raise ValueError('Duplicate receipt/payment identity within this report. Correct the file; do not reconcile it twice.')
            seen.add(identity);result['record']=r
        except (ValueError,KeyError,TypeError) as error:result['error']=str(error)
        parsed.append(result)
    if not parsed:raise ValueError('No report transaction rows found.')
    d=dict(id=str(uuid.uuid4()),kind=kind,filename=Path(filename).name,digest=digest,sheet=label,rows=parsed)
    core.add_audit(s,'BANK_SOURCE_REPORT_UPLOADED',d);return copy.deepcopy(d)


def _same_lines(a,b):
    def total(lines):
        result=defaultdict(int)
        for l in lines:result[l['branch'],l['account']]+=l['debit']-l['credit']
        return {k:v for k,v in result.items() if v}
    return total(a)==total(b)


def receipt_voucher(s,r,index=None,known=None):
    matches=index.get((ap.norm(r['receipt']),core.financial_year(r['date']),r['branch']),[]) if index is not None else [v for v in s['vouchers'] if ap.norm(v.get('metadata',{}).get('reference',''))==ap.norm(r['receipt']) and core.financial_year(v['date'])==core.financial_year(r['date']) and any(l['branch']==r['branch'] for l in v['lines']) and not v.get('reverses')]
    exact=[v for v in matches if v['date']==r['date'] and _same_lines(v['lines'],receipts.lines(s,r))]
    if len(exact)==1:return exact[0]
    if matches:raise ValueError('Receipt already exists but date/amount/payment split differs or is ambiguous. Correct/review the original Sales receipt entry.')
    if receipts.identity(r) in (known if known is not None else receipts.known(s)):raise ValueError('Receipt is already in a pending/processed sales batch. Complete or correct that batch in Sales receipt first.')
    return None


def invoice_for(s,r):
    vendors=[v for v in ap.data(s)['vendors'] if ap.norm(r['vendor_name']) in {ap.norm(n) for n in [v['name'],*v.get('previous_names',[])]}]
    if len(vendors)!=1:raise ValueError('Vendor name does not match one Vendor master. Correct spelling or create the genuine vendor first.')
    matches=[v for v in ap.data(s)['invoices'] if v['vendor']==vendors[0]['id'] and ap.norm(v['reference'])==ap.norm(r['invoice_number']) and core.financial_year(v['invoice_date'])==core.financial_year(r['invoice_date']) and v['branch']==r['branch']]
    if len(matches)!=1:raise ValueError('Invoice/unit/fiscal year does not identify one registered AP invoice. Enter the invoice before recording its payment.')
    if matches[0]['invoice_date']!=r['invoice_date']:raise ValueError('Invoice date differs from the registered invoice; review the source.')
    return matches[0]


def payment_link(s,r,invoice):
    from . import tds
    net=tds._net(s);matches=[];other=[]
    for p in ap.data(s)['payments']:
        if p['bank_account']!=r['bank_account'] or net.get(p['voucher'],0)!=1:continue
        item=next((i for i in p['items'] if i['invoice']==invoice['id'] and i['amount']==r['amount']),None)
        if item:
            if p['date']==r['payment_date']:matches.append(p)
            else:other.append(p)
    exact=[p for p in matches if ap.norm(p['reference'])==ap.norm(r['payment_reference'])]
    if len(exact)==1:return exact[0]
    if len(matches)==1:return matches[0]
    if matches or other and ap.position(s,invoice)['remaining']<r['amount']:raise ValueError('A payment for this invoice/amount already exists on a different date or is ambiguous. Correct the original AP payment; no duplicate payment will be created.')
    # Never create a second bank entry where an unallocated journal already identifies the transfer.
    if any(v['date']==r['payment_date'] and ap.norm(v.get('metadata',{}).get('reference',''))==ap.norm(r['payment_reference']) and any(l['account']==r['bank_account'] and l['credit'] for l in v['lines']) for v in s['vouchers']):raise ValueError('This bank transfer is already in the books but is not allocated to this AP invoice. Link its exact existing voucher in AP first.')
    return None


def _row(key,kind,date,branch,reference,label,amount,**kw):return dict(id=key,kind=kind,date=date,branch=branch,reference=reference,label=label,amount=amount,status='READY',error='',**kw)


def sources(s,account,scope,kind,doc_id=None,through=None):
    """One selectable row per actual bank leg/receipt payment split; never duplicate a leg."""
    _,books=bank.outstanding(s,account,scope);books={b['key']:b for b in books};clear={}
    for channel in (('1000','1110','1120') if kind=='Sales receipts' else ()):
        for x in bank.clearing_items(s,channel,scope,through):
            if x['remaining']>0:clear[x['key']]=dict(x,channel=channel)
    out={};byid={v['id']:v for v in s['vouchers']}
    books_by_voucher=defaultdict(list);clear_by_voucher=defaultdict(list)
    for x in books.values():books_by_voucher[x['voucher']].append(x)
    for x in clear.values():clear_by_voucher[x['voucher']].append(x)
    def add_book(x,label='',docrow=None):
        key='book:'+x['key'];out[key]=_row(key,'book',x['date'],x['branch'],x['reference'],label or x['payee'] or x['narration'],x['remaining'],book_key=x['key'],voucher=x['voucher'],docrow=docrow)
    def add_sale(v,r=None,docrow=None):
        for x in books_by_voucher[v['id']]:
            if x['remaining']>0:add_book(x,(r['receipt']+' | '+r['party']) if r else '',docrow)
        for x in clear_by_voucher[v['id']]:
            key='clearing:'+x['key'];out[key]=_row(key,'clearing',x['date'],x['branch'],r['receipt'] if r else v.get('metadata',{}).get('reference',''),({'1000':'Cash deposit','1110':'UPI','1120':'Card'}[x['channel']])+' | '+(r['party'] if r else v['narration']),x['remaining'],clearing_key=x['key'],channel=x['channel'],voucher=v['id'],docrow=docrow)
    def add_payment(p,docrow=None):
        labels='; '.join(ap.invoice(s,i['invoice'])['vendor_name']+' / '+ap.invoice(s,i['invoice'])['reference'] for i in p['items'])
        for x in books_by_voucher[p['voucher']]:
            if x['remaining']<0:add_book(x,labels,docrow)
    if not doc_id:
        if kind=='Invoice payments':
            for p in ap.data(s)['payments']:
                if p['bank_account']==account:add_payment(p)
        elif kind=='All book movements':
            for x in books.values():add_book(x)
        else:
            pettyids={a['payload']['voucher'] for a in s['audit'] if a['action']=='PETTY_CASH_RECORDED'}
            saleids={v['id'] for v in s['vouchers'] if v.get('source',{}).get('kind')=='daily_sales' or v.get('metadata',{}).get('type')=='Receipt' or any(l['debit'] and l['account'] in ('1000','1110','1120',account) for l in v['lines']) and any(next(a['kind'] for a in s['accounts'] if a['code']==l['account'])=='Revenue' for l in v['lines'])}
            for key in saleids-pettyids:add_sale(byid[key])
        return sorted(out.values(),key=lambda x:(x['date'],x['id']))
    doc=document(s,doc_id)
    if doc['kind']!=kind:raise ValueError('Report type and selected source file differ.')
    receipt_index=defaultdict(list);receipt_known=receipts.known(s) if kind=='Sales receipts' else set()
    if kind=='Sales receipts':
        for v in s['vouchers']:
            ref=v.get('metadata',{}).get('reference','')
            if ref and not v.get('reverses'):
                for branch in {l['branch'] for l in v['lines']}:receipt_index[ap.norm(ref),core.financial_year(v['date']),branch].append(v)
    for i,row in enumerate(doc['rows']):
        key='report:'+doc_id+':'+str(i);raw=row['raw'];rec=row.get('record');base=dict(docrow=(doc_id,i))
        try:
            if row['error']:raise ValueError(row['error'])
            branch=rec['branch']
            if scope!='ALL' and branch!=scope:continue
            if kind=='Sales receipts':
                v=receipt_voucher(s,rec,receipt_index,receipt_known)
                if v:add_sale(v,rec,(doc_id,i))
                else:
                    for mode,amount in rec['payments'].items():
                        if not amount:continue
                        channel={'cash':'1000','upi':'1110','card':'1120','bank':account}.get(mode)
                        part=key+':'+mode;out[part]=_row(part,'new_sale',rec['date'],branch,rec['receipt'],mode.upper()+' | '+rec['party'],amount,status_override='Needs sales entry',channel=channel,mode=mode,**base)
                        if channel is None:out[part].update(status='BLOCKED',error='Other receipt clearing needs its dedicated review workflow.')
                        if mode=='bank' and account!='1010':out[part].update(status='BLOCKED',error='Standard sales bank column posts to 1010. Choose 1010 or review the correct bank source first.')
            else:
                if rec['bank_account']!=account:continue
                invoice=invoice_for(s,rec);p=payment_link(s,rec,invoice)
                if p:add_payment(p,(doc_id,i))
                else:
                    if rec['payment_date']<invoice['accounting_date']:raise ValueError('Actual payment date precedes the invoice accrual date '+invoice['accounting_date']+'. Review its historical accounting date first.')
                    if min(ap.position(s,invoice,rec['payment_date'])['remaining'],ap.position(s,invoice)['remaining'])<rec['amount']:raise ValueError('Paid amount exceeds the invoice dated/current outstanding balance. Review prior payments, cancellation or allocation before reconciling.')
                    out[key]=_row(key,'new_payment',rec['payment_date'],branch,rec['payment_reference'],rec['vendor_name']+' / '+rec['invoice_number'],-rec['amount'],invoice=invoice['id'],status_override='Needs AP payment',**base)
        except (ValueError,KeyError) as error:
            out[key]=_row(key,'error',str((rec or {}).get('date',(rec or {}).get('payment_date',''))),str((rec or {}).get('branch','')),str((rec or {}).get('receipt',(rec or {}).get('payment_reference',''))),str(raw.get('Vendor Name',raw.get('party','Source row '+str(row['source_row'])))),0,**base);out[key].update(status='BLOCKED',error=str(error))
    return sorted(out.values(),key=lambda x:(x['date'],x['id']))


def _post_sales(s,keys,basis):
    if not keys:return {}
    if len({key[0] for key in keys})!=1:raise ValueError('Choose one sales source report at a time.')
    doc=document(s,keys[0][0]);out=io.StringIO();writer=csv.writer(out);writer.writerow(receipts.HEADERS)
    for _,index in keys:writer.writerow([doc['rows'][index]['raw'].get(k,'') for k in receipts.HEADERS])
    q=receipts.stage(s,out.getvalue().encode(),'Reconcile-'+Path(doc['filename']).stem+'.csv');receipts.review(s,q['id'],list(range(len(q['rows']))),True,basis,True);receipts.post(s,q['id']);posted=[v for v in s['vouchers'] if v.get('source',{}).get('document_id')==q['id']];result={}
    for key,row in zip(keys,q['rows']):
        v=next(v for v in posted if v['source']['record_id']==row['key']);result[key]=v
        core.add_audit(s,'BANK_REPORT_SALE_LINKED',dict(report=doc['id'],source_row=doc['rows'][key[1]]['source_row'],voucher=v['id']))
    return result


def _match_bank_legs(s,bank_ids,book_keys,account,scope):
    banks=[b for b in bank.outstanding(s,account,scope)[0] if b['id'] in bank_ids];books=[b for b in bank.outstanding(s,account,scope)[1] if b['key'] in book_keys]
    if len(books)!=len(book_keys):raise ValueError('A selected posted movement is already matched or missing.')
    capacity={b['id']:abs(b['remaining']) for b in banks};matches=[]
    for book in sorted(books,key=lambda b:(b['date'],ap.norm(b['reference']),b['key'])):
        sign=1 if book['remaining']>0 else -1;need=abs(book['remaining']);allocated=[]
        def preference(b):
            exact=bool(book['reference']) and ap.norm(book['reference'])==ap.norm(b['reference']);near=bank._date_near(s,book['date'],b['date']);gap=abs((date.fromisoformat(book['date'])-date.fromisoformat(b['date'])).days)
            return (not exact,not near,gap,b['date'],b['id'])
        for b in sorted(banks,key=preference):
            if b['branch']!='ALL' and b['branch']!=book['branch']:continue
            take=min(need,capacity[b['id']])
            if take:allocated.append(dict(b,remaining=sign*take));capacity[b['id']]-=take;need-=take
            if not need:break
        if need:raise ValueError('Posted source amounts exceed selected remaining bank capacity.')
        matches.append(bank._record_match(s,allocated,[book]))
    return matches


def _settle_pool(s,banks,parts,fees,partial_cash=False):
    """Split selected clearing lines over bank deposits, preserving every bank date."""
    fee_by_bank=bank._split(fees,{b['id']:b['remaining'] for b in banks}) if fees else {};pool=[dict(p) for p in sorted(parts,key=lambda p:(p['date'],p['clearing_key']))];matches=[]
    for selected in sorted(banks,key=lambda b:(b['date'],b['id'])):
        live=next((b for b in bank.outstanding(s,selected['bank_account'])[0] if b['id']==selected['id']),None)
        if not live:continue
        fee=fee_by_bank.get(live['id'],0);need=live['remaining']+fee;alloc=[];bygroup=defaultdict(int)
        narration=ap.norm(live['narration']);preferred='1110' if 'upi' in narration else '1120' if 'card' in narration or 'terminal' in narration else '1000' if 'cash' in narration else None
        ordered=sorted(pool,key=lambda p:(p['channel']!=preferred,p['date'],p['clearing_key'])) if preferred else pool
        for p in ordered:
            if not need:break
            if p['amount']<=0 or p['date']>live['date']:continue
            if live['branch']!='ALL' and live['branch']!=p['branch']:continue
            take=min(need,p['amount']);alloc.append(dict(key=p['clearing_key'],amount=take,account=p['channel']));bygroup[p['branch'],p['channel']]+=take;p['amount']-=take;need-=take
        if need:
            eligible=live['remaining']+fee-need
            later=sum(p['amount'] for p in pool if p['date']>live['date'] and (live['branch']=='ALL' or live['branch']==p['branch']))
            raise ValueError('Deposit dated '+live['date']+' requires '+core.rupees(live['remaining']+fee)+' including reviewed fees; selected unallocated receipts available by that date for '+('all operating units' if live['branch']=='ALL' else live['branch'])+' total '+core.rupees(eligible)+'. Shortfall '+core.rupees(need)+'. Later receipts '+core.rupees(later)+' cannot fund this earlier deposit. Select the missing earlier receipts, check the deposit date/unit, or review opening cash and other cash movements. Receipts from multiple earlier days are allowed. Nothing saved.')
        branchgross=defaultdict(int)
        for (branch,channel),gross in bygroup.items():
            available=core.balances(s,live['date'],branch)[channel]
            if available<gross:raise ValueError('Deposit '+live['date']+' needs '+core.rupees(gross)+' from '+branch+' / '+channel+', but the dated book balance is '+core.rupees(available)+'. Shortfall '+core.rupees(gross-available)+'. Review cash expenses, refunds, prior deposits and opening balances. Nothing saved.')
            branchgross[branch]+=gross
        branchfees=bank._split(fee,branchgross) if fee else {};lines=[]
        for branch,gross in branchgross.items():
            if gross-branchfees.get(branch,0):lines.append(dict(account=live['bank_account'],branch=branch,debit=gross-branchfees.get(branch,0),credit=0))
            if branchfees.get(branch):lines.append(dict(account='4560',branch=branch,debit=branchfees[branch],credit=0))
        for (branch,channel),gross in bygroup.items():lines.append(dict(account=channel,branch=branch,debit=0,credit=gross))
        v=core.post(s,live['date'],'Reviewed selected sales settlement '+live['reference'],lines,metadata=dict(type='Transfer',reference=live['reference'],bank_account=live['bank_account'],source='Bank settlement'))
        books=[dict(x,remaining=x['amount']) for x in bank.book_items(s,live['bank_account']) if x['voucher']==v['id']];matches.append(bank._record_match(s,[live],books,'settlement',v['id'],alloc))
    remaining=sum(p['amount'] for p in pool)
    if remaining and not partial_cash:raise ValueError('Selected receipt allocations were not fully consumed. Nothing reconciled.')
    return matches,remaining


def _match_charged_books(s,banks,bookkeys,account,scope,fees,basis):
    if len(banks)!=1:raise ValueError('For bank charges against posted bank entries/invoice payments, select one bank transaction at a time.')
    live=banks[0];books=[b for b in bank.outstanding(s,account,scope)[1] if b['key'] in bookkeys]
    if len(books)!=len(bookkeys):raise ValueError('Selected book movements changed. Refresh before posting charges.')
    if live['branch']!='ALL' and any(b['branch']!=live['branch'] for b in books):raise ValueError('Bank charges and selected sources must belong to the statement operating unit.')
    weights=defaultdict(int)
    for b in books:weights[b['branch']]+=abs(b['remaining'])
    allocations=bank._split(fees,weights);lines=[]
    for branch,amount in allocations.items():
        if amount:lines.extend([dict(account='4560',branch=branch,debit=amount,credit=0),dict(account=account,branch=branch,debit=0,credit=amount)])
    voucher=core.post(s,live['date'],'Reviewed reconciliation bank charges '+live['reference']+' | '+basis,lines,metadata=dict(type='Payment',reference=live['reference'],bank_account=account,source='Bank charges'))
    charges=[dict(b,remaining=b['amount']) for b in bank.book_items(s,account,scope) if b['voucher']==voucher['id']]
    return [bank._record_match(s,[live],books+charges,'adjustment',voucher['id'])]


def channel(row,side):
    """Structured source channels first; bank channels are narration search aids only."""
    if side=='source':
        code=row.get('channel')
        if code in ('1110','1120','1000'):return {'1110':'UPI','1120':'Card','1000':'Cash'}[code]
        if row.get('mode') in ('upi','card','cash'):return row['mode'].title() if row['mode']!='upi' else 'UPI'
    text=(row.get('narration','')+' '+row.get('label','')+' '+row.get('reference','')).casefold()
    if 'upi' in text:return 'UPI'
    if any(t in text for t in ('card','terminal','pos ')):return 'Card'
    if 'cash' in text:return 'Cash'
    if any(t in text for t in ('neft','rtgs','imps')):return 'Bank transfer'
    return 'Other'


@ap.atomic
def reconcile(s,account,sid,kind,doc_id,bank_ids,source_ids,basis,fees_minor=0,allow_date_difference=False,partial_cash=False):
    if not basis.strip():raise ValueError('Enter the reconciliation/source review basis.')
    if not bank_ids or not source_ids or len(set(bank_ids))!=len(bank_ids) or len(set(source_ids))!=len(source_ids):raise ValueError('Tick one or more bank transactions and corresponding source transactions.')
    statement=bank.statement(s,sid) if sid else None;scope=statement['scope'] if statement else 'ALL'
    if statement and (statement['bank_account']!=account or statement['status']!='OPEN' or not set(bank_ids)<=set(statement['row_ids'])):raise ValueError('Choose transactions from the selected open bank statement.')
    banks=[b for b in bank.outstanding(s,account,scope)[0] if b['id'] in bank_ids]
    if len(banks)!=len(bank_ids):raise ValueError('A bank transaction is already matched, missing or outside scope. Refresh selections.')
    if any((b['remaining']>0)!=(banks[0]['remaining']>0) for b in banks):raise ValueError('Select deposits or withdrawals in one action; do not net unrelated transactions.')
    available={x['id']:x for x in sources(s,account,scope,kind,doc_id,statement['through'] if statement else None)}
    if any(k not in available for k in source_ids):raise ValueError('A selected source is already reconciled or changed. Refresh selections.')
    selected=[available[k] for k in source_ids]
    if any(x['status']=='BLOCKED' for x in selected):raise ValueError(next(x['error'] for x in selected if x['status']=='BLOCKED'))
    if any((x['amount']>0)!=(banks[0]['remaining']>0) for x in selected):raise ValueError('Deposit sources and invoice withdrawals must be reconciled separately.')
    if type(fees_minor)!=int or fees_minor<0:raise ValueError('Reviewed bank charges must be nonnegative INR.')
    bt=sum(b['remaining'] for b in banks);st=sum(x['amount'] for x in selected)
    if partial_cash and (kind!='Sales receipts' or bt<=0 or fees_minor or any(not (x['kind']=='clearing' and x.get('channel')=='1000' or x['kind']=='new_sale' and x.get('mode')=='cash') for x in selected)):raise ValueError('Partial cash deposit requires only cash receipts and positive bank deposits, with bank charges zero. Review actual charges separately; cash retained is not an expense.')
    if st-fees_minor!=bt and not (partial_cash and st>=bt):raise ValueError('Selected source '+core.rupees(st)+' minus reviewed fees '+core.rupees(fees_minor)+' does not equal bank '+core.rupees(bt)+'. No rounding or balancing entry is guessed.')
    for x in selected:
        near=any(bank._date_near(s,x['date'],b['date']) for b in banks)
        if (x['kind'] in ('book','new_payment') or x['kind']=='new_sale' and x.get('mode')=='bank') and not near and not allow_date_difference:raise ValueError('Source date '+x['date']+' / reference differs from the selected bank dates. Correct an entry-date error, or explicitly allow a reviewed timing difference.')
    before=len(s['vouchers']);newpay=defaultdict(list)
    sale_keys=list(dict.fromkeys(tuple(x['docrow']) for x in selected if x['kind']=='new_sale'));sales=_post_sales(s,sale_keys,basis)
    for x in selected:
        if x['kind']=='new_payment':
            rec=document(s,x['docrow'][0])['rows'][x['docrow'][1]]['record'];newpay[rec['payment_date'],rec['bank_account'],rec['payment_reference']].append((x,rec))
    payment_vouchers={}
    for (day,acct,ref),items in newpay.items():
        p=ap.pay(s,dict(date=day,bank_account=acct,reference=ref,items=[dict(invoice=x['invoice'],amount=str(rec['amount']//100)+'.'+str(rec['amount']%100).zfill(2)) for x,rec in items],reviewed=True,basis=basis))
        for x,rec in items:payment_vouchers[x['id']]=p['voucher']
    # Atomic helpers replace the candidate dictionary, so re-read facts after posting.
    bookkeys=set();parts=[]
    for x in selected:
        if x['kind']=='book':bookkeys.add(x['book_key'])
        elif x['kind']=='clearing':parts.append(dict(x))
        elif x['kind']=='new_payment':
            bookkeys.update(b['key'] for b in bank.book_items(s,account,scope) if b['voucher']==payment_vouchers[x['id']] and b['branch']==x['branch'])
        elif x['kind']=='new_sale':
            v=sales[tuple(x['docrow'])]
            if x['mode']=='bank':bookkeys.update(b['key'] for b in bank.book_items(s,account,scope) if b['voucher']==v['id'])
            else:
                item=next((c for c in bank.clearing_items(s,x['channel'],scope) if c['voucher']==v['id']),None)
                if not item:raise ValueError('Selected receipt clearing line is missing or already settled.')
                parts.append(dict(x,kind='clearing',clearing_key=item['key']))
    matches=[];cash_remaining=0
    if bookkeys and not parts and fees_minor:
        matches.extend(_match_charged_books(s,banks,bookkeys,account,scope,fees_minor,basis))
    elif bookkeys:matches.extend(_match_bank_legs(s,bank_ids,bookkeys,account,scope))
    if parts:
        remaining=[b for b in bank.outstanding(s,account,scope)[0] if b['id'] in bank_ids]
        if not remaining or any(b['remaining']<=0 for b in remaining):raise ValueError('Only positive settlement deposits can receive clearing receipts.')
        settlements,cash_remaining=_settle_pool(s,remaining,parts,fees_minor,partial_cash);matches.extend(settlements)

    if any(b['id'] in bank_ids for b in bank.outstanding(s,account,scope)[0]):raise ValueError('Selected bank transactions are not fully reconciled. Nothing saved.')
    core.add_audit(s,'BANK_WORKBENCH_RECONCILED',dict(bank_ids=bank_ids,source_ids=source_ids,report=doc_id,kind=kind,review_basis=basis,fees_minor=fees_minor,matches=[m['id'] for m in matches],new_vouchers=len(s['vouchers'])-before,allow_date_difference=allow_date_difference,partial_cash=partial_cash,cash_remaining_minor=cash_remaining))
    return dict(bank_transactions=len(bank_ids),source_transactions=len(source_ids),bank_total_INR=core.rupees(bt),source_total_INR=core.rupees(st),reviewed_fees_INR=core.rupees(fees_minor),difference_INR='0.00',cash_remaining_INR=core.rupees(cash_remaining),partial_cash=partial_cash,new_journals=len(s['vouchers'])-before,matches=len(matches))


def payment_template(path):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(PAYMENT_HEADERS)
        return
    if path.suffix.lower()!='.xlsx':raise ValueError('Save invoice payment template as XLSX or CSV.')
    from openpyxl import Workbook
    from openpyxl.styles import Alignment,Font,PatternFill
    w=Workbook();ws=w.active;ws.title='Payments';ws.append(PAYMENT_HEADERS);ws.freeze_panes='C2';ws.auto_filter.ref='A1:I1001'
    for c in ws[1]:c.font=Font(bold=True,color='154C8A');c.fill=PatternFill('solid',fgColor='E8F0FC');c.alignment=Alignment(wrap_text=True)
    ws.row_dimensions[1].height=35
    for col in 'ABCDEFGHI':ws.column_dimensions[col].width=30
    for row in range(2,1002):
        for col in (2,6,8):ws.cell(row,col).number_format='@'
        for col in (3,4):ws.cell(row,col).number_format='yyyy-mm-dd'
        ws.cell(row,7).number_format='#,##0.00'
    help=w.create_sheet('Instructions');help.append(['Topic','Instruction'])
    for r in [('Rows','One actual paid amount per vendor invoice per transfer. Do not include unpaid invoices. All nine headings required; upload is read-only and creates no journal.'),('Vendor/invoice','Exact saved vendor name, registered invoice number and invoice date. Unit must match that AP invoice. Invoice date identifies the fiscal year; actual payment date is not the date of data entry.'),('Bank/ref','Actual bank ledger code and full transfer/UTR reference. Preserve leading zeros as text. Paid Amount INR must be positive. No formulas.'),('Grouped transfer','Several invoices paid by one transfer use the same actual payment date/bank/reference. Select all related invoice rows and the corresponding bank withdrawal(s); selected totals must agree.'),('Existing payment','Already-posted AP payments link to their existing bank ledger movement; never post a second payment. Conflicting dates/amounts or unallocated bank vouchers require correction in AP.'),('New payment','If not recorded, the invoice must already exist and have sufficient dated outstanding capacity. Automatic reconcile previews a normal AP payment using the source historical date and bank reference before approval.'),('Review','Accounting Review Basis records the bank/payment evidence. Reconciliation screen also requires confirmation/basis. Upload does not post or match. Duplicate source identities in one file are blocked; exact file reupload reuses its saved report.'),('Safety','Use the standard Sales receipt report for sales. Bank statements are uploaded independently with balances/period mapping. Do not import the same bank period twice.')]:help.append(r)
    help.column_dimensions['A'].width=28;help.column_dimensions['B'].width=115
    for row in help:
        for c in row:c.alignment=Alignment(wrap_text=True,vertical='top')
        help.row_dimensions[row[0].row].height=45
    w.save(path);w.close()

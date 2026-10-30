"""Offline Vaikom FX receipts. All ledger amounts remain integer INR paise."""
import copy
import csv
import io
import uuid
from datetime import date
from decimal import Decimal,ROUND_HALF_UP,InvalidOperation,localcontext
from . import core,foundation

# ISO minor-unit precision for supported receipt currencies; INR is the base.
CURRENCIES={c:2 for c in ('USD','EUR','GBP','AED','AUD','CAD','CHF','SGD','SAR','QAR','CNY','NZD','HKD','MYR','THB','ZAR','SEK','NOK','DKK','BDT','LKR','NPR','MVR','MUR','EGP','KES','NGN','RUB','ILS','IDR','PHP','TWD','TRY','BRL','MXN','PLN','CZK','HUF','PKR')}
CURRENCIES.update(JPY=0,KRW=0,VND=0,KWD=3,BHD=3,OMR=3,JOD=3,TND=3,IQD=3,LYD=3)


def day(value):
    if date.fromisoformat(value).isoformat()!=value:raise ValueError('Use YYYY-MM-DD for the payment/rate date.')
    return value


def decimal(value,places,label,positive=True):
    try:
        d=Decimal(str(value).replace(',','').strip())
        if not d.is_finite() or d<0 or (positive and d==0) or d>=Decimal('1e18'):raise ValueError()
        quantum=Decimal(1).scaleb(-places)
        if d!=d.quantize(quantum):raise ValueError()
        return d
    except (InvalidOperation,ValueError):raise ValueError(f'{label}: enter a {"positive" if positive else "non-negative"} amount with at most {places} decimals.') from None


def currency(value):
    value=str(value).strip().upper()
    if value not in CURRENCIES:raise ValueError('Select a supported foreign currency; INR is the base currency.')
    return value


def text(value):return format(value,'f')


def save_rate(state,payment_date,code,inr_per_unit,source):
    day(payment_date);code=currency(code);rate=decimal(inr_per_unit,8,'INR per 1 '+code)
    source=source.strip()
    if not source:raise ValueError('Enter the rate source, such as the dated bank advice. No live rate is assumed.')
    rates=state.get('fx_rates',[])
    same=[r for r in rates if r['date']==payment_date and r['currency']==code]
    if same and Decimal(same[-1]['inr_per_unit'])==rate and same[-1]['source']==source:return copy.deepcopy(same[-1])
    entry={'id':str(uuid.uuid4()),'date':payment_date,'currency':code,'inr_per_unit':text(rate),'source':source,'revision':len(same)+1}
    state.setdefault('fx_rates',[]).append(entry)
    core.add_audit(state,'FX_RATE_SAVED',copy.deepcopy(entry))
    return copy.deepcopy(entry)


def get_rate(state,payment_date,code,rate_id=None):
    day(payment_date);code=currency(code)
    rates=[r for r in state.get('fx_rates',[]) if r['date']==payment_date and r['currency']==code and (rate_id is None or r['id']==rate_id)]
    if not rates:raise ValueError('No '+code+' rate for '+payment_date+'. Enter that exact payment-date rate; no previous-day rate is substituted.')
    return copy.deepcopy(rates[-1])


def import_rates(state,csv_text):
    reader=csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')))
    if not {'date','currency','inr_per_unit','source'}.issubset(reader.fieldnames or []):raise ValueError('Rate CSV needs date,currency,inr_per_unit,source.')
    candidate=copy.deepcopy(state);seen=set();entries=[]
    for n,row in enumerate(reader,2):
        try:
            key=(row['date'],currency(row['currency']))
            if key in seen:raise ValueError('Repeated currency/date in the same file.')
            seen.add(key);entries.append(save_rate(candidate,row['date'],row['currency'],row['inr_per_unit'],row['source']))
        except (ValueError,TypeError) as e:raise ValueError(f'Rate CSV row {n}: {e}') from e
    if not entries:raise ValueError('No rates found in the CSV.')
    state.clear();state.update(candidate)
    return entries


def create_foreign_account(state,code,name,code_currency):
    code_currency=currency(code_currency)
    if any(a['code']==code for a in state['accounts']):raise ValueError('Use an unused ledger code for a dedicated foreign-currency bank/cash account.')
    candidate=copy.deepcopy(state)
    foundation.save_account(candidate,code,name,'Asset','Cash and bank','Cash equivalent')
    candidate.setdefault('foreign_accounts',{})[code]={'currency':code_currency,'branch':'VK'}
    core.add_audit(candidate,'FX_ACCOUNT_CREATED',{'account':code,'currency':code_currency,'branch':'VK'})
    state.clear();state.update(candidate)


def _ledger(state,key,preferred,name,kind):
    mapping=state.setdefault('fx_ledgers',{})
    if key in mapping:return mapping[key]
    used={a['code'] for a in state['accounts']}
    lo,hi=foundation.KINDS[kind]
    code=preferred if preferred not in used else next((str(n) for n in range(lo,hi+1) if str(n) not in used),None)
    if not code:raise ValueError('No available account code for FX differences.')
    foundation.save_account(state,code,name,kind,'Other revenue' if kind=='Revenue' else 'Finance costs','Operating')
    mapping[key]=code
    return code


def _line(code,debit=0,credit=0):return dict(account=code,branch='VK',debit=debit,credit=credit)


def _bank(state,code):
    if code in state.get('foreign_accounts',{}):raise ValueError('Select an INR cash/bank ledger for INR conversion proceeds.')
    if not any(a['code']==code and a['kind']=='Asset' for a in state['accounts']) or state['account_details'].get(code,{}).get('group')!='Cash and bank':raise ValueError('Select an INR cash/bank ledger.')


def _holding_delta(state,voucher):
    fx=voucher.get('fx',{})
    if fx.get('kind')=='reversal':
        original=next(v for v in state['vouchers'] if v['id']==fx['original'])
        account,units=_holding_delta(state,original);return account,-units
    if fx.get('kind')=='receipt' and fx['inputs']['mode']=='held':return fx['inputs']['foreign_account'],Decimal(fx['foreign_amount'])
    if fx.get('kind')=='conversion':return fx['inputs']['foreign_account'],-Decimal(fx['foreign_amount'])
    return None,Decimal(0)


def holding_balance(state,account,through=None):
    if account not in state.get('foreign_accounts',{}):raise ValueError('Select a configured foreign-currency account.')
    units=Decimal(0);carrying=0;latest=''
    for v in state['vouchers']:
        if through and v['date']>through:continue
        code,change=_holding_delta(state,v)
        if code==account:units+=change;latest=max(latest,v['date'])
        carrying+=sum(l['debit']-l['credit'] for l in v['lines'] if l['account']==account)
    return {'currency':state['foreign_accounts'][account]['currency'],'foreign_amount':text(units),'inr_minor':carrying,'latest_date':latest}


def _chronology(state,account,payment_date):
    if holding_balance(state,account)['latest_date']>payment_date:raise ValueError('Enter foreign-account movements chronologically; later movements already exist. Do not change an earlier conversion cost by backdating.')


def _reference(state,reference):
    reference=reference.strip()
    if not reference:raise ValueError('Enter a unique bank/payment reference for this FX transaction.')
    def effective(v):
        reversal=next((r for r in state['vouchers'] if r.get('reverses')==v['id']),None)
        return not effective(reversal) if reversal else True
    if any(v.get('fx',{}).get('kind') in ('receipt','conversion') and effective(v) and v.get('metadata',{}).get('reference','').strip().casefold()==reference.casefold() for v in state['vouchers']):raise ValueError('This FX payment reference is already posted. No duplicate receipt/conversion was created.')
    return reference


def _difference(state,lines,gross,carrying):
    delta=gross-carrying
    if delta>0:lines.append(_line(_ledger(state,'gain','4160','Realised FX gains','Revenue'),credit=delta))
    elif delta<0:lines.append(_line(_ledger(state,'loss','4620','Realised FX losses','Expense'),debit=-delta))


def _build_receipt(state,payment_date,code,foreign_amount,credit_account,reference,mode='converted',bank_account='1010',foreign_account='',gross_inr='',fees_inr='0',narration='Foreign currency receipt',payee='',rate_id=None,bill_inr=''):
    day(payment_date);code=currency(code);amount=decimal(foreign_amount,CURRENCIES[code],code+' receipt')
    reference=_reference(state,reference)
    if mode not in ('converted','held'):raise ValueError('Choose immediate INR conversion or a foreign-currency holding.')
    rate=get_rate(state,payment_date,code,rate_id)
    with localcontext() as ctx:
        ctx.prec=64
        inr=int((amount*Decimal(rate['inr_per_unit'])*100).quantize(Decimal(1),rounding=ROUND_HALF_UP))
    if inr<=0:raise ValueError('The receipt converts to less than one INR paise.')
    a=next((a for a in state['accounts'] if a['code']==credit_account),None)
    if not a or not (a['kind']=='Revenue' or credit_account in ('2300',state['patient_control'])):raise ValueError('Choose earned revenue, patient advances, or shared Patient A/C for an existing bill.')
    if credit_account==state['patient_control']:
        credit_inr=int(decimal(bill_inr,2,'Existing bill carrying amount in INR')*100)
    else:
        if str(bill_inr).strip():raise ValueError('Existing bill carrying amount applies only to Patient A/C settlements.')
        credit_inr=inr
    fees=int(decimal(fees_inr or '0',2,'INR bank fees',False)*100)
    gross=int(decimal(gross_inr,2,'Actual gross INR conversion')*100) if str(gross_inr).strip() else inr
    if mode=='held':
        config=state.get('foreign_accounts',{}).get(foreign_account)
        if not config or config['currency']!=code:raise ValueError('Choose a dedicated foreign account configured for '+code+'.')
        if fees or str(gross_inr).strip():raise ValueError('INR bank fees/actual conversion apply to immediate conversion. Leave them blank/zero for a foreign holding.')
        _chronology(state,foreign_account,payment_date)
        lines=[_line(foreign_account,debit=inr),_line(credit_account,credit=credit_inr)]
        _difference(state,lines,inr,credit_inr)
        bank_account='';gross=inr
    else:
        _bank(state,bank_account)
        if fees>=gross:raise ValueError('Fees must be less than gross INR proceeds.')
        foreign_account='';lines=[_line(bank_account,debit=gross-fees),_line(credit_account,credit=credit_inr)]
        if fees:lines.append(_line('4560',debit=fees))
        _difference(state,lines,gross,credit_inr)
    inputs=dict(payment_date=payment_date,code=code,foreign_amount=text(amount),credit_account=credit_account,reference=reference,
       mode=mode,bank_account=bank_account,foreign_account=foreign_account,gross_inr='' if mode=='held' or not str(gross_inr).strip() else text(Decimal(gross)/100),
       fees_inr=text(Decimal(fees)/100),narration=narration.strip(),payee=payee.strip(),rate_id=rate['id'],bill_inr=text(Decimal(credit_inr)/100) if credit_account==state['patient_control'] else '')
    packet=dict(kind='receipt',inputs=inputs,foreign_amount=text(amount),inr_minor=inr,credit_inr_minor=credit_inr,rate=rate,gross_inr_minor=gross,fees_inr_minor=fees)
    metadata={'type':'Receipt','reference':reference,'payee':payee.strip(),'source':'FX receipt'}
    if bank_account:metadata['bank_account']=bank_account
    return dict(date=payment_date,narration=narration.strip(),lines=lines,metadata=metadata,fx=packet,ledger_names={l['account']:next(a['name'] for a in state['accounts'] if a['code']==l['account']) for l in lines})


def receipt_plan(state,**inputs):return _build_receipt(copy.deepcopy(state),**inputs)


def _build_conversion(state,payment_date,foreign_account,foreign_amount,bank_account,gross_inr,fees_inr,reference,narration='Convert foreign currency to INR'):
    day(payment_date);reference=_reference(state,reference);before=holding_balance(state,foreign_account)
    amount=decimal(foreign_amount,CURRENCIES[before['currency']],'Foreign amount to convert')
    available=Decimal(before['foreign_amount'])
    if amount>available:raise ValueError('Conversion exceeds the foreign currency held.')
    _chronology(state,foreign_account,payment_date);_bank(state,bank_account)
    gross=int(decimal(gross_inr,2,'Actual gross INR proceeds')*100);fees=int(decimal(fees_inr or '0',2,'INR bank fees',False)*100)
    if fees>=gross:raise ValueError('Fees must be less than gross INR proceeds.')
    with localcontext() as ctx:
        ctx.prec=64
        carrying=before['inr_minor'] if amount==available else int((Decimal(before['inr_minor'])*amount/available).quantize(Decimal(1),rounding=ROUND_HALF_UP))
    lines=[_line(bank_account,debit=gross-fees)]
    if carrying:lines.append(_line(foreign_account,credit=carrying))
    if fees:lines.append(_line('4560',debit=fees))
    _difference(state,lines,gross,carrying)
    inputs=dict(payment_date=payment_date,foreign_account=foreign_account,foreign_amount=text(amount),bank_account=bank_account,gross_inr=text(Decimal(gross)/100),fees_inr=text(Decimal(fees)/100),reference=reference,narration=narration.strip())
    packet=dict(kind='conversion',inputs=inputs,foreign_amount=text(amount),currency=before['currency'],inr_minor=carrying,gross_inr_minor=gross,fees_inr_minor=fees)
    return dict(date=payment_date,narration=narration.strip(),lines=lines,metadata={'type':'Transfer','reference':reference,'bank_account':bank_account,'source':'FX conversion'},fx=packet,ledger_names={l['account']:next(a['name'] for a in state['accounts'] if a['code']==l['account']) for l in lines})


def conversion_plan(state,**inputs):return _build_conversion(copy.deepcopy(state),**inputs)


def _post(state,builder,inputs):
    candidate=copy.deepcopy(state);plan=builder(candidate,**inputs)
    v=core.post(candidate,plan['date'],plan['narration'],plan['lines'],metadata=plan['metadata'],fx=plan['fx'])
    state.clear();state.update(candidate)
    return v


def post_receipt(state,**inputs):return _post(state,_build_receipt,inputs)
def post_conversion(state,**inputs):return _post(state,_build_conversion,inputs)


def validate_post(state,packet,payment_date,narration,lines,metadata,reverses):
    if packet.get('kind')=='reversal':
        if packet!={'kind':'reversal','original':reverses}:raise ValueError('FX reversal must refer to the original voucher.')
        original=next((v for v in state['vouchers'] if v['id']==reverses),None)
        if not original or not original.get('fx'):raise ValueError('Original FX transaction not found.')
        account,units=_holding_delta(state,original)
        if account:
            _chronology(state,account,payment_date)
            before=holding_balance(state,account)
            remaining=Decimal(before['foreign_amount'])-units
            carrying=before['inr_minor']-sum(l['debit']-l['credit'] for l in original['lines'] if l['account']==account)
            if remaining<0 or carrying<0 or (remaining==0 and carrying!=0):raise ValueError('This FX reversal would invalidate the remaining holding. Review later conversions first.')
        return
    if reverses:raise ValueError('Use the FX reversal link when reversing an FX voucher.')
    if packet.get('kind')=='receipt':expected=receipt_plan(state,**packet['inputs'])
    elif packet.get('kind')=='conversion':expected=conversion_plan(state,**packet['inputs'])
    else:raise ValueError('Unknown FX transaction type.')
    if packet!=expected['fx'] or lines!=expected['lines'] or payment_date!=expected['date'] or metadata!=expected['metadata'] or narration!=expected['narration']:
        raise ValueError('FX journal differs from its conversion record. Refresh the reviewed draft.')


def summary(voucher,state):
    packet=voucher.get('fx')
    if not packet:return ''
    if packet['kind']=='reversal':
        original=next(v for v in state['vouchers'] if v['id']==packet['original'])
        return 'FX reversal of '+original['id']+' | '+summary(original,state)
    code=packet['rate']['currency'] if packet['kind']=='receipt' else packet['currency']
    detail=code+' '+packet['foreign_amount']+' | INR '+format(Decimal(packet['inr_minor'])/100,'.2f')
    if packet['kind']=='receipt':detail+=' | 1 '+code+' = INR '+packet['rate']['inr_per_unit']+' on '+packet['rate']['date']+' | '+packet['rate']['source']
    return detail

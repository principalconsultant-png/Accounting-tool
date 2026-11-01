"""Offline entity extraction + statistical interpretation, always a reviewed draft."""
import copy
import re
from datetime import date,datetime
from decimal import Decimal
from . import core,foundation,local_model,revenue


def interpret(state,text,selected_branch,selected_date):
    if not text.strip():raise ValueError('Describe one transaction first.')
    if len(text)>3000:raise ValueError('Describe one transaction in fewer than 3000 characters.')
    original=text;lower=text.lower();work=text
    if re.search(r'\b(not|never|cancel\w*|revers\w*|unpaid|pending|will|tomorrow|yesterday|today|maybe|might|if|returned|exchange\w*)\b',lower):raise ValueError('Confirm the actual completed transaction, direction and explicit date; negation, relative dates or conditional actions need review.')
    workflows=[(r'\b(gst|igst|cgst|sgst|cess|inclusive|tax|rcm)\b','GST accounting / GST reverse charge'),(r'\b(tds|withhold\w*|net of)\b','TDS accounting'),(r'\b(advance|refund|unearned|package|outstanding|on credit|credit sale)\b','Service revenue'),(r'\b(cwip|commission\w*|construction|retention)\b','CWIP & commissioning'),(r'\b(depreciation|disposal)\b','Assets & depreciation')]
    for pattern,page in workflows:
        if re.search(pattern,lower):raise ValueError('Open '+page+' to review source and deterministic posting rules. No tax, source allocation or special journal was guessed.')
    if re.search(r'\b(dollars?|usd|eur|gbp|aed|forex)\b|[$€£]',lower):raise ValueError('Use FX receipts with the reviewed currency and exchange rate.')
    found=[]
    patterns=[(r'\b\d{4}-\d{2}-\d{2}\b','%Y-%m-%d'),(r'\b\d{1,2}/\d{1,2}/\d{4}\b','%d/%m/%Y'),(r'\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b',None)]
    for pattern,fmt in patterns:
        for m in re.finditer(pattern,work):
            try:
                if fmt:d=datetime.strptime(m.group(),fmt).date()
                else:
                    try:d=datetime.strptime(m.group(),'%d %B %Y').date()
                    except ValueError:d=datetime.strptime(m.group(),'%d %b %Y').date()
            except ValueError:raise ValueError('Review the invalid explicit transaction date.')
            found.append(d.isoformat())
        work=re.sub(pattern,' ',work)
    if len(found)>1:raise ValueError('There is more than one transaction date. Describe one transaction.')
    day=found[0] if found else selected_date
    if date.fromisoformat(day).isoformat()!=day:raise ValueError('Choose a valid transaction date.')
    units=foundation.branches(state,True);unit_matches=set()
    for code,name in units.items():
        if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',work,re.I) or re.search(r'\b(?:branch|unit|at)\s+'+re.escape(code)+r'\b',work,re.I):unit_matches.add(code)
    if len(unit_matches)>1:raise ValueError('Multiple operating units found; split the transaction or select reviewed inter-branch lines.')
    branch=next(iter(unit_matches),selected_branch)
    if branch not in units:raise ValueError('Select one active operating unit.')
    methods=[]
    aliases={'1000':r'\bcash\b','1010':r'\b(bank|neft|rtgs|imps|cheque)\b','1110':r'\b(upi|gpay|phonepe)\b','1120':r'\b(card|pos)\b'}
    for code,pattern in aliases.items():
        if re.search(pattern,work,re.I):methods.append(code)
    if len(methods)!=1:raise ValueError('Which actual payment method was used? Choose cash, bank, UPI or card; use Sales receipt for split collections.')
    payment=methods[0]
    reference='';refs=re.findall(r'\b(?:invoice|receipt|ref(?:erence)?)\s*(?:no\.?\s*)?[#:]?\s*([A-Za-z0-9][A-Za-z0-9/_-]*\d[A-Za-z0-9/_-]*)',work,re.I)
    if len(refs)>1:raise ValueError('Multiple source references found. Review one transaction at a time.')
    if refs:
        reference=refs[0];work=re.sub(re.escape(reference),' ',work)
    party=''
    party_match=re.search(r'\b(?:to|from)\s+(.+?)(?=\s+(?:for|by|via|through|using|at|on|inr|rs\b)|[₹\d]|[.;]|$)',work,re.I)
    if party_match:
        candidate=party_match.group(1).strip(' ,')
        if candidate.lower() not in ('cash','bank','upi','card'):party=candidate
    currency=r'(?:₹\s*|rs\.?\s*|inr\s*)(\d+(?:,\d+)*(?:\.\d{1,2})?)(?:\s*(lakh|lakhs|crore|crores|thousand))?\b'
    amounts=list(re.finditer(currency,work,re.I))
    if not amounts:
        amounts=list(re.finditer(r'(?<![\w.])\d+(?:,\d+)*(?:\.\d{1,2})?(?:\s*(?:lakh|lakhs|crore|crores|thousand))?(?![\w.])',work,re.I))
        if len(amounts)!=1:raise ValueError('Specify one gross INR amount. Several numbers need source review.')
        raw=amounts[0].group();n=re.match(r'([\d,.]+)\s*(.*)',raw);value,unit=n.group(1),n.group(2)
    else:
        if len(amounts)!=1:raise ValueError('Specify exactly one gross INR amount; split multi-amount descriptions.')
        value,unit=amounts[0].group(1),amounts[0].group(2) or ''
    rest=work[:amounts[0].start()]+' '+work[amounts[0].end():]
    if re.search(r'\d',rest):raise ValueError('Additional numbers found. Review quantities, references and the single gross amount.')
    scale={'lakh':100000,'lakhs':100000,'crore':10000000,'crores':10000000,'thousand':1000}.get(unit.lower(),1)
    whole=value.split('.')[0]
    if ',' in whole and not re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})',whole):raise ValueError('Review the INR comma grouping.')
    n=Decimal(value.replace(',',''))*scale;amount=core.money(n)
    if amount<=0 or re.search(r'-\s*(?:₹|rs|inr|\d)',work,re.I):raise ValueError('Confirm a positive gross INR amount.')
    customer=bool(re.search(r'\b(?:patient|customer)\b.*?\b(?:paid|purchased|bought)\b|\b(?:purchased|bought|paid)\b.*?\bby\s+(?:the\s+)?(?:patient|customer)\b',lower))
    received=bool(re.search(r'\b(received|collected|credited|sales|sale|sold|income)\b',lower)) or customer
    paid=bool(re.search(r'\b(paid|purchased|bought|settled|remitted|spent|debited)\b',lower)) and not customer
    if received==paid:raise ValueError('Was this money paid by the hospital or received from a patient/customer?')
    if received and re.search(r'\b(supplier|vendor|wholesaler|distributor)\b',lower):raise ValueError('Receiving goods from suppliers is not a service receipt. Review purchase and stock accounts manually.')
    legacy=None
    # Preserve established deterministic, actor-aware revenue distinctions.
    cleaned=rest
    for code,name in units.items():cleaned=re.sub(re.escape(name),' ',cleaned,flags=re.I)
    if party:cleaned=cleaned.replace(party,' ')
    model=local_model.predict(cleaned)
    topic_patterns=[r'\b(?:rent|rental|lease|landlord)\b',r'\b(?:electricity|utilities|power|water|broadband|telephone)\b',r'\b(?:repair|repairs|maintenance|servicing|upkeep)\b',r'\b(?:salary|salaries|payroll|wages)\b',r'\b(?:doctor|physician|honorarium)\b',r'\b(?:bank charges|bank fee|processing|commission)\b',r'\b(?:equipment|apparatus|machinery)\b',r'\b(?:furniture|chairs|desks|cabinet)\b']
    if paid and sum(bool(re.search(p,cleaned,re.I)) for p in topic_patterns)>1:raise ValueError('Multiple expense or asset purposes found. Split their gross amounts and select separate lines.')
    normalized=(('Received' if received else 'Paid')+' INR '+str(n)+' '+cleaned)
    normalized=re.sub(r'\b(?:neft|rtgs|imps|cheque)\b','bank',normalized,flags=re.I)
    normalized=re.sub(r'\b(?:gpay|phonepe)\b','upi',normalized,flags=re.I)
    normalized=re.sub(r'\bpos\b','card',normalized,flags=re.I)
    try:
        legacy=core.parse_transaction(normalized,branch,day,state);account=next(l['account'] for l in legacy if l['account']!=payment)
    except ValueError as error:
        if not str(error).startswith(('Account classification is ambiguous or unsupported.','Specify whether money was paid or received')):raise
        account=None
    intent=model['intent']
    predicted=state['revenue_mode_accounts'].get(intent.split(':',1)[1]) if intent and intent.startswith('service:') else intent
    if account is None:
        if not predicted:raise ValueError('Account interpretation is uncertain. Which ledger and transaction purpose apply? Select manual lines; no draft was guessed.')
        account=predicted
    records={a['code']:a for a in state['accounts']}
    if account not in records or (received and records[account]['kind']!='Revenue') or (paid and records[account]['kind'] not in ('Expense','Asset')):raise ValueError('The payment direction and account interpretation disagree. Review the purpose and source.')
    if paid and payment in ('1110','1120'):raise ValueError('Outgoing UPI/card payments need selection of the actual bank/card liability; collection clearing cannot be used.')
    if len(revenue.match_modes(lower))>1:raise ValueError('Multiple service categories found. Split their amounts in Sales receipt.')
    for code in (account,payment):
        if code not in records or not state['account_details'].get(code,{}).get('active',True):raise ValueError('A required ledger is absent or inactive. Review the valid chart of accounts.')
    debit,credit=(payment,account) if received else (account,payment)
    lines=[dict(account=debit,branch=branch,debit=amount,credit=0),dict(account=credit,branch=branch,debit=0,credit=amount)]
    # Pure validation on a disposable candidate applies every normal posting guard.
    core.post(copy.deepcopy(state),day,original,lines,metadata={'payee':party,'reference':reference})
    explanation=f'Offline {local_model.VERSION}: '+('deterministic source-language match' if legacy else 'statistical topic '+str(intent))+f'. Gross INR {n}; debit {debit} {records[debit]["name"]}, credit {credit} {records[credit]["name"]}; unit {units[branch]}; date {day}'+(' (from description)' if found else ' (selected date)')+'. Review these facts before posting. No tax split inferred.'
    return dict(date=day,branch=branch,party=party,reference=reference,amount=amount,method=payment,account=account,lines=lines,explanation=explanation,model=model,source=original)

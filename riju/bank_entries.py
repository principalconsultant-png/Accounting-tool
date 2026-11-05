"""Explicit, reviewed bank-originated entries; no narration-based accounting guesses."""
from . import core,ap,foundation,reconciliation as bank

CATEGORIES=('Bank / SMS / card charges','Loan repayment / EMI','Cash withdrawal','Cash deposit','Own-bank transfer','Loan proceeds received','Loan given recovered','Standing instruction / other payment','Transfer to another person','Other reviewed receipt')
DEFAULTS={'Bank / SMS / card charges':'4560','Loan repayment / EMI':'2400','Cash withdrawal':'1000','Cash deposit':'1000','Loan proceeds received':'2400'}
GUIDANCE={
 CATEGORIES[0]:'Expense only a genuine bank/service charge. Card settlements belong in settlement review. No GST input is inferred.',
 CATEGORIES[1]:'Use the lender statement: principal reduces the loan; interest and fees are expenses. Enter all three components; their sum must equal the withdrawal.',
 CATEGORIES[2]:'Cash withdrawn for the business is Dr Cash / Cr Bank, not an expense. Record actual petty-cash spending separately.',
 CATEGORIES[3]:'Cash already in the books is Dr Bank / Cr Cash, not sales again. For receipt-linked deposits use settlement review.',
 CATEGORIES[4]:'Move between your own saved INR bank ledgers. Post once; match the other bank statement to the existing movement.',
 CATEGORIES[5]:'A loan received increases a borrowing liability; it is not revenue.',
 CATEGORIES[6]:'Recovery of a loan you previously gave reduces the loan-receivable asset. Interest received requires a separately reviewed journal.',
 CATEGORIES[7]:'Standing instruction is a payment method. Select the real expense, advance, payroll liability or equity ledger. For EMI choose Loan repayment; for vendor invoices use AP payment.',
 CATEGORIES[8]:'Identify the purpose: expense, employee advance, payroll settlement or owner drawings. Vendor payments belong in AP; personal drawings are not business expenses.',
 CATEGORIES[9]:'Identify capital, borrowing, advance or another genuine non-sales source. Customer receipts, GST/TDS and AP allocations use their dedicated screens.'}

def accounts(s,category,bank_account):
    out=[];banks={a['code'] for a in bank.bank_accounts(s)}
    for a in s['accounts']:
        code=a['code'];group=s['account_details'][code]['group'];kind=a['kind']
        if code==bank_account or code in s.get('foreign_accounts',{}) or not s['account_details'][code].get('active',True):continue
        allowed=(code=='4560' and kind=='Expense') if category==CATEGORIES[0] else (kind=='Liability' and group=='Borrowings') if category in (CATEGORIES[1],CATEGORIES[5]) else code=='1000' and kind=='Asset' if category in (CATEGORIES[2],CATEGORIES[3]) else code in banks if category==CATEGORIES[4] else kind=='Asset' and group=='Other assets' if category==CATEGORIES[6] else kind in ('Expense','Equity') or kind=='Asset' and group in ('Other assets','Inventory','PPE','CWIP') or kind=='Liability' and group=='Other liabilities'
        if category==CATEGORIES[9]:allowed=kind=='Equity' or kind=='Liability' and group in ('Borrowings','Other liabilities') or kind=='Asset' and group=='Other assets'
        if allowed:out.append(a)
    return out

@ap.atomic
def record(s,bank_id,values):
    category=values.get('category');branch=values.get('branch');account=values.get('account');basis=str(values.get('basis','')).strip()
    if category not in CATEGORIES:raise ValueError('Choose a bank transaction treatment.')
    if values.get('reviewed') is not True or not basis:raise ValueError('Review the bank evidence, accounting purpose and existing books; enter the review basis.')
    original=next((b for b in bank.bank_rows(s,values.get('bank_account','')) if b['id']==bank_id),None)
    if not original:raise ValueError('Select an imported bank transaction.')
    rows,books=bank.outstanding(s,original['bank_account']);row=next((b for b in rows if b['id']==bank_id),None)
    if not row:raise ValueError('The transaction is already matched. Refresh.')
    if row['branch']!='ALL' and row['branch']!=branch:raise ValueError('Operating unit must match the statement scope.')
    if branch not in foundation.branches(s,True):raise ValueError('Select an active operating unit.')
    n=row['remaining'];amount=abs(n)
    if category in (CATEGORIES[0],CATEGORIES[1],CATEGORIES[2],CATEGORIES[7],CATEGORIES[8]) and n>=0:raise ValueError('This treatment requires a bank withdrawal.')
    if category in (CATEGORIES[3],CATEGORIES[5],CATEGORIES[6],CATEGORIES[9]) and n<=0:raise ValueError('This treatment requires a bank deposit.')
    if account not in {a['code'] for a in accounts(s,category,row['bank_account'])}:raise ValueError('Choose a genuine eligible ledger for this treatment. Use AP/tax/receipt screens for their controlled transactions.')
    # A matching reference already in the books must be linked, not posted twice.
    if row['reference'] and any(b['branch']==branch and b['date']==row['date'] and abs(b['remaining'])==amount and ap.norm(b['reference'])==ap.norm(row['reference']) and b['remaining']*n>0 for b in books):raise ValueError('An unmatched bank movement already has this reference. Match the existing book movement instead of posting again.')
    lines=[dict(account=row['bank_account'],branch=branch,debit=max(n,0),credit=max(-n,0))]
    def add(code,value):
        if value:lines.append(dict(account=code,branch=branch,debit=value if n<0 else 0,credit=value if n>0 else 0))
    if category==CATEGORIES[1]:
        principal=bank.amount(str(values.get('principal','0')));interest=bank.amount(str(values.get('interest','0')));fees=bank.amount(str(values.get('fees','0')))
        if min(principal,interest,fees)<0 or principal+interest+fees!=amount:raise ValueError('Principal + interest + fees must equal the remaining bank withdrawal exactly; use the lender breakup.')
        interest_account=values.get('interest_account','4580')
        if interest and not any(a['code']==interest_account and a['kind']=='Expense' and s['account_details'][a['code']].get('active',True) for a in s['accounts']):raise ValueError('Choose an active interest expense ledger.')
        if fees and not any(a['code']=='4560' and a['kind']=='Expense' for a in s['accounts']):raise ValueError('4560 must be a genuine bank-charge expense ledger.')
        for day in {row['date'],*[v['date'] for v in s['vouchers'] if v['date']>=row['date']]}:
            if core.balances(s,day,branch)[account]>-principal:raise ValueError('Principal exceeds the recorded loan liability. Review opening loan balances and later repayments first.')
        add(account,principal);add(interest_account,interest);add('4560',fees)
    else:
        dates={row['date'],*[v['date'] for v in s['vouchers'] if v['date']>=row['date']]}
        if category in (CATEGORIES[3],CATEGORIES[6]) and any(core.balances(s,day,branch)[account]<amount for day in dates):raise ValueError('Deposit/recovery exceeds the recorded cash or loan-receivable balance. Review opening balances and source entries first.')
        if n<0 and next(a['kind'] for a in s['accounts'] if a['code']==account)=='Liability' and any(core.balances(s,day,branch)[account]>-amount for day in dates):raise ValueError('Settlement exceeds the recorded liability. Review its opening/accrual and later payments first.')
        add(account,amount)
    narration=category+' | '+row['narration']+' | '+basis
    voucher=core.post(s,row['date'],narration,lines,metadata=dict(type='Transfer' if category in (CATEGORIES[2],CATEGORIES[3],CATEGORIES[4]) else 'Receipt' if n>0 else 'Payment',reference=row['reference'],bank_account=row['bank_account'],source='Reviewed bank transaction'))
    movements=[dict(b,remaining=b['amount']) for b in bank.book_items(s,row['bank_account']) if b['voucher']==voucher['id']]
    match=bank._record_match(s,[row],movements,'adjustment',voucher['id'])
    core.add_audit(s,'BANK_TRANSACTION_RECORDED',dict(category=category,bank_id=bank_id,voucher=voucher['id'],match=match['id'],basis=basis))
    return dict(voucher=voucher['id'],match=match['id'])

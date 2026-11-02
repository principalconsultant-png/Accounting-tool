"""Generate isolated training inputs and verified reports; never open a user vault."""
import csv
import io
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from riju import core,foundation,receipt_import,ap,reconciliation as bank,cash_flow,financial_reports as reports


def build_example(output):
    from openpyxl import load_workbook
    out=Path(output);out.mkdir(parents=True,exist_ok=True);s=core.empty_state();foundation.save_entity(s,'TRAINING ONLY — Daily sales to financial reports',{})
    def pair(dr,cr,n):return [dict(account=dr,branch='JP',debit=n,credit=0),dict(account=cr,branch='JP',debit=0,credit=n)]
    core.post(s,'2026-04-01','TRAINING opening bank/capital',pair('1010','3000',5000000),opening=True)
    rows=[]
    for ref,values in [('WALK-001',dict(consultation='500',treatment='300',cash='200',upi='600',total='800')),('WALK-002',dict(consultation='200',room_rent='1000',card='1200',total='1200'))]:
        r=dict.fromkeys(receipt_import.HEADERS,'');r.update(receipt_date='2026-11-01',branch='JP',receipt_no=ref,record_type='earned',tax_mode='no_separate_tax');r.update(values);rows.append(r)
    csvpath=out/'Worked-Example-Daily-Sales.csv'
    with csvpath.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=receipt_import.HEADERS);w.writeheader();w.writerows(rows)
    xlsxpath=out/'Worked-Example-Daily-Sales.xlsx';receipt_import.template(xlsxpath);w=load_workbook(xlsxpath)
    for r in rows:w['Receipts'].append([r[h] for h in receipt_import.HEADERS])
    w.save(xlsxpath);w.close()
    q=receipt_import.stage(s,csvpath.read_bytes(),csvpath.name);receipt_import.review(s,q['id'],[0,1],True,'TRAINING only: earned services and no separate GST/TDS',True);receipt_import.post(s,q['id'])
    vendor=ap.save_vendor(s,dict(name='TRAINING Office Supplier',credit_days='0'));invoice=ap.enter_invoice(s,dict(vendor=vendor['id'],branch='JP',reference='WALK-AP-001',invoice_date='2026-11-01',received_date='2026-11-01',accounting_date='2026-11-01',credit_days='0',due_basis='Receipt date',amount='1000',payable='2000',allocations=[dict(account='4590',amount='1000')],tax_treatment='No separate GST/TDS; reviewed',reviewed=True,basis='TRAINING administration service, not legal tax guidance'))
    ap.extend(s,invoice['id'],'2026-11-02','2026-11-10','TRAINING agreed payment plan',True)
    payment=ap.pay(s,dict(date='2026-11-02',reference='WALK-PAY-001',bank_account='1010',items=[dict(invoice=invoice['id'],amount='400')],reviewed=True,basis='TRAINING actual partial bank payment'))
    banktext='date,narration,reference,debit,credit,balance\n2026-11-02,TRAINING UPI settlement,WALK-UPI-001,0,600,50600\n2026-11-02,TRAINING card settlement,WALK-CARD-001,0,1200,51800\n2026-11-02,TRAINING vendor payment,WALK-PAY-001,400,0,51400\n'
    bankpath=out/'Worked-Example-Bank.csv';bankpath.write_text(banktext,encoding='utf-8-sig');statement=bank.import_statement(s,bankpath.read_bytes(),bankpath.name,'1010','JP','2026-11-01','2026-11-02','50000','51400')
    bankrows={r['reference']:r for r in s['bank_lines']}
    for ref,account in [('WALK-UPI-001','1110'),('WALK-CARD-001','1120')]:
        keys=[r['key'] for r in bank.clearing_items(s,account,'JP','2026-11-02')];bank.settle(s,bankrows[ref]['id'],account,keys)
    paymentvoucher=next(v for v in s['vouchers'] if v['id']==payment['voucher']);key=paymentvoucher['id']+':'+str(next(i for i,l in enumerate(paymentvoucher['lines']) if l['account']=='1010'))
    bank.match_existing(s,[bankrows['WALK-PAY-001']['id']],[key]);proof=bank.brs(s,statement['id']);assert proof['ready'] and proof['variance']==0;bank.finalize(s,statement['id'])
    cash_flow.save_policy(s,dict(cash_flow.defaults(s),effective='2026-04-01',reviewed=True,note='TRAINING: cash 1000 and bank 1010 only; UPI/card excluded until settled; reviewed Operating policy'))
    b=core.balances(s,'2026-11-02','JP');assert (b['1000'],b['1010'],b['1110'],b['1120'],b['2000'])==(20000,5140000,0,0,-60000)
    start,end='2026-11-01','2026-11-02';packs=[reports.snapshot(s,m,start,end,'JP') for m in ('Trial balance','Profit and loss','Balance sheet',cash_flow.DIRECT,cash_flow.INDIRECT)];forecast=ap.forecast_snapshot(s,end,end,'2026-11-30','JP');packs.append(forecast)
    cf=cash_flow.analyse(s,start,end,'JP');assert cf['ready'] and cf['profit']==100000 and cf['totals']['Operating']==160000 and cf['closing']==5160000 and cf['indirect_difference']==0
    assert next(r for r in packs[1]['rows'] if r[2]=='Profit / (loss)')[3]==100000
    assert next(r for r in packs[2]['rows'] if r[2]=='Total assets')[3]==5160000
    assert sum(r['amount'] for r in ap.forecast(s,end,end,'2026-11-30','JP'))==-60000
    for p in packs:p['note']='TRAINING ONLY — expected results of guide chapter 26. '+p['note']
    reports.export_pack_xlsx(packs,out/'Worked-Example-Financial-Reports.xlsx');reports.export_pdf(packs,out/'Worked-Example-Financial-Reports.pdf');core.verify_audit(s)
    return dict(state=s,proof=proof,packs=packs,cash_flow=cf)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='work/worked-example');args=parser.parse_args();build_example(args.output);print('Verified training sample inputs and financial reports generated.')

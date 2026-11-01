"""Cash-flow classification policy, reviewed exceptions and statement outputs."""
from datetime import datetime
import csv
import io
import json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import cash_flow as cf,core,history


class CashFlowUI:
    def cash_flow_setup(self):
        self.note('Cash-flow statements use a report-wide reviewed cash/equivalent definition and account classifications. Default mappings are proposals. Review actual cash-equivalent/overdraft, interest and tax policies; mixed transactions remain draft until classified. Financial reports also includes both methods and their Excel/PDF handover sections.')
        bar=self.bar();self.button(bar,'New / revised policy',self.new_cash_flow_policy,True);self.button(bar,'Review voucher allocation',self.review_cash_flow_voucher);self.button(bar,'AP payment forecast',lambda:self.show('AP Vendor Invoices'))
        for kind in ('xlsx','pdf','json'):self.button(bar,'Export '+('Excel' if kind=='xlsx' else kind.upper()),lambda kind=kind:self.export_cash_flow(kind))
        result=cf.analyse(self.state,*self.dates(),self.unit());self.cash_flow_result=result
        ttk.Label(self.content,text=('Reviewed — proofs passed' if result['ready'] else 'DRAFT — review required')+' | Policy: '+(result['policy']['id'] or 'Default proposals')+' | Cash ledgers: '+', '.join(result['policy']['cash_accounts']),wraplength=1000).pack(anchor='w',pady=10)
        self.table(('Cash proof','INR'),[('Opening',core.rupees(result['opening'])),('Balances introduced during period',core.rupees(result['introduced'])),*[(category,core.rupees(n)) for category,n in result['totals'].items()],('Closing',core.rupees(result['closing'])),('Cash reconciliation difference',core.rupees(result['cash_difference'])),('Direct / indirect operating difference',core.rupees(result['indirect_difference']))],height=8)
        self.table(('Voucher','Review item','Cash movement INR'),[(i['voucher'],i['reason'],core.rupees(i['cash_movement'])) for i in result['issues']],height=5)
        ttk.Label(self.content,text='Zero arithmetic differences do not clear classification issues. Mid-period opening introductions remain separate from cash flows and keep the report draft; review the reporting start/history. Statement exports include direct, indirect and voucher support; JSON also retains noncash support and policy evidence.',wraplength=1000).pack(anchor='w',pady=10)

    def new_cash_flow_policy(self):
        proposed=cf.defaults(self.state);start,_=self.dates()
        win,body,f=self._tax_form('Review cash-flow policy',[('effective','Effective report-policy date',start,None),('cash','Cash/equivalent ledger codes',', '.join(proposed['cash_accounts']),None),('noncash','Noncash P&L adjustment codes',', '.join(proposed['noncash_accounts']),None),('note','Verified definition/classification basis','',None)])
        ttk.Label(body,text='Overrides CSV: account,category. Categories: Operating, Investing, Financing, Exchange effects, Review. Unlisted accounts use the displayed standard proposals. Cash equivalents beyond Cash and bank must first be marked Cash equivalent in account masters. Include inactive historical cash accounts where needed.',wraplength=1000).pack(anchor='w',pady=8)
        overrides=tk.Text(body,height=5);overrides.pack(fill='x');overrides.insert('1.0','account,category\n')
        proposals=tk.Text(body,height=12,wrap='word');proposals.pack(fill='both',expand=True);proposals.insert('1.0',json.dumps(proposed['mapping'],indent=2));proposals.configure(state='disabled')
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed this report-wide cash definition, classifications and noncash adjustment policy',variable=reviewed).pack(anchor='w',pady=8)
        def save():
            mapping=dict(proposed['mapping'])
            rows=csv.DictReader(io.StringIO(overrides.get('1.0','end').strip()))
            if not {'account','category'}.issubset(rows.fieldnames or []):raise ValueError('Override CSV requires account,category.')
            for row in rows:mapping[str(row['account']).strip()]=str(row['category']).strip()
            self.commit(lambda s:cf.save_policy(s,dict(effective=f['effective'].get().strip(),cash_accounts=[c.strip() for c in f['cash'].get().split(',') if c.strip()],noncash_accounts=[c.strip() for c in f['noncash'].get().split(',') if c.strip()],mapping=mapping,note=f['note'].get(),reviewed=reviewed.get())));win.destroy();self.show('Cash flow setup')
        self.button(body,'Save policy version',save,True)

    def review_cash_flow_voucher(self):
        result=cf.analyse(self.state,*self.dates(),self.unit());policy=result['policy']
        if not policy['id'] or not policy['reviewed']:raise ValueError('Save a reviewed cash-flow policy before classifying voucher exceptions.')
        choices={v['id']+' · '+v['date']+' · '+v['narration'][:40]:v['id'] for v in self.state['vouchers'] if not v.get('reverses') and not v.get('opening') and any(l['account'] in policy['cash_accounts'] and (self.unit()=='ALL' or l['branch']==self.unit()) for l in v['lines'])}
        if not choices:raise ValueError('No original cash vouchers in this scope.')
        win,body,f=self._tax_form('Review cash-flow voucher',[('voucher','Original voucher',next(iter(choices)),list(choices)),('reason','Supporting classification reason','',None)])
        ttk.Label(body,text='Enter signed cash-flow lines: category,amount,label. Positive = receipt/increase; negative = payment/decrease. Sum must equal the voucher cash change under this policy/scope. For a reviewed composite with no net/gross external flows, leave only the header. Exact reversals inherit opposite signs. Use the source bank/other evidence, not an unexplained balancing amount.',wraplength=1000).pack(anchor='w',pady=10)
        text=tk.Text(body,height=8);text.pack(fill='both',expand=True);text.insert('1.0','category,amount,label\n')
        gross=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I independently verified gross flows that exceed the net cash legs in this voucher',variable=gross).pack(anchor='w',pady=8)
        def save():
            rows=csv.DictReader(io.StringIO(text.get('1.0','end').strip()))
            if not {'category','amount','label'}.issubset(rows.fieldnames or []):raise ValueError('Use category,amount,label.')
            self.commit(lambda s:cf.save_allocation(s,policy['id'],choices[f['voucher'].get()],self.unit(),list(rows),f['reason'].get(),gross.get()));win.destroy();self.show('Cash flow setup')
        self.button(body,'Save reviewed cash allocation',save,True)

    def export_cash_flow(self,kind):
        path=filedialog.asksaveasfilename(parent=self,initialfile='cash-flow-working-statements.'+kind,defaultextension='.'+kind)
        if path:cf.export(self.state,*self.dates(),self.unit(),path,kind)

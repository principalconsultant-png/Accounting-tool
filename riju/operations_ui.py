"""Foreign receipts/rates and client work-volume desktop screens."""
import csv
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import fx,activity,ledgers


class OperationsUI:
    def fx_receipts(self):
        self.note('Vaikom FX receipts — all journals on this screen post to '+self.branches.get('VK','Vaikom')+'. Enter the exact payment-day rate offline. Books remain in INR; original currency and rate/source are retained. No GST is guessed.')
        tabs=ttk.Notebook(self.content);tabs.pack(fill='both',expand=True)
        rates=ttk.Frame(tabs,padding=12);receipt=ttk.Frame(tabs,padding=12);holdings=ttk.Frame(tabs,padding=12)
        for widget,name in ((rates,'Daily FX rates'),(receipt,'Receive payment'),(holdings,'Foreign accounts & conversion')):tabs.add(widget,text=name)
        today=datetime.now(activity.INDIA).date().isoformat()
        def row(parent):
            w=ttk.Frame(parent);w.pack(fill='x',pady=5);return w
        top=row(rates)
        self.fx_rate_day=self.field(top,'Rate / payment date',today,width=13)
        self.fx_rate_currency=self.field(top,'Currency','USD',list(fx.CURRENCIES),width=8)
        self.fx_rate_value=self.field(top,'INR per 1 currency unit','',width=20)
        self.fx_rate_source=self.field(top,'Source / bank advice reference','',width=31)
        ttk.Label(rates,text='Example: USD 1 = INR 83.25000000. Corrections create a new revision; posted receipts keep the rate originally reviewed. No live or previous-day rate is automatically substituted.',wraplength=900).pack(anchor='w',pady=8)
        def refresh_rates():
            self.fx_rate_table.delete(*self.fx_rate_table.get_children())
            for r in sorted(self.state.get('fx_rates',[]),key=lambda r:(r['date'],r['currency'],r['revision']),reverse=True):
                self.fx_rate_table.insert('','end',values=(r['date'],r['currency'],r['inr_per_unit'],r['source'],r['revision']))
        def save_rate():
            self.commit(lambda s:fx.save_rate(s,self.fx_rate_day.get(),self.fx_rate_currency.get(),self.fx_rate_value.get(),self.fx_rate_source.get()));refresh_rates()
        def import_rates():
            path=filedialog.askopenfilename(filetypes=[('FX rate CSV','*.csv')],parent=self)
            if path:
                self.commit(lambda s:fx.import_rates(s,Path(path).read_text(encoding='utf-8-sig')));refresh_rates()
        def export_rates():
            path=filedialog.asksaveasfilename(initialfile='FX-rates.csv',defaultextension='.csv',parent=self)
            if path:
                current={}
                for r in self.state.get('fx_rates',[]):current[(r['date'],r['currency'])]=r
                with open(path,'w',newline='',encoding='utf-8-sig') as stream:
                    writer=csv.writer(stream);writer.writerow(['date','currency','inr_per_unit','source'])
                    for key,r in sorted(current.items()):writer.writerow([r['date'],r['currency'],r['inr_per_unit'],ledgers.safe_csv(r['source'])])
        actions=row(rates);self.button(actions,'Save dated rate',save_rate,True);self.button(actions,'Import rate CSV',import_rates);self.button(actions,'Export current rates',export_rates)
        self.fx_rate_table=self.table(('Date','Currency','INR per unit','Source','Revision'),[],parent=rates,height=6);refresh_rates()
        bank_options=[a['code']+' · '+a['name'] for a in self.state['accounts'] if self.state['account_details'].get(a['code'],{}).get('group')=='Cash and bank' and a['code'] not in self.state.get('foreign_accounts',{}) and self.state['account_details'][a['code']]['active']]
        foreign_options=[a['code']+' · '+a['name']+' ['+self.state['foreign_accounts'][a['code']]['currency']+']' for a in self.state['accounts'] if a['code'] in self.state.get('foreign_accounts',{})]
        credits=[a['code']+' · '+a['name'] for a in self.state['accounts'] if (a['kind']=='Revenue' or a['code'] in ('2300',self.state['patient_control'])) and self.state['account_details'].get(a['code'],{}).get('active',True)]
        self.fx_input={};spec=[('payment_date','Payment date',today,None),('code','Currency','USD',list(fx.CURRENCIES)),('foreign_amount','Foreign amount','',None),
           ('mode','Receipt treatment','Convert immediately to INR',['Convert immediately to INR','Hold foreign currency']),('bank_account','INR bank / cash',next(o for o in bank_options if o.startswith('1010')),bank_options),('foreign_account','Foreign account (if held)',foreign_options[0] if foreign_options else '',foreign_options or ['']),
           ('credit_account','Credit ledger',next(o for o in credits if o.startswith('2300' if self.state['branches'].get('VK',{}).get('status')=='Under construction' else '4040')),credits),('gross_inr','Actual gross INR (optional)','',None),('fees_inr','INR bank fees','0',None),
           ('reference','Unique payment / bank reference','',None),('payee','Payer / guest (optional)','',None),('bill_inr','Old bill carrying INR (Patient A/C only)','',None),('narration','Narration','Foreign currency receipt',None)]
        for i,(key,label,default,values) in enumerate(spec):
            if i%3==0:top=row(receipt)
            self.fx_input[key]=self.field(top,label,default,values,width=25 if key not in ('code','payment_date') else 13)
        ttk.Label(receipt,text='Use an earned revenue ledger for completed services, Patient/package advances for future services, or Patient A/C for a recorded bill. For Patient A/C, enter the bill’s INR carrying amount. INR gross/fee fields apply only to immediate conversion.',wraplength=900).pack(anchor='w',pady=8)
        def receipt_inputs():
            values={k:v.get() for k,v in self.fx_input.items()}
            values['mode']='held' if values['mode']=='Hold foreign currency' else 'converted'
            for k in ('bank_account','foreign_account','credit_account'):values[k]=values[k].split(' · ')[0]
            return values
        self.fx_plans={};self.fx_summaries={};self.fx_tables={}
        def preview(kind,getter):
            plan=(fx.receipt_plan if kind=='receipt' else fx.conversion_plan)(self.state,**getter())
            self.fx_plans[kind]=plan
            packet=plan['fx'];code=packet['rate']['currency'] if kind=='receipt' else packet['currency']
            summary=code+' '+packet['foreign_amount']+' | Book value INR '+ledgers.number(packet['inr_minor'],True)+' | Gross INR '+ledgers.number(packet['gross_inr_minor'],True)+' | Fees INR '+ledgers.number(packet['fees_inr_minor'],True)+' | Net bank INR '+ledgers.number(packet['gross_inr_minor']-packet['fees_inr_minor'],True)
            if kind=='receipt' and packet['inputs']['mode']=='held':summary=code+' '+packet['foreign_amount']+' held | INR book value '+ledgers.number(packet['inr_minor'],True)+' | No INR bank conversion yet'
            if kind=='receipt' and packet['credit_inr_minor']!=packet['inr_minor']:summary+='\nExisting bill credit INR '+ledgers.number(packet['credit_inr_minor'],True)
            if kind=='receipt':summary+='\nRate: 1 '+code+' = INR '+packet['rate']['inr_per_unit']+' on '+packet['rate']['date']+' | '+packet['rate']['source']
            self.fx_summaries[kind].configure(text=summary)
            table=self.fx_tables[kind];table.delete(*table.get_children())
            for l in plan['lines']:table.insert('','end',values=(l['account'],plan['ledger_names'][l['account']],ledgers.number(l['debit'],True),ledgers.number(l['credit'],True)))
        def post(kind,getter):
            if kind not in self.fx_plans:raise ValueError('Prepare and review the FX journal first.')
            inputs=getter();plan=(fx.receipt_plan if kind=='receipt' else fx.conversion_plan)(self.state,**inputs)
            if plan!=self.fx_plans[kind]:raise ValueError('Inputs or rates changed. Refresh the FX preview before posting.')
            if not messagebox.askyesno('Approve Vaikom FX journal','Post to '+self.branches.get('VK','Vaikom')+' on '+plan['date']+'?\n\n'+self.fx_summaries[kind].cget('text')+'\n\nReference: '+plan['metadata']['reference'],parent=self):return
            v=self.commit(lambda s:(fx.post_receipt if kind=='receipt' else fx.post_conversion)(s,**inputs))
            messagebox.showinfo('Posted',v['id'],parent=self);self.show('FX receipts')
        def preview_controls(parent,kind,getter):
            actions=row(parent);self.button(actions,'Prepare FX journal',lambda:preview(kind,getter),True);self.button(actions,'Review & post FX journal',lambda:post(kind,getter),True)
            self.fx_summaries[kind]=ttk.Label(parent,text='No FX journal prepared.',wraplength=900);self.fx_summaries[kind].pack(anchor='w',pady=7)
            self.fx_tables[kind]=self.table(('Account','Ledger','Debit INR','Credit INR'),[],parent=parent,height=4)
        preview_controls(receipt,'receipt',receipt_inputs)
        top=row(holdings);code=self.field(top,'New account code','1012',width=12);name=self.field(top,'Foreign account name','USD bank — Vaikom',width=30);ccy=self.field(top,'Currency','USD',list(fx.CURRENCIES),width=8)
        def create():
            self.commit(lambda s:fx.create_foreign_account(s,code.get(),name.get(),ccy.get()));self.show('FX receipts')
        self.button(top,'Create dedicated foreign account',create)
        data=[]
        for code_account in self.state.get('foreign_accounts',{}):
            b=fx.holding_balance(self.state,code_account);data.append((code_account,self.account_name(code_account),b['currency'],b['foreign_amount'],ledgers.number(b['inr_minor'],True)))
        self.table(('Account','Name','Currency','Foreign units held','INR book value'),data,parent=holdings,height=4)
        ttk.Label(holdings,text='Foreign movements must be recorded chronologically. Later conversion uses the holding’s average INR carrying cost; actual bank gross proceeds and fees determine realised FX gain/loss. Period-end revaluation is not automatic in this draft.',wraplength=900).pack(anchor='w',pady=8)
        self.fx_conversion={}
        specs=[('payment_date','Conversion date',today,None),('foreign_account','Foreign account',foreign_options[0] if foreign_options else '',foreign_options or ['']),('foreign_amount','Foreign amount to convert','',None),
          ('bank_account','INR bank / cash',next(o for o in bank_options if o.startswith('1010')),bank_options),('gross_inr','Actual gross INR proceeds','',None),('fees_inr','INR bank fees','0',None),('reference','Unique conversion reference','',None)]
        for i,(key,label,default,values) in enumerate(specs):
            if i%3==0:top=row(holdings)
            self.fx_conversion[key]=self.field(top,label,default,values,width=25 if key!='payment_date' else 13)
        def conversion_inputs():
            values={k:v.get() for k,v in self.fx_conversion.items()}
            for k in ('bank_account','foreign_account'):values[k]=values[k].split(' · ')[0]
            return values
        preview_controls(holdings,'conversion',conversion_inputs)
        self.fx_preview_receipt=lambda:preview('receipt',receipt_inputs)
        self.fx_post_receipt=lambda:post('receipt',receipt_inputs)
        self.fx_preview_conversion=lambda:preview('conversion',conversion_inputs)
        self.fx_post_conversion=lambda:post('conversion',conversion_inputs)

    def work_volume(self):
        self.note('Work completed for this customer’s books. Counts come from posted vouchers, saved drafts and processed source records. Import/bank/draft breakdowns overlap journal activity; do not add them into a single sales-pitch total.')
        top=self.bar();start,end=self.dates()
        self.work_period=self.field(top,'Period','All time',['All time','Selected dates'],width=15)
        self.work_basis=self.field(top,'Date basis','Work performed (India dates)',['Work performed (India dates)','Book transaction dates'],width=28)
        self.work_from=self.field(top,'From',start,width=13);self.work_to=self.field(top,'Through',end,width=13)
        self.work_include_client=tk.BooleanVar(value=False)
        ttk.Checkbutton(self.content,text='Include client and branch names in exported statistics',variable=self.work_include_client).pack(anchor='w',pady=5)
        actions=self.bar()
        def current():
            return activity.report(self.state,self.work_from.get() if self.work_period.get()=='Selected dates' else None,self.work_to.get() if self.work_period.get()=='Selected dates' else None,self.unit(),'book' if self.work_basis.get()=='Book transaction dates' else 'work')
        def refresh():
            result=current();self.work_table.delete(*self.work_table.get_children())
            for key,value in result['metrics'].items():self.work_table.insert('','end',values=(activity.LABELS[key],value,result['definitions'][key]))
        def export():
            result=current();path=filedialog.asksaveasfilename(initialfile='Client-work-volume.csv',defaultextension='.csv',filetypes=[('Statistics CSV','*.csv')],parent=self)
            if path:activity.export_csv(result,path,self.work_include_client.get());messagebox.showinfo('Saved','Work-volume summary saved. No patient/transaction details are included.',parent=self)
        self.button(actions,'Refresh statistics',refresh,True);self.button(actions,'Export statistics CSV',export)
        self.work_table=self.table(('Metric','Count','Counting rule'),[],height=15)
        self.work_table.column('Metric',width=260);self.work_table.column('Count',width=85);self.work_table.column('Counting rule',width=680)
        ttk.Label(self.content,text='Permanent journal creation and posting are one atomic action, so their counts match. Saved drafts are a separate measure. Use one vault per legal client; this report does not combine different customers’ books.',wraplength=950).pack(anchor='w',pady=8)
        refresh()

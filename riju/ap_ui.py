"""Vendor AP register, due-date processing, source review and forecast."""
from datetime import date,timedelta,datetime
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog,messagebox
from . import ap,core,history,tds,financial_reports as f

class ApUI:
    def ap_invoices(self):
        self.note('Register vendor invoices once: accrual debits cost/asset and credits Trade payables on the accounting date. Actual payment debits payable and credits the chosen cash/bank. Payment schedules affect forecast only; this tool does not send money to a bank.')
        bar=self.bar();self.ap_on=self.field(bar,'As at',datetime.now(history.INDIA).date().isoformat(),width=12)
        self.button(bar,'Refresh AP',self.refresh_ap,True);self.button(bar,'Add vendor',self.ap_vendor);self.button(bar,'Enter invoice',self.ap_enter)
        bar=self.bar();self.button(bar,'Mark selected invoices paid',self.ap_payment,True);self.button(bar,'Extend payment date',self.ap_extend);self.button(bar,'Reverse selected payment',self.ap_reverse_payment);self.button(bar,'Cancel selected invoice',self.ap_cancel_invoice)
        self.ap_summary=ttk.Label(self.content,text='',wraplength=1050);self.ap_summary.pack(anchor='w')
        self.ap_table=self.table(('Vendor','Invoice','Unit','Received','Contractual due','Scheduled payment','Outstanding INR','Status','Accrual voucher'),[],height=9);self.ap_table.configure(selectmode='extended')
        bar=self.bar();self.ap_forecast_end=self.field(bar,'Forecast through',(datetime.now(history.INDIA).date()+timedelta(days=90)).isoformat(),width=12)
        for kind in ('xlsx','pdf'):self.button(bar,'AP register '+kind.upper(),lambda kind=kind:self.export_ap(kind));self.button(bar,'AP forecast '+kind.upper(),lambda kind=kind:self.export_ap_forecast(kind))
        self.ap_payments=self.table(('Payment date','Reference','INR','Voucher','Status'),[],height=4);self.refresh_ap()
    def refresh_ap(self):
        rows=ap.register(self.state,self.ap_on.get(),self.unit());self.ap_rows={r['id']:r for r in rows};self.ap_table.delete(*self.ap_table.get_children())
        for r in rows:self.ap_table.insert('','end',iid=r['id'],values=(r['vendor_name'],r['reference'],r['branch'],r['received_date'],r['due_date'],r['scheduled_date'],core.rupees(r['remaining']),('DUE / OVERDUE — ' if r['overdue'] else '')+r['status'],r['voucher']))
        due=[r for r in rows if r['overdue']];self.ap_summary.configure(text=f'{len(due)} due/overdue invoice(s) | Outstanding '+core.rupees(sum(r['remaining'] for r in rows))+' | Due now '+core.rupees(sum(r['remaining'] for r in due))+'. Select due invoices to record actual payment or extend their scheduled date with a reason.')
        if hasattr(self,'ap_reminder'):self.update_ap_reminder()
        self.ap_payments.delete(*self.ap_payments.get_children());net=tds._net(self.state,self.ap_on.get())
        for p in ap.data(self.state)['payments']:
            if p['date']<=self.ap_on.get() and (self.unit()=='ALL' or p['branch']==self.unit()):self.ap_payments.insert('','end',iid=p['id'],values=(p['date'],p['reference'],core.rupees(sum(i['amount'] for i in p['items'])),p['voucher'],'Active' if net.get(p['voucher'])==1 else 'Reversed'))
    def ap_selected(self,one=False):
        keys=list(self.ap_table.selection())
        if not keys or one and len(keys)!=1:raise ValueError('Select '+('one invoice.' if one else 'one or more invoices.'))
        return keys
    def ap_vendor(self):
        win,body,fields=self._tax_form('Add AP vendor',[('name','Vendor legal/source name','',None),('credit_days','Default credit period calendar days','30',None),('reference','Optional vendor code / source reference','',None)])
        def save():self.commit(lambda s:ap.save_vendor(s,{k:v.get().strip() for k,v in fields.items()}));win.destroy();self.show('AP Vendor Invoices')
        self.button(body,'Save vendor',save,True)
    def ap_enter(self):
        vendors={v['name']+' · '+v['id'][:8]:v['id'] for v in ap.data(self.state)['vendors']}
        if not vendors:raise ValueError('Add a vendor first.')
        on=self.ap_on.get();chosen=next(iter(vendors));supplier=ap.vendor(self.state,vendors[chosen]);unit=self.unit() if self.unit()!='ALL' else 'JP'
        specs=[('vendor','Vendor',chosen,list(vendors)),('reference','Vendor invoice number','',None),('invoice_date','Invoice date',on,None),('received_date','Invoice received date',on,None),('accounting_date','Accrual accounting date',on,None),('credit_days','Credit period calendar days',str(supplier['credit_days']),None),('due_basis','Credit period starts at','Receipt date',['Receipt date','Invoice date']),('payment_date','Scheduled payment date (blank = due)','',None),('branch','Operating unit',unit,list(self.branches)),('amount','Net amount payable to vendor INR','',None),('payable','Trade payables ledger','2000',None),('cost_account','New accrual: cost/asset ledger','4590',None),('existing_voucher','Existing GST/TDS/CWIP accrual voucher (optional)','',None),('basis','Source / tax / accounting review basis','',None)]
        win,body,fields=self._tax_form('Enter AP vendor invoice',specs)
        def vend_changed(*args):fields['credit_days'].set(str(ap.vendor(self.state,vendors[fields['vendor'].get()])['credit_days']))
        fields['vendor'].trace_add('write',vend_changed)
        ttk.Label(body,text='New accrual: one reviewed cost/asset allocation for the amount above. For tax, retention or CWIP: first post the correct source in its dedicated page, then link the original unpaid accrual voucher here. Linking does not create a second expense or tax entry. Due date is contractual; an extension changes only the payment plan.',wraplength=1000).pack(anchor='w')
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed source, period, vendor payable and tax. A new simple accrual needs no separate GST/TDS journal.',variable=confirmed).pack(anchor='w')
        def preview():
            values={k:w.get().strip() for k,w in fields.items()};values.update(vendor=vendors[values['vendor']],reviewed=confirmed.get(),tax_treatment='No separate GST/TDS; reviewed',allocations=[dict(account=values['cost_account'],amount=values['amount'])])
            self._service_preview('Review invoice accrual / existing source link',lambda s:ap.enter_invoice(s,values),win,page='AP Vendor Invoices')
        self.button(body,'Preview invoice accrual',preview,True)
    def ap_payment(self):
        keys=self.ap_selected();rows=[self.ap_rows[k] for k in keys]
        if any(r['remaining']<=0 for r in rows):raise ValueError('Select outstanding invoices only.')
        amount=str(sum(r['remaining'] for r in rows)/100)
        specs=[('date','Actual payment date',self.ap_on.get(),None),('bank_account','Actual cash/bank ledger','1010',None),('reference','Actual payment reference','',None),('existing_voucher','Existing exact payment voucher (optional; avoids reposting)','',None),('amount','Pay amount INR (single invoice may be partial)',amount,None),('basis','Payment evidence / approval basis','',None)]
        win,body,fields=self._tax_form('Record vendor payment',specs);ttk.Label(body,text='Selected: '+'; '.join(r['vendor_name']+' / '+r['reference']+' '+core.rupees(r['remaining']) for r in rows),wraplength=1000).pack(anchor='w')
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I confirm the payment actually occurred and reviewed the source/bank evidence',variable=confirmed).pack(anchor='w')
        def preview():
            v={k:w.get().strip() for k,w in fields.items()};n=ap.positive(v['amount'])
            if len(rows)>1 and n!=sum(r['remaining'] for r in rows):raise ValueError('Multiple selected invoices must be paid in full; pay partial invoices one at a time.')
            v.update(items=[dict(invoice=r['id'],amount=str((n if len(rows)==1 else r['remaining'])/100)) for r in rows],reviewed=confirmed.get());self._service_preview('Review AP payment journal',lambda s:ap.pay(s,v),win,page='AP Vendor Invoices')
        self.button(body,'Preview payment journal',preview,True)
    def ap_extend(self):
        key=self.ap_selected(True)[0];r=self.ap_rows[key];win,body,fields=self._tax_form('Extend AP payment date',[('effective','Extension effective date',self.ap_on.get(),None),('payment_date','New scheduled payment date',r['scheduled_date'],None),('reason','Vendor agreement / extension reason','',None)])
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed the agreed payment extension; this does not change contractual due date or post a journal',variable=confirmed).pack(anchor='w')
        def preview():self._service_preview('Review AP payment extension',lambda s:ap.extend(s,key,fields['effective'].get(),fields['payment_date'].get(),fields['reason'].get(),confirmed.get()),win,page='AP Vendor Invoices')
        self.button(body,'Preview payment extension',preview,True)
    def ap_reverse_payment(self):
        if not self.ap_payments.selection():raise ValueError('Select a payment in the payment-history table.')
        p=next(p for p in ap.data(self.state)['payments'] if p['id']==self.ap_payments.selection()[0]);on=simpledialog.askstring('Reverse AP payment','Actual correction/reversal date YYYY-MM-DD:',initialvalue=self.ap_on.get(),parent=self)
        if on:self._service_preview('Review AP payment reversal',lambda s:core.reverse(s,p['voucher'],on),page='AP Vendor Invoices')
    def ap_cancel_invoice(self):
        r=self.ap_rows[self.ap_selected(True)[0]];on=simpledialog.askstring('Cancel AP invoice','Actual cancellation accounting date YYYY-MM-DD. Reverse dependent payments first. Linked GST/TDS/CWIP sources retain their own reversal guards:',initialvalue=self.ap_on.get(),parent=self)
        if on:
            reason=simpledialog.askstring('Invoice cancellation evidence','Source reason for cancelling this invoice accrual:',parent=self)
            if reason:self._service_preview('Review AP invoice accrual reversal',lambda s:ap.cancel_invoice(s,r['id'],on,reason,True),page='AP Vendor Invoices')
    def export_ap(self,kind):
        self.refresh_ap();start=min([self.ap_on.get()]+[r['accounting_date'] for r in self.ap_rows.values()]);packs=ap.snapshots(self.state,start,self.ap_on.get(),self.unit());self.ap_export(packs,kind)
    def export_ap_forecast(self,kind):self.ap_export([ap.forecast_snapshot(self.state,self.ap_on.get(),self.ap_on.get(),self.ap_forecast_end.get(),self.unit())],kind)
    def ap_export(self,packs,kind):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:(f.export_pack_xlsx if kind=='xlsx' else f.export_pdf)(packs,path)
    def update_ap_reminder(self):
        prior=getattr(self,'_ap_reminder_after',None)
        if prior:self.after_cancel(prior)
        on=datetime.now(history.INDIA).date().isoformat();rows=[r for r in ap.register(self.state,on) if r['overdue']]
        self.ap_reminder.configure(text=('AP PAYMENT DUE: '+str(len(rows))+' invoice(s), '+core.rupees(sum(r['remaining'] for r in rows))+' — open AP to pay or extend' if rows else 'AP Vendor Invoices — no scheduled payments due today'))
        self._ap_reminder_after=self.after(60000,self.update_ap_reminder)

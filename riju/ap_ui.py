"""Vendor AP register, due-date processing, source review and forecast."""
from .date_picker import ask_date
from datetime import date,timedelta,datetime
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog,messagebox
from . import ap,core,history,tds,financial_reports as f

class ApUI:
    def ap_invoices(self):
        self.note('Register vendor invoices once: accrual debits cost/asset and credits Trade payables on the accounting date. Actual payment debits payable and credits the chosen cash/bank. Payment schedules affect forecast only; this tool does not send money to a bank.')
        bar=self.bar();self.ap_on=self.field(bar,'As at',datetime.now(history.INDIA).date().isoformat(),width=12)
        self.button(bar,'Refresh AP',self.refresh_ap,True);self.button(bar,'Add vendor',self.ap_vendor);self.button(bar,'Vendor master',lambda:self.show('Vendor master'));self.button(bar,'Enter invoice',self.ap_enter);self.button(bar,'Upload bulk invoices',self.upload_bulk_invoices,True)
        bar=self.bar();self.button(bar,'Bulk invoice Excel template',lambda:self.ap_bulk_template('xlsx'));self.button(bar,'Bulk invoice CSV template',lambda:self.ap_bulk_template('csv'));self.button(bar,'Review bulk invoice batches',self.ap_bulk_batches)
        bar=self.bar();self.button(bar,'Mark selected invoices paid',self.ap_payment,True);self.button(bar,'Extend payment date',self.ap_extend);self.button(bar,'Correct selected payment date',self.ap_correct_payment_date,True);self.button(bar,'Reverse selected payment',self.ap_reverse_payment);self.button(bar,'Cancel selected invoice',self.ap_cancel_invoice)
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
    def vendor_master(self):
        self.note('Saved AP vendors. Edit name, credit days, reference or active status here. Vendor ID remains stable. Posted invoices retain their original vendor/source snapshot and credit terms; edits apply to new invoices.')
        bar=self.bar();self.button(bar,'Add vendor',self.ap_vendor,True);self.button(bar,'Edit selected vendor',self.ap_edit_vendor);self.button(bar,'Upload bulk vendors',self.upload_vendor_master,True)
        templates=self.bar();self.button(templates,'Vendor template — Excel',lambda:self.vendor_master_template('xlsx'));self.button(templates,'Vendor template — CSV',lambda:self.vendor_master_template('csv'))
        self.vendor_table=self.table(('Vendor ID','Vendor name','Default credit days','Reference','Active'),[],height=12)
        for v in ap.data(self.state)['vendors']:self.vendor_table.insert('','end',iid=v['id'],values=(v['id'],v['name'],v['credit_days'],v['reference'],'Yes' if v.get('active',True) else 'No'))
        self.vendor_table.bind('<Double-1>',lambda e:self.guarded(self.ap_edit_vendor))
    def vendor_master_template(self,kind):
        from . import vendor_import
        path=filedialog.asksaveasfilename(parent=self,initialfile='Yathartha-Vendor-Master-Template.'+kind,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:vendor_import.template(path);messagebox.showinfo('Vendor template saved',str(path)+'\nUse the Vendors sheet. The template mirrors individual vendor entry; no vendors have been created.',parent=self)
    def upload_vendor_master(self):
        from . import vendor_import
        path=filedialog.askopenfilename(parent=self,title='Upload vendor master',filetypes=[('Vendor CSV / Excel','*.csv *.xlsx')])
        if not path:return
        from pathlib import Path
        plan=vendor_import.preview(self.state,Path(path).read_bytes(),Path(path).name)
        win=tk.Toplevel(self);win.title('Review bulk vendor master — '+plan['filename']);win.geometry('1180x650');win.transient(self)
        counts={k:sum(r['status']==k for r in plan['rows']) for k in ('NEW','INVALID','DUPLICATE')}
        ttk.Label(win,text=str(counts)+' | Ignored default-only rows '+str(plan['ignored'])+'\nSelect NEW rows to create vendors. Existing masters are never overwritten. No journals or opening balances are created.',wraplength=1130,padding=8).pack(anchor='w')
        detail=ttk.Label(win,text='Select a row for its full validation reason.',wraplength=1130,padding=8);detail.pack(anchor='w',fill='x')
        table=self.table(('Row','Vendor name','Credit days','Reference','Active','Status','Reason / correction'),[],parent=win,height=12);table.configure(selectmode='extended');table.column('Row',width=55,stretch=False);table.column('Reason / correction',width=350);table.column('Vendor name',width=220)
        table.tag_configure('INVALID',background='#FCE8E6',foreground='#8B1A12');table.tag_configure('DUPLICATE',background='#FFF1CB',foreground='#754600')
        for i,r in enumerate(plan['rows']):
            raw=r['raw'];v=r.get('values',{});table.insert('','end',iid=str(i),tags=(r['status'],),values=(r['source_row'],raw.get('name',''),v.get('credit_days',raw.get('credit_days','')),raw.get('reference',''),'Yes' if v.get('active') is True else 'No' if v.get('active') is False else raw.get('active',''),r['status'],r['error'] or 'Ready to create new vendor'))
        def selected(event=None):
            if table.selection():
                r=plan['rows'][int(table.selection()[0])];detail.configure(text='Source row '+str(r['source_row'])+' | '+r['raw'].get('name','')+' | '+r['status']+': '+(r['error'] or 'Ready to create new vendor'),foreground='#9C261B' if r['status']!='NEW' else '#154C8A')
        table.bind('<<TreeviewSelect>>',selected)
        def selectnew():
            table.selection_set([str(i) for i,r in enumerate(plan['rows']) if r['status']=='NEW']);selected()
        def save():
            indices=[int(i) for i in table.selection()];created=self.commit(lambda s:vendor_import.save_selected(s,plan,indices));win.destroy();self.show('Vendor master');messagebox.showinfo('Vendor master imported',str(len(created))+' new vendor(s) saved. Existing vendors were not changed. No journal entries were posted.',parent=self)
        bar=ttk.Frame(win);bar.pack(fill='x',pady=10);self.button(bar,'Select all new vendors',selectnew);self.button(bar,'Save selected new vendors',save,True);self.button(bar,'Close without saving',win.destroy)
        target=next((str(i) for i,r in enumerate(plan['rows']) if r['status']!='NEW'),None)
        if target is not None:table.selection_set(target);table.see(target);selected()

    def ap_edit_vendor(self):
        if not self.vendor_table.selection():raise ValueError('Select a vendor in Vendor master to edit.')
        self.ap_vendor(self.vendor_table.selection()[0])
    def ap_vendor(self,key=None):
        old=ap.vendor(self.state,key) if key else {};page='Vendor master' if self.current=='Vendor master' else 'AP Vendor Invoices'
        win,body,fields=self._tax_form('Edit AP vendor' if key else 'Add AP vendor',[('name','Vendor legal/source name',old.get('name',''),None),('credit_days','Default credit period calendar days',str(old.get('credit_days',30)),None),('reference','Optional vendor code / source reference',old.get('reference',''),None)])
        active=tk.BooleanVar(value=old.get('active',True));ttk.Checkbutton(body,text='Active vendor (inactive vendors remain in history)',variable=active).pack(anchor='w')
        def save():
            values={k:v.get().strip() for k,v in fields.items()};values['active']=active.get();self.commit(lambda s:ap.save_vendor(s,values,key));win.destroy();self.show(page)
        self.button(body,'Save vendor',save,True)
    def ap_enter(self):
        vendors={v['name']+' · '+v['id'][:8]:v['id'] for v in ap.data(self.state)['vendors'] if v.get('active',True)}
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
    def ap_correct_payment_date(self):
        if not self.ap_payments.selection():raise ValueError('Select the payment in the lower payment-history table. Set As at to include its recorded date, then Refresh AP.')
        key=self.ap_payments.selection()[0];p=next(p for p in ap.data(self.state)['payments'] if p['id']==key)
        win,body,fields=self._tax_form('Correct AP payment date',[('date','Correct actual bank payment date',p['date'],None),('basis','Bank evidence / correction reason','',None)])
        allocations='; '.join(ap.invoice(self.state,i['invoice'])['vendor_name']+' / '+ap.invoice(self.state,i['invoice'])['reference']+' / '+ap.invoice(self.state,i['invoice'])['branch']+' / '+core.rupees(i['amount']) for i in p['items'])
        ttk.Label(body,text=p['voucher']+' | Recorded '+p['date']+' | '+p['reference']+' | '+core.rupees(sum(i['amount'] for i in p['items']))+'\nAllocated to: '+allocations+'\nThe bank/reference, amount, unit and invoice allocation stay the same. The wrong posting is cancelled on its recorded date and replaced on the actual bank date. No expense is posted again. Active bank matches must be undone first; closed periods require review/reopening.',wraplength=1020,padding=8).pack(anchor='w')
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I verified the actual payment date against bank evidence and reviewed the correction.',variable=confirmed).pack(anchor='w')
        def preview():self._service_preview('Review AP payment-date correction',lambda s:ap.correct_payment_date(s,key,fields['date'].get().strip(),fields['basis'].get().strip(),confirmed.get()),win,page='AP Vendor Invoices')
        self.button(body,'Preview payment-date correction',preview,True)

    def ap_reverse_payment(self):
        if not self.ap_payments.selection():raise ValueError('Select a payment in the payment-history table.')
        p=next(p for p in ap.data(self.state)['payments'] if p['id']==self.ap_payments.selection()[0]);on=ask_date('Reverse AP payment','Actual correction/reversal date YYYY-MM-DD:',initialvalue=self.ap_on.get(),parent=self)
        if on:self._service_preview('Review AP payment reversal',lambda s:core.reverse(s,p['voucher'],on),page='AP Vendor Invoices')
    def ap_cancel_invoice(self):
        r=self.ap_rows[self.ap_selected(True)[0]];on=ask_date('Cancel AP invoice','Actual cancellation accounting date YYYY-MM-DD. Reverse dependent payments first. Linked GST/TDS/CWIP sources retain their own reversal guards:',initialvalue=self.ap_on.get(),parent=self)
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

"""Guided source-linked service revenue review."""
import copy
import json
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog
from . import service_revenue as sr,core,tax

class ServiceRevenueUI:
    def service_revenue(self):
        self.note('Service/package revenue: record direct earned receipts, unearned advances or bills. Select original sources to recognize advance-funded services, collect bills, cancel services or refund actual credits. Shared Patient A/C; no per-patient ledger or ageing. Use separate service rows/actions for differently taxed services. Taxed advances retain their original tax; earning never posts tax twice. All actions require actual service/tax/source review.')
        bar=self.bar();self.service_end=self.field(bar,'Service as at',getattr(self,'service_report_end',self.dates()[1]),width=14)
        def refresh():self.service_report_end=self.service_end.get();self.show('Service revenue')
        self.button(bar,'Refresh service reports',refresh)
        bar=self.bar()
        for kind in sr.KINDS[:3]:self.button(bar,kind,lambda k=kind:self.service_action(k))
        bar=self.bar()
        for kind in sr.KINDS[3:]:self.button(bar,kind,lambda k=kind:self.service_action(k))
        bar=self.bar();self.button(bar,'Reverse service action',self.reverse_service_action)
        for kind in ('xlsx','pdf'):self.button(bar,'Export '+('Excel' if kind=='xlsx' else 'PDF'),lambda k=kind:self.export_service_revenue(k))
        start,_=self.dates();end=self.service_end.get();r=sr.report(self.state,min(start,end),end,self.unit());self.service_report=r
        self.service_table=self.table(('Date','Reference','Action','Unit','Package','Source ID','Parent','Revenue','Base','Gross','Unearned gross','Voucher','State','GST rule','Basis','Bill outstanding Dr/(Cr)'),[[core.rupees(v) if i in (8,9) or i in (10,15) and isinstance(v,int) else v for i,v in enumerate(row)] for row in r['rows']],height=10);self.service_rows=dict(zip(self.service_table.get_children(),r['rows']))
        self.table(('Unit','Control','Source Dr/(Cr)','Ledger Dr/(Cr)','Unallocated'),[[*r[:2],*[core.rupees(n) for n in r[2:]]] for r in r['proof']],height=5)
        self.note('Control differences include other/manual workflows and must be reviewed; they are not automatically allocated to a package. Source documents are cumulative as at the selected date. Taxed advances contribute to the GST tax-point working base; accounting revenue is recognized only when earned.')

    def _selected_service(self):
        if not self.service_table.selection():raise ValueError('Select the original advance/bill or action first.')
        return sr.get(self.state,self.service_rows[self.service_table.selection()[0]][5])

    def _service_preview(self,title,action,form=None,page='Service revenue'):
        before=copy.deepcopy(self.state);candidate=copy.deepcopy(before);result=action(candidate)
        win=tk.Toplevel(self);win.title(title);win.geometry('1000x650');win.transient(form or self);win.grab_set()
        bar=ttk.Frame(win);bar.pack(side='bottom',fill='x');text=tk.Text(win,wrap='word');text.pack(fill='both',expand=True);text.insert('1.0',json.dumps(dict(result=result,journals=candidate['vouchers'][len(before['vouchers']):]),ensure_ascii=False,indent=2));text.configure(state='disabled')
        def approve():
            if self.state!=before:raise ValueError('Books changed after preview. Review a fresh service action.')
            def save(s):s.clear();s.update(copy.deepcopy(candidate));return result
            self.commit(save);win.destroy()
            if form and form.winfo_exists():form.destroy()
            self.show(page)
        self.button(bar,'Approve service action' if page=='Service revenue' else 'Approve bulk import' if page=='Bulk import review' else 'Approve sales batch' if page=='Sales receipt' else 'Approve AP action' if page=='AP Vendor Invoices' else 'Approve provision' if page=='Statement review' else 'Approve GST action',approve,True)

    def service_action(self,kind):
        source=None if kind in sr.KINDS[:3] else self._selected_service();rules=sorted({r['key'] for r in tax.rules(self.state) if r['family']=='GST'})
        unit=source['branch'] if source else self.unit() if self.unit()!='ALL' else 'JP'
        specs=[('date','Action date',self.service_end.get(),None),('reference','Unique action reference','',None),('branch','Unit code',unit,list(self.branches)),('package','Package / optional source reference','',None),('amount','Service / allocated gross INR','',None),('account','Revenue ledger','4000',None),('rule_key','Reviewed GST rule',rules[0] if rules else '',rules or None),('registration','Supplying GSTIN (required for taxable)','',None),('place_of_supply','Place of supply state code','',None),('existing','Existing original voucher (blank posts new)','',None),('basis','Service / tax / source review basis','',None)]
        win,body,f=self._tax_form(kind,specs);inclusive=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='New original service amount includes GST',variable=inclusive).pack(anchor='w')
        ttk.Label(body,text='Actual split payments JSON: {"1000":"100", "1110":"200"}. Amounts INR. Leave {} for billing, earning or cancellation. For source actions, service/rate/branch facts come from the original source, and amount is gross. For new originals, enter a reviewed revenue ledger/rule per service.').pack(anchor='w')
        payments=self.field(body,'Actual payments JSON','{}',width=75);reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed service completion/cancellation, sources, tax point, applicability and payment evidence',variable=reviewed).pack(anchor='w',pady=8)
        def preview():
            values={k:v.get().strip() for k,v in f.items()};values.update(payments=json.loads(payments.get()),inclusive=inclusive.get(),reviewed=reviewed.get(),source=source['id'] if source else '')
            self._service_preview(kind,lambda s:sr.link_existing(s,kind,values,values['existing']) if values['existing'] else sr.post(s,kind,values),win)
        self.button(body,'Validate service preview',preview,True)

    def reverse_service_action(self):
        r=self._selected_service();on=simpledialog.askstring('Reverse service action','Reversal date YYYY-MM-DD:',initialvalue=self.service_end.get(),parent=self)
        if on:self._service_preview('Reverse service action',lambda s:core.reverse(s,r['voucher'],on))

    def export_service_revenue(self,kind):
        start,_=self.dates();end=self.service_end.get();path=filedialog.asksaveasfilename(parent=self,initialfile='service-revenue.'+kind,defaultextension='.'+kind)
        if path:sr.export(self.state,min(start,end),end,self.unit(),path,kind)

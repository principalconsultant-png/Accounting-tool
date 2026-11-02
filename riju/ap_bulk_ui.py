"""Bulk invoice upload/review beside manual AP entry."""
from pathlib import Path
import json
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog,messagebox
from . import ap_bulk as bulk,core,financial_reports as reports

class ApBulkUI:
    def ap_bulk_template(self,kind):
        path=filedialog.asksaveasfilename(parent=self,initialfile='Yathartha-AP-Bulk-Invoices-Template.'+kind,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:bulk.template(path,self.state);messagebox.showinfo('AP invoice template saved','The template has the same fields as Enter invoice. Excel includes vendor/unit/account lookup snapshots. Use Trade payables (vendor liability), not a tax-payable ledger. No invoice has been posted.',parent=self)
    def upload_bulk_invoices(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Invoice workbook or CSV','*.xlsx *.csv')])
        if not path:return
        raw=Path(path).read_bytes();sheet=None
        try:sheet=bulk._sheet(raw,Path(path).name,None)
        except ValueError as error:
            if 'multiple sheets' not in str(error):raise
            sheet=simpledialog.askstring('Invoice worksheet','This workbook has multiple sheets and no Invoices sheet. Enter the exact sheet to import:',parent=self)
            if not sheet:return
        q=self.commit(lambda s:bulk.stage(s,raw,Path(path).name,sheet));self.ap_bulk_review(q['id'])
    def ap_bulk_batches(self):
        batches=[q for q in self.state['queue'] if q.get('kind')=='ap_bulk']
        if not batches:raise ValueError('Upload a bulk invoice file first.')
        win=tk.Toplevel(self);win.title('AP bulk invoice batches');win.geometry('1050x500');table=self.table(('ID','File','Rows','Status'),[(q['id'],q['filename'],len(q['rows']),q['status']) for q in batches],parent=win)
        def openbatch():
            if not table.selection():raise ValueError('Select a bulk invoice batch.')
            key=batches[table.index(table.selection()[0])]['id'];win.destroy();self.ap_bulk_review(key)
        self.button(win,'Review selected batch',openbatch,True)
    def ap_bulk_review(self,key):
        q=bulk.batch(self.state,key);win=tk.Toplevel(self);win.title('Review AP bulk invoices — '+q['filename']);win.geometry('1200x760');win.transient(self)
        status=ttk.Label(win,text='',wraplength=1150);status.pack(anchor='w');flagged=tk.BooleanVar(value=False)
        table=self.table(('Row','Vendor','Invoice','Unit','Invoice date','Received','Accrual date','Credit days','Credit starts','Due date','Scheduled','Payable INR','AP ledger','Cost / existing source','Validation','Decision'),[],parent=win,height=10);table.configure(selectmode='extended')
        detail=ttk.Label(win,text='Select a row for its error/review evidence; View selected invoice shows all original/resolved fields.',wraplength=1150);detail.pack(anchor='w')
        confirmed=tk.BooleanVar(value=False)
        def refresh():
            q=bulk.batch(self.state,key);table.delete(*table.get_children());counts={k:sum(r['validation']==k for r in q['rows']) for k in ('VALID','INVALID','DUPLICATE')};approved=sum(r.get('amount',0) for r in q['rows'] if r['review']=='APPROVED');total=sum(r.get('amount',0) for r in q['rows'] if r['validation']=='VALID')
            status.configure(text=q['status']+' | '+str(len(q['rows']))+' invoices | '+str(counts)+' | Valid source '+core.rupees(total)+' | Approved '+core.rupees(approved)+' | Ignored default-only rows '+str(q['ignored_placeholders'])+'\n'+'\n'.join(q['warnings']))
            names={a['code']:a['name'] for a in self.state['accounts']}
            for i,r in enumerate(q['rows']):
                if flagged.get() and r['validation']=='VALID':continue
                v=r.get('values',{});cost=next((a['account'] for a in v.get('allocations',[])),v.get('existing_voucher',''));payable=v.get('payable','')
                table.insert('','end',iid=str(i),values=(r['source_row'],r.get('vendor_name',r['raw'].get('vendor_name','')),r.get('reference',r['raw'].get('reference','')),r.get('branch',''),v.get('invoice_date',''),v.get('received_date',''),r.get('date',''),v.get('credit_days',''),v.get('due_basis',''),r.get('due_date',''),r.get('payment_date',''),core.rupees(r.get('amount',0)),payable+' '+names.get(payable,''),cost+' '+names.get(cost,''),r['validation'],r['review']))
        def selected(event=None):
            if table.selection():
                r=bulk.batch(self.state,key)['rows'][int(table.selection()[0])];detail.configure(text=r['error']+' | '+r['reason']+' | Invoice accounting basis: '+r['raw'].get('basis',''))
        table.bind('<<TreeviewSelect>>',selected);filters=ttk.Frame(win);filters.pack(fill='x');ttk.Checkbutton(filters,text='Show flagged rows only',variable=flagged,command=refresh).pack(side='left')
        def viewrow():
            if not table.selection():raise ValueError('Select a source invoice.')
            r=bulk.batch(self.state,key)['rows'][int(table.selection()[0])];view=tk.Toplevel(win);view.title('Invoice source details');view.geometry('950x600');text=tk.Text(view,wrap='word');text.pack(fill='both',expand=True);text.insert('1.0',json.dumps(r,ensure_ascii=False,indent=2));text.configure(state='disabled')
        self.button(filters,'View selected invoice',viewrow)
        ttk.Checkbutton(win,text='I reviewed vendor/source, period, cost/asset account and net payable/tax. New simple accruals need no separate GST/TDS; existing source links were verified.',variable=confirmed).pack(anchor='w')
        def review(approved,allrows=False):
            q=bulk.batch(self.state,key);indices=([i for i,r in enumerate(q['rows']) if (r['validation']=='VALID' and r['review']!='REJECTED' if approved else r['validation']!='VALID' and r['review']!='REJECTED')] if allrows else [int(i) for i in table.selection()])
            if not indices:raise ValueError('Select invoice rows; no matching unreviewed rows exist for this action.')
            if approved and not confirmed.get():raise ValueError('Confirm source/accounting/tax review before approval. Rejections do not require that checkbox.')
            reason=simpledialog.askstring('AP invoice review','Approval basis:' if approved else 'Rejection/correction reason:',parent=win)
            if reason:self.commit(lambda s:bulk.review(s,key,indices,approved,reason,confirmed.get()));refresh()
        bar=ttk.Frame(win);bar.pack(fill='x');self.button(bar,'Approve selected rows',lambda:review(True));self.button(bar,'Reject selected rows',lambda:review(False));self.button(bar,'Approve all valid invoices',lambda:review(True,True),True);self.button(bar,'Reject flagged rows',lambda:review(False,True))
        def revalidate():
            self.commit(lambda s:bulk.revalidate(s,key));confirmed.set(False);refresh();messagebox.showinfo('Batch revalidated','Source rows rechecked. Previous approvals cleared; explicit rejections retained. Review fresh values before approval.',parent=win)
        def cancel():
            reason=simpledialog.askstring('Cancel unused AP batch','Reason for cancelling this pending import:',parent=win)
            if reason:self.commit(lambda s:bulk.cancel(s,key,reason));refresh()
        bar=ttk.Frame(win);bar.pack(fill='x');self.button(bar,'Revalidate after master changes',revalidate);self.button(bar,'Cancel unused batch',cancel)
        def preview():
            if not confirmed.get():raise ValueError('Confirm vendor/source/accounting/tax review before previewing approved invoices.')
            self._service_preview('Review AP bulk invoice accruals',lambda s:bulk.post(s,key),win,page='AP Vendor Invoices')
        self.button(bar,'Preview invoice journals',preview,True)
        def export(kind):
            pack=bulk.snapshot(self.state,key);path=filedialog.asksaveasfilename(parent=win,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
            if path:(reports.export_xlsx if kind=='xlsx' else reports.export_pdf)(pack,path)
        self.button(bar,'Review Excel',lambda:export('xlsx'));self.button(bar,'Review PDF',lambda:export('pdf'));refresh()

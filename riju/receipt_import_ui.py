"""Batch sales receipt import directly from the Sales receipt screen."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog,messagebox
from . import receipt_import as ri,financial_reports as f,core

class ReceiptImportUI:
    def sales_report_template(self,kind):
        path=filedialog.asksaveasfilename(parent=self,initialfile='riju-sales-receipts-template.'+kind,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:ri.template(path);messagebox.showinfo('Standard receipt template','Template saved. One earned receipt per row, 15 revenue categories and five payment splits. Use literal values; review Instructions / the user guide before import.',parent=self)
    def import_sales_report(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Standard receipt report','*.xlsx *.csv')])
        if not path:return
        q=self.commit(lambda s:ri.stage(s,Path(path).read_bytes(),Path(path).name));self.receipt_import_review(q['id'])
    def review_sales_reports(self):
        batches=[q for q in self.state['queue'] if q.get('kind')=='standard_sales']
        if not batches:raise ValueError('Import a standard sales receipt report first.')
        win=tk.Toplevel(self);win.title('Sales receipt report batches');win.geometry('1000x500')
        table=self.table(('ID','File','Rows','Status'),[(q['id'],q['filename'],len(q['rows']),q['status']) for q in batches],parent=win)
        def openbatch():
            if not table.selection():raise ValueError('Select a report batch.')
            key=batches[table.index(table.selection()[0])]['id'];win.destroy();self.receipt_import_review(key)
        self.button(win,'Review selected report',openbatch,True)
    def receipt_import_review(self,key):
        q=ri._batch(self.state,key);win=tk.Toplevel(self);win.title('Review sales receipts — '+q['filename']);win.geometry('1180x720');win.transient(self)
        status=ttk.Label(win,text='',wraplength=1100);status.pack(anchor='w');table=self.table(('Source row','Date','Unit','Receipt','Revenue INR','Payments INR','Validation','Decision','Error / reason'),[],parent=win,height=12);table.configure(selectmode='extended')
        breakdown=ttk.Label(win,text='',wraplength=1100);breakdown.pack(anchor='w')
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(win,text='I reviewed earned services, source totals, actual payment splits and no separate GST/TDS treatment; this batch contains no advances/refunds or duplicate manual receipts',variable=confirmed).pack(anchor='w')
        def refresh():
            batch=ri._batch(self.state,key);table.delete(*table.get_children());totals={k:sum(r['validation']==k for r in batch['rows']) for k in ('VALID','INVALID','DUPLICATE')};status.configure(text=f'{len(batch["rows"])} source rows | '+str(totals)+' | '+batch['status']+' | Nothing posts until all rows have decisions and batch preview is approved.')
            pack=ri.totals_snapshot(self.state,key);valid=sum(r.get('amount',0) for r in batch['rows'] if r['validation']=='VALID');approved=sum(r.get('amount',0) for r in batch['rows'] if r['review']=='APPROVED')
            breakdown.configure(text='Valid source total '+core.rupees(valid)+' | Approved to post '+core.rupees(approved)+' | '+'; '.join(r[0]+' '+r[1]+' '+core.rupees(r[2]) for r in pack['rows'] if r[2]))
            for i,r in enumerate(batch['rows']):table.insert('','end',iid=str(i),values=(r['source_row'],r.get('date',''),r.get('branch',''),r.get('receipt',''),core.rupees(r.get('amount',0)),core.rupees(sum(r.get('payments',{}).values())),r['validation'],r['review'],r['error']+' '+r['reason']))
        refresh();bar=ttk.Frame(win);bar.pack(fill='x')
        def review(approved,bulk=False):
            batch=ri._batch(self.state,key)
            indices=[i for i,r in enumerate(batch['rows']) if (r['validation']=='VALID' if approved else r['validation']!='VALID')] if bulk else [int(i) for i in table.selection()]
            reason=simpledialog.askstring('Receipt source review','Review/approval basis:' if approved else 'Rejection/correction reason:',parent=win)
            if reason:self.commit(lambda s:ri.review(s,key,indices,approved,reason,confirmed.get()));refresh()
        self.button(bar,'Approve selected rows',lambda:review(True));self.button(bar,'Reject selected rows',lambda:review(False));self.button(bar,'Approve all valid rows',lambda:review(True,True),True);self.button(bar,'Reject flagged rows',lambda:review(False,True))
        bar=ttk.Frame(win);bar.pack(fill='x')
        def post():
            if not confirmed.get():raise ValueError('Confirm earned-source, tax and payment review first.')
            self._service_preview('Review standard sales receipt batch',lambda s:ri.post(s,key),win,page='Sales receipt')
        self.button(bar,'Preview batch journals',post,True)
        def export(kind):
            packs=[ri.snapshot(self.state,key),ri.totals_snapshot(self.state,key)];path=filedialog.asksaveasfilename(parent=win,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
            if path:(f.export_pack_xlsx if kind=='xlsx' else f.export_pdf)(packs,path)
        self.button(bar,'Review Excel',lambda:export('xlsx'));self.button(bar,'Review PDF',lambda:export('pdf'))

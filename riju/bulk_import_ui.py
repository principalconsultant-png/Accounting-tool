"""Mapped bulk import and source-row review desktop."""
import json
from pathlib import Path
from tkinter import filedialog,simpledialog,ttk
from . import bulk_import as bulk,core

class BulkImportUI:
    def bulk_imports(self):
        self.note('Mapped expense, petty-cash, journal and opening CSV/XLSX. Staging never posts. Each source row needs approval or reasoned rejection. Duplicate branch/date/reference blocks changed-file reuse. Explicit journal_id groups must be approved together. Openings group by unit/date into one journal. Existing daily-sales ingestion remains available in Import queue.')
        bar=self.bar();self.bulk_type=self.field(bar,'Import type','Expense',list(bulk.TYPES),width=14);self.bulk_sheet=self.field(bar,'XLSX sheet (exact)','',width=18);self.button(bar,'Stage mapped file',self.stage_bulk,True);self.button(bar,'Download bulk template',self.bulk_template)
        self.bulk_mapping=self.field(self.bar(),'Mapping JSON (blank uses standard headings)','',width=110)
        self.bulk_batches=self.table(('ID','File','Type','Rows','Status'),[(q['id'],q['filename'],q['type'],len(q['rows']),q['status']) for q in self.state['queue'] if q.get('kind')=='bulk'],height=5);self.bulk_batch_ids=dict(zip(self.bulk_batches.get_children(),[q['id'] for q in self.state['queue'] if q.get('kind')=='bulk']))
        bar=self.bar();self.button(bar,'Open selected batch',self.open_bulk_rows);self.button(bar,'Approve selected row',lambda:self.review_bulk_row(True));self.button(bar,'Reject selected row',lambda:self.review_bulk_row(False));self.button(bar,'Post reviewed batch',self.post_bulk,True);self.button(bar,'Cancel unposted batch',self.cancel_bulk)
        bar=self.bar()
        for kind in ('xlsx','pdf'):self.button(bar,'Export review '+('Excel' if kind=='xlsx' else 'PDF'),lambda k=kind:self.export_bulk(k))
        self.bulk_rows=self.table(('Source row','Date','Reference','Unit','Narration','Debit','Credit','Amount','Review','Error / reason'),[],height=10);self.bulk_row_ids={}

    def _bulk_selected(self):
        if not self.bulk_batches.selection():raise ValueError('Select a mapped bulk batch first.')
        return bulk._queue(self.state,self.bulk_batch_ids[self.bulk_batches.selection()[0]])

    def open_bulk_rows(self):
        q=self._bulk_selected();self.bulk_rows.delete(*self.bulk_rows.get_children());self.bulk_row_ids={}
        for i,r in enumerate(q['rows']):
            item=self.bulk_rows.insert('','end',values=(r['source_row'],r.get('date',''),r.get('reference',''),r.get('branch',''),r.get('narration',''),r.get('debit_account',''),r.get('credit_account',''),core.rupees(r['amount']) if type(r.get('amount'))==int else str(r.get('amount','')),r['review'],r['reason'] or r['error']));self.bulk_row_ids[item]=i

    def stage_bulk(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Reviewable imports','*.csv *.xlsx')])
        if not path:return
        raw=Path(path).read_bytes();kind=self.bulk_type.get();sheet=self.bulk_sheet.get();mapping=json.loads(self.bulk_mapping.get()) if self.bulk_mapping.get().strip() else None
        self.commit(lambda s:bulk.stage(s,raw,Path(path).name,kind,mapping,sheet));self.show('Bulk import review')

    def bulk_template(self):
        path=filedialog.asksaveasfilename(parent=self,initialfile='bulk-'+self.bulk_type.get().lower().replace(' ','-')+'.csv',defaultextension='.csv')
        if path:bulk.template(path,self.bulk_type.get())

    def review_bulk_row(self,approved):
        q=self._bulk_selected()
        if not self.bulk_rows.selection():raise ValueError('Open the batch and select a source row.')
        i=self.bulk_row_ids[self.bulk_rows.selection()[0]];reason=simpledialog.askstring('Source row review','Approval/rejection basis:',parent=self)
        if reason:self.commit(lambda s:bulk.review_row(s,q['id'],i,approved,reason));self.open_bulk_rows()

    def post_bulk(self):
        q=self._bulk_selected();self._service_preview('Review atomic bulk approval',lambda s:bulk.approve(s,q['id']),page='Bulk import review')

    def cancel_bulk(self):
        q=self._bulk_selected();reason=simpledialog.askstring('Cancel unposted batch','Cancellation reason:',parent=self)
        if reason:self.commit(lambda s:bulk.cancel(s,q['id'],reason));self.show('Bulk import review')

    def export_bulk(self,kind):
        q=self._bulk_selected();path=filedialog.asksaveasfilename(parent=self,initialfile='bulk-review.'+kind,defaultextension='.'+kind)
        if path:bulk.export(self.state,q['id'],path,kind)

    def review_sales_rows(self,qid):
        import tkinter as tk
        from . import sales_import
        q=next((q for q in self.state['queue'] if q['id']==qid and q.get('kind')=='daily_sales'),None)
        if not q or q['status']!='PENDING_REVIEW':raise ValueError('Select a pending daily-sales import.')
        win=tk.Toplevel(self);win.title('Review individual sales sources');win.geometry('1000x600')
        table=self.table(('Row','Date','Receipt','Gross INR','Review'),[(i,r['date'],r['receipt'],core.rupees(r['amount']),q.get('row_reviews',{}).get(str(i),{}).get('status','PENDING')) for i,r in enumerate(q['rows'])],parent=win)
        def decide(approved):
            if not table.selection():raise ValueError('Select a sales source row.')
            i=table.index(table.selection()[0]);reason=simpledialog.askstring('Sales source review','Review/rejection basis:',parent=win)
            if reason:self.commit(lambda s:sales_import.review_sales_row(s,qid,i,approved,reason));table.set(table.selection()[0],'Review','APPROVED' if approved else 'REJECTED')
        self.button(win,'Approve selected sales row',lambda:decide(True),True);self.button(win,'Reject selected sales row',lambda:decide(False))

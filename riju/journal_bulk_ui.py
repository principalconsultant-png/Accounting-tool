"""Journal studio imports: general balanced pairs and monthly salary sources."""
import copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import core,bulk_import as bulk,salary_bulk
from .journal_preview import render

class JournalBulkUI:
    def journal_bulk_upload(self,salary=False):
        path=filedialog.askopenfilename(parent=self,title='Upload salary journals' if salary else 'Upload general journals',filetypes=[('Excel / CSV','*.xlsx *.csv')])
        if not path:return
        raw=Path(path).read_bytes()
        if salary:
            advance_mode=messagebox.askyesnocancel('Early salary payments', 'Does this file contain salary paid before its accrual date?\n\nYes: use a dedicated Salary advances asset for early payments, then apply them against payable on the accrual date. The asset ledger is created if needed. All journals still require review and confirmation.\n\nNo: use the standard payable settlement workflow. Cancel: return without uploading.',parent=self) if salary_bulk.has_early_payments(self.state,raw,Path(path).name) else False
            if advance_mode is None:return
            q=self.commit(lambda s:salary_bulk.stage(s,raw,Path(path).name,advance_mode=advance_mode))
        else:q=self.commit(lambda s:bulk.stage(s,raw,Path(path).name,'Journal',sheet='Journals' if Path(path).suffix.lower()=='.xlsx' else ''))
        self.journal_bulk_review(q['id'])
    def journal_bulk_templates(self):
        win=tk.Toplevel(self);win.title('Journal studio — templates and saved batches');win.geometry('1100x650');win.transient(self)
        ttk.Label(win,text='Salary: one monthly accrual plus actual payment rows; no PF/deduction split inferred. General JEs: one balanced debit/credit pair per row; shared journal_id groups approved rows into a compound voucher. Upload/review does not post.',wraplength=1030,padding=10).pack(anchor='w')
        bar=ttk.Frame(win);bar.pack(fill='x',padx=10)
        for salary,label in ((True,'Salary'),(False,'General JE')):
            for ext in ('xlsx','csv'):self.button(bar,label+' '+ext.upper(),lambda salary=salary,ext=ext:self.journal_bulk_template(salary,ext,win))
        batches=[q for q in self.state['queue'] if q.get('kind')=='bulk' and q.get('type')=='Journal'];table=self.table(('ID','File','Type','Rows','Status'),[],parent=win,height=12)
        for q in batches:table.insert('','end',iid=q['id'],values=(q['id'],q['filename'],'Salary' if q.get('salary_journal') else 'General JE',len(q['rows']),q['status']))
        def openbatch():
            if not table.selection():raise ValueError('Select a saved journal batch.')
            self.journal_bulk_review(table.selection()[0])
        self.button(win,'Open selected JE batch',openbatch,True)
    def journal_bulk_template(self,salary,ext,parent=None):
        name='Yathartha-Salary-Journals-Template' if salary else 'Yathartha-General-JE-Template';path=filedialog.asksaveasfilename(parent=parent or self,initialfile=name+'.'+ext,defaultextension='.'+ext,filetypes=[(ext.upper(),'*.'+ext)])
        if not path:return
        if salary:salary_bulk.template(path,self.state)
        else:general_template(path)
    def journal_bulk_review(self,qid):
        q=bulk._queue(self.state,qid);win=tk.Toplevel(self);win.title('Review salary journals' if q.get('salary_journal') else 'Review general journals');win.geometry(f'{int(win.winfo_screenwidth()*.96)}x{int(win.winfo_screenheight()*.92)}');win.transient(self)
        if q.get('salary_journal'):ttk.Label(win,text='Salary text dates are interpreted day-first (DD/MM/YY or DD/MM/YYYY); two-digit years mean 20xx. Review the ISO dates displayed below.',wraplength=1160,padding=5).pack(anchor='w')
        status=ttk.Label(win,text='',wraplength=1160,padding=8);status.pack(fill='x')
        ttk.Label(win,text='Approve valid rows and explicitly reject unwanted/flagged rows, then preview. No journal is posted by upload or row approval. Do not reject a genuine accrual and attempt to pay against it; monthly/date/payable capacity is checked at posting.',wraplength=1160,padding=8).pack(anchor='w')
        controls=ttk.Frame(win);controls.pack(side='bottom',fill='x')
        table=self.table(('Row','Type','Salary month','Date','Unit','Reference','Debit ledger','Credit ledger','INR','Existing voucher','Review','Reason'),[],parent=win,height=12);table.configure(selectmode='extended');table.column('Reason',width=430,minwidth=200);table.column('Row',width=50,stretch=False);table.tag_configure('flagged',background='#FCE8E6',foreground='#8B1A12')
        bar=ttk.Frame(controls);bar.pack(fill='x',padx=8);basis=self.field(bar,'Review / rejection basis','Reviewed original payroll, monthly totals, actual bank transfers and existing books',width=110)
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(controls,text='I reviewed accounts, dates, amounts and duplicates. '+('This salary file has no PF/other deduction splits.' if q.get('salary_journal') else 'I reviewed every general JE pair and complete compound group.'),variable=confirmed).pack(anchor='w',padx=8)
        detail=ttk.Label(controls,text='',wraplength=1150,padding=8);detail.pack(fill='x')
        def refresh():
            q=bulk._queue(self.state,qid);table.delete(*table.get_children());names={a['code']:a['name'] for a in self.state['accounts']}
            for i,r in enumerate(q['rows']):
                table.insert('','end',iid=str(i),tags=('flagged',) if r['review'] in ('INVALID','DUPLICATE') else (),values=(r['source_row'],r.get('event','Journal')+(' (advance)' if r.get('advance') else ''),r.get('month',''),r.get('date',''),r.get('branch',''),r.get('reference',''),r.get('debit_account','')+' '+names.get(r.get('debit_account',''),''),r.get('credit_account','')+' '+names.get(r.get('credit_account',''),''),core.rupees(r['amount']) if type(r.get('amount'))==int else str(r.get('amount','')),r.get('existing',''),r['review'],r['error'] or r['reason']))
            counts={k:sum(r['review']==k for r in q['rows']) for k in ('PENDING','APPROVED','REJECTED','INVALID','DUPLICATE')};status.configure(text=q['filename']+' | '+q['status']+' | '+str(counts)+(' | Salary amounts not fully paid remain payable.' if q.get('salary_journal') else ' | General JE groups require final approval.'))
        def selected(event=None):
            q=bulk._queue(self.state,qid)
            if table.selection():
                r=q['rows'][int(table.selection()[0])];detail.configure(text='Source row '+str(r['source_row'])+' | '+(r['error'] or r['reason'] or 'Awaiting source review'))
        table.bind('<<TreeviewSelect>>',selected)
        def review(approve,allrows=False):
            q=bulk._queue(self.state,qid)
            if approve and not confirmed.get():raise ValueError('Confirm source/account review before approving journals.')
            indices=[i for i,r in enumerate(q['rows']) if (r['review'] in ('PENDING','APPROVED') if approve else r['review'] in ('INVALID','DUPLICATE'))] if allrows else [int(i) for i in table.selection()]
            if not indices:raise ValueError('Select source rows to review.')
            def action(s):
                for i in indices:bulk.review_row(s,qid,i,approve,basis.get().strip())
            self.commit(action);refresh()
        bar=ttk.Frame(controls);bar.pack(fill='x',padx=8)
        self.button(bar,'Approve selected rows',lambda:review(True));self.button(bar,'Approve all valid rows',lambda:review(True,True),True);self.button(bar,'Reject selected rows',lambda:review(False));self.button(bar,'Reject flagged rows',lambda:review(False,True))
        def preview():
            if not confirmed.get():raise ValueError('Confirm source/account review before previewing.')
            before=copy.deepcopy(self.state);candidate=copy.deepcopy(before);result=bulk.approve(candidate,qid);dialog=tk.Toplevel(win);dialog.title('Confirm bulk journal posting');dialog.geometry('1100x680');dialog.transient(win);dialog.grab_set();footer=ttk.Frame(dialog);footer.pack(side='bottom',fill='x');linked=[next(v for v in candidate['vouchers'] if v['id']==r['voucher']) for r in bulk._queue(candidate,qid)['rows'] if r.get('existing') and r.get('voucher')];render(self,dialog,before,candidate,dict(processed_vouchers=result,linked_source_journals=linked))
            def approve():
                if self.state!=before:raise ValueError('Books changed after preview. Review a fresh batch preview.')
                def save(s):s.clear();s.update(copy.deepcopy(candidate))
                self.commit(save);dialog.destroy();refresh();messagebox.showinfo('Bulk journals posted','Reviewed journal batch processed. Match salary bank movements under All book movements. No bank reconciliation was performed by this import.',parent=win)
            self.button(footer,'Confirm post reviewed JEs',approve,True)
        def cancel():
            if not basis.get().strip():raise ValueError('Enter the cancellation reason.')
            self.commit(lambda s:bulk.cancel(s,qid,basis.get().strip()));refresh()
        bar=ttk.Frame(controls);bar.pack(fill='x',padx=8,pady=6);self.button(bar,'Preview reviewed journals',preview,True);self.button(bar,'Cancel unposted batch',cancel);refresh()

def general_template(path):
    if Path(path).suffix.lower()=='.csv':
        import csv
        with open(path,'w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(bulk.FIELDS)
        return
    from openpyxl import Workbook
    from openpyxl.styles import Alignment,Font,PatternFill
    w=Workbook();ws=w.active;ws.title='Journals';ws.append(bulk.FIELDS);ws.freeze_panes='D2'
    for c in ws[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='154C8A')
    for col in 'ABCDEFGH':ws.column_dimensions[col].width=27 if col!='D' else 70
    instructions=w.create_sheet('Instructions')
    for text in ['One positive amount with a debit and credit account per row. Exact active unit code/date, unique source line reference and narration required. No formulas.','journal_id optional: same unit/date/journal_id combines balanced pairs into one compound journal; review all grouped lines consistently. Use unique line references inside a group.','Salary totals/accruals/dated payments should use the Salary Journals template for monthly capacity and existing-voucher linking safeguards.','General Journal imports do not infer salary, tax, gross/net, opening balances or duplicate manual entries. Use dedicated AP/tax/receipt workflows for controlled source allocations.','Upload and row approval do not post. Explicit journal preview/final confirmation posts the approved batch atomically; every other row must be rejected or approved.']:
        instructions.append([text]);instructions.cell(instructions.max_row,1).alignment=Alignment(wrap_text=True);instructions.row_dimensions[instructions.max_row].height=45
    instructions.column_dimensions['A'].width=120;w.save(path);w.close()

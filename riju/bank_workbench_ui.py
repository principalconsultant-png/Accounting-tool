"""Two visible checkbox lists, source uploads and one selected-total reconciliation."""
import copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import bank_workbench as work,reconciliation as bank,core,ledgers,receipt_import

class BankWorkbenchUI:
    def build_bank_workbench(self,parent):
        self.wb_bank_checks=set();self.wb_source_checks=set();self.wb_bank_rows={};self.wb_source_rows={}
        bar=ttk.Frame(parent);bar.pack(fill='x')
        self.button(bar,'Upload bank statement',self.import_bank_statement,True);self.button(bar,'Upload sales report',lambda:self.wb_upload('Sales receipts'));self.button(bar,'Upload invoice payments',lambda:self.wb_upload('Invoice payments'))
        self.button(bar,'Automatically reconcile selected',self.wb_reconcile,True)
        bar=ttk.Frame(parent);bar.pack(fill='x')
        prior=getattr(self,'wb_prior_kind','Sales receipts');self.wb_kind=self.field(bar,'Compare bank against',prior,['Sales receipts','Invoice payments','All book movements'],width=21)
        self.wb_report=self.field(bar,'Source report','All posted sources',['All posted sources'],width=33);self.wb_document_choices={};self.wb_report_combo=bar.winfo_children()[-1].winfo_children()[-1]
        self.button(bar,'Load source / refresh',self.wb_load_sources);self.button(bar,'Clear checks',self.wb_clear)
        self.wb_find=self.field(bar,'Find text / amount','',width=19);self.button(bar,'Find',self.wb_refresh)
        # React to changing modes immediately; choosing a file retains its reviewed source selection.
        self.wb_kind.trace_add('write',lambda *args:self.wb_change_kind())
        self.wb_info=ttk.Label(parent,text='Tick the bank rows on the left and corresponding source rows on the right. Totals must agree; uploads alone never post.',wraplength=1160,padding=5);self.wb_info.pack(anchor='w',fill='x')
        self.wb_detail=ttk.Label(parent,text='',wraplength=1160,padding=5);self.wb_detail.pack(anchor='w',fill='x')
        self.wb_confirm=tk.BooleanVar(value=False);ttk.Checkbutton(parent,text='I reviewed the selected bank/source entries, actual dates, unit, transfer references and any new accounting/fee treatment.',variable=self.wb_confirm).pack(anchor='w')
        self.wb_totals=ttk.Label(parent,text='',padding=7);self.wb_totals.pack(anchor='w')
        parent.bind('<Configure>',lambda e:[label.configure(wraplength=max(260,e.width-24)) for label in (self.wb_info,self.wb_detail,self.wb_totals)])
        panes=ttk.Panedwindow(parent,orient='horizontal',width=850);panes.pack(fill='both',expand=True)
        left=ttk.Frame(panes,width=400,height=260);right=ttk.Frame(panes,width=400,height=260);left.pack_propagate(False);right.pack_propagate(False);panes.add(left,weight=1);panes.add(right,weight=1)
        ttk.Label(left,text='BANK STATEMENT — select actual deposit(s) or withdrawal(s)').pack(anchor='w')
        ttk.Label(right,text='SOURCE TRANSACTIONS — select corresponding receipt(s) or payment(s)').pack(anchor='w')
        self.wb_bank_table=self.table(('Check','Date','Remaining INR','Narration / party','Reference','Status'),[],parent=left,height=8)
        self.wb_source_table=self.table(('Check','Date','Remaining INR','Party / invoice / channel','Unit','Receipt / transfer','Action / status'),[],parent=right,height=8)
        self.wb_check_images=[]
        for checked in (False,True):
            icon=tk.PhotoImage(master=self,width=16,height=16);icon.put('#154C8A',to=(1,1,15,15));icon.put('#FFFFFF',to=(2,2,14,14))
            if checked:
                for x,y in ((4,8),(5,9),(6,10),(7,9),(8,8),(9,7),(10,6),(11,5),(12,4)):icon.put('#154C8A',to=(x,y,x+2,y+2))
            self.wb_check_images.append(icon)
        for table in (self.wb_bank_table,self.wb_source_table):
            table.configure(show='tree headings',displaycolumns=tuple(c for c in table['columns'] if c!='Check'));table.heading('#0',text='Tick');table.column('#0',width=42,minwidth=42,stretch=False)
            table.column('Check',width=55,minwidth=55,stretch=False);table.column('Date',width=100,minwidth=95,stretch=False);table.column('Remaining INR',width=120,minwidth=110,stretch=False)
            table.tag_configure('BLOCKED',background='#FCE8E6',foreground='#8B1A12');table.tag_configure('new',background='#FFF1CB')
        self.wb_bank_table.bind('<ButtonRelease-1>',lambda e:self.wb_click(e,'bank'));self.wb_source_table.bind('<ButtonRelease-1>',lambda e:self.wb_click(e,'source'))
        self.wb_bank_table.bind('<space>',lambda e:self.wb_space('bank'));self.wb_source_table.bind('<space>',lambda e:self.wb_space('source'))
        self.wb_source_table.bind('<<TreeviewSelect>>',self.wb_source_detail)
        bar=ttk.Frame(parent);bar.pack(fill='x');self.wb_fees=self.field(bar,'Reviewed settlement fees INR','0',width=14);self.wb_basis=self.field(bar,'Reconciliation / source review basis','Reviewed selected bank/source dates, references and amounts.',width=58)
        self.wb_fees.trace_add('write',lambda *args:self.wb_update_totals())
        self.wb_allow_dates=tk.BooleanVar(value=False);ttk.Checkbutton(parent,text='Allow a reviewed date/reference timing difference (correct mistaken payment dates in AP first)',variable=self.wb_allow_dates).pack(anchor='w')
        bar=ttk.Frame(parent);bar.pack(fill='x');self.button(bar,'Sales Excel template',lambda:self.wb_template('sales','xlsx'));self.button(bar,'Invoice payment Excel template',lambda:self.wb_template('payments','xlsx'));self.button(bar,'Invoice payment CSV template',lambda:self.wb_template('payments','csv'));self.button(bar,'Sales CSV template',lambda:self.wb_template('sales','csv'))
        self.wb_change_kind()
    def wb_change_kind(self):
        self.wb_prior_kind=self.wb_kind.get();docs=work.documents(self.state,self.wb_kind.get());self.wb_document_choices={'All posted sources':None,**{d['id'][:8]+' | '+d['filename']:d['id'] for d in docs}}
        self.wb_report_combo.configure(values=list(self.wb_document_choices));prior=getattr(self,'wb_prior_doc',None);self.wb_report.set(next((label for label,key in self.wb_document_choices.items() if key==prior),'All posted sources'))
        if hasattr(self,'wb_bank_table'):self.wb_refresh()
    def wb_load_sources(self):
        self.wb_prior_doc=self.wb_document_choices.get(self.wb_report.get());self.wb_refresh()
    def wb_clear(self):
        self.wb_bank_checks.clear();self.wb_source_checks.clear()
        for table in (self.wb_bank_table,self.wb_source_table):
            for item in table.get_children():table.set(item,'Check','☐');table.item(item,image=self.wb_check_images[0])
        self.wb_update_totals()
    def wb_refresh(self):
        if not hasattr(self,'wb_bank_table'):return
        self.wb_bank_checks.clear();self.wb_source_checks.clear();self.wb_bank_table.delete(*self.wb_bank_table.get_children());self.wb_source_table.delete(*self.wb_source_table.get_children());self.wb_bank_rows={};self.wb_source_rows={}
        sid=self._statement_id();s=bank.statement(self.state,sid) if sid else None;scope=s['scope'] if s else 'ALL';rows,_=bank.outstanding(self.state,self._bank_account(),scope)
        term=self.wb_find.get().strip().casefold().replace(',','')
        for b in rows:
            if term and term not in (' '.join([b['date'],b['narration'],b['reference'],core.rupees(b['remaining']),str(abs(b['remaining']))])).casefold().replace(',',''):continue
            if s and b['id'] not in s['row_ids']:continue
            self.wb_bank_rows[b['id']]=b;self.wb_bank_table.insert('','end',iid=b['id'],image=self.wb_check_images[0],values=('☐',b['date'],core.rupees(b['remaining']),b['narration'],b['reference'],'Partial' if b['remaining']!=b['amount'] else 'Unmatched'))
        doc=self.wb_document_choices.get(self.wb_report.get());self.wb_prior_doc=doc
        rows=work.sources(self.state,self._bank_account(),scope,self.wb_kind.get(),doc,s['through'] if s else None)
        for x in rows:
            if term and term not in (' '.join([x['date'],x['reference'],x['label'],x['branch'],core.rupees(x['amount']),str(abs(x['amount']))])).casefold().replace(',',''):continue
            self.wb_source_rows[x['id']]=x;status=x['error'] if x['status']=='BLOCKED' else x.get('status_override','Posted bank movement' if x['kind']=='book' else 'Unsettled receipt')
            self.wb_source_table.insert('','end',iid=x['id'],image=self.wb_check_images[0],tags=('BLOCKED',) if x['status']=='BLOCKED' else ('new',) if x['kind'] in ('new_sale','new_payment') else (),values=('☐',x['date'],core.rupees(x['amount']),x['label'],x['branch'],x['reference'],status))
        self.wb_info.configure(text=str(len(self.wb_bank_rows))+' unmatched bank transaction(s) | '+str(len(self.wb_source_rows))+' visible outstanding source transaction(s). Negative = bank withdrawal/payment; positive = deposit/collection. Amber needs an accounting entry; red is blocked. A full posted bank transfer may cover several invoices.')
        self.wb_detail.configure(text='Select a source row to read its full status/reason. Tick checkboxes to include rows in reconciliation.');self.wb_update_totals()
    def wb_toggle(self,side,item):
        table=self.wb_bank_table if side=='bank' else self.wb_source_table;checks=self.wb_bank_checks if side=='bank' else self.wb_source_checks
        if side=='source' and self.wb_source_rows[item]['status']=='BLOCKED':self.wb_source_table.selection_set(item);self.wb_source_detail();return
        if item in checks:checks.remove(item)
        else:checks.add(item)
        table.set(item,'Check','☑' if item in checks else '☐');table.item(item,image=self.wb_check_images[1 if item in checks else 0]);self.wb_update_totals()
    def wb_click(self,event,side):
        table=self.wb_bank_table if side=='bank' else self.wb_source_table;item=table.identify_row(event.y)
        if item and table.identify_column(event.x)=='#0':self.wb_toggle(side,item)
    def wb_space(self,side):
        table=self.wb_bank_table if side=='bank' else self.wb_source_table
        for item in table.selection():self.wb_toggle(side,item)
        return 'break'
    def wb_source_detail(self,event=None):
        if self.wb_source_table.selection():
            x=self.wb_source_rows[self.wb_source_table.selection()[0]];self.wb_detail.configure(text=x['date']+' | '+x['reference']+' | '+x['label']+' | '+(x['error'] or x.get('status_override','Already recorded: match without reposting' if x['kind']=='book' else 'Creates only the bank/clearing settlement; no duplicate sales revenue.')),foreground='#9C261B' if x['error'] else '#154C8A')
    def wb_update_totals(self):
        if not hasattr(self,'wb_totals'):return
        bt=sum(self.wb_bank_rows[k]['remaining'] for k in self.wb_bank_checks if k in self.wb_bank_rows);st=sum(self.wb_source_rows[k]['amount'] for k in self.wb_source_checks if k in self.wb_source_rows)
        try:fees=bank.amount(self.wb_fees.get()) if hasattr(self,'wb_fees') else 0;difference=st-fees-bt;label=core.rupees(difference)
        except ValueError:fees=0;label='Enter valid fees'
        self.wb_totals.configure(text='BANK selected '+str(len(self.wb_bank_checks))+' = '+core.rupees(bt)+' | SOURCE selected '+str(len(self.wb_source_checks))+' = '+core.rupees(st)+' | Fees '+core.rupees(fees)+' | DIFFERENCE '+label)
    def wb_upload(self,kind):
        path=filedialog.askopenfilename(parent=self,title='Upload '+kind,filetypes=[('Source CSV / Excel','*.csv *.xlsx')])
        if not path:return
        doc=self.commit(lambda s:work.upload(s,Path(path).read_bytes(),Path(path).name,kind));self.wb_prior_doc=doc['id'];self.wb_kind.set(kind);self.wb_change_kind();messagebox.showinfo('Source report loaded',str(len(doc['rows']))+' source rows loaded for review. Upload created no sales/payment journal and no bank match. Select corresponding bank/source rows and review reconciliation.',parent=self)
    def wb_template(self,kind,ext):
        filename='Yathartha-Invoice-Payments-Template' if kind=='payments' else 'RijuBooks-Sales-Receipts-Template';path=filedialog.asksaveasfilename(parent=self,initialfile=filename+'.'+ext,defaultextension='.'+ext,filetypes=[(ext.upper(),'*.'+ext)])
        if path:(work.payment_template if kind=='payments' else receipt_import.template)(path)
    def wb_reconcile(self):
        if not self.wb_confirm.get():raise ValueError('Confirm bank/source/accounting review before reconciliation.')
        args=(self._bank_account(),self._statement_id(),self.wb_kind.get(),self.wb_document_choices.get(self.wb_report.get()),list(self.wb_bank_checks),list(self.wb_source_checks),self.wb_basis.get().strip(),bank.amount(self.wb_fees.get()),self.wb_allow_dates.get())
        before=copy.deepcopy(self.state);candidate=copy.deepcopy(before);result=work.reconcile(candidate,*args)
        win=tk.Toplevel(self);win.title('Confirm selected bank reconciliation');win.geometry('1080x680');win.transient(self)
        ttk.Label(win,text='Bank '+result['bank_total_INR']+' | Source '+result['source_total_INR']+' | Fees '+result['reviewed_fees_INR']+' | Difference 0.00\n'+str(result['bank_transactions'])+' bank row(s), '+str(result['source_transactions'])+' source row(s), '+str(result['new_journals'])+' new journal(s). Confirm only after reviewing the entries below.',wraplength=1020,padding=10).pack(anchor='w')
        names={a['code']:a['name'] for a in candidate['accounts']};vouchers=candidate['vouchers'][len(before['vouchers']):]
        self.table(('Date','Voucher','Unit','Account','Ledger name','Debit INR','Credit INR'),[(v['date'],v['id'],l['branch'],l['account'],names.get(l['account'],''),core.rupees(l['debit']),core.rupees(l['credit'])) for v in vouchers for l in v['lines']],parent=win,height=12)
        if not vouchers:ttk.Label(win,text='Existing entries only. This records match links and posts no journal.').pack(anchor='w')
        def approve():
            if self.state!=before:raise ValueError('Books changed after preview. Refresh and review the reconciliation again.')
            def save(s):s.clear();s.update(copy.deepcopy(candidate))
            self.commit(save);win.destroy();self.refresh_bank_tables();messagebox.showinfo('Reconciliation completed',str(result['bank_transactions'])+' selected bank transaction(s) fully reconciled. Difference 0.00.',parent=self)
        self.button(win,'Confirm reconcile',approve,True)

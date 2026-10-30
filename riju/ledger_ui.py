"""Ledger A/c navigation and printable customer handover books."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import webbrowser
from . import ledgers


class LedgerUI:
    def ledger_accounts(self):
        self.note('Open any ledger account below. Select several accounts or Select all shown to print/export a handover pack. Only posted entries appear; initial balances and year-end closing entries reconcile to the trial balance.')
        start,end=self.dates()
        if getattr(self,'ledger_filter_year',None)==self.year.get():start,end=self.ledger_from.get(),self.ledger_to.get()
        search=self.ledger_search.get() if hasattr(self,'ledger_search') else ''
        category=self.ledger_category.get() if hasattr(self,'ledger_category') else 'All ledgers'
        self.ledger_restore_selection=getattr(self,'ledger_last_selection',[])
        self.ledger_filter_year=self.year.get()
        top=self.bar()
        self.ledger_from=self.field(top,'From',start,width=13);self.ledger_to=self.field(top,'Through',end,width=13)
        ttk.Label(top,text='Scope: '+('All operating units — entity total' if self.unit()=='ALL' else self.branches[self.unit()]),wraplength=450).pack(side='left',padx=15)
        controls=self.bar();self.ledger_search=self.field(controls,'Find ledger (name or code)',search,width=26)
        self.ledger_category=self.field(controls,'Show',category,['All ledgers','Assets','Liabilities','Equity','Revenue','Expenses','Cash book','Bank books'],width=18)
        self.button(controls,'Find / filter',self.filter_ledgers)
        self.button(controls,'Refresh dates',self.render_ledger,True)
        self.button(controls,'Select all shown',self.select_all_ledgers)
        pane=ttk.Frame(self.content);pane.pack(fill='both',expand=True,pady=8)
        left=ttk.Frame(pane);left.pack(side='left',fill='y',padx=(0,12))
        ttk.Label(left,text='Accounts (Ctrl/Shift selects several)').pack(anchor='w')
        listframe=ttk.Frame(left);listframe.pack(fill='both',expand=True)
        self.ledger_list=tk.Listbox(listframe,selectmode='extended',exportselection=False,width=28,height=16,background='#FFFEFC',selectbackground='#E3EEDF',foreground='#293B55')
        scroll=ttk.Scrollbar(listframe,orient='vertical',command=self.ledger_list.yview)
        self.ledger_list.configure(yscrollcommand=scroll.set);self.ledger_list.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        right=ttk.Frame(pane,width=650,height=500);right.pack_propagate(False);right.pack(side='left',fill='both',expand=True)
        self.ledger_title=ttk.Label(right,text='',font=('Segoe UI',14,'bold'));self.ledger_title.pack(anchor='w',pady=4)
        self.ledger_summary=ttk.Label(right,text='',wraplength=700);self.ledger_summary.pack(anchor='w',pady=6)
        self.ledger_table=self.table(('Date','Voucher','Narration','Debit (INR)','Credit (INR)','Running balance','Reference','Branch','Department'),[],parent=right,height=12)
        for col,width in [('Date',90),('Voucher',140),('Narration',180),('Debit (INR)',95),('Credit (INR)',95),('Running balance',125),('Reference',120),('Branch',140),('Department',120)]:self.ledger_table.column(col,width=width,stretch=False)
        self.ledger_table.bind('<Double-1>',lambda event:self.guarded(self.ledger_voucher))
        self.ledger_list.bind('<<ListboxSelect>>',lambda event:self.guarded(self.render_ledger))
        self.ledger_search.trace_add('write',lambda *args:self.guarded(self.filter_ledgers))
        self.ledger_category.trace_add('write',lambda *args:self.guarded(self.filter_ledgers))
        row=self.bar();row.pack(before=pane,fill='x',pady=5);self.button(row,'View selected entry voucher',self.ledger_voucher)
        self.button(row,'Print / preview selected',lambda:self.export_ledgers('html'),True)
        row=self.bar();row.pack(before=pane,fill='x',pady=5);self.button(row,'Save PDF',lambda:self.export_ledgers('pdf'),True)
        self.button(row,'Save Excel',lambda:self.export_ledgers('xlsx'))
        self.button(row,'Save CSV',lambda:self.export_ledgers('csv'))
        ttk.Label(self.content,text='Exports use the selected accounts, branch and date range. Each ledger starts a separate printable section. Files contain financial records; choose the handover folder when saving.',wraplength=950).pack(anchor='w',pady=8)
        self.ledger_visible_codes=[];self.ledger_row_vouchers={}
        self.filter_ledgers()

    def selected_ledger_codes(self):
        return [self.ledger_visible_codes[i] for i in self.ledger_list.curselection()]

    def filter_ledgers(self):
        if not hasattr(self,'ledger_list') or not self.ledger_list.winfo_exists():return
        prior=self.selected_ledger_codes() if hasattr(self,'ledger_visible_codes') else []
        if not prior:prior=self.ledger_restore_selection
        self.ledger_restore_selection=[]
        query=self.ledger_search.get().strip().casefold();category=self.ledger_category.get()
        types={'Assets':'Asset','Liabilities':'Liability','Equity':'Equity','Revenue':'Revenue','Expenses':'Expense'}
        accounts=[]
        for account in self.state['accounts']:
            if query and query not in (account['code']+' '+account['name']).casefold():continue
            if category in types and account['kind']!=types[category]:continue
            isbank=self.state['account_details'].get(account['code'],{}).get('group')=='Cash and bank'
            if category=='Cash book' and account['code']!='1000':continue
            if category=='Bank books' and (not isbank or account['code']=='1000'):continue
            accounts.append(account)
        self.ledger_list.delete(0,'end');self.ledger_visible_codes=[a['code'] for a in accounts]
        for i,a in enumerate(accounts):
            suffix=' (inactive)' if not self.state['account_details'].get(a['code'],{}).get('active',True) else ''
            self.ledger_list.insert('end',a['code']+' · '+a['name']+suffix)
            if a['code'] in prior:self.ledger_list.selection_set(i)
        if accounts and not self.ledger_list.curselection():self.ledger_list.selection_set(0)
        self.render_ledger()

    def select_all_ledgers(self):
        self.ledger_list.selection_set(0,'end');self.render_ledger()

    def selected_ledger_pack(self):
        return ledgers.ledger_pack(self.state,self.selected_ledger_codes(),self.ledger_from.get().strip(),self.ledger_to.get().strip(),self.unit())

    def render_ledger(self):
        self.ledger_table.delete(*self.ledger_table.get_children());self.ledger_row_vouchers={}
        if not self.selected_ledger_codes():
            self.ledger_title.configure(text='No ledger accounts selected');self.ledger_summary.configure(text='Change the search/filter or select an account.');return
        self.ledger_last_selection=self.selected_ledger_codes()
        pack=self.selected_ledger_pack();book=pack['books'][0]
        self.ledger_title.configure(text=book['code']+' · '+book['name'])
        self.ledger_summary.configure(text=f"Opening: INR {ledgers.balance(book['opening'])}   |   Debits: {ledgers.number(book['debit'],True)}   |   Credits: {ledgers.number(book['credit'],True)}\nClosing: INR {ledgers.balance(book['closing'])}   |   {len(book['rows'])} lines   |   {len(pack['books'])} account(s) selected for export/print")
        def insert(values,voucher=None):
            item=self.ledger_table.insert('','end',values=values)
            if voucher:self.ledger_row_vouchers[item]=voucher
        insert((pack['start'],'','Opening balance','','',ledgers.balance(book['opening']),'','',''))
        for r in book['rows']:
            insert((r['date'],r['voucher'],r['narration'],ledgers.number(r['debit'],True),ledgers.number(r['credit'],True),ledgers.balance(r['balance']),r['reference'],r['branch'],r['department']),r['voucher'])
        insert((pack['end'],'','Period totals',ledgers.number(book['debit'],True),ledgers.number(book['credit'],True),'','','',''))
        insert((pack['end'],'','Closing balance','','',ledgers.balance(book['closing']),'','',''))

    def ledger_voucher(self):
        selected=self.ledger_table.selection()
        voucher_id=self.ledger_row_vouchers.get(selected[0]) if selected else None
        if not voucher_id:raise ValueError('Select a transaction row to open its posted voucher.')
        v=next(v for v in self.state['vouchers'] if v['id']==voucher_id)
        text=v['date']+' | '+v['narration']+'\nReference: '+v.get('metadata',{}).get('reference','')+'\n\n'
        text+='\n'.join(self.branches[l['branch']]+' | '+l['account']+' '+self.account_name(l['account'])+' | Dr '+ledgers.number(l['debit'],True)+' | Cr '+ledgers.number(l['credit'],True) for l in v['lines'])
        messagebox.showinfo(v['id'],text,parent=self)

    def export_ledgers(self,kind):
        # Build from current controls now; never export a stale on-screen snapshot.
        pack=self.selected_ledger_pack()
        labels={'pdf':'PDF document','xlsx':'Excel workbook','csv':'CSV file','html':'Offline print preview'}
        path=filedialog.asksaveasfilename(title=labels[kind],initialfile='Riju-Ledgers-'+pack['start']+'-to-'+pack['end']+'.'+kind,defaultextension='.'+kind,filetypes=[(labels[kind],'*.'+kind)],parent=self)
        if not path:return
        {'pdf':ledgers.export_pdf,'xlsx':ledgers.export_xlsx,'csv':ledgers.export_csv,'html':ledgers.export_html}[kind](pack,path)
        if kind=='html':
            opened=webbrowser.open(Path(path).resolve().as_uri())
            if not opened:messagebox.showinfo('Preview saved','Open '+path+' in your browser, then choose Print / Save as PDF.',parent=self)
        else:messagebox.showinfo('Ledger books saved',f"{len(pack['books'])} ledger account(s) saved to:\n{path}",parent=self)

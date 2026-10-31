"""Complete INR bank-statement review and reconciliation desktop workflow."""
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
import webbrowser
from . import reconciliation as r,brs_exports,ledgers,foundation,activity,bank_templates as bt


class BankUI:
    def banking(self):
        self.note('Reconcile the selected bank statement, including withdrawals and deposits. Shared-account statements cover all branches independently of the global report selector. Every match/adjustment needs review; closing a statement locks that bank period until explicitly reopened.')
        accounts=r.bank_accounts(self.state)
        choices=[a['code']+' · '+a['name'] for a in accounts]
        prior=self.brs_bank.get().split(' · ')[0] if hasattr(self,'brs_bank') else '1010'
        top=self.bar();self.brs_bank=self.field(top,'INR bank ledger',next((c for c in choices if c.startswith(prior+' · ')),choices[0]),choices,width=30)
        self.brs_scope=self.field(top,'New statement scope','All operating units',['All operating units']+list(self.branches.values()),width=24)
        self.button(top,'Load bank',lambda:self.show('Bank reconciliation'),True)
        self.button(top,'Import statement',self.import_bank_statement)
        self.button(top,'CSV template',self.bank_template)
        account=self.brs_bank.get().split(' · ')[0]
        statements=[s for s in self.state.get('bank_statements',[]) if s['bank_account']==account]
        names={'All imported transactions':None,**{s['id'][:8]+' · '+s['start']+' to '+s['through']+' · '+s['filename']+' ['+s['status']+']':s['id'] for s in reversed(statements)}}
        row=self.bar();selected=getattr(self,'brs_selected_statement',None)
        self.brs_statement_names=names;self.brs_statement=self.field(row,'Statement / reporting period',next((k for k,v in names.items() if v==selected),'All imported transactions'),list(names),width=69)
        self.button(row,'Load statement',self.reload_bank_statement)
        self.brs_only_open=tk.BooleanVar(value=True);ttk.Checkbutton(row,text='Show unmatched / partial only',variable=self.brs_only_open,command=self.refresh_bank_tables).pack(side='left',padx=8)
        tabs=ttk.Notebook(self.content);tabs.pack(fill='both',expand=True);self.brs_tabs=tabs
        self.brs_frames={}
        for key,label in [('bank','Bank transactions'),('books','Book movements'),('matches','Match history'),('report','BRS / handover'),('calendar','Business calendar')]:
            f=ttk.Frame(tabs,padding=10);tabs.add(f,text=label);self.brs_frames[key]=f
        self.brs_bank_table=self.table(('ID','Date','Value date','Narration','Reference','Bank debit','Bank credit','Unmatched INR','Status'),[],parent=self.brs_frames['bank'],height=9);self.brs_bank_table.configure(selectmode='extended')
        actions=ttk.Frame(self.brs_frames['bank']);actions.pack(fill='x',pady=8)
        self.button(actions,'Suggest book matches',self.bank_suggestions,True);self.button(actions,'Match selected bank + book rows',self.match_bank_books)
        actions=ttk.Frame(self.brs_frames['bank']);actions.pack(fill='x',pady=5)
        self.button(actions,'Review UPI / card / cash settlement',self.bank_settlement)
        self.button(actions,'Create reviewed adjustment',self.bank_adjustment)
        self.button(actions,'Classify reconciling item',self.bank_exception)
        self.button(actions,'Remove item classification',self.remove_bank_exception)
        ttk.Label(self.brs_frames['books'],text='Select one or several unmatched bank-ledger movements, then select bank rows on the first tab and choose Match. Partial amounts are supported. Later-dated books remain visible for reviewed cutoff matching.',wraplength=950).pack(anchor='w',pady=7)
        self.brs_book_table=self.table(('Key','Date','Voucher','Reference','Branch','Narration','Unmatched INR'),[],parent=self.brs_frames['books'],height=12);self.brs_book_table.configure(selectmode='extended')
        self.brs_match_table=self.table(('ID','Kind','Status','Bank rows','Book vouchers','Created India','Undo date'),[],parent=self.brs_frames['matches'],height=10)
        self.button(self.brs_frames['matches'],'Undo selected match',self.undo_bank_match)
        actions=ttk.Frame(self.brs_frames['report']);actions.pack(fill='x',pady=5)
        self.button(actions,'Set verified statement balances',self.set_bank_balances)
        self.button(actions,'Review & mark reconciled',self.finalize_bank_statement,True)
        self.button(actions,'Reopen with reason',self.reopen_bank_statement)
        self.button(actions,'Void unused statement import',self.void_bank_statement)
        actions=ttk.Frame(self.brs_frames['report']);actions.pack(fill='x',pady=5)
        self.button(actions,'Print / preview BRS',lambda:self.export_brs('html'),True);self.button(actions,'Save BRS PDF',lambda:self.export_brs('pdf'));self.button(actions,'Save BRS CSV',lambda:self.export_brs('csv'))
        self.brs_report_label=ttk.Label(self.brs_frames['report'],text='',wraplength=950);self.brs_report_label.pack(anchor='w',pady=8)
        self.brs_report_table=self.table(('Reconciliation line','INR'),[],parent=self.brs_frames['report'],height=8)
        self.brs_report_table.column('Reconciliation line',width=650)
        self._calendar_tab(self.brs_frames['calendar'])
        self.refresh_bank_tables()

    def reload_bank_statement(self):
        self.brs_selected_statement=self.brs_statement_names[self.brs_statement.get()];self.refresh_bank_tables()

    def _bank_account(self):return self.brs_bank.get().split(' · ')[0]
    def _statement_id(self):return self.brs_statement_names[self.brs_statement.get()]

    def refresh_bank_tables(self):
        account=self._bank_account();sid=self._statement_id();self.brs_selected_statement=sid
        statement=r.statement(self.state,sid) if sid else None
        scope=statement['scope'] if statement else 'ALL'
        used,_=r.used_allocations(self.state);self.brs_bank_data={}
        self.brs_bank_table.delete(*self.brs_bank_table.get_children())
        for b in r.bank_rows(self.state,account):
            if statement and b['id'] not in statement['row_ids']:continue
            remain=b['amount']-used[b['id']]
            if self.brs_only_open.get() and not remain:continue
            status='MATCHED' if not remain else 'PARTIAL' if remain!=b['amount'] else 'UNMATCHED'
            if b['id'] in self.state.get('bank_exceptions',{}):status+=' / CLASSIFIED'
            item=self.brs_bank_table.insert('','end',values=(b['id'][:12],b['date'],b['value_date'],b['narration'],b['reference'],ledgers.number(b['debit'],True),ledgers.number(b['credit'],True),ledgers.number(remain,True),status));self.brs_bank_data[item]=b
        self.brs_book_table.delete(*self.brs_book_table.get_children());self.brs_book_data={}
        _,books=r.outstanding(self.state,account,scope)
        for b in books:
            item=self.brs_book_table.insert('','end',values=(b['key'],b['date'],b['voucher'],b['reference'],self.branches[b['branch']],b['narration'],ledgers.number(b['remaining'],True)));self.brs_book_data[item]=b
        self.brs_match_table.delete(*self.brs_match_table.get_children());self.brs_match_data={}
        for m in self.state['matches']:
            bank_ids={e['bank_id'] for e in r._edges(self.state,m)}
            if not any(b['id'] in bank_ids for b in r.bank_rows(self.state,account)):continue
            item=self.brs_match_table.insert('','end',values=(m.get('id',m.get('bank_id')),m.get('kind','legacy settlement'),m.get('status','ACTIVE'),len(bank_ids),', '.join(m.get('vouchers',[])),datetime.fromisoformat(m['created_at']).astimezone(activity.INDIA).isoformat(timespec='seconds') if m.get('created_at') else 'Legacy record',m.get('undo_date','')));self.brs_match_data[item]=m
        self.brs_report_table.delete(*self.brs_report_table.get_children())
        if statement:
            report=r.brs(self.state,sid)
            label=('VOID — import cancelled' if report['status']=='VOID' else 'RECONCILED' if report['status']=='RECONCILED' else 'READY FOR REVIEW' if report['ready'] else 'DRAFT / INCOMPLETE')+' | '+report['scope_name']+'\n'+statement['coverage']+' | '+str(report['unclassified_count'])+' unclassified bank item(s). Positive balance = funds; negative = overdraft.'
            self.brs_report_label.configure(text=label)
            for key,text in brs_exports.SUMMARY:self.brs_report_table.insert('','end',values=(text,'Not supplied' if report[key] is None else ledgers.number(report[key],True)))
        else:self.brs_report_label.configure(text='Select an imported statement with its bank-verified opening and closing balances to prepare a formal BRS. Legacy deposits remain available for matching on the first tabs.')

    def _selected_banks(self):return [self.brs_bank_data[i]['id'] for i in self.brs_bank_table.selection()]
    def _one_bank(self):
        ids=self._selected_banks()
        if len(ids)!=1:raise ValueError('Select one bank transaction for this action.')
        return ids[0]

    def bank_template(self):
        path=filedialog.asksaveasfilename(initialfile='bank-statement-template.csv',defaultextension='.csv',parent=self)
        if path:Path(path).write_text('date,value_date,narration,reference,debit,credit,balance\n2026-04-02,2026-04-02,Patient deposit,UTR-TEST,0,1000,1000\n2026-04-03,2026-04-03,Bank charges,FEE-TEST,50,0,950\n',encoding='utf-8')

    def import_bank_statement(self):
        path=filedialog.askopenfilename(filetypes=[('Bank statements','*.csv *.xlsx *.ofx'),('CSV','*.csv'),('Excel','*.xlsx'),('OFX','*.ofx')],parent=self)
        if not path:return
        raw=Path(path).read_bytes();account=self._bank_account();scope='ALL' if self.brs_scope.get()=='All operating units' else self.branch_names[self.brs_scope.get()]
        dialog=tk.Toplevel(self);dialog.title('Review bank statement import');dialog.geometry(f'{min(1020,self.winfo_screenwidth()-80)}x{min(760,self.winfo_screenheight()-100)}');dialog.transient(self);dialog.grab_set()
        canvas=tk.Canvas(dialog,highlightthickness=0);vertical=ttk.Scrollbar(dialog,orient='vertical',command=canvas.yview);horizontal=ttk.Scrollbar(dialog,orient='horizontal',command=canvas.xview)
        canvas.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        vertical.pack(side='right',fill='y');horizontal.pack(side='bottom',fill='x');canvas.pack(fill='both',expand=True)
        f=ttk.Frame(canvas,padding=12);window=canvas.create_window((0,0),window=f,anchor='nw')
        f.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=max(e.width,f.winfo_reqwidth())))
        dialog.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-1 if e.delta>0 else 1,'units') if e.widget.winfo_class() not in ('Text','Treeview','TCombobox') else None)
        ttk.Label(f,text=Path(path).name+' | '+account+' | '+('All branches / shared bank' if scope=='ALL' else self.branches[scope]),wraplength=950).pack(anchor='w')
        row=ttk.Frame(f);row.pack(fill='x');start,end=self.dates()
        start_v=self.field(row,'Statement from',start,width=13);end_v=self.field(row,'Through',end,width=13);opening=self.field(row,'Bank opening INR (optional)','',width=20);closing=self.field(row,'Bank closing INR (optional)','',width=20)
        row=ttk.Frame(f);row.pack(fill='x')
        fmt=self.field(row,'Date format','ISO',['ISO','DD/MM/YYYY','DD-MM-YYYY'],width=17);order=self.field(row,'Row order','Oldest first',['Oldest first','Newest first'],width=17)
        sheet=self.field(row,'XLSX sheet (if multiple)','',width=24);header=self.field(row,'Header row','1',width=10)
        ttk.Label(f,text='Use exact statement dates. Blank balances permit transaction review but cannot be marked fully reconciled. OFX uses its supplied closing balance. Debit = withdrawal; credit = deposit; signed Amount is positive for money received.',wraplength=950).pack(anchor='w',pady=9)
        mapping={};widgets={}
        for i,key in enumerate(('date','value_date','narration','reference','debit','credit','amount','balance','fitid')):
            if i%3==0:row=ttk.Frame(f);row.pack(fill='x')
            mapping[key]=self.field(row,key.replace('_',' ').title()+' column','(Auto)',['(Auto)','(Not provided)'],width=27)
            widgets[key]=row.winfo_children()[-1].winfo_children()[-1]
        def columns():
            records,head=r._raw_rows(raw,Path(path).suffix.lower().lstrip('.'),sheet.get().strip() or None,int(header.get()))
            names=list(records[0]) if records else head.get('columns',[])
            for combo in widgets.values():combo.configure(values=['(Auto)','(Not provided)']+[str(v) for v in names if v])
        self.button(f,'Load column names for mapping',columns)
        kind=Path(path).suffix.lower().lstrip('.')
        layout_row=ttk.Frame(f);layout_row.pack(fill='x',pady=5)
        saved=self.field(layout_row,'Saved layout','(Manual mapping)',['(Manual mapping)'],width=34)
        name=self.field(layout_row,'Layout name','',width=28)
        selected={'id':None,'options':None};choices={}
        def parser_options():
            return dict(date_format=fmt.get(),order=order.get(),sheet=sheet.get().strip() or None,header_row=int(header.get()),mapping={k:'' if v.get()=='(Not provided)' else v.get() for k,v in mapping.items() if v.get()!='(Auto)'})
        def refresh_layouts():
            choices.clear()
            for t in bt.available(self.state,account,scope,kind):choices[t['name']+' · v'+str(t['revision'])+' · '+t['id'][:8]]=t
            combo=layout_row.winfo_children()[0].winfo_children()[-1];combo.configure(values=['(Manual mapping)',*choices])
        def manual():
            selected.update(id=None,options=None);saved.set('(Manual mapping)')
        def apply_layout():
            if saved.get() not in choices:raise ValueError('Select a saved bank layout.')
            t=choices[saved.get()];opts,_=bt.resolve(self.state,t['id'],raw,Path(path).name,account,scope)
            fmt.set(opts['date_format']);order.set(opts['order']);sheet.set(opts['sheet'] or '');header.set(str(opts['header_row']))
            for key,var in mapping.items():var.set(opts['mapping'][key] or '(Not provided)')
            name.set(t['name']);selected.update(id=t['id'],options=opts)
        def save_layout():
            t=self.commit(lambda state:bt.save(state,raw,Path(path).name,account,scope,name.get(),**parser_options()))
            refresh_layouts();saved.set(next(label for label,item in choices.items() if item['id']==t['id']));apply_layout()
        def disable_layout():
            if saved.get() not in choices:raise ValueError('Select a saved bank layout.')
            reason=simpledialog.askstring('Disable saved layout','Reason for disabling this layout:',parent=dialog)
            if reason is None:return
            self.commit(lambda state:bt.disable(state,choices[saved.get()]['id'],reason));manual();refresh_layouts()
        actions=ttk.Frame(f);actions.pack(fill='x')
        self.button(actions,'Apply saved layout',apply_layout);self.button(actions,'Use manual mapping',manual)
        self.button(actions,'Validate & save layout',save_layout);self.button(actions,'Disable layout',disable_layout)
        ttk.Label(f,text='Layouts are saved per bank ledger, scope and file type. Changed headings require a reviewed revision. Dates and balances are never reused. OFX has fixed fields and does not need a layout.',wraplength=950).pack(anchor='w',pady=5)
        refresh_layouts()
        def review():
            args=dict(filename=Path(path).name,account=account,scope=scope,start=start_v.get(),end=end_v.get(),opening=opening.get(),closing=closing.get())
            opts=parser_options()
            if selected['id']:
                if opts!=selected['options']:raise ValueError('Parser fields changed after applying the layout. Use manual mapping or save a reviewed layout revision.')
                args['template_id']=selected['id']
            else:args.update(opts)
            import copy
            temp=copy.deepcopy(self.state);s=r.import_statement(temp,raw,**args)
            preview=tk.Toplevel(dialog);preview.title('Verify statement before importing');preview.geometry('1100x620');preview.transient(dialog);preview.grab_set()
            ttk.Label(preview,text=s['coverage']+'\n'+str(len(s['row_ids']))+' rows. Verify column mapping, amounts, scope and exact statement dates.',padding=12,wraplength=1000).pack(anchor='w')
            rows={b['id']:b for b in r.bank_rows(temp,account)}
            self.table(('Date','Narration','Reference','Debit','Credit','Running balance'),[(rows[k]['date'],rows[k]['narration'],rows[k]['reference'],ledgers.number(rows[k]['debit'],True),ledgers.number(rows[k]['credit'],True),'' if rows[k]['balance'] is None else ledgers.number(rows[k]['balance'],True)) for k in s['row_ids']],parent=preview,height=12)
            def approve():
                imported=self.commit(lambda state:r.import_statement(state,raw,**args));self.brs_selected_statement=imported['id'];preview.destroy();dialog.destroy();self.show('Bank reconciliation')
            self.button(preview,'Approve statement import',approve,True)
        self.button(f,'Validate & preview rows',review,True)

    def match_bank_books(self):
        bank_ids=self._selected_banks();keys=[self.brs_book_data[i]['key'] for i in self.brs_book_table.selection()]
        if not bank_ids or not keys:raise ValueError('Select bank rows on the first tab and book rows on the second tab.')
        partial=simpledialog.askstring('Reviewed match','Partial INR amount (leave blank to match full remaining totals):',parent=self)
        if partial is None:return
        n=r.amount(partial) if partial.strip() else None
        if messagebox.askyesno('Approve bank/book match','Confirm '+str(len(bank_ids))+' bank row(s) against '+str(len(keys))+' book movement(s)?\nReview amount, date/value date, reference and branch before approving.',parent=self):
            self.commit(lambda s:r.match_existing(s,bank_ids,keys,n));self.refresh_bank_tables()

    def bank_suggestions(self):
        bank_id=self._one_bank();suggestions=r.suggestions(self.state,bank_id)
        if not suggestions:raise ValueError('No amount/date/reference suggestions found. Review book movements or create an adjustment manually.')
        dialog=tk.Toplevel(self);dialog.title('Review suggested book matches');dialog.geometry('1000x470');dialog.transient(self)
        books={b['key']:b for b in r.book_items(self.state,self._bank_account())}
        table=self.table(('Key','Date','Voucher','Reference','Narration','Reason'),[(x['book_key'],books[x['book_key']]['date'],books[x['book_key']]['voucher'],books[x['book_key']]['reference'],books[x['book_key']]['narration'],x['reason']) for x in suggestions],parent=dialog,height=10)
        def approve():
            if not table.selection():raise ValueError('Select a suggestion.')
            key=suggestions[table.index(table.selection()[0])]['book_key']
            if messagebox.askyesno('Approve suggested match','Have you reviewed the amount, dates, reference and narration?',parent=dialog):
                self.commit(lambda s:r.match_existing(s,[bank_id],[key]));dialog.destroy();self.refresh_bank_tables()
        self.button(dialog,'Review & approve selected match',approve,True)

    def bank_adjustment(self):
        bank_id=self._one_bank();bank=next(b for b in r.bank_rows(self.state,self._bank_account()) if b['id']==bank_id)
        dialog=tk.Toplevel(self);dialog.title('Review bank adjustment');dialog.geometry('950x280');dialog.transient(self);dialog.grab_set()
        f=ttk.Frame(dialog,padding=15);f.pack(fill='both',expand=True)
        row=ttk.Frame(f);row.pack(fill='x')
        branch=self.field(row,'Posting branch',self.branches[bank['branch']] if bank['branch']!='ALL' else self.branches[next(iter(self.branches))],list(self.branches.values()),width=24)
        options=[a['code']+' · '+a['name'] for a in self.state['accounts'] if a['code']!=self._bank_account() and a['code'] not in self.state.get('foreign_accounts',{}) and self.state['account_details'].get(a['code'],{}).get('active',True)]
        contra=self.field(row,'Contra ledger',next((x for x in options if x.startswith('4560')),options[0]),options,width=40)
        row=ttk.Frame(f);row.pack(fill='x');narration=self.field(row,'Narration','Bank adjustment: '+bank['narration'],width=80)
        ttk.Label(f,text='Creates a balanced receipt/payment against the selected ledger and matches only the unallocated amount. Tax is not inferred; use a reviewed compound journal for tax-bearing entries.',wraplength=880).pack(anchor='w',pady=12)
        def approve():
            if messagebox.askyesno('Approve adjustment','Post the reviewed bank adjustment to '+branch.get()+' against '+contra.get()+'?',parent=dialog):
                self.commit(lambda s:r.adjust(s,bank_id,self.branch_names[branch.get()],contra.get().split(' · ')[0],narration.get()));dialog.destroy();self.refresh_bank_tables()
        self.button(f,'Approve & post adjustment',approve,True)

    def bank_settlement(self):
        bank_id=self._one_bank();bank=next(b for b in r.bank_rows(self.state,self._bank_account()) if b['id']==bank_id)
        dialog=tk.Toplevel(self);dialog.title('Review gross receipts to net bank settlement');dialog.geometry('1120x690');dialog.transient(self);dialog.grab_set()
        f=ttk.Frame(dialog,padding=12);f.pack(fill='both',expand=True)
        row=ttk.Frame(f);row.pack(fill='x')
        channel=self.field(row,'Receipt channel','UPI',['UPI','Card','Cash'],width=12)
        fees=self.field(row,'Total fee incl. GST INR','0',width=20);tax=self.field(row,'Eligible fee GST INR','0',width=20);taxmode=self.field(row,'Fee GST treatment','None',['None','Intra-state','Inter-state'],width=18)
        row=ttk.Frame(f);row.pack(fill='x');partial=self.field(row,'Partial gross INR (optional)','',width=23)
        ttk.Label(f,text='Select gross receipt lines below. Gross minus total fees must equal the unmatched bank deposit. Tax fields require invoice-backed eligibility; none is assumed. Manual selections outside NBD tolerance are possible only after your review.',wraplength=1000).pack(anchor='w',pady=8)
        table=self.table(('Key','Date','Branch','Gross remaining INR','Narration','Expected NBD'),[],parent=f,height=10);table.configure(selectmode='extended');items=[]
        def refresh():
            nonlocal items
            account={'UPI':'1110','Card':'1120','Cash':'1000'}[channel.get()];items=r.clearing_items(self.state,account,bank['branch'],bank['date'])
            table.delete(*table.get_children())
            for b in items:table.insert('','end',values=(b['key'],b['date'],self.branches[b['branch']],ledgers.number(b['remaining'],True),b['narration'],'Manual cash deposit' if account=='1000' else r.next_business_day(self.state,b['date'])))
        def suggest():
            account={'UPI':'1110','Card':'1120','Cash':'1000'}[channel.get()];proposals=r.settlement_suggestions(self.state,bank_id,account)
            if not proposals:raise ValueError('No contiguous batch within the configured business calendar/tolerance. Select the actual receipt lines manually.')
            proposed=proposals[0];table.selection_remove(*table.selection())
            for item,b in zip(table.get_children(),items):
                if b['key'] in proposed['keys']:table.selection_add(item)
            fees.set(ledgers.number(proposed['proposed_fee']));messagebox.showinfo('Suggestion only','Selected a possible batch. The proposed fee difference is not posted. Verify the provider advice, days, amounts and fee/GST before approval.',parent=dialog)
        def approve():
            keys=[items[table.index(i)]['key'] for i in table.selection()]
            account={'UPI':'1110','Card':'1120','Cash':'1000'}[channel.get()]
            import copy
            args=dict(bank_id=bank_id,clearing_account=account,keys=keys,fees_minor=r.amount(fees.get()),gst_minor=r.amount(tax.get()),gst_mode=taxmode.get(),partial_gross_minor=r.amount(partial.get()) if partial.get().strip() else None)
            test=copy.deepcopy(self.state);record=r.settle(test,**args)
            voucher=next(v for v in test['vouchers'] if v['id']==record['posting'])
            lines='\n'.join(self.branches[l['branch']]+' | '+l['account']+' | Dr '+ledgers.number(l['debit'])+' Cr '+ledgers.number(l['credit']) for l in voucher['lines'])
            if messagebox.askyesno('Approve settlement journal',lines+'\n\nPost and match this reviewed gross-to-net settlement?',parent=dialog):
                self.commit(lambda s:r.settle(s,**args));dialog.destroy();self.refresh_bank_tables()
        actions=ttk.Frame(f);actions.pack(fill='x');self.button(actions,'Load channel receipts',refresh);self.button(actions,'Suggest NBD batch',suggest);self.button(actions,'Review & post settlement',approve,True);refresh()

    def bank_exception(self):
        bank_id=self._one_bank();reason=simpledialog.askstring('Reviewed bank reconciling item','Reason for the bank error/dispute or genuine cutoff item (ordinary fees/receipts should be posted):',parent=self)
        if reason:self.commit(lambda s:r.classify_exception(s,bank_id,reason));self.refresh_bank_tables()
    def remove_bank_exception(self):
        bank_id=self._one_bank();reason=simpledialog.askstring('Remove classification','Reason:',parent=self)
        if reason:self.commit(lambda s:r.remove_exception(s,bank_id,reason));self.refresh_bank_tables()
    def undo_bank_match(self):
        selected=self.brs_match_table.selection()
        if not selected:raise ValueError('Select a match in Match history.')
        m=self.brs_match_data[selected[0]];reason=simpledialog.askstring('Undo match','Reason (owned adjustment/settlement journals are reversed, not deleted):',parent=self)
        if not reason:return
        day=simpledialog.askstring('Undo / reversal date','YYYY-MM-DD',initialvalue=datetime.now(activity.INDIA).date().isoformat(),parent=self)
        if day:self.commit(lambda s:r.undo_match(s,m.get('id',m.get('bank_id')),reason,day));self.refresh_bank_tables()
    def _required_statement(self):
        sid=self._statement_id()
        if not sid:raise ValueError('Select a specific imported statement first.')
        return sid
    def set_bank_balances(self):
        sid=self._required_statement();s=r.statement(self.state,sid)
        opening=simpledialog.askstring('Verified bank opening','Opening INR (negative for overdraft):',initialvalue='' if s['opening'] is None else ledgers.number(s['opening']),parent=self)
        if opening is None:return
        closing=simpledialog.askstring('Verified bank closing','Closing INR (negative for overdraft):',initialvalue='' if s['closing'] is None else ledgers.number(s['closing']),parent=self)
        if closing is not None:self.commit(lambda state:r.update_balances(state,sid,opening,closing));self.refresh_bank_tables()
    def finalize_bank_statement(self):
        sid=self._required_statement();report=r.brs(self.state,sid)
        if not report['ready']:raise ValueError('BRS remains incomplete. Check the unexplained difference, missing balances and unclassified bank rows.')
        if messagebox.askyesno('Complete bank reconciliation','Confirm the statement, all outstanding/cutoff items and zero unexplained difference? This locks bank postings through the statement end until it is reopened.',parent=self):
            self.commit(lambda s:r.finalize(s,sid));self.refresh_bank_tables()
    def reopen_bank_statement(self):
        sid=self._required_statement();reason=simpledialog.askstring('Reopen reconciliation','Reason:',parent=self)
        if reason:self.commit(lambda s:r.reopen(s,sid,reason));self.refresh_bank_tables()
    def export_brs(self,kind):
        report=r.brs(self.state,self._required_statement());path=filedialog.asksaveasfilename(initialfile='BRS-'+report['statement']['bank_account']+'-'+report['statement']['through']+'.'+kind,defaultextension='.'+kind,parent=self)
        if not path:return
        {'pdf':brs_exports.export_pdf,'csv':brs_exports.export_csv,'html':brs_exports.export_html}[kind](report,path)
        if kind=='html':webbrowser.open(Path(path).resolve().as_uri())
        else:messagebox.showinfo('BRS saved',path,parent=self)
    def void_bank_statement(self):
        sid=self._required_statement();reason=simpledialog.askstring('Void unused import','Reason (bank rows shared with another statement are retained; matched rows must be undone first):',parent=self)
        if reason:self.commit(lambda s:r.void_statement(s,sid,reason));self.refresh_bank_tables()
    def _calendar_tab(self,parent):
        policy=self.state['settings'].get('bank_reconciliation',{})
        top=ttk.Frame(parent);top.pack(fill='x');tol=self.field(top,'Business-day tolerance',str(policy.get('tolerance',1)),['0','1'],width=15)
        use=tk.BooleanVar(value=policy.get('use_value_date',False));ttk.Checkbutton(top,text='Use value date for matching suggestions',variable=use).pack(side='left',padx=15)
        top=ttk.Frame(parent);top.pack(fill='x');working=self.field(top,'Exceptional working dates (comma-separated YYYY-MM-DD)',', '.join(policy.get('working_days',[])),width=70)
        years=', '.join(sorted({d[:4] for d in self.state['holidays']})) or 'none'
        ttk.Label(parent,text='Holiday years currently represented: '+years+'. Review the complete Bengaluru bank list for each statement year.',wraplength=900).pack(anchor='w',pady=5)
        ttk.Label(parent,text='Bengaluru calendar: Sundays and second/fourth Saturdays are excluded. Existing manual holidays in Settings remain in force. Import dated holidays with name and source; no online calendar is silently assumed.',wraplength=900).pack(anchor='w',pady=12)
        def save(calendar=''):
            self.commit(lambda s:r.set_policy(s,int(tol.get()),use.get(),calendar,working.get()));messagebox.showinfo('Calendar saved','Policy saved for future suggestions. Existing matches retain their reviewed policy snapshot.',parent=self)
        def upload():
            path=filedialog.askopenfilename(filetypes=[('Holiday CSV','*.csv')],parent=self)
            if path:save(Path(path).read_text(encoding='utf-8-sig'))
        actions=ttk.Frame(parent);actions.pack(fill='x');self.button(actions,'Save matching policy',save,True);self.button(actions,'Import holiday CSV',upload)
        ttk.Label(parent,text='Holiday CSV columns: date,name,source. Manual matches remain reviewable when the actual bank date lies outside a suggestion window. Source holiday dates remain editable in Settings & backup.',wraplength=900).pack(anchor='w',pady=12)

"""Dedicated cash expense/funding entry, category report mapping and review."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from . import petty_cash as pc,bulk_import as bulk,core,foundation
from .date_picker import today

class PettyCashUI:
    def petty_cash_page(self):
        self.note('Record actual dated cash expenses and funding. Stock, staff advances and salary-liability payments have separate treatments. 1000 Cash is used; no opening, sales or GST/TDS is guessed. Review cash custody/funding if physical cash is negative.')
        bar=self.bar();self.pc_start=self.field(bar,'From',self.dates()[0],width=13);self.pc_end=self.field(bar,'Through',self.dates()[1],width=13);self.button(bar,'Refresh petty cash',self.refresh_petty_cash,True)
        bar=self.bar();self.button(bar,'Record cash expense / top-up',self.petty_cash_entry,True);self.button(bar,'Upload bulk petty cash',self.petty_cash_upload)
        self.button(bar,'Excel template',lambda:self.petty_cash_template('xlsx'));self.button(bar,'CSV template',lambda:self.petty_cash_template('csv'))
        self.pc_summary=ttk.Label(self.content,text='',wraplength=1050);self.pc_summary.pack(anchor='w',pady=8)
        self.pc_table=self.table(('Date','Reference','Unit','Category','Treatment','Counterpart','INR','Voucher','Status'),[],height=8)
        self.pc_batches=self.table(('Batch','File','Rows','Status'),[],height=4)
        bar=self.bar();self.button(bar,'Review selected petty cash batch',self.petty_cash_open_batch)
        for kind in ('xlsx','pdf'):self.button(bar,'Register '+kind.upper(),lambda kind=kind:self.petty_cash_export(kind))
        self.refresh_petty_cash()
    def refresh_petty_cash(self):
        start,end=self.pc_start.get(),self.pc_end.get();pack=pc.register_pack(self.state,start,end,self.unit());self.pc_table.delete(*self.pc_table.get_children())
        for row in pack['rows']:self.pc_table.insert('','end',values=[core.rupees(v) if i==6 else v for i,v in enumerate(row)])
        cash=core.balances(self.state,end,self.unit())['1000'];self.pc_summary.configure(text='Closing cash '+core.rupees(cash)+' | '+str(len(pack['rows']))+' cash records in period. '+('NEGATIVE CASH: review opening/funding and staff-paid items.' if cash<0 else 'Funding is not an expense; cash already collected in Sales receipt must not be entered again.'))
        self.pc_batches.delete(*self.pc_batches.get_children())
        for q in self.state['queue']:
            if q.get('petty_cash'):self.pc_batches.insert('','end',iid=q['id'],values=(q['id'][:8],q['filename'],len(q['rows']),q['status']))
    def petty_cash_template(self,kind):
        path=filedialog.asksaveasfilename(parent=self,initialfile='Yathartha-Petty-Cash-Template.'+kind,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:pc.template(path,self.state);messagebox.showinfo('Petty cash template',str(path),parent=self)
    def petty_cash_entry(self):
        accounts=[a['code']+' '+a['name'] for a in self.state['accounts'] if self.state['account_details'][a['code']].get('active',True) and a['code']!='1000'];units=list(foundation.branches(self.state,True));unit=self.unit() if self.unit()!='ALL' else ''
        win,body,fields=self._tax_form('Record petty cash',[
            ('date','Actual payment / receipt date','',None),('reference','Unique cash voucher reference','',None),('branch','Operating unit',unit,['']+units),('category','Category','',None),('treatment','Accounting treatment','Expense',list(pc.TREATMENTS)),('account','Counterpart account (code and name)','',['']+accounts),('amount','Cash amount INR','',None),('narration','Description / payee','',None),('basis','Accounting review basis','',None)])
        ttk.Label(body,text='Cash top-up debits cash and credits its genuine source. Other treatments credit cash. Salary liabilities must already be accrued; vendor invoices and GST/TDS use their dedicated pages. Actual date is required for historical entries.',wraplength=1000).pack(anchor='w',pady=8)
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed the source, actual date, cash/funding, category and tax treatment; no duplicate receipt/payment.',variable=confirmed).pack(anchor='w')
        def preview():
            v={k:w.get().strip() for k,w in fields.items()};v['account']=v['account'].split(' ')[0];self._service_preview('Review petty cash journal',lambda s:pc.record(s,v,confirmed.get()),win,page='Petty cash')
        self.button(body,'Preview petty cash journal',preview,True)
    def petty_cash_upload(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Petty cash report or standard template','*.xlsx *.csv')])
        if not path:return
        raw=Path(path).read_bytes();parsed=pc.read_source(raw,Path(path).name);win=tk.Toplevel(self);win.title('Review petty cash source and mapping');win.geometry('1120x800');win.transient(self)
        ttk.Label(win,text=str(len(parsed['entries']))+' source item(s) | '+parsed['layout']+' | '+parsed['sheet']+'\n'+'\n'.join(parsed['warnings']),wraplength=1060,padding=8).pack(anchor='w',fill='x')
        config=ttk.Frame(win);config.pack(fill='x');units=list(foundation.branches(self.state,True));unit=self.field(config,'Operating unit (matrix)',self.unit() if self.unit()!='ALL' else '',['']+units,width=16)
        first=parsed['entries'][0]['values'].get('date','');prefix=self.field(config,'Stable report reference (matrix)','PC-'+first[:7] if first else '',width=23);basis=self.field(config,'Accounting review basis (matrix)','',width=42)
        # Scroll category mappings so all controls remain reachable for long reports.
        canvas=tk.Canvas(win,height=300,highlightthickness=0);scroll=ttk.Scrollbar(win,orient='vertical',command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        holder=ttk.Frame(canvas);window=canvas.create_window((0,0),window=holder,anchor='nw');holder.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=max(e.width,holder.winfo_reqwidth())))
        mapping={};accounts=[a['code']+' '+a['name'] for a in self.state['accounts'] if self.state['account_details'][a['code']].get('active',True) and a['code']!='1000']
        for category in parsed['categories']:
            m=pc.defaults(self.state,category);bar=ttk.Frame(holder);bar.pack(fill='x',pady=4);ttk.Label(bar,text=category,width=29).pack(side='left');t=self.field(bar,'Treatment',m['treatment'],list(pc.TREATMENTS),width=23);choice=next((a for a in accounts if a.split(' ')[0]==m['account']),'');a=self.field(bar,'Reviewed counterpart ledger',choice,['']+accounts,width=40);mapping[category]=(t,a)
        if parsed['layout']=='standard':ttk.Label(holder,text='Standard source rows already contain unit, treatment, account and review basis. These are validated per row in the next screen. No mapping overrides are applied.',wraplength=1000).pack(anchor='w')
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(win,text='I reviewed source dates, unit, ledger mappings and tax treatment. Funding/opening/cash sales will not be duplicated.',variable=confirmed).pack(anchor='w',pady=8)
        def stage():
            mappings={category:dict(treatment=t.get(),account=a.get().split(' ')[0]) for category,(t,a) in mapping.items()}
            q=self.commit(lambda s:pc.stage(s,raw,Path(path).name,parsed,unit.get(),prefix.get(),mappings,basis.get(),confirmed.get()));win.destroy();self.petty_cash_review(q['id'])
        self.button(win,'Stage and review petty cash rows',stage,True)
    def petty_cash_open_batch(self):
        if not self.pc_batches.selection():raise ValueError('Select a petty cash batch.')
        self.petty_cash_review(self.pc_batches.selection()[0])
    def petty_cash_review(self,key):
        q=bulk._queue(self.state,key)
        if not q.get('petty_cash'):raise ValueError('Select a petty cash batch.')
        win=tk.Toplevel(self);win.title('Review petty cash — '+q['filename']);win.geometry('1220x760');win.transient(self)
        status=ttk.Label(win,text='',wraplength=1160,padding=6);status.pack(anchor='w');detail=ttk.Label(win,text='Select a row for source, reason and accounting basis.',wraplength=1160,padding=6);detail.pack(anchor='w',fill='x')
        columns=('Source','Date','Reference','Unit','Category','Treatment','Account','Amount INR','Review','Reason / correction')
        table=self.table(columns,[],parent=win,height=11);table.configure(selectmode='extended');table.column('Reason / correction',width=400);table.column('Source',width=65,stretch=False)
        table.tag_configure('INVALID',background='#FCE8E6',foreground='#8B1A12');table.tag_configure('DUPLICATE',background='#FFF1CB',foreground='#754600')
        def select(event=None):
            if table.selection():
                r=bulk._queue(self.state,key)['rows'][int(table.selection()[0])];detail.configure(text='Source '+(r.get('source_cell') or str(r['source_row']))+' | '+r.get('petty_category','')+' | '+(r['error'] or 'Source checks passed')+'\nReview: '+r['reason']+' | Basis: '+r.get('petty_basis',''))
        table.bind('<<TreeviewSelect>>',select)
        def refresh():
            q=bulk._queue(self.state,key);table.delete(*table.get_children());counts={v:sum(r['review']==v for r in q['rows']) for v in ('PENDING','APPROVED','REJECTED','INVALID','DUPLICATE')};status.configure(text=q['status']+' | '+str(counts)+' | Source outflows/receipts '+core.rupees(sum(r['amount'] for r in q['rows'] if type(r.get('amount'))==int))+'\n'+'\n'.join(q.get('warnings',[])))
            names={a['code']:a['name'] for a in self.state['accounts']}
            for i,r in enumerate(q['rows']):
                a=r.get('petty_account','');table.insert('','end',iid=str(i),tags=(r['review'],),values=(r.get('source_cell') or r['source_row'],r.get('date',''),r.get('reference',''),r.get('branch',''),r.get('petty_category',''),r.get('petty_treatment',''),a+' '+names.get(a,''),core.rupees(r['amount']) if type(r.get('amount'))==int else str(r.get('amount','')),r['review'],r['error'] or r['reason']))
            first=next((str(i) for i,r in enumerate(q['rows']) if r['review'] in ('INVALID','DUPLICATE')),None)
            if first is not None:table.selection_set(first);table.see(first);select()
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(win,text='I reviewed actual dates, cash evidence, ledger/tax treatment, source totals and no duplicate sales/funding.',variable=confirmed).pack(anchor='w')
        def review(approved,allrows=False):
            if approved and not confirmed.get():raise ValueError('Confirm source/accounting/tax review before approving cash rows.')
            q=bulk._queue(self.state,key);indices=[i for i,r in enumerate(q['rows']) if r['review']=='PENDING'] if allrows and approved else [i for i,r in enumerate(q['rows']) if r['review'] in ('INVALID','DUPLICATE')] if allrows else [int(i) for i in table.selection()]
            if not indices:raise ValueError('Select source rows; no eligible rows remain.')
            reason=simpledialog.askstring('Petty cash review','Approval/rejection basis:',parent=win)
            if reason:
                def action(s):
                    for i in indices:bulk.review_row(s,key,i,approved,reason)
                self.commit(action);refresh()
        bar=ttk.Frame(win);bar.pack(fill='x');self.button(bar,'Approve selected rows',lambda:review(True));self.button(bar,'Reject selected rows',lambda:review(False));self.button(bar,'Approve all valid rows',lambda:review(True,True),True);self.button(bar,'Reject flagged rows',lambda:review(False,True))
        def preview():
            if not confirmed.get():raise ValueError('Confirm cash/source/accounting review before previewing journals.')
            self._service_preview('Review petty cash batch journals',lambda s:bulk.approve(s,key),win,page='Petty cash')
        def cancel():
            reason=simpledialog.askstring('Cancel unposted petty cash','Reason (correct source/mapping and reupload if needed):',parent=win)
            if reason:self.commit(lambda s:bulk.cancel(s,key,reason));refresh()
        bar=ttk.Frame(win);bar.pack(fill='x');self.button(bar,'Preview cash journals',preview,True);self.button(bar,'Cancel unused batch',cancel)
        for kind in ('xlsx','pdf'):
            def export(kind=kind):
                path=filedialog.asksaveasfilename(parent=win,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
                if path:
                    from . import financial_reports
                    pack=pc.review_pack(self.state,key);(financial_reports.export_xlsx if kind=='xlsx' else financial_reports.export_pdf)(pack,path)
            self.button(bar,'Review '+kind.upper(),export)
        refresh()
    def petty_cash_export(self,kind):
        from . import financial_reports
        pack=pc.register_pack(self.state,self.pc_start.get(),self.pc_end.get(),self.unit());path=filedialog.asksaveasfilename(parent=self,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:(financial_reports.export_xlsx if kind=='xlsx' else financial_reports.export_pdf)(pack,path)

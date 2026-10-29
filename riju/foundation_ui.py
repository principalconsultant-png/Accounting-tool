"""Desktop setup, ledger master and saved-draft screens."""
import copy
import csv
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from . import core, foundation as f


class FoundationUI:
    @property
    def branches(self):
        return f.branches(self.state)

    def refresh_masters(self):
        self.branch_names={'All operating units':'ALL',**{v:k for k,v in self.branches.items()}}
        self.branch_select.configure(values=list(self.branch_names))
        if self.branch.get() not in self.branch_names:self.branch.set('All operating units')
        years={date.today().year,core.financial_year(date.today().isoformat()),*map(int,self.state['financial_years'])}
        years.update(core.financial_year(v['date']) for v in self.state['vouchers'])
        self.year_select.configure(values=sorted(years,reverse=True))

    def setup(self):
        self.note('One legal entity. Registration details are optional: leave them blank and enter them later. Branch codes remain stable in posted books.')
        tabs=ttk.Notebook(self.content);tabs.pack(fill='both',expand=True)
        entity=ttk.Frame(tabs,padding=12);branches=ttk.Frame(tabs,padding=12);periods=ttk.Frame(tabs,padding=12)
        tabs.add(entity,text='Entity details');tabs.add(branches,text='Branches');tabs.add(periods,text='Years & openings')
        row=ttk.Frame(entity);row.pack(fill='x')
        self.entity_name=self.field(row,'Legal entity name',self.state['settings']['entity'],width=45)
        self.entity_fields={}
        labels=[('address','Address'),('city','City'),('state','State'),('state_code','State code'),('pan','PAN'),('tan','TAN'),('gstin','GSTIN'),('cin','CIN')]
        for i,(key,label) in enumerate(labels):
            if i%3==0:row=ttk.Frame(entity);row.pack(fill='x')
            self.entity_fields[key]=self.field(row,label+' (optional)',self.state['settings']['registration'].get(key,''),width=26)
        ttk.Label(entity,text='Blank means not yet supplied. Saving a number checks its format, not registration validity.',wraplength=850).pack(anchor='w',pady=15)
        def save_entity():
            self.commit(lambda s:f.save_entity(s,self.entity_name.get(),{k:v.get() for k,v in self.entity_fields.items()}))
            messagebox.showinfo('Saved','Entity details saved. You can add missing registration numbers later.',parent=self)
        self.button(entity,'Save entity details',save_entity,True)
        row=ttk.Frame(entity);row.pack(fill='x',pady=12)
        departments=self.field(row,'Department tags (optional, comma-separated)',', '.join(self.state['settings']['departments']),width=70)
        self.button(row,'Save department tags',lambda:self.commit(lambda s:f.save_departments(s,departments.get().split(','))))
        table=self.table(('Code','Name','Status','Active','Beds','GSTIN'),[(c,b['name'],b['status'],'Yes' if b['active'] else 'No',b['beds'],b['gstin']) for c,b in self.state['branches'].items()],parent=branches,height=4)
        self.branch_fields={}
        spec=[('code','Stable branch code','',None),('name','Branch name','',None),('city','City (optional)','',None),
              ('state','State (optional)','',None),('state_code','State code (optional)','',None),('gstin','GSTIN (optional)','',None),
              ('beds','Beds','0',None),('status','Operating status','Operational',['Operational','Under construction','Closed']),('opening_date','Opening date (optional)','',None)]
        for i,(key,label,default,values) in enumerate(spec):
            if i%3==0:row=ttk.Frame(branches);row.pack(fill='x')
            self.branch_fields[key]=self.field(row,label,default,values,width=24)
        self.branch_active=tk.BooleanVar(value=True)
        ttk.Checkbutton(branches,text='Active for new entries (history remains visible when inactive)',variable=self.branch_active).pack(anchor='w',pady=8)
        self.editing_branch=None
        def fill(event=None):
            if not table.selection():return
            code=str(table.item(table.selection()[0])['values'][0]);b=self.state['branches'][code]
            self.editing_branch=code
            for key,var in self.branch_fields.items():var.set(code if key=='code' else str(b.get(key,'')))
            self.branch_active.set(b['active'])
        table.bind('<<TreeviewSelect>>',fill)
        def new():
            self.editing_branch=None
            for key,var in self.branch_fields.items():var.set('0' if key=='beds' else 'Operational' if key=='status' else '')
            self.branch_active.set(True);table.selection_remove(*table.selection())
        def save_branch():
            values={k:v.get() for k,v in self.branch_fields.items()};code=values.pop('code').strip().upper()
            if self.editing_branch and code!=self.editing_branch:raise ValueError('Existing branch codes cannot change. Choose New branch to add one.')
            if not self.editing_branch and code in self.state['branches']:raise ValueError('That code exists. Select its row to edit it.')
            values['active']=self.branch_active.get()
            self.commit(lambda s:f.save_branch(s,code,values));self.show('Setup & periods')
        row=ttk.Frame(branches);row.pack(fill='x');self.button(row,'New branch',new);self.button(row,'Save branch',save_branch,True)
        ttk.Label(periods,text='Opening balances are entered once per branch. Subsequent years carry forward automatically.\nUse retained earnings for prior-year results; openings cannot use revenue or expense ledgers.',wraplength=900).pack(anchor='w',pady=8)
        t=self.table(('Financial year','Status'),[(y+'–'+str(int(y)+1),'Closed' if v['closed'] else 'Open') for y,v in sorted(self.state['financial_years'].items())],parent=periods,height=4)
        row=ttk.Frame(periods);row.pack(fill='x')
        self.setup_year=self.field(row,'Financial year starts in',self.year.get(),width=14)
        def add_year():
            y=self.commit(lambda s:f.register_year(s,self.setup_year.get()));self.year.set(str(y));self.show('Setup & periods')
        self.button(row,'Add financial year',add_year,True)
        def opening():
            self.show('Journal studio');self.jopening.set(True)
            self.jdate.set(core.fy_bounds(int(self.year.get()))[0]);self.narration.insert('1.0','Initial opening balances')
        self.button(row,'Enter opening balances',opening)
        row=ttk.Frame(periods);row.pack(fill='x',pady=8)
        def template():
            p=filedialog.asksaveasfilename(initialfile='riju-opening-balances.csv',defaultextension='.csv',parent=self)
            if p:Path(p).write_text('date,narration,branch,debit_account,credit_account,amount\n'+core.fy_bounds(int(self.year.get()))[0]+',Initial opening,JP,1010,3000,100000\n',encoding='utf-8')
        self.button(row,'Opening CSV template',template)
        def upload():
            p=filedialog.askopenfilename(filetypes=[('Opening CSV','*.csv')],parent=self)
            if not p:return
            raw=Path(p).read_text(encoding='utf-8-sig');candidate=copy.deepcopy(self.state)
            posted=f.import_openings(candidate,raw)
            dialog=tk.Toplevel(self);dialog.title('Review opening balances');dialog.geometry('1000x550');dialog.transient(self)
            self.table(('Date','Unit','Account','Debit','Credit'),[(v['date'],self.branches[l['branch']],l['account']+' '+self.account_name(l['account']),core.rupees(l['debit']),core.rupees(l['credit'])) for v in posted for l in v['lines']],parent=dialog)
            def approve():
                self.commit(lambda s:f.import_openings(s,raw));dialog.destroy();self.show('Setup & periods')
            self.button(dialog,'Approve balanced opening vouchers',approve,True)
        self.button(row,'Review opening CSV',upload)
        row=ttk.Frame(periods);row.pack(fill='x',pady=8)
        self.lock_date=self.field(row,'Lock through (YYYY-MM-DD)',self.state['locked_through'],width=22)
        def lock():
            if messagebox.askyesno('Lock period','Block new and backdated entries through this date? This lock cannot be moved backwards in this build.',parent=self):
                self.commit(lambda s:f.lock_period(s,self.lock_date.get()));self.show('Setup & periods')
        self.button(row,'Lock period',lock)
        def close():
            year=int(self.setup_year.get());candidate=copy.deepcopy(self.state);f.close_year(candidate,year)
            entries=candidate['vouchers'][len(self.state['vouchers']):]
            detail='\n'.join(self.branches[v['lines'][0]['branch']]+': '+core.rupees(sum(l['debit'] for l in v['lines']))+' closing debits / credits' for v in entries)
            if messagebox.askyesno('Review year-end close',f'Close FY {year}–{year+1}?\n\n{detail or "No unclosed income/expense balances."}\n\nThis transfers all unclosed results through year-end to retained earnings and locks entries through 31 March. It cannot be undone in this build. Review your statements first.',parent=self):
                self.commit(lambda s:f.close_year(s,year));self.show('Setup & periods')
        self.button(row,'Review & close financial year',close)

    def accounts(self):
        self.note('Create ledger masters here. Patient A/C is shared; individual patient ledgers are not required. Select a row to edit its name or mappings. Used ledgers remain in history.')
        table=self.table(('Code','Ledger name','Classification','Report group','Active'),[(a['code'],a['name'],a['kind'],self.state['account_details'].get(a['code'],{}).get('group','Review'),'Yes' if self.state['account_details'].get(a['code'],{}).get('active',True) else 'No') for a in self.state['accounts']],height=8)
        row=self.bar();self.ledger_code=self.field(row,'4-digit code','',width=10);self.ledger_name=self.field(row,'Ledger name','',width=30)
        self.ledger_kind=self.field(row,'Classification','Expense',list(f.KINDS),width=14)
        row=self.bar();self.ledger_group=self.field(row,'Report group','Administration',f.GROUPS['Expense'],width=24)
        # Reconfigure the group choices when the classification changes.
        group_combo=row.winfo_children()[0].winfo_children()[-1]
        def kind_changed(*args):
            groups=f.GROUPS[self.ledger_kind.get()];group_combo.configure(values=groups)
            if self.ledger_group.get() not in groups:self.ledger_group.set(groups[0])
        self.ledger_kind.trace_add('write',kind_changed)
        self.ledger_flow=self.field(row,'Cash-flow group','Review',list(f.CASH_FLOW),width=18)
        self.ledger_description=self.field(row,'Description','',width=30)
        self.ledger_active=tk.BooleanVar(value=True);ttk.Checkbutton(row,text='Active',variable=self.ledger_active).pack(side='left',padx=8)
        self.editing_ledger=None
        def fill(event=None):
            if not table.selection():return
            code=str(table.item(table.selection()[0])['values'][0]);a=next(a for a in self.state['accounts'] if a['code']==code);d=self.state['account_details'][code]
            self.editing_ledger=code;self.ledger_code.set(code);self.ledger_name.set(a['name']);self.ledger_kind.set(a['kind'])
            self.ledger_group.set(d['group']);self.ledger_flow.set(d['cash_flow']);self.ledger_description.set(d['description']);self.ledger_active.set(d['active'])
        table.bind('<<TreeviewSelect>>',fill)
        def new():
            self.editing_ledger=None;self.ledger_code.set('');self.ledger_name.set('');self.ledger_description.set('');self.ledger_active.set(True)
            table.selection_remove(*table.selection())
        def save():
            code=self.ledger_code.get().strip()
            if self.editing_ledger and code!=self.editing_ledger:raise ValueError('Ledger codes are stable. Choose New ledger to create a different account.')
            if not self.editing_ledger and any(a['code']==code for a in self.state['accounts']):raise ValueError('Select the existing ledger to edit it.')
            self.commit(lambda s:f.save_account(s,code,self.ledger_name.get(),self.ledger_kind.get(),self.ledger_group.get(),self.ledger_flow.get(),self.ledger_active.get(),self.ledger_description.get()))
            self.show('Chart of accounts')
        def delete():
            if not self.editing_ledger:raise ValueError('Select an unused inactive ledger.')
            if messagebox.askyesno('Delete unused ledger','Delete this unused inactive ledger?',parent=self):
                self.commit(lambda s:f.delete_account(s,self.editing_ledger));self.show('Chart of accounts')
        row=self.bar();self.button(row,'New ledger',new);self.button(row,'Save ledger',save,True);self.button(row,'Delete unused inactive ledger',delete)

    def journal_metadata(self):
        metadata={'type':self.jtype.get(),'reference':self.jreference.get(),'payee':self.jpayee.get()}
        if self.jbank.get()!='From journal lines':metadata['bank_account']=self.jbank.get().split(' · ')[0]
        return metadata

    def save_current_draft(self):
        d=self.commit(lambda s:f.save_draft(s,self.jdate.get(),self.narration.get('1.0','end').strip(),self.draft,self.journal_metadata(),self.draft_id,self.jopening.get()))
        self.draft_id=d['id'];messagebox.showinfo('Draft saved','Draft saved locally. No ledger posting has occurred.',parent=self)

    def saved_drafts(self):
        self.note('Saved drafts can be incomplete or unbalanced. They are validated again before posting and do not affect the books until approved.')
        table=self.table(('ID','Date','Type','Narration','Lines'),[(d['id'],d['date'],d['metadata'].get('type','Journal'),d['narration'],len(d['lines'])) for d in self.state['drafts']])
        def selected():
            if not table.selection():raise ValueError('Select a saved draft.')
            return self.state['drafts'][table.index(table.selection()[0])]
        def edit():
            d=copy.deepcopy(selected());self.show('Journal studio');self.draft_id=d['id'];self.jdate.set(d['date']);self.jopening.set(d['opening'])
            self.narration.insert('1.0',d['narration']);self.draft=d['lines']
            self.jtype.set(d['metadata'].get('type','Journal'));self.jreference.set(d['metadata'].get('reference',''));self.jpayee.set(d['metadata'].get('payee',''))
            if d['metadata'].get('bank_account'):
                code=d['metadata']['bank_account'];self.jbank.set(code+' · '+self.account_name(code))
            if d['lines']:self.jbranch.set(self.branches[d['lines'][0]['branch']])
            self.refresh_draft()
        def discard():
            d=selected()
            if messagebox.askyesno('Discard draft','Discard this unposted draft?',parent=self):
                self.commit(lambda s:f.discard_draft(s,d['id']));self.show('Saved drafts')
        row=self.bar();self.button(row,'Open & edit draft',edit,True);self.button(row,'Discard draft',discard)

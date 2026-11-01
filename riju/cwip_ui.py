"""Desktop review screens for project construction and commissioning."""
import copy
import csv
import io
import json
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from . import cwip, core, fixed_assets as fa, tax


class CwipUI:
    def cwip_projects(self):
        self.note('Vaikom / project CWIP: review eligible capitalization separately from hospital expenses. Budgets are optional; blank means unknown. Each cost, withholding, retention release and commissioning requires a frozen review preview. Cost amounts include nonrecoverable taxes; exclude eligible input GST. GST/RCM and TDS challans retain their separate reviewed workflows. No project budget or operating date is assumed.')
        start,end=self.dates();bar=self.bar()
        self.cwip_asof=self.field(bar,'CWIP as at',getattr(self,'cwip_report_end',end),width=15)
        def refresh():self.cwip_report_end=self.cwip_asof.get();self.show('CWIP & commissioning')
        self.button(bar,'Refresh CWIP',refresh)
        bar=self.bar();self.button(bar,'Create project',self.new_cwip_project,True);self.button(bar,'Revise budgets / milestones',self.cwip_plan);self.button(bar,'Review project cost',self.cwip_cost)
        bar=self.bar();self.button(bar,'Deduct project TDS',self.cwip_tds);self.button(bar,'Link B09 deduction',self.cwip_link_tds);self.button(bar,'Link existing retention',self.cwip_existing_retention);self.button(bar,'Release / pay retention',self.cwip_retention);self.button(bar,'Expense ineligible CWIP',self.cwip_expense);self.button(bar,'Commission into PPE',self.cwip_commission,True)
        bar=self.bar();self.button(bar,'Reverse selected project event',self.cwip_reverse)
        for kind in ('xlsx','pdf','json'):self.button(bar,'Export '+('Excel' if kind=='xlsx' else kind.upper()),lambda kind=kind:self.export_cwip(kind))
        end=self.cwip_asof.get();start=min(start,end);self.cwip_report=cwip.report(self.state,start,end,self.unit());r=self.cwip_report
        ttk.Label(self.content,text=('Reconciled project working' if r['ready'] else 'DRAFT — '+ '; '.join(r['issues'])),wraplength=1000).pack(anchor='w',pady=8)
        self.cwip_project_table=self.table(('Key','Project','Unit'),[(p['key'],cwip.plan(p,end)['name'],p['branch']) for p in cwip.data(self.state)['projects'] if self.unit() in ('ALL',p['branch'])],height=4)
        self.cwip_project_rows=dict(zip(self.cwip_project_table.get_children(),[p for p in cwip.data(self.state)['projects'] if self.unit() in ('ALL',p['branch'])]))
        self.table(('Project','Name','Unit','Category','Budget','Gross costs','Capital','Commissioned','Reclassified expense','Operating expense','CWIP','Budget less gross'),[[core.rupees(v) if i>=4 and v is not None else '' if v is None else v for i,v in enumerate(row)] for row in r['summary']],height=5)
        self.cwip_cost_table=self.table(('Project','Cost ID','Source ref','Supplier','Category','Date','Gross','Capital','Expense','CWIP','Retention','TDS','Voucher','Status','Review basis'),[[core.rupees(v) if 6<=i<=11 else v for i,v in enumerate(row)] for row in r['costs']],height=5)
        self.cwip_cost_rows=dict(zip(self.cwip_cost_table.get_children(),r['costs']))
        self.cwip_event_table=self.table(('Project','Date','Action','Voucher','Asset ID','Amount','Status','Basis'),[[*r[:5],core.rupees(r[5]),*r[6:]] for r in r['events']],height=4)
        self.cwip_event_rows=dict(zip(self.cwip_event_table.get_children(),r['events']))
        self.table(('Project','Unit','Ledger','Source Dr/(Cr)','Ledger Dr/(Cr)','Difference'),[[*r[:3],*[core.rupees(v) for v in r[3:]]] for r in r['proof']],height=5)
        self.table(('Project','Key','Milestone','Target date','Completed date','Basis'),r['milestones'],height=4)

    def _cwip_project(self):
        if not self.cwip_project_table.selection():raise ValueError('Select a project first.')
        return self.cwip_project_rows[self.cwip_project_table.selection()[0]]

    def _cwip_cost(self):
        if not self.cwip_cost_table.selection():raise ValueError('Select a project cost source first.')
        return cwip.cost(self.state,self.cwip_cost_rows[self.cwip_cost_table.selection()[0]][1])

    def _cwip_preview(self,title,action,form=None):
        before=copy.deepcopy(self.state);candidate=copy.deepcopy(before);result=action(candidate)
        win=tk.Toplevel(self);win.title(title);win.geometry('1000x650');win.transient(form or self);win.grab_set()
        ttk.Label(win,text='Review the exact sources, allocations and journals. Approval saves this frozen result only while the books remain unchanged.',wraplength=950,padding=10).pack(anchor='w')
        bar=ttk.Frame(win);bar.pack(side='bottom',fill='x');text=tk.Text(win,wrap='word');scroll=ttk.Scrollbar(win,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True)
        text.insert('1.0',json.dumps(dict(result=result,new_journals=candidate['vouchers'][len(before['vouchers']):]),ensure_ascii=False,indent=2));text.configure(state='disabled')
        def approve():
            if self.state!=before:raise ValueError('Books changed after this preview. Prepare a fresh CWIP review.')
            def persist(s):s.clear();s.update(copy.deepcopy(candidate));return result
            self.commit(persist);win.destroy()
            if form and form.winfo_exists():form.destroy()
            self.show('CWIP & commissioning')
        self.button(bar,'Approve CWIP action',approve,True)

    def _cwip_form(self,title,specs,action):
        win,body,fields=self._tax_form(title,specs)
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed source allocation, capitalization/expense basis, tax applicability and actual dates',variable=reviewed).pack(anchor='w',pady=10)
        self.button(body,'Validate & preview CWIP',lambda:self._cwip_preview(title,lambda s:action(s,{k:v.get().strip() for k,v in fields.items()},reviewed.get()),win),True)
        return win,body,fields

    def new_cwip_project(self):
        self._cwip_form('Create construction project',[('key','Unique project key','',None),('name','Project name','',None),('branch','Unit','VK',list(self.branches)),*[(c,c+' existing CWIP ledger (blank creates new)','',None) for c in cwip.CATEGORIES],('retention','Existing retention ledger (blank creates new)','',None),('basis','Project/source basis','',None)],lambda s,v,r:cwip.save_project(s,v['key'],v['name'],v['branch'],v['basis'],r,{c:v[c] for c in cwip.CATEGORIES},v['retention']))

    def cwip_plan(self):
        p=self._cwip_project();pp=cwip.plan(p,self.cwip_asof.get())
        specs=[('name','Project name',pp['name'],None),('date','Effective date',self.cwip_asof.get(),None),*[(c,c+' budget INR (blank unknown)','' if pp['budgets'][c] is None else cwip.format_money(pp['budgets'][c]),None) for c in cwip.CATEGORIES],('basis','Plan revision basis','',None)]
        def save(s,v,r):
            rows=list(csv.DictReader(io.StringIO(text.get('1.0','end'))))
            return cwip.save_plan(s,p['id'],v['date'],{c:v[c] for c in cwip.CATEGORIES},rows,v['basis'],r,v['name'])
        win,body,fields=self._cwip_form('Revise project plan',specs,save)
        ttk.Label(body,text='Milestones CSV: key,name,due,completed. Dates YYYY-MM-DD; completed may be blank. Revisions retain earlier plans.').pack(anchor='w')
        text=tk.Text(body,height=7);text.pack(fill='x');out=io.StringIO();w=csv.DictWriter(out,fieldnames=['key','name','due','completed']);w.writeheader();w.writerows(pp['milestones']);text.insert('1.0',out.getvalue())

    def cwip_cost(self):
        p=self._cwip_project();specs=[('mode','Cost source mode','Post cost',['Post cost','Link existing']),('date','Cost / source date',self.cwip_asof.get(),None),('reference','Supplier/source reference','',None),('party','Supplier/payee reference','',None),('category','Cost category','Civil',list(cwip.CATEGORIES)),('gross','Gross cost INR','',None),('capital','Eligible capital INR','',None),('expense','Hospital expense ledger','4590',None),('payable','Supplier payable ledger','2000',None),('retention','Retention to hold INR','0',None),('source','Existing source voucher ID','',None),('basis','Capitalization / expense review basis','',None)]
        self._cwip_form('Review project cost',specs,lambda s,v,r:cwip.record_cost(s,p['id'],dict(v,reviewed=r)))

    def cwip_tds(self):
        c=self._cwip_cost();parties={p['party_id'] for p in tax.parties(self.state)};keys=sorted({r['key'] for r in tax.rules(self.state) if r['family']=='TDS'})
        if not parties or not keys:raise ValueError('Set up a resident payee and reviewed effective-dated TDS rule in Tax setup first.')
        specs=[('kind','TDS action','Existing payable',['Existing payable','Register existing deduction']),('tds_source','Existing TDS voucher (blank uses cost source)','',None),('date','Deduction posting date',self.cwip_asof.get(),None),('tax_date','Tax point date',c['date'],None),('rule_key','Reviewed TDS rule key',keys[0],keys),('party_id','Payee ID',sorted(parties)[0],sorted(parties)),('base','Eligible TDS base INR',cwip.format_money(c['gross']),None),('mode','Deduction mode','Automatic',['Automatic','Reviewed manual']),('manual_tax','Manual deduction INR','0',None),('review_reason','Verified applicability / exception basis','',None)]
        self._cwip_form('Deduct project TDS',specs,lambda s,v,r:cwip.deduct_tds(s,c['id'],dict(v,confirmed=r,resident_reviewed=r,narration='Project withholding '+c['reference'])))

    def cwip_link_tds(self):
        c=self._cwip_cost();self._cwip_form('Link B09 deduction already recorded',[('record','Existing B09 deduction ID','',None),('basis','Existing B09 source basis','',None)],lambda s,v,r:cwip.link_tds(s,c['id'],v['record'],v['basis'],r))

    def cwip_existing_retention(self):
        c=self._cwip_cost();self._cwip_form('Link retention already posted',[('source','Existing retention credit voucher ID',c['voucher'],None),('amount','Allocated retention INR','',None),('basis','Existing retention source basis','',None)],lambda s,v,r:cwip.link_retention(s,c['id'],v['source'],v['amount'],v['basis'],r))

    def cwip_retention(self):
        c=self._cwip_cost();self._cwip_form('Release / pay retention',[('date','Release / payment date',self.cwip_asof.get(),None),('amount','Retention amount INR','',None),('counter','Original payable or INR cash/bank ledger',c['payable'],None),('basis','Retention release / payment basis','',None)],lambda s,v,r:cwip.settle_retention(s,c['id'],v['date'],v['amount'],v['counter'],v['basis'],r))

    def cwip_expense(self):
        c=self._cwip_cost();self._cwip_form('Expense ineligible CWIP',[('date','Reclassification date',self.cwip_asof.get(),None),('amount','Ineligible cost INR','',None),('expense','Hospital expense ledger','4590',None),('basis','Reclassification source basis','',None)],lambda s,v,r:cwip.expense_remaining(s,c['id'],v['date'],v['amount'],v['expense'],v['basis'],r))

    def cwip_commission(self):
        p=self._cwip_project()
        specs=[('date','Commissioning transfer date',self.cwip_asof.get(),None),('put_to_use','Actual put-to-use date',self.cwip_asof.get(),None),('reference','Unique book asset reference','',None),('name','Asset / component name','',None),('category','Schedule II category','Manual / specific Schedule II category',list(fa.CLASSES)),('months','Reviewed useful life months','',None),('residual','Residual INR','0',None),('ppe','PPE ledger','1030',None),('accum','Accumulated depreciation ledger','1050',None),('expense','Book depreciation expense ledger','4570',None),('override_basis','Technical / override basis','',None),('basis','Ready-for-use / capitalization certificate basis','',None)]
        def save(s,v,r):
            allocations={}
            for row in csv.DictReader(io.StringIO(text.get('1.0','end'))):
                if row['cost_id'] in allocations:raise ValueError('Duplicate cost allocation row.')
                allocations[row['cost_id']]=row['amount']
            return cwip.commission(s,p['id'],v['date'],allocations,dict(v,months=int(v['months'])),v['basis'],r)
        win,body,f=self._cwip_form('Commission project into PPE',specs,save)
        ttk.Label(body,text='Allocate cost_id,amount CSV. Edit to commission only eligible ready components; leave unready costs in CWIP. Depreciation begins at actual put-to-use, never the purchase date. Tax-block additions require separate B17 review.',wraplength=950).pack(anchor='w')
        text=tk.Text(body,height=8);text.pack(fill='x');text.insert('1.0','cost_id,amount\n'+''.join(c['id']+','+cwip.format_money(cwip._remaining(self.state,c,self.cwip_asof.get()))+'\n' for c in cwip.data(self.state)['costs'] if c['project']==p['id'] and cwip._remaining(self.state,c,self.cwip_asof.get())>0))

    def cwip_reverse(self):
        if not self.cwip_event_table.selection():raise ValueError('Select a project event first; cost-source reversals are available in Vouchers after reversing dependent events.')
        e=self.cwip_event_rows[self.cwip_event_table.selection()[0]]
        on=simpledialog.askstring('Project reversal','Exact dated reversal date YYYY-MM-DD:',initialvalue=self.cwip_asof.get(),parent=self)
        if on:self._cwip_preview('Review project reversal',lambda s:core.reverse(s,e[3],on))

    def export_cwip(self,kind):
        start,_=self.dates();end=self.cwip_asof.get();start=min(start,end)
        path=filedialog.asksaveasfilename(parent=self,initialfile='project-cwip.'+kind,defaultextension='.'+kind)
        if path:cwip.export(self.state,start,end,self.unit(),path,kind);self.cwip_report_end=end;self.show('CWIP & commissioning')

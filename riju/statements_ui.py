"""Accountant-reviewed financial presentation and provision desktop workflow."""
import copy
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import statements as s,financial_reports as f,core

class StatementsUI:
    def statement_page(self):
        self.note('Review applicable presentation, ledger classifications and disclosure evidence. Packs include comparatives, notes, equity movements, branch matrix and clearing proof. No certification or statutory tax rate is inferred.')
        start,end=self.dates();bar=self.bar();self.st_from=self.field(bar,'From',start,width=12);self.st_end=self.field(bar,'Through',end,width=12)
        self.button(bar,'Review presentation & notes',self.statement_setup,True);self.button(bar,'Review current tax',self.statement_tax)
        bar=self.bar();self.button(bar,'Refresh pack',self.refresh_statements)
        self.button(bar,'Statement pack Excel',lambda:self.export_statements('xlsx'));self.button(bar,'Statement pack PDF',lambda:self.export_statements('pdf'))
        self.st_holder=ttk.Frame(self.content);self.st_holder.pack(fill='both',expand=True)
        if any(p['start']==start and p['end']==end for p in self.state.get('statement_policies',[])):self.refresh_statements()
        else:ttk.Label(self.st_holder,text='Review and save the presentation for this exact period to prepare statements.').pack(anchor='w')
    def refresh_statements(self):
        packs=s.report_pack(self.state,self.st_from.get(),self.st_end.get(),self.unit());self.statement_packs=packs
        for w in self.st_holder.winfo_children():w.destroy()
        tabs=ttk.Notebook(self.st_holder);tabs.pack(fill='both',expand=True)
        for p in packs:
            body=ttk.Frame(tabs);tabs.add(body,text=p['mode']);ttk.Label(body,text=p['status']+' | '+p['note'],wraplength=1050).pack(anchor='w')
            self.table(p['columns'],f.display_rows(p),parent=body)
            ttk.Label(body,text=' | '.join(k+': '+core.rupees(v) for k,v in p['controls'].items())).pack(anchor='w')
    def export_statements(self,kind):
        self.refresh_statements();path=filedialog.asksaveasfilename(parent=self,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:(f.export_pack_xlsx if kind=='xlsx' else f.export_pdf)(self.statement_packs,path)
    def statement_setup(self):
        start,end=self.st_from.get(),self.st_end.get();old=next((p for p in reversed(self.state.get('statement_policies',[])) if p['start']==start and p['end']==end),None)
        maps=copy.deepcopy(old['mappings']) if old else s.proposal(self.state)
        for code,m in s.proposal(self.state).items():maps.setdefault(code,m)
        maps={a['code']:maps[a['code']] for a in self.state['accounts']};notes=copy.deepcopy(old['disclosures']) if old else {}
        win=tk.Toplevel(self);win.title('Review statement presentation');win.geometry('1100x820');win.transient(self)
        bar=ttk.Frame(win);bar.pack(fill='x');framework=self.field(bar,'Applicable presentation',old['framework'] if old else s.FRAMEWORKS[0],list(s.FRAMEWORKS),width=38)
        line=ttk.Frame(win);line.pack(fill='x')
        basis=self.field(line,'Legal applicability, effective standard and source review',old['basis'] if old else '',width=90)
        ttk.Label(win,text='Proposed sections need review: maturity, financial/nonfinancial nature, tax, OCI and note cross-references. Source: '+s.SOURCE,wraplength=1000).pack(anchor='w')
        tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True);ledger=ttk.Frame(tabs);disclosure=ttk.Frame(tabs);tabs.add(ledger,text='Ledger classifications');tabs.add(disclosure,text='Disclosures')
        table=self.table(('Code','Ledger','Section','Note','Basis'),[],parent=ledger,height=8)
        accounts={a['code']:a for a in self.state['accounts']}
        def refresh():
            table.delete(*table.get_children())
            for code,m in maps.items():table.insert('','end',iid=code,values=(code,accounts[code]['name'],m['section'],m['note'],m['basis']))
        refresh();edit=ttk.Frame(ledger);edit.pack(fill='x');section=self.field(edit,'Section','',sorted({v for a in s.SECTIONS.values() for v in a}),width=45);ref=self.field(edit,'Note','',width=14)
        line=ttk.Frame(ledger);line.pack(fill='x')
        why=self.field(line,'Classification evidence','',width=95)
        def selected(event=None):
            if table.selection():
                m=maps[table.selection()[0]];section.set(m['section']);ref.set(m['note']);why.set(m['basis'])
        table.bind('<<TreeviewSelect>>',selected)
        def apply():
            if not table.selection():raise ValueError('Select a ledger.')
            code=table.selection()[0]
            if section.get() not in s.SECTIONS[accounts[code]['kind']]:raise ValueError('Select a section appropriate for this ledger kind.')
            maps[code]=dict(section=section.get(),note=ref.get(),basis=why.get());refresh()
        self.button(ledger,'Apply ledger classification',apply)
        line=ttk.Frame(disclosure);line.pack(fill='x')
        title=self.field(line,'Disclosure',s.DISCLOSURES[0],list(s.DISCLOSURES),width=65);status=self.field(line,'Review status','Pending',['Pending','Reviewed','Not applicable'],width=20)
        text=tk.Text(disclosure,height=12,wrap='word');text.pack(fill='both',expand=True)
        def load(event=None):
            n=notes.get(title.get(),{});status.set(n.get('status','Pending'));text.delete('1.0','end');text.insert('1.0',n.get('text',''))
        title.trace_add('write',lambda *args:load());load()
        def applynote():
            if not text.get('1.0','end').strip():raise ValueError('Record evidence or a reason for non-applicability.')
            notes[title.get()]=dict(status=status.get(),text=text.get('1.0','end').strip());messagebox.showinfo('Disclosure retained','This disclosure is retained in the pending policy. Save reviewed presentation to persist all edits.',parent=win)
        self.button(disclosure,'Retain disclosure edit',applynote)
        line=ttk.Frame(win);line.pack(fill='x')
        clearing=self.field(line,'Inter-branch clearing ledgers (comma-separated)',','.join(old['clearing_accounts']) if old else '1130',width=50)
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(win,text='I reviewed applicability, every classification and recorded disclosure evidence; pending items remain visibly pending',variable=reviewed).pack(anchor='w')
        def save():
            values=dict(start=start,end=end,framework=framework.get(),basis=basis.get(),mappings=maps,disclosures=notes,clearing_accounts=[x.strip() for x in clearing.get().split(',')],confirmed=reviewed.get())
            self.commit(lambda state:s.save_policy(state,values));win.destroy();self.refresh_statements()
        self.button(win,'Save reviewed presentation',save,True)
    def statement_tax(self):
        branch=self.unit() if self.unit()!='ALL' else 'JP'
        specs=[('start','Period start',self.st_from.get(),None),('end','Provision date / period end',self.st_end.get(),None),('branch','Unit',branch,list(self.branches)),('expense_account','Current-tax expense ledger','4610',None),('payable_account','Reviewed current-tax liability ledger','',None),('rate','Reviewed base rate %','',None),('surcharge','Reviewed surcharge %','0',None),('cess','Reviewed cess %','0',None),('additions','Taxable additions INR','0',None),('deductions','Reviewed deductions INR','0',None),('losses','Reviewed loss utilisation INR','0',None),('basis','Effective assumptions / source evidence','',None)]
        win,body,fields=self._tax_form('Current tax provision review',specs);confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed applicability, current-tax assumptions and source evidence; deferred tax and MAT/AMT are separately reviewed',variable=confirmed).pack(anchor='w')
        def calculate():
            v={k:w.get().strip() for k,w in fields.items()};v['confirmed']=confirmed.get();return s.tax_estimate(self.state,v)
        def preview():
            p=calculate();self._service_preview('Review tax provision',lambda state:s.post_tax(state,p),win,page='Statement review')
        self.button(body,'Preview incremental provision',preview,True)
        def export(kind):
            p=calculate();pack=s.tax_pack(self.state,p);path=filedialog.asksaveasfilename(parent=win,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
            if path:(f.export_xlsx if kind=='xlsx' else f.export_pdf)(pack,path)
        self.button(body,'Tax working Excel',lambda:export('xlsx'));self.button(body,'Tax working PDF',lambda:export('pdf'))

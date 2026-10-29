from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from . import core, APP_VERSION
from .storage import Vault
from .foundation_ui import FoundationUI
from . import foundation

# Soft Indian tricolor: saffron, ivory, sage, with restrained Chakra-blue accents.
BG='#FBF9F5'; WHITE='#FFFEFC'; INK='#293B55'; GREEN='#355D49'
SAGE='#E3EEDF'; SAFFRON='#F9E5D1'; MUTED='#596878'
SAFFRON_HOVER='#F2D5B5'; SAGE_HOVER='#D1E2CB'; BLUE='#E7EDF7'; BORDER='#DCE2DC'

class App(FoundationUI,tk.Tk):
    def __init__(self,vault):
        super().__init__()
        self.vault=vault
        self._instance_guard=vault.instance_lock()
        acquired=False
        try:
            self._instance_guard.__enter__();acquired=True
            self.state=vault.load()
        except Exception:
            if acquired:self._instance_guard.__exit__(None,None,None)
            self._instance_guard=None
            super().destroy()
            raise
        self.title(f'Riju Books {APP_VERSION} · ऋजु · Offline accounting')
        self.geometry('1280x820'); self.minsize(1000,680); self.configure(bg=BG)
        style=ttk.Style(self); style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10),background=BG,foreground=INK)
        style.configure('TFrame',background=BG); style.configure('Card.TFrame',background=WHITE)
        style.configure('TLabel',background=BG); style.configure('Title.TLabel',font=('Segoe UI',25,'bold'))
        style.configure('Sub.TLabel',foreground=MUTED)
        style.configure('TButton',padding=(11,6),background=SAGE,borderwidth=0)
        style.configure('TButton',background=WHITE,bordercolor=BORDER,foreground=INK)
        style.map('TButton',background=[('pressed',SAFFRON_HOVER),('active',SAFFRON)],foreground=[('disabled',MUTED)])
        style.configure('Accent.TButton',background=SAGE,foreground=GREEN)
        style.map('Accent.TButton',background=[('pressed',SAGE_HOVER),('active',SAGE_HOVER)],foreground=[('active',GREEN)])
        style.configure('Nav.TButton',background=BG,foreground=INK,anchor='w')
        style.map('Nav.TButton',background=[('active',SAFFRON)])
        style.configure('Selected.Nav.TButton',background=SAFFRON,foreground=INK)
        style.map('Selected.Nav.TButton',background=[('active',SAFFRON_HOVER)])
        style.configure('TEntry',fieldbackground=WHITE,bordercolor=BORDER,insertcolor=INK)
        style.configure('TCombobox',fieldbackground=WHITE,background=SAGE,arrowcolor=INK,bordercolor=BORDER)
        style.map('TCombobox',fieldbackground=[('readonly',WHITE)],selectbackground=[('readonly',BLUE)],selectforeground=[('readonly',INK)])
        style.configure('TCheckbutton',background=BG)
        style.map('TCheckbutton',background=[('active',BG)])
        style.configure('Treeview',background=WHITE,fieldbackground=WHITE,rowheight=31,borderwidth=0)
        style.configure('Treeview.Heading',background=SAGE,padding=8,font=('Segoe UI',10,'bold'))
        style.map('Treeview',background=[('selected',BLUE)],foreground=[('selected',INK)])
        ribbon=tk.Frame(self,bg=BG);ribbon.pack(fill='x')
        for color in (SAFFRON,WHITE,SAGE):tk.Frame(ribbon,bg=color,height=3).pack(fill='x')
        header=ttk.Frame(self,padding=(24,18)); header.pack(fill='x')
        ttk.Label(header,text='ऋजु  RIJU BOOKS',font=('Segoe UI',19,'bold')).pack(side='left')
        ttk.Label(header,text='  /  Clear books. Thoughtful decisions.',style='Sub.TLabel').pack(side='left',padx=15)
        self.branch=tk.StringVar(value='All operating units')
        self.branch_names={'All operating units':'ALL',**{v:k for k,v in self.branches.items()}}
        select=ttk.Combobox(header,textvariable=self.branch,values=list(self.branch_names),state='readonly',width=23)
        self.branch_select=select
        select.pack(side='right'); select.bind('<<ComboboxSelected>>',lambda e:self.show(self.current))
        self.year=tk.StringVar(value=str(core.financial_year(date.today().isoformat())))
        fy=ttk.Combobox(header,textvariable=self.year,values=[str(i) for i in range(2000,date.today().year+3)],state='readonly',width=7)
        self.year_select=fy
        self.refresh_masters()
        fy.pack(side='right',padx=12); fy.bind('<<ComboboxSelected>>',lambda e:self.show(self.current))
        self.status=tk.StringVar()
        ttk.Label(self,textvariable=self.status,padding=(24,9),background=SAFFRON).pack(side='bottom',fill='x')
        body=ttk.Frame(self); body.pack(fill='both',expand=True)
        nav=ttk.Frame(body,padding=(16,20),width=210); nav.pack(side='left',fill='y'); nav.pack_propagate(False)
        self.pages={'Overview':self.overview,'Journal studio':self.studio,'Sales receipt':self.sales_receipt,'Vouchers':self.vouchers,
                    'Chart of accounts':self.accounts,'Setup & periods':self.setup,'Saved drafts':self.saved_drafts,'Financial reports':self.reports,
                    'Import queue':self.imports,'Bank reconciliation':self.banking,
                    'Assets & depreciation':self.assets,'Settings & backup':self.settings,'Change history':self.history}
        self.nav_buttons={}
        for name in self.pages:
            b=ttk.Button(nav,text=name,style='Nav.TButton',command=lambda n=name:self.show(n))
            b.pack(fill='x',pady=2);self.nav_buttons[name]=b
        ttk.Label(nav,text='ONE ENTITY · BRANCH BOOKS\nOffline · No external AI calls',style='Sub.TLabel',wraplength=175).pack(side='bottom',pady=8)
        workspace=ttk.Frame(body);workspace.pack(side='left',fill='both',expand=True)
        self.page_canvas=tk.Canvas(workspace,bg=BG,highlightthickness=0)
        page_scroll=ttk.Scrollbar(workspace,orient='vertical',command=self.page_canvas.yview)
        page_xscroll=ttk.Scrollbar(workspace,orient='horizontal',command=self.page_canvas.xview)
        self.page_canvas.configure(yscrollcommand=page_scroll.set,xscrollcommand=page_xscroll.set)
        workspace.rowconfigure(0,weight=1);workspace.columnconfigure(0,weight=1)
        self.page_canvas.grid(row=0,column=0,sticky='nsew');page_scroll.grid(row=0,column=1,sticky='ns');page_xscroll.grid(row=1,column=0,sticky='ew')
        self.content=ttk.Frame(self.page_canvas,padding=(20,14,26,20))
        self.content_window=self.page_canvas.create_window((0,0),window=self.content,anchor='nw')
        def resize(event=None):
            self.page_canvas.itemconfigure(self.content_window,width=max(self.page_canvas.winfo_width(),self.content.winfo_reqwidth()))
            self.page_canvas.configure(scrollregion=self.page_canvas.bbox('all'))
        self.content.bind('<Configure>',resize);self.page_canvas.bind('<Configure>',resize)
        def wheel(event):
            if str(event.widget).startswith(str(self.content)) and event.widget.winfo_class() not in ('Text','Treeview','TCombobox'):
                self.page_canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        self.bind_all('<MouseWheel>',wheel)

        self.current='Overview'; self.show(self.current)
        self.after(1500,self.daily_backup)
    def destroy(self):
        guard=getattr(self,'_instance_guard',None)
        if guard is not None:
            self._instance_guard=None;guard.__exit__(None,None,None)
        super().destroy()
    def daily_backup(self):
        folder=self.state['settings'].get('backup_dir')
        if folder:
            try:
                existing=list(Path(folder).glob('Riju-'+date.today().strftime('%Y%m%d')+'-*')) if Path(folder).is_dir() else []
                if not existing:
                    if not self.vault.path.exists(): self.vault.save(self.state)
                    self.vault.backup(folder)
                self.status.set('Daily backup available · '+folder)
            except Exception as e: self.status.set('BACKUP PENDING · '+str(e))
        self.after(60*60*1000,self.daily_backup)
    def commit(self,action):
        candidate=copy.deepcopy(self.state)
        result=action(candidate)
        self.vault.save(candidate)
        self.state=candidate
        self.refresh_masters()
        return result
    def guarded(self,fn):
        try: return fn()
        except Exception as e: messagebox.showerror('Please review',str(e),parent=self)
    def show(self,name):
        self.current=name
        for page,button in self.nav_buttons.items():button.configure(style='Selected.Nav.TButton' if page==name else 'Nav.TButton')
        for w in self.content.winfo_children(): w.destroy()
        self.status.set(('DEVELOPMENT DEMO · unencrypted disposable data' if self.vault.demo else 'Windows-protected local vault · No application password')+'  |  '+str(len(self.state['vouchers']))+' posted vouchers')
        ttk.Label(self.content,text=name,style='Title.TLabel').pack(anchor='w',pady=(0,7))
        if self.vault.migration_pending:
            ttk.Label(self.content,text='UPGRADE PENDING · Choose your external backup folder in Settings & backup before saving changes. Original books are unchanged.',wraplength=950,padding=8,background=SAFFRON).pack(fill='x')
        self.pages[name]()
        self.page_canvas.yview_moveto(0);self.page_canvas.xview_moveto(0)
    def note(self,text): ttk.Label(self.content,text=text,style='Sub.TLabel',wraplength=950).pack(anchor='w',pady=(0,14))
    def bar(self):
        f=ttk.Frame(self.content); f.pack(fill='x',pady=8); return f
    def button(self,parent,text,fn,accent=False):
        b=ttk.Button(parent,text=text,command=lambda:self.guarded(fn),style='Accent.TButton' if accent else 'TButton'); b.pack(side='left',padx=(0,8)); return b
    def table(self,columns,rows,parent=None,height=14):
        frame=ttk.Frame(parent or self.content); frame.pack(fill='both',expand=True,pady=6)
        t=ttk.Treeview(frame,columns=columns,show='headings',height=height,selectmode='browse')
        for c in columns: t.heading(c,text=c); t.column(c,width=140,minwidth=65,stretch=True)
        sy=ttk.Scrollbar(frame,orient='vertical',command=t.yview); sx=ttk.Scrollbar(frame,orient='horizontal',command=t.xview)
        t.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        t.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns'); sx.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
        for row in rows: t.insert('', 'end', values=row)
        return t
    def unit(self): return self.branch_names[self.branch.get()]
    def dates(self): return core.fy_bounds(int(self.year.get()))
    def account_name(self,code): return next((a['name'] for a in self.state['accounts'] if a['code']==code),code)
    def field(self,parent,label,default='',values=None,width=28):
        f=ttk.Frame(parent); f.pack(side='left',padx=(0,12),pady=5)
        ttk.Label(f,text=label).pack(anchor='w')
        var=tk.StringVar(value=default)
        w=ttk.Combobox(f,textvariable=var,values=values,state='readonly',width=width) if values else ttk.Entry(f,textvariable=var,width=width)
        w.pack(fill='x',pady=5); return var
    def overview(self):
        self.note('One entity. Three perspectives. Your books stay on this computer.')
        start,end=self.dates(); b=core.balances(self.state,end,self.unit(),start); allb=core.balances(self.state,end,self.unit())
        revenue=-sum(b[a['code']] for a in self.state['accounts'] if a['kind']=='Revenue')
        expense=sum(b[a['code']] for a in self.state['accounts'] if a['kind']=='Expense')
        cards=ttk.Frame(self.content); cards.pack(fill='x',pady=14)
        for (title,val),color in zip([('Operating revenue',revenue),('Operating expenses',expense),('Surplus / (deficit)',revenue-expense),('Cash & bank',allb['1000']+allb['1010'])],(SAFFRON,WHITE,SAGE,BLUE)):
            f=tk.Frame(cards,bg=color,padx=18,pady=22); f.pack(side='left',fill='both',expand=True,padx=(0,10))
            tk.Label(f,text=title,bg=color,fg=INK,font=('Segoe UI',10)).pack(anchor='w')
            tk.Label(f,text=core.rupees(val),bg=color,fg=INK,font=('Segoe UI',19,'bold')).pack(anchor='w',pady=(12,0))
        ttk.Label(self.content,text='Operating unit snapshot',font=('Segoe UI',15,'bold')).pack(anchor='w',pady=(20,8))
        rows=[]
        for code,name in self.branches.items():
            bb=core.balances(self.state,end,code,start)
            rev=-sum(bb[a['code']] for a in self.state['accounts'] if a['kind']=='Revenue')
            exp=sum(bb[a['code']] for a in self.state['accounts'] if a['kind']=='Expense')
            rows.append((name,self.state['branches'][code]['status'],core.rupees(rev),core.rupees(exp),core.rupees(rev-exp)))
        self.table(('Operating unit','Status','Revenue','Expenses','Result'),rows,height=5)
        ttk.Label(self.content,text='Start with opening balances or describe a transaction in Journal studio.\nTax rates are starter values: review applicability and effective dates before use.',background=SAFFRON,padding=16).pack(fill='x',pady=12)
    def studio(self):
        self.note('Describe a supported payment or receipt. Review every account before posting. Unknown treatments require manual entry; no LLM is bundled.')
        top=self.bar()
        self.jdate=self.field(top,'Transaction date',date.today().isoformat(),width=13)
        names=list(self.branches.values()); chosen=self.branch.get() if self.unit()!='ALL' else names[0]
        self.jbranch=self.field(top,'Operating unit',chosen,names,width=22)
        self.jopening=tk.BooleanVar(); ttk.Checkbutton(top,text='Opening balances',variable=self.jopening).pack(side='left',padx=12,pady=20)
        details=self.bar()
        self.jtype=self.field(details,'Voucher type','Journal',list(foundation.VOUCHER_TYPES),width=13)
        self.jreference=self.field(details,'Invoice / receipt reference (optional)','',width=28)
        self.jpayee=self.field(details,'Party / description (optional)','',width=28)
        banks=['From journal lines']+[a['code']+' · '+a['name'] for a in self.state['accounts'] if self.state['account_details'].get(a['code'],{}).get('group')=='Cash and bank' and self.state['account_details'][a['code']]['active']]
        self.jbank=self.field(self.bar(),'Cash / bank reference (optional)',banks[0],banks,width=35)
        self.draft_id=None
        self.narration=tk.Text(self.content,height=3,font=('Segoe UI',12),bg=WHITE,fg=INK,relief='solid',borderwidth=1,padx=12,pady=12)
        self.narration.pack(fill='x',pady=10)
        ttk.Label(self.content,text='Example: Patient purchased medicines in cash INR1291  •  Paid ₹5,000 rent by bank',style='Sub.TLabel').pack(anchor='w')
        self.draft=[]
        actions=self.bar(); self.button(actions,'Prepare offline draft',self.prepare,True); self.button(actions,'Add manual line',self.add_line)
        self.button(actions,'Edit selected line',self.edit_line)
        self.button(actions,'Remove selected line',self.remove_line)
        self.button(actions,'Save draft',self.save_current_draft)
        self.drafttable=self.table(('Account','Ledger','Operating unit','Department','Debit','Credit'),[],height=5)
        bottom=self.bar(); self.balance_label=ttk.Label(bottom,text='No draft prepared'); self.balance_label.pack(side='left',expand=True,anchor='w')
        self.button(bottom,'Review & post voucher',self.post_draft,True)
    def refresh_draft(self):
        self.drafttable.delete(*self.drafttable.get_children())
        for l in self.draft: self.drafttable.insert('','end',values=(l['account'],self.account_name(l['account']),self.branches[l['branch']],l.get('cost_center',''),core.rupees(l['debit']),core.rupees(l['credit'])))
        dr=sum(l['debit'] for l in self.draft); cr=sum(l['credit'] for l in self.draft)
        self.balance_label.configure(text=f'Debits {core.rupees(dr)}   ·   Credits {core.rupees(cr)}   ·   Difference {core.rupees(dr-cr)}')
    def prepare(self):
        text=self.narration.get('1.0','end').strip(); branch=self.branch_names[self.jbranch.get()]
        lines=core.parse_transaction(text,branch,self.jdate.get(),self.state)
        self.draft=lines; self.refresh_draft()
    def edit_line(self):
        if not self.drafttable.selection():raise ValueError('Select a journal line to edit.')
        self.add_line(self.drafttable.index(self.drafttable.selection()[0]))
    def add_line(self,index=None):
        dialog=tk.Toplevel(self); dialog.title('Add journal line'); dialog.geometry('740x290'); dialog.transient(self); dialog.grab_set()
        f=ttk.Frame(dialog,padding=18); f.pack(fill='both',expand=True)
        row=ttk.Frame(f); row.pack(fill='x')
        options=[a['code']+' · '+a['name'] for a in self.state['accounts'] if self.state['account_details'].get(a['code'],{}).get('active',True)]
        old=self.draft[index] if index is not None else None
        if old and not any(o.startswith(old['account']+' · ') for o in options):options.append(old['account']+' · '+self.account_name(old['account']))
        acc=self.field(row,'Ledger',options[0],options,width=34)
        unit=self.field(row,'Operating unit',self.jbranch.get(),list(self.branches.values()),width=20)
        row2=ttk.Frame(f); row2.pack(fill='x'); side=self.field(row2,'Side','Debit',['Debit','Credit'],width=10); amount=self.field(row2,'Amount (₹)','',width=15)
        row3=ttk.Frame(f);row3.pack(fill='x')
        department=self.field(row3,'Department (optional; revenue/expense only)','',['']+self.state['settings']['departments'],width=36)
        if old:
            department.set(old.get('cost_center',''))
            acc.set(old['account']+' · '+self.account_name(old['account']));unit.set(self.branches[old['branch']])
            side.set('Debit' if old['debit'] else 'Credit');amount.set(str((old['debit'] or old['credit'])/100))
        def add():
            n=core.money(amount.get())
            if n<=0: raise ValueError('Amount must be positive.')
            line={'account':acc.get().split(' · ')[0],'branch':self.branch_names[unit.get()],'debit':n if side.get()=='Debit' else 0,'credit':n if side.get()=='Credit' else 0}
            if department.get():line['cost_center']=department.get()
            if index is None:self.draft.append(line)
            else:self.draft[index]=line
            self.refresh_draft(); dialog.destroy()
        self.button(row2,'Add line',add,True)
    def remove_line(self):
        selected=self.drafttable.selection()
        if selected: self.draft.pop(self.drafttable.index(selected[0])); self.refresh_draft()
    def post_draft(self):
        text=self.narration.get('1.0','end').strip()
        # Validate on a copy before asking for review.
        core.post(copy.deepcopy(self.state),self.jdate.get(),text,self.draft,self.jopening.get(),metadata=self.journal_metadata())
        if not messagebox.askyesno('Approve journal',f'Post this reviewed journal dated {self.jdate.get()}?\n\n{text}\n\nPosted entries can only be corrected by reversal.',parent=self): return
        def action(s):
            if self.draft_id:
                foundation.save_draft(s,self.jdate.get(),text,self.draft,self.journal_metadata(),self.draft_id,self.jopening.get())
                return foundation.post_draft(s,self.draft_id)
            return core.post(s,self.jdate.get(),text,self.draft,self.jopening.get(),metadata=self.journal_metadata())
        v=self.commit(action)
        messagebox.showinfo('Posted',v['id'],parent=self); self.show('Vouchers')
    def sales_receipt(self):
        from .revenue import MODES, receipt_lines
        self.note('Split a receipt across any of the 15 hospital collection categories and cash, card, UPI or other. Treatment payments received are earned revenue; Other source remains in clearing. No GST split is inferred.')
        top=self.bar(); day=self.field(top,'Date',date.today().isoformat(),width=13)
        unit=self.field(top,'Operating unit',self.branch.get() if self.unit()!='ALL' else next(iter(self.branches.values())),list(self.branches.values()),width=22)
        narration=self.field(top,'Receipt / narration','Daily sales receipt',width=36)
        grid=ttk.Frame(self.content);grid.pack(fill='x',pady=10)
        values={}
        for i,(key,label,code,name,pattern) in enumerate(MODES):
            box=ttk.Frame(grid,padding=(0,4,16,4));box.grid(row=i//3,column=i%3,sticky='ew')
            grid.columnconfigure(i%3,weight=1)
            ttk.Label(box,text=label.strip()).pack(anchor='w')
            var=tk.StringVar(value='0');values[key]=var
            ttk.Entry(box,textvariable=var,width=22).pack(fill='x',pady=4)
        ttk.Label(self.content,text='Payment methods · amounts in rupees',font=('Segoe UI',13,'bold')).pack(anchor='w',pady=12)
        bar=self.bar();payments={}
        for key,label in [('cash','Cash'),('card','Card'),('upi','UPI'),('other','Other source')]:payments[key]=self.field(bar,label,'0',width=16)
        def prepare():
            branch=self.branch_names[unit.get()];date.fromisoformat(day.get())
            lines=receipt_lines(self.state,branch,{k:core.money(v.get()) for k,v in values.items()},{k:core.money(v.get()) for k,v in payments.items()})
            draft_date=day.get();draft_unit=unit.get();text=narration.get().strip()
            if not text:raise ValueError('Enter a receipt narration.')
            self.show('Journal studio');self.jdate.set(draft_date);self.jbranch.set(draft_unit)
            self.narration.insert('1.0',text);self.draft=lines;self.refresh_draft()
        self.button(self.bar(),'Prepare compound journal for review',prepare,True)

    def vouchers(self):
        self.note('Posted entries are retained. Select a voucher to view its lines or create a reversal.')
        start,end=self.dates()
        vs=[v for v in self.state['vouchers'] if start<=v['date']<=end and (self.unit()=='ALL' or any(l['branch']==self.unit() for l in v['lines']))]
        t=self.table(('Voucher','Date','Narration','Total debits','Type'),[(v['id'],v['date'],v['narration'],core.rupees(sum(l['debit'] for l in v['lines'])),'Opening' if v.get('opening') else 'Reversal' if v.get('reverses') else 'Journal') for v in reversed(vs)])
        def selected():
            if not t.selection(): raise ValueError('Select a voucher.')
            return next(v for v in vs if v['id']==t.item(t.selection()[0])['values'][0])
        def view():
            v=selected(); messagebox.showinfo(v['id'],'\n'.join(f"{self.branches[l['branch']]} | {l['account']} {self.account_name(l['account'])} | Dr {core.rupees(l['debit'])} Cr {core.rupees(l['credit'])}" for l in v['lines']),parent=self)
        def rev():
            v=selected(); day=simpledialog.askstring('Reversal date','YYYY-MM-DD',initialvalue=date.today().isoformat(),parent=self)
            if day and messagebox.askyesno('Confirm reversal','Reverse '+v['id']+'?',parent=self):
                self.commit(lambda s:core.reverse(s,v['id'],day)); self.show('Vouchers')
        bar=self.bar(); self.button(bar,'View lines',view); self.button(bar,'Reverse selected voucher',rev)
    def reports(self):
        self.note('Financial working statements. Final statutory formats and disclosures need accountant review; these are not certified Schedule III statements.')
        bar=self.bar(); report=self.field(bar,'Report','Trial balance',['Trial balance','Profit and loss','Balance sheet','Comparative P&L','Comparative balance sheet','Branch matrix','General ledger'],width=21)
        start,end=self.dates(); fromdate=self.field(bar,'From',start,width=12); todate=self.field(bar,'Through',end,width=12)
        holder=ttk.Frame(self.content); holder.pack(fill='both',expand=True)
        result={'table':None}
        def render():
            date.fromisoformat(fromdate.get()); date.fromisoformat(todate.get())
            if fromdate.get()>todate.get(): raise ValueError('From date must precede end date.')
            for w in holder.winfo_children(): w.destroy()
            mode=report.get(); b=core.balances(self.state,todate.get(),self.unit()); movement=core.balances(self.state,todate.get(),self.unit(),fromdate.get())
            cols=('Code','Ledger','Debit','Credit'); rows=[]
            if mode in ('Comparative P&L','Comparative balance sheet'):
                from calendar import monthrange
                def previous(day):
                    d=date.fromisoformat(day);y=d.year-1
                    return date(y,d.month,min(d.day,monthrange(y,d.month)[1])).isoformat()
                oldfrom,oldto=previous(fromdate.get()),previous(todate.get())
                pl=mode=='Comparative P&L'
                prior=core.balances(self.state,oldto,self.unit(),oldfrom if pl else None)
                now=movement if pl else b
                cols=('Code','Ledger','Current period','Previous year','Change')
                for a in self.state['accounts']:
                    if (a['kind'] in ('Revenue','Expense'))!=pl:continue
                    sign=-1 if a['kind'] in ('Revenue','Liability','Equity') else 1
                    n,o=sign*now[a['code']],sign*prior[a['code']]
                    rows.append((a['code'],a['name'],core.rupees(n),core.rupees(o),core.rupees(n-o)))
                if not pl:
                    current_result=-sum(now[a['code']] for a in self.state['accounts'] if a['kind'] in ('Revenue','Expense'))
                    prior_result=-sum(prior[a['code']] for a in self.state['accounts'] if a['kind'] in ('Revenue','Expense'))
                    rows.append(('—','Unclosed accumulated result',core.rupees(current_result),core.rupees(prior_result),core.rupees(current_result-prior_result)))
            elif mode=='General ledger':
                cols=('Date','Voucher','Unit','Account','Narration','Debit','Credit')
                for v in sorted(self.state['vouchers'],key=lambda v:(v['date'],v['id'])):
                    if not fromdate.get()<=v['date']<=todate.get(): continue
                    for l in v['lines']:
                        if self.unit()=='ALL' or l['branch']==self.unit(): rows.append((v['date'],v['id'],self.branches[l['branch']],l['account']+' '+self.account_name(l['account']),v['narration'],core.rupees(l['debit']),core.rupees(l['credit'])))
            elif mode=='Branch matrix':
                cols=('Account','Classification',*self.branches.values(),'Entity total')
                units={u:core.balances(self.state,todate.get(),u) for u in self.branches}
                for a in self.state['accounts']:
                    values=[units[u][a['code']] for u in self.branches]
                    rows.append((a['code']+' '+a['name'],a['kind'],*[core.rupees(n) for n in values],core.rupees(sum(values))))
            else:
                source=movement if mode=='Profit and loss' else b
                for a in self.state['accounts']:
                    if mode=='Profit and loss' and a['kind'] not in ('Revenue','Expense'): continue
                    if mode=='Balance sheet' and a['kind'] in ('Revenue','Expense'): continue
                    value=source[a['code']]; rows.append((a['code'],a['name'],core.rupees(max(value,0)),core.rupees(max(-value,0))))
                if mode=='Balance sheet':
                    earnings=-sum(b[a['code']] for a in self.state['accounts'] if a['kind'] in ('Revenue','Expense'))
                    rows.append(('—','Unclosed accumulated result',core.rupees(max(-earnings,0)),core.rupees(max(earnings,0))))
                if mode=='Profit and loss':
                    profit=-sum(movement[a['code']] for a in self.state['accounts'] if a['kind'] in ('Revenue','Expense'))
                    rows.append(('','Profit / (loss)',core.rupees(max(-profit,0)),core.rupees(max(profit,0))))
                if mode=='Trial balance': rows.append(('','Control difference',core.rupees(sum(b.values())),''))
            result['table']=self.table(cols,rows,parent=holder)
        def export():
            t=result['table']; path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],parent=self)
            if path:
                with open(path,'w',newline='',encoding='utf-8-sig') as f:
                    w=csv.writer(f); w.writerow(t['columns']); w.writerows(t.item(i)['values'] for i in t.get_children())
                messagebox.showinfo('Exported','Report exported. This CSV is unencrypted; store it securely.',parent=self)
        self.button(bar,'Refresh',render,True); self.button(self.bar(),'Export report CSV',export); render()
    def imports(self):
        self.note('Upload the hospital daily-sales XLSX or journal CSV into a local review queue. Select the operating unit before uploading. Every report is checked before posting; Gmail connection remains pending.')
        bar=self.bar()
        def upload():
            path=filedialog.askopenfilename(filetypes=[('CSV','*.csv')],parent=self)
            if not path: return
            raw=Path(path).read_bytes(); digest=hashlib.sha256(raw).hexdigest()
            if any(q['digest']==digest for q in self.state['queue']): raise ValueError('This file is already in the queue.')
            rows=core.read_csv(raw.decode('utf-8-sig'),'journals')
            # Validate every row before staging; no partial imports.
            for row in rows:
                core.post(copy.deepcopy(self.state),row['date'],row['narration'],self.import_lines(row))
            def action(s):
                s['queue'].append({'id':digest[:12],'digest':digest,'filename':Path(path).name,'rows':rows,'status':'PENDING_REVIEW'})
                core.add_audit(s,'IMPORT_STAGED',{'digest':digest,'rows':len(rows)})
            self.commit(action); self.show('Import queue')
        self.button(bar,'Upload journal CSV',upload)
        salesbranch=self.field(bar,'Sales report operating unit',self.branch.get() if self.unit()!='ALL' else next(iter(self.branches.values())),list(self.branches.values()),width=21)
        def upload_sales():
            from .sales_import import stage_sales
            path=filedialog.askopenfilename(filetypes=[('Daily sales Excel','*.xlsx')],parent=self)
            if not path:return
            raw=Path(path).read_bytes();branch=self.branch_names[salesbranch.get()]
            q=self.commit(lambda state:stage_sales(state,raw,Path(path).name,branch))
            total=sum(r['amount'] for r in q['rows'])
            messagebox.showinfo('Report staged',f'{len(q["rows"])} receipts · {core.rupees(total)} · {self.branches[branch]}\nReview service and payment lines, then approve the file. Nothing has been posted yet.',parent=self)
            self.show('Import queue')
        self.button(bar,'Upload daily sales XLSX',upload_sales,True)
        def template():
            path=filedialog.asksaveasfilename(initialfile='riju-journal-template.csv',defaultextension='.csv',parent=self)
            if path: Path(path).write_text('date,narration,branch,debit_account,credit_account,amount\n2026-04-01,Capital introduced,JP,1010,3000,100000\n',encoding='utf-8')
        self.button(bar,'Download CSV template',template)
        t=self.table(('ID','Filename','Rows','Status'),[(q['id'],q['filename'],len(q['rows']),q['status']) for q in self.state['queue']])
        def selected():
            if not t.selection(): raise ValueError('Select an import file.')
            return self.state['queue'][t.index(t.selection()[0])]
        def review():
            q=selected(); dialog=tk.Toplevel(self); dialog.title('Review '+q['filename']); dialog.geometry('1050x600')
            if q.get('kind')=='daily_sales':
                from .revenue import MODES, receipt_lines
                totals={key:sum(r['revenues'].get(key,0) for r in q['rows']) for key,*_ in MODES}
                summary='  |  '.join(label.strip()+': '+core.rupees(totals[key]) for key,label,*_ in MODES if totals[key])
                ttk.Label(dialog,text=summary,wraplength=1000,padding=10).pack(fill='x')
                if q.get('warnings'):ttk.Label(dialog,text='\n'.join(q['warnings'][:3]),wraplength=1000,padding=10).pack(fill='x')
                rows=[]
                for r in q['rows']:
                    for l in receipt_lines(self.state,r['branch'],r['revenues'],r['payments'],q['treatment_policy'],q['other_policy']):
                        rows.append((r['date'],r['source_row'],r['receipt'],self.branches[r['branch']],l['account']+' '+self.account_name(l['account']),core.rupees(l['debit']),core.rupees(l['credit'])))
                self.table(('Date','Source row','Receipt','Unit','Ledger','Debit','Credit'),rows,parent=dialog)
            else:
                self.table(('Date','Narration','Branch','Debit account','Credit account','Amount'),[(r['date'],r['narration'],r['branch'],r['debit_account'],r['credit_account'],core.rupees(r['amount'])) for r in q['rows']],parent=dialog)
        def approve():
            q=selected()
            if q['status']!='PENDING_REVIEW': raise ValueError('Only pending files can be posted.')
            if not messagebox.askyesno('Approve import',f'Have you reviewed all {len(q["rows"])} rows? Post them together?',parent=self): return
            def action(s):
                if q.get('kind')=='daily_sales':
                    from .sales_import import approve_sales
                    approve_sales(s,q['id']);return
                item=next(x for x in s['queue'] if x['id']==q['id'])
                for row in item['rows']: core.post(s,row['date'],row['narration'],self.import_lines(row))
                item['status']='PROCESSED'
            self.commit(action); self.show('Import queue')
        bar=self.bar(); self.button(bar,'Review rows',review); self.button(bar,'Approve & post entire file',approve,True)
    def import_lines(self,row):
        return [{'account':row['debit_account'],'branch':row['branch'],'debit':row['amount'],'credit':0},
                {'account':row['credit_account'],'branch':row['branch'],'debit':0,'credit':row['amount']}]
    def banking(self):
        self.note('UPI/card receipts: match one or several sales days to a net bank deposit. Fee differences require explicit review. Set Bengaluru holidays before matching.')
        bar=self.bar(); bankbranch=self.field(bar,'Operating unit',self.branch.get() if self.unit()!='ALL' else next(iter(self.branches.values())),list(self.branches.values()),width=20)
        def upload():
            path=filedialog.askopenfilename(filetypes=[('CSV','*.csv')],parent=self)
            if not path:return
            raw=Path(path).read_bytes(); rows=core.read_csv(raw.decode('utf-8-sig'),'bank')
            branch=self.branch_names[bankbranch.get()]
            def action(s):
                for r in rows:
                    key=hashlib.sha256(json.dumps([branch,r['date'],r['reference'],r['narration'],r['amount']],sort_keys=True).encode()).hexdigest()[:20]
                    if any(b['id']==key for b in s['bank_lines']): continue
                    s['bank_lines'].append(dict(r,id=key,branch=branch,status='UNMATCHED'))
                core.add_audit(s,'BANK_IMPORT',{'filename':Path(path).name,'rows':len(rows),'branch':branch})
            self.commit(action); self.show('Bank reconciliation')
        self.button(bar,'Import bank deposits CSV',upload,True)
        def template():
            path=filedialog.asksaveasfilename(initialfile='riju-bank-template.csv',defaultextension='.csv',parent=self)
            if path: Path(path).write_text('date,narration,amount,reference\n2026-04-02,UPI SETTLEMENT -AII125,11880,UTR123\n',encoding='utf-8')
        self.button(bar,'CSV template',template)
        banks=[b for b in self.state['bank_lines'] if self.unit()=='ALL' or self.unit()==b['branch']]
        t=self.table(('ID','Date','Unit','Narration','Amount','Status'),[(b['id'],b['date'],self.branches[b['branch']],b['narration'],core.rupees(b['amount']),b['status']) for b in banks],height=9)
        def match():
            if not t.selection(): raise ValueError('Select a bank deposit.')
            bank=next(b for b in banks if b['id']==t.item(t.selection()[0])['values'][0])
            if bank['status']=='MATCHED': raise ValueError('This deposit is already matched.')
            suggestions=core.settlement_matches(self.state,bank,bank['branch'])
            if not suggestions: raise ValueError('No eligible clearing batch found within 0–1 business day. Review dates, holidays and gross/fee amounts manually.')
            dialog=tk.Toplevel(self); dialog.title('Review settlement candidates'); dialog.geometry('1000x450'); dialog.transient(self)
            ttk.Label(dialog,text='Candidates are suggestions. Confirm sales dates, fees, GST and reference before posting.',padding=12).pack(anchor='w')
            st=self.table(('Candidate','Clearing account','Gross receipts','Bank deposit','Proposed fee','Sales vouchers'),[(i,s['account'],core.rupees(s['gross']),core.rupees(bank['amount']),core.rupees(s['fee']),', '.join(s['vouchers'])) for i,s in enumerate(suggestions)],parent=dialog,height=7)
            def accept():
                if not st.selection(): raise ValueError('Select a candidate.')
                chosen=suggestions[int(st.item(st.selection()[0])['values'][0])]
                if not messagebox.askyesno('Approve settlement','Confirm the difference is a processing fee with no separately claimable GST?\nThis posts bank / fee debits against the clearing account.',parent=dialog): return
                branch=bank['branch']; lines=[{'account':'1010','branch':branch,'debit':bank['amount'],'credit':0},{'account':chosen['account'],'branch':branch,'debit':0,'credit':chosen['gross']}]
                if chosen['fee']:lines.append({'account':'4560','branch':branch,'debit':chosen['fee'],'credit':0})
                def action(s):
                    v=core.post(s,bank['date'],'Settlement '+bank['reference']+' '+bank['narration'],lines)
                    next(b for b in s['bank_lines'] if b['id']==bank['id'])['status']='MATCHED'
                    s['matches'].append(dict(chosen,bank_id=bank['id'],posting=v['id']))
                self.commit(action); dialog.destroy(); self.show('Bank reconciliation')
            f=ttk.Frame(dialog,padding=10); f.pack(fill='x'); self.button(f,'Approve selected settlement',accept,True)
        self.button(self.bar(),'Find clearing settlement matches',match,True)
        ttk.Label(self.content,text='Current scope: incoming UPI/card settlement matching. Cash deposits, bank debits, general BRS, OFX and Excel imports require further implementation.',wraplength=900,style='Sub.TLabel').pack(anchor='w',pady=12)
    def assets(self):
        self.note('Register assets and calculate draft book depreciation. Tax rates and useful lives require your review. No depreciation is posted automatically.')
        self.table(('Asset','Unit','Acquired','Cost','Residual','Life (months)','Tax WDV %'),[(a['name'],self.branches[a['branch']],a['date'],core.rupees(a['cost']),core.rupees(a['residual']),a['life'],a['tax_rate']) for a in self.state['assets']],height=7)
        bar=self.bar(); name=self.field(bar,'Asset name','',width=23); branch=self.field(bar,'Unit',next(iter(self.branches.values())),list(self.branches.values()),width=20); day=self.field(bar,'Acquired','',width=12)
        bar2=self.bar(); cost=self.field(bar2,'Cost (₹)','',width=13); residual=self.field(bar2,'Residual (₹)','0',width=13); life=self.field(bar2,'Life (months)','60',width=12); tax=self.field(bar2,'Tax WDV %','15',width=12)
        def register():
            date.fromisoformat(day.get()); c=core.money(cost.get()); r=core.money(residual.get()); months=int(life.get()); rate=float(tax.get())
            book,taxvalue=core.depreciation(c,r,months,rate)
            if not name.get().strip():raise ValueError('Enter the asset name.')
            def action(s):
                item={'name':name.get().strip(),'branch':self.branch_names[branch.get()],'date':day.get(),'cost':c,'residual':r,'life':months,'tax_rate':rate}
                s['assets'].append(item); core.add_audit(s,'ASSET_REGISTERED',item)
            self.commit(action); messagebox.showinfo('Registered',f'Full-year illustration only:\nBook SLM: {core.rupees(book)}\nTax WDV: {core.rupees(taxvalue)}\n\nTax block pooling, additions/disposals and the 180-day rule are not yet implemented. Do not use this estimate as a tax depreciation schedule.',parent=self); self.show('Assets & depreciation')
        self.button(self.bar(),'Register asset',register,True)
        ttk.Label(self.content,text='Asset registration does not post an acquisition voucher. Post the purchase separately in Journal studio. Full Companies Act and Income-tax schedules are pending.',wraplength=900,style='Sub.TLabel').pack(anchor='w',pady=15)
    def settings(self):
        self.note('No app password. Windows protects the live vault. Backups currently require the same Windows account; portable recovery is pending.')
        bar=self.bar(); entity=self.field(bar,'Legal entity name',self.state['settings']['entity'],width=42); locked=self.field(bar,'Lock through (YYYY-MM-DD)',self.state['locked_through'],width=22)
        ttk.Label(self.content,text='Bengaluru banking holidays — comma-separated YYYY-MM-DD dates. Sundays and 2nd/4th Saturdays are built in.',style='Sub.TLabel',wraplength=900).pack(anchor='w',pady=10)
        holiday=tk.Text(self.content,height=3,bg=WHITE,font=('Segoe UI',10)); holiday.pack(fill='x'); holiday.insert('1.0',', '.join(self.state['holidays']))
        ttk.Label(self.content,text='Editable tax rule reference — starter values only, not validated legal advice. Manual journals do not automatically apply these rates.',style='Sub.TLabel',wraplength=900).pack(anchor='w',pady=10)
        rule_fields=[]
        for rule in self.state['settings']['tax_rules']:
            row=self.bar()
            section=self.field(row,'TDS section',rule['section'],width=12)
            rate=self.field(row,'Rate (%)',rule['rate'],width=12)
            effective=self.field(row,'Effective from',rule['effective'],width=15)
            rule_fields.append((section,rate,effective))
        def save():
            if not entity.get().strip(): raise ValueError('Entity name is required.')
            lock=locked.get().strip()
            if lock: date.fromisoformat(lock)
            if self.state['locked_through'] and lock<self.state['locked_through']: raise ValueError('Existing period locks cannot be moved backwards in this version.')
            holidays=[h.strip() for h in holiday.get('1.0','end').split(',') if h.strip()]
            for h in holidays: date.fromisoformat(h)
            taxrules=[{'section':section.get().strip(),'rate':rate.get().strip(),'effective':effective.get().strip()} for section,rate,effective in rule_fields]
            for r in taxrules:
                if not r['section'] or not 0<=float(r['rate'])<=100: raise ValueError('Tax rate must be between 0 and 100.')
                date.fromisoformat(r['effective'])
            def action(s):
                s['settings']['entity']=entity.get().strip(); s['locked_through']=lock; s['holidays']=sorted(set(holidays)); s['settings']['tax_rules']=taxrules
                core.add_audit(s,'SETTINGS',{'entity':entity.get().strip(),'locked_through':lock,'holidays':holidays,'tax_rules':taxrules})
            self.commit(action); messagebox.showinfo('Saved','Settings saved locally.',parent=self)
        bar=self.bar(); self.button(bar,'Save settings',save,True)
        def choose():
            folder=filedialog.askdirectory(title='Choose a folder on your external drive',parent=self)
            if folder:
                def action(s):s['settings']['backup_dir']=folder; core.add_audit(s,'BACKUP_FOLDER',{'path':folder})
                self.commit(action); self.show('Settings & backup')
        def backup():
            folder=self.state['settings']['backup_dir']
            if not folder:raise ValueError('Select your external backup folder first.')
            messagebox.showinfo('Backup verified',str(self.vault.backup(folder)),parent=self)
        self.button(bar,'Choose backup folder',choose); self.button(bar,'Back up now',backup)
        ttk.Label(self.content,text='External backup: '+(self.state['settings']['backup_dir'] or 'Not configured — choose your external drive'),wraplength=900).pack(anchor='w',pady=8)
        def restore():
            path=filedialog.askopenfilename(filetypes=[('Riju vault','*.riju'),('Demo JSON','*.json')],parent=self)
            if not path:return
            Vault(path,demo=self.vault.demo).load()
            if not messagebox.askyesno('Restore backup','Replace the active books with this backup? A safety copy of the active vault will be written to the selected external backup folder first.',parent=self):return
            folder=self.state['settings']['backup_dir']
            if not folder:raise ValueError('Configure the external backup folder first.')
            self.state=self.vault.restore(path,folder);self.refresh_masters();self.show('Overview')
        self.button(self.bar(),'Restore backup',restore)
    def history(self):
        self.note('Local hash-chained change history for traceability. This is not a certified statutory audit trail or protection against a fully compromised Windows account.')
        core.verify_audit(self.state)
        self.table(('Sequence','Timestamp (UTC)','Action','Hash'),[(a['sequence'],a['timestamp'],a['action'],a['hash']) for a in reversed(self.state['audit'])])

def main():
    parser=argparse.ArgumentParser(description='Riju Books offline Windows accounting')
    parser.add_argument('--demo',action='store_true',help='Unencrypted disposable development vault; never use real financial information.')
    parser.add_argument('--data',help='Optional vault path')
    parser.add_argument('--self-test-output',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.self_test_output:
        from .selftest import run
        raise SystemExit(0 if run(args.self_test_output) else 1)
    try:
        vault=Vault(args.data,args.demo); app=App(vault); app.mainloop()
    except Exception as e:
        root=tk.Tk(); root.withdraw(); messagebox.showerror('Riju Books could not start',str(e)); root.destroy(); raise

if __name__=='__main__': main()

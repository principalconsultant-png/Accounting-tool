"""Monthly colour matrix and reviewed report inputs/mappings under Financial reports."""
from calendar import monthrange
from datetime import date,timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import business_pulse as pulse,business_pulse_exports as exports,core,foundation
from .date_picker import today

class BusinessPulseUI:
    def business_pulse(self):
        old=getattr(self,'pulse_window',None)
        if old is not None and old.winfo_exists():old.lift();return
        win=tk.Toplevel(self);self.pulse_window=win;win.title(pulse.TITLE);sw,sh=win.winfo_screenwidth(),win.winfo_screenheight();win.geometry(f'{int(sw*.96)}x{int(sh*.92)}');win.transient(self)
        shell=ttk.Frame(win,padding=12);shell.pack(fill='both',expand=True)
        title=ttk.Frame(shell);title.pack(fill='x');ttk.Label(title,text='BUSINESS PULSE',font=('Segoe UI',23,'bold'),foreground=pulse.PALETTE[0]).pack(side='left');ttk.Label(title,text='Monthly Performance',font=('Segoe UI',14),foreground='#60788B').pack(side='left',padx=16)
        bar=ttk.Frame(shell);bar.pack(fill='x',pady=7);self.pulse_year=self.field(bar,'Financial year starts',self.year.get(),[str(y) for y in range(2020,today().year+2)],width=12)
        first=today().replace(day=1);previous=first-timedelta(days=1);fy=int(self.year.get());through=min(previous,date(fy+1,3,31));through=max(through,date(fy,4,1))
        self.pulse_through=self.field(bar,'Through',through.isoformat(),width=13);units={'All operating units':'ALL',**{name:code for code,name in foundation.branches(self.state).items()}};self.pulse_units=units;selected=next(k for k,v in units.items() if v==self.unit());self.pulse_scope=self.field(bar,'Scope',selected,list(units),width=23);self.pulse_scale=self.field(bar,'Money display','INR', ['INR','INR thousands','INR lakh'],width=17)
        self.button(bar,'Refresh',self.refresh_pulse,True)
        bar=ttk.Frame(shell);bar.pack(fill='x');self.button(bar,'Review ledger mappings',self.pulse_mapping);self.button(bar,'Monthly counts / review',self.pulse_month);self.button(bar,'Upload monthly inputs',self.pulse_import_inputs)
        for ext in ('xlsx','csv'):self.button(bar,'Input template '+ext.upper(),lambda ext=ext:self.pulse_template(ext))
        for ext in ('xlsx','pdf'):self.button(bar,'Export '+ext.upper(),lambda ext=ext:self.pulse_export(ext),ext=='pdf')
        self.pulse_status=ttk.Label(shell,text='',wraplength=1150,padding=(0,7));self.pulse_status.pack(fill='x')
        legend=ttk.Frame(shell);legend.pack(fill='x',pady=3)
        for label,b in [('Q1 highest',0),('Q2 upper-middle',1),('Q3 lower-middle',2),('Q4 lowest',3),('N/A / unavailable',None),('Short / flat history',-1)]:tk.Label(legend,text=label,bg=pulse.colour(b),fg='white' if b==0 else pulse.INK,font=('Segoe UI',9),padx=10,pady=5).pack(side='left',padx=(0,5))
        ttk.Label(shell,text='Each row uses its own observed history through that month. Colours show levels, not good/bad. Receipt counts are the agreed patient-visit proxy.',wraplength=1150).pack(anchor='w',pady=5)
        frame=ttk.Frame(shell);frame.pack(fill='both',expand=True);canvas=tk.Canvas(frame,highlightthickness=0,bg='white');ys=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview);xs=ttk.Scrollbar(frame,orient='horizontal',command=canvas.xview);canvas.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);ys.pack(side='right',fill='y');xs.pack(side='bottom',fill='x');canvas.pack(fill='both',expand=True);self.pulse_grid=ttk.Frame(canvas);canvas.create_window((0,0),window=self.pulse_grid,anchor='nw');self.pulse_grid.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        self.pulse_note=ttk.Label(shell,text='',wraplength=1150,padding=(0,7));self.pulse_note.pack(fill='x');self.refresh_pulse()
    def refresh_pulse(self):
        if not getattr(self,'pulse_window',None) or not self.pulse_window.winfo_exists():return
        pack=pulse.snapshot(self.state,int(self.pulse_year.get()),self.pulse_through.get(),self.pulse_units[self.pulse_scope.get()],self.pulse_scale.get());self.pulse_snapshot=pack
        for w in self.pulse_grid.winfo_children():w.destroy()
        self.pulse_status.configure(text=pack['entity']+' | FY '+str(pack['year'])+'–'+str(pack['year']+1)+' | '+pack['scope']+' | Through '+pack['through']+' | Amounts '+pack['scale']+'; ARPP INR; counts #\n'+('DRAFT: metric mappings not reviewed. ' if not pack['policy']['reviewed'] else '')+'Months with no posted data/future dates are N/A. Provisional months have not been marked complete.')
        from datetime import datetime
        def cell(row,col,text,bg,fg=pulse.INK,bold=False,width=10,span=1):
            label=tk.Label(self.pulse_grid,text=text,bg=bg,fg=fg,font=('Segoe UI',9,'bold' if bold else 'normal'),width=width,anchor='w' if col==0 else 'center',padx=5,pady=7,wraplength=220 if col==0 else 90,relief='flat',borderwidth=1);label.grid(row=row,column=col,columnspan=span,sticky='nsew',padx=1,pady=1);return label
        cell(0,0,'CRITICAL BUSINESS METRICS',pulse.PALETTE[0],'white',True,29)
        for i,m in enumerate(pack['months'],1):cell(0,i,datetime.strptime(m,'%Y-%m').strftime('%b %y'),pulse.PALETTE[0],'white',True)
        cell(1,0,'Month coverage','#EEF2F6',width=29)
        for i,c in enumerate(pack['coverage'],1):cell(1,i,c,'#EEF2F6',width=10)
        current=2;group=None
        for r in pack['rows']:
            if r['group']!=group:group=r['group'];cell(current,0,group.upper(),'#DEE7F0',bold=True,width=29,span=13);current+=1
            label=r['label']+(' · '+pack['scale'] if r['unit']=='money' else ' · INR' if r['unit']=='ratio' else ' · #');cell(current,0,label,'#F4F6F8',bold=True,width=29)
            for i,value in enumerate(r['values']):
                b=r['bands'][i];label=cell(current,i+1,pulse.display(value,r['unit'],pack['scale']),pulse.colour(b),'white' if b==0 else pulse.INK)
                label.bind('<Button-1>',lambda e,r=r,i=i:self.pulse_detail(r,i))
            current+=1
        self.pulse_note.configure(text=' | '.join(pack['warnings'][:3])+'\nClick a metric cell for source/definition details. Petty-cash disbursements may overlap salary and other payments; these rows are not an additive expense total.')
    def pulse_detail(self,row,index):
        p=self.pulse_snapshot;month=p['months'][index];d=next((d for d in p['details'] if d['month']==month and (d['metric']==row['label'] or row['key']=='petty' and d['metric']=='Petty cash expenses')),None)
        text=month+' | '+row['label']+'\nValue: '+pulse.display(row['values'][index],row['unit'],p['scale'])+'\nCoverage: '+p['coverage'][index]
        if d:text+='\nSource: '+d['source']+'\nVoucher(s): '+(', '.join(d['vouchers']) or 'No linked journal / supplied monthly input')+'\nReview basis: '+d['review_basis']
        if row['key']=='arpp':text+='\nFormula: selected revenue divided by visits; visits use a supplied override or posted receipt-count proxy. Zero/missing visits gives N/A.'
        messagebox.showinfo('Business Pulse — metric detail',text,parent=self.pulse_window)
    def pulse_mapping(self):
        p=pulse.policy(self.state);win=tk.Toplevel(self.pulse_window);win.title('Business Pulse — review metric definitions');win.geometry('1100x790');ttk.Label(win,text='Select genuine ledger sources. Salary/OT are CASH PAID against expense/payroll-liability accounts; compliance is accrued expense. General Employee benefits/Administration accounts can mix unrelated costs: use dedicated ledgers. Empty mappings remain N/A.',wraplength=1050,padding=10).pack(fill='x')
        holder=ttk.Frame(win);holder.pack(fill='both',expand=True);boxes={}
        accounts={a['code']:a for a in self.state['accounts']}
        for key,title in [('revenue_accounts','Revenue earned / ARPP numerator'),('salary_accounts','Salary disbursed'),('ot_accounts','Staff overtime paid'),('compliance_accounts','Compliance expense')]:
            frame=ttk.Frame(holder);frame.pack(side='left',fill='both',expand=True,padx=5);ttk.Label(frame,text=title,wraplength=240).pack(anchor='w');box=tk.Listbox(frame,selectmode='multiple',exportselection=False,height=21,width=28);scroll=ttk.Scrollbar(frame,command=box.yview);box.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');box.pack(fill='both',expand=True);codes=[]
            for a in self.state['accounts']:
                kind=a['kind'];group=self.state['account_details'][a['code']]['group'];allowed=kind=='Revenue' if key=='revenue_accounts' else kind=='Expense' if key=='compliance_accounts' else kind=='Expense' or kind=='Liability' and group=='Other liabilities'
                if allowed:
                    i=len(codes);codes.append(a['code']);box.insert('end',a['code']+' '+a['name'])
                    if a['code'] in p[key]:box.selection_set(i)
            boxes[key]=(box,codes)
        bar=ttk.Frame(win);bar.pack(fill='x');mode=self.field(bar,'Petty cash definition',p['petty_mode'],['All petty-cash disbursements','Operating expenses only'],width=31);basis=self.field(bar,'Metric mapping review basis',p['basis'],width=65);confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(win,text='I reviewed account classifications, separate salary/OT sources and the petty cash definition.',variable=confirmed).pack(anchor='w')
        def save():
            v={key:[codes[i] for i in box.curselection()] for key,(box,codes) in boxes.items()};v.update(petty_mode=mode.get(),basis=basis.get(),reviewed=confirmed.get());self.commit(lambda s:pulse.save_policy(s,v));win.destroy();self.refresh_pulse()
        self.button(win,'Save reviewed metric mappings',save,True)
    def pulse_month(self):
        month=self.pulse_through.get()[:7];scope=self.pulse_units[self.pulse_scope.get()];old=pulse.observations(self.state).get((month,scope),{});units=['ALL',*foundation.branches(self.state)]
        win,body,fields=self._tax_form('Business Pulse — monthly counts',[('month','Reporting month YYYY-MM',month,None),('branch','Operating unit / ALL',scope,units),('visits','Actual visit override (blank = receipt proxy)','' if old.get('visits') is None else str(old['visits']),None),('new_patients','New patients (blank = unavailable)','' if old.get('new_patients') is None else str(old['new_patients']),None),('basis','Monthly source / review basis',old.get('basis',''),None)])
        reviewed=tk.BooleanVar(value=old.get('books_reviewed',False));ttk.Checkbutton(body,text='Books for this entire month/unit are complete and reviewed',variable=reviewed).pack(anchor='w');ttk.Label(body,text='Each save replaces this month/unit observation and retains history. ALL observations are separate from branch observations. Blank means unavailable, not zero. No financial journal is posted.',wraplength=1000).pack(anchor='w',pady=8)
        def save():
            v={k:w.get() for k,w in fields.items()};v['books_reviewed']=reviewed.get();self.commit(lambda s:pulse.save_month(s,v));win.destroy();self.refresh_pulse()
        self.button(body,'Save monthly observations',save,True)
    def pulse_template(self,kind):
        path=filedialog.asksaveasfilename(parent=self.pulse_window,initialfile='Yathartha-Business-Pulse-Monthly-Inputs.'+kind,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:pulse.input_template(path)
    def pulse_import_inputs(self):
        path=filedialog.askopenfilename(parent=self.pulse_window,filetypes=[('Monthly observations','*.csv *.xlsx')])
        if not path:return
        plan=pulse.preview_inputs(self.state,Path(path).read_bytes(),Path(path).name);win=tk.Toplevel(self.pulse_window);win.title('Review Business Pulse monthly inputs');win.geometry('1120x620');ttk.Label(win,text='NEW/UPDATE rows save operational observations only. Existing monthly values are replaced with an audit revision; no financial journals. Select reviewed rows.',wraplength=1060,padding=8).pack(anchor='w');table=self.table(('Row','Month','Unit','Visits override','New patients','Status','Reason'),[],parent=win,height=12);table.configure(selectmode='extended')
        for i,r in enumerate(plan['rows']):
            v=r.get('values',r['raw']);table.insert('','end',iid=str(i),values=(r['source_row'],v.get('month',''),v.get('branch',''),v.get('visits',''),v.get('new_patients',''),r['status'],r['error']))
        def choose():table.selection_set([str(i) for i,r in enumerate(plan['rows']) if r['status']!='INVALID'])
        def save():
            self.commit(lambda s:pulse.save_inputs(s,plan,[int(i) for i in table.selection()]));win.destroy();self.refresh_pulse()
        self.button(win,'Select valid new/update rows',choose);self.button(win,'Save reviewed monthly inputs',save,True)
    def pulse_export(self,kind):
        self.refresh_pulse();p=self.pulse_snapshot;path=filedialog.asksaveasfilename(parent=self.pulse_window,initialfile='Yathartha-Business-Pulse-'+p['through']+'.'+kind,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:(exports.export_xlsx if kind=='xlsx' else exports.export_pdf)(p,path);messagebox.showinfo('Business Pulse exported',str(path),parent=self.pulse_window)

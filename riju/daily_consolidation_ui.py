"""Daily management table, saved relational database and explicit coverage gaps."""
import copy
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import daily_consolidation as daily,financial_reports as reports,foundation,core
from .date_picker import today

SECTIONS=('Daily table','What is left out','Source gaps','Source drilldown')
class DailyConsolidationUI:
    def daily_register(self):
        old=getattr(self,'daily_window',None)
        if old is not None and old.winfo_exists():old.lift();return
        win=tk.Toplevel(self);self.daily_window=win;win.title(daily.TITLE);win.geometry(f'{int(win.winfo_screenwidth()*.96)}x{int(win.winfo_screenheight()*.92)}');win.transient(self)
        body=ttk.Frame(win,padding=10);body.pack(fill='both',expand=True)
        ttk.Label(body,text='DAILY BUSINESS REGISTER',font=('Segoe UI',20,'bold'),foreground='#154C8A').pack(anchor='w')
        fy=int(self.year.get());meta=self.state['settings'].get(daily.STORE,{}).get('metadata',{});start=meta.get('start',f'{fy}-04-01');end=meta.get('end',min(max(today(),date(fy,4,1)),date(fy+1,3,31)).isoformat())
        bar=ttk.Frame(body);bar.pack(fill='x');self.daily_start=self.field(bar,'From',start,width=12);self.daily_end=self.field(bar,'Through',end,width=12);self.daily_unit=self.field(bar,'Operating unit','ALL',['ALL',*foundation.branches(self.state)],width=12);self.daily_section=self.field(bar,'View','Daily table',list(SECTIONS),width=23)
        self.button(bar,'Build / refresh database',self.daily_build,True);self.button(bar,'Load saved table',self.daily_load)
        bar=ttk.Frame(body);bar.pack(fill='x',pady=5);self.button(bar,'Excel — table and support',lambda:self.daily_export('xlsx'));self.button(bar,'PDF — current view',lambda:self.daily_export('pdf'));self.button(bar,'CSV — current view',lambda:self.daily_export('csv'));self.button(bar,'Export full SQLite database',lambda:self.daily_export('sqlite'))
        self.daily_status=ttk.Label(body,text='Build the database from posted books. Pending/unmatched uploads appear under Source gaps. The saved database is protected with the book and included in backups.',wraplength=1130,padding=7);self.daily_status.pack(fill='x')
        self.daily_holder=ttk.Frame(body);self.daily_holder.pack(fill='both',expand=True)
        self.daily_note=ttk.Label(body,text='',wraplength=1130,padding=7);self.daily_note.pack(fill='x')
        self.daily_section.trace_add('write',lambda *args:self.guarded(self.daily_load));self.daily_unit.trace_add('write',lambda *args:self.guarded(self.daily_load))
        if daily.STORE in self.state['settings']:self.daily_load()
    def daily_build(self):
        # The database has its own audited refresh event; do not duplicate its binary
        # payload in CHANGE_SET. Vault checkpoints still cover the entire saved state.
        candidate=copy.deepcopy(self.state);daily.refresh(candidate,self.daily_start.get(),self.daily_end.get());self.vault.save(candidate);self.state=candidate;self.refresh_masters();self.daily_load()
    def daily_load(self):
        if daily.STORE not in self.state['settings']:return
        p=daily.pack(self.state,self.daily_start.get(),self.daily_end.get(),self.daily_unit.get(),self.daily_section.get());self.daily_pack=p
        for w in self.daily_holder.winfo_children():w.destroy()
        rows=[[core.rupees(v) if i in p['money_columns'] and v is not None else v for i,v in enumerate(row)] for row in p['rows']]
        self.daily_table=self.table(p['columns'],rows,parent=self.daily_holder,height=15)
        for col in p['columns']:
            if col in ('Reason','Basis'):self.daily_table.column(col,width=520,minwidth=260)
        self.daily_status.configure(text=('STALE: books changed since this database was built. Refresh before using these figures. ' if p['stale'] else 'Saved database agrees with the current book sources. ')+str(len(rows))+' row(s) | '+p['scope']+' | '+p['start']+' to '+p['end']+' | Built '+p['prepared'],foreground='#9C261B' if p['stale'] else '#154C8A')
        self.daily_note.configure(text=p['note'])
    def daily_export(self,kind):
        self.daily_load()
        if not hasattr(self,'daily_pack'):raise ValueError('Build the database first.')
        if self.daily_pack['stale']:raise ValueError('Refresh the database before exporting current figures.')
        path=filedialog.asksaveasfilename(parent=self.daily_window,initialfile='Yathartha-Daily-Business-Register.'+kind,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if not path:return
        if kind=='xlsx':
            from openpyxl import Workbook
            wb=Workbook();wb.remove(wb.active)
            for section in SECTIONS:reports._worksheet(wb,daily.pack(self.state,self.daily_start.get(),self.daily_end.get(),self.daily_unit.get(),section),section)
            wb.save(path);wb.close()
        elif kind=='sqlite':
            db,meta,stale=daily.saved(self.state)
            try:Path(path).write_bytes(db.serialize())
            finally:db.close()
        else:(reports.export_pdf if kind=='pdf' else reports.export_csv)(self.daily_pack,path)
        messagebox.showinfo('Daily register exported',str(path)+('\nAll units and supporting history through the saved Through date; this exported SQLite file contains financial data outside the encrypted book.' if kind=='sqlite' else ''),parent=self.daily_window)

"""Desktop history and integrity review; financial records are read-only here."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from . import history as h


class HistoryUI:
    def history(self):
        self.note('Review recorded changes and source links. Dates below filter when work was performed in India, independently of the global accounting-year/branch selectors. Legacy events may lack user or before/after details. This is a local history, without statutory certification.')
        bar=self.bar();self.history_start=self.field(bar,'Work date from (optional)','',width=15);self.history_end=self.field(bar,'Through (optional)','',width=15)
        self.history_action=self.field(bar,'Action','All actions',['All actions']+sorted({r['action'] for r in self.state['audit']}),width=25)
        bar=self.bar();self.history_query=self.field(bar,'Search ID, account, branch or text','',width=42)
        self.history_checkpoints=tk.BooleanVar(value=False);ttk.Checkbutton(bar,text='Show saved-state checkpoints',variable=self.history_checkpoints).pack(side='left',padx=10)
        self.button(bar,'Apply filters',self.refresh_history,True)
        bar=self.bar();self.button(bar,'Check integrity',self.check_history_integrity,True);self.button(bar,'Inspect backup file',self.inspect_history_backup)
        self.button(bar,'Trace voucher',self.trace_history_voucher)
        self.button(bar,'Export filtered CSV',lambda:self.export_history('csv'));self.button(bar,'Export filtered JSON',lambda:self.export_history('json'))
        self.history_status=ttk.Label(self.content,text='',wraplength=950);self.history_status.pack(anchor='w',pady=8)
        self.history_table=self.table(('Sequence','Time India','User','Action','Description'),[],height=10)
        self.history_table.column('Description',width=480);self.history_table.column('Sequence',width=75)
        self.history_table.bind('<<TreeviewSelect>>',lambda e:self.show_history_detail())
        ttk.Label(self.content,text='Selected event — full recorded details, including before/after where available').pack(anchor='w',pady=5)
        self.history_detail=tk.Text(self.content,height=12,wrap='word',font=('Consolas',10));self.history_detail.pack(fill='both',expand=True)
        self.refresh_history()

    def refresh_history(self):
        rows=h.entries(self.state,self.history_start.get().strip(),self.history_end.get().strip(),self.history_action.get(),self.history_query.get(),self.history_checkpoints.get())
        self.history_rows=rows;self.history_items={};self.history_table.delete(*self.history_table.get_children())
        for r in rows:
            item=self.history_table.insert('','end',values=(r['sequence'],r['timestamp_india'],r['actor'],r['action'],r['summary']));self.history_items[item]=r
        self.history_status.configure(text=str(len(rows))+' recorded event(s) in this filter. Export uses the same filter. User names identify the local OS session; legacy users are not inferred.')
        self._history_text('Select an event to inspect its recorded details.')

    def _history_text(self,text):
        self.history_detail.configure(state='normal');self.history_detail.delete('1.0','end');self.history_detail.insert('1.0',text);self.history_detail.configure(state='disabled')

    def show_history_detail(self):
        selected=self.history_table.selection()
        if selected:self._history_text(h.detail_text(self.history_items[selected[0]]))

    def _history_dialog(self,title,value):
        win=tk.Toplevel(self);win.title(title);win.geometry('1000x650');win.transient(self)
        text=tk.Text(win,wrap='word',font=('Consolas',10));scroll=ttk.Scrollbar(win,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True)
        text.insert('1.0',json.dumps(value,ensure_ascii=False,indent=2));text.configure(state='disabled')
        def export():
            path=filedialog.asksaveasfilename(parent=win,defaultextension='.json',initialfile='riju-review.json')
            if path:Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        self.button(win,'Save review JSON',export)

    def check_history_integrity(self):
        self._history_dialog('Books integrity review',h.integrity_report(self.state))

    def inspect_history_backup(self):
        path=filedialog.askopenfilename(parent=self,title='Inspect a backup without restoring',filetypes=[('Riju books','*.riju *.json')])
        if not path:return
        from .storage import Vault
        backup=Vault(path,demo=self.vault.demo).load();report=h.integrity_report(backup)
        report['filename']=Path(path).name;report['entity']=backup['settings']['entity']
        report['recovery']='This inspection did not restore or alter the active books. Restore through Settings & backup; keep the safety copy and verify the restored period/balances. DPAPI backups need the original Windows account keys.'
        self._history_dialog('Backup inspection',report)

    def trace_history_voucher(self):
        selected=self.history_table.selection();initial=''
        if selected:
            r=self.history_items[selected[0]]
            if r['action']=='POST':initial=r['payload']['id']
            elif r['action']=='DRAFT_POSTED':initial=r['payload']['voucher_id']
        vid=simpledialog.askstring('Trace voucher','Voucher ID:',initialvalue=initial,parent=self)
        if vid:self._history_dialog('Voucher source and correction history',h.trace_voucher(self.state,vid.strip()))

    def export_history(self,kind):
        # Reapply edited filter inputs before exporting, avoiding stale filter results.
        self.refresh_history()
        path=filedialog.asksaveasfilename(parent=self,initialfile='riju-change-history.'+kind,defaultextension='.'+kind)
        if path:h.export_rows(self.history_rows,path,kind);messagebox.showinfo('History exported',str(path),parent=self)


def offer_integrity_recovery(vault,error,parent):
    """Restore only after source validation, explicit confirmation and a safety copy."""
    text=str(error)
    if vault is None or vault.last_digest is None or not any(word in text.lower() for word in ('integrity','history sequence','voucher records differ')):return False
    if not messagebox.askyesno('Books integrity check failed',text+'\n\nOpen recovery from a trusted external backup? The current file must first be copied to your selected external folder. Nothing is repaired or discarded automatically.',parent=parent):return False
    path=filedialog.askopenfilename(parent=parent,title='Select trusted backup',filetypes=[('Riju books','*.riju *.json')])
    if not path:return False
    from .storage import Vault
    source=Vault(path,demo=vault.demo).load()
    report=h.integrity_report(source)
    if not report['passed']:raise ValueError('Selected backup failed integrity review: '+'; '.join(report['errors']))
    folder=filedialog.askdirectory(parent=parent,title='External folder for safety copy of current file')
    if not folder:return False
    if not messagebox.askyesno('Confirm recovery','Restore '+Path(path).name+' for '+source['settings']['entity']+'?\nThe current file is preserved in the selected external folder before replacement. Review restored balances and periods before resuming work.',parent=parent):return False
    with vault.instance_lock():vault.restore(path,folder)
    return True

"""Review findings and read-only questions with source-traced exports."""
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog,messagebox
from . import accounting_checks as checks,financial_reports as f,core

class ChecksUI:
    def accounting_check_page(self):
        self.note('Offline review checks and ledger questions. Findings never post corrections or assert legal violations. Answers show posted facts and source references; review commentary is separate.')
        start,end=self.dates();bar=self.bar();self.ck_start=self.field(bar,'From',start,width=12);self.ck_end=self.field(bar,'Through',end,width=12)
        self.button(bar,'Run checks',self.refresh_checks,True);self.button(bar,'Review thresholds',self.check_policy)
        bar=self.bar();self.button(bar,'Record finding review',self.review_finding);self.button(bar,'Checks Excel',lambda:self.export_checks('xlsx'));self.button(bar,'Checks PDF',lambda:self.export_checks('pdf'))
        self.ck_status=ttk.Label(self.content,text='',wraplength=1050);self.ck_status.pack(anchor='w');self.ck_table=self.table(('Rule','Unit','Date','INR','Status','Finding','Sources'),[],height=6)
        bar=self.bar();self.ck_question=self.field(bar,'Offline question','What is the cash balance?',width=65);self.button(bar,'Ask ledger question',self.ask_ledger,True)
        self.button(bar,'Answer Excel',lambda:self.export_answer('xlsx'));self.button(bar,'Answer PDF',lambda:self.export_answer('pdf'))
        self.ck_answer=ttk.Label(self.content,text='Examples: total expenses; rent expense; 1010 balance; compare profit; top expenses; CWIP. Period and scope come from the selectors.',wraplength=1050);self.ck_answer.pack(anchor='w');self.ck_answer_holder=ttk.Frame(self.content);self.ck_answer_holder.pack(fill='both',expand=True);self.ck_answer_packs=None
        self.refresh_checks()
    def refresh_checks(self):
        r=checks.run(self.state,self.ck_start.get(),self.ck_end.get(),self.unit());self.ck_result=r;self.ck_table.delete(*self.ck_table.get_children())
        self.ck_status.configure(text=str(len(r['alerts']))+' findings | '+r['policy']['basis']+' | '+r['note'])
        for a in r['alerts']:self.ck_table.insert('','end',iid=a['id'],values=(a['rule'],a['branch'],a['date'],core.rupees(a['amount']),a['status'],a['message'],'; '.join(a['sources'])))
    def check_policy(self):
        p=checks.policy(self.state,self.ck_end.get());specs=[('effective','Effective from',self.ck_start.get(),None),('cash_payment','Daily payee cash outflow review INR','' if p['thresholds']['cash_payment'] is None else str(p['thresholds']['cash_payment']/100),None),('cumulative_tds_base','Potential TDS booked expense review INR','' if p['thresholds']['cumulative_tds_base'] is None else str(p['thresholds']['cumulative_tds_base']/100),None),('unusual_posting','Large posting review INR','' if p['thresholds']['unusual_posting'] is None else str(p['thresholds']['unusual_posting']/100),None),('clearing_days','Collection clearing calendar days','' if p['thresholds']['clearing_days'] is None else str(p['thresholds']['clearing_days']),None),('basis','Reviewed thresholds and source basis','' if p['id']=='UNREVIEWED' else p['basis'],None)]
        win,body,fields=self._tax_form('Review accounting check thresholds',specs);ttk.Label(body,text='Blank disables a threshold; zero is an explicit threshold, not an unknown value. TDS source assessment still uses reviewed B09 rules. No legal threshold or applicability is inferred.',wraplength=850).pack(anchor='w')
        confirmed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed effective thresholds, source basis and entity scope',variable=confirmed).pack(anchor='w')
        def save():
            v={k:w.get().strip() for k,w in fields.items()};v['confirmed']=confirmed.get();self.commit(lambda s:checks.save_policy(s,v));win.destroy();self.refresh_checks()
        self.button(body,'Save reviewed thresholds',save,True)
    def review_finding(self):
        if not self.ck_table.selection():raise ValueError('Select a current finding.')
        key=self.ck_table.selection()[0];status=simpledialog.askstring('Finding review','Status: Investigating, Explained or Action required',parent=self)
        if not status:return
        note=simpledialog.askstring('Finding evidence','Source evidence / explanation. Review does not suppress or correct this finding:',parent=self)
        if note:self.commit(lambda s:checks.review(s,self.ck_result,key,status,note));self.refresh_checks()
    def export_checks(self,kind):
        self.refresh_checks();pack=checks.snapshots(self.state,self.ck_start.get(),self.ck_end.get(),self.unit());path=filedialog.asksaveasfilename(parent=self,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:(f.export_xlsx if kind=='xlsx' else f.export_pdf)(pack,path)
    def ask_ledger(self):
        try:r=checks.answer(self.state,self.ck_question.get(),self.ck_start.get(),self.ck_end.get(),self.unit())
        except ValueError:
            self.ck_answer_packs=None;self.ck_answer.configure(text='Question requires clarification; no previous answer remains selected for export.');raise
        self.ck_answer_packs=r['packs'];self.ck_answer.configure(text='Posted facts: '+r['summary']+'\nReview commentary: '+r['commentary'])
        for child in self.ck_answer_holder.winfo_children():child.destroy()
        tabs=ttk.Notebook(self.ck_answer_holder);tabs.pack(fill='both',expand=True)
        for p in r['packs']:
            body=ttk.Frame(tabs);tabs.add(body,text=p['mode']);self.table(p['columns'],f.display_rows(p),parent=body,height=5)
    def export_answer(self,kind):
        # Recalculate current selectors and question before export to avoid stale facts.
        self.ask_ledger();path=filedialog.asksaveasfilename(parent=self,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if path:(f.export_pack_xlsx if kind=='xlsx' else f.export_pdf)(self.ck_answer_packs,path)

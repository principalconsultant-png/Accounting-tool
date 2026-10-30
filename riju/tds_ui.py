"""Desktop TDS review, cumulative assessment, challan allocation and exports."""
import csv
import io
import json
from datetime import datetime
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from . import tds,tax,history,financial_reports,core


class TdsUI:
    def tds_accounting(self):
        self.note('Reviewed TDS bookkeeping for configured resident-payee sections, including 194J/194C/194I. Rates, threshold groups and categories come from Tax setup. Aggregation spans all units of the entity. Choose the actual credit/payment tax point; no legal applicability or special PAN/certificate treatment is guessed.')
        dates=self.dates()
        if getattr(self,'tds_report_year',None)!=self.year.get():self.tds_report_period=dates;self.tds_report_year=self.year.get()
        period=self.bar();self.tds_from=self.field(period,'Posting period from',self.tds_report_period[0],width=15);self.tds_through=self.field(period,'Through',self.tds_report_period[1],width=15);self.button(period,'Refresh period',self.refresh_tds_page,True)
        bar=self.bar()
        for kind,label in [('Expense','New expense + TDS'),('Existing payable','TDS on existing payable'),('Register existing deduction','Register prior TDS'),('Adjustment','Catch-up deduction'),('Challan','Record challan payment')]:self.button(bar,label,lambda kind=kind:self.new_tds(kind),kind=='Expense')
        actions=self.bar();self.button(actions,'Allocate challan tax',self.allocate_tds);self.button(actions,'Undo allocation',self.undo_tds_allocation);self.button(actions,'CIN details',self.edit_tds_challan);self.button(actions,'Void zero-tax record',self.void_tds_record)
        actions=self.bar()
        for kind in ('xlsx','pdf','json'):self.button(actions,'Export '+('Excel' if kind=='xlsx' else kind.upper()),lambda kind=kind:self.export_tds(kind))
        report=tds.report(self.state,*self.tds_report_period,self.unit());self.tds_report=report;tabs=ttk.Notebook(self.content);tabs.pack(fill='both',expand=True)
        for key,title in [('deductions','Period deductions'),('outstanding','Outstanding'),('challans','Challan reconciliation'),('section_report','Section summary'),('proof_report','Ledger proof')]:
            frame=ttk.Frame(tabs);tabs.add(frame,text=title);pack=report[key];self.table(pack['columns'],financial_reports.display_rows(pack),parent=frame,height=11)
        frame=ttk.Frame(tabs);tabs.add(frame,text='Allocation history')
        records={r['id']:r for r in self.state['tds_records']}
        self.table(('Allocation ID','Date','Deduction','Payment','Tax INR','Undo date'),[(a['id'],a['date'],records[a['document_id']]['reference'],records[a['payment_id']]['reference'],core.rupees(a['amount']),a.get('undo_date','')) for a in self.state['tds_allocations']],parent=frame,height=11)
        ttk.Label(self.content,text='Unknown TAN/PAN/CIN and manual exceptions remain visible for review; reports are working records, not a filed return. Zero-tax existing-payable records create no journal. Allocations do not post another payment. Reverse financial entries through Vouchers after undoing any dated allocations.',wraplength=1000).pack(anchor='w',pady=10)

    def new_tds(self,kind):
        today=datetime.now(history.INDIA).date().isoformat();branch=self.unit() if self.unit()!='ALL' else next(iter(self.branches))
        specs=[('date','Posting date',today,None),('branch','Operating unit',branch,list(self.branches)),('reference','Unique invoice/payment reference','',None),('narration','Narration','',None)]
        parties={};keys=[]
        if kind!='Challan':
            keys=sorted({r['key'] for r in tax.rules(self.state) if r['family']=='TDS'})
            latest={}
            for p in sorted(tax.parties(self.state),key=lambda p:(p['effective'],p.get('revision',1))):latest[p['party_id']]=p
            parties={p['name']+' · '+pid:pid for pid,p in latest.items()}
            if not keys or not parties:raise ValueError('Create a reviewed TDS rule and party in Tax setup first.')
            specs.extend([('tax_date','Credit/payment tax-point date',today,None),('rule_key','TDS rule',keys[0],keys),('party','Party',next(iter(parties)),list(parties)),('mode','Assessment','Automatic',['Automatic','Reviewed manual']),('gross','Gross expense/payable INR','0' if kind=='Adjustment' else '',None),('base','Deduction base INR','0' if kind=='Adjustment' else '',None),('counter_account','Supplier payment/payable ledger','2000',None),('account','Cost/PPE/inventory ledger','4510',None),('source_voucher','Existing source voucher ID','',None),('tds_account','TDS payable ledger (optional)','',None),('manual_tax','Manual deduction INR','0',None),('manual_target','Reviewed source liability INR (optional)','',None),('review_reason','Manual exception source/reason','',None)])
        else:specs.extend([('bank_account','Actual INR bank ledger','1010',None),('interest','Interest INR (separate charge)','0',None),('fee','Late fee INR (separate charge)','0',None),('charge_account','Interest/fee expense ledger','4580',None)])
        win,body,fields=self._tax_form('Review TDS '+kind,specs)
        resident=tk.BooleanVar(value=False)
        if kind!='Challan':ttk.Checkbutton(body,text='I reviewed resident-payee/section applicability, tax point and the deduction base (including any GST exclusion)',variable=resident).pack(anchor='w',pady=6)
        csvtext=None
        if kind=='Challan':
            ttk.Label(body,text='Tax payment rows: section,branch,year,tax — year is the liability financial-year start, not necessarily the bank-payment year. Tax amounts only; interest/fees stay separate.').pack(anchor='w')
            csvtext=tk.Text(body,height=4);csvtext.pack(fill='x');csvtext.insert('1.0','section,branch,year,tax\n194J,'+branch+','+str(core.financial_year(today))+',0\n')
        ttk.Label(body,text='Automatic catch-up uses source snapshots across all branches and matching PAN identities. Reviewed manual amounts require a reason/source; they are retained in future assessments. Existing payable avoids recording the expense twice and requires its original payable-credit voucher. Challan payments may cover several sections/units and can be allocated partially later.',wraplength=1000).pack(anchor='w',pady=8)
        preview=tk.Text(body,height=9,wrap='word',font=('Consolas',10));preview.pack(fill='both',expand=True);prepared={}
        def values():
            data={k:v.get().strip() for k,v in fields.items()}
            if kind!='Challan':data['party_id']=parties[data.pop('party')];data['resident_reviewed']=resident.get()
            else:data['rows']=list(csv.DictReader(io.StringIO(csvtext.get('1.0','end').strip())))
            return data
        def prepare():
            data=values();record=tds.prepare(self.state,kind,data);prepared.clear();prepared.update(values=data,fingerprint=history.fingerprints(self.state))
            preview.configure(state='normal');preview.delete('1.0','end');preview.insert('1.0',json.dumps(record,ensure_ascii=False,indent=2));preview.configure(state='disabled')
        def post():
            if not prepared or prepared['values']!=values() or prepared['fingerprint']!=history.fingerprints(self.state):raise ValueError('Prepare a fresh preview after changing any fields or books.')
            if messagebox.askyesno('Approve TDS entry','Have you checked the source, tax point, section, thresholds, historical catch-up and journal? No real bank instruction or return is sent.',parent=win):
                self.commit(lambda s:tds.post(s,kind,dict(prepared['values'],confirmed=True)));win.destroy();self.show('TDS accounting')
        bar=ttk.Frame(body);bar.pack(fill='x');self.button(bar,'Prepare TDS preview',prepare,True);self.button(bar,'Approve & record TDS',post)

    def _tds_choices(self,kind):
        records=[r for r in self.state['tds_records'] if (r['kind']=='Challan')==kind and (kind or r.get('withheld',0)>0)]
        return {r['reference']+' · '+r['date']+' · '+r['id']:r for r in records}

    def allocate_tds(self):
        docs=self._tds_choices(False);payments=self._tds_choices(True)
        if not docs or not payments:raise ValueError('Record a deduction and a challan payment first.')
        row_choices={p['reference']+' · '+r['section']+' / '+r['branch']+' / '+str(r['year'])+' · '+p['id']+' row '+str(i+1):(p['id'],i) for p in payments.values() for i,r in enumerate(p['rows'])}
        win,body,f=self._tax_form('Allocate challan tax',[( 'document','Deduction',next(iter(docs)),list(docs)),('payment_row','Payment tax row',next(iter(row_choices)),list(row_choices)),('amount','Tax to allocate INR','',None),('date','Allocation date',datetime.now(history.INDIA).date().isoformat(),None)])
        def save():
            d=docs[f['document'].get()];pid,index=row_choices[f['payment_row'].get()]
            if messagebox.askyesno('Confirm allocation','Link this deduction to the selected section/unit/FY tax payment? Interest/fees are excluded; no new journal is created.',parent=win):self.commit(lambda s:tds.allocate(s,d['id'],pid,index,f['amount'].get(),f['date'].get()));win.destroy();self.show('TDS accounting')
        self.button(body,'Approve allocation',save,True)

    def undo_tds_allocation(self):
        choices={a['id']:a for a in self.state['tds_allocations'] if not a.get('undo_date')}
        if not choices:raise ValueError('No active allocations.')
        win,body,f=self._tax_form('Undo dated allocation',[('id','Allocation ID',next(iter(choices)),list(choices)),('date','Undo date',datetime.now(history.INDIA).date().isoformat(),None),('reason','Reason','',None)])
        def save():self.commit(lambda s:tds.unallocate(s,f['id'].get(),f['date'].get(),f['reason'].get()));win.destroy();self.show('TDS accounting')
        self.button(body,'Undo allocation',save)

    def edit_tds_challan(self):
        choices=self._tds_choices(True)
        if not choices:raise ValueError('Record a challan payment first.')
        win,body,f=self._tax_form('CIN verification details',[('payment','Payment',next(iter(choices)),list(choices)),('bsr','BSR code (optional)','',None),('serial','Challan serial (optional)','',None),('deposit_date','Actual deposit date (optional)','',None),('reference','Verification source/reference','',None)])
        verified=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed the actual CIN/payment evidence',variable=verified).pack(anchor='w')
        def save():self.commit(lambda s:tds.challan_details(s,choices[f['payment'].get()]['id'],dict({k:v.get() for k,v in f.items() if k!='payment'},verified=verified.get())));win.destroy();self.show('TDS accounting')
        self.button(body,'Save detail revision',save,True)

    def void_tds_record(self):
        choices={r['reference']+' · '+r['id']:r for r in self.state['tds_records'] if not r.get('voucher_id') and not r.get('void_date')}
        if not choices:raise ValueError('No live zero-journal TDS records. Reverse financial vouchers instead.')
        win,body,f=self._tax_form('Void zero-tax record',[('record','Record',next(iter(choices)),list(choices)),('date','Void date',datetime.now(history.INDIA).date().isoformat(),None),('reason','Reason','',None)])
        def save():self.commit(lambda s:tds.void_record(s,choices[f['record'].get()]['id'],f['date'].get(),f['reason'].get()));win.destroy();self.show('TDS accounting')
        self.button(body,'Void with history',save)

    def refresh_tds_page(self):
        dates=(self.tds_from.get().strip(),self.tds_through.get().strip());tds.report(self.state,*dates,self.unit());self.tds_report_period=dates;self.show('TDS accounting')

    def export_tds(self,kind):
        self.refresh_tds_page()
        path=filedialog.asksaveasfilename(parent=self,initialfile='tds-working-reconciliation.'+kind,defaultextension='.'+kind)
        if path:tds.export(self.state,*self.tds_report_period,self.unit(),path,kind)

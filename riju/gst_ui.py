"""Desktop reviewed GST posting, ledger proofs and offline 2B reconciliation."""
from datetime import datetime
from pathlib import Path
import json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from . import gst,tax,history,core


class GstUI:
    def gst_accounting(self):
        self.note('Reviewed domestic forward-charge GST invoices. Preview before posting; eligible ITC is your explicit assessment. Place of supply is entered, not inferred from a customer address. Exact journal reversals appear in dated summaries. Linked credit/debit notes retain the original tax treatment. Use source-line entry for mixed rates and reviewed export/SEZ. GST cash & filing records actual cash/credit and portal preparation separately.')
        bar=self.bar();self.button(bar,'New GST invoice',self.new_gst_invoice,True);self.button(bar,'Credit / debit note',self.new_gst_note);self.button(bar,'Export working summary',self.export_gst_summary)
        self.button(bar,'Import normalized 2B',self.import_gst_2b);self.button(bar,'2B CSV template',self.gst_2b_template)
        bar=self.bar();self.button(bar,'Mixed-rate / export / SEZ invoice',self.new_multiline_gst);self.button(bar,'Source-line credit / debit note',lambda:self.new_multiline_gst(True))
        for kind in ('xlsx','pdf'):self.button(bar,'Export GST '+kind.upper(),lambda k=kind:self.export_gst_pack(k))
        start,end=self.dates();report=gst.summary(self.state,start,end,self.unit());self.gst_report=report
        self.table(('Working summary','INR'),[(k.replace('_',' ').capitalize(),core.rupees(n)) for k,n in report['totals'].items()]+[('Net GST ledger movement (not payment due)',core.rupees(report['net_movement']))],height=7)
        self.table(('Tax ledger','Actual movement INR','Unclassified/manual movement INR'),[(c,core.rupees(report['ledger_movements'][c]),core.rupees(report['unclassified'][c])) for c in gst.INPUT+gst.OUTPUT],height=4)
        ttk.Label(self.content,text='Unclassified/manual movements must be reviewed against supporting invoices; matching 2B never posts or claims credit. Net movement excludes opening balances and is not a GST return or payment calculation. Separate GST registrations need separate review.',wraplength=960).pack(anchor='w',pady=8)
        self.gst_docs=self.table(('Voucher','Date','Kind','Document type','Original invoice','Invoice','Registration','Tax base','CGST','SGST','IGST','ITC'),[(d['movement_voucher'],d['movement_date'],d['kind'],d.get('document_type','Invoice'),d.get('original_reference',''),d['reference'],d['registration'],core.rupees(d['totals']['base']),core.rupees(d['totals']['cgst']),core.rupees(d['totals']['sgst']),core.rupees(d['totals']['igst']),d['itc']) for d in report['documents']],height=5)
        bar=self.bar();self.button(bar,'Review 2B import',self.review_gst_2b);self.button(bar,'Void unused 2B import',self.void_gst_2b)
        self.gst_import_table=self.table(('ID','Period','Registration','File','Documents','Status'),[(x['id'],x['period'],x['registration'],x['filename'],len(x['rows']),x.get('status','OPEN')) for x in self.state['gst_2b_imports']],height=4)

    def new_gst_invoice(self):
        keys=sorted({r['key'] for r in tax.rules(self.state) if r['family']=='GST'})
        if not keys:raise ValueError('Create and review a GST rule in Tax setup first.')
        branches=self.branches;branch=self.unit() if self.unit()!='ALL' else next(iter(branches));unit=self.state['branches'][branch]
        registration=unit.get('gstin') or self.state['settings']['registration'].get('gstin','')
        specs=[('date','Invoice date',datetime.now(history.INDIA).date().isoformat(),None),('branch','Operating unit',branch,list(branches)),('kind','Document kind','Sale',['Sale','Purchase']),
            ('registration','Our GSTIN for this invoice',registration,None),('place_of_supply','Place-of-supply state code','',None),('counterparty_gstin','Customer/supplier GSTIN (optional B2C)','',None),
            ('reference','Invoice/reference number','',None),('rule_key','Reviewed GST rule',keys[0],keys),('amount','INR amount','',None),
            ('account','Revenue/cost ledger code','4000',None),('counter_account','Payment/control ledger code','1010',None),('itc','Purchase ITC assessment','Not applicable',['Not applicable','Eligible','Ineligible']),
            ('narration','Narration','',None)]
        win,body,fields=self._tax_form('Review GST invoice',specs)
        inclusive=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='Entered amount includes GST',variable=inclusive).pack(anchor='w',pady=5)
        ttk.Label(body,text='For purchases enter supplier GSTIN, cost/PPE/inventory ledger, credit/payment ledger and your ITC assessment. Configure branch registration/state before using a GSTIN different from the entity. Tax split is based on the supplier registration state and reviewed place of supply.',wraplength=1000).pack(anchor='w',pady=8)
        preview=tk.Text(body,height=11,wrap='word',font=('Consolas',10));preview.pack(fill='both',expand=True);approved={}
        def values():return dict({k:v.get().strip() for k,v in fields.items()},inclusive=inclusive.get())
        def prepare():
            data=values();doc=gst.plan(self.state,data)
            # Preview uses the real posting validators on a disposable copy.
            import copy
            core.post(copy.deepcopy(self.state),doc['date'],doc['narration'],doc['lines'])
            approved.clear();approved.update(values=data,doc=doc,fingerprint=history.fingerprints(self.state))
            preview.configure(state='normal');preview.delete('1.0','end');preview.insert('1.0',json.dumps(doc,ensure_ascii=False,indent=2));preview.configure(state='disabled')
        def post():
            if not approved or approved['values']!=values() or approved['fingerprint']!=history.fingerprints(self.state):raise ValueError('Prepare a fresh preview after changing any fields.')
            if messagebox.askyesno('Approve GST journal','Have you checked the invoice, rule applicability, place of supply, tax rounding and purchase ITC? This posts the displayed double-entry journal.',parent=win):
                self.commit(lambda s:gst.post(s,dict(approved['values'],confirmed=True)));win.destroy();self.show('GST accounting')
        bar=ttk.Frame(body);bar.pack(fill='x');self.button(bar,'Prepare journal preview',prepare,True);self.button(bar,'Approve & post',post)

    def export_gst_summary(self):
        path=filedialog.asksaveasfilename(parent=self,initialfile='gst-working-summary.csv',defaultextension='.csv',filetypes=[('CSV','*.csv'),('JSON','*.json')])
        if path:(gst.export_report if Path(path).suffix.lower()=='.json' else gst.export_csv)(gst.summary(self.state,*self.dates(),self.unit()),path)

    def gst_2b_template(self):
        path=filedialog.asksaveasfilename(parent=self,initialfile='gst-2b-template.csv',defaultextension='.csv')
        if path:Path(path).write_text('supplier_gstin,invoice,date,taxable,cgst,sgst,igst,itc_available,document_type,original_invoice,original_date\n',encoding='utf-8')

    def import_gst_2b(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Normalized 2B CSV/XLSX','*.csv *.xlsx')])
        if not path:return
        registration=simpledialog.askstring('2B registration','Recipient GSTIN for this 2B file:',parent=self)
        if not registration:return
        period=simpledialog.askstring('2B period','Statement period YYYY-MM:',parent=self)
        if not period:return
        raw=Path(path).read_bytes()
        import copy
        preview=gst.import_2b(copy.deepcopy(self.state),raw,Path(path).name,registration,period)
        if messagebox.askyesno('Import 2B for review',str(len(preview['rows']))+' normalized document(s) for '+registration+' / '+period+'? No journal or ITC claim will be posted.',parent=self):
            self.commit(lambda s:gst.import_2b(s,raw,Path(path).name,registration,period));self.show('GST accounting')

    def review_gst_2b(self):
        selected=self.gst_import_table.selection()
        if not selected:raise ValueError('Select a 2B import first.')
        import_id=self.gst_import_table.item(selected[0],'values')[0];win=tk.Toplevel(self);win.title('Review 2B against books');win.geometry('1150x680');win.transient(self)
        ttk.Label(win,text='Linking is a reconciliation record, not an ITC claim. Availability N stays visible; matching does not change eligibility. Notes must match their type and original invoice. Match outstanding notes before clearing an adjusted original invoice. Reversed documents invalidate earlier links.',wraplength=1050,padding=12).pack(anchor='w')
        table=self.table(('Supplier','Type','Invoice / note','Date','Original invoice','Available','Book candidate','Match status','Book ITC'),[],parent=win,height=12);items={}
        ttk.Label(win,text='Book invoices and notes dated in the statement period absent from this imported 2B (check late reporting separately)').pack(anchor='w')
        totals_label=ttk.Label(win,text='',wraplength=1050);totals_label.pack(anchor='w')
        missing=self.table(('Book voucher','Type','Invoice / note','Date','Supplier','ITC'),[],parent=win,height=3)
        def refresh():
            table.delete(*table.get_children());items.clear();missing.delete(*missing.get_children())
            report=gst.review_2b(self.state,import_id)
            totals_label.configure(text='Signed source tax: '+', '.join(k.upper()+' '+core.rupees(report['statement_signed_totals'][k]) for k in ('cgst','sgst','igst'))+' | Credit notes subtract; invoices/debit notes add. This is not credit claimed.')
            for d in report['book_documents_without_2b']:missing.insert('','end',values=(d['voucher_id'],d.get('document_type','Invoice'),d['reference'],d['date'],d['counterparty_gstin'],d['itc']))
            for entry in report['rows']:
                row=entry['row']
                for c in entry['candidates'] or [None]:
                    item=table.insert('','end',values=(row['supplier_gstin'],row.get('document_type','Invoice'),row['invoice'],row['date'],row.get('original_invoice',''),row['itc_available'],c['voucher_id'] if c else '—',entry['status']+' / '+c['status'] if c else entry['status'],c['itc'] if c else '—'));items[item]=(row,c)
        def match():
            if not table.selection():raise ValueError('Select a candidate row.')
            row,c=items[table.selection()[0]]
            if not c:raise ValueError('No book candidate exists.')
            if messagebox.askyesno('Link reviewed 2B invoice','Confirm supplier, invoice, date, base and tax match? Source availability and book eligibility stay unchanged.',parent=win):self.commit(lambda s:gst.match_2b(s,import_id,row['id'],c['document_id']));refresh()
        def undo():
            if not table.selection():raise ValueError('Select a linked row.')
            row,_=items[table.selection()[0]];m=next((m for m in self.state['gst_2b_matches'] if m['row_id']==row['id'] and m.get('active',True)),None)
            if not m:raise ValueError('No active link for this row.')
            reason=simpledialog.askstring('Undo 2B match','Reason:',parent=win)
            if reason:self.commit(lambda s:gst.unmatch_2b(s,m['id'],reason));refresh()
        bar=ttk.Frame(win);bar.pack(fill='x');self.button(bar,'Approve exact match',match,True);self.button(bar,'Undo selected match',undo)
        def export():
            path=filedialog.asksaveasfilename(parent=win,initialfile='2b-review.csv',defaultextension='.csv',filetypes=[('CSV','*.csv'),('JSON','*.json')])
            if path:(gst.export_report if Path(path).suffix.lower()=='.json' else gst.export_2b_csv)(gst.review_2b(self.state,import_id),path)
        self.button(bar,'Export review CSV / JSON',export);refresh()

    def void_gst_2b(self):
        selected=self.gst_import_table.selection()
        if not selected:raise ValueError('Select a 2B import first.')
        import_id=self.gst_import_table.item(selected[0],'values')[0]
        reason=simpledialog.askstring('Cancel unused 2B import','Reason (undo active links first; original data stays in history):',parent=self)
        if reason:self.commit(lambda s:gst.void_2b(s,import_id,reason));self.show('GST accounting')

    def new_gst_note(self):
        originals=[d for d in self.state['gst_documents'] if not d.get('original_document_id')]
        if not originals:raise ValueError('Post the original GST invoice first.')
        choices={d['voucher_id']+' · '+d['kind']+' · '+d['reference']:d['id'] for d in originals}
        specs=[('original','Original invoice',next(iter(choices)),list(choices)),('date','Note date',datetime.now(history.INDIA).date().isoformat(),None),('document_type','Note type','Credit note',['Credit note','Debit note']),('reference','Unique note reference','',None),('amount','Adjustment base INR (excludes GST)','',None),('counter_account','Refund / balance-adjustment ledger','',None),('narration','Reason / narration','',None)]
        win,body,fields=self._tax_form('Review GST credit / debit note',specs)
        ttk.Label(body,text='Credit notes reduce the original invoice; debit notes increase it. Select the actual bank refund ledger only when money is being refunded; otherwise use the correct receivable/payable/advance control. The original branch, registration, tax treatment and ITC assessment are retained. Verify legal time limits and the actual note; commercial-only adjustments need manual review.',wraplength=1000).pack(anchor='w',pady=12)
        repay=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='Reviewed: convert already-used purchase ITC reversal to tax payable for repayment',variable=repay).pack(anchor='w')
        text=tk.Text(body,height=16,wrap='word',font=('Consolas',10));text.pack(fill='both',expand=True);reviewed={}
        def values():
            data={k:v.get().strip() for k,v in fields.items()};data['original_document_id']=choices[data.pop('original')];data.update(repay_used_itc=repay.get(),repayment_basis=data['narration']);return data
        def preview():
            data=values();doc=gst.plan_note(self.state,data)
            import copy
            core.post(copy.deepcopy(self.state),doc['date'],doc['narration'],doc['lines'])
            reviewed.clear();reviewed.update(values=data,fingerprint=history.fingerprints(self.state));text.configure(state='normal');text.delete('1.0','end');text.insert('1.0',json.dumps(doc,ensure_ascii=False,indent=2));text.configure(state='disabled')
        def post():
            if not reviewed or reviewed['values']!=values() or reviewed['fingerprint']!=history.fingerprints(self.state):raise ValueError('Prepare a fresh note preview after changing any fields.')
            if messagebox.askyesno('Approve GST note','Have you reviewed the original invoice, note amounts, tax treatment and actual refund/balance adjustment?',parent=win):
                self.commit(lambda s:gst.post_note(s,dict(reviewed['values'],confirmed=True)));win.destroy();self.show('GST accounting')
        bar=ttk.Frame(body);bar.pack(fill='x');self.button(bar,'Prepare note preview',preview,True);self.button(bar,'Approve & post note',post)

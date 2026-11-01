"""Reviewed GST invoice lines, actual cash/credit and portal source review."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog
from . import core,foundation,gst,gst_extensions as ext,gst_payments as pay,gst_portal as portal,tax,history

class GstCompletionUI:
    def new_multiline_gst(self,note=False):
        specs=[('date','Document date',self.dates()[1],None),('reference','Unique source reference','',None),('narration','Reviewed source / statutory note basis','',None),('counter_account','Actual settlement / control ledger','2000' if note else '1010',None)]
        if note:specs.extend([('original_document_id','Original multi-line invoice ID','',None),('document_type','Note type','Credit note',['Credit note','Debit note'])])
        else:specs.extend([('kind','Document kind','Sale',['Sale','Purchase']),('branch','Unit',self.unit() if self.unit()!='ALL' else 'JP',list(self.branches)),('registration','Supplying/receiving GSTIN','',None),('counterparty_gstin','Counterparty GSTIN (purchase/SEZ required)','',None),('place_of_supply','Reviewed place of supply state (96 export)','',None),('supply_type','Supply type','Domestic',['Domestic','Export under LUT','Export with IGST','SEZ under LUT','SEZ with IGST']),('country','Export destination country (e.g. US)','',None),('export_basis','LUT / export / authorized SEZ evidence','',None)])
        win,body,f=self._tax_form('Review multi-line GST '+('note' if note else 'invoice'),specs)
        ttk.Label(body,text='Source line allocations JSON. Invoice: [{"account":"4000","rule_key":"REVIEWED-RULE","amount":"100","inclusive":false,"itc":"Not applicable","description":"Service"}]. Purchase ITC is Eligible/Ineligible per line. Notes: [{"line_id":"original-source-line-id","amount":"base INR"}]. Original line IDs are in Excel/PDF/source data. All amounts INR; different rates/eligibility retain separate sources.',wraplength=1000).pack(anchor='w')
        text=tk.Text(body,height=8);text.pack(fill='x');text.insert('1.0','[]');repay=tk.BooleanVar(value=False)
        if note:ttk.Checkbutton(body,text='I reviewed converting already-used purchase ITC reversal into GST payable for actual repayment',variable=repay).pack(anchor='w')
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed actual invoice/note, place of supply, tax/ITC and export/SEZ evidence where applicable',variable=reviewed).pack(anchor='w')
        def preview():
            v={k:w.get().strip() for k,w in f.items()};v.update(items=json.loads(text.get('1.0','end')),confirmed=reviewed.get(),export_reviewed=reviewed.get(),repay_used_itc=repay.get(),repayment_basis=v['narration'])
            self._service_preview('Review GST source lines',lambda s:gst.post_note(s,v) if note else ext.post_invoice(s,v),win,page='GST accounting')
        self.button(body,'Preview GST source lines',preview,True)

    def export_gst_pack(self,kind):
        path=filedialog.asksaveasfilename(parent=self,initialfile='gst-working-pack.'+kind,defaultextension='.'+kind)
        if path:ext.export(self.state,*self.dates(),self.unit(),path,kind)

    def gst_cash_filing(self):
        self.note('GST cash/credit and filing preparation. Actual bank funding, component utilisation, legal credit order, eligibility changes and cash refunds are separately reviewed. Each unit/registration stays isolated. A reviewed preparation/entered acknowledgement is an offline record; the app never submits or verifies a government filing. Source changes flag old reviewed snapshots as stale.')
        bar=self.bar()
        for kind in ('Deposit','Cash utilisation','ITC utilisation','Cash refund'):self.button(bar,kind,lambda k=kind:self.gst_cash_action(k))
        bar=self.bar()
        for kind in ('Cash transfer','ITC reclassification','Register opening'):self.button(bar,kind,lambda k=kind:self.gst_cash_action(k))
        self.button(bar,'Review credit-order policy',self.gst_utilisation_policy);self.button(bar,'Bind existing cash controls',self.bind_gst_cash_controls);self.button(bar,'Review filing preparation',self.gst_filing_review);self.button(bar,'Import portal 2B JSON',self.import_portal_gst)
        bar=self.bar()
        for kind in ('xlsx','pdf'):self.button(bar,'Export '+kind.upper(),lambda k=kind:self.export_gst_pack(k))
        end=self.dates()[1];scopes={(d['registration'],d['branch']) for d in self.state['gst_documents']}|{(r['registration'],r['branch']) for r in pay.actions(self.state)};rows=[]
        for reg,branch in sorted(scopes):
            if self.unit() not in ('ALL',branch):continue
            pos=pay.position(self.state,reg,branch,end)
            for part in pay.PARTS:rows.append([reg,branch,part,*[core.rupees(pos[k][part]) for k in ('due','credit','cash')]])
        self.table(('Registration','Unit','Component','Classified due/(overpaid)','Available input credit','Electronic cash'),rows,height=5)
        self.table(('Date','Action','Registration','Unit','Reference','Voucher'),[(r['date'],r['kind'],r['registration'],r['branch'],r['reference'],r['voucher_id']) for r in pay.actions(self.state) if r['date']<=end and self.unit() in ('ALL',r['branch'])],height=5)
        filing=[]
        for r in self.state['gst_filing_reviews']:
            current=pay.period_fingerprint(self.state,r['registration'],r['branch'],r['period'])[0];filing.append([r['registration'],r['branch'],r['period'],r['status'],'Current' if current==r['review_fingerprint'] else 'STALE — source changed',r['acknowledgement'],r['basis']])
        self.table(('Registration','Unit','Period','Review state','Snapshot check','Manual acknowledgement','Basis'),filing,height=4)
        self.portal_rows_table=self.table(('Import ID','Source row ID','GSTIN','Period','Supplier','Type','Reference','Date','Available','Match / candidates'),[],height=5);self.portal_row_values={}
        for item in self.state['gst_portal_imports']:
            if item.get('status')=='VOID' or self.unit() not in ('ALL',item['branch']):continue
            for row in item['rcm_rows']:
                candidates=portal.rcm_candidates(self.state,item,row);status='Linked' if row['match'] and any(c['record_id']==row['match']['record_id'] and c['status']=='Exact' for c in candidates) else 'Review / '+str(len(candidates))+' candidate(s)'
                iid=self.portal_rows_table.insert('','end',values=(item['id'],row['id'],item['registration'],item['period'],row['supplier_gstin'],row['document_type'],row['invoice'],row['date'],row['itc_available'],status));self.portal_row_values[iid]=(item,row,candidates)
        bar=self.bar();self.button(bar,'Match selected RCM source',lambda:self.match_portal_rcm(False));self.button(bar,'Undo selected RCM source',lambda:self.match_portal_rcm(True))

    def gst_cash_action(self,kind):
        branch=self.unit() if self.unit()!='ALL' else 'JP';registration=self.state['branches'][branch].get('gstin','') or self.state['settings']['registration'].get('gstin','')
        specs=[('date','Actual action date',self.dates()[1],None),('branch','Unit',branch,list(self.branches)),('registration','GST registration',registration,None),('reference','Actual challan/utilisation/source reference','',None),('narration','Reviewed source / eligibility / portal evidence','',None)]
        if kind in ('Deposit','Cash refund'):specs.append(('bank_account','INR bank ledger','1010',None))
        if kind in ('Deposit','Cash refund','Cash utilisation'):specs.extend([(p,p.upper()+' actual amount INR','0',None) for p in pay.PARTS])
        if kind in ('Cash transfer','ITC utilisation'):specs.extend([('from_component','Source component','igst',list(pay.PARTS)),('to_component','Destination component','igst',list(pay.PARTS)),('amount','Actual amount INR','',None)])
        if kind=='ITC reclassification':specs.extend([('document_id','Original purchase ID','',None),('line_id','Original mixed line ID (blank uses simple invoice)','',None),('eligible_percent','Revised eligible percentage','',None)])
        if kind=='Register opening':specs.extend([('source_voucher','Original opening voucher ID','',None),('opening_input','Input opening JSON (cgst/sgst/igst INR)','{}',None),('opening_output','Output opening JSON (cgst/sgst/igst INR)','{}',None),('opening_cash','Cash opening JSON (cgst/sgst/igst INR)','{}',None)])
        win,body,f=self._tax_form('GST '+kind,specs);reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed the actual source, legal eligibility/order, registration, amount and portal evidence',variable=reviewed).pack(anchor='w',pady=8)
        def preview():
            v={k:w.get().strip() for k,w in f.items()};v.update(confirmed=reviewed.get(),eligibility_reviewed=reviewed.get())
            if not v.get('line_id'):v.pop('line_id',None)
            for key in ('opening_input','opening_output','opening_cash'):
                if key in v:v[key]=json.loads(v[key])
            self._service_preview('Review GST '+kind,lambda s:pay.post(s,kind,v),win,page='GST cash & filing')
        self.button(body,'Preview GST action',preview,True)

    def gst_filing_review(self):
        specs=[('registration','GST registration','',None),('branch','Unit',self.unit() if self.unit()!='ALL' else 'JP',list(self.branches)),('period','Tax period YYYY-MM',self.dates()[0][:7],None),('basis','Actual source / eligibility / filing review basis','',None),('acknowledgement','Actual portal acknowledgement (blank = preparation)','',None)]
        win,body,f=self._tax_form('Review filing preparation',specs);reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed this ended period and actual source/portal facts; this does not submit a return',variable=reviewed).pack(anchor='w')
        self.button(body,'Preview filing snapshot',lambda:self._service_preview('Review filing source snapshot',lambda s:pay.review_filing(s,f['registration'].get(),f['branch'].get(),f['period'].get(),f['basis'].get(),reviewed.get(),f['acknowledgement'].get()),win,page='GST cash & filing'),True)

    def import_portal_gst(self):
        path=filedialog.askopenfilename(parent=self,title='Supported GSTR-2B b2b/cdnr JSON',filetypes=[('JSON','*.json')])
        if not path:return
        specs=[('registration','Recipient GSTIN','',None),('period','Statement YYYY-MM',self.dates()[0][:7],None),('branch','Receiving unit',self.unit() if self.unit()!='ALL' else 'JP',list(self.branches)),('links','Verified note parents JSON {GSTIN|note:{invoice,date}}','{}',None)]
        win,body,f=self._tax_form('Review raw portal source',specs);self.note('Portal import never posts or claims credit. Nonempty unsupported sections/cess or ambiguous note parents fail; no source section is silently dropped.')
        raw=Path(path).read_bytes()
        self.button(body,'Preview portal source import',lambda:self._service_preview('Review portal 2B source',lambda s:portal.import_json(s,raw,Path(path).name,f['registration'].get(),f['period'].get(),f['branch'].get(),json.loads(f['links'].get())),win,page='GST cash & filing'),True)

    def match_portal_rcm(self,undo):
        if not self.portal_rows_table.selection():raise ValueError('Select a raw RCM source row.')
        item,row,candidates=self.portal_row_values[self.portal_rows_table.selection()[0]];record=row['match']['record_id'] if undo and row['match'] else candidates[0]['record_id'] if candidates else ''
        if not record:raise ValueError('No exact candidate/link is available; review source discrepancies.')
        reason=simpledialog.askstring('Review RCM source','Exact-source match/undo basis:',parent=self)
        if reason:self._service_preview('Review RCM source link',lambda s:portal.match_rcm(s,item['id'],row['id'],record,reason,undo),page='GST cash & filing')

    def bind_gst_cash_controls(self):
        specs=[('registration','GST registration','',None),*[(p,p.upper()+' existing Other assets ledger','',None) for p in pay.PARTS],('basis','Reviewed opening/control mapping basis','',None)]
        win,body,f=self._tax_form('Bind existing cash controls',specs)
        self.button(body,'Preview cash control binding',lambda:self._service_preview('Review actual cash controls',lambda s:pay.bind_cash_controls(s,f['registration'].get(),{p:f[p].get() for p in pay.PARTS},f['basis'].get(),True),win,page='GST cash & filing'),True)

    def gst_utilisation_policy(self):
        specs=[('effective','Effective credit-order date','2019-03-29',None),('igst_first','Exhaust IGST credit before other credit','Yes',['Yes','No']),('residual_order','Remaining IGST credit order','Any',['Any','CGST then SGST','SGST then CGST']),('own_first','Use own-head credit against own tax first','Yes',['Yes','No']),('basis','Governing-year statute/source review basis','',None)]
        win,body,f=self._tax_form('Review effective GST credit order',specs)
        self.button(body,'Preview credit-order policy',lambda:self._service_preview('Review credit-order policy',lambda s:pay.save_utilisation_policy(s,f['effective'].get(),f['igst_first'].get()=='Yes',f['residual_order'].get(),f['own_first'].get()=='Yes',f['basis'].get(),True),win,page='GST cash & filing'),True)

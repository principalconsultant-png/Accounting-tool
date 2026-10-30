"""Desktop RCM review stages; cash funding and tax discharge remain distinct."""
from datetime import datetime
import json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import core,tax,history,rcm


class RcmUI:
    def reverse_charge(self):
        self.note('Record domestic reverse-charge purchases only after verifying applicability. A bank challan deposit funds electronic cash; it does not discharge the liability. Record actual cash utilisation separately, then review ITC. Full-document discharge and ITC only; no auto filing or legal determination.')
        bar=self.bar()
        for stage,label in [('Purchase','RCM purchase'),('Deposit','Electronic-cash deposit'),('Discharge','Record tax discharge'),('Claim','Review ITC claim')]:self.button(bar,label,lambda stage=stage:self.new_rcm(stage),stage=='Purchase')
        self.button(bar,'Export RCM review',self.export_rcm)
        start,end=self.dates();report=rcm.report(self.state,start,end,self.unit());self.rcm_report=report
        self.rcm_table=self.table(('Voucher','Date','Stage','Registration','Branch','Reference','Base INR','CGST INR','SGST INR','IGST INR'),[(r['movement_voucher'],r['movement_date'],r['stage'],r['registration'],self.branches[r['branch']],r['reference'],core.rupees(r['amounts'].get('base',0)*r['sign']),*[core.rupees(r['amounts'][p]*r['sign']) for p in rcm.PARTS]) for r in report['records']],height=10)
        self.table(('RCM control','Ledger','Opening INR','Movement INR','Closing INR','Unclassified/manual INR'),[(name,code,core.rupees(report['opening_balances'][code]),core.rupees(report['ledger_movements'][code]),core.rupees(report['closing_balances'][code]),core.rupees(report['unclassified'][code])) for name,code in report['control_ledgers'].items()],height=7)
        self.table(('RCM purchase','Registration','Branch','Unpaid RCM tax','Pending ITC review'),[(r['reference'],r['registration'],self.branches[r['branch']],core.rupees(sum(r['tax_due'].values())),core.rupees(r['itc_pending'])) for r in report['outstanding']],height=5)
        ttk.Label(self.content,text='Input credit appears in the GST working summary only after an explicit Claim entry. RCM payable, pending review and electronic cash stay separate. Signed control movements are debit-positive; review unclassified manual movements before relying on balances. Deposit amounts must reflect actual component allocations.',wraplength=1000).pack(anchor='w',pady=12)

    def new_rcm(self,stage):
        today=datetime.now(history.INDIA).date().isoformat();branch=self.unit() if self.unit()!='ALL' else next(iter(self.branches));registration=self.state['branches'][branch].get('gstin') or self.state['settings']['registration'].get('gstin','')
        specs=[('date','Accounting/action date',today,None),('reference','Invoice / challan / utilisation reference','',None),('narration','Narration / supporting review','',None)]
        choices={r['reference']+' · '+r['voucher_id']:r['id'] for r in self.state['gst_rcm_records'] if r['stage']=='Purchase'}
        if stage in ('Claim','Discharge'):
            if not choices:raise ValueError('Record the RCM purchase first.')
            specs.append(('purchase','RCM purchase',next(iter(choices)),list(choices)))
        else:specs.extend([('branch','Operating unit',branch,list(self.branches)),('registration','Recipient GSTIN',registration,None)])
        if stage=='Purchase':
            keys=sorted({r['key'] for r in tax.rules(self.state) if r['family']=='GST'})
            if not keys:raise ValueError('Create and review the appropriate GST rate in Tax setup first.')
            specs.extend([('rule_key','Reviewed GST rate rule',keys[0],keys),('rcm_basis','Verified RCM applicability basis','',None),('supplier_name','Supplier name (required if unregistered)','',None),('supplier_gstin','Supplier GSTIN (blank if unregistered)','',None),('supplier_state','Supplier state code','',None),('place_of_supply','Reviewed place-of-supply state','',None),('amount','Purchase base INR (excludes RCM)','',None),('account','Cost / asset ledger','4590',None),('counter_account','Supplier payable / payment ledger','2000',None)])
        if stage=='Deposit':specs.extend([('bank_account','Actual INR bank ledger','1010',None)]+[(p,p.upper()+' cash deposit INR','0',None) for p in rcm.PARTS])
        win,body,fields=self._tax_form('Review RCM '+stage,specs)
        check=tk.BooleanVar(value=False)
        if stage=='Purchase':ttk.Checkbutton(body,text='ITC expected after actual cash discharge and separate eligibility review (otherwise tax adds to cost)',variable=check).pack(anchor='w',pady=10)
        if stage=='Claim':ttk.Checkbutton(body,text='I verified payment, documents, eligibility and applicable timing; this is not an automated legal check',variable=check).pack(anchor='w',pady=10)
        ttk.Label(body,text='Deposit = bank to electronic cash; Discharge = actual utilisation of that cash against RCM liability. Enter the actual utilisation reference, not merely a deposit challan. Claim is allowed only after linked discharge and separate review. Reverse claim before discharge, and discharge before purchase/deposit. Pending-review tax is not available ITC.',wraplength=1000).pack(anchor='w',pady=10)
        text=tk.Text(body,height=10,wrap='word',font=('Consolas',10));text.pack(fill='both',expand=True);reviewed={}
        def values():
            data={k:v.get().strip() for k,v in fields.items()}
            if 'purchase' in data:data['purchase_id']=choices[data.pop('purchase')]
            if stage=='Purchase':data['claim_expected']=check.get()
            if stage=='Claim':data['eligibility_reviewed']=check.get()
            return data
        def preview():
            data=values();prepared=rcm.prepare(self.state,stage,data);reviewed.clear();reviewed.update(values=data,fingerprint=history.fingerprints(self.state))
            text.configure(state='normal');text.delete('1.0','end');text.insert('1.0',json.dumps(prepared,ensure_ascii=False,indent=2));text.configure(state='disabled')
        def post():
            if not reviewed or reviewed['values']!=values() or reviewed['fingerprint']!=history.fingerprints(self.state):raise ValueError('Prepare a fresh preview after changing any fields or books.')
            if messagebox.askyesno('Approve RCM '+stage,'Confirm the source documents, actual stage, applicability and all journal lines?',parent=win):
                self.commit(lambda s:rcm.post(s,stage,dict(reviewed['values'],confirmed=True)));win.destroy();self.show('GST reverse charge')
        bar=ttk.Frame(body);bar.pack(fill='x');self.button(bar,'Prepare RCM preview',preview,True);self.button(bar,'Approve & post RCM',post)

    def export_rcm(self):
        path=filedialog.asksaveasfilename(parent=self,initialfile='rcm-working-review.json',defaultextension='.json')
        if path:rcm.export(rcm.report(self.state,*self.dates(),self.unit()),path)

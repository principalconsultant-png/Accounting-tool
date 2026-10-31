"""Reviewed fixed assets, SLM previews, disposal/transfer and customer packs."""
import copy
import json
from datetime import datetime
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog
from . import fixed_assets as fa,core,history


class FixedAssetsUI:
    def assets(self):
        self.note('Book fixed-asset register: reviewed Schedule II life/residual and put-to-use dates; monthly straight-line depreciation with actual-day partial months. Link opening/purchase journals already posted, or explicitly post a new purchase. Each depreciation, transfer or disposal is previewed before posting. Income Tax block depreciation is available separately under Tax depreciation.')
        start,end=self.dates()
        if getattr(self,'asset_report_year',None)==self.year.get():start,end=self.asset_from.get(),self.asset_to.get()
        else:end=min(end,max(start,datetime.now(history.INDIA).date().isoformat()))
        self.asset_report_year=self.year.get();bar=self.bar();self.asset_from=self.field(bar,'Report from',start,width=14);self.asset_to=self.field(bar,'As at / through',end,width=14);self.button(bar,'Refresh asset reports',lambda:self.show('Assets & depreciation'))
        bar=self.bar();self.button(bar,'Register book asset',self.register_book_asset,True);self.button(bar,'Post book depreciation',self.book_depreciation);self.button(bar,'Revise estimate',self.asset_estimate);self.button(bar,'Link prior depreciation',self.link_asset_depreciation)
        self.button(bar,'Transfer asset',self.asset_transfer);self.button(bar,'Dispose asset',self.asset_disposal)
        bar=self.bar();self.button(bar,'Record extra-shift usage',self.asset_shift_usage);self.button(bar,'Withdraw shift usage',self.withdraw_asset_shift)
        bar=self.bar();self.button(bar,'Withdraw latest estimate',self.withdraw_asset_estimate);self.button(bar,'Reverse selected asset journal',self.reverse_asset_journal)
        for kind in ('xlsx','pdf','json'):self.button(bar,'Export '+('Excel' if kind=='xlsx' else kind.upper()),lambda kind=kind:self.export_assets(kind))
        self.asset_report=fa.report(self.state,start,end,self.unit());r=self.asset_report
        ttk.Label(self.content,text=('Reviewed / reconciled' if r['ready'] else 'DRAFT — review required')+' | '+'; '.join(r['issues']),wraplength=1000).pack(anchor='w',pady=8)
        self.asset_table=self.table(('Reference','Asset','Unit','PPE','Original cost','Lifetime depreciation','Closing NBV','Target depreciation','Unposted','Status'),[[*row[:4],*[core.rupees(n) for n in row[4:9]],row[9]] for row in r['register']],height=7)
        self.asset_rows=dict(zip(self.asset_table.get_children(),r['register']))
        self.asset_event_rows={};self.asset_events_table=self.table(('Date','Kind','Voucher','Asset references','Current family status'),[],height=5)
        references={a['id']:a['reference'] for a in self.state['book_assets']}
        for e in self.state['fixed_asset_events']:
            if not any(i['asset_id'] in {a['id'] for a in self.state['book_assets'] if self.unit()=='ALL' or fa.branch_at(self.state,a,end)==self.unit()} for i in e['items']):continue
            row=self.asset_events_table.insert('','end',values=(e['date'],e['kind'],e['voucher'],', '.join(references[i['asset_id']] for i in e['items']),'Active' if fa.family(self.state,e['voucher']) else 'Reversed'));self.asset_event_rows[row]=e
        self.table(('Unit','Ledger','Name','Register Dr/(Cr)','Ledger Dr/(Cr)','Difference'),[[*row[:3],*[core.rupees(n) for n in row[3:]]] for row in r['proof']],height=5)
        if r['legacy_indices']:
            ttk.Label(self.content,text='Legacy calculator entries are retained without automatic posting. Register them with source vouchers and their zero-based legacy index after review.').pack(anchor='w')
            self.table(('Legacy index','Name','Branch','Acquired','Cost'),[(i,self.state['assets'][i]['name'],self.state['assets'][i]['branch'],self.state['assets'][i]['date'],core.rupees(self.state['assets'][i]['cost'])) for i in r['legacy_indices']],height=4)

    def _selected_asset(self):
        if not self.asset_table.selection():raise ValueError('Select an asset in the register first.')
        reference=self.asset_rows[self.asset_table.selection()[0]][0]
        return next(a for a in self.state['book_assets'] if a['reference']==reference)

    def _asset_preview(self,title,action,form=None):
        before=copy.deepcopy(self.state);temp=copy.deepcopy(before);result=action(temp)
        win=tk.Toplevel(self);win.title(title);win.geometry(f'{min(1050,self.winfo_screenwidth()-80)}x{min(650,self.winfo_screenheight()-100)}');win.transient(form or self);win.grab_set()
        ttk.Label(win,text='Review the source, scope, period and complete journal below. Approval saves this exact action only while the books remain unchanged.',wraplength=950,padding=10).pack(anchor='w')
        text=tk.Text(win,wrap='word',height=25);scroll=ttk.Scrollbar(win,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True)
        source_ids={result.get(k) for k in ('voucher','cost_voucher','accum_voucher')} if isinstance(result,dict) else set()
        text.insert('1.0',json.dumps(dict(result=result,linked_source_journals=[v for v in before['vouchers'] if v['id'] in source_ids],new_journals=temp['vouchers'][len(before['vouchers']):]),ensure_ascii=False,indent=2));text.configure(state='disabled')
        def approve():
            if self.state!=before:raise ValueError('Books changed after this preview. Close it and prepare a fresh preview.')
            def persist(candidate):
                candidate.clear();candidate.update(copy.deepcopy(temp));return copy.deepcopy(result)
            self.commit(persist);win.destroy()
            if form and form.winfo_exists():form.destroy()
            self.show('Assets & depreciation')
        self.button(win,'Approve asset action',approve,True)

    def register_book_asset(self):
        unit=self.unit() if self.unit()!='ALL' else next(iter(self.branches));today=self.asset_to.get()
        specs=[('reference','Unique asset reference','',None),('name','Asset / component name','',None),('branch','Operating unit code',unit,list(self.branches)),('category','Schedule II category','Manual / specific Schedule II category',list(fa.CLASSES)),('mode','Cost source mode','Link existing',['Link existing','Post purchase']),('acquired','Acquired date',today,None),('put_to_use','Put-to-use date',today,None),('baseline','Book baseline date',today,None),('cost','Original capitalized cost INR','',None),('opening_accum','Opening accumulated depreciation INR','0',None),('residual','Residual value INR','0',None),('months','Useful / remaining life months','',None),('ppe','PPE ledger code','1030',None),('accum','Accumulated depreciation ledger','1050',None),('expense','Book depreciation expense ledger','4570',None),('counter','New-purchase counter ledger','2000',None),('cost_voucher','Existing cost voucher ID','',None),('accum_voucher','Opening accumulated voucher ID','',None),('legacy_index','Legacy row index (optional)','',None),('basis','Reviewed classification/source basis','',None),('override_basis','Override / opening remaining-life basis','',None)]
        win,body,f=self._tax_form('Register reviewed book asset',specs)
        ttk.Label(body,text=fa.REFERENCE+' Purchase mode posts only capitalized cost; account separately for GST/TDS/fees or link the existing reviewed acquisition voucher. Opening assets require source-linked cost/accumulated balances and assessed remaining life. Register separate components/additions with separate references and source allocations.',wraplength=1000).pack(anchor='w',pady=8)
        def reference_life():
            months=fa.CLASSES[f['category'].get()]
            if months is None:raise ValueError('Enter the reviewed life for this specific category.')
            f['months'].set(str(months))
            if not months:f['residual'].set(f['cost'].get())
        self.button(body,'Use reference life proposal',reference_life)
        approved=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed source allocation, put-to-use, Schedule II category/life, residual, shifts and any override basis',variable=approved).pack(anchor='w',pady=10)
        def preview():
            values={k:field.get().strip() for k,field in f.items()};values['reviewed']=approved.get();values['months']=int(values['months']);self._asset_preview('Preview asset registration',lambda s:fa.register(s,values),win)
        self.button(body,'Validate & preview asset',preview,True)

    def book_depreciation(self):
        win,body,f=self._tax_form('Post reviewed book depreciation',[('through','Depreciate through',self.asset_to.get(),None),('date','Journal posting date',self.asset_to.get(),None)])
        ttk.Label(body,text='Monthly or catch-up charge: cumulative reviewed SLM target less net posted book depreciation. Partial months use actual calendar days. Posting date cannot precede coverage. Prior-year/locked-period and duplicate/dependency controls apply.',wraplength=950).pack(anchor='w',pady=8)
        self.button(body,'Preview depreciation journal',lambda:self._asset_preview('Preview book depreciation',lambda s:fa.post_depreciation(s,f['through'].get(),f['date'].get(),self.unit()),win),True)

    def link_asset_depreciation(self):
        a=self._selected_asset();win,body,f=self._tax_form('Link depreciation already posted',[('voucher','Original depreciation voucher ID','',None),('amount','Allocated posted depreciation INR','',None),('through','Depreciation coverage through',self.asset_to.get(),None),('basis','Reviewed source / allocation basis','',None)])
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed the existing source journal; link only, do not duplicate the expense or accumulated depreciation',variable=reviewed).pack(anchor='w',pady=10)
        self.button(body,'Preview prior depreciation link',lambda:self._asset_preview('Review prior depreciation registration',lambda s:fa.link_prior_depreciation(s,a['id'],f['voucher'].get(),f['amount'].get(),f['through'].get(),f['basis'].get(),reviewed.get()),win),True)

    def asset_estimate(self):
        a=self._selected_asset();p=fa.policy(a,self.asset_to.get()) or a['estimates'][0]
        win,body,f=self._tax_form('Prospective estimate revision',[('effective','Effective date',self.asset_to.get(),None),('months','Assessed remaining life months',str(p['months']),None),('residual','Revised residual INR',str(p['residual']/100),None),('basis','Technical / estimate-review basis','',None)])
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed this prospective estimate; depreciation through the previous day is posted',variable=reviewed).pack(anchor='w',pady=10)
        self.button(body,'Preview estimate revision',lambda:self._asset_preview('Review estimate revision',lambda s:fa.revise_estimate(s,a['id'],f['effective'].get(),int(f['months'].get()),f['residual'].get(),f['basis'].get(),reviewed.get()),win),True)

    def withdraw_asset_estimate(self):
        a=self._selected_asset();reason=simpledialog.askstring('Withdraw estimate','Reason for withdrawing the latest unused estimate:',parent=self)
        if reason is not None:self._asset_preview('Review estimate withdrawal',lambda s:fa.withdraw_estimate(s,a['id'],reason))

    def asset_transfer(self):
        a=self._selected_asset();win,body,f=self._tax_form('Transfer book asset',[('date','Transfer date',self.asset_to.get(),None),('branch','Destination unit code',next(iter(self.branches)),list(self.branches)),('basis','Transfer source basis','',None)])
        ttk.Label(body,text='Preview includes unposted depreciation through the preceding day in the old unit, then gross cost and accumulated-depreciation transfers through inter-branch clearing. Depreciation from the transfer day belongs to the destination.',wraplength=950).pack(anchor='w',pady=10)
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed ownership, effective transfer date and source basis',variable=reviewed).pack(anchor='w')
        self.button(body,'Preview transfer journal',lambda:self._asset_preview('Review asset transfer',lambda s:fa.transfer(s,a['id'],f['date'].get(),f['branch'].get(),f['basis'].get(),reviewed.get()),win),True)

    def asset_disposal(self):
        a=self._selected_asset();win,body,f=self._tax_form('Dispose reviewed book asset',[('date','Disposal date',self.asset_to.get(),None),('proceeds','Proceeds excluding taxes INR','0',None),('counter','Bank / receivable ledger','1010',None),('gain','Gain ledger (blank = create)','',None),('loss','Loss ledger (blank = create)','',None),('basis','Disposal source / tax-review basis','',None)])
        ttk.Label(body,text='Preview charges outstanding depreciation through the disposal day, derecognizes original cost and accumulated depreciation and records the gain/loss. Separately review and account for GST/TDS/fees; do not duplicate proceeds already posted elsewhere. Blank gain/loss fields create dedicated ledgers without reusing occupied codes.',wraplength=950).pack(anchor='w',pady=10)
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed disposal proceeds, source documents and separate tax accounting',variable=reviewed).pack(anchor='w')
        self.button(body,'Preview disposal journal',lambda:self._asset_preview('Review asset disposal',lambda s:fa.dispose(s,a['id'],f['date'].get(),f['proceeds'].get(),f['counter'].get(),f['gain'].get(),f['loss'].get(),f['basis'].get(),reviewed.get()),win),True)

    def asset_shift_usage(self):
        a=self._selected_asset();win,body,f=self._tax_form('Reviewed extra-shift usage',[('start','Usage from',self.asset_from.get(),None),('end','Usage through',self.asset_to.get(),None),('factor','Double / triple shift factor','1.5',['1.5','2']),('basis','Eligibility / usage source basis','',None)])
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I verified actual extra-shift use and Schedule II eligibility; this asset is not NESD',variable=reviewed).pack(anchor='w',pady=10)
        self.button(body,'Preview shift usage',lambda:self._asset_preview('Review extra-shift usage',lambda s:fa.save_shift_usage(s,a['id'],f['start'].get(),f['end'].get(),f['factor'].get(),f['basis'].get(),reviewed.get()),win),True)

    def withdraw_asset_shift(self):
        a=self._selected_asset();reason=simpledialog.askstring('Withdraw shift usage','Reason for withdrawing latest unused shift record:',parent=self)
        if reason is not None:self._asset_preview('Review shift withdrawal',lambda s:fa.withdraw_shift_usage(s,a['id'],reason))

    def reverse_asset_journal(self):
        if not self.asset_events_table.selection():raise ValueError('Select an asset journal in the event table.')
        e=self.asset_event_rows[self.asset_events_table.selection()[0]];roots=fa.gst._roots(self.state);chain=[v for v in self.state['vouchers'] if roots[v['id']][0]==e['voucher']];source=chain[-1]
        on=simpledialog.askstring('Reverse asset journal','Exact reversal date (YYYY-MM-DD):',initialvalue=max(self.asset_to.get(),source['date']),parent=self)
        if on:self._asset_preview('Review exact asset reversal',lambda s:core.reverse(s,source['id'],on))

    def export_assets(self,kind):
        path=filedialog.asksaveasfilename(parent=self,initialfile='book-fixed-assets.'+kind,defaultextension='.'+kind)
        if path:fa.export(self.state,self.asset_from.get(),self.asset_to.get(),self.unit(),path,kind)

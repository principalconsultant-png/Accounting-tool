"""Income Tax depreciation working papers, distinct from book postings."""
import copy
import csv
import io
import json
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog
from . import core,foundation,tax_depreciation as td


class TaxDepreciationUI:
    def tax_depreciation(self):
        self.note('Income Tax WDV blocks belong to the one legal entity. Unit schedules are management allocations, not separate taxable entities. Reviewed openings, rates, actual first use, sales and additional-depreciation eligibility remain separate from book SLM. These actions create no book journals. FY '+self.year.get()+' / AY '+str(int(self.year.get())+1)+'.')
        bar=self.bar();self.button(bar,'Create tax block',self.new_tax_block,True);self.button(bar,'Revise opening allocation',lambda:self.new_tax_block(True));self.button(bar,'Save tax rate policy',self.tax_depreciation_rule)
        bar=self.bar();self.button(bar,'Register tax addition',self.tax_addition);self.button(bar,'Record first use',self.tax_first_use);self.button(bar,'Record tax disposal',self.tax_disposal);self.button(bar,'Review additional claim',self.tax_additional_claim);self.button(bar,'Review block status',self.tax_block_status)
        bar=self.bar();self.button(bar,'Void selected tax source',self.void_tax_source);self.button(bar,'Deactivate unused block',self.deactivate_tax_block);self.button(bar,'Finalize tax year',self.finalize_tax_year);self.button(bar,'Reopen tax year',self.reopen_tax_year)
        bar=self.bar()
        for kind in ('xlsx','pdf','json'):self.button(bar,'Export '+('Excel' if kind=='xlsx' else kind.upper()),lambda kind=kind:self.export_tax_depreciation(kind))
        self.tax_dep_report=td.calculate(self.state,int(self.year.get()));r=self.tax_dep_report
        ttk.Label(self.content,text=('FINALIZED WORKING' if r.get('finalized_review_id') else 'DRAFT / PROVISIONAL' if r['issues'] or r['provisional'] else 'Reviewed working')+' | Normal: '+core.rupees(r['normal'])+' | Additional: '+core.rupees(r['additional'])+' | Closing tax WDV: '+core.rupees(r['closing']),wraplength=1000).pack(anchor='w',pady=8)
        ttk.Label(self.content,text='; '.join(r['issues']) or 'Tax calculations reconcile. Review client/year/regime applicability before filing.',wraplength=1000).pack(anchor='w')
        rows=[[b['key'],b['name'],*[core.rupees(b[k]) for k in ('opening','full','short','realizations','normal','additional','closing','gain','loss')]] for b in r['blocks']]
        self.tax_block_table=self.table(('Block','Name','Opening WDV','Full additions','Short additions','Gross realizations','Normal depreciation','Additional','Closing WDV','Block capital gain','Block capital loss'),rows,height=6);self.tax_block_rows=dict(zip(self.tax_block_table.get_children(),r['blocks']))
        self.table(('Block','Unit','Opening','Full additions','Short additions','Realizations','Pool/capital adjustment','Normal','Additional','Closing','Count'),[[*row[:2],*[core.rupees(n) for n in row[2:10]],row[10]] for b in r['blocks'] for row in b['branches'] if self.unit()=='ALL' or row[1]==self.unit()],height=5)
        self.tax_source_table=self.table(('Kind','Source ID','Reference / addition','Date / year','State'),[],height=5);self.tax_source_rows={}
        for kind in ('additions','uses','disposals','claims'):
            for source in td.data(self.state)[kind]:
                iid=self.tax_source_table.insert('','end',values=(kind,source['id'],source.get('reference',source.get('addition_id','')),source.get('acquired',source.get('date',source.get('year',''))),'Active' if source['active'] else 'Voided / superseded'));self.tax_source_rows[iid]=(kind,source['id'])
        self.note('First-use days are inclusive through the earlier of sale and 31 March. The short-use restriction applies to assets acquired during that financial year. Capital costs not put to use stay outside the depreciable pool. Additional depreciation is not assumed eligible for hospital assets. Finalize the entity tax year only after it ends and prior carry forwards are finalized; reopening proceeds newest year first.')

    def _tax_block(self):
        if not self.tax_block_table.selection():raise ValueError('Select a tax block in the entity summary first.')
        return td.block(self.state,self.tax_block_rows[self.tax_block_table.selection()[0]]['id'])

    def _tax_work_preview(self,title,action,form=None):
        before=copy.deepcopy(self.state);temp=copy.deepcopy(before);result=action(temp)
        win=tk.Toplevel(self);win.title(title);win.geometry(f'{min(1050,self.winfo_screenwidth()-80)}x{min(650,self.winfo_screenheight()-100)}');win.transient(form or self);win.grab_set()
        ttk.Label(win,text='Review this tax working-paper change. No book journal is posted. The frozen preview is rejected if the books change.',padding=10,wraplength=950).pack(anchor='w')
        bar=ttk.Frame(win);bar.pack(side='bottom',fill='x');text=tk.Text(win,wrap='word');scroll=ttk.Scrollbar(win,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);text.insert('1.0',json.dumps(result,ensure_ascii=False,indent=2));text.configure(state='disabled')
        def approve():
            if self.state!=before:raise ValueError('Books changed after preview. Prepare a new tax working preview.')
            def persist(s):s.clear();s.update(copy.deepcopy(temp));return result
            self.commit(persist);win.destroy()
            if form and form.winfo_exists():form.destroy()
            self.show('Tax depreciation')
        self.button(bar,'Approve tax working action',approve,True)

    def _tax_confirm(self,body,label='I reviewed tax-year/source applicability and the supporting basis'):
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text=label,variable=reviewed).pack(anchor='w',pady=8);return reviewed

    def new_tax_block(self,revise=False):
        b=self._tax_block() if revise else None
        win,body,f=self._tax_form('Review opening tax WDV',[("key","Block key",b['key'] if b else '',None),("name","Block name",b['name'] if b else '',None),("year","First tax financial year",str(b['start_year']) if b else self.year.get(),None),("basis","Opening WDV / control-count source basis","",None)])
        ttk.Label(body,text='Opening allocations CSV: unit,wdv,count. Counts refer to existing in-use assets/components, not patients. Positive WDV requires a positive count. Exclude unused capital costs. Revisions retain prior opening versions and require all dependent tax years to be open.',wraplength=1000).pack(anchor='w')
        text=tk.Text(body,height=6);text.pack(fill='x');alloc=b['openings'][-1]['allocations'] if b else {u:dict(wdv=0,count=0) for u in self.branches};text.insert('1.0','unit,wdv,count\n'+''.join(u+','+str(v['wdv']/100)+','+str(v['count'])+'\n' for u,v in alloc.items()));reviewed=self._tax_confirm(body)
        def preview():
            rows=csv.DictReader(io.StringIO(text.get('1.0','end').strip()))
            if set(rows.fieldnames or [])!={'unit','wdv','count'}:raise ValueError('Use unit,wdv,count headings.')
            allocations={}
            for row in rows:
                u=row['unit'].strip()
                if u in allocations:raise ValueError('Each unit can appear once.')
                allocations[u]=dict(wdv=row['wdv'],count=int(row['count']))
            action=(lambda s:td.revise_opening(s,b['id'],allocations,f['basis'].get(),reviewed.get())) if revise else (lambda s:td.save_block(s,f['key'].get(),f['name'].get(),f['year'].get(),allocations,f['basis'].get(),reviewed.get()))
            self._tax_work_preview('Preview opening tax pool',action,win)
        self.button(body,'Preview opening tax pool',preview,True)

    def tax_depreciation_rule(self):
        b=self._tax_block();win,body,f=self._tax_form('Review annual Income Tax rate',[('year','Effective financial year',self.year.get(),None),('proposal','Reference proposal',next(iter(td.REFERENCES)),list(td.REFERENCES)),('rate','WDV rate %','',None),('threshold','Short-use threshold days','180',None),('factor','Short-use factor','0.5',None),('additional','Additional depreciation rate %','0',None),('rounding','Allowance rounding','Paise',['Paise','Whole rupee']),('basis','Reviewed year / regime / rate source','',None)])
        self.button(body,'Use rate reference proposal',lambda:f['rate'].set(td.REFERENCES[f['proposal'].get()]));enabled=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='Additional depreciation is allowed by the reviewed business/regime (individual assets still require eligibility)',variable=enabled).pack(anchor='w');ttk.Label(body,text=td.SOURCE,wraplength=1000).pack(anchor='w');reviewed=self._tax_confirm(body)
        self.button(body,'Preview tax rate policy',lambda:self._tax_work_preview('Review tax rate revision',lambda s:td.save_rule(s,b['id'],f['year'].get(),f['rate'].get(),f['basis'].get(),reviewed.get(),additional_rate=f['additional'].get(),additional_enabled=enabled.get(),threshold=int(f['threshold'].get()),short_factor=f['factor'].get(),rounding=f['rounding'].get()),win),True)

    def _addition_choices(self,block_id):return {a['reference']+' · '+a['id'][:8]:a['id'] for a in td.data(self.state)['additions'] if a['active'] and a['block_id']==block_id}

    def tax_addition(self):
        b=self._tax_block();books={'Manual tax source':''};books.update({a['reference']+' · '+a['id'][:8]:a['id'] for a in self.state['book_assets']})
        win,body,f=self._tax_form('Register reviewed tax addition',[('source','Book asset link','Manual tax source',list(books)),('reference','Unique tax addition reference','',None),('branch','Tax attribution unit',next(iter(self.branches)),list(self.branches)),('acquired','Acquired date',str(self.year.get())+'-04-01',None),('cost','Actual tax cost INR','',None),('use','Actual first use (blank if unused)','',None),('basis','Reviewed cost / tax-source basis','',None),('additional_basis','Additional/new-plant eligibility basis','',None)])
        def fill():
            if not books[f['source'].get()]:raise ValueError('Select a book asset to copy its factual proposals.')
            a=next(a for a in self.state['book_assets'] if a['id']==books[f['source'].get()])
            for key,value in [('reference',a['reference']),('branch',a['branch']),('acquired',a['acquired']),('cost',str(a['cost']/100)),('use',a['put_to_use'])]:f[key].set(value)
        self.button(body,'Use selected book asset facts',fill);ttk.Label(body,text='One asset/component per tax addition. Tax cost can differ from book cost only with a reviewed basis. Assets used before the opening year belong in opening WDV. Leaving first use blank excludes cost from depreciation until commissioned. This does not post an acquisition.',wraplength=1000).pack(anchor='w')
        eligible=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='This new asset specifically qualifies for additional depreciation; eligibility is documented',variable=eligible).pack(anchor='w');reviewed=self._tax_confirm(body)
        self.button(body,'Preview tax addition',lambda:self._tax_work_preview('Review tax addition',lambda s:td.add_asset(s,b['id'],f['reference'].get(),f['branch'].get(),f['acquired'].get(),f['cost'].get(),f['basis'].get(),reviewed.get(),put_to_use=f['use'].get().strip(),book_asset_id=books[f['source'].get()],additional_eligible=eligible.get(),additional_basis=f['additional_basis'].get()),win),True)

    def tax_first_use(self):
        b=self._tax_block();choices=self._addition_choices(b['id'])
        if not choices:raise ValueError('Register a tax addition first.')
        win,body,f=self._tax_form('Record actual tax first use',[('asset','Tax addition',next(iter(choices)),list(choices)),('date','Actual first-use date',self.year.get()+'-04-01',None),('basis','Commissioning source basis','',None)]);reviewed=self._tax_confirm(body)
        self.button(body,'Preview tax first use',lambda:self._tax_work_preview('Review commissioning',lambda s:td.commission(s,choices[f['asset'].get()],f['date'].get(),f['basis'].get(),reviewed.get()),win),True)

    def tax_disposal(self):
        b=self._tax_block();choices={'Opening block assets':''};choices.update(self._addition_choices(b['id']))
        win,body,f=self._tax_form('Review tax disposal',[('source','Disposal source','Opening block assets',list(choices)),('reference','Unique tax disposal reference','',None),('branch','Tax attribution unit',next(iter(self.branches)),list(self.branches)),('date','Disposal date',self.year.get()+'-04-01',None),('count','Opening asset/component count','1',None),('money','Gross moneys payable INR','0',None),('expenses','Eligible transfer expenses INR','0',None),('basis','Reviewed disposal / capital-result basis','',None)])
        ttk.Label(body,text='Gross moneys payable include applicable sale, insurance and scrap amounts. Transfer expenses are separate. Select the exact new addition when applicable; its actually-used days determine the full/short cohort. One specific addition is sold once with count one. Opening source counts cannot consume current-year additions. A pre-use disposal is outside this depreciable block and requires separate capital-result review.',wraplength=1000).pack(anchor='w');reviewed=self._tax_confirm(body)
        self.button(body,'Preview tax disposal',lambda:self._tax_work_preview('Review disposal working',lambda s:td.dispose(s,b['id'],f['reference'].get(),f['branch'].get(),f['date'].get(),f['money'].get(),f['expenses'].get(),f['basis'].get(),reviewed.get(),addition_id=choices[f['source'].get()],count=int(f['count'].get())),win),True)

    def tax_additional_claim(self):
        b=self._tax_block();choices=self._addition_choices(b['id'])
        if not choices:raise ValueError('Select a block with eligible additions.')
        win,body,f=self._tax_form('Review additional allowance / forfeiture',[('asset','Eligible tax addition',next(iter(choices)),list(choices)),('year','Claim financial year',self.year.get(),None),('claim','Reviewed claim INR','0',None),('carry','Next-year deferred INR','0',None),('basis','Eligibility / disposal / regime basis','',None)]);reviewed=self._tax_confirm(body)
        ttk.Label(body,text='Inspect the additional-depreciation export for source maxima and proposals. Explicitly record forfeiture as zero/zero when appropriate. Claims cannot exceed original entitlements or a ceased/disallowed block. Only the statutory short-use deferred portion carries once to the next year; this is not an unabsorbed-income-tax-loss schedule.',wraplength=1000).pack(anchor='w')
        self.button(body,'Preview additional claim review',lambda:self._tax_work_preview('Review additional claim',lambda s:td.additional_claim(s,choices[f['asset'].get()],f['year'].get(),f['claim'].get(),f['carry'].get(),f['basis'].get(),reviewed.get()),win),True)

    def tax_block_status(self):
        b=self._tax_block();win,body,f=self._tax_form('Review statutory tax-block status',[('year','Financial year',self.year.get(),None),('status','Block / current allowance status','Continuing; allowance supported',['Ceased; unused costs excluded','Continuing; allowance supported','Continuing; no current allowance']),('basis','Statutory continuity / business-use basis','',None)])
        ttk.Label(body,text='Use explicit tax review where unused capital remains after in-use assets are sold, or no current allowance is supported. Pending costs stay outside the depreciable amount. Resolve count contradictions and review additional claims separately. This never invents asset counts or posts journals.',wraplength=1000).pack(anchor='w');reviewed=self._tax_confirm(body)
        self.button(body,'Preview block status review',lambda:self._tax_work_preview('Review tax-block continuity',lambda s:td.review_block_status(s,b['id'],f['year'].get(),f['status'].get(),f['basis'].get(),reviewed.get()),win),True)

    def void_tax_source(self):
        if not self.tax_source_table.selection():raise ValueError('Select a tax source row.')
        kind,key=self.tax_source_rows[self.tax_source_table.selection()[0]];reason=simpledialog.askstring('Void tax fact','Correction reason (history is retained):',parent=self)
        if reason is not None:self._tax_work_preview('Review tax source withdrawal',lambda s:td.void_record(s,kind,key,reason))

    def deactivate_tax_block(self):
        b=self._tax_block();reason=simpledialog.askstring('Deactivate unused tax block','Reason for deactivating this unused block:',parent=self)
        if reason is not None:self._tax_work_preview('Review unused tax block',lambda s:td.deactivate_block(s,b['id'],reason))

    def finalize_tax_year(self):
        win,body,f=self._tax_form('Finalize entity tax-depreciation year',[('basis','Entity year-end source / tax review basis','',None)]);reviewed=self._tax_confirm(body,'I reviewed the complete entity tax year, counts, rates, carry forwards and additional claims')
        self.button(body,'Preview final tax working',lambda:self._tax_work_preview('Review complete entity tax year',lambda s:td.finalize(s,int(self.year.get()),f['basis'].get(),reviewed.get()),win),True)

    def reopen_tax_year(self):
        reason=simpledialog.askstring('Reopen entity tax year','Reason for reopening this tax year (later years first):',parent=self)
        if reason is not None:self._tax_work_preview('Review tax-year reopening',lambda s:td.reopen(s,int(self.year.get()),reason))

    def export_tax_depreciation(self,kind):
        path=filedialog.asksaveasfilename(parent=self,initialfile='income-tax-depreciation-'+self.year.get()+'.'+kind,defaultextension='.'+kind)
        if path:td.export(self.state,int(self.year.get()),self.unit(),path,kind)

"""Reviewed, effective-dated GST/TDS master configuration."""
import copy
from datetime import datetime
import json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import tax,history


class TaxUI:
    def taxes(self):
        self.note('Set up GST/TDS rules and optional payee registrations. Every saved change is a new effective-dated version; earlier versions remain available. Same-date corrections add a revision. These masters do not post tax or determine legal applicability automatically. No individual patient accounts are needed.')
        bar=self.bar();self.button(bar,'New tax rule',lambda:self.edit_tax_rule(),True);self.button(bar,'New version of selected rule',self.version_tax_rule)
        self.button(bar,'Preview applicability',self.preview_tax_rule);self.button(bar,'Export configuration',self.export_taxes)
        self.tax_rule_table=self.table(('Key','Family','Effective from','Revision','Label','Treatment','Rate %','Review'),[],height=7);self.tax_rule_items={}
        for r in sorted(tax.rules(self.state),key=lambda r:(r['key'],r['effective'],r.get('revision',1)),reverse=True):
            item=self.tax_rule_table.insert('','end',values=(r['key'],r['family'],r['effective'],r.get('revision',1),r['label'],r['treatment'],r['rate'],'Reviewed' if r['reviewed'] else 'Needs review'));self.tax_rule_items[item]=r
        ttk.Label(self.content,text='Payees / suppliers — versioned registration details; GSTIN, PAN and TAN may stay blank.').pack(anchor='w',pady=8)
        bar=self.bar();self.button(bar,'New party',lambda:self.edit_tax_party(),True);self.button(bar,'New version of selected party',self.version_tax_party)
        self.tax_party_table=self.table(('Party ID','Name','Effective from','Revision','Category','GSTIN','PAN','Active'),[],height=5);self.tax_party_items={}
        for p in sorted(tax.parties(self.state),key=lambda p:(p['name'],p['effective'],p.get('revision',1)),reverse=True):
            item=self.tax_party_table.insert('','end',values=(p['party_id'],p['name'],p['effective'],p.get('revision',1),p['category'],p['registration']['gstin'] or 'Unknown',p['registration']['pan'] or 'Unknown','Yes' if p['active'] else 'No'));self.tax_party_items[item]=p
        legacy=self.state['settings'];ttk.Label(self.content,text='Legacy reference settings (not applied automatically): GST '+str(legacy.get('gst_rates',''))+'; TDS '+', '.join(r['section']+' '+r['rate']+'% from '+r['effective'] for r in legacy.get('tax_rules',[]))+'. Enter verified effective dates and conditions in a new rule above.',wraplength=960).pack(anchor='w',pady=12)

    def _tax_selected(self,table,items):
        selected=table.selection()
        if not selected:raise ValueError('Select the version to copy first.')
        return copy.deepcopy(items[selected[0]])

    def version_tax_rule(self):self.edit_tax_rule(self._tax_selected(self.tax_rule_table,self.tax_rule_items))
    def version_tax_party(self):self.edit_tax_party(self._tax_selected(self.tax_party_table,self.tax_party_items))

    def _tax_form(self,title,specs):
        win=tk.Toplevel(self);win.title(title);win.geometry('1100x790');win.transient(self)
        canvas=tk.Canvas(win,highlightthickness=0);scroll=ttk.Scrollbar(win,orient='vertical',command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        body=ttk.Frame(canvas,padding=14);window=canvas.create_window((0,0),window=body,anchor='nw');fields={}
        body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=max(e.width,body.winfo_reqwidth())))
        win.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-1 if e.delta>0 else 1,'units') if e.widget.winfo_class() not in ('Text','Treeview','TCombobox') else None)
        for i in range(0,len(specs),3):
            row=ttk.Frame(body);row.pack(fill='x')
            for key,label,value,choices in specs[i:i+3]:fields[key]=self.field(row,label,value,choices,width=30)
        return win,body,fields

    def edit_tax_rule(self,prior=None):
        r=prior or {};today=datetime.now(history.INDIA).date().isoformat()
        specs=[('family','Tax family',r.get('family','GST'),['GST','TDS']),('key','Stable rule key',r.get('key',''),None),('effective','New effective date',today,None),
            ('label','Rule label',r.get('label',''),None),('treatment','Treatment',r.get('treatment','Taxable'),list(tax.GST_TREATMENTS+tax.TDS_TREATMENTS)),('rate','Total rate (%)',r.get('rate',''),None),
            ('section','TDS section (GST: leave blank)',r.get('section',''),None),('party_category','Party category',r.get('party_category','Any'),list(tax.CATEGORIES)),('hsn_sac','HSN/SAC (TDS: leave blank)',r.get('hsn_sac',''),None),
            ('single_threshold','Single threshold INR (blank=unknown)',r.get('single_threshold') or '',None),('annual_threshold','Annual threshold INR (blank=unknown)',r.get('annual_threshold') or '',None),('threshold_basis','Threshold basis (TDS)',r.get('threshold_basis','Review required'),['Review required','Per payment','Financial-year aggregate','Either threshold']),
            ('ledger_codes','Linked ledger codes, comma-separated',', '.join(r.get('ledger_codes',[])),None),('source','Verified source / reference',r.get('source',''),None),('applicability','Specific applicability / conditions',r.get('applicability',''),None)]
        specs.extend([('threshold_group','TDS aggregation group (blank=section)',r.get('threshold_group',''),None),('threshold_trigger','TDS trigger comparison',r.get('threshold_trigger','Exceeds'),['Exceeds','At least']),('deduction_method','TDS deduction base',r.get('deduction_method','Whole eligible base'),['Whole eligible base','Excess over annual threshold','Current transaction only']),('tds_rounding','TDS rounding',r.get('tds_rounding','Paise'),['Paise','Whole rupee'])])
        win,body,f=self._tax_form('Add tax rule version',specs)
        reviewed=tk.BooleanVar(value=False);ttk.Checkbutton(body,text='I reviewed the source, effective date and applicability for this new version',variable=reviewed).pack(anchor='w',pady=12)
        ttk.Label(body,text='Changing a key creates a separate rule. The latest version effective on a transaction date is selected, including an unreviewed version; the app never silently falls back to an older reviewed rate. Exempt, nil-rated, zero-rated and outside-GST are distinct. GST rates are total percentages. Threshold tests and tax posting follow in B08/B09.',wraplength=1000).pack(anchor='w',pady=10)
        def save():
            values={k:v.get().strip() for k,v in f.items()};values['reviewed']=reviewed.get();values['ledger_codes']=[x.strip() for x in values['ledger_codes'].split(',') if x.strip()]
            self.commit(lambda s:tax.save_rule(s,values));win.destroy();self.show('Tax setup')
        self.button(body,'Save new version',save,True)

    def edit_tax_party(self,prior=None):
        p=prior or {};reg=p.get('registration',{});today=datetime.now(history.INDIA).date().isoformat()
        specs=[('name','Party / payee name',p.get('name',''),None),('effective','New effective date',today,None),('category','Category',p.get('category','Unknown'),list(tax.CATEGORIES[:-1]))]
        for key,label in [('gstin','GSTIN (optional)'),('pan','PAN (optional)'),('tan','TAN (optional)'),('state_code','Indian state code (optional)'),('address','Address (optional)'),('city','City (optional)'),('state','State (optional)'),('cin','CIN (optional)')]:specs.append((key,label,reg.get(key,''),None))
        specs.append(('note','Notes',p.get('note',''),None));win,body,f=self._tax_form('Add party registration version',specs)
        active=tk.BooleanVar(value=p.get('active',True));ttk.Checkbutton(body,text='Active from this date',variable=active).pack(anchor='w',pady=12)
        ttk.Label(body,text='Blank registration fields remain unknown. Validation checks format, state-code and PAN consistency; it does not check government registration status. Earlier versions are preserved. This is a payee master for tax work, not an ageing or per-patient ledger.',wraplength=1000).pack(anchor='w',pady=10)
        def save():
            values={k:v.get().strip() for k,v in f.items()};values['active']=active.get()
            self.commit(lambda s:tax.save_party(s,values,p.get('party_id')));win.destroy();self.show('Tax setup')
        self.button(body,'Save new version',save,True)

    def preview_tax_rule(self):
        keys=sorted({r['key'] for r in tax.rules(self.state)})
        if not keys:raise ValueError('Create an effective-dated rule first.')
        win=tk.Toplevel(self);win.title('Review rule applicability');win.geometry('1100x700');win.transient(self)
        row=ttk.Frame(win,padding=12);row.pack(fill='x');selected=self.tax_rule_table.selection();initial=self.tax_rule_items[selected[0]]['key'] if selected else keys[0]
        key=self.field(row,'Rule key',initial,keys,width=24);ondate=self.field(row,'Transaction date',datetime.now(history.INDIA).date().isoformat(),width=15)
        latest={}
        for p in sorted(tax.parties(self.state),key=lambda p:(p['effective'],p.get('revision',1))):latest[p['party_id']]=p
        choices={'No party selected':None,**{p['name']+' · '+pid:pid for pid,p in latest.items()}}
        party=self.field(row,'Party (optional)','No party selected',list(choices),width=35)
        text=tk.Text(win,wrap='word',font=('Consolas',10));text.pack(fill='both',expand=True,padx=12,pady=12)
        def show():
            value=tax.preview(self.state,key.get(),ondate.get().strip(),choices[party.get()]);text.configure(state='normal');text.delete('1.0','end');text.insert('1.0',json.dumps(value,ensure_ascii=False,indent=2));text.configure(state='disabled')
        self.button(row,'Preview',show,True)

    def export_taxes(self):
        path=filedialog.asksaveasfilename(parent=self,initialfile='riju-tax-configuration.json',defaultextension='.json')
        if path:tax.export_config(self.state,path);messagebox.showinfo('Tax configuration exported',str(path),parent=self)

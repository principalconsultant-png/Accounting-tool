"""Human-readable copies of journal data; persisted source records stay unchanged."""
import copy

def with_account_names(state,value):
    names={a['code']:a['name'] for a in state['accounts']}
    def expand(item):
        if isinstance(item,list):return [expand(v) for v in item]
        if isinstance(item,dict):
            result={k:expand(v) for k,v in item.items()}
            if isinstance(item.get('account'),str) and item['account'] in names:result['account_name']=names[item['account']]
            return result
        return copy.deepcopy(item)
    return expand(value)


def render(app,parent,before,candidate,result):
    import json
    import tkinter as tk
    from tkinter import ttk
    from . import core
    tabs=ttk.Notebook(parent);tabs.pack(fill='both',expand=True);journal=ttk.Frame(tabs);detail=ttk.Frame(tabs);tabs.add(journal,text='Journal lines');tabs.add(detail,text='Source details')
    vouchers=candidate['vouchers'][len(before['vouchers']):];linked=False
    if not vouchers and isinstance(result,dict):
        key=result.get('voucher') or result.get('voucher_id')
        keys={key}|{v['id'] for v in result.get('linked_source_journals',[])}
        vouchers=[v for v in candidate['vouchers'] if v['id'] in keys];linked=bool(vouchers)
    ttk.Label(journal,text='Existing source only — this action does not post this journal again.' if linked else 'Review these new journal lines before approval.' if vouchers else 'No journal is posted by this action.',wraplength=950).pack(anchor='w')
    names={a['code']:a['name'] for a in candidate['accounts']};rows=[]
    for v in vouchers:
        for l in v['lines']:rows.append((v['date'],v['id'],l['branch'],l['account'],names.get(l['account'],'Unknown ledger'),core.rupees(l['debit']),core.rupees(l['credit'])))
    app.table(('Date','Voucher','Unit','Account code','Ledger name','Debit INR','Credit INR'),rows,parent=journal,height=12)
    dr=sum(l['debit'] for v in vouchers for l in v['lines']);cr=sum(l['credit'] for v in vouchers for l in v['lines']);ttk.Label(journal,text='Total debit '+core.rupees(dr)+' | Total credit '+core.rupees(cr)+' | Difference '+core.rupees(dr-cr)).pack(anchor='w')
    text=tk.Text(detail,wrap='word');scroll=ttk.Scrollbar(detail,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);text.insert('1.0',json.dumps(with_account_names(candidate,dict(result=result,journals=vouchers)),ensure_ascii=False,indent=2));text.configure(state='disabled');return tabs

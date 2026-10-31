"""Bank-scoped, versioned statement layouts; never store period dates or balances."""
import copy
import hashlib
import uuid
from . import core,reconciliation as r

FIELDS=('date','value_date','narration','reference','debit','credit','amount','balance','fitid')
ALIASES=r.STATEMENT_ALIASES


def layout(raw,kind,options):
    if kind not in ('csv','xlsx'):raise ValueError('Saved layouts support CSV/XLSX; OFX already has fixed fields.')
    if type(options.get('header_row',1))!=int or not 1<=options.get('header_row',1)<=100:raise ValueError('Header row must be between 1 and 100.')
    _,meta=r._raw_rows(raw,kind,options.get('sheet'),options.get('header_row',1))
    columns=meta.get('columns',[])
    if not columns or any(not str(c or '').strip() for c in columns) or len(set(columns))!=len(columns):raise ValueError('Saved layouts require unique nonblank column headings.')
    return columns


def available(state,account,scope,kind):
    return [copy.deepcopy(t) for t in state.get('bank_mapping_templates',[]) if t['active'] and (t['bank_account'],t['scope'],t['kind'])==(account,scope,kind)]


def save(state,raw,filename,account,scope,name,*,mapping=None,date_format='ISO',order='Oldest first',sheet=None,header_row=1):
    r._account(state,account);r._scope(state,scope)
    name=str(name).strip()
    if not name or len(name)>100:raise ValueError('Enter a template name up to 100 characters.')
    from pathlib import Path
    kind=Path(filename).suffix.lower().lstrip('.')
    if date_format not in ('ISO','DD/MM/YYYY','DD-MM-YYYY') or order not in ('Oldest first','Newest first'):raise ValueError('Choose a supported date format and row order.')
    options=dict(date_format=date_format,order=order,sheet=sheet,header_row=header_row)
    columns=layout(raw,kind,options)
    fields={r._normal(c):c for c in columns}
    if len(fields)!=len(columns):raise ValueError('Column headings are ambiguous after normalization; use distinct headings.')
    resolved={key:next((fields[a] for a in names if a in fields),'') for key,names in ALIASES.items()}
    if not isinstance(mapping or {},dict) or any(key not in FIELDS for key in (mapping or {})):raise ValueError('Use supported bank column mapping fields.')
    resolved.update(mapping or {})
    used=[c for c in resolved.values() if c]
    if len(set(used))!=len(used):raise ValueError('One source column cannot serve multiple bank fields.')
    # Explicit blanks freeze absent optional fields; later imports cannot auto-pick new columns.
    options['mapping']=resolved
    r.read_statement(raw,kind,**options)
    prior=[t for t in state.get('bank_mapping_templates',[]) if (t['bank_account'],t['scope'],t['kind'],t['name'].casefold())==(account,scope,kind,name.casefold())]
    t=dict(id=str(uuid.uuid4()),name=name,revision=max((p['revision'] for p in prior),default=0)+1,bank_account=account,scope=scope,kind=kind,columns=columns,options=options,active=True,created_at=r._now(),source_digest=hashlib.sha256(raw).hexdigest())
    for old in prior:old['active']=False
    state.setdefault('bank_mapping_templates',[]).append(t)
    core.add_audit(state,'BANK_MAPPING_TEMPLATE_SAVED',dict(template=copy.deepcopy(t),superseded=[p['id'] for p in prior if p['id']!=t['id']]))
    return copy.deepcopy(t)


def disable(state,template_id,reason):
    t=next((t for t in state.get('bank_mapping_templates',[]) if t['id']==template_id),None)
    if not t or not t['active']:raise ValueError('Select an active saved layout.')
    if not str(reason).strip():raise ValueError('Enter a reason for disabling this layout.')
    t['active']=False;core.add_audit(state,'BANK_MAPPING_TEMPLATE_DISABLED',dict(id=template_id,reason=str(reason).strip()))


def resolve(state,template_id,raw,filename,account,scope):
    from pathlib import Path
    t=next((t for t in state.get('bank_mapping_templates',[]) if t['id']==template_id),None)
    if not t or not t['active']:raise ValueError('This bank layout is unavailable or has been superseded/disabled; select a current layout.')
    if (t['bank_account'],t['scope'],t['kind'])!=(account,scope,Path(filename).suffix.lower().lstrip('.')):raise ValueError('Saved bank layout does not match this bank ledger, scope or file type.')
    options=copy.deepcopy(t['options'])
    if layout(raw,t['kind'],options)!=t['columns']:raise ValueError('Statement columns differ from the saved layout. Review the changed file and save a new layout revision.')
    return options,copy.deepcopy(t)

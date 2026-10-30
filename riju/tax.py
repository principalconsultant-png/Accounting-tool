"""Offline effective-dated tax configuration. No inferred law or automatic posting."""
import copy
from datetime import date
from decimal import Decimal,InvalidOperation
import json
from pathlib import Path
import re
import uuid
from . import core,foundation

CATEGORIES=('Unknown','Individual / HUF','Company','Firm / LLP','Other','Any')
GST_TREATMENTS=('Taxable','Exempt','Nil rated','Zero rated','Outside GST')
TDS_TREATMENTS=('Withholding','Not applicable')


def day(value):
    if not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value:raise ValueError('Use YYYY-MM-DD for the effective date.')
    return value


def decimal_text(value,percent=False,optional=False):
    if value is None and optional:return None
    text=str(value).strip()
    if not text and optional:return None
    try:n=Decimal(text.replace(',',''))
    except InvalidOperation:raise ValueError('Enter a valid numeric rate or threshold.') from None
    if not n.is_finite() or n<0 or (percent and n>100) or n.as_tuple().exponent < (-4 if percent else -2):raise ValueError('Rates must be 0–100 with at most 4 decimals; thresholds need nonnegative INR with at most 2 decimals.')
    return format(n,'f')


def rules(state):return state.get('tax_config',{}).get('rules',[])
def parties(state):return state.get('tax_config',{}).get('parties',[])


def save_rule(state,values):
    """Append a new version; never rewrite or delete a previously recorded version."""
    family=values.get('family','');key=str(values.get('key','')).strip().upper()
    if family not in ('GST','TDS') or not re.fullmatch(r'[A-Z0-9][A-Z0-9_.-]{0,49}',key):raise ValueError('Choose GST/TDS and a rule key using letters, numbers, dot, underscore or hyphen.')
    effective=day(values.get('effective',''));label=str(values.get('label','')).strip()
    scope=str(values.get('applicability','')).strip();source=str(values.get('source','')).strip()
    if not label or not scope:raise ValueError('Enter a rule label and its specific applicability/conditions.')
    if type(values.get('reviewed',False))!=bool:raise ValueError('Review status must be yes or no.')
    reviewed=values.get('reviewed',False)
    if reviewed and not source:raise ValueError('Record your verified source/reference before marking a rule reviewed.')
    rate=decimal_text(values.get('rate',''),percent=True);treatment=values.get('treatment','')
    category=values.get('party_category','Any')
    if category not in CATEGORIES:raise ValueError('Choose a supported party category.')
    hsn=str(values.get('hsn_sac','')).strip();section=str(values.get('section','')).strip().upper()
    single=decimal_text(values.get('single_threshold',''),optional=True);annual=decimal_text(values.get('annual_threshold',''),optional=True)
    basis=values.get('threshold_basis','Review required')
    if basis not in ('Review required','Per payment','Financial-year aggregate','Either threshold'):raise ValueError('Choose a supported threshold basis.')
    if family=='GST':
        if treatment not in GST_TREATMENTS:raise ValueError('Choose the GST treatment explicitly.')
        if hsn and not re.fullmatch(r'(?:[0-9]{4}|[0-9]{6}|[0-9]{8})',hsn):raise ValueError('HSN/SAC must have 4, 6 or 8 digits, or be blank for later review.')
        if (treatment=='Taxable' and Decimal(rate)==0) or (treatment!='Taxable' and Decimal(rate)!=0):raise ValueError('Taxable requires a positive rate. Exempt/nil/zero-rated/outside-GST treatments require a zero rate.')
        if section or single is not None or annual is not None or basis!='Review required':raise ValueError('TDS section/threshold fields must be blank for a GST rule.')
    else:
        if treatment not in TDS_TREATMENTS or not re.fullmatch(r'[0-9]{3}[A-Z]{0,3}',section):raise ValueError('Choose TDS treatment and a section such as 194J, 194C or 194I.')
        if hsn:raise ValueError('HSN/SAC belongs on GST rules only.')
        if (treatment=='Withholding' and Decimal(rate)==0) or (treatment=='Not applicable' and Decimal(rate)!=0):raise ValueError('Withholding needs a positive rate; not-applicable needs zero.')
        if basis=='Per payment' and single is None or basis=='Financial-year aggregate' and annual is None or basis=='Either threshold' and (single is None or annual is None):raise ValueError('Enter the threshold(s) required by the selected basis; unknown and zero are different.')
    if not isinstance(values.get('ledger_codes',[]),list):raise ValueError('Linked ledger codes must be a list.')
    ledgers=sorted(set(str(x).strip() for x in values.get('ledger_codes',[]) if str(x).strip()))
    if any(code not in {a['code'] for a in state['accounts']} for code in ledgers):raise ValueError('A linked ledger does not exist.')
    prior=[r for r in rules(state) if r['key']==key]
    if any(r['family']!=family for r in prior):raise ValueError('An existing rule key cannot change tax family.')
    same_date=[r for r in prior if r['effective']==effective]
    revision=1+max((r.get('revision',1) for r in same_date),default=0)
    threshold_group=str(values.get('threshold_group','')).strip() or section
    threshold_trigger=values.get('threshold_trigger','Exceeds');deduction_method=values.get('deduction_method','Whole eligible base');rounding=values.get('tds_rounding','Paise')
    if threshold_trigger not in ('Exceeds','At least') or deduction_method not in ('Whole eligible base','Excess over annual threshold','Current transaction only') or rounding not in ('Paise','Whole rupee'):raise ValueError('Choose supported TDS threshold/computation/rounding settings.')
    if family=='TDS' and deduction_method=='Excess over annual threshold' and annual is None:raise ValueError('Excess-base calculation requires a known annual threshold.')
    r=dict(id=str(uuid.uuid4()),revision=revision,family=family,key=key,label=label,effective=effective,rate=rate,treatment=treatment,section=section,party_category=category,hsn_sac=hsn,single_threshold=single,annual_threshold=annual,threshold_basis=basis,applicability=scope,source=source,reviewed=reviewed,ledger_codes=ledgers)
    if family=='TDS':r.update(threshold_group=threshold_group,threshold_trigger=threshold_trigger,deduction_method=deduction_method,tds_rounding=rounding)
    state['tax_config']['rules'].append(r);core.add_audit(state,'TAX_RULE_VERSION_ADDED',copy.deepcopy(r));return copy.deepcopy(r)


def save_party(state,values,party_id=None):
    effective=day(values.get('effective',''));name=str(values.get('name','')).strip();category=values.get('category','Unknown')
    if not name or category not in CATEGORIES[:-1]:raise ValueError('Enter a party name and category; Unknown is allowed for later completion.')
    registration=foundation.optional_registration(values)
    active=values.get('active',True)
    if type(active)!=bool:raise ValueError('Party active status must be yes or no.')
    prior=[p for p in parties(state) if p['party_id']==party_id]
    if party_id and not prior:raise ValueError('Party not found.')
    revision=1+max((p.get('revision',1) for p in prior if p['effective']==effective),default=0)
    item=dict(id=str(uuid.uuid4()),revision=revision,party_id=party_id or str(uuid.uuid4()),effective=effective,name=name,category=category,registration=registration,active=active,note=str(values.get('note','')).strip())
    state['tax_config']['parties'].append(item);core.add_audit(state,'TAX_PARTY_VERSION_ADDED',copy.deepcopy(item));return copy.deepcopy(item)


def resolve_rule(state,key,on_date):
    day(on_date);eligible=[r for r in rules(state) if r['key']==key.upper().strip() and r['effective']<=on_date]
    if not eligible:raise ValueError('No rule version applies on this date. Add and review an effective-dated rule; legacy reference rates are not applied automatically.')
    return copy.deepcopy(max(eligible,key=lambda r:(r['effective'],r.get('revision',1))))


def resolve_party(state,party_id,on_date):
    day(on_date);eligible=[p for p in parties(state) if p['party_id']==party_id and p['effective']<=on_date]
    if not eligible:raise ValueError('No party registration version applies on this date.')
    return copy.deepcopy(max(eligible,key=lambda p:(p['effective'],p.get('revision',1))))


def preview(state,key,on_date,party_id=None):
    r=resolve_rule(state,key,on_date);p=resolve_party(state,party_id,on_date) if party_id else None;warnings=[]
    if not r['reviewed']:warnings.append('Rule source and applicability have not been marked reviewed.')
    if not r['source']:warnings.append('Verified source/reference is missing.')
    if r['family']=='GST':
        if not r['hsn_sac']:warnings.append('HSN/SAC has not been entered.')
        if not state['settings'].get('registration',{}).get('gstin'):warnings.append('Entity GSTIN is unknown; registration/applicability must be reviewed.')
        if p and not p['registration']['gstin']:warnings.append('Party GSTIN is unknown; no registration status or ITC eligibility is inferred.')
    if r['family']=='TDS':
        if r['threshold_basis']=='Review required':warnings.append('Threshold applicability requires review; no cumulative test has been performed.')
        if r['single_threshold'] is None or r['annual_threshold'] is None:warnings.append('One or more thresholds are unknown; blank does not mean zero.')
        if not p or p['category']=='Unknown':warnings.append('Party category/PAN applicability needs review.')
    if r['party_category']!='Any' and (not p or p['category']!=r['party_category']):warnings.append('Selected party does not satisfy the rule category; do not apply this rule.')
    if p and not p['active']:warnings.append('Party is inactive on the selected date.')
    if p and not p['registration']['pan'] and r['family']=='TDS':warnings.append('PAN is unknown; no higher-rate or other special treatment has been inferred.')
    versions=sorted(x['effective'] for x in rules(state) if x['key']==r['key'] and x['effective']>r['effective'])
    return dict(on_date=on_date,rule=r,party=p,entity_registration=copy.deepcopy(state['settings'].get('registration',{})),next_effective_date=versions[0] if versions else None,warnings=warnings,scope='Configuration preview only. No GST split, threshold accumulation, withholding, journal or filing has been calculated. Confirm transaction-specific applicability.')


def export_config(state,path):
    payload={'entity':state['settings']['entity'],'rules':copy.deepcopy(rules(state)),'parties':copy.deepcopy(parties(state)),'legacy_references':{'tds':copy.deepcopy(state['settings'].get('tax_rules',[])),'gst':state['settings'].get('gst_rates','')},'scope':'Configuration and source references only; not a tax return or legal applicability certification.'}
    Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')

"""Hospital collection taxonomy shared by language drafts and sales imports."""
import re

# Fifteen source columns H:V, in workbook order. Payments are not revenue modes.
MODES = (
 ('treatment','Treatment','4010','Therapy revenue',r'\b(?:treatments?|therapy|panchakarma)\b'),
 ('consultation','Consultation','4000','OPD consultation revenue',r'\b(?:consultations?|opd)\b'),
 ('eye_check','Eye Check Up','4050','Eye check-up revenue',r'\beye[ -]?(?:check[ -]?ups?|checks?|examinations?)\b'),
 ('registration','REGISTRTION','4060','Registration revenue',r'\b(?:registrations?|registrtion|registr[a-z]*tion)\b'),
 ('medicine_retail','Medicine Retail','4030','Pharmacy sales',r'\b(?:retail medicines?|medicines? retail|pharmacy|medicines?)\b'),
 ('medicine_treatment','Medicine Treatment','4070','Treatment medicine revenue',r'\b(?:medicines? (?:for )?treatments?|treatments? medicines?)\b'),
 ('consumables','Consumables','4080','Consumables revenue',r'\bconsumables?\b'),
 ('room_rent','Roomrent','4020','IPD room revenue',r'\b(?:room[ -]?rent|rooms?|ipd)\b'),
 ('nursing','Nursing charges','4090','Nursing charges revenue',r'\bnursing(?: charges?| fees?)?\b'),
 ('duty_doctor','Duty doctor charges','4100','Duty doctor charges revenue',r'\bduty doctor(?: charges?| fees?)?\b'),
 ('food','Food expenses','4110','Patient food revenue',r'\b(?:food(?: expenses?| charges?)?|meals?|diet charges?)\b'),
 ('swarnaprashna','SWARNAPRASHNA','4120','Swarnaprashna revenue',r'\b(?:swarnaprashna|swarnaprashana|swarnaprashan|suvarnaprashana)\b'),
 ('kalari','KALARI','4130','Kalari revenue',r'\bkalari\b'),
 ('treatment_receipt','Trtmt Pymt RECD','4140','Treatment receipts — earned services',r'\b(?:trtmt pymt recd|treatment payment(?:s)? (?:recd|received)|treatment receipts?)\b'),
 ('misc','Misc Charges','4150','Miscellaneous patient charges revenue',r'\b(?:misc(?:ellaneous)?[.]? charges?|miscellaneous)\b'),
)
PAYMENTS={'card':'1120','upi':'1110','cash':'1000','other':'1140'}
BASE_CODES={'4000','4010','4020','4030'}

def ensure_accounts(state, audit=False):
    """Add missing accounts without reclassifying or overwriting custom accounts."""
    from .core import add_audit
    existing={a['code']:a for a in state['accounts']}
    mapping=state.setdefault('revenue_mode_accounts',{})
    added=[]; changed=False
    for key,label,preferred,name,pattern in MODES:
        if key in mapping: continue
        found=existing.get(preferred)
        if found and found['kind']=='Revenue' and (preferred in BASE_CODES or found['name']==name):
            code=preferred
        else:
            code=preferred
            if found:
                code=next((str(n) for n in range(4000,4500) if str(n) not in existing),None)
                if not code: raise ValueError('No unused revenue account codes remain.')
            item={'code':code,'name':name,'kind':'Revenue'}
            state['accounts'].append(item);existing[code]=item;added.append(item)
        mapping[key]=code;changed=True
    # Dedicated clearing never invents a bank or treats an unknown source as income.
    for key,preferred,name,kind in [('other_receipts','1140','Other receipts clearing','Asset')]:
        if key in mapping: continue
        code=preferred;found=existing.get(code)
        if found and (found['kind']!=kind or found['name']!=name):
            code=next((str(n) for n in range(1140,1200) if str(n) not in existing),None)
            if not code: raise ValueError('No unused clearing account codes remain.')
            found=None
        if not found:
            item={'code':code,'name':name,'kind':kind};state['accounts'].append(item);added.append(item)
        mapping[key]=code;changed=True
    state['accounts'].sort(key=lambda a:a['code'])
    if changed and audit:add_audit(state,'REVENUE_MODES_ADDED',{'accounts':added,'mapping':dict(mapping)})
    return state

def match_modes(text):
    # Consume specific compound labels first so "medicine treatment" does not
    # also select retail medicine and generic treatment.
    found=[];remaining=text
    priority=['treatment_receipt','medicine_treatment','eye_check','duty_doctor']
    modes=sorted(MODES,key=lambda m:priority.index(m[0]) if m[0] in priority else 100)
    for key,label,code,name,pattern in modes:
        if re.search(pattern,remaining):
            found.append(key);remaining=re.sub(pattern,' ',remaining)
    return found

def receipt_lines(state, branch, revenues, payments, treatment_policy='earned', other_policy='clearing'):
    """One compound draft: debit actual payment buckets, credit service buckets."""
    from .foundation import branches
    if branch not in branches(state,active_only=True):raise ValueError('Select a valid operating unit.')
    if treatment_policy not in ('review','earned','advance'):raise ValueError('Unknown treatment receipt policy.')
    if other_policy not in ('clearing','bank'):raise ValueError('Unknown other-source policy.')
    if set(revenues)-{m[0] for m in MODES}:raise ValueError('Unknown revenue mode.')
    if set(payments)-set(PAYMENTS):raise ValueError('Unknown payment method.')
    for value in list(revenues.values())+list(payments.values()):
        if type(value)!=int or value<0:raise ValueError('Collection amounts must be non-negative integer paise.')
    total=sum(revenues.values())
    if total<=0 or total!=sum(payments.values()):raise ValueError('Service amounts must equal cash/card/UPI/other collections.')
    mapping=state['revenue_mode_accounts'];lines=[]
    for key,value in payments.items():
        if not value:continue
        code=PAYMENTS[key] if key!='other' else ('1010' if other_policy=='bank' else mapping['other_receipts'])
        lines.append(dict(account=code,branch=branch,debit=value,credit=0))
    for key,value in revenues.items():
        if not value:continue
        if key=='treatment_receipt' and treatment_policy=='review':
            raise ValueError('Choose whether Trtmt Pymt RECD is earned treatment revenue or a patient advance.')
        code='2300' if key=='treatment_receipt' and treatment_policy=='advance' else mapping[key]
        lines.append(dict(account=code,branch=branch,debit=0,credit=value))
    return lines

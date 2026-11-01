"""Versioned offline Bengaluru banking calendar. Installation is explicit and audited."""
import copy
from datetime import date,timedelta,datetime,timezone
from . import core

ANNUAL='https://www.canarabank.bank.in/documents/d/guest/holiday-list-2026'
REVISED='https://www.hdfc.bank.in/bank-holiday-list'
SPECIAL='https://www.pib.gov.in/PressReleasePage.aspx?PRID=2313778&lang=1&reg=3'
# Bank-published Karnataka lists; Kodagu-only holidays are deliberately excluded.
_DATES={'01-15':'Makar Sankranti','01-26':'Republic Day','02-15':'Maha Shivaratri','03-19':'Ugadi','03-21':'Eid-ul-Fitr (notification dependent)','03-31':'Mahavir Jayanti','04-01':'Annual bank closing','04-03':'Good Friday','04-14':'Ambedkar Jayanti','04-20':'Basava Jayanti','05-01':'May Day','05-28':'Bakri Id (notification dependent)','06-26':'Muharram (notification dependent)','08-15':'Independence Day','08-26':'Eid Milad (notification dependent)','09-14':'Ganesh Chaturthi','10-02':'Gandhi Jayanti','10-10':'Mahalaya Amavasya','10-20':'Mahanavami','10-21':'Vijaya Dashami','10-25':'Valmiki Jayanti','11-01':'Kannada Rajyotsava','11-08':'Naraka Chaturdashi','11-10':'Balipadyami','11-27':'Kanakadasa Jayanti','12-25':'Christmas'}
REVISIONS=('BLR-2026-annual-v1','BLR-2026-reviewed-v2')


def dataset(revision=REVISIONS[-1]):
    if revision not in REVISIONS:raise ValueError('Choose a supported calendar revision.')
    days=dict(_DATES)
    if revision==REVISIONS[-1]:days['03-30']=days.pop('03-31')
    return dict(id=revision,year=2026,city='Bengaluru',reviewed_on='2026-11-01',sources=[ANNUAL]+([REVISED] if revision==REVISIONS[-1] else []),holidays=[dict(date='2026-'+d,name=n,source=REVISED if d=='03-30' else ANNUAL) for d,n in sorted(days.items())],note='Bank-published Karnataka schedule, excluding Kodagu-only dates. Moon-dependent dates and actual bank exceptions require review. Revised bank list moves Mahavir Jayanti from March 31 to March 30. Apr 1 is bank annual closing.')


def install(state,revision,reason,bank_class='Other/private',confirmed=False):
    if not confirmed or not reason.strip():raise ValueError('Review the calendar sources and record a reason before installation.')
    if bank_class not in ('Other/private','Public sector/RRB'):raise ValueError('Choose the actual bank class.')
    row=dataset(revision);candidate=copy.deepcopy(state);p=candidate['settings'].setdefault('bank_reconciliation',{})
    old=p.setdefault('calendar_datasets',{}).get(str(row['year']))
    if old and REVISIONS.index(revision)<REVISIONS.index(old['id']):raise ValueError('Do not downgrade an installed calendar; use a documented manual override.')
    row.update(bank_class=bank_class,reason=reason.strip(),installed_at=datetime.now(timezone.utc).isoformat(),working_days=['2026-09-27'] if bank_class=='Public sector/RRB' and revision==REVISIONS[-1] else [],working_source=SPECIAL if bank_class=='Public sector/RRB' else '')
    p['calendar_datasets'][str(row['year'])]=row;p.setdefault('calendar_history',[]).append(copy.deepcopy(row))
    core.add_audit(candidate,'BANK_CALENDAR_INSTALLED',{'old':old,'new':row});state.clear();state.update(candidate);return row


def explain(state,value):
    d=date.fromisoformat(value);p=state['settings'].get('bank_reconciliation',{});bundle=p.get('calendar_datasets',{}).get(str(d.year));manual=next((x for x in reversed(p.get('holiday_sources',[])) if x['date']==value),None)
    if value in p.get('working_days',[]):working,why,source=True,'Manual exceptional working date','Reviewed matching policy'
    elif value in state['holidays']:working,why,source=False,'Manual holiday: '+(manual['name'] if manual else value),manual['source'] if manual else 'Settings & backup'
    elif bundle and value in bundle.get('working_days',[]):working,why,source=True,'Special opening: '+bundle['bank_class'],bundle['working_source']
    elif bundle and any(x['date']==value for x in bundle['holidays']):
        item=next(x for x in bundle['holidays'] if x['date']==value);working,why,source=False,item['name'],item['source']
    elif d.weekday()==6:working,why,source=False,'Sunday','Weekly banking rule'
    elif d.weekday()==5 and (d.day-1)//7+1 in (2,4):working,why,source=False,'Second/fourth Saturday','Weekly banking rule'
    else:working,why,source=True,'Ordinary working day','Weekly banking rule'
    return dict(date=value,working=working,reason=why,source=source,revision=bundle['id'] if bundle else '',warning='' if bundle else f'No reviewed bundled calendar installed for {d.year}; review a sourced full-year CSV and actual bank exceptions.')


def next_day(state,value):
    d=date.fromisoformat(value);steps=[]
    for _ in range(370):
        d+=timedelta(days=1);row=explain(state,d.isoformat());steps.append(row)
        if row['working']:return dict(date=row['date'],steps=steps,warning=' '.join(sorted({x['warning'] for x in steps if x['warning']})))
    raise ValueError('No working date within 370 days; review manual overrides.')


def snapshot(state,start,end):
    from . import financial_reports
    # Reuse the verified spreadsheet/PDF rendering contract, without posting.
    pack=financial_reports.snapshot(state,'Trial balance',start,end)
    pack.update(mode='Bengaluru banking calendar',columns=['Date','Working','Reason','Revision','Source','Review warning'],money_columns=[],rows=[],controls={},note='Explicitly installed year revisions, manual holidays and working-date overrides. Missing years require sourced review. Existing matches retain their original policy and holiday snapshots.')
    d=date.fromisoformat(start);last=date.fromisoformat(end)
    if (last-d).days>740:raise ValueError('Export at most two calendar years per review.')
    while d<=last:
        x=explain(state,d.isoformat());pack['rows'].append([x['date'],'Yes' if x['working'] else 'No',x['reason'],x['revision'],x['source'],x['warning']]);d+=timedelta(days=1)
    return pack

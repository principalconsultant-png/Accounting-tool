"""Packaged executable readiness check; operates only in a disposable directory."""
import io
import copy
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime
from . import APP_VERSION,core,foundation
from .revenue import MODES
from .sales_import import stage_sales,approve_sales
from .storage import Vault

def run(output):
    result={'version':APP_VERSION,'passed':False,'platform':os.name}
    try:
        from openpyxl import Workbook
        w=Workbook();s=w.active
        for col,(_,label,*_) in enumerate(MODES,8):s.cell(4,col,label)
        for col,label in enumerate(('Sub total','Card','UPI','Cash','Other source','Total'),23):s.cell(4,col,label)
        s.cell(5,1,1);s.cell(5,2,datetime(2026,6,1));s.cell(5,6,'TEST-INVOICE');s.cell(5,7,'TEST-RECEIPT')
        for col in range(8,23):s.cell(5,col,100)
        s.cell(5,23,1500);s.cell(5,24,500);s.cell(5,25,500);s.cell(5,26,500);s.cell(5,27,0);s.cell(5,28,1500)
        raw=io.BytesIO();w.save(raw);w.close()
        with tempfile.TemporaryDirectory() as directory:
            v=Vault(Path(directory)/'check.riju');state=v.load()
            q=stage_sales(state,raw.getvalue(),'synthetic.xlsx','JP');approve_sales(state,q['id'])
            v.save(state);loaded=v.load();core.verify_audit(loaded)
            if state!=loaded or len(loaded['vouchers'])!=1:raise ValueError('Vault round-trip mismatch')
            if sum(core.balances(loaded,'2026-06-30').values())!=0:raise ValueError('Unbalanced report')
            folder=Path(directory)/'external';folder.mkdir();dest=v.backup(folder)
            if Vault(dest).load()!=loaded:raise ValueError('Backup restore mismatch')
            foundation.save_entity(loaded,'Synthetic hospital',{})
            foundation.save_branch(loaded,'NEW',{'name':'Synthetic branch','beds':0})
            foundation.save_account(loaded,'1011','Synthetic bank','Asset','Cash and bank')
            lines=[dict(account='1011',branch='NEW',debit=10000,credit=0),dict(account='3000',branch='NEW',debit=0,credit=10000)]
            draft=foundation.save_draft(loaded,'2024-04-01','Synthetic opening',lines,{'type':'Journal'},opening=True)
            foundation.post_draft(loaded,draft['id']);v.save(loaded)
            if v.load()!=loaded:raise ValueError('Foundation vault round-trip mismatch')
            # A real previous-format encrypted vault must be preserved before migration.
            from .storage import MAGIC,protect
            legacy=core.empty_state();legacy['version']=1
            for key in ('schema_revision','branches','account_details','financial_years','drafts','patient_control'):legacy.pop(key,None)
            old=Vault(Path(directory)/'legacy.riju')
            original=MAGIC+protect(json.dumps(legacy).encode());old.path.write_bytes(original)
            upgraded=old.load();upgraded['settings']['backup_dir']=str(folder);old.save(upgraded)
            if old.last_upgrade_backup.read_bytes()!=original:raise ValueError('Upgrade backup differs from original vault')
            if old.load()!=upgraded:raise ValueError('Upgrade round-trip mismatch')
            result['foundation_checks_passed']=True
            from . import ledgers
            pack=ledgers.ledger_pack(loaded,['1011','3000'],'2024-04-01','2026-06-30','NEW')
            if pack['books'][0]['opening']!=10000 or pack['books'][0]['closing']!=10000:
                raise ValueError('Ledger opening/closing mismatch')
            root=Path(directory)
            ledgers.export_pdf(pack,root/'ledgers.pdf')
            ledgers.export_xlsx(pack,root/'ledgers.xlsx')
            ledgers.export_csv(pack,root/'ledgers.csv')
            ledgers.export_html(pack,root/'ledgers.html')
            if not (root/'ledgers.pdf').read_bytes().startswith(b'%PDF-'):raise ValueError('Packaged PDF export failed')
            from openpyxl import load_workbook
            workbook=load_workbook(root/'ledgers.xlsx',read_only=True)
            try:
                if workbook.sheetnames!=['1011','3000']:raise ValueError('Packaged Excel ledger pack mismatch')
            finally:workbook.close()
            result['ledger_exports_passed']=True
            from . import fx,activity
            fx.save_rate(loaded,'2026-06-01','USD','83.25','Synthetic bank advice')
            receipt=fx.post_receipt(loaded,payment_date='2026-06-01',code='USD',foreign_amount='20',credit_account='2300',reference='SELFTEST-FX-1')
            if receipt['fx']['inr_minor']!=166500:raise ValueError('Packaged FX conversion mismatch')
            v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged FX vault round-trip mismatch')
            metrics=activity.report(loaded)['metrics']
            if metrics['fx_receipts_posted']!=1 or metrics['journal_vouchers_posted']!=3:raise ValueError('Packaged work-volume mismatch')
            result['fx_and_work_volume_passed']=True
            from . import reconciliation as bank,brs_exports
            receipt=core.post(loaded,'2026-06-02','Synthetic bank receipt',[
                dict(account='1011',branch='NEW',debit=5000,credit=0),
                dict(account='4000',branch='NEW',debit=0,credit=5000)])
            statement=bank.import_statement(loaded,b'date,narration,reference,amount\n2026-06-02,Receipt,SELFTEST-BANK,50\n','selftest-bank.csv','1011','NEW','2026-06-01','2026-06-30','100','150')
            bank.match_existing(loaded,statement['row_ids'],[receipt['id']+':0'])
            report=bank.brs(loaded,statement['id'])
            if not report['ready']:raise ValueError('Packaged bank reconciliation proof failed')
            brs_exports.export_pdf(report,root/'brs.pdf')
            if not (root/'brs.pdf').read_bytes().startswith(b'%PDF-'):raise ValueError('Packaged BRS export failed')
            bank.finalize(loaded,statement['id']);v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged bank reconciliation vault round-trip mismatch')
            result['bank_reconciliation_passed']=True
            from . import history
            if not history.verify_saved_state(loaded) or not history.integrity_report(loaded)['passed']:
                raise ValueError('Packaged history integrity review failed')
            trace=history.trace_voucher(loaded,receipt['id'])
            if len(trace['matches'])!=1:raise ValueError('Packaged bank history trace failed')
            history.export_rows(history.entries(loaded),root/'history.csv')
            history.export_rows(history.entries(loaded),root/'history.json','json')
            result['history_integrity_passed']=True
            from . import tax
            tax.save_rule(loaded,dict(family='GST',key='SELFTEST-GST',label='Synthetic taxable service',effective='2026-04-01',rate='18',treatment='Taxable',hsn_sac='999311',applicability='Invented test rule only',source='Packaged synthetic test',reviewed=True))
            party=tax.save_party(loaded,dict(name='Synthetic supplier',effective='2026-04-01',category='Unknown'))
            preview=tax.preview(loaded,'SELFTEST-GST','2026-06-01',party['party_id'])
            if preview['rule']['rate']!='18':raise ValueError('Packaged tax configuration preview failed')
            tax.export_config(loaded,root/'tax-config.json');v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged tax configuration vault round-trip mismatch')
            result['tax_configuration_passed']=True
            from . import gst
            gst.post(loaded,dict(date='2026-06-03',branch='JP',kind='Sale',registration='29ABCDE1234F1Z5',place_of_supply='29',counterparty_gstin='',reference='SELFTEST-GST-1',rule_key='SELFTEST-GST',amount='100',inclusive=False,account='4000',counter_account='1010',itc='Not applicable',narration='Synthetic GST sale',confirmed=True))
            working=gst.summary(loaded,'2026-06-01','2026-06-30')
            if working['totals']['output_cgst']!=900:raise ValueError('Packaged GST journal/summary failed')
            gst.export_csv(working,root/'gst-working.csv');gst.export_report(working,root/'gst-working.json');v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged GST vault round-trip mismatch')
            result['gst_accounting_passed']=True
            original=loaded['gst_documents'][-1]
            gst.post_note(loaded,dict(original_document_id=original['id'],date='2026-06-04',document_type='Credit note',amount='25',reference='SELFTEST-CN-1',counter_account='1010',narration='Synthetic partial refund',confirmed=True))
            corrected=gst.summary(loaded,'2026-06-01','2026-06-30')
            if corrected['totals']['output_cgst']!=675 or any(corrected['unclassified'].values()):raise ValueError('Packaged GST note proof failed')
            v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged GST note persistence failed')
            result['gst_notes_passed']=True
            purchase=gst.post(loaded,dict(date='2026-06-05',branch='JP',kind='Purchase',registration='29ABCDE1234F1Z5',place_of_supply='29',counterparty_gstin='29ZZZZZ1234Z1Z5',reference='SELFTEST-P-1',rule_key='SELFTEST-GST',amount='100',inclusive=False,account='4590',counter_account='1010',itc='Eligible',narration='Synthetic purchase',confirmed=True))
            credit=gst.post_note(loaded,dict(original_document_id=purchase['id'],date='2026-06-06',document_type='Credit note',amount='25',reference='SELFTEST-PC-1',counter_account='2000',narration='Synthetic purchase correction',confirmed=True))
            source=b'supplier_gstin,invoice,date,taxable,cgst,sgst,igst,itc_available,document_type,original_invoice,original_date\n29ZZZZZ1234Z1Z5,SELFTEST-PC-1,2026-06-06,25,2.25,2.25,0,Y,Credit note,SELFTEST-P-1,2026-06-05\n'
            statement=gst.import_2b(loaded,source,'selftest-2b.csv','29ABCDE1234F1Z5','2026-06')
            gst.match_2b(loaded,statement['id'],statement['rows'][0]['id'],credit['id'])
            review=gst.review_2b(loaded,statement['id'])
            if review['matched_signed_totals']['cgst']!=-225:raise ValueError('Packaged 2B note sign/link failed')
            gst.export_2b_csv(review,root/'2b-notes.csv');v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged 2B note persistence failed')
            result['gst_2b_notes_passed']=True
            from . import rcm
            reverse=rcm.post(loaded,'Purchase',dict(date='2026-06-07',branch='JP',registration='29ABCDE1234F1Z5',reference='SELFTEST-RCM-1',narration='Synthetic RCM purchase',rule_key='SELFTEST-GST',rcm_basis='Invented test applicability only',supplier_name='Synthetic unregistered supplier',supplier_gstin='',supplier_state='29',place_of_supply='29',amount='100',account='4590',counter_account='2000',claim_expected=True,confirmed=True))
            rcm.post(loaded,'Deposit',dict(date='2026-06-08',branch='JP',registration='29ABCDE1234F1Z5',reference='SELFTEST-CIN-1',narration='Synthetic electronic cash funding',bank_account='1010',cgst='9',sgst='9',igst='0',confirmed=True))
            for stage,on,reference in [('Discharge','2026-06-09','SELFTEST-UTIL-1'),('Claim','2026-06-10','SELFTEST-RCM-ITC-1')]:
                rcm.post(loaded,stage,dict(date=on,purchase_id=reverse['id'],reference=reference,narration='Reviewed synthetic '+stage,eligibility_reviewed=True,confirmed=True))
            review=rcm.report(loaded,'2026-06-01','2026-06-30')
            if any(review['unclassified'].values()) or review['outstanding'][0]['itc_pending']:raise ValueError('Packaged RCM stage/proof failed')
            rcm.export(review,root/'rcm-working.json');v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged RCM persistence failed')
            result['gst_rcm_passed']=True
            from . import financial_reports
            statement=financial_reports.snapshot(loaded,'Balance sheet','2026-04-01','2027-03-31')
            if any(statement['controls'].values()):raise ValueError('Packaged financial statement proof failed')
            financial_reports.export_xlsx(statement,root/'financial-report.xlsx')
            financial_reports.export_pdf(statement,root/'financial-report.pdf')
            workbook=load_workbook(root/'financial-report.xlsx',read_only=True)
            try:
                if workbook.active['A2'].value!='Balance sheet':raise ValueError('Packaged financial workbook mismatch')
            finally:workbook.close()
            if not (root/'financial-report.pdf').read_bytes().startswith(b'%PDF-'):raise ValueError('Packaged financial PDF export failed')
            result['financial_report_exports_passed']=True
            reports=financial_reports.report_pack(loaded,'2026-04-01','2027-03-31')
            financial_reports.export_pack_xlsx(reports,root/'financial-pack.xlsx')
            financial_reports.export_pdf(reports,root/'financial-pack.pdf')
            workbook=load_workbook(root/'financial-pack.xlsx',read_only=True)
            try:
                if workbook.sheetnames!=['Contents',*financial_reports.MODES]:raise ValueError('Packaged financial pack mismatch')
            finally:workbook.close()
            result['financial_report_pack_passed']=True
            from . import report_branding
            from PIL import Image
            branded=copy.deepcopy(loaded)
            for slot,color in [('client','red'),('axiom','blue')]:
                logo=root/(slot+'-logo.png');Image.new('RGB',(240,80),color).save(logo);report_branding.set_logo(branded,slot,logo);logo.unlink()
            tform=financial_reports.snapshot(branded,'Balance sheet - T form','2026-04-01','2027-03-31')
            if any(tform['controls'].values()) or len(tform['logos'])!=2:raise ValueError('Packaged T-form/logo snapshot mismatch')
            financial_reports.export_xlsx(tform,root/'branded-t-form.xlsx');financial_reports.export_pdf(tform,root/'branded-t-form.pdf')
            workbook=load_workbook(root/'branded-t-form.xlsx')
            try:
                if len(workbook.active._images)!=2:raise ValueError('Packaged Excel report logos missing')
            finally:workbook.close()
            result['t_form_and_report_logos_passed']=True
            from . import tds
            payee=tax.save_party(loaded,dict(name='Synthetic TDS company',effective='2026-04-01',category='Company',pan='ABCDE1234F'))
            tax.save_rule(loaded,dict(family='TDS',key='SELFTEST-J',label='Synthetic TDS rule',effective='2026-04-01',section='194J',rate='10',treatment='Withholding',party_category='Company',annual_threshold='1000',threshold_basis='Financial-year aggregate',applicability='Invented test only',source='Packaged test',reviewed=True))
            for day,reference in [('2026-06-11','SELFTEST-TDS-1'),('2026-06-12','SELFTEST-TDS-2')]:
                deduction=tds.post(loaded,'Expense',dict(date=day,branch='JP',reference=reference,narration='Synthetic professional fees',rule_key='SELFTEST-J',party_id=payee['party_id'],mode='Automatic',gross='600',base='600',account='4510',counter_account='2000',resident_reviewed=True,confirmed=True))
            if deduction['withheld']!=12000:raise ValueError('Packaged TDS catch-up failed')
            payment=tds.post(loaded,'Challan',dict(date='2026-06-13',branch='JP',reference='SELFTEST-TDS-UTR',narration='Synthetic TDS payment',bank_account='1010',rows=[dict(section='194J',branch='JP',year=2026,tax='120')],confirmed=True))
            tds.allocate(loaded,deduction['id'],payment['id'],0,'120','2026-06-13')
            tds.challan_details(loaded,payment['id'],dict(bsr='0123456',serial='00001',deposit_date='2026-06-13',verified=True))
            working=tds.report(loaded,'2026-04-01','2027-03-31')
            if working['outstanding']['rows'] or any(working['deductions']['controls'].values()):raise ValueError('Packaged TDS reconciliation failed')
            tds.export(loaded,'2026-04-01','2027-03-31','ALL',root/'tds.xlsx','xlsx');tds.export(loaded,'2026-04-01','2027-03-31','ALL',root/'tds.pdf','pdf');v.save(loaded)
            if v.load()!=loaded:raise ValueError('Packaged TDS persistence failed')
            result['tds_bookkeeping_passed']=True
            from . import cash_flow
            cfbook=core.empty_state()
            def cfpost(dr,cr,amount,opening=False):
                return core.post(cfbook,'2026-04-01','Synthetic cash-flow check',[dict(account=dr,branch='JP',debit=amount,credit=0),dict(account=cr,branch='JP',debit=0,credit=amount)],opening=opening)
            cfpost('1010','3000',100000,True)
            cfpost('1010','4000',20000);cfpost('1030','1010',10000);cfpost('1010','2400',30000);cfpost('4570','1050',2000)
            cash_flow.save_policy(cfbook,dict(cash_flow.defaults(cfbook),effective='2026-04-01',note='Synthetic reviewed policy only',reviewed=True))
            cfresult=cash_flow.analyse(cfbook,'2026-04-01','2026-04-30')
            if not cfresult['ready'] or cfresult['totals']['Investing']!=-10000 or cfresult['totals']['Financing']!=30000:raise ValueError('Packaged cash-flow classification/proof failed')
            for kind in ('xlsx','pdf'):cash_flow.export(cfbook,'2026-04-01','2026-04-30','ALL',root/('cash-flow.'+kind),kind)
            cfvault=Vault(root/'cash-flow.riju');cfvault.save(cfbook)
            if cfvault.load()!=cfbook:raise ValueError('Packaged cash-flow policy persistence failed')
            result['cash_flow_passed']=True
            from . import bank_templates
            templatebook=core.empty_state();bankraw=b'Booked,Movement,Ref\n02/04/2026,100,TEST-TEMPLATE-1\n'
            template=bank_templates.save(templatebook,bankraw,'bank.csv','1010','ALL','Synthetic packaged layout',mapping={'date':'Booked','amount':'Movement','reference':'Ref'},date_format='DD/MM/YYYY')
            from . import reconciliation
            imported=reconciliation.import_statement(templatebook,bankraw,'bank.csv','1010','ALL','2026-04-01','2026-04-30','0','100',template_id=template['id'])
            if imported['mapping_template']['id']!=template['id'] or len(templatebook['bank_lines'])!=1 or templatebook['vouchers']:raise ValueError('Packaged saved bank layout/provenance failed')
            templatevault=Vault(root/'bank-template.riju');templatevault.save(templatebook)
            if templatevault.load()!=templatebook:raise ValueError('Packaged saved bank layout persistence failed')
            result['bank_mapping_templates_passed']=True
            from . import fixed_assets
            assetbook=core.empty_state()
            registered=fixed_assets.register(assetbook,dict(reference='PACKAGED-ASSET',name='Synthetic medical equipment',branch='JP',category='Manual / specific Schedule II category',mode='Post purchase',acquired='2026-04-01',put_to_use='2026-04-01',baseline='2026-04-01',cost='1200',opening_accum='0',residual='0',months=12,basis='Synthetic reviewed book SLM and source only',reviewed=True))
            fixed_assets.post_depreciation(assetbook,'2026-04-30')
            fixed_assets.transfer(assetbook,registered['id'],'2026-05-01','KM','Synthetic approved transfer',True)
            for kind in ('xlsx','pdf'):fixed_assets.export(assetbook,'2026-04-01','2026-04-30','ALL',root/('fixed-assets.'+kind),kind)
            fixed_assets.dispose(assetbook,registered['id'],'2026-05-31','1050','1010','','','Synthetic disposal and separate tax review',True)
            if not fixed_assets.report(assetbook,'2026-04-01','2026-05-31')['ready']:raise ValueError('Packaged fixed-asset ledger/depreciation proof failed')
            avault=Vault(root/'fixed-assets.riju');avault.save(assetbook)
            if avault.load()!=assetbook:raise ValueError('Packaged fixed-asset persistence failed')
            result['book_fixed_assets_passed']=True
            from . import tax_depreciation
            taxbook=core.empty_state()
            taxblock=tax_depreciation.save_block(taxbook,'PACKAGED-TAX','Synthetic tax block',2024,{'JP':{'wdv':'1000','count':2}},'Synthetic reviewed opening tax WDV',True)
            tax_depreciation.save_rule(taxbook,taxblock['id'],2024,'15','Synthetic reviewed rate/regime',True)
            tax_depreciation.add_asset(taxbook,taxblock['id'],'TAX-ADD','JP','2024-12-01','500','Synthetic reviewed tax cost',True,put_to_use='2024-12-01')
            taxworking=tax_depreciation.calculate(taxbook,2024)
            if taxworking['normal']!=18750 or not taxworking['ready'] or taxbook['vouchers']:raise ValueError('Packaged tax WDV/short-use/no-journal proof failed')
            tax_depreciation.finalize(taxbook,2024,'Synthetic reviewed ended tax year',True)
            if tax_depreciation.calculate(taxbook,2025)['blocks'][0]['opening']!=131250:raise ValueError('Packaged tax carry-forward failed')
            for kind in ('xlsx','pdf'):tax_depreciation.export(taxbook,2024,'ALL',root/('income-tax-depreciation.'+kind),kind)
            tvault=Vault(root/'tax-depreciation.riju');tvault.save(taxbook)
            if tvault.load()!=taxbook:raise ValueError('Packaged tax depreciation persistence failed')
            result['tax_depreciation_passed']=True
            from . import cwip
            cwbook=core.empty_state()
            project=cwip.save_project(cwbook,'PACKAGED-VK','Synthetic construction','VK','Synthetic reviewed project only',True)
            cwip.save_plan(cwbook,project['id'],'2026-04-01',{'Civil':'2000'},[dict(key='READY',name='Synthetic certificate',due='2026-05-01',completed='2026-05-01')],'Synthetic budget and milestones',True)
            cost=cwip.record_cost(cwbook,project['id'],dict(reference='PACKAGED-BILL',party='Synthetic contractor',date='2026-04-01',category='Civil',gross='1000',capital='900',retention='100',basis='Synthetic reviewed direct cost and operating expense',reviewed=True))
            cparty=tax.save_party(cwbook,dict(name='Synthetic contractor',effective='2026-04-01',category='Company',pan='ABCDE1234F'))
            tax.save_rule(cwbook,dict(family='TDS',key='PACKAGED-CWIP',label='Synthetic contractor rule',effective='2026-04-01',section='194C',rate='10',treatment='Withholding',party_category='Company',annual_threshold='0',threshold_basis='Financial-year aggregate',applicability='Synthetic only',source='Packaged test',reviewed=True))
            deduction=cwip.deduct_tds(cwbook,cost['id'],dict(date='2026-04-02',rule_key='PACKAGED-CWIP',party_id=cparty['party_id'],base='1000',mode='Automatic',review_reason='Synthetic reviewed resident contractor',resident_reviewed=True,confirmed=True,narration='Synthetic withholding'))
            cwip.settle_retention(cwbook,cost['id'],'2026-04-20','40','2000','Synthetic approved partial release',True)
            commissioned=cwip.commission(cwbook,project['id'],'2026-05-01',{cost['id']:'900'},dict(reference='PACKAGED-CWIP-PPE',name='Synthetic commissioned component',months=12,residual='0',put_to_use='2026-05-16'),'Synthetic ready-for-use certificate',True)
            registered=fixed_assets.asset(cwbook,commissioned['asset'])
            if not cwip.report(cwbook,'2026-04-01','2026-05-31')['ready'] or cwip.retained(cwbook,cost)!=6000 or deduction['withheld']!=10000 or fixed_assets.target(registered,'2026-05-15')!=0:raise ValueError('Packaged CWIP/retention/TDS/commissioning proof failed')
            fixed_assets.post_depreciation(cwbook,'2026-05-31',branch='VK')
            if not fixed_assets.report(cwbook,'2026-04-01','2026-05-31','VK')['ready']:raise ValueError('Packaged commissioned depreciation proof failed')
            for kind in ('xlsx','pdf'):cwip.export(cwbook,'2026-04-01','2026-05-31','VK',root/('cwip.'+kind),kind)
            cwvault=Vault(root/'cwip.riju');cwvault.save(cwbook)
            if cwvault.load()!=cwbook:raise ValueError('Packaged CWIP persistence failed')
            result['cwip_commissioning_passed']=True
            from . import service_revenue
            servicebook=core.empty_state()
            tax.save_rule(servicebook,dict(family='GST',key='SELF-SERVICE',effective='2026-04-01',label='Synthetic exempt service',rate='0',treatment='Exempt',source='Packaged test',applicability='Synthetic only',reviewed=True))
            advance=service_revenue.post(servicebook,'Advance',dict(date='2026-04-01',reference='SELF-ADV',branch='JP',account='4010',rule_key='SELF-SERVICE',amount='1000',payments={'1010':'1000'},basis='Synthetic source review only',reviewed=True))
            service_revenue.post(servicebook,'Earn advance',dict(date='2026-04-02',reference='SELF-EARN',branch='JP',source=advance['id'],amount='600',basis='Synthetic service completed',reviewed=True))
            service_revenue.post(servicebook,'Refund advance',dict(date='2026-04-03',reference='SELF-REFUND',branch='JP',source=advance['id'],amount='400',payments={'1010':'400'},basis='Synthetic actual cancellation refund',reviewed=True))
            if core.balances(servicebook,'2026-04-30')['2300'] or core.balances(servicebook,'2026-04-30')['4010']!=-60000:raise ValueError('Packaged revenue recognition/refund failed')
            for kind in ('xlsx','pdf'):service_revenue.export(servicebook,'2026-04-01','2026-04-30','JP',root/('service-revenue.'+kind),kind)
            servicevault=Vault(root/'service-revenue.riju');servicevault.save(servicebook)
            if servicevault.load()!=servicebook:raise ValueError('Packaged service source persistence failed')
            result['service_revenue_passed']=True
            from . import bulk_import
            bulkbook=core.empty_state()
            raw=b'date,reference,branch,narration,debit_account,credit_account,amount,journal_id\n2026-04-01,SELF-BULK,JP,Synthetic expense,4590,2000,100,\n'
            batch=bulk_import.stage(bulkbook,raw,'synthetic.csv','Expense')
            bulk_import.review_row(bulkbook,batch['id'],0,True,'Synthetic source review')
            bulk_import.approve(bulkbook,batch['id'])
            if core.balances(bulkbook,'2026-04-30')['4590']!=10000 or activity.report(bulkbook)['metrics']['import_rows_processed']!=1:raise ValueError('Packaged mapped import/source counts failed')
            for kind in ('xlsx','pdf'):bulk_import.export(bulkbook,batch['id'],root/('bulk-review.'+kind),kind)
            bulkvault=Vault(root/'bulk.riju');bulkvault.save(bulkbook)
            if bulkvault.load()!=bulkbook:raise ValueError('Packaged mapped import persistence failed')
            result['bulk_import_review_passed']=True
            from . import gst_extensions,gst_payments,gst_portal
            completed_gst=core.empty_state()
            for key,rate,treatment in [('PACK-G18','18','Taxable'),('PACK-GEX','0','Exempt')]:tax.save_rule(completed_gst,dict(family='GST',key=key,label=key,effective='2026-04-01',rate=rate,treatment=treatment,source='Packaged synthetic source',applicability='Invented tests only',reviewed=True))
            gst_extensions.post_invoice(completed_gst,dict(kind='Sale',date='2026-04-02',branch='JP',registration='29ABCDE1234F1Z5',place_of_supply='29',reference='SELF-MIXED',counter_account='1010',narration='Synthetic mixed invoice',confirmed=True,items=[dict(account='4000',rule_key='PACK-G18',amount='100',itc='Not applicable'),dict(account='4010',rule_key='PACK-GEX',amount='50',itc='Not applicable')]))
            context=dict(date='2026-04-03',branch='JP',registration='29ABCDE1234F1Z5',narration='Synthetic actual portal source',confirmed=True,eligibility_reviewed=True,cgst='9',sgst='9')
            gst_payments.post(completed_gst,'Deposit',dict(context,reference='SELF-NORMAL-CASH',bank_account='1010'))
            gst_payments.post(completed_gst,'Cash utilisation',dict(context,reference='SELF-NORMAL-USE'))
            purchase=rcm.post(completed_gst,'Purchase',dict(context,reference='SELF-RCM-PARTIAL',rule_key='PACK-G18',rcm_basis='Synthetic reviewed RCM',supplier_name='Synthetic supplier',supplier_gstin='29ZZZZZ1234Z1Z5',supplier_state='29',place_of_supply='29',amount='100',account='4590',counter_account='2000',claim_expected=True,eligible_percent='50'))
            rcm.post(completed_gst,'Deposit',dict(context,reference='SELF-RCM-DEPOSIT',bank_account='1010'))
            rcm.post(completed_gst,'Discharge',dict(context,reference='SELF-RCM-PART-USE',purchase_id=purchase['id'],cgst='4.5',sgst='4.5'))
            rcm.post(completed_gst,'Claim',dict(context,reference='SELF-RCM-PART-CLAIM',purchase_id=purchase['id'],cgst='4.5',sgst='4.5'))
            if gst_payments.position(completed_gst,'29ABCDE1234F1Z5','JP','2026-04-30')['due']['cgst'] or any(gst.summary(completed_gst,'2026-04-01','2026-04-30')['unclassified'].values()):raise ValueError('Packaged mixed GST/actual cash/partial RCM proof failed')
            for kind in ('xlsx','pdf'):gst_extensions.export(completed_gst,'2026-04-01','2026-04-30','JP',root/('completed-gst.'+kind),kind)
            gstvault=Vault(root/'completed-gst.riju');gstvault.save(completed_gst)
            if gstvault.load()!=completed_gst:raise ValueError('Packaged completed GST persistence failed')
            result['gst_extended_bookkeeping_passed']=True
            from . import bank_calendar
            bank_calendar.install(completed_gst,bank_calendar.REVISIONS[-1],'Synthetic packaged source review',confirmed=True)
            if bank_calendar.next_day(completed_gst,'2026-03-27')['date']!='2026-03-31':raise ValueError('Packaged calendar amendment failed')
            calendarpack=bank_calendar.snapshot(completed_gst,'2026-03-27','2026-04-03')
            financial_reports.export_xlsx(calendarpack,root/'calendar.xlsx');financial_reports.export_pdf(calendarpack,root/'calendar.pdf')
            result['bank_calendar_passed']=True
            from . import statements
            statements.save_policy(completed_gst,dict(start='2026-04-01',end='2027-03-31',framework=statements.FRAMEWORKS[0],basis='Synthetic packaged presentation review',mappings=statements.proposal(completed_gst),disclosures={},confirmed=True))
            statementpacks=statements.report_pack(completed_gst,'2026-04-01','2027-03-31')
            if any(statementpacks[0]['controls'].values()):raise ValueError('Packaged statement proof failed')
            financial_reports.export_pack_xlsx(statementpacks,root/'presented-statements.xlsx');financial_reports.export_pdf(statementpacks,root/'presented-statements.pdf')
            taxbook=core.empty_state()
            foundation.save_account(taxbook,'2500','Reviewed current tax payable','Liability','Other liabilities')
            core.post(taxbook,'2026-04-02','Synthetic earned revenue',[dict(account='1010',branch='JP',debit=10000,credit=0),dict(account='4000',branch='JP',debit=0,credit=10000)])
            mapping=statements.proposal(taxbook);mapping['2500']['section']='Current liabilities: current tax'
            statements.save_policy(taxbook,dict(start='2026-04-01',end='2027-03-31',framework=statements.FRAMEWORKS[0],basis='Synthetic tax review',mappings=mapping,disclosures={},confirmed=True))
            taxvalues=dict(start='2026-04-01',end='2027-03-31',branch='JP',expense_account='4610',payable_account='2500',rate='25',surcharge='0',cess='4',basis='Synthetic assumptions',confirmed=True)
            taxpreview=statements.tax_estimate(taxbook,taxvalues);statements.post_tax(taxbook,taxpreview)
            if statements.tax_estimate(taxbook,taxvalues)['delta']:raise ValueError('Packaged incremental tax provision duplicated')
            financial_reports.export_xlsx(statements.tax_pack(taxbook,taxpreview),root/'tax-provision.xlsx');financial_reports.export_pdf(statements.tax_pack(taxbook,taxpreview),root/'tax-provision.pdf')
            result['statement_presentation_passed']=True
            from . import offline_language,local_model
            import time
            langstarted=time.perf_counter()
            for _ in range(100):
                interpretation=offline_language.interpret(core.empty_state(),'Settled monthly premises rental INR5000 by NEFT at Kammanahalli on 18 June 2026','JP','2026-04-01')
            language_seconds=time.perf_counter()-langstarted
            if interpretation['account']!='4530' or interpretation['branch']!='KM' or interpretation['date']!='2026-06-18':raise ValueError('Packaged offline interpretation failed')
            try:offline_language.interpret(core.empty_state(),'Paid INR500 rent net of TDS by bank','JP','2026-04-01')
            except ValueError:pass
            else:raise ValueError('Packaged tax-language guard failed')
            result['offline_language_passed']=True
            from . import accounting_checks
            accounting_checks.save_policy(taxbook,dict(effective='2026-04-01',unusual_posting='10',basis='Synthetic review threshold',confirmed=True))
            beforefacts=copy.deepcopy(taxbook)
            checkresult=accounting_checks.run(taxbook,'2026-04-01','2027-03-31')
            answer=accounting_checks.answer(taxbook,'profit','2026-04-01','2027-03-31')
            if answer['amount']!=7400 or not checkresult['alerts'] or taxbook!=beforefacts:raise ValueError('Packaged ledger facts/checks failed')
            questionpacks=[accounting_checks.snapshots(taxbook,'2026-04-01','2027-03-31'),*answer['packs']]
            financial_reports.export_pack_xlsx(questionpacks,root/'checks-and-answer.xlsx');financial_reports.export_pdf(questionpacks,root/'checks-and-answer.pdf')
            result['accounting_checks_questions_passed']=True
            from . import ap,receipt_import
            import csv
            apbook=core.empty_state();supplier=ap.save_vendor(apbook,dict(name='Synthetic packaged vendor',credit_days='30'))
            apinvoice=ap.enter_invoice(apbook,dict(vendor=supplier['id'],branch='JP',reference='PACK-AP-1',invoice_date='2026-04-02',received_date='2026-04-03',accounting_date='2026-04-03',credit_days='30',due_basis='Receipt date',amount='1000',payable='2000',allocations=[dict(account='4590',amount='1000')],tax_treatment='No separate GST/TDS; reviewed',reviewed=True,basis='Synthetic reviewed source'))
            ap.extend(apbook,apinvoice['id'],'2026-04-30','2026-05-20','Synthetic vendor agreement',True)
            appayment=ap.pay(apbook,dict(date='2026-05-03',reference='PACK-AP-PAY',bank_account='1010',items=[dict(invoice=apinvoice['id'],amount='400')],basis='Synthetic payment evidence',reviewed=True))
            if ap.position(apbook,apinvoice)['remaining']!=60000 or ap.forecast(apbook,'2026-05-04','2026-05-04','2026-05-31')[0]['amount']!=-60000:raise ValueError('Packaged AP payment/forecast failed')
            appacks=ap.snapshots(apbook,'2026-04-01','2026-05-31')+[ap.forecast_snapshot(apbook,'2026-05-04','2026-05-04','2026-05-31')]
            financial_reports.export_pack_xlsx(appacks,root/'vendor-ap.xlsx');financial_reports.export_pdf(appacks,root/'vendor-ap.pdf')
            apvault=Vault(root/'ap.riju');apvault.save(apbook)
            if apvault.load()!=apbook:raise ValueError('Packaged AP persistence failed')
            core.reverse(apbook,appayment['voucher'],'2026-05-05')
            if ap.position(apbook,apinvoice)['remaining']!=100000:raise ValueError('Packaged AP reversal failed')
            result['vendor_ap_passed']=True
            receiptbook=core.empty_state();csvbuffer=io.StringIO();writer=csv.DictWriter(csvbuffer,fieldnames=receipt_import.HEADERS);writer.writeheader()
            for i in range(100):
                r=dict.fromkeys(receipt_import.HEADERS,'');r.update(receipt_date='2026-04-02',branch='JP',receipt_no='PACK-R-'+str(i),record_type='earned',tax_mode='no_separate_tax',consultation='100',cash='40',upi='60',total='100');writer.writerow(r)
            receiptbatch=receipt_import.stage(receiptbook,csvbuffer.getvalue().encode(),'packaged-receipts.csv');receipt_import.review(receiptbook,receiptbatch['id'],list(range(100)),True,'Synthetic receipt/tax/payment review',True);receipt_import.post(receiptbook,receiptbatch['id'])
            if len(receiptbook['vouchers'])!=100 or core.balances(receiptbook,'2026-04-30')['4000']!=-1000000:raise ValueError('Packaged standard receipt batch failed')
            for suffix in ('xlsx','csv'):receipt_import.template(root/('receipt-template.'+suffix))
            receiptpack=receipt_import.snapshot(receiptbook,receiptbatch['id']);financial_reports.export_xlsx(receiptpack,root/'receipt-review.xlsx');financial_reports.export_pdf(receiptpack,root/'receipt-review.pdf')
            receiptvault=Vault(root/'receipts.riju');receiptvault.save(receiptbook)
            if receiptvault.load()!=receiptbook:raise ValueError('Packaged standard receipts persistence failed')
            result['standard_receipt_import_passed']=True
            from .journal_preview import with_account_names
            from .date_picker import date_mode
            uxbuffer=io.StringIO();writer=csv.DictWriter(uxbuffer,fieldnames=receipt_import.HEADERS);writer.writeheader()
            uxrow=dict.fromkeys(receipt_import.HEADERS,'');uxrow.update(receipt_date='2026-04-02',branch='JP',receipt_no='PACK-REJECT-DUPLICATE',record_type='earned',tax_mode='no_separate_tax',consultation='100',cash='100',total='100');writer.writerow(uxrow);writer.writerow(uxrow)
            uxbatch=receipt_import.stage(receiptbook,uxbuffer.getvalue().encode(),'reject-duplicate.csv');receipt_import.review(receiptbook,uxbatch['id'],[1],False,'Duplicate excluded without approving posting',False);receipt_import.review(receiptbook,uxbatch['id'],[0],True,'Reviewed valid source',True)
            if receipt_import.post(receiptbook,uxbatch['id'])!=1:raise ValueError('Packaged duplicate rejection fix failed')
            if with_account_names(receiptbook,{'account':'4000'})['account_name']!='OPD consultation revenue' or date_mode('Scheduled payment date')!='day':raise ValueError('Packaged journal names/calendar detection failed')
            ap.save_vendor(apbook,dict(name='Updated packaged vendor',credit_days='45',active=True),supplier['id']);apvault.save(apbook)
            if apvault.load()['ap']['vendors'][0]['credit_days']!=45 or ap.invoice(apbook,apinvoice['id'])['vendor_name']!='Synthetic packaged vendor':raise ValueError('Packaged vendor edit/history failed')
            result['calendar_vendor_duplicate_preview_fixes_passed']=True
            from . import ap_bulk
            bulkbook=core.empty_state();ap.save_vendor(bulkbook,dict(name='Packaged bulk vendor',credit_days='45'))
            bulkbuffer=io.StringIO();bulkwriter=csv.writer(bulkbuffer);bulkwriter.writerow(ap_bulk.HEADERS)
            for i in range(100):bulkwriter.writerow(['Packaged bulk vendor','PACK-AP-BULK-'+str(i),'2026-04-01','2026-04-02','2026-04-02','','Receipt date','','JP','100','2000','1100','Synthetic source/tax review',''])
            bulkwriter.writerow(['Packaged bulk vendor','PACK-AP-BULK-0','2026-04-01','2026-04-02','2026-04-02','','Receipt date','','JP','100','2000','1100','Duplicate source excluded',''])
            bulkbatch=ap_bulk.stage(bulkbook,bulkbuffer.getvalue().encode(),'packaged-ap.csv');ap_bulk.review(bulkbook,bulkbatch['id'],[100],False,'Duplicate rejected',False);ap_bulk.review(bulkbook,bulkbatch['id'],list(range(100)),True,'Reviewed all vendor/invoice/period/tax sources',True);ap_bulk.post(bulkbook,bulkbatch['id'])
            if len(bulkbook['ap']['invoices'])!=100 or core.balances(bulkbook,'2026-04-30')['2000']!=-1000000 or ap_bulk.batch(bulkbook,bulkbatch['id'])['status']!='PROCESSED':raise ValueError('Packaged AP bulk registration failed')
            for suffix in ('xlsx','csv'):ap_bulk.template(root/('ap-bulk-template.'+suffix),bulkbook)
            bulkpack=ap_bulk.snapshot(bulkbook,bulkbatch['id']);financial_reports.export_xlsx(bulkpack,root/'ap-bulk-review.xlsx');financial_reports.export_pdf(bulkpack,root/'ap-bulk-review.pdf')
            bulkvault=Vault(root/'ap-bulk.riju');bulkvault.save(bulkbook)
            if bulkvault.load()!=bulkbook:raise ValueError('Packaged AP bulk persistence failed')
            result['ap_bulk_invoice_import_passed']=True
            diagnosticbook=copy.deepcopy(bulkbook)
            diagnosticraw=ap_bulk.row_display(diagnosticbook,dict(source_row=2,raw=dict(vendor_name='Synthetic unmatched supplier',reference='DIAG-01',invoice_date='2026-04-01',received_date='2026-04-01',accounting_date='2026-04-01',branch='JP',amount='16547',payable='2000',cost_account='1100'),validation='INVALID',review='PENDING',error='Vendor name mismatch',reason=''))
            if diagnosticraw['amount']!=1654700 or diagnosticraw['invoice_date']!='2026-04-01':raise ValueError('Packaged invalid-row source display lost source values')
            result['ap_bulk_validation_diagnostics_passed']=True
            from . import vendor_import
            import csv
            vendorbook=core.empty_state();vendorcsv=io.StringIO();vendorwriter=csv.writer(vendorcsv);vendorwriter.writerow(vendor_import.HEADERS)
            vendorwriter.writerows([['Packaged vendor '+str(i),30,'SYN-'+str(i),'Yes'] for i in range(100)]+[['Packaged vendor 0',45,'DUPLICATE','No'],['Invalid vendor','1.5','','Yes']])
            vendorplan=vendor_import.preview(vendorbook,vendorcsv.getvalue().encode(),'synthetic-vendors.csv')
            if [r['status'] for r in vendorplan['rows'][-2:]]!=['DUPLICATE','INVALID']:raise ValueError('Packaged vendor duplicate/invalid check failed')
            vendor_import.save_selected(vendorbook,vendorplan,list(range(100)))
            if len(vendorbook['ap']['vendors'])!=100 or vendorbook['vouchers']:raise ValueError('Packaged vendor bulk master mismatch')
            for kind in ('xlsx','csv'):vendor_import.template(root/('vendor-master-template.'+kind))
            result['vendor_master_bulk_import_passed']=True
            from . import petty_cash
            pettybook=core.empty_state()
            cashentry=dict(date='2026-09-01',reference='PACK-PC-1',branch='JP',category='Office',treatment='Expense',account='4590',amount='10',narration='Synthetic packaged cash expense',basis='Reviewed actual synthetic cash evidence and tax')
            petty_cash.record(pettybook,cashentry,True)
            pettycsv=io.StringIO();writer=csv.writer(pettycsv);writer.writerow(petty_cash.HEADERS);writer.writerow([cashentry[k] for k in petty_cash.FIELDS]);cashentry['reference']='PACK-PC-2';writer.writerow([cashentry[k] for k in petty_cash.FIELDS])
            pettyraw=pettycsv.getvalue().encode();parsed=petty_cash.read_source(pettyraw,'synthetic-petty.csv');pettyq=petty_cash.stage(pettybook,pettyraw,'synthetic-petty.csv',parsed,confirmed=True)
            if [r['review'] for r in pettyq['rows']]!=['DUPLICATE','PENDING']:raise ValueError('Packaged cash duplicate/valid review mismatch')
            bulk_import.review_row(pettybook,pettyq['id'],0,False,'Existing cash entry rejected');bulk_import.review_row(pettybook,pettyq['id'],1,True,'Reviewed cash source');bulk_import.approve(pettybook,pettyq['id'])
            if core.balances(pettybook,'2026-09-30')['1000']!=-2000:raise ValueError('Packaged petty cash total mismatch')
            for kind in ('xlsx','csv'):petty_cash.template(root/('petty-cash-template.'+kind))
            cashpack=petty_cash.register_pack(pettybook,'2026-09-01','2026-09-30');financial_reports.export_xlsx(cashpack,root/'petty-register.xlsx');financial_reports.export_pdf(cashpack,root/'petty-register.pdf')
            result['petty_cash_manual_bulk_passed']=True
            from . import bank_workbench
            reconbook=core.empty_state()
            bankstatement=reconciliation.import_statement(reconbook,b'date,narration,reference,debit,credit,balance\n2026-04-03,Synthetic UPI,BW1,0,100,100\n','workbench-bank.csv','1010','ALL','2026-04-01','2026-04-30','0','100')
            salescsv=io.StringIO();writer=csv.writer(salescsv);writer.writerow(receipt_import.HEADERS);salesrow=dict.fromkeys(receipt_import.HEADERS,'');salesrow.update(receipt_date='2026-04-02',branch='JP',receipt_no='PACK-WB-1',record_type='earned',tax_mode='no_separate_tax',consultation='100',upi='100',total='100');writer.writerow([salesrow[k] for k in receipt_import.HEADERS])
            report=bank_workbench.upload(reconbook,salescsv.getvalue().encode(),'workbench-sales.csv','Sales receipts');choices=bank_workbench.sources(reconbook,'1010','ALL','Sales receipts',report['id'],'2026-04-30')
            outcome=bank_workbench.reconcile(reconbook,'1010',bankstatement['id'],'Sales receipts',report['id'],bankstatement['row_ids'],[x['id'] for x in choices],'Reviewed packaged source and bank')
            if outcome['new_journals']!=2 or reconciliation.outstanding(reconbook,'1010')[0]:raise ValueError('Packaged checkbox reconciliation engine mismatch')
            for kind in ('xlsx','csv'):bank_workbench.payment_template(root/('invoice-payment-template.'+kind))
            result['bank_side_by_side_reconciliation_passed']=True
            chargebook=core.empty_state()
            core.post(chargebook,'2026-04-03','Synthetic gross bank receipt',[dict(account='1010',branch='JP',debit=10000,credit=0),dict(account='4000',branch='JP',debit=0,credit=10000)],metadata={'type':'Receipt','reference':'NET1'})
            chargest=reconciliation.import_statement(chargebook,b'date,narration,reference,debit,credit,balance\n2026-04-03,Net after charges,NET1,0,99,99\n','net-bank.csv','1010','ALL','2026-04-01','2026-04-30','0','99')
            chargechoices=bank_workbench.sources(chargebook,'1010','ALL','Sales receipts')
            bank_workbench.reconcile(chargebook,'1010',chargest['id'],'Sales receipts',None,chargest['row_ids'],[x['id'] for x in chargechoices],'Synthetic charge evidence',100)
            if reconciliation.outstanding(chargebook,'1010')[0] or core.balances(chargebook,'2026-04-30')['4560']!=100:raise ValueError('Packaged bank-charge reconciliation failed')
            result['bank_charge_difference_passed']=True
            from . import bank_entries
            entrybook=core.empty_state()
            core.post(entrybook,'2026-04-01','Synthetic loan opening',[dict(account='1010',branch='JP',debit=100000,credit=0),dict(account='2400',branch='JP',debit=0,credit=100000)],opening=True)
            entryst=reconciliation.import_statement(entrybook,b'date,narration,reference,debit,credit,balance\n2026-04-05,EMI,EMI1,110,0,890\n','emi.csv','1010','ALL','2026-04-01','2026-04-30','1000','890')
            bank_entries.record(entrybook,entryst['row_ids'][0],dict(category='Loan repayment / EMI',branch='JP',account='2400',bank_account='1010',principal='100',interest='9',fees='1',interest_account='4580',reviewed=True,basis='Synthetic lender breakup'))
            if core.balances(entrybook,'2026-04-30')['2400']!=-90000 or reconciliation.outstanding(entrybook,'1010')[0]:raise ValueError('Packaged loan bank entry failed')
            result['guided_bank_transaction_passed']=True
            from . import daily_consolidation
            dailybook=core.empty_state()
            core.post(dailybook,'2026-04-02','Synthetic daily receipt',[dict(account='1000',branch='JP',debit=12500,credit=0),dict(account='4000',branch='JP',debit=0,credit=12500)],metadata={'type':'Receipt','reference':'DAILY1'})
            daily_consolidation.refresh(dailybook,'2026-04-01','2026-04-30')
            dailyrows=daily_consolidation.pack(dailybook,'2026-04-01','2026-04-30')['rows']
            if dailyrows[1][1:4]!=[12500,1,12500]:raise ValueError('Packaged daily database metrics failed')
            dailyvault=Vault(root/'daily-database.riju');dailyvault.save(dailybook);dailyloaded=dailyvault.load();dailydb,dailymeta,dailystale=daily_consolidation.saved(dailyloaded)
            try:
                if dailystale or dailydb.execute('SELECT COUNT(*) FROM daily_metrics').fetchone()[0]!=120:raise ValueError('Packaged daily database persistence failed')
            finally:dailydb.close()
            result['daily_consolidation_database_passed']=True
            correctionbook=core.empty_state();cv=ap.save_vendor(correctionbook,dict(name='Synthetic date vendor',credit_days='30'))
            ci=ap.enter_invoice(correctionbook,dict(vendor=cv['id'],reference='DATE-INV',invoice_date='2026-05-22',received_date='2026-05-22',accounting_date='2026-05-22',credit_days='30',due_basis='Receipt date',branch='JP',amount='100',payable='2000',allocations=[dict(account='4590',amount='100')],reviewed=True,basis='Synthetic invoice',tax_treatment='No separate GST/TDS; reviewed'))
            cp=ap.pay(correctionbook,dict(date='2026-11-25',reference='SYNTHETIC-DATE-UTR',bank_account='1010',items=[dict(invoice=ci['id'],amount='100')],reviewed=True,basis='Synthetic wrong date'))
            ap.correct_payment_date(correctionbook,cp['id'],'2026-06-25','Synthetic evidence corrects November to June',True)
            if ap.position(correctionbook,ci,'2026-11-05')['status']!='Paid' or core.balances(correctionbook,'2026-11-30')['1010']!=-10000 or core.balances(correctionbook,'2026-06-30')['1010']!=-10000:raise ValueError('Packaged AP date correction failed')
            result['ap_payment_date_correction_passed']=True
            from . import payroll_accounts
            payrollbook=core.empty_state();payroll_accounts.setup(payrollbook,payroll_accounts.choices(payrollbook),'Synthetic role setup',True);payrollmap=payrollbook['settings']['payroll_ledgers']
            if len(set(payrollmap.values()))!=5 or payrollbook['vouchers']:raise ValueError('Packaged payroll ledger setup failed')
            draft=core.parse_transaction('Paid salary INR100 by bank','JP','2026-04-02',payrollbook)
            if draft[0]['account']!=payrollmap['salary_expense']:raise ValueError('Packaged salary ledger mapping failed')
            payrollvault=Vault(root/'payroll-ledgers.riju');payrollvault.save(payrollbook)
            if payrollvault.load()['settings']['payroll_ledgers']!=payrollmap:raise ValueError('Packaged payroll ledger persistence failed')
            result['salary_pf_ledgers_passed']=True
            from . import salary_bulk,bulk_import
            salarycsv=io.StringIO();writer=csv.writer(salarycsv);writer.writerow(salary_bulk.HEADERS);writer.writerow(['ACCRUAL','2026-04','JP','','','','100','','','Synthetic payroll no deductions']);writer.writerow(['PAYMENT','2026-04','JP','2026-05-05','SYNTHETIC-SAL1','1010','100','','','Synthetic bank evidence'])
            salaryq=salary_bulk.stage(payrollbook,salarycsv.getvalue().encode(),'synthetic-salary.csv')
            for i in range(2):bulk_import.review_row(payrollbook,salaryq['id'],i,True,'Reviewed source')
            bulk_import.approve(payrollbook,salaryq['id'])
            if core.balances(payrollbook,'2026-05-31')[payrollmap['salary_payable']]!=0 or core.balances(payrollbook,'2026-05-31')[payrollmap['salary_expense']]!=10000:raise ValueError('Packaged monthly salary import failed')
            advancebook=core.empty_state();payroll_accounts.setup(advancebook,payroll_accounts.choices(advancebook),'Synthetic role setup',True)
            early=io.StringIO();writer=csv.writer(early);writer.writerow(salary_bulk.HEADERS);writer.writerow(['ACCRUAL','2026-04','JP','','','','100','','','Synthetic early payroll']);writer.writerow(['PAYMENT','2026-04','JP','05/04/26','SYN-EARLY','1010','100','','','Synthetic evidence'])
            earlyq=salary_bulk.stage(advancebook,early.getvalue().encode(),'synthetic-early.csv',advance_mode=True)
            for i in range(2):bulk_import.review_row(advancebook,earlyq['id'],i,True,'Reviewed source')
            if len(bulk_import.approve(advancebook,earlyq['id']))!=3:raise ValueError('Packaged salary advance application missing')
            earlybalances=core.balances(advancebook,'2026-04-30')
            if earlybalances[advancebook['settings']['salary_advance_ledger']] or earlybalances[advancebook['settings']['payroll_ledgers']['salary_payable']]:raise ValueError('Packaged salary advances failed to clear')
            salary_bulk.template(root/'salary-template.xlsx');result['salary_bulk_journals_passed']=True








            from . import business_pulse,business_pulse_exports
            pulsebook=core.empty_state()
            core.post(pulsebook,'2026-04-02','Synthetic pulse receipt',[dict(account='1000',branch='JP',debit=12500,credit=0),dict(account='4000',branch='JP',debit=0,credit=12500)])
            business_pulse.save_month(pulsebook,dict(month='2026-04',branch='ALL',visits='',new_patients=0,books_reviewed=True,basis='Synthetic complete month'))
            pulsepack=business_pulse.snapshot(pulsebook,2026,'2026-04-30')
            pulserows={r['key']:r['values'][0] for r in pulsepack['rows']}
            if pulserows['visits']!=1 or pulserows['arpp']!=12500 or pulserows['new_patients']!=0 or len(pulsebook['vouchers'])!=1:raise ValueError('Packaged monthly metric calculation failed')
            business_pulse_exports.export_xlsx(pulsepack,root/'business-pulse.xlsx');business_pulse_exports.export_pdf(pulsepack,root/'business-pulse.pdf')
            business_pulse.input_template(root/'business-pulse-inputs.xlsx')
            result['business_pulse_report_passed']=True

            resetvault=Vault(root/'reset.riju');resetstate=core.empty_state();core.post(resetstate,'2026-04-01','Synthetic test entry to clear',[dict(account='1000',branch='JP',debit=10000,credit=0),dict(account='4000',branch='JP',debit=0,credit=10000)]);resetvault.save(resetstate)
            resetoriginal=resetvault.path.read_bytes();resetfolder=root/'reset-backup';resetfolder.mkdir();clean,resetbackup=resetvault.start_clean_books(resetfolder,'START CLEAN BOOKS')
            if clean['vouchers'] or resetbackup.read_bytes()!=resetoriginal or resetvault.load()!=clean or len(Vault(resetbackup).load()['vouchers'])!=1:raise ValueError('Packaged verified clean-books reset failed')
            result['verified_clean_books_reset_passed']=True


            result['offline_model_version']=local_model.VERSION;result['offline_model_digest']=local_model.digest();result['offline_language_100_drafts_seconds']=round(language_seconds,4)




            result.update(passed=True,revenue_modes=len(MODES),posted_vouchers=len(loaded['vouchers']),windows_vault_backup_roundtrip=True)
    except Exception as error:
        result['error']=str(error)
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result['passed']

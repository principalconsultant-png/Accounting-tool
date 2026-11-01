import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from openpyxl import Workbook
from riju import core,gst,tax,history
from riju.storage import Vault
from test_gst import values,OUR,LOCAL


class Gst2bNoteTests(unittest.TestCase):
    def setUp(self):
        self.s=core.empty_state()
        tax.save_rule(self.s,dict(family='GST',key='TEST-GST',effective='2026-04-01',label='Invented',rate='18',treatment='Taxable',hsn_sac='999311',applicability='Tests only',source='Invented reference',reviewed=True))
        self.invoice=gst.post(self.s,values(kind='Purchase',counterparty_gstin=LOCAL,reference='P-1',account='4590',itc='Eligible'))
        self.note=gst.post_note(self.s,dict(original_document_id=self.invoice['id'],date='2026-05-01',document_type='Credit note',amount='50',reference='CN-1',counter_account='2000',narration='Invented purchase correction',confirmed=True))
    def raw(self,rows):
        out=io.StringIO();writer=csv.DictWriter(out,fieldnames=['supplier_gstin','invoice','date','taxable','cgst','sgst','igst','itc_available','document_type','original_invoice','original_date']);writer.writeheader();writer.writerows(rows);return out.getvalue().encode()
    def row(self,**extra):
        r=dict(supplier_gstin=LOCAL,invoice='CN-1',date='2026-05-01',taxable='50',cgst='4.5',sgst='4.5',igst='0',itc_available='Y',document_type='Credit note',original_invoice='P-1',original_date='2026-04-02');r.update(extra);return r
    def load(self,rows=None,period='2026-05'):
        return gst.import_2b(self.s,self.raw(rows or [self.row()]),'2b.csv',OUR,period)
    def test_credit_note_matches_type_parent_and_signed_totals_without_posting(self):
        item=self.load();before=len(self.s['vouchers']);row=gst.candidates_2b(self.s,item['id'])[0]
        self.assertEqual(row['candidates'][0]['status'],'Exact');gst.match_2b(self.s,item['id'],item['rows'][0]['id'],self.note['id'])
        r=gst.review_2b(self.s,item['id']);self.assertEqual(r['statement_signed_totals']['taxable'],-5000);self.assertEqual(r['matched_signed_totals']['cgst'],-450)
        self.assertEqual(len(self.s['vouchers']),before);self.assertEqual(r['book_documents_without_2b'],[]);core.verify_audit(self.s)
    def test_invoice_clears_adjustment_flag_only_when_all_notes_linked(self):
        invoice_row=self.row(invoice='P-1',date='2026-04-02',taxable='100',cgst='9',sgst='9',document_type='Invoice',original_invoice='',original_date='')
        imp=self.load([invoice_row],period='2026-04');source_id=imp['rows'][0]['id']
        with self.assertRaises(ValueError):gst.match_2b(self.s,imp['id'],source_id,self.invoice['id'])
        notes=self.load();m=gst.match_2b(self.s,notes['id'],notes['rows'][0]['id'],self.note['id'])
        gst.match_2b(self.s,imp['id'],source_id,self.invoice['id']);self.assertEqual(gst.candidates_2b(self.s,imp['id'])[0]['status'],'Matched')
        gst.unmatch_2b(self.s,m['id'],'Review source');self.assertIn('adjusted',gst.candidates_2b(self.s,imp['id'])[0]['status'])
    def test_one_of_two_linked_notes_does_not_clear_original(self):
        gst.post_note(self.s,dict(original_document_id=self.invoice['id'],date='2026-05-02',document_type='Debit note',amount='10',reference='DN-1',counter_account='2000',narration='Invented debit',confirmed=True))
        source=self.load();gst.match_2b(self.s,source['id'],source['rows'][0]['id'],self.note['id'])
        inv=self.load([self.row(invoice='P-1',date='2026-04-02',taxable='100',cgst='9',sgst='9',document_type='Invoice',original_invoice='',original_date='')],period='2026-04')
        self.assertEqual(gst.candidates_2b(self.s,inv['id'])[0]['candidates'][0]['status'],'Adjusted by GST note - review')
    def test_wrong_parent_reference_date_amount_and_type_cannot_match(self):
        for i,change in enumerate(({'original_invoice':'OTHER'},{'original_date':'2026-04-03'},{'taxable':'51'},{'document_type':'Debit note'})):
            item=self.load([self.row(**change)],period='2026-'+str(6+i).zfill(2));before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):gst.match_2b(self.s,item['id'],item['rows'][0]['id'],self.note['id'])
            self.assertEqual(before,self.s)
    def test_note_cannot_be_imported_as_positive_invoice(self):
        item=self.load([self.row(document_type='Invoice',original_invoice='',original_date='')])
        self.assertEqual(gst.candidates_2b(self.s,item['id'])[0]['candidates'],[])
    def test_missing_parent_invalid_type_and_negative_note_reject_atomically(self):
        for change in ({'original_invoice':''},{'original_date':''},{'original_date':'2026-06-01'},{'document_type':'Unknown'},{'taxable':'-50'},{'cgst':'=4.5'}):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):self.load([self.row(**change)])
            self.assertEqual(before,self.s)
    def test_debit_note_positive_and_unavailable_source_stays_unavailable(self):
        d=gst.post_note(self.s,dict(original_document_id=self.invoice['id'],date='2026-05-02',document_type='Debit note',amount='20',reference='DN-1',counter_account='2000',narration='Test debit',confirmed=True))
        item=self.load([self.row(invoice='DN-1',date='2026-05-02',taxable='20',cgst='1.8',sgst='1.8',document_type='Debit note',itc_available='N')]);m=gst.match_2b(self.s,item['id'],item['rows'][0]['id'],d['id'])
        r=gst.review_2b(self.s,item['id']);self.assertEqual(r['statement_signed_totals']['cgst'],180);self.assertEqual(r['unavailable_signed_totals']['cgst'],180);self.assertEqual(m['itc_available'],'N');self.assertEqual(d['itc'],'Eligible')
    def test_reversed_note_link_flags_and_cannot_be_reused(self):
        a=self.load();gst.match_2b(self.s,a['id'],a['rows'][0]['id'],self.note['id'])
        b=self.load(period='2026-06')
        with self.assertRaises(ValueError):gst.match_2b(self.s,b['id'],b['rows'][0]['id'],self.note['id'])
        core.reverse(self.s,self.note['voucher_id'],'2026-06-02');self.assertIn('reversed',gst.candidates_2b(self.s,a['id'])[0]['status'])
    def test_missing_book_notes_reported_separately_from_invoice_alias(self):
        item=self.load([self.row(invoice='NO-BOOK-NOTE')]);report=gst.review_2b(self.s,item['id'])
        self.assertEqual(report['rows'][0]['status'],'Missing in books');self.assertEqual(report['book_documents_without_2b'][0]['id'],self.note['id']);self.assertEqual(report['book_invoices_without_2b'],[])
    def test_xlsx_note_import_and_legacy_invoice_header_compatibility(self):
        row=self.row();w=Workbook();ws=w.active;ws.append(list(row));ws.append(list(row.values()));out=io.BytesIO();w.save(out);w.close()
        item=gst.import_2b(self.s,out.getvalue(),'notes.xlsx',OUR,'2026-05');self.assertEqual(item['rows'][0]['document_type'],'Credit note')
        raw=('supplier_gstin,invoice,date,taxable,cgst,sgst,igst,itc_available\n'+LOCAL+',P-1,2026-04-02,100,9,9,0,Y\n').encode()
        old=gst.import_2b(self.s,raw,'old.csv',OUR,'2026-04');self.assertEqual(old['rows'][0]['document_type'],'Invoice')
    def test_signed_csv_export_and_void_import_preserve_history(self):
        item=self.load([self.row(invoice='=FORMULA')]);before=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'notes.csv';gst.export_2b_csv(gst.review_2b(self.s,item['id']),p);text=p.read_text(encoding='utf-8-sig');self.assertIn("'=FORMULA",text);self.assertIn('-50.00',text)
        self.assertEqual(before,self.s);gst.void_2b(self.s,item['id'],'Wrong file');self.load();core.verify_audit(self.s)
    def test_format_seven_upgrade_keeps_legacy_rows_links_and_backups(self):
        state=core.empty_state();tax.save_rule(state,copy.deepcopy(self.s['tax_config']['rules'][0]))
        invoice=gst.post(state,values(kind='Purchase',counterparty_gstin=LOCAL,reference='P-LEGACY',account='4590',itc='Eligible'))
        raw=('supplier_gstin,invoice,date,taxable,cgst,sgst,igst,itc_available\n'+LOCAL+',P-LEGACY,2026-04-02,100,9,9,0,Y\n').encode()
        item=gst.import_2b(state,raw,'legacy.csv',OUR,'2026-04');gst.match_2b(state,item['id'],item['rows'][0]['id'],invoice['id'])
        # Recreate the invoice-only live-row shape used before typed 2B documents.
        for row in state['gst_2b_imports'][0]['rows']:
            for key in ('document_type','original_invoice','original_date'):row.pop(key,None)
        state['gst_2b_matches'][0].pop('document_type',None)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ext=root/'external';ext.mkdir();old=copy.deepcopy(state);old['version']=7;old['schema_revision']=7;history.checkpoint(old)
            p=root/'old.json';p.write_text(json.dumps(old));original=p.read_bytes();v=Vault(p,demo=True);new=v.load();new['settings']['backup_dir']=str(ext)
            self.assertTrue(v.migration_pending);self.assertEqual(new['gst_2b_imports'],old['gst_2b_imports']);self.assertEqual(new['gst_2b_matches'],old['gst_2b_matches'])
            v.save(new);self.assertEqual(v.last_upgrade_backup.read_bytes(),original);self.assertEqual(new['version'],18);self.assertEqual(v.load(),new)
            self.assertEqual(gst.candidates_2b(new,item['id'])[0]['status'],'Matched')

    def test_matched_row_uses_its_actual_link_not_a_reused_reference_in_another_year(self):
        # A reversed older invoice must not invalidate a newer invoice with the same reference.
        older=gst.post(self.s,values(date='2026-04-03',kind='Purchase',counterparty_gstin=LOCAL,reference='REUSED',account='4590',itc='Eligible'))
        core.reverse(self.s,older['voucher_id'],'2026-04-04')
        newer=gst.post(self.s,values(date='2027-04-03',kind='Purchase',counterparty_gstin=LOCAL,reference='REUSED',account='4590',itc='Eligible'))
        item=self.load([self.row(invoice='REUSED',date='2027-04-03',taxable='100',cgst='9',sgst='9',document_type='Invoice',original_invoice='',original_date='')],period='2027-04')
        gst.match_2b(self.s,item['id'],item['rows'][0]['id'],newer['id']);self.assertEqual(gst.candidates_2b(self.s,item['id'])[0]['status'],'Matched')

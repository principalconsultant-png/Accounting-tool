import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from openpyxl import Workbook
from riju import bank_templates as bt,core,foundation,history,reconciliation as r
from riju.storage import Vault

RAW=b'Bank export\nWhen,Details,Ref,Out,In,After\n02/04/2026,Receipt,R1,0,100,100\n'
MAP=dict(date='When',narration='Details',reference='Ref',debit='Out',credit='In',balance='After')

class BankTemplateTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def save(self,raw=RAW,**kwargs):
        opts=dict(mapping=MAP,date_format='DD/MM/YYYY',header_row=2);opts.update(kwargs)
        return bt.save(self.s,raw,'bank.csv','1010','ALL','Synthetic bank layout',**opts)
    def load(self,t,raw=RAW,**kwargs):
        opts=dict(filename='bank.csv',account='1010',scope='ALL',start='2026-04-01',end='2026-04-30',opening='0',closing='100',template_id=t['id']);opts.update(kwargs)
        return r.import_statement(self.s,raw,**opts)
    def test_layout_reuse_keeps_each_period_balances_and_provenance(self):
        t=self.save();self.assertEqual(t['options']['mapping']['amount'],'');self.assertNotIn('opening',t['options']);self.assertNotIn('start',t['options'])
        first=self.load(t);second=self.load(t,RAW.replace(b'02/04/2026',b'02/05/2026').replace(b'R1',b'R2').replace(b',100,100',b',100,200'),filename='may.csv',start='2026-05-01',end='2026-05-31',opening='100',closing='200')
        self.assertEqual(len(self.s['bank_lines']),2);self.assertEqual(second['closing'],20000);self.assertEqual(first['mapping_template']['id'],t['id']);self.assertEqual(first['parser_options'],t['options']);core.verify_audit(self.s)
    def test_revision_supersedes_without_changing_imported_snapshot(self):
        old=self.save();statement=self.load(old);snapshot=copy.deepcopy(statement['mapping_template']);new=self.save()
        self.assertEqual(new['revision'],2);self.assertEqual(len(bt.available(self.s,'1010','ALL','csv')),1)
        self.assertEqual(self.s['bank_statements'][0]['mapping_template'],snapshot)
        before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'superseded'):self.load(old)
        self.assertEqual(self.s,before)
    def test_disable_requires_reason_retains_evidence_and_blocks_use(self):
        t=self.save();self.load(t)
        with self.assertRaises(ValueError):bt.disable(self.s,t['id'],'')
        bt.disable(self.s,t['id'],'Bank changed its layout');self.assertFalse(bt.available(self.s,'1010','ALL','csv'));self.assertTrue(self.s['bank_statements'][0]['mapping_template']['active'])
        with self.assertRaises(ValueError):bt.resolve(self.s,t['id'],RAW,'bank.csv','1010','ALL')
    def test_layout_drift_wrong_bank_scope_and_kind_rejected_atomically(self):
        t=self.save();foundation.save_account(self.s,'1011','Second bank','Asset','Cash and bank');before=copy.deepcopy(self.s)
        for raw,name,account,scope in [(RAW.replace(b'Details',b'Description'),'bank.csv','1010','ALL'),(RAW,'bank.csv','1011','ALL'),(RAW,'bank.csv','1010','JP'),(RAW,'bank.xlsx','1010','ALL')]:
            with self.assertRaises(ValueError):bt.resolve(self.s,t['id'],raw,name,account,scope)
        self.assertEqual(self.s,before)
    def test_invalid_mapping_or_source_never_saves_or_supersedes(self):
        self.save();before=copy.deepcopy(self.s)
        for kwargs in [dict(mapping=dict(MAP,debit='In')),dict(mapping=dict(MAP,date='Missing')),dict(header_row=101),dict(date_format='MM/DD/YYYY'),dict(order='Unknown')]:
            with self.assertRaises(ValueError):self.save(**kwargs)
        with self.assertRaises(ValueError):self.save(RAW.replace(b'02/04/2026',b'bad-date'))
        self.assertEqual(self.s,before)
    def test_duplicate_or_normalization_ambiguous_headings_rejected(self):
        for raw in [b'date,date,amount\n2026-04-02,2026-04-02,10\n',b'date,Date,amount\n2026-04-02,2026-04-02,10\n',b'date,,amount\n2026-04-02,x,10\n']:
            with self.assertRaises(ValueError):bt.save(self.s,raw,'bank.csv','1010','ALL','Ambiguous')
        self.assertEqual(self.s['bank_mapping_templates'],[])
    def test_template_and_manual_options_cannot_conflict_and_balance_proof_still_required(self):
        t=self.save();before=copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError,'not both'):self.load(t,mapping=MAP)
        with self.assertRaisesRegex(ValueError,'closing balance'):self.load(t,closing='99')
        self.assertEqual(self.s,before)
    def test_overlap_reuse_and_file_duplicate_guards_survive_templates(self):
        t=self.save();first=self.load(t)
        with self.assertRaisesRegex(ValueError,'already imported'):self.load(t)
        second=self.load(t,RAW+b'03/04/2026,Another,R2,0,50,150\n',closing='150')
        self.assertEqual(first['row_ids'][0],second['row_ids'][0]);self.assertEqual(len(self.s['bank_lines']),2)
    def test_explicit_xlsx_sheet_header_and_newest_first_are_reused(self):
        w=Workbook();w.active.title='Ignore';ws=w.create_sheet('Statement');ws.append(['Bank header']);ws.append(['date','amount','reference']);ws.append(['03-04-2026',-20,'FEE']);ws.append(['02-04-2026',100,'RECEIPT']);out=io.BytesIO();w.save(out);w.close();raw=out.getvalue()
        t=bt.save(self.s,raw,'bank.xlsx','1010','JP','Excel bank',sheet='Statement',header_row=2,date_format='DD-MM-YYYY',order='Newest first')
        imported=r.import_statement(self.s,raw,'bank.xlsx','1010','JP','2026-04-01','2026-04-30','0','80',template_id=t['id']);self.assertEqual(imported['closing'],8000);self.assertEqual(self.s['bank_lines'][0]['reference'],'RECEIPT')
    def test_ofx_does_not_accept_layout_templates(self):
        with self.assertRaisesRegex(ValueError,'OFX'):bt.save(self.s,b'','bank.ofx','1010','ALL','OFX layout')
    def test_saved_layout_retains_bank_master_even_when_disabled(self):
        foundation.save_account(self.s,'1011','Unused bank','Asset','Cash and bank');t=bt.save(self.s,b'date,amount\n2026-04-02,10\n','bank.csv','1011','JP','Unused');bt.disable(self.s,t['id'],'Keep history');foundation.save_account(self.s,'1011','Unused bank','Asset','Cash and bank',active=False)
        with self.assertRaisesRegex(ValueError,'saved bank layout'):foundation.delete_account(self.s,'1011')
    def test_format_eleven_upgrade_backup_and_layout_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ext=root/'external';ext.mkdir();old=core.empty_state();old['version']=11;old['schema_revision']=11;old.pop('bank_mapping_templates');history.checkpoint(old);path=root/'old.json';path.write_text(json.dumps(old),encoding='utf-8');raw=path.read_bytes();v=Vault(path,demo=True);self.s=v.load();self.s['settings']['backup_dir']=str(ext);self.save();v.save(self.s)
            self.assertEqual(v.last_upgrade_backup.read_bytes(),raw);self.assertEqual(v.load(),self.s);self.assertEqual(self.s['version'],19)

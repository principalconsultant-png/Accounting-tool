import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from riju import core,foundation,history as h,reconciliation as bank
from riju.storage import Vault


def lines():return [dict(account='1010',branch='JP',debit=10000,credit=0),dict(account='4000',branch='JP',debit=0,credit=10000)]


class HistoryTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()

    def test_payload_snapshot_and_actor_are_not_aliased(self):
        payload={'new':{'amount':10}}
        with patch('getpass.getuser',return_value='Bookkeeper'):core.add_audit(self.s,'EXAMPLE',payload)
        payload['new']['amount']=99
        self.assertEqual(self.s['audit'][-1]['payload']['new']['amount'],10)
        self.assertEqual(self.s['audit'][-1]['actor'],'Bookkeeper');core.verify_audit(self.s)
        v=core.post(self.s,'2026-04-01','Receipt',lines());v['narration']='Changed'
        with self.assertRaises(ValueError):core.verify_audit(self.s)

    def test_sequence_must_be_contiguous_even_with_valid_rehashed_record(self):
        r=self.s['audit'][0];r['sequence']=99
        r['hash']=hashlib.sha256(json.dumps({k:v for k,v in r.items() if k!='hash'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'sequence'):core.verify_audit(self.s)

    def test_exact_before_after_and_removed_values(self):
        before=copy.deepcopy(self.s)
        foundation.save_entity(self.s,'Hospital books',{'tan':'BLRA12345B'})
        h.record_changes(before,self.s,'Entity setup')
        changes=self.s['audit'][-1]['payload']['changes'];name=next(x for x in changes if x['path']=='/settings/entity')
        self.assertEqual(name['before'],before['settings']['entity']);self.assertEqual(name['after'],'Hospital books')
        self.assertEqual(h.differences({'a/b':1},{}),[{'path':'/a~1b','change':'removed','before':1}])
        self.s['settings']['entity']='Later';self.assertEqual(name['after'],'Hospital books')

    def test_checkpoint_full_state_roundtrip_and_no_extra_unchanged_save(self):
        with tempfile.TemporaryDirectory() as d:
            v=Vault(Path(d)/'demo.json',demo=True);v.save(self.s)
            self.assertTrue(h.verify_saved_state(v.load()));count=len(self.s['audit'])
            v.save(self.s);self.assertEqual(len(self.s['audit']),count)
            self.s['settings']['entity']='Changed';v.save(self.s)
            self.assertEqual(v.load(),self.s);self.assertEqual(len(self.s['audit']),count+1)
            self.assertTrue(h.integrity_report(self.s)['passed'])

    def test_checkpoint_rejects_tampered_masters_and_bank_data(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'demo.json';v=Vault(p,demo=True);v.save(self.s);original=p.read_bytes()
            for section in ('settings','accounts','bank_lines'):
                state=json.loads(original)
                if section=='settings':state['settings']['entity']='Tampered'
                elif section=='accounts':state['accounts'][0]['name']='Tampered'
                else:state['bank_lines'].append({'id':'unrecorded'})
                p.write_text(json.dumps(state))
                with self.assertRaisesRegex(ValueError,'Saved books integrity'):Vault(p,demo=True).load()

    def test_failed_save_leaves_history_and_disk_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            v=Vault(Path(d)/'demo.json',demo=True);v.save(self.s);raw=v.path.read_bytes()
            self.s['settings']['entity']='New';before=copy.deepcopy(self.s)
            with patch('riju.storage.os.replace',side_effect=OSError('Drive unavailable')):
                with self.assertRaises(OSError):v.save(self.s)
            self.assertEqual(self.s,before);self.assertEqual(v.path.read_bytes(),raw)

    def test_legacy_actor_and_checkpoint_coverage_is_explicit(self):
        # Construct a valid old event, without inventing a user.
        r=self.s['audit'][0];r.pop('actor')
        r['hash']=hashlib.sha256(json.dumps({k:v for k,v in r.items() if k!='hash'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertFalse(h.verify_saved_state(self.s));self.assertIn('legacy',h.entries(self.s)[0]['actor'])
        self.assertEqual(len(h.integrity_report(self.s)['warnings']),2)

    def test_india_work_dates_action_and_search_filters(self):
        core.add_audit(self.s,'NOTE',{'text':'JP branch review'})
        r=self.s['audit'][-1];r['timestamp']='2026-04-01T20:00:00+00:00'
        rows=h.entries(self.s,'2026-04-02','2026-04-02','NOTE','jp')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['timestamp_india'],'2026-04-02T01:30:00+05:30')
        self.assertFalse(h.entries(self.s,'2026-04-01','2026-04-01','NOTE'))
        with self.assertRaises(ValueError):h.entries(self.s,'2026-04-02','2026-04-01')

    def test_draft_to_post_and_reversal_trace_preserve_original(self):
        d=foundation.save_draft(self.s,'2026-04-01','Receipt',lines())
        original=foundation.post_draft(self.s,d['id']);rev=core.reverse(self.s,original['id'],'2026-04-02')
        before=copy.deepcopy(self.s);trace=h.trace_voucher(self.s,original['id'])
        self.assertEqual(trace['drafts'][0]['draft_id'],d['id']);self.assertEqual(trace['reversals'][0],rev)
        self.assertEqual(h.trace_voucher(self.s,rev['id'])['original'],original)
        self.assertEqual(self.s,before);self.assertTrue(h.integrity_report(self.s)['passed'])

    def test_source_and_bank_trace_without_reposting(self):
        source={'kind':'journal_csv','document_id':'DOC-1','record_id':'2','row_count':1}
        self.s['queue'].append({'id':'DOC-1','filename':'test.csv','rows':[],'status':'PROCESSED'})
        v=core.post(self.s,'2026-04-02','Receipt',lines(),source=source)
        s=bank.import_statement(self.s,b'date,narration,reference,amount\n2026-04-02,Receipt,R1,100\n','bank.csv','1010','ALL','2026-04-01','2026-04-30','0','100')
        bank.match_existing(self.s,s['row_ids'],[v['id']+':0'])
        trace=h.trace_voucher(self.s,v['id'])
        self.assertEqual(trace['imports'][0]['filename'],'test.csv');self.assertEqual(len(trace['matches'][0]['bank_rows']),1)
        self.assertTrue(h.integrity_report(self.s)['passed'])
        self.s['matches'][0]['edges'][0]['book_key']='MISSING:0'
        self.assertFalse(h.integrity_report(self.s)['passed'])

    def test_readonly_exports_safe_csv_and_full_json(self):
        core.add_audit(self.s,'NOTE',{'id':'=formula','old':{'value':1},'new':{'value':2}})
        rows=h.entries(self.s);rows[0]['actor']='=HYPERLINK("bad")';before=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);h.export_rows(rows,p/'history.csv');h.export_rows(rows,p/'history.json','json')
            self.assertIn("'=HYPERLINK",(p/'history.csv').read_text(encoding='utf-8-sig'))
            self.assertEqual(json.loads((p/'history.json').read_text()),rows)
        self.assertEqual(self.s,before)

    def test_backup_inspection_and_restore_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);external=root/'external';external.mkdir()
            v=Vault(root/'books.json',demo=True);v.save(self.s);backup=v.backup(external)
            core.post(self.s,'2026-04-01','Receipt',lines());v.save(self.s)
            raw=v.path.read_bytes();inspected=Vault(backup,demo=True).load()
            self.assertTrue(h.integrity_report(inspected)['passed']);self.assertEqual(v.path.read_bytes(),raw)
            restored=v.restore(backup,external)
            self.assertFalse(restored['vouchers']);self.assertTrue(h.verify_saved_state(restored))
            self.assertIn('BACKUP_RESTORED',[a['action'] for a in restored['audit']])

    def test_startup_recovery_preserves_corrupt_file_and_validates_backup(self):
        from riju.history_ui import offer_integrity_recovery
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);external=root/'external';external.mkdir()
            v=Vault(root/'books.json',demo=True);v.save(self.s);backup=v.backup(external)
            corrupt=json.loads(v.path.read_text());corrupt['settings']['entity']='Unexpected edit'
            v.path.write_text(json.dumps(corrupt));original=v.path.read_bytes()
            broken=Vault(v.path,demo=True)
            try:broken.load()
            except ValueError as e:error=e
            with patch('riju.history_ui.messagebox.askyesno',return_value=True),patch('riju.history_ui.filedialog.askopenfilename',return_value=str(backup)),patch('riju.history_ui.filedialog.askdirectory',return_value=str(external)):
                self.assertTrue(offer_integrity_recovery(broken,error,None))
            loaded=broken.load();self.assertEqual(loaded['settings']['entity'],self.s['settings']['entity'])
            event=next(a for a in loaded['audit'] if a['action']=='BACKUP_RESTORED')
            self.assertEqual((external/event['payload']['safety_copy']).read_bytes(),original)
            self.assertTrue(h.verify_saved_state(loaded))

    def test_recovery_cancellation_and_non_integrity_errors_never_write(self):
        from riju.history_ui import offer_integrity_recovery
        with tempfile.TemporaryDirectory() as d:
            v=Vault(Path(d)/'books.json',demo=True);v.save(self.s);raw=v.path.read_bytes()
            with patch('riju.history_ui.messagebox.askyesno',return_value=False) as ask:
                self.assertFalse(offer_integrity_recovery(v,ValueError('another instance'),None));ask.assert_not_called()
                self.assertFalse(offer_integrity_recovery(v,ValueError('integrity failed'),None))
            self.assertEqual(v.path.read_bytes(),raw)

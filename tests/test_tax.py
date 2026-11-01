import copy
import json
from pathlib import Path
import tempfile
import unittest
from riju import core,foundation,tax,history
from riju.storage import Vault


def gst(**overrides):
    value=dict(family='GST',key='TEST-SERVICE',label='Invented test service',effective='2024-04-01',rate='18',treatment='Taxable',applicability='Synthetic taxable service for testing only',source='Invented test reference',reviewed=True,hsn_sac='999311',ledger_codes=['4000'])
    value.update(overrides);return value


def tds(**overrides):
    value=dict(family='TDS',key='TEST-194J',label='Invented professional fees',effective='2024-04-01',rate='10',treatment='Withholding',section='194J',party_category='Company',single_threshold='',annual_threshold='50000',threshold_basis='Financial-year aggregate',applicability='Invented test conditions, not legal guidance',source='Invented test reference',reviewed=True)
    value.update(overrides);return value


class TaxConfigurationTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def test_no_legacy_rate_implicitly_applies(self):
        self.assertEqual(tax.rules(self.s),[])
        with self.assertRaises(ValueError):tax.resolve_rule(self.s,'194J','2026-04-01')
        self.assertTrue(self.s['settings']['tax_rules'])
    def test_effective_versions_and_readonly_snapshots(self):
        old=tax.save_rule(self.s,gst());new=tax.save_rule(self.s,gst(effective='2025-04-01',rate='12'))
        self.assertEqual(tax.resolve_rule(self.s,'test-service','2025-03-31')['rate'],'18')
        self.assertEqual(tax.resolve_rule(self.s,'TEST-SERVICE','2025-04-01')['rate'],'12')
        self.assertEqual(tax.preview(self.s,'TEST-SERVICE','2024-05-01')['next_effective_date'],'2025-04-01')
        old['rate']='99';self.assertEqual(tax.rules(self.s)[0]['rate'],'18')
        self.assertNotEqual(old['id'],new['id']);core.verify_audit(self.s)
        copied=copy.deepcopy(new);copied['effective']='2026-04-01'
        self.assertIsNone(tax.save_rule(self.s,copied)['single_threshold'])
    def test_no_rule_before_effective_date(self):
        tax.save_rule(self.s,gst())
        with self.assertRaises(ValueError):tax.resolve_rule(self.s,'TEST-SERVICE','2024-03-31')
    def test_unreviewed_new_version_never_falls_back(self):
        tax.save_rule(self.s,gst());tax.save_rule(self.s,gst(effective='2025-04-01',rate='5',reviewed=False,source=''))
        p=tax.preview(self.s,'TEST-SERVICE','2025-05-01')
        self.assertEqual(p['rule']['rate'],'5');self.assertTrue(p['warnings'])
    def test_same_date_corrections_preserve_prior_version_and_family(self):
        first=tax.save_rule(self.s,gst());second=tax.save_rule(self.s,gst(rate='12'))
        self.assertEqual(second['revision'],2);self.assertEqual(tax.rules(self.s)[0],first)
        self.assertEqual(tax.resolve_rule(self.s,'TEST-SERVICE','2024-04-01')['id'],second['id'])
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):tax.save_rule(self.s,tds(key='TEST-SERVICE',effective='2025-04-01'))
        self.assertEqual(self.s,before)
    def test_invalid_tax_values_leave_books_unchanged(self):
        for extra in ({'rate':'NaN'},{'rate':'101'},{'rate':'-1'},{'rate':'1.12345'},{'hsn_sac':'ABC'},{'hsn_sac':'12345'},{'reviewed':True,'source':''},{'effective':'01/04/2024'},{'ledger_codes':['NOPE']},{'ledger_codes':'4000'},{'applicability':''}):
            with self.subTest(extra=extra):
                before=copy.deepcopy(self.s)
                with self.assertRaises(ValueError):tax.save_rule(self.s,gst(**extra))
                self.assertEqual(before,self.s)
    def test_distinct_zero_rate_treatments(self):
        for index,treatment in enumerate(tax.GST_TREATMENTS[1:]):
            rule=tax.save_rule(self.s,gst(key='ZERO-'+str(index),treatment=treatment,rate='0'))
            self.assertEqual(rule['treatment'],treatment)
        with self.assertRaises(ValueError):tax.save_rule(self.s,gst(rate='0'))
        with self.assertRaises(ValueError):tax.save_rule(self.s,gst(treatment='Exempt',rate='18'))
    def test_gst_and_tds_fields_cannot_be_mixed(self):
        for value in (gst(section='194J'),gst(single_threshold='100'),tds(hsn_sac='999311'),tds(treatment='Exempt'),tds(section='no')):
            with self.assertRaises(ValueError):tax.save_rule(self.s,value)
    def test_unknown_and_zero_thresholds_are_distinct(self):
        a=tax.save_rule(self.s,tds());self.assertIsNone(a['single_threshold'])
        b=tax.save_rule(self.s,tds(effective='2025-04-01',single_threshold='0'))
        self.assertEqual(b['single_threshold'],'0')
        with self.assertRaises(ValueError):tax.save_rule(self.s,tds(key='MISSING',annual_threshold=''))
        with self.assertRaises(ValueError):tax.save_rule(self.s,tds(annual_threshold='1.005'))
    def test_tds_not_applicable_requires_zero_rate(self):
        r=tax.save_rule(self.s,tds(treatment='Not applicable',rate='0'))
        self.assertEqual(r['rate'],'0')
        with self.assertRaises(ValueError):tax.save_rule(self.s,tds(key='BAD',treatment='Not applicable'))
    def test_party_details_optional_then_versioned(self):
        first=tax.save_party(self.s,dict(name='Test supplier',effective='2024-04-01',category='Unknown'))
        self.assertEqual(first['registration']['gstin'],'')
        second=tax.save_party(self.s,dict(name='Test supplier',effective='2025-04-01',category='Company',pan='ABCDE1234F',tan='BLRA12345B',state_code='29'),first['party_id'])
        self.assertEqual(tax.resolve_party(self.s,first['party_id'],'2024-12-01')['category'],'Unknown')
        self.assertEqual(tax.resolve_party(self.s,first['party_id'],'2025-04-01')['registration']['tan'],'BLRA12345B')
        second['registration']['tan']='changed';core.verify_audit(self.s)
    def test_party_gstin_state_and_pan_validation(self):
        for fields in ({'gstin':'bad'},{'state_code':'99'},{'pan':'bad'},{'tan':'bad'},{'gstin':'29ABCDE1234F1Z5','state_code':'32'},{'gstin':'29ABCDE1234F1Z5','pan':'ZZZZZ1234Z'}):
            before=copy.deepcopy(self.s)
            with self.assertRaises(ValueError):tax.save_party(self.s,dict(name='Test',effective='2024-04-01',**fields))
            self.assertEqual(before,self.s)
    def test_party_duplicate_missing_id_and_unknown_category(self):
        p=tax.save_party(self.s,dict(name='Test',effective='2024-04-01'))
        revised=tax.save_party(self.s,dict(name='Corrected test',effective='2024-04-01'),p['party_id'])
        self.assertEqual(revised['revision'],2)
        self.assertEqual(tax.resolve_party(self.s,p['party_id'],'2024-04-01')['name'],'Corrected test')
        for fields,pid in ((dict(name='Test',effective='2025-04-01'),'missing'),(dict(name='Test',effective='2025-04-01',category='Any'),None)):
            with self.assertRaises(ValueError):tax.save_party(self.s,fields,pid)
    def test_preview_flags_category_missing_pan_and_inactive_party(self):
        tax.save_rule(self.s,tds());p=tax.save_party(self.s,dict(name='Unknown supplier',effective='2024-04-01',active=False))
        before=copy.deepcopy(self.s);result=tax.preview(self.s,'TEST-194J','2024-05-01',p['party_id'])
        self.assertTrue(any('category' in x for x in result['warnings']));self.assertTrue(any('PAN' in x for x in result['warnings']))
        self.assertTrue(any('inactive' in x for x in result['warnings']));self.assertEqual(before,self.s)
    def test_linked_tax_ledger_cannot_be_deleted(self):
        foundation.save_account(self.s,'4595','Synthetic tax expense','Expense','Other expenses')
        tax.save_rule(self.s,gst(ledger_codes=['4595']))
        foundation.save_account(self.s,'4595','Synthetic tax expense','Expense','Other expenses',active=False)
        with self.assertRaisesRegex(ValueError,'tax rule'):foundation.delete_account(self.s,'4595')
    def test_export_keeps_versions_and_books_unchanged(self):
        tax.save_rule(self.s,gst());tax.save_rule(self.s,gst(effective='2025-04-01',rate='12'));before=copy.deepcopy(self.s)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tax.json';tax.export_config(self.s,p);data=json.loads(p.read_text());self.assertEqual(len(data['rules']),2)
        self.assertEqual(before,self.s)
    def test_format_four_upgrade_requires_original_external_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);external=root/'external';external.mkdir();s=copy.deepcopy(self.s)
            s['version']=4;s['schema_revision']=4;s.pop('tax_config');history.checkpoint(s)
            p=root/'old.json';p.write_text(json.dumps(s));original=p.read_bytes()
            v=Vault(p,demo=True);upgraded=v.load();self.assertTrue(v.migration_pending)
            self.assertEqual(upgraded['version'],17);self.assertEqual(upgraded['vouchers'],s['vouchers'])
            with self.assertRaises(ValueError):v.save(upgraded)
            self.assertEqual(p.read_bytes(),original)
            upgraded['settings']['backup_dir']=str(external);v.save(upgraded)
            self.assertEqual(v.last_upgrade_backup.read_bytes(),original)
            tax.save_rule(upgraded,gst());v.save(upgraded);self.assertEqual(v.load(),upgraded)
            self.assertTrue(history.verify_saved_state(upgraded))

import copy
import time
import unittest
from unittest.mock import patch
from riju import core,foundation,local_model as m,offline_language as lang

class LanguageTests(unittest.TestCase):
    def setUp(self):self.s=core.empty_state()
    def parse(self,text):return lang.interpret(self.s,text,'JP','2026-04-01')
    def test_entities_model_paraphrase_date_unit_party_reference_and_no_network(self):
        before=copy.deepcopy(self.s)
        with patch('socket.socket',side_effect=AssertionError('No network permitted')):
            p=self.parse('Settled monthly premises rental INR 5,000 to ABC Estates for the lease by NEFT at Kammanahalli on 18 June 2026 ref RENT-26')
        self.assertEqual((p['date'],p['branch'],p['party'],p['reference'],p['amount'],p['account']),('2026-06-18','KM','ABC Estates','RENT-26',500000,'4530'));self.assertEqual(before,self.s);self.assertIn('statistical topic',p['explanation'])
        p=self.parse('Collected INR 800 from Hema for outpatient consultation by GPay at Vaikom on 19/06/2026');self.assertEqual((p['party'],p['date'],p['branch'],p['account'],p['method']),('Hema','2026-06-19','VK','4000','1110'))
    def test_statistical_model_held_out_topics(self):
        # Evaluation phrases are not present as full phrases in the training corpus.
        cases={'monthly landlord rental premises':'4530','utility power electricity meter':'4540','maintenance plumbing upkeep servicing':'4550','monthly employee payroll wages':'4520','professional physician honorarium':'4510','merchant processing bank commission':'4560','new diagnostic medical apparatus':'1030','office chairs furniture desks':'1040','outpatient appointment consult':'service:consultation','vision screening examination':'service:eye_check','patient enrolment registration':'service:registration','nurse nursing care':'service:nursing','hospital inpatient room accommodation':'service:room_rent','patient diet meals food':'service:food','kalari training session':'service:kalari','swarnaprashna service fee':'service:swarnaprashna','resort hospitality stay':'4040','pharmacy retail prescription':'service:medicine_retail','therapy therapeutic panchakarma':'service:treatment','treatment medicines therapy':'service:medicine_treatment','miscellaneous patient charges':'service:misc','earned treatment payment receipts':'service:treatment_receipt','patient consumables supply':'service:consumables','duty physician rounds doctor':'service:duty_doctor'}
        for text,label in cases.items():self.assertEqual(m.predict(text)['intent'],label,text)
        self.assertIsNone(m.predict('unidentified thing zebras unknown')['intent'])
    def test_legacy_patient_actor_and_fifteen_services(self):
        for text in ['Medicines purchased from our Pharmacy by Patient Hema R in Cash INR1291','Received cash INR1291 from Patient Hema R for Medicines.']:
            self.assertEqual(self.parse(text)['account'],'4030')
        from riju.revenue import MODES
        phrases={'treatment':'therapy','consultation':'OPD','eye_check':'eye checkup','registration':'registration','medicine_retail':'pharmacy','medicine_treatment':'medicine for treatment','consumables':'consumables','room_rent':'room rent','nursing':'nursing charges','duty_doctor':'duty doctor charges','food':'food charges','swarnaprashna':'swarnaprashna','kalari':'kalari','treatment_receipt':'trtmt pymt recd','misc':'misc charges'}
        for key,*_ in MODES:self.assertEqual(self.parse('Received INR 100 '+phrases[key]+' by cash')['account'],self.s['revenue_mode_accounts'][key],key)
    def test_ambiguity_routes_and_adversarial_inputs_never_post(self):
        before=copy.deepcopy(self.s)
        for text in ['Paid INR500 rent and salary by bank','Received INR500 OPD and nursing by cash','Paid INR500 rent by bank and cash','Paid INR5000 rent plus INR200 electricity by bank','Did not pay INR500 rent by bank','Will pay INR500 rent by bank','Paid rent INR500 yesterday by bank','Received INR500 advance by cash','Paid INR500 rent net of TDS by bank','Received INR500 OPD including GST by cash','Paid INR500 CWIP by bank','Paid USD500 rent by bank','Paid INR500 unknown thing by bank','Paid INR500 rent by card','Received medicines INR500 from supplier by cash','Paid INR500 pharmacy to supplier by bank','Paid INR500 rent at JP Nagar and Vaikom by bank','Paid INR500 rent by bank 2026-04-02 and 2026-04-03','Paid INR1,00,0 rent by bank','Paid -INR500 rent by bank','Paid rent INR500 and 2 utilities by bank','Paid INR500 rent if approved by bank']:
            with self.subTest(text=text),self.assertRaises(ValueError):self.parse(text)
        self.assertEqual(before,self.s)
    def test_units_amounts_master_and_period_guards(self):
        self.assertEqual(self.parse('Paid 1.25 lakh medical equipment by bank')['amount'],12500000)
        self.assertEqual(self.parse('Paid INR1,25,000 medical equipment by bank')['amount'],12500000)
        self.s['account_details']['4530']['active']=False
        with self.assertRaises(ValueError):self.parse('Paid INR500 rent by bank')
        self.s['account_details']['4530']['active']=True;self.s['locked_through']='2026-04-01'
        with self.assertRaises(ValueError):self.parse('Paid INR500 rent by bank')
    def test_runtime_license_identity_and_cpu_budget(self):
        self.assertEqual(len(m.digest()),64);self.assertEqual(m.VERSION,'riju-intents-1');started=time.perf_counter()
        for _ in range(100):self.parse('Settled monthly premises rental INR5000 by bank')
        self.assertLess(time.perf_counter()-started,5,'Small offline CPU model should not need an accelerator')

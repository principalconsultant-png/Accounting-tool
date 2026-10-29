"""Patient purchases are hospital revenue, never hospital expenditure."""
import unittest
from riju import core

class PharmacyReceiptsTests(unittest.TestCase):
    def setUp(self): self.state=core.empty_state()
    def test_patient_descriptions_and_payment_methods(self):
        descriptions=[
            'Medicines purchased from our Pharmacy by Patient Hema R in Cash INR1291',
            'Received cash INR1291 from Patient Hema R for Medicines.',
            'Patient Hema R purchased medicines from our pharmacy paying cash INR1291',
            'Customer bought medicine for INR 1291 in cash',
            'Patient paid cash INR1291 for medicines',
            'Cash INR1291 paid by the patient for medicines',
            'Medicines sold to patient Hema R for INR1291 cash',
            'Pharmacy sale cash INR1291',
            'Received payment from patient for medicines cash INR1291',
            'Payment from customer for medicines cash INR1291',
        ]
        for branch in core.BRANCHES:
            for text in descriptions:
                for word,account in [('Cash','1000'),('UPI','1110'),('Card','1120'),('Bank','1010')]:
                    text_variant=text.replace('Cash',word).replace('cash',word.lower())
                    with self.subTest(branch=branch,text=text_variant):
                        before=len(self.state['vouchers'])
                        lines=core.parse_transaction(text_variant,branch,'2026-10-29',self.state)
                        self.assertEqual(lines,[dict(account=account,branch=branch,debit=129100,credit=0),dict(account='4030',branch=branch,debit=0,credit=129100)])
                        self.assertEqual(len(self.state['vouchers']),before,'Parsing must not post')
                        posted=core.post(self.state,'2026-10-29',text_variant,lines)
                        self.assertEqual(sum(l['debit']-l['credit'] for l in posted['lines']),0)
        core.verify_audit(self.state)
    def test_supplier_purchase_and_ambiguous_cases_not_sales(self):
        for text in [
            'We purchased medicines from supplier for cash INR1291',
            'Our pharmacy bought medicine from vendor for cash INR1291',
            'Received medicines from supplier for cash INR1291',
            'Medicines purchased for cash INR1291',
            'Patient bought medicine on credit INR1291 cash',
            'Patient returned medicine for cash INR1291',
            'Patient bought medicines cash INR1291 with GST',
            'Patient bought medicine INR1291',
            'Patient bought medicines with cash and card INR1291',
            'Patient bought medicines and paid doctor fees cash INR1291',
            'Patient bought medicine cash INR1291 and hospital paid supplier',
        ]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):core.parse_transaction(text,'JP','2026-10-29',self.state)
        self.assertFalse(self.state['vouchers'])

if __name__=='__main__':unittest.main()

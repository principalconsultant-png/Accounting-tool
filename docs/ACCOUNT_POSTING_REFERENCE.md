# Yathartha — Everyday Account and Posting Reference

Starter accounts verified against version 0.30.0-dev, 2 November 2026. This is a practical lookup for regular hospital/pharmacy bookkeeping. It is not a copy of your local Windows book: renamed/custom accounts can differ. The named journal preview shows the accounts in your actual book. Shared Patient A/C and generated revenue/project controls may use different codes if a code was already occupied.

## 1. Everyday accounts: choose the purpose first

| Code | Account name | Use it for |
| --- | --- | --- |
| 1000 | Cash | Actual physical cash received or paid |
| 1010 | Bank | Main bank; use the actual bank ledger if more than one exists |
| 1100 | Medicine inventory | Medicines purchased and held for later sale/use |
| 1110 | UPI settlement clearing | UPI collections not yet transferred to bank |
| 1120 | Card settlement clearing | Card collections not yet transferred to bank |
| 1140 | Other receipts clearing | Unresolved Other payment source; do not assume bank |
| 1150 | Patient A/C (starter shared control) | Separate patient billing/collection, not each patient's own account |
| 2000 | Trade payables | Vendor invoices owed and subsequently settled |
| 2300 | Patient/package advances | Unearned deposits pending delivery of services |
| 4500 | Medical consumables | Medical supplies/stock consumed in treatment or operations |
| 4510 | Doctor professional fees | Expense for doctors' professional services |
| 4520 | Employee benefits | Salaries/wages and reviewed employee-benefit expense |
| 4530 | Rent | Hospital/office rental expense |
| 4540 | Utilities | Electricity, water and related utility expense |
| 4550 | Repairs and maintenance | Routine repair/maintenance expense, not a new capital asset |
| 4560 | Bank and payment processing charges | Bank/provider fees; account for fee GST separately where appropriate |
| 4570 | Depreciation | Book depreciation expense from the reviewed asset workflow |
| 4580 | Finance costs | Interest/finance expense, not loan principal repayment |
| 4590 | Administration | Genuine office/admin costs; not medicine purchases or a balancing plug |
| 4600 | Medicine cost of sales | Cost of medicines sold, not their selling price |
| 4610 | Income tax expense | Reviewed income-tax provision/expense, not GST or TDS withheld |
| 1030 | Medical equipment | Capitalised medical equipment |
| 1040 | Furniture and fixtures | Capitalised furniture/fixtures |
| 1050 | Accumulated depreciation | Cumulative depreciation credited by book asset journals |
| 2400 | Bank loans | Loan principal liability; keep interest separate |
| 3000 | Capital | Owner/share capital according to the reviewed entity setup |
| 3100 | Retained earnings | Prior accumulated results/closing transfers, not current sales |

For your medicine vendor invoice, use 1100 Medicine inventory as the cost/asset debit, not 4590 Administration. Vendor liability is 2000 Trade payables. A separate Purchase ledger is not required for this inventory method. Eligible input GST, if applicable, is recorded separately; ineligible tax follows the reviewed inventory/cost treatment.

## 2. Regular transactions: which account to debit and credit

The entries below show the core accounts before any separately applicable GST/TDS, retention, discounts or other allocations. Use the dedicated tax/source modules when those apply. Do not post an expense again when settling an invoice already accrued.

| Transaction | Debit | Credit | Screen / important check |
| --- | --- | --- | --- |
| Receive vendor invoice for medicines kept in stock | 1100 Medicine inventory | 2000 Trade payables | AP Vendor Invoices; taxed source first through GST as appropriate, then link once |
| Pay that medicine/vendor invoice | 2000 Trade payables | 1010 Bank or 1000 Cash | AP → select invoice → Mark selected invoices paid; actual payment date/amount |
| Sell medicines and collect immediately | Actual collection: 1000/1010/1110/1120 | 4030 Pharmacy sales | Sales receipt/import for supported earned receipts; appropriate GST workflow for taxable splits |
| Recognise cost of medicines sold | 4600 Medicine cost of sales | 1100 Medicine inventory | Reviewed journal from stock/dispensing records at COST, not sale value |
| Issue stocked medicines/supplies for treatment consumption | 4500 Medical consumables | 1100 Medicine inventory | Reviewed journal at issued stock cost; do not also expense the same stock through 4600 |
| Receive rent invoice, not yet paid | 4530 Rent | 2000 Trade payables | AP; separately review GST/TDS applicability |
| Receive electricity/water invoice | 4540 Utilities | 2000 Trade payables | AP, then settle payable on payment |
| Receive routine repairs invoice | 4550 Repairs and maintenance | 2000 Trade payables | AP; distinguish repair from capital addition |
| Receive doctor professional-service invoice | 4510 Doctor professional fees | 2000 Trade payables, with separate withholding control if applicable | TDS/source workflow where required; AP registers only net vendor payable |
| Pay salary immediately, not previously accrued | 4520 Employee benefits | 1010 Bank | Journal; split actual deductions/liabilities where applicable. If accrued earlier, settle the salary-payable ledger instead, not expense again |
| Bank fee already debited by bank, not previously recorded | 4560 Bank and payment processing charges | 1010 Bank | Reviewed bank adjustment/journal; separately review fee tax |
| Routine office/admin vendor bill | 4590 Administration | 2000 Trade payables | AP; use only for genuine administration |
| Buy medical equipment on credit | 1030 Medical equipment | 2000 Trade payables | Reviewed accrual/AP; register/link asset once in Assets & depreciation |
| Buy furniture on credit | 1040 Furniture and fixtures | 2000 Trade payables | Reviewed accrual/AP; apply asset review, not duplicate purchase entry |
| Post book depreciation | 4570 Depreciation | 1050 Accumulated depreciation, or configured asset control | Assets & depreciation; do not duplicate its posted depreciation manually |
| Receive bank loan principal | 1010 Bank | 2400 Bank loans | Reviewed journal; loan is not sales income |
| Repay bank loan principal | 2400 Bank loans | 1010 Bank | Reviewed journal; principal is not expense |
| Pay loan interest not already accrued | 4580 Finance costs | 1010 Bank | Reviewed journal; settle interest payable instead if already accrued |
| Collect an unearned package advance | Actual cash/bank/clearing account | 2300 Patient/package advances | Service revenue → Advance; not earned sales yet |
| Earn an existing advance | 2300 Patient/package advances | Correct service revenue account | Service revenue → Earn advance; original tax/source controls retained |
| Raise a separate unpaid patient bill | Shared Patient A/C (starter 1150) | Correct service revenue account | Service revenue → Bill |
| Collect that previously raised bill | Actual cash/bank/clearing account | Shared Patient A/C (starter 1150) | Service revenue → Collect bill; do not credit revenue a second time |
| UPI provider transfers collections into bank, no fees | 1010 Bank | 1110 UPI settlement clearing | Bank reconciliation → Review UPI/card/cash settlement; not another sale |
| Card provider transfers collections into bank, no fees | 1010 Bank | 1120 Card settlement clearing | Same settlement workflow; review real provider fees separately |
| Deposit physical cash into bank | 1010 Bank | 1000 Cash | Cash deposit/transfer; no income or expense |
| Withdraw bank money for physical cash | 1000 Cash | 1010 Bank | Transfer/journal; no expense merely because money left bank |

Inventory warning: a sales receipt records revenue and collection. It does not by itself establish medicine quantity, purchase cost or the cost of stock sold/consumed. Use actual stock records and a reviewed cost journal; do not subtract the customer selling price from 1100. This tool's current inventory ledger is not a full batch/expiry/quantity stock system.

Worked example: medicine invoice INR 11,923 with no separate tax allocation is Dr 1100 / Cr 2000 for 11,923. Full later bank payment is Dr 2000 / Cr 1010 for 11,923. The payment does not debit inventory or administration again. If medicines costing 2,000 are later sold for 3,000 without a separate tax split, the collection/sale credits 4030 for 3,000 and the separate cost journal is Dr 4600 / Cr 1100 for 2,000. The medicine margin in that example is 1,000 before other expenses.

## 3. Sales categories: which revenue account to credit

For earned receipts, debit the ACTUAL collection account: 1000 Cash, 1010 actual main-bank receipt, 1110 UPI clearing or 1120 Card clearing. Split across accounts when the receipt has mixed payment methods. Other source stays in its configured clearing account (starter 1140) until identified. Credit the appropriate category below; the imported standard table resolves these through the book's saved service mappings.

| Code | Revenue account / source category |
| --- | --- |
| 4000 | OPD consultation revenue |
| 4010 | Therapy / Treatment revenue |
| 4020 | IPD room revenue / Roomrent |
| 4030 | Pharmacy sales / Medicine Retail |
| 4050 | Eye check-up revenue |
| 4060 | Registration revenue |
| 4070 | Treatment medicine revenue / Medicine Treatment |
| 4080 | Consumables revenue charged to patients |
| 4090 | Nursing charges revenue |
| 4100 | Duty doctor charges revenue |
| 4110 | Patient food revenue charged to patients |
| 4120 | Swarnaprashna revenue |
| 4130 | Kalari revenue |
| 4140 | Treatment receipts — earned services / Trtmt Pymt RECD |
| 4150 | Miscellaneous patient charges revenue |
| 4040 | Resort service revenue (separate resort category) |

Do not confuse 4080 Consumables REVENUE with 4500 Medical consumables EXPENSE. The legacy source heading Food expenses maps to patient food REVENUE 4110 when it is a patient charge; the hospital's own kitchen costs require an appropriate expense ledger, not a debit to 4110. Likewise, doctor fees charged to a patient (4100) are different from doctor fees paid by the hospital (4510). An advance is 2300, not 4140 simply because the source says treatment payment.

## 4. Tax, project and control accounts: use the reviewed workflow

| Code | Account | Use / safeguard |
| --- | --- | --- |
| 1200 / 1210 / 1220 | Input CGST / SGST / IGST | Purchase input tax only after reviewed applicability/eligibility; not every tax amount is available ITC |
| 2200 / 2210 / 2220 | Output CGST / SGST / IGST | Tax on taxable sales according to the actual source and reviewed rule |
| 2100 / 2110 / 2120 | TDS payable — 194J / 194C / 194I | Starter controls only; use the accountant-reviewed section/rule, not an assumed section from the name |
| 2010 | Contractor retention | Amount withheld for later contractual release; actual project may use its configured control |
| 1020 | Vaikom resort CWIP (starter aggregate) | Use CWIP module's actual project/category ledgers for project costs; do not default every cost to this aggregate |
| 1130 | Inter-branch clearing | Genuine cross-unit funding/charges; each unit must balance and entity clearing must reconcile |

Tax/control ledgers can be created or mapped by their modules, so use their configured accounts and source previews rather than overwriting an existing control. No GST/TDS rate, legal applicability or ITC entitlement is implied by this list. Salary accruals need a dedicated reviewed salary-payable liability if used; that is not supplied as a fixed starter code here, and employee payroll should not be disguised as a vendor invoice.

Daily check before approving: correct unit; actual accounting date; invoice/reference; correct account NAME beside the code; balanced debit/credit; tax/source reviewed; no duplicate accrual/payment. Payments settle the balance already recorded; transfers are not income/expense; stock issues use cost. If the preview account name does not match this reference because your master was customised, stop and use the actual reviewed mapping.

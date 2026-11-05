# Salary and PF — separate ledgers and posting guide

Employee benefits is a valid P&L report group. The original 4520 Employee benefits ledger is broad; separate salary and PF ledgers provide posting detail without changing that overall financial classification. Employee PF deducted from gross salary is a payable, not an additional employer expense. Employer PF is an additional expense and a separate payable until remitted.

## Set up the five ledgers

Open Chart of accounts → Set up salary & PF ledgers. Each role can create a new dedicated ledger or use an explicitly reviewed existing eligible ledger. Review the setup basis, tick confirmation, Preview ledger setup, inspect the proposed account codes/names and Confirm ledger setup.

| Role | Preferred code when free | Classification / report group | Purpose |
| --- | --- | --- | --- |
| Salaries and wages | 4521 | Expense / Employee benefits | Gross salary expense for the earned period. |
| Employer PF contributions | 4522 | Expense / Employee benefits | Employer's own PF cost, not the employee withholding. |
| Salaries payable | 2310 | Liability / Other liabilities | Net salary owed to staff after the reviewed deductions. |
| Employee PF deductions payable | 2311 | Liability / Other liabilities | Employee share withheld from gross salary, awaiting remittance. |
| Employer PF contributions payable | 2312 | Liability / Other liabilities | Employer share accrued, awaiting remittance. |

Codes are not universal. If a client already uses a proposed code, setup selects a free code rather than overwriting or renaming it. The preview gives the actual codes to use. Exact existing matching names can be proposed for review; custom/combined PF accounts are not automatically split. The five roles must use distinct active ledgers. Setup creates/maps masters only: no JE, balance, historical reclassification or PF calculation is posted. Existing 4520 and its entries stay intact. Mapped ledgers retain their required group/activity until the role is remapped.

## Accrue salary and PF once

Use the approved payroll and earned-period accounting date. The following figures are illustrative reviewed amounts, not assumed statutory rates or a calculation engine: gross salary INR 10,000; employee PF withheld INR 1,000; net salary INR 9,000; employer PF INR 1,200. Other deductions are assumed absent only for this example.

1. Journal studio: debit Salaries and wages 10,000; credit Salaries payable 9,000; credit Employee PF deductions payable 1,000. Preview and approve the balanced payroll journal.
2. Journal studio: debit Employer PF contributions 1,200; credit Employer PF contributions payable 1,200. Preview and approve. This can instead be part of one correctly balanced compound payroll voucher.
3. When the bank pays net salary: debit Salaries payable 9,000; credit the actual Bank 9,000 on the actual payment date. If that bank JE already exists, match it rather than post it again. Record bank transaction → Standing instruction / other payment can settle the reviewed salary payable; the original expense is not repeated.
4. When PF is remitted: debit Employee PF deductions payable 1,000 plus Employer PF contributions payable 1,200; credit Bank 2,200. Use a compound Journal studio entry because the payment clears two liabilities. Then reconcile the one bank withdrawal to its existing book movement using All book movements.

Total booked payroll Opex in this example is 11,200 (gross salary 10,000 plus employer PF 1,200), not 12,200. The employee share is already included in gross salary. Total cash paid is 9,000 salary plus 2,200 PF, potentially on later dates. After both payments all three payables are zero, assuming no other opening/current transactions.

Salary paid before a prior accrual can use a reviewed direct expense/bank entry only where appropriate to the earned period and actual gross/net facts; do not infer gross payroll from the net bank statement. If deductions apply, record their liability splits. Salary accrual, salary payment and PF remittance must not each be expensed as if they were independent costs.

PF amounts, EPS allocation, EDLI/administration charges, applicable wage caps/rates and remittance details must come from the approved payroll/ECR/challan review. The setup does not calculate PF, file returns or infer eligibility. Add/review separate additional ledgers/splits for ESI, salary TDS under Section 192 and other applicable deductions/costs. Existing professional TDS 194J/194C/194I ledgers are not automatically salary TDS accounts.

## Reconcile and report

Post approved payroll/accruals first, then record actual payments and match their bank movements. In Bank reconciliation → Reconcile side by side choose All book movements to see salary/PF JEs; these are not vendor Invoice payments. Journal studio/payment approval posts accounting entries; matching existing entries creates links only. Do not put the full PF bank remittance into Employer PF expense, Employee benefits or a generic compliance expense when the liabilities were already accrued.

Daily Business Register automatically includes the two booked Expense ledgers in Opex, on their accrual dates. Salary/PF liability settlements are not additional Opex. Rebuild the database if its snapshot is stale after setup/posting.

Business Pulse: Review ledger mappings before using Salary disbursed. Select the actual salary expense and net-salary-payable ledgers as appropriate for the source workflow; keep employer PF expense and both PF payables out of Salary disbursed. The example produces salary cash disbursed 9,000, not 11,200. Keep overtime sources separate and use distinct payable/source allocations where overtime was accrued separately; a combined payroll liability cannot identify an overtime split automatically. Existing reviewed report mappings are not silently changed by account setup.

New ledgers are designated Operating for cash-flow setup. If a reviewed cash-flow policy already exists, update/review its mappings for the new payroll/payable accounts before relying on the direct cash-flow report. Trial balance, ledger, P&L and balance sheet use the new expense/liability classifications automatically.

New simple salary drafts use the configured salary expense instead of 4520. If a salary liability already exists for the unit/date, automatic salary-expense drafting asks for manual settlement review. Descriptions containing PF/ESI or payroll deductions require compound manual review; the tool does not guess a gross/net split.

## Existing entries in 4520

Review the original payroll evidence before moving earlier entries. If an amount is a genuine salary expense already included in 4520, a reviewed reclassification can debit the dedicated salary expense and credit 4520 in the correct open period, leaving total expense unchanged. Mixed benefits, employee/employer PF, net bank payments and salary settlements need the actual payroll breakup before deciding the correction. Do not post the original salary again or rename a mixed-use ledger to make all historical entries appear to be salary. Closed periods and matched bank entries retain their existing correction/reopening safeguards.

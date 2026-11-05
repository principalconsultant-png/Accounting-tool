# Journal studio — bulk JEs and monthly salaries

Journal studio now has Upload bulk JEs, Upload monthly salary JEs and JE templates / saved batches. Use the salary template for one total monthly accrual per operating unit plus several actual salary-payment rows. No employee-level accrual split is required. General JE imports remain available for reviewed compound journals and other purposes.

## Salary template fields

Download Salary XLSX or Salary CSV from JE templates / saved batches. Excel sheet name is Salary Journals; preserve all ten headings. Blank templates contain no synthetic transactions. The Excel template exported within the app includes the current ledger/unit lookup; the public blank template contains no client data.

| Heading | ACCRUAL row | PAYMENT row |
| --- | --- | --- |
| Entry Type | ACCRUAL | PAYMENT |
| Salary Month YYYY-MM | Earned month, e.g.2026-04 | Same earned month being settled, even when paid in May |
| Operating Unit | Actual active unit code, e.g.JP | Same unit as the corresponding accrual |
| Entry Date | Blank defaults to month end; or actual reviewed accrual date within the earned month | Actual bank/cash payment date, required |
| Reference | Blank generates SAL-ACCR-YYYY-MM-UNIT, or provide a stable accrual reference | Actual bank transfer/UTR reference, required; preserve leading zeros as text |
| Bank Ledger | Leave blank; not used | Actual active INR bank/cash code, e.g.1010 |
| Amount INR | Total reviewed salary accrual for this month/unit | Amount actually paid in this transfer; positive number |
| Existing Voucher (optional) | Exact already-posted accrual voucher to link instead of creating another | Exact already-posted salary-payable/bank payment voucher to link instead of paying again |
| Payee (optional) | Optional payroll description | Employee/batch description to help identify the bank transfer |
| Accounting Review Basis | Source payroll review and no-deduction basis | Bank evidence/payment approval basis |

Before upload, use Chart of accounts → Set up salary & PF ledgers to review the salary expense and salary-payable roles. These actual mapped accounts are used automatically; the salary template does not require ledger codes for every accrual. PF is not currently part of this simple payroll format. Where PF/ESI/TDS/other deductions apply, do not put net pay into a gross salary accrual or leave deduction balances unexplained: use the reviewed general compound JE/manual payroll workflow and correct liability splits.

## Example: monthly total and several payments

Assume approved April salary with no deductions is INR 30,000. Enter one ACCRUAL row for 2026-04 / JP /30,000. The default accrual date is 30 April 2026. Enter three PAYMENT rows for the same earned month/unit, each 10,000, with their actual bank dates, actual bank ledger and separate real transfer references. Payments may be to different employees or batches.

Final approval posts:

- On 30 April: Dr Salaries and wages 30,000 / Cr Salaries payable 30,000.
- On each actual payment date: Dr Salaries payable 10,000 / Cr actual Bank 10,000, with that payment reference.

This produces four JEs, not one fictitious month-end bank payment. If only 25,000 is actually paid,5,000 remains payable. Accrual is an earned-period expense; payments do not expense the salary again. Use one ACCRUAL row for each additional month/unit; the same file can cover all seven historical months. All dates come from the source file, not today's Journal studio date.

For same-month salaries paid early, keep actual payment dates and the genuine month-end accrual. Choose **Yes** at the early salary payments prompt. The importer creates a separate collision-safe **Salary advances** asset ledger if needed, then proposes Dr Salary advances / Cr Bank on early payment dates, the normal month-end Dr Salaries and wages / Cr Salaries payable accrual, and Dr Salaries payable / Cr Salary advances on the accrual date. These extra application journals appear in the final preview. Choosing No retains normal payable settlement checks. Upload never posts financial journals. Do not move earned months or backdate accruals to bypass validation.

Entry Date accepts real Excel dates, ISO YYYY-MM-DD, or day-first text DD/MM/YYYY and DD/MM/YY (two-digit years mean 20xx). For example, 05/04/26 means 5 April 2026. Invalid calendar dates remain flagged with a reason. Existing invalid unposted batches can be cancelled with a reason, then the original workbook uploaded again.

For the early-payment example, three April payments plus one April accrual create five journals: three actual bank payments, one accrual and one advance application. Expense arises once at month end. Part-paid amounts stay payable; early transfers stay in advances until the accrual/application date. Reverse the application before reversing an early payment; reverse dependent payments/applications before reversing the accrual.

## Upload, review and post

1. Journal studio → Upload monthly salary JEs → choose the XLSX/CSV file. Upload stores a pending source batch; no accounting entry is posted.
2. Inspect each row's type, earned month, date, unit, accounts, amount, existing voucher, review status and reason. Invalid/duplicate rows are highlighted. Select a row to read its complete reason.
3. Correct the source where necessary and cancel an unused batch before restaging. Reject unwanted/flagged rows with a reason. Do not reject an actual missing accrual and then approve its payments without a valid existing monthly accrual/link.
4. Enter the review basis and tick the source confirmation, including no PF/other deduction splits for the simple salary template. Approve all valid rows or selected rows. Row approval is a review decision, not posting.
5. Preview reviewed journals. Posting order is chronological, with accruals before payments on the same date, regardless of the file's row order. All proposed journals and existing links must pass monthly and actual payable capacity checks. A failure saves none of the selected postings; the message identifies the issue/source row where applicable.
6. Inspect the complete preview. Confirm post reviewed JEs to save the approved batch. The pending manual Journal studio draft is preserved rather than overwritten by the bulk workflow.
7. Verify salary expense, salary payable and bank in Ledger A/c. For bank reconciliation select All book movements and match the dated salary payment JEs to actual bank withdrawals. Upload/posting does not import bank statements or automatically match them.
8. Rebuild any stale Daily Business Register and review Business Pulse salary mappings. Opex recognises the accrual once; early payments move through salary advances and normal payments clear liabilities. Known salary-import bank transfers count once in Business Pulse salary disbursed when salary mappings are configured. Report dates and unit selections remain relevant.

## Existing entries and duplicate safeguards

If an accrual or salary-payable payment already exists, supply its exact Existing Voucher, actual date, unit and amount. The accounts must match the reviewed salary roles; an existing payment must use the actual bank/reference. Eligible existing sources are linked with no new JE, including earlier general bulk sources. The source is not allowed to be registered twice.

An existing direct Dr Salary expense / Cr Bank payment is not an accrual-plus-payable settlement. Review/reclassify that original transaction appropriately before creating another salary accrual and payment; linking it as a salary-payable settlement would be incorrect. Legacy 4520 Employee benefits entries also need source-based review; the tool does not infer their salary content from narration.

Only one active monthly total accrual per unit is allowed. Pending/posted source identities, changed-file reimports and active existing bank references are checked. Payments cannot exceed the earned month's reviewed accrual; ordinary payable settlements also require a dated accrual, even if another month has an unpaid balance; actual salary-payable capacity is also checked so unlinked manual payments do not get paid again. A repeated file does not append the same payroll twice.

Do not change references, earned months or amounts to bypass validation. Correct the original source. Reverse dependent tagged payments before reversing their supporting salary accrual; original journals and audit history are retained. Opening salary liabilities and complex historical corrections require the reviewed opening/general journal workflow, not a new current-period salary expense.

## General bulk JE format

Upload bulk JEs uses CSV or an Excel sheet named Journals. Columns: date, reference, branch, narration, debit_account, credit_account, amount, journal_id. Each row supplies one balanced debit/credit pair with a positive INR amount. Use actual active ledger/unit codes and literal values, not formulas. Each source line needs a unique reference.

The optional journal_id combines rows with the same date/unit into one compound voucher, such as reviewed gross payroll/deduction allocations. All rows in a compound group must be approved consistently; a partially rejected group cannot post. General imports do not infer tax/payroll splits or automatically detect every pre-existing manually posted expense. Review source purpose and use dedicated AP/tax/receipt workflows for controlled allocations.

General and salary batches use the same Journal studio review and frozen final-confirmation preview. Saved batches can be reopened from JE templates / saved batches or the existing Bulk import review page. General templates, salary templates and this guide are included with the documentation bundle. Synthetic worked examples are labelled separately and must not be uploaded as live client transactions.

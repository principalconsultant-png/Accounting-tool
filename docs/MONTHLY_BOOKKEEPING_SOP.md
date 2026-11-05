# Monthly Bookkeeping SOP — Yathartha

Applies to Yathartha 0.38.1-dev and the controls currently available. Inputs: Daily Sales Receipt report, vendor Invoice report and Bank statement. Obtain payroll, petty-cash, loan and other supporting information where the bank statement alone does not establish the accounting purpose. Process the earliest incomplete month first, then move forward chronologically.

## Monthly route at a glance

| Stage | User action | Result |
| --- | --- | --- |
| Source control | Check dates/units/totals, opening position and missing evidence | No monthly JE; approved initial openings are a separate one-time posting. |
| Sales | Upload → validate → approve rows → preview → approve sales batch | Earned-revenue and collection-method JEs; ledgers updated. |
| Invoices | Upload → review accounts/tax → approve → preview → approve AP action | Expense/stock/asset and payable accruals; unpaid vendor balances created. |
| Payroll / petty cash | Review earned-period payroll and actual petty items; preview and post | Salary/expense/asset/liability entries according to purpose; no double expense. |
| Bank statement | Import and approve correct bank/period/balances | Statement source rows only; no accounting JE. |
| Vendor payments | Record actual date, bank, amount and invoice allocation once | Payable reduces; bank credits. Existing exact payments are linked instead. |
| Reconciliation | Match existing entries; review any missing settlement, payment or charge | Existing matches: links only. Confirmed new settlements/adjustments: previewed JEs plus match. |
| Bank-only items | Obtain purpose/evidence; choose treatment; preview and confirm | New salary/cash/loan/fee/transfer JE only if not already recorded. Unknowns remain queried. |
| Month-end | Review ledgers, AP/payroll/cash controls, BRS and reports | Corrections where needed; approved BRS completion locks the bank period. |
| Handover | Refresh daily register; export reviewed reports; create dated backup | Derived database and files; no new transaction JE. |

## 1. Operating rules and responsibilities

Books continue month on month within the same financial year. Starting the next month does not require a backup, new books, a restore, reset or fresh opening balances. Backups are for recovery and are recommended regularly, particularly after significant posting/month-end review; they are not an application gate to the next month. A completed bank period can be locked while the following month remains available.

The preparer checks source completeness, uploads, reviews, posts and reconciles. The owner/client confirms the business purpose, missing evidence and payment details. The reviewer verifies accounting, tax, bank reconciliation and month-end reports before completion. If one person performs several roles, retain the review basis and sign-off record.

JE means journal entry. Posting a balanced JE updates the ledgers; those posted ledger records feed the trial balance, P&L, balance sheet and management reports. A preview is not a posted JE. Uploading a report is not the same as posting it. Reconciliation of existing entries creates match links, not another expense or receipt. Actions that propose a new settlement/payment/charge must be reviewed and confirmed before they post.

Use the date the business transaction actually occurred, not the date you are entering it. Salary accrual uses the period earned; payment uses the actual payment date. Record invoice accounting dates in the correct period. Payment due dates and scheduled dates are not evidence of an actual bank payment. A displayed future financial-year date must be corrected before approval.

Never post the same receipt, purchase or payment twice because it appears in two reports. A supplier invoice and its bank payment are different stages of one payable. A sales receipt and its UPI/card bank settlement are different stages of one collection. Matching similar amounts alone does not establish the business purpose.

## 2. One-time setup before the first month

1. Back up the current books through Settings & backup. Retain the .riju file in a dated external backup folder. Existing Windows-protected books/backups remain tied to the originating Windows account/computer; do not assume a .riju file is an Excel report or a portable cross-computer backup.
2. Confirm entity, financial year, operating units and the actual bank ledger for each bank account. If the client has two bank accounts, keep two distinct bank ledgers and statements. Select units consistently in every source.
3. Review the opening trial balance at the bookkeeping start date. Include bank, physical cash, outstanding vendor invoices/payables, loan principal, stock, receivables, salary liabilities, tax balances and capital as applicable. Review any necessary opening invoice/source links so individual balances agree with the opening trial balance.
4. Enter approved opening balances once through the opening-balance workflow in Setup & periods. Do not add an opening voucher every month, add another loan opening on top of an existing one, or create current-year expense for an opening payable. Previous months carry forward automatically. The tool requires initial openings dated 1 April; if takeover is later in the year, agree the opening/history approach with the reviewer before posting.
5. Confirm Chart of accounts and Vendor master. Typical existing ledgers: 1000 Cash, 1010 Bank, 1100 Medicine inventory, 1110 UPI clearing, 1120 Card clearing, 2000 Trade payables, 2400 Bank loans, 4520 Employee benefits, 4560 Bank/payment-processing charges and 4580 Finance costs. Use the actual client bank/payable codes where different.
6. Create dedicated ledgers when genuinely needed: salaries payable under Other liabilities, staff advances and loans receivable under Other assets, and the appropriate owner/director current/drawings account for the legal entity. Do not invent or assume that an example custom ledger code already exists. Separate salary/overtime ledgers support a reliable management-report split.

Outcome: a reviewed starting position, correct masters and a recoverable backup. Master creation itself does not post an expense or payment. Initial opening approval posts balance-sheet opening entries; it is not current-month revenue/Opex.

## 3. Receive and control the monthly sources

Keep an unchanged copy of each original source and a separate import-ready copy. Maintain a source-control log with month, unit, filename, period, row count, amount/control totals, uploaded batch, posted voucher references, exceptions and reviewer.

| Source | Checks before upload | Additional evidence required |
| --- | --- | --- |
| Daily Sales Receipt | Every date/unit; receipt numbers; revenue totals; Cash/UPI/Card/other/bank splits; duplicates; refunds/advances and tax treatment | Explanations for missing dates, mismatched totals, advances/refunds, unusual adjustments and separate GST/TDS |
| Vendor Invoice report | Vendor, unique invoice reference, invoice/received/accounting dates, unit, amount, ledger and payment terms | Original invoices and tax review; identify expense versus stock/asset and invoices already paid |
| Bank statement | Correct bank, full period, opening/closing balances, dates, debit/credit signs and transfer references | Payroll, lender breakup, fee advice/tax invoices, cash movement records, employee advances and explanations of unknown transfers |
| Payroll and petty cash | Earned month, gross/net pay/deductions; approved petty items and cash custody/funding | Payroll approval/payment evidence; original bills or an approved alternative expense record; cash count |

Do not treat a bank narration as a salary register, a lender principal/interest schedule or a valid GST invoice. Mark missing information in the exception log and request it from the client.

## 4. Post the Daily Sales Receipt report

1. Open Sales receipt and use its standard Excel/CSV template. Preserve required headings and text receipt numbers. Map source payment methods correctly; a UPI collection is not already a bank settlement.
2. Import the month/unit report and open its review. Upload stages source rows only: no sales JE or ledger movement yet.
3. Compare row counts, valid-source totals and payment splits to the original report. Inspect INVALID/DUPLICATE reasons. Correct and re-upload a corrected source where required; explicitly reject unwanted/duplicate rows. Rejected rows remain excluded and need follow-up if they represent a genuine missing transaction.
4. For the standard earned-receipt import, confirm earned services, actual payment splits and the reviewed no-separate-GST/TDS treatment. Do not approve advances/refunds or taxable splits as ordinary earned no-tax sales. Use Service revenue/GST workflows for those cases.
5. Tick the review confirmation, choose Approve all valid rows or Approve selected rows and enter the review basis. Row approval records the decision; it is not the final posting.
6. Choose Preview batch journals. Inspect date, unit, revenue ledgers, payment splits and totals, then choose Approve sales batch in the preview to post.
7. Check one receipt in Ledger A/c and the batch control totals. Retain the processed batch ID and voucher references. Do not create separate manual JEs for the same imported sales.

Outcome after final approval: one balanced receipt journal per approved receipt entry, with the relevant revenue and collection ledgers updated. Cash debits 1000; UPI debits 1110; Card debits 1120; direct-bank receipts debit their bank; other recorded collection methods use their configured clearing treatment. Revenue credits the appropriate earned-revenue ledgers. The standard import does not guess separate GST/TDS. Rejected/unposted rows do not enter accounting reports or patient counts.

Example: earned sales 1,000 paid Cash 200 / UPI 300 / Card 500 post Dr Cash 200 + Dr UPI clearing 300 + Dr Card clearing 500 / Cr Revenue 1,000. This is one sales-receipt/patient-proxy entry, not three patients.

## 5. Post vendor invoices before recording their payments

1. Check Vendor master. Create/review missing vendors individually or by the bulk-vendor template. Adding a vendor creates master data, not a purchase JE.
2. Open AP Vendor Invoices → Upload bulk invoices (beside Enter invoice). Use the standard invoice template, correct operating units and actual dates. Upload/review alone posts nothing.
3. Classify each purchase correctly. Medicine for stock normally debits 1100 Inventory; equipment/CWIP debits the appropriate asset; a current operating cost debits its expense ledger. Do not expense stock or loan principal merely because cash was paid.
4. Inspect validation reasons, duplicates and existing-source links. For GST/TDS/retention/complex allocations, post the correctly reviewed original source in its appropriate workflow, then link the existing unpaid accrual in AP. Do not also create a second simple AP accrual for that invoice.
5. Confirm vendor, period, account and tax review; approve valid rows and explicitly reject flagged/unwanted rows as appropriate. Choose Preview invoice journals, inspect them and choose Approve AP action in the preview.
6. Verify the invoice register, accrual voucher and vendor outstanding total. Leave genuinely unpaid invoices unpaid.

Outcome after final approval: a new simple accrual normally posts Dr Expense/Inventory/Asset / Cr Trade payables, on the accounting date. Linking an existing accrual creates the invoice registration/link without a second expense or tax entry. No bank payment is created just because the invoice was uploaded, accrued or assigned a due date.

## 6. Record salaries, petty cash and other period accruals

Salary: obtain the approved payroll and identify whether the expense is already accrued. If not accrued, use Journal studio to post Dr Salary expense / Cr Salaries payable for the earned period, with statutory/other deduction liabilities separated where applicable. If expensing at the actual payment date is appropriate and no prior accrual exists, a reviewed Dr Salary expense / Cr Bank entry is possible; do not use payment timing to shift expenses out of the earned period. Gross payroll must not be inferred from a net bank transfer.

Petty cash: open Petty cash → Record cash expense / top-up, or Upload bulk petty cash. Review treatment, unit, ledger, amount and source basis. For bulk imports, stage/review the rows, approve/reject them, preview and confirm the posting. An expense posts Dr Expense / Cr 1000 Cash. Stock, staff advance and salary-liability settlement use their respective asset/liability treatments instead of being expensed again. A cash top-up is a transfer, not an expense. Use a consistent report/reference when no supplier voucher number exists; the tool generates its own accounting voucher on posting. Do not manufacture an external invoice.

Other accruals: record reviewed earned-but-unpaid costs in the proper period through Journal studio or the relevant dedicated workflow. Tax-bearing transactions and payroll deductions need their own reviewed splits.

Outcome: salary and petty-cash expense are in the ledgers once. Liability settlement later reduces the liability; it is not another expense. Payroll/petty imports still need the final posting approval.

## 7. Import the bank statement

1. Open Bank reconciliation, choose the actual INR bank ledger and correct new-statement scope. Use All operating units only for a genuinely shared bank account.
2. Import statement using the supported CSV/template/mapping workflow. Check debit/credit signs, transaction/value dates, references, reporting start/end and verified bank opening/closing balances. Convert an unsupported original layout to the tool's format before approval.
3. Review the import preview and approve the statement import. Do not load overlapping duplicate periods. Confirm that every statement row is represented and that imported totals reconcile to the supplied balances.

Outcome: bank-statement source rows become available for reconciliation. Statement import does not automatically post salary, sales, purchases, loan repayment or bank charges. It does not replace the opening-balance JE or create money movements in the real bank.

## 8. Record vendor payments — choose one route

Route A, AP first: in AP Vendor Invoices select the paid invoice(s) → Mark selected invoices paid. Enter Actual payment date, actual bank, transfer reference and actual paid amount, including partial payment if applicable. Review and approve the preview. If the exact payment voucher already exists, link it through the optional existing-payment-voucher field instead of posting again. Then reconcile to its existing bank movement.

Route B, source-assisted reconciliation: upload the standard Invoice Payment Report in Reconcile side by side. The invoice must already be registered/accrued. Upload is read-only. Select the matching invoice-payment source rows and actual bank withdrawal, review the reconciliation preview and confirm. The preview may create the missing ordinary AP payment, or use an existing valid payment without reposting it.

Do not use both routes to create a new payment for the same transfer. A due/scheduled payment date is not an actual payment. Never mark every invoice paid using today's date when historical payments occurred in April/May. Use bank evidence and the true invoice allocation. For one transfer paying several invoices, select all corresponding invoice amounts. For a partial payment, record only the portion actually paid.

Outcome when a new AP payment is approved: Dr Trade payables / Cr Actual bank, using the actual payment date. An invoice accrued in April and paid in May creates expense/asset in April and bank outflow in May; not another May expense. Extending a scheduled payment date affects the payment plan/forecast, not the journal or bank.



### Correct an AP payment entered with the wrong date

A future-dated payment is excluded from AP paid/outstanding status until that date. Its reference still exists, so creating another payment is correctly blocked. Changing the As at filter only changes the view; it does not fix the entry.

Set AP As at to include the wrong recorded date and Refresh AP. Select that payment in the lower payment-history table, then Correct selected payment date. Verify the listed vendor/invoice, unit and amount first. Enter the actual bank date and evidence/reason, tick review, Preview payment-date correction and Approve AP action. The action cancels the erroneous posting on its recorded date and creates the replacement on the evidenced date, atomically preserving amount, bank, unit, transfer reference and invoice allocation. It creates no additional purchase expense. Original/cancellation/replacement vouchers remain auditable; there is one net bank payment. Reset As at to the intended report date and refresh. Refresh bank source tables and any stale daily database before reporting.

Only active AP-created payments within the same financial year are supported. Linked independent source vouchers require their owning correction workflow. Undo active bank matches first and reopen locked periods only after review; no match or period is silently changed. New dates before invoice accrual/initial openings, duplicate active references, changed books after preview and invalid allocations are blocked. Do not manually reverse/repost or alter the genuine bank UTR to get around the duplicate warning.

## 9. Reconcile existing entries and customer settlements

Open Bank reconciliation → Reconcile side by side. Load the bank/statement. Select Compare bank against according to the task:

| Compare option | Use it for | Accounting result after confirmation |
| --- | --- | --- |
| Sales receipts | Posted cash/UPI/card receipts awaiting bank settlement, or a deliberately selected unposted source needing accounting | For posted clearing receipts, only Dr Bank plus reviewed charges / Cr Clearing. No new revenue. An amber unposted receipt may create its receipt JE as well; inspect the preview to avoid duplication. |
| Invoice payments | Registered AP payments or reviewed Invoice Payment Report rows | Existing payment: match links only. Missing valid payment: Dr Payable / Cr Bank, then match. |
| All book movements | Salary JEs, bank-only entries, own-bank transfers and other posted bank-ledger movements | Matching existing entries creates links only; no second JE. |

1. Filter each panel independently, for example UPI on both sides. Click column headers for date/reference/amount/party/unit filters. Filter changes clear checks and proposed charges: reselect the intended rows.
2. Tick the actual bank row(s) and corresponding source/book row(s). Use the correct sign, unit, references and actual transaction dates. A single bank amount may correspond to several receipt/invoice/payroll entries.
3. Check selected totals. For an evidence-backed net fee, use Use difference as bank charges, inspect Reviewed bank charges INR and enter the review basis. Gross 1,000 settled at 990 gives fee 10. Vendor paid 1,000 with withdrawal 1,010 gives vendor payment 1,000 plus charge 10. For invoice/existing-bank charge adjustments, select one bank transfer per action; multiple related invoices can be selected.
4. Confirm the review checkbox and choose Automatically reconcile selected. Inspect every proposed journal. An existing-only match should show no new journal. Confirm reconcile only when correct.
5. Refresh and inspect remaining items/Match history. The main Bank reconciliation screen's Book movements tab also lists posted JEs containing the selected bank ledger.

Do not expense a cash deposit or bank settlement. Do not increase sales because card/UPI money appears in the bank later. Do not label every difference as bank charges. If a posted payment has an incorrect date, correct/reverse it through its owning workflow; use the reviewed timing-difference option only for a genuine settlement/clearing delay.

## 10. Bank entries without a supplier invoice or voucher

A supplier invoice is not normally the source document for salary, cash movement or loan principal. These still need appropriate evidence and approval. A bank statement proves movement of money; it may not establish its full accounting classification or tax eligibility.

For a genuinely new entry: select an unmatched row in Bank reconciliation → Record bank transaction, or tick exactly one bank row in the standalone workspace → Record bank transaction. Choose treatment/unit/eligible ledger, enter evidence/review basis and confirm the review. Preview journal, inspect debits/credits/date, then Confirm post and match. The form posts a new voucher and matches the selected bank remainder. If the JE already exists, use All book movements and match instead.

| Bank item | Obtain/verify | Entry and correct tool action |
| --- | --- | --- |
| Salaries paid; expense already accrued | Payroll, approved net pay/deductions, payment reference and salary-payable balance | Dr Salaries payable / Cr Bank. Journal studio first then match All book movements, or Record bank transaction → Standing instruction / other payment against the saved salary liability. No second salary expense. |
| Salaries paid; no earlier accrual | Approved payroll and earned period; gross/net and deduction details | Post the appropriate salary expense/payable/deduction entries. For a simple reviewed payment with no deductions/prior accrual, Dr 4520 or dedicated salary expense / Cr Bank. Record once, then match. A net bank amount alone is not a complete gross-payroll allocation. |
| ATM/cash withdrawal for business use | Cash withdrawal evidence and cash-custody record | Dr 1000 Cash / Cr Bank. Use Cash withdrawal. Record later expenses separately from petty cash. Do not also post the same top-up in Petty cash. |
| Cash deposited from recorded cash | Cash deposit slip/custody record; sufficient recorded cash; related receipts | Dr Bank / Cr 1000 Cash. Use receipt-linked cash settlement where applicable, otherwise Cash deposit. Never create sales again. |
| Deposit from a customer | Receipt/invoice/advance details and whether already posted | Use Sales receipt/Service revenue and settlement or match the existing entry. Do not treat every bank deposit as new revenue. |
| New bank loan received | Sanction/disbursement advice and loan ledger | Dr Bank / Cr 2400 or the lender-specific borrowing ledger. Use Loan proceeds received. It is not income. |
| Loan recovery/EMI paid | Lender statement with principal, interest and fees; recorded opening principal | Use Loan repayment / EMI. Dr 2400 principal + Dr 4580 interest + Dr 4560 fees / Cr Bank total. Example: INR 10,000 +1,800 +200 =12,000. Do not expense the full EMI or guess the split. Capitalised borrowing costs, if applicable, need the separately reviewed CWIP/journal workflow instead of automatic interest expense. |
| Loan you gave is repaid to you | Original loan-receivable record and repayment evidence | Dr Bank / Cr Dedicated loan-receivable asset. Use Loan given recovered. Interest received needs its own reviewed income allocation. |
| SMS/bank/card-processing fee | Statement/fee advice; valid tax invoice if claiming input GST | Dr 4560 / Cr Bank for a gross charge with no separately claimed input tax. Use Bank / SMS / card charges. A separate fee debit is not a sales settlement. |
| Actual card purchase or credit-card bill payment | Purchase invoice, asset/expense purpose and card-payable balance | Use the actual expense/asset/payable treatment. Do not book a card purchase or card-bill principal automatically to 4560. Avoid expensing both the purchase and its later card-bill payment. |
| Standing instruction | Underlying agreement or approved instruction: EMI, insurance, vendor, payroll, etc. | SI is a payment method, not a ledger. EMI: loan split. Vendor invoice: AP payment. Other supported non-tax purpose: Standing instruction / other payment. |
| Transfer to vendor | Registered invoice, actual allocation and transfer reference | AP payment, Dr 2000 or actual trade payable / Cr Bank, then match. Do not expense a previously accrued invoice again. |
| Employee advance | Approved advance request and recoverability | Dr Dedicated staff-advance asset / Cr Bank. Use Transfer to another person. Not salary expense yet. |
| Owner/director personal transfer | Ownership/legal form and approved purpose | Use the appropriate drawings, owner/director current account or receivable. Use Transfer to another person with the reviewed ledger. Not automatically a business expense. |
| Transfer between your own business banks | Both account details and transfer references; same legal entity | Dr Receiving bank / Cr Sending bank once. Use Own-bank transfer, then match the receiving statement's existing book leg. Do not post a second receipt JE on the other bank. |
| GST/TDS remittance | Filed/reviewed liability and challan/payment evidence | Dedicated GST/TDS workflow, then match its existing bank entry. Remittance reduces a tax balance; it is not a fresh expense. |
| Unidentified withdrawal/deposit | Client clarification and supporting evidence | Leave unmatched and log the query until identified; do not invent an expense/invoice or classify a genuine unknown transfer as a bank error. If a reviewer authorises a temporary suspense treatment, use an appropriate balance-sheet journal and a tracked clearance action; it is not a permanent expense or proof of completed reconciliation. |

GST on fees is not inferred. If eligible and supported, a 118 domestic fee might be Dr 4560 100 + Dr 1200 CGST 9 + Dr 1210 SGST 9 / Cr Bank 118; use IGST 1220 only where appropriate. Use the reviewed GST/settlement or compound Journal studio workflow, then match. Ineligible/non-creditable tax forms part of cost as applicable. Do not force a separate input-tax claim through the simple gross-fee form.

If two entries share a narration or similar amount but the source is uncertain, request clarification. For payroll and other transfers, retain an approved supporting schedule; the tool-generated voucher number is the internal accounting reference, not a fabricated external invoice.

## 11. Review month-end reports and exceptions

Run and compare:

1. Ledger A/c: cash, each bank, UPI/card clearing, trade payables, salary expense/payable, loans, bank charges, stock and relevant tax balances. Trace unusual/negative balances to vouchers.
2. AP register: opening payable + accruals/adjustments − actual payments = outstanding, subject to reversals/source links. An unpaid invoice remains outstanding; an unexplained bank transfer does not prove which invoice was paid.
3. Payroll: earned-period expense and liabilities reconcile to the approved payroll; bank payments reconcile to net pay. Advances and liability settlements are separated from fresh salary cost.
4. Petty cash: opening cash + funding/receipts − disbursements = closing physical cash, after other cash entries. Reconcile custody/counts. Funding is counted once, not an expense.
5. Trial balance, Profit and loss and Balance sheet: check both control totals and classification. A balanced JE/trial balance alone does not prove the right account, month, tax or completeness.
6. Bank reconciliation → BRS / handover: verify statement balances using Set verified statement balances; review all residual book/bank items, timing differences and support. Do not mark complete merely because selected rows matched. Resolve unexplained differences. Review & mark reconciled locks bank posting through that statement end until explicitly reopened.

Some genuine timing items may remain reconciling items under the reviewed BRS rules. A recorded bank error/dispute needs actual evidence; it is not a label for an unidentified ordinary expense. Corrections to owned settlement/adjustment entries should use Match history → Undo selected match with a reason/date, then correct and re-review. Do not delete posted history. For an own-bank transfer matched on both statements, undo the counterpart match before reversing the originating transfer.

## 12. Generate the consolidated daily register and monthly pack

Financial reports → Daily Business Register — consolidated database: choose the period and unit, then Build / refresh database after posting/corrections. It derives records from posted books; it does not post missing transactions from reports. Review Daily table, What is left out, Source gaps and Source drilldown. Refresh stale snapshots before export.

| Metric | Interpretation / check |
| --- | --- |
| Revenue | Earned ledger revenue, not every bank deposit; excludes output tax and opening/year-close families. |
| Sales Units / patients | Active receipt-entry proxy, once across payment splits; not unique patients. Cancelled receipts are excluded as of Through. No patient-ID information is invented. |
| Collections | Net customer receipts/refunds into recorded payment methods. Bank settlements, capital and loan proceeds are not extra customer collections. |
| Opex | Booked operating expenses, including salary and petty-cash expense once, depreciation and cost of sales. Finance costs/income tax are outside this definition and shown as left out. |
| Capex | Booked PPE/CWIP additions and acquisition reversals, including credit purchases; not simply all asset cash payments. Internal capitalisation/disposals are not new additions. |
| Cash Balance | Closing cash plus bank balances; excludes unbanked UPI/card clearing. Do not sum closing balances across days. |

Inventory purchases, staff advances, loan principal, recoverable tax and payable settlements are not fresh Opex. The expense portion of petty cash is included; its stock/advance/top-up/payable-settlement portions are not expensed again. Source gaps includes pending/rejected imports and unmatched bank rows; an unmatched bank row may already have an existing book entry. Review before posting.

For Business Pulse — Monthly Performance, refresh the appropriate financial year/through date/unit. Review salary/OT/compliance mappings, supplied new-patient inputs and month completeness. OT means staff overtime; ARPP uses total receipt-proxy visits unless a reviewed actual visit override applies. This separate report's all-petty-disbursements metric can overlap salary/other categories; do not add it as a second expense total.

Export the reviewed Financial pack and required ledger/AP/petty/BRS reports. Daily register Excel includes the support views; PDF/CSV export the current view. The saved consolidated database is inside the protected book. Explicit SQLite exports contain financial information outside the encrypted book and include all units/supporting history, not only a filtered display.

## 13. Final sign-off and handover

Use a monthly checklist with status Complete / Pending / Not applicable and evidence references:

- All expected dates, units and source reports received; missing sources listed and agreed.
- Sales rows/totals/payment splits reconciled; duplicate/invalid/rejected rows resolved or tracked.
- Vendor invoices reviewed/accrued once; actual paid/unpaid status correct.
- Salary/payroll, petty cash, loan split and bank-only entries supported and posted once.
- Bank statement import totals/balances verified; existing entries matched; settlements do not duplicate sales.
- All unusual transfers/unmatched items have owner, reason, action and target date. No unidentified balance silently expensed.
- Trial balance, ledgers, tax working and financial/management reports reviewed; daily database current.
- BRS completion approved where its conditions are met; outstanding permitted timing items documented. Do not perform annual year-close just to finish a monthly reconciliation.
- Dated .riju backup created after final approved postings, stored externally and visible with the expected filename/time; retain prior checkpoints. Exported reports are additional handover files, not replacements for the protected book.

Record month/unit/bank scope, preparer/date, reviewer/date, pending items and output filenames. Continue the next month in the same books, reviewing carry-forward balances and explicitly tracking unresolved earlier-period issues. Never assume that uploading all files has completed the accounting.

## 14. Quick action-to-result reference

| User action | Posts a JE? | Ledger / accounting result |
| --- | --- | --- |
| Add vendor / maintain master | No | Master/setup only. |
| Upload sales or invoice report | No | Staged source rows and validation. |
| Approve individual source rows | No | Review decisions only; final preview approval still required. |
| Approve sales batch from journal preview | Yes | Receipt/payment-method debits and earned-revenue credits. |
| Approve new AP accrual | Yes | Expense/stock/asset debit and payable credit. |
| Link exact existing AP accrual/payment | No additional JE | Registration/link to already posted source. |
| Approve a new AP payment | Yes | Payable debit and bank/cash credit. |
| Import bank statement | No | Statement source rows for matching. |
| Match existing bank/book entries | No | Reconciliation links only. |
| Confirm a new clearing settlement / reviewed charge | Yes | Bank/fee/clearing or bank-charge journal as previewed, plus match. |
| Confirm Record bank transaction | Yes | Purpose-based new journal plus selected bank-row match. |
| Post approved Journal studio draft | Yes | The reviewed balanced lines; then match its bank movement if relevant. |
| Extend scheduled AP payment date | No | Payment plan/forecast only. |
| Build/refresh Daily Business Register | No | Rebuilds derived database; no missing source is automatically posted. |
| Export reports or back up books | No | Output/backup files; accounting figures do not change. |
| Mark BRS reconciled | No new transaction JE | Statement completion and bank-period posting lock. |
| Undo an owned bank adjustment/settlement match | Reversal where applicable | Match becomes undone; its owned journal reverses with audit history. Existing-only match undo does not reverse an independently posted original payment. |

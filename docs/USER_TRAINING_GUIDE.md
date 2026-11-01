# Riju Books — Bookkeeping Training and User Guide

Development version 0.29.1-dev | 1 November 2026 | Windows | INR

Audience: a new bookkeeper, an accountant reviewing the work, and the person delivering the books to the hospital. This guide explains both the workflow and the bookkeeping behind it. Use the matching development executable; screen names refer to that version. Dates shown in examples are practice dates, not instructions to post into live books.

## 1. Start here: what the tool does

Riju Books keeps one legal entity's books with operating-unit analysis for JP Nagar (JP), Kammanahalli (KM) and Vaikom (VK). It is a single-user, local Windows application. The same transaction must be entered only once, even when it appears in a hospital report, bank statement and invoice file. The bank statement normally reconciles an existing payment or receipt; it is not a second sale or expense.

The left navigation opens each module. Select the financial year and unit in the top selectors. All units means the entity view, not a separate company. Scroll the left navigation or the main workspace if a button is outside the visible area. Reports have their own date selectors where shown: change them and refresh before reading totals.

The new AP Vendor Invoices page records vendor bills, tracks payment dates, posts reviewed payments and exports an AP register/forecast. Sales receipt now has an Import sales receipt report button and Excel/CSV templates, so daily collections can be processed in batches instead of entered one at a time.

Posting always requires review. Previewing, uploading, changing a schedule or exporting a report does not itself mean that a journal was posted. The permanent evidence is the voucher ID in Vouchers and the corresponding ledger lines.

## 2. Install and use a safe training copy

1. Download the RijuBooks-Windows ZIP supplied for the matching build and extract all files. Do not run the application from inside the ZIP.
2. Find RijuBooks.exe, normally under dist in the extracted bundle. The application does not require the end user to install Python.
3. Read packaged-selftest.json: version should be 0.29.1-dev and passed should be true. The included checksum file identifies the executable supplied by the build.
4. Use a disposable training book first. Do not practise by adding sample invoices to the live hospital book. Your administrator can start a demo copy with `RijuBooks.exe --demo --data training.json`; the JSON training file is not protected for live use.
5. For normal Windows use, the default book is under `%LOCALAPPDATA%\RijuBooks\books.riju`. Keep the same Windows user/profile for that book.
6. In Settings & backup choose the external backup folder. Confirm the device is connected and a backup is actually created.
7. When an upgrade banner appears, configure the external backup first. The original-format book must be retained before the upgraded file is saved. Older executables cannot open format 20 books.

The existing Windows DPAPI storage remains in this build. New portable encryption/recovery and mailbox ingestion were deferred. There is no new password/recovery-key setup. A copy of a DPAPI file by itself is not a proven replacement-computer recovery method; keep the original Windows profile and follow the existing recovery arrangement. Do not discard the original book/profile when testing a newer executable.

To remove all practice entries from your own Windows book, open Settings & backup and select Start clean books — clear all test data. Review the counts, select a separate backup folder and type START CLEAN BOOKS exactly. The original saved book is byte-verified into that backup before the active book is replaced. If backup or save fails, do not assume a reset occurred. This clears all entered transactions, imports, drafts, AP vendors/invoices/payments and custom setup; no accounting balances are carried forward. The starter chart/branches and chosen backup location remain. Use Restore backup to recover the original book under the existing Windows account. Merely replacing the executable does not erase locally saved entries, and the application never clears a book automatically on launch. ChatGPT/API credits are separate; the reset does not access billing or API accounts. Standard ChatGPT usage terms still apply to work requested in this chat.

## 3. Bookkeeping essentials for a new user

A journal records the financial effect of a transaction. Every voucher has at least one debit and one credit, and their totals must be equal. A debit is not automatically an expense and a credit is not automatically income. The account determines what the amount means.

| Account type | Normal balance | Common increase | Examples |
| --- | --- | --- | --- |
| Asset | Debit | Debit | Cash, bank, inventory, equipment, eligible GST input |
| Liability | Credit | Credit | Vendor payable, patient advances, TDS payable |
| Equity | Credit | Credit | Capital, retained earnings |
| Revenue | Credit | Credit | Consultation, therapy, pharmacy sales |
| Expense | Debit | Debit | Rent, salaries, utilities |

Accrual means recording a cost and obligation when it belongs in the accounts, even though cash will be paid later. Paying that obligation later settles the payable; it does not create the same expense again.

Example, simple vendor service with no separate tax entry, INR 10,000:

| Event | Debit | Credit | Effect |
| --- | --- | --- | --- |
| Invoice entered | Relevant expense 10,000 | Trade payables 10,000 | Cost and vendor liability recorded |
| Vendor paid | Trade payables 10,000 | Bank 10,000 | Liability settled; bank reduced |
| Payment date extended | No journal | No journal | Planning date changes only |

Keep invoice date, invoice receipt date, accounting date, contractual due date, scheduled payment date and actual payment date distinct. A due date is not a reason to post a second expense. A future payment plan is not an actual bank payment.

Use a source document for each entry: invoice, receipt report, bank advice, contract, tax computation or approved adjustment. Record a clear reference and narration. Keep the source files outside the application in an organised folder; typing an invoice number is not uploading the original scanned invoice.

## 4. Set up the entity, units, ledgers and starting year

Use Setup & periods to review the entity name, available financial years, branch details and registration information. Unknown registrations should remain unknown until confirmed. Unit codes in imports must match the current active unit masters.

Use Chart of accounts to inspect or create ledgers. Choose account kind, reporting group and cash-flow classification deliberately. The number is an identifier; do not reuse a tax, patient, clearing or project control for a different purpose. Common starting codes include:

| Code | Ledger | Use |
| --- | --- | --- |
| 1000 | Cash | Actual physical cash |
| 1010 | Bank | Main INR bank ledger; create separate bank ledgers where appropriate |
| 1110 | UPI settlement clearing | Collections awaiting provider settlement |
| 1120 | Card settlement clearing | Card collections awaiting settlement |
| 2000 | Trade payables | Vendor obligations; AP adds invoice detail beneath the control |
| 2300 | Patient/package advances | Unearned receipts, not earned revenue |
| 4530 | Rent | Rent expense |
| 4590 | Administration | Reviewed administration costs, not a catch-all balancing account |

There are 15 service-revenue categories. Their current account codes come from the book's revenue mappings; imported categories use those mappings. Patient A/C is a shared billing/collection control, not an individual ledger for every patient. AP vendor tracking does not create a patient ageing module.

Enter initial opening balances using the Opening balances option and the reviewed financial-year start. Opening assets must balance liabilities and equity. Do not enter historical capital again as revenue. Confirm the opening trial balance before entering daily work. Closed years and locked/reconciled bank periods block conflicting edits and backdated postings.

## 5. A normal working day

1. Open the correct book, year and unit. Check backup and upgrade notices.
2. Read the AP payment reminder. Open AP to pay genuinely paid items or extend agreed payment dates.
3. Enter newly received vendor invoices once. Deal with special GST/TDS/CWIP sources before AP registration if necessary.
4. Import the daily sales receipts using the standard table. Review totals and flagged rows, then post the approved batch once.
5. Record any separate advances, refunds, outstanding-bill collections and non-template journals in their proper workflows.
6. Import bank statements and match existing postings. Record genuine missing charges or credits only after confirming they are absent from the books.
7. Review cash, bank, UPI/card clearing, AP differences and accounting-check findings.
8. Refresh reports and export the required evidence. Confirm the final backup and hand unresolved items to the reviewer.

## 6. Journal studio: prepare, edit and approve

For a simple completed transaction, enter narration in Journal studio and choose Prepare offline draft. For example: `Paid INR 5000 rent by bank on 1 November 2026 at JP Nagar`. The local model can extract supported dates, units, parties, amounts and methods, but the resulting lines still need your review.

Check date, unit, accounts, debit/credit amounts, source reference and party. A model draft is not a journal until approved. If the description is ambiguous, the tool clears the old draft and asks for clarification or a dedicated workflow. It does not invent GST/TDS, allocate an advance or post automatically.

Add or edit manual lines when you know the correct accounts. Each branch must balance; genuine cross-unit transactions need explicit inter-branch clearing. Save draft retains unposted work. Review & post voucher is the explicit posting step. Once posted, correct errors by a dated reversal and a new reviewed transaction rather than editing the original history.

The offline language component is a small authored statistical intent model, not a general generative LLM. Read MODEL_CARD_OFFLINE.md for supported topics, licence and limitations. A refusal is a request to review the source, not permission to disguise a taxed transaction as a simple expense.

## 7. AP Vendor Invoices: add the vendor

Open AP Vendor Invoices in the left navigation. The As at date controls the positions being displayed. The default is the current India date; do not confuse a historical As at view with today's payment instruction.

Select Add vendor. Enter the vendor's legal/source name, default credit period in whole calendar days and optional vendor code/reference. Save vendor. The same normalised vendor name cannot be added twice. Use the same saved vendor for later bills, rather than creating a slightly different name to bypass an invoice duplicate warning. The default credit period is only a starting value; review it for every invoice.

Adding a vendor does not post a journal. Vendor information does not independently verify GSTIN, PAN, bank instructions or legal tax applicability. Obtain and verify payment instructions through the organisation's normal approval process.

## 8. AP Vendor Invoices: enter a new invoice

Select Enter invoice and complete the following fields.

| Field | What to enter | Why it matters |
| --- | --- | --- |
| Vendor | Existing vendor | Groups the invoice with the correct source party |
| Vendor invoice number | Exact supplier invoice reference | Duplicate control within the vendor's fiscal year |
| Invoice date | Date printed on invoice | Identifies source period and invoice fiscal year |
| Invoice received date | Actual receipt date | Records when the invoice arrived |
| Accrual accounting date | Reviewed date the liability is booked | Determines journal period, not payment timing |
| Credit period calendar days | Contracted whole days | Used to calculate contractual due date |
| Credit period starts at | Receipt date or Invoice date | Avoids silently assuming the contract's terms |
| Scheduled payment date | Planned date; blank uses due date | Feeds the AP cash-outflow schedule |
| Operating unit | Unit receiving the cost/asset | Preserves branch analysis |
| Net amount payable to vendor | Actual vendor payable in INR | Excludes amounts separately owed to tax/retention controls |
| Trade payables ledger | Usually 2000 or another reviewed Trade payables ledger | Credited by the accrual, debited by payment |
| New accrual: cost/asset ledger | Genuine expense/asset | Determines the debit for a new simple invoice |
| Existing accrual voucher | Blank for a new simple accrual; otherwise original voucher ID | Links an already-posted source without duplicating it |
| Review basis | Source and accounting/tax review evidence | Explains the decision to the next bookkeeper/reviewer |

For a simple invoice without a separate GST/TDS allocation, review the checkbox and select Preview invoice accrual. Read the proposed voucher, amount, dates and unit. Approve AP action posts the accrual. The register then shows the original accrual voucher and unpaid balance. The amount has not left the bank.

Example: invoice dated 1 November, received 2 November, accounting date 2 November, 30 calendar days from receipt and amount INR 10,000. Contractual due date is 2 December. If the scheduled date is blank, 2 December is used. The expense/AP journal is dated 2 November, not 2 December.

The simple entry screen uses one cost/asset debit. For split costs, GST/TDS, retention or CWIP, first create the correct compound accrual in its dedicated workflow or Journal studio and use the existing-source procedure below. Do not force a bank, GST input, CWIP, patient or collection-clearing control into the simple cost field.

## 9. AP: taxed invoices, CWIP and already-posted sources

If GST, TDS, retention or project capitalization applies, review and post the source in GST accounting, TDS accounting, CWIP & commissioning or an approved compound journal as appropriate. These modules retain their own legal/source and reversal controls. Then register the unpaid vendor portion in AP by entering the original accrual voucher ID and exact accounting date.

The linked voucher must be an active original unpaid accrual. The selected branch/payable credit must cover the AP amount not already registered. The link creates AP metadata and a payment plan; it does not post the expense or tax again. A voucher containing an actual cash/bank payment cannot be linked as an unpaid accrual.

Example: reviewed source debits expense 1,000 and eligible GST 180, credits TDS payable 100 and Trade payables 1,080. AP vendor payable is 1,080. The 100 tax liability and any retention remain in their separate controls/workflows; AP payment settles only the 1,080 owed to the vendor. The values are illustrative, not legal tax-rate guidance.

One compound source can support several separately identified invoice allocations within its payable capacity. Do not cancel one invoice by reversing a source shared by other invoices. The AP cancellation action blocks that case; use the original source correction process and review every related allocation.

Existing manual payments and unregistered invoices can cause the AP control to differ from the register. Export AP payable reconciliation and investigate the difference. The software displays it rather than inventing an invoice or silently allocating an old payment.

## 10. AP: process a due invoice or extend it

While the application is open, a reminder at the bottom of the workspace displays the number and outstanding amount of AP invoices due by today's India date. It refreshes periodically. Select the reminder or AP Vendor Invoices to process items. This is an in-app reminder; it is not an email, operating-system background task or bank payment instruction while the app is closed.

Within AP, the register flags DUE / OVERDUE using the selected As at date and current scheduled payment date. Read both Contractual due and Scheduled payment. A changed plan does not erase the original contractual obligation.

To extend, select one outstanding invoice and choose Extend payment date. Enter effective date, new later payment date and vendor agreement/reason. Preview and approve. The new date must be later, not before the effective date, and extension history must be chronological. No journal is posted. Historical forecasts before the extension still use the earlier schedule.

An extension records planning agreement; it does not independently establish a change in legal terms, waive interest or satisfy the organisation's approval process. Keep the actual supporting communication with the source records.

## 11. AP: mark invoices paid and record the journal

1. Confirm the payment actually occurred and obtain the bank/cash evidence. Selecting an invoice is not authorisation to move money outside the application.
2. Refresh AP at the required date and select one or more outstanding invoices. Use Ctrl/Shift to select several rows.
3. Choose Mark selected invoices paid. Enter actual payment date, actual INR cash/bank ledger, payment reference and evidence/review basis.
4. For one invoice you may enter a partial amount. For multiple selected invoices, the current screen pays their full outstanding totals together; process partials separately. Keep one operating unit per payment batch.
5. Leave Existing exact payment voucher blank to create the payment journal. If it was already posted elsewhere, enter the exact original payment voucher ID: date, unit, cash/bank and payable allocation must agree. This links it once without reposting.
6. Confirm actual payment evidence, choose Preview payment journal and inspect debit AP / credit cash-bank. Approve AP action to save.
7. Confirm the Paid or Part paid status, outstanding amount and payment voucher in the history table. Reconcile the bank statement to this existing payment later.

UPI/card collection clearing is not an outgoing vendor bank account. Use the actual bank or cash ledger. Foreign-currency payments require their own reviewed treatment and cannot be passed as a simple INR AP payment. If bank fees are separate, record/reconcile their actual source separately; do not reduce an invoice allocation to disguise a bank charge.

Repeated payment references at the same bank/fiscal year, overpayment, payment before accrual, duplicate invoice selections and future capacity conflicts are blocked. A backdated second payment cannot consume capacity already reserved by a later posted payment.

## 12. AP: reversals, cancellations and exports

If a payment was wrongly recorded, select it in the payment-history table and choose Reverse selected payment. Review the date and full journal before approval. Reversing a payment reopens the invoice balance as of that reversal date. If one payment covered several invoices, its reversal affects that whole payment allocation, not just a single invoice.

To cancel a simple unneeded accrual, select one invoice and use Cancel selected invoice. Enter cancellation date and source reason. Dependent payments must be reversed first. Shared sources and GST/TDS/CWIP sources retain their own correction constraints. The original invoice/reference remains in history and cannot be reused to hide a duplicate.

AP register Excel/PDF contains invoice detail, payment history, payable reconciliation and schedule changes. AP forecast Excel/PDF contains outstanding payment commitments for the selected horizon. Reconcile Registered outstanding to Ledger credit for every payable/unit. Investigate Unregistered difference; do not post a balancing plug merely to make a report show zero.

## 13. Cash flow: actual statements and AP planning

Cash flow setup defines cash/equivalent accounts and Operating/Investing/Financing classifications. Save a reviewed report-wide policy. Unreviewed mappings and ambiguous mixed controls keep working statements in draft even when arithmetic totals reconcile.

Actual direct cash flow records bank/cash movements; actual indirect cash flow bridges profit, working-capital changes and noncash adjustments. An unpaid invoice creates no actual cash outflow. A new simple AP payment follows its reviewed invoice-cost classifications where provable, including a split between an asset and an expense. Ambiguous linked-source classification still needs a reviewed cash allocation.

Financial reports includes Cash flow - AP forecast. Its From date is also its as-of date: only invoices outstanding at that date are planned through Through. This is different from a retrospective actual report covering that period. AP's own forecast controls allow an explicit As at date and future horizon. Cash flow setup exports also include an AP schedule for the 90 days from the actual reporting end.

Overdue unpaid invoices are carried into the forecast's start bucket, rather than disappearing because their scheduled date is in the past. Extending a payment moves the future bucket from the extension effective date. Partial payments reduce the remaining plan; full payment removes the invoice from subsequent as-of plans. A later-dated payment does not erase what was outstanding in an earlier historical forecast.

The AP forecast is a vendor-outflow schedule, not a complete projected bank balance or sales budget. It does not assume future customer receipts, unknown supplier invoices, interest or financing. Never add its planning totals into actual cash-flow movement or treat its forecast as another journal.

## 14. Sales receipt: one manual receipt

Use Sales receipt for a single earned receipt. Allocate the amount across the 15 revenue categories and actual cash/card/UPI/other splits. Service total must equal payment total. Prepare compound journal for review opens Journal studio; check and post there.

A receipt can contain consultation plus therapy and be paid using several methods. It is still one business transaction and one compound journal. UPI/card initially debit collection clearing, not bank. Later provider settlement transfers clearing to actual bank, with separately reviewed fees/tax as appropriate.

Use Service revenue instead for advances, earning an advance, separate outstanding bills, cancellations/refunds and collections of a previously recognised bill. Collecting a bill must debit cash/bank and credit the shared Patient A/C; it must not credit revenue a second time.

## 15. Sales receipt: prepare the standard import table

In Sales receipt choose Excel receipt template or CSV receipt template. Excel contains an empty Receipts sheet and an Instructions sheet. It contains no sample receipt rows to accidentally post. Keep the sheet name Receipts and all 28 headings; columns can be reordered. Save as XLSX or UTF-8 CSV. Use one earned receipt per row, not one row per payment leg.

| Heading | Requirement | Meaning |
| --- | --- | --- |
| receipt_date | Required | YYYY-MM-DD or actual Excel date |
| branch | Required | Current active code, such as JP, KM, VK |
| receipt_no | Required | Unique receipt ID per unit/fiscal year; preserve leading zeros as text |
| invoice_no | Optional | Linked hospital invoice reference |
| party | Optional | Source description/name; does not create a separate patient account |
| record_type | Required: earned | Confirms earned service, not advance/refund/old bill collection |
| tax_mode | Required: no_separate_tax | Confirms this standard receipt needs no separately posted GST/TDS split |
| treatment | Money | Treatment/therapy earned revenue |
| consultation | Money | OPD consultation |
| eye_check | Money | Eye check-up |
| registration | Money | Registration charges |
| medicine_retail | Money | Retail pharmacy sales |
| medicine_treatment | Money | Medicines for treatment |
| consumables | Money | Patient consumables revenue |
| room_rent | Money | IPD room revenue |
| nursing | Money | Nursing charges |
| duty_doctor | Money | Duty doctor charges |
| food | Money | Patient food revenue |
| swarnaprashna | Money | Swarnaprashna revenue |
| kalari | Money | Kalari revenue |
| treatment_receipt | Money | Earned treatment receipts; not unearned deposits |
| misc | Money | Miscellaneous earned patient charges |
| cash | Money | Actual physical cash collected |
| bank | Money | Actual direct receipt into main bank ledger 1010 |
| upi | Money | UPI collected into UPI clearing |
| card | Money | Card collected into card clearing |
| other | Money | Other receipts clearing; not silently treated as bank |
| total | Optional money | Control total; if supplied must agree with both sides |

Money columns are INR with no more than two decimal places. Blank money cells mean zero; all 15 service columns must total the five payment columns. Negative amounts, spreadsheet formulas and mismatched totals are flagged. Paste values from the source report rather than keeping formulas. Optional text fields may be blank, but required identity/treatment fields may not.

For a different bank ledger, a taxable receipt, refund, advance or separate bill collection, use its dedicated workflow and keep it out of this simple earned-receipt batch. The template does not infer tax from gross collections. Do not call taxable sales no_separate_tax merely to clear an error.

Example source row, with all unmentioned money columns zero:

| Date | Unit | Receipt | Record/tax | Service allocations | Payment allocations | Total |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-01 | JP | TRAIN-001 | earned / no_separate_tax | consultation 500; treatment 300 | cash 200; upi 600 | 800 |

The proposed journal debits Cash 200 and UPI clearing 600, credits Consultation 500 and Therapy 300. No bank receipt is created until the actual UPI settlement is recorded. This example is training data; do not include it in the live source file.

## 16. Sales receipt: upload, bulk-review and post hundreds of rows

1. Select Import sales receipt report from Sales receipt and choose the aligned XLSX/CSV.
2. The report is saved as a review batch. Upload posts no journal. It retains every nonblank source row, including invalid and duplicate rows, with filename, source row and file digest.
3. Review valid/invalid/duplicate counts. Check date/unit/reference, revenue and payment totals. Compare batch totals to the original hospital report before approval.
4. Tick the explicit earned-service/tax/payment review confirmation after checking it. Select Approve all valid rows to approve hundreds together, entering the source review basis. You can also select several rows and approve/reject those rows only.
5. Review each flagged source issue. Use Reject flagged rows with a reason if they must be corrected outside the batch. An invalid or duplicate row cannot be approved just by ticking the checkbox.
6. Every row must have an approved or rejected decision. Rejected rows remain in history and never post. Correct their source file and import a new corrected report; do not edit the original audit trail.
7. Select Preview batch journals. Check the proposed journals and approved/rejected counts. Approve sales batch posts the selected receipts atomically: if a selected row now violates a period/account/duplicate guard, the batch does not partly post.
8. Confirm status PROCESSED and voucher/ledger totals. Work volume counts each posted source receipt once, not once per journal line.

Use Review sales report imports to reopen pending or completed standard batches. Import queue also routes these batches back to the standard receipt review. Review Excel/PDF exports retain all row decisions, error messages and source digest for handover.

Receipt identity is checked across queued/posted standard and legacy daily-sales reports. Renaming or editing a file does not permit a second copy of the same unit/fiscal-year receipt. Source numbers can repeat in another unit or fiscal year. Manually entered or unlinked historical receipts still need a source check: the software cannot recognise every duplicate whose original lacked a usable receipt identity.

Do not fix a duplicate by inventing a new receipt number, changing the date or entering the batch in another unit. Review the original source and use an approved correction/refund workflow if needed. A previously rejected row can be corrected and uploaded without being falsely reserved as an already-posted receipt.

## 17. Service revenue and shared Patient A/C

Service revenue separates money received from revenue earned. Use Direct receipt for earned services collected immediately, Advance for unearned deposits, Earn advance only when service has been delivered, and Refund advance when returning an unearned amount. Where a bill was separately recognised, use Collect bill against Patient A/C.

Follow the original source for cancellations/refunds. Choose the original action and reviewed amount; the module retains the original tax/source capacity and blocks reuse or over-refund. Review action previews before approval and export the service register to Excel/PDF. Do not import those same transactions again as earned receipt rows.

## 18. Bank statements, settlement and formal reconciliation

Import the actual bank statement using CSV/XLSX/OFX support and the reviewed bank-specific mapping. Review account, unit coverage, statement dates, opening/closing balances and row totals. A statement import alone is not a sale or vendor payment journal.

Match vendor payment rows to the payment already created/linked in AP. Match direct customer receipts to their existing receipt vouchers. Use a genuine adjustment only for a bank entry absent from the books, such as an unrecorded charge. Verify the bank date and supporting source.

For UPI/card settlements select the original collection-clearing items. Review gross receipts, actual net deposit and fee/tax treatment. Do not credit service revenue again when clearing reaches bank. Partial and multi-day settlements retain allocation limits; do not reuse settled source receipts.

Business calendar provides explicit Bengaluru year revisions, source review and exceptional working dates. Sundays and second/fourth Saturdays are normally nonworking, with installed bank-specific exceptions. Explain NBD shows skipped dates. Unknown years require a reviewed source list; a suggestion is not evidence that a bank actually settled on that date.

Review unmatched deposits, unpresented payments, direct bank items and proof differences in the formal BRS. Finalise only when reviewed and reconciled. Reopen with a reason before correcting a finalised bank period. AP payment corrections do not bypass a bank reconciliation lock.

## 19. GST and TDS workflows

Tax setup holds reviewed effective-dated rules and parties. Obtain the accountant's confirmed applicability and source rates; the software does not establish current law by using an account code or a patient/vendor name.

GST accounting retains reviewed source invoices, notes, mixed-rate lines and export/SEZ evidence. GST reverse charge separates purchase, cash funding, discharge and eligible ITC. GST cash & filing distinguishes actual deposits/utilisation from filing preparation. GSTR-2B source matching does not post or claim credit just because a file contains a row; unsupported portal variants need reviewed normalisation.

TDS accounting uses reviewed party/PAN, section, taxable base, fiscal-year history, deductions and challans. Verify late sources and prior deductions before a catch-up. A vendor's net AP balance may differ from gross invoice value because TDS is owed to a different control. Register only the vendor-payable portion in AP; do not pay TDS through the vendor row.

Use the tax modules' Excel/PDF proofs and retain source links. Do not use the simple sales template or simple AP allocation to conceal a required tax split.

## 20. Fixed assets, Vaikom CWIP and depreciation

Capital expenditure belongs in the reviewed asset/project accounts rather than being charged as an ordinary daily expense automatically. CWIP & commissioning records project/category costs, budgets, milestones, capitalisation review, retention and related TDS/source links. Unknown budgets remain blank; zero means an explicitly entered zero budget.

When an asset is ready for use, review commissioning evidence, allocations, asset class, put-to-use date, useful life and residual assumptions. Commissioning transfers eligible project balances to fixed assets once. Follow the source constraints before reversing costs that already support commissioning or retention/TDS events.

Assets & depreciation handles book assets, depreciation, transfers and disposals. Tax depreciation is a separate reviewed block/rule schedule and is not a replacement for book depreciation. Do not post the same depreciation from both a manual journal and a module action. Export and reconcile asset/project schedules to the ledger controls.

## 21. Financial statements, ledgers and questions

Ledger A/c provides opening, dated debit/credit movements, running/closing balances and voucher drilldown. Select the unit and reporting dates; use Excel/PDF/CSV/print for handover. A positive debit balance is different from a positive normal liability balance; read the report headings/signs.

Financial reports includes trial balance, P&L, balance sheet, comparatives, branch matrix, general ledger, actual direct/indirect cash flow and the AP forecast. Refresh edited selectors before comparing screen and export. Opening balances must be counted once, and both sides of the trial balance should reconcile.

Statement review stores exact-period reviewed presentation mappings and notes. Review Division I/AS, Division II/Ind AS or another applicable presentation with the accountant; complete every ledger classification and disclosure evidence. Missing notes stay pending. Current-tax working uses reviewed assumptions and posts an incremental provision after already-booked tax expense, with a frozen review. Deferred tax and other transaction-specific requirements still need evidenced accountant review.

Checks & questions provides editable review thresholds and source-linked findings. A finding is a prompt to investigate, not a legal conclusion or an automatic correction. Record Investigating, Explained or Action required with evidence. Correct the original workflow, not the alert table.

Questions use explicit period and unit selectors. Examples: cash balance; 1010 balance; rent expense; total expenses; profit; compare profit; top expenses; CWIP. Trace rows identify the voucher/line and signed arithmetic. Balance questions include history through the selected end; period profit/expense excludes opening/closing entries. Comparative answers include both periods' traces. Review suggestions are labelled separately from posted facts.

## 22. Month-end close and handover

1. Confirm all source files for the period were received and uniquely identified. Resolve import rows left pending or rejected.
2. Reconcile cash count and each bank statement. Investigate UPI/card clearing still awaiting settlement.
3. Export AP register, payment history, reconciliation and upcoming forecast. Confirm paid items agree to actual bank/cash evidence and unexplained payable differences have owners.
4. Review patient advances/Patient A/C, vendor/tax/retention controls and any inter-branch balances. Shared controls are not automatically separate-company consolidation.
5. Complete reviewed GST/TDS, project/asset and depreciation actions needed for the period. Retain source and rate assumptions.
6. Review trial balance, P&L, balance sheet, branch matrix, actual cash flow and comparative movements. Complete financial statement notes and supporting schedules with the accountant.
7. Export ledgers, BRS, AP, tax, asset/project and financial packs in the agreed Excel/PDF formats. Each pack must show entity, unit/scope, period and review status.
8. Run Change history/integrity checks. Keep a list of unresolved differences rather than hiding them with unsupported journals.
9. Confirm external backup, reviewer approval and period-lock/close actions. A lock is not a substitute for review; reopen only with a documented reason when supported.

## 23. Troubleshooting without damaging the books

| Message / symptom | What to check | Correct next action |
| --- | --- | --- |
| Upgrade pending | External backup folder/device unavailable | Connect/configure it and retain original-format backup before save |
| Required period is closed/locked | Year/period or finalised bank statement | Ask the reviewer to use the documented reopen process; do not change the transaction to a false date |
| AP invoice duplicate | Vendor, normalised invoice reference, source fiscal year | Open original invoice/history; do not invent a new reference |
| AP payment exceeds capacity | Partial/full payments, reversals, later-dated payments | Check complete payment history and exact outstanding at the actual date |
| Existing AP source does not match | Date, unit, payable credit or bank-payment totals | Correct the source/link selection; never post a second copy simply to clear the warning |
| AP register differs from payable ledger | Manual/unregistered accruals/payments, source allocations | Use reconciliation and voucher trace; register genuine missing sources or correct approved entries |
| Sales template headings rejected | Missing/renamed fields or wrong Excel sheet | Download the current template; keep Receipts and all headings |
| Sales totals differ | Missing service category/payment leg or bad control total | Correct source values, paste literal values and reimport rejected rows |
| Sales duplicate/invalid row | Edited file, already-posted receipt or wrong purpose | Review original; reject with reason and correct source; do not force approval |
| Batch partly reviewed | Some rows still have no decision | Approve valid rows/reject others explicitly, then preview the batch |
| Account/model interpretation uncertain | Unsupported or mixed purpose, missing date/method | Clarify one transaction or choose reviewed manual/dedicated source lines |
| Cash flow draft despite zero differences | Classification issues or unreviewed policy | Review actual nature and saved allocations, not just arithmetic |
| Download has no GitHub button | Actions artifact requires an appropriate signed-in session | Use supplied direct ZIP or sign into the authorised GitHub account; do not download an old release instead |

If a save fails, do not assume the screen represents a persisted book. Read the error, retain source documents, check the saved state and backup, and re-open the correct book only after resolving the issue. Never edit the protected vault or its audit JSON by hand to clear an error.

## 24. Guided training exercises and answer key

Use a disposable practice book, one unit JP and sources marked TRAINING ONLY. If the example dates are locked or unavailable, the trainer must choose a consistent unlocked practice period. Assume no separate GST/TDS for these exercises only.

Exercise A — starting bank: post an opening Dr Bank 50,000 / Cr Capital 50,000. Confirm bank opening and balanced trial balance. Do not count opening capital as sales or operating cash flow.

Exercise B — AP accrual: create Practice Supplier, invoice TRAIN-AP-1 for administration INR 10,000, invoice/received/accounting date 1 November 2026, zero credit days. Approve accrual. Expected: administration expense 10,000; AP credit 10,000; bank still 50,000; due reminder 10,000. The unpaid invoice creates no actual cash outflow.

Exercise C — extend: effective 1 November extend payment to 10 November with a training agreement reason. Expected: no new voucher; contractual due remains 1 November; scheduled date 10 November; forecast moves to 10 November from that effective date.

Exercise D — pay part: record actual payment INR 4,000 from bank on an appropriate actual training date with reference TRAIN-PAY-1. Expected Dr AP 4,000 / Cr Bank 4,000; Part paid; AP outstanding 6,000; bank 46,000. Forecast after payment contains only 6,000. If the training as-of precedes the payment date, it correctly still shows the earlier outstanding.

Exercise E — sales import: use the sample TRAIN-001 row from Chapter 15. Upload, approve valid rows and explicitly post. Expected: Cash Dr 200; UPI clearing Dr 600; consultation Cr 500; therapy Cr 300. Bank remains 46,000. Import the same receipt in a changed file: it must be flagged duplicate, not become another sale.

Exercise F — settle UPI: using a training bank statement, record reviewed settlement of that 600 clearing into bank without fees. Expected Dr Bank 600 / Cr UPI clearing 600; no extra revenue. Bank becomes 46,600, cash is 200 and UPI clearing returns to zero.

Exercise G — review: total cash/bank is 46,800; AP liability is 6,000; capital is 50,000; period profit/loss is revenue 800 less administration 10,000 = loss 9,200. Net assets after liabilities are 40,800, agreeing to capital less loss. Actual cash movement excluding opening is -3,200: bank payment -4,000 plus earned cash collections +800. A UPI-to-bank transfer is classified consistently under the reviewed cash-definition policy and is not another customer receipt.

Exercise H — correction: reverse TRAIN-PAY-1 at a later actual training date. AP outstanding reopens to 10,000 from that date, bank increases by 4,000 and the original payment stays visible as reversed. Explain why the earlier dated paid position must not be rewritten.

Exercise I — handover: export AP register/forecast, import review, trial balance, P&L, bank/cash ledgers and actual cash flow to both Excel and PDF. Point to one amount on screen, its source voucher and the same amount in each export. Confirm no export action created a voucher.

## 25. Suggested training session and acceptance checklist

Allow an introductory session of about three hours plus supervised practice. Suggested sequence: 25 minutes for debit/credit and dates; 25 for setup/openings; 45 for AP accrual/payment/extension and source links; 35 for standard sales import and exceptions; 30 for bank/clearing/report reconciliation; 20 for backups, corrections and handover. Adjust pace to the trainee's bookkeeping experience.

Before independent live use, the trainee should be able to identify the book/year/unit, explain invoice versus payment journals, process a partial payment without duplicating expense, extend a plan without posting, align and review a multi-receipt report, reject a duplicate, trace a bank match to the existing voucher, explain actual cash flow versus AP forecast, export a reconciled pack, and demonstrate backup and a safe correction in training books.

The reviewer should verify real source samples, applicable accounting/tax treatment, vendor controls, bank mappings, required financial disclosures, supported language examples and the actual Windows PC. Development/CI tests do not replace those acceptance steps. New portable encryption/recovery, mailbox ingestion, full MIS/executive pack and other tracker items remain separate from this AP/import delivery.

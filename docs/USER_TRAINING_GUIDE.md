# Yathartha — Bookkeeping Training and User Guide

Development version 0.35.1-dev | Guide updated 4 November 2026 | Windows | INR

Audience: a new bookkeeper, an accountant reviewing the work, and the person delivering the books to the hospital. This guide explains both the workflow and the bookkeeping behind it. Use the matching development executable; screen names refer to that version. Dates shown in examples are practice dates, not instructions to post into live books.

## 1. Start here: what the tool does

The application is now named Yathartha, with a saffron-and-blue wordmark. Its existing RijuBooks Windows data folder and older document filenames are retained for compatibility; renaming the application does not clear or move your saved books. Close the old application before opening Yathartha.exe.

Yathartha keeps one legal entity's books with operating-unit analysis for JP Nagar (JP), Kammanahalli (KM) and Vaikom (VK). It is a single-user, local Windows application. The same transaction must be entered only once, even when it appears in a hospital report, bank statement and invoice file. The bank statement normally reconciles an existing payment or receipt; it is not a second sale or expense.

The left navigation opens each module. Select the financial year and unit in the top selectors. All units means the entity view, not a separate company. Scroll the left navigation or the main workspace if a button is outside the visible area. Reports have their own date selectors where shown: change them and refresh before reading totals.

The new AP Vendor Invoices page records vendor bills, tracks payment dates, posts reviewed payments and exports an AP register/forecast. Sales receipt now has an Import sales receipt report button and Excel/CSV templates, so daily collections can be processed in batches instead of entered one at a time.

Posting always requires review. Previewing, uploading, changing a schedule or exporting a report does not itself mean that a journal was posted. The permanent evidence is the voucher ID in Vouchers and the corresponding ledger lines.

## 2. Install and use a safe training copy

1. Download the RijuBooks-Windows ZIP supplied for the matching build and extract all files. Do not run the application from inside the ZIP.
2. Find Yathartha.exe, normally under dist in the extracted bundle. The application does not require the end user to install Python.
3. Read packaged-selftest.json: version should be 0.35.1-dev and passed should be true. The included checksum file identifies the executable supplied by the build.
4. Use a disposable training book first. Do not practise by adding sample invoices to the live hospital book. Your administrator can start a demo copy with `Yathartha.exe --demo --data training.json`; the JSON training file is not protected for live use.
5. For normal Windows use, the default book is under `%LOCALAPPDATA%\RijuBooks\books.riju`. Keep the same Windows user/profile for that book.
6. In Settings & backup choose the external backup folder. Confirm the device is connected and a backup is actually created.
7. When an upgrade banner appears, configure the external backup first. The original-format book must be retained before the upgraded file is saved. Older executables cannot open format 22 books.

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

Date fields have a Cal button. Click it, choose month/year (use Go to jump), then click the day; Today, Clear and Cancel are available. You can still type an ISO date directly. Report From/Through, optional dates, AP dates and reversal dialogs use the same picker. A month-period field selects YYYY-MM; an exceptional-date list appends selected dates. For holiday/milestone text areas use Insert calendar date at the cursor and retain the required comma/CSV separators. Picking a date changes only the form until you save or approve its normal action.

For a simple completed transaction, enter narration in Journal studio and choose Prepare offline draft. For example: `Paid INR 5000 rent by bank on 1 November 2026 at JP Nagar`. The local model can extract supported dates, units, parties, amounts and methods, but the resulting lines still need your review.

Check date, unit, accounts, debit/credit amounts, source reference and party. A model draft is not a journal until approved. If the description is ambiguous, the tool clears the old draft and asks for clarification or a dedicated workflow. It does not invent GST/TDS, allocate an advance or post automatically.

Add or edit manual lines when you know the correct accounts. Each branch must balance; genuine cross-unit transactions need explicit inter-branch clearing. Save draft retains unposted work. Review & post voucher is the explicit posting step. Once posted, correct errors by a dated reversal and a new reviewed transaction rather than editing the original history.

The offline language component is a small authored statistical intent model, not a general generative LLM. Read MODEL_CARD_OFFLINE.md for supported topics, licence and limitations. A refusal is a request to review the source, not permission to disguise a taxed transaction as a simple expense.

## 7. AP Vendor Invoices: add the vendor

Vendor master is a separate visible item in the left navigation, also accessible from AP. Every saved vendor appears there immediately. Select a row and choose Edit selected vendor (or double-click) to change its name, default credit days, reference or active status. The stable vendor ID stays unchanged. Inactive vendors remain visible and retain existing invoices/payments; reactivate them before creating a new invoice. Changes apply to new invoices. Posted invoice names and credit terms retain their original source snapshot. Historical aliases cannot be reused to create another vendor and bypass duplicate checks.

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

You may reject duplicate/invalid rows before ticking the earned-service/tax/payment approval checkbox. Enter a rejection reason; their Decision must become REJECTED. Rejection alone does not approve the other rows. Then tick the review checkbox, choose Approve all valid rows and enter the approval basis. Only after all source rows have a decision should you choose Preview batch journals. The first preview tab now shows a table with Account code, Ledger name and INR debit/credit side by side. Source details retain the full source record; ledger names in the display do not change the saved journals.

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

## 26. End-to-end worked example: daily sales report to final financial reports

Follow this example in a disposable training book, never in live hospital books. It starts with the actual daily-sales file, accounts for the transactions, reconciles the bank and ends with P&L, balance sheet and cash flow. All amounts are INR, all transactions belong to JP Nagar (JP), and the two working days are 1–2 November 2026. Assume these specific training services need no separate GST/TDS entry, no depreciation and no closing journal. For real taxed receipts, follow the dedicated source workflow rather than copying this training tax assumption.

The guide ZIP includes Worked-Example-Daily-Sales.xlsx, the identical CSV alternative, Worked-Example-Bank.csv and verified expected financial reports in Excel/PDF. Import only one sales-file format, not both. The expected-report files are an answer key to read and compare, not transaction files to import. Nothing from these samples is automatically loaded into your book.

**Step 1 — Open the correct book and select the scope.** Extract and open Yathartha.exe. Ask the trainer to open a disposable demo/training book, using the command in Chapter 2. At the top select financial year 2026 and operating unit JP Nagar. This financial year runs 1 April 2026–31 March 2027. The report period later will be 1–2 November, not the whole year. Do not use Start clean books on live data just to practise this example.

**Step 2 — Establish the opening bank balance once.** In Journal studio select Transaction date 2026-04-01, unit JP Nagar and Opening balances. Enter narration TRAINING opening bank/capital. Choose Add manual line: account 1010 Bank, debit INR 50,000, unit JP. Add another line: account 3000 Capital, credit INR 50,000, unit JP. Review the balanced draft, select Review & post voucher and approve. There is no daily activity between April and October in this example, so the bank carries INR 50,000 into November. Opening balances must be dated 1 April; do not date the opening 1 November or post it again each month. Open Ledger A/c and confirm Bank's opening balance at 1 November is INR 50,000. If your practice book already contains an opening or other transactions, use a different empty training book instead of adding this opening twice.

**Step 3 — Pick the daily sales report.** Open Worked-Example-Daily-Sales.xlsx and inspect the Receipts sheet. Alternatively inspect the same rows in Worked-Example-Daily-Sales.csv. These are the two receipts:

| Receipt / date / unit | Earned revenue columns | Actual payment columns | Receipt total |
| --- | --- | --- | --- |
| WALK-001 / 2026-11-01 / JP | consultation 500; treatment 300 | cash 200; upi 600 | 800 |
| WALK-002 / 2026-11-01 / JP | consultation 200; room_rent 1,000 | card 1,200 | 1,200 |

All other monetary cells are blank/zero. Both rows use record_type earned and tax_mode no_separate_tax. Source revenue is consultation 700 + therapy 300 + room revenue 1,000 = INR 2,000. Source collections are cash 200 + UPI 600 + card 1,200 = INR 2,000. There is no bank collection yet. For your real report, align it to these same template headings, replace sample IDs with genuine unique receipt numbers and verify applicable tax/service recognition before uploading.

**Step 4 — Import and review the report.** In the left navigation select Sales receipt, then Import sales receipt report. Select the XLSX file or its CSV alternative once. In the review window expect two VALID rows and no INVALID/DUPLICATE rows. Uploading creates a queue batch, not revenue. Compare the valid-source category/payment totals to the source totals above. If they differ, stop and correct the source rather than changing the bank figure to make it balance.

Tick the earned-service/tax/payment review confirmation, select Approve all valid rows and enter TRAINING source totals and payment splits checked. Every row must have a decision. Select Preview batch journals and inspect the two balanced journals. Approve sales batch. Reopen Review sales report imports if needed and confirm PROCESSED. Do not import the CSV alternative after posting the XLSX: the same receipt IDs must be treated as duplicates.

| Source journal | Debits | Credits |
| --- | --- | --- |
| WALK-001 | Cash 1000: 200; UPI clearing 1110: 600 | Consultation 4000: 500; Therapy 4010: 300 |
| WALK-002 | Card clearing 1120: 1,200 | Consultation 4000: 200; IPD room revenue 4020: 1,000 |

Open Vouchers to view the source references and journal lines. In Ledger A/c through 1 November, Cash should be 200 debit, UPI clearing 600 debit and Card clearing 1,200 debit. Bank must still be 50,000 debit. UPI/card collection is not yet a bank deposit. Current code numbers above assume unchanged starter account mappings.

**Step 5 — Record a vendor invoice when received.** In AP Vendor Invoices set As at to 2026-11-01. Choose Add vendor: name TRAINING Office Supplier, credit period 0. Save vendor. Choose Enter invoice and fill the following:

| AP field | Training value |
| --- | --- |
| Vendor invoice number | WALK-AP-001 |
| Invoice / received / accrual accounting dates | 2026-11-01 for all three |
| Credit period / starts at | 0 days / Receipt date |
| Scheduled payment date | Blank, so contractual due date 2026-11-01 is used |
| Operating unit | JP |
| Net amount payable | 1,000 |
| Trade payables ledger / cost ledger | 2000 / 4590 Administration |
| Existing accrual voucher | Blank: this is a new simple accrual |
| Review basis | TRAINING administration service, no separate tax split |

Confirm source review, select Preview invoice accrual and Approve AP action. Expected journal: Dr Administration 1,000 / Cr Trade payables 1,000. Bank is still 50,000. The entire expense belongs in P&L even though the supplier has not been paid. The invoice is due in the AP register. Do not also enter a manual expense journal for this same invoice.

**Step 6 — Record the revised payment plan, then the actual partial payment.** Set AP As at to 2026-11-02 and refresh. Select WALK-AP-001 → Extend payment date. Enter effective date 2026-11-02, new date 2026-11-10 and reason TRAINING supplier agreement. Confirm, preview and approve. Contractual due stays 1 November, scheduled payment becomes 10 November and no voucher is added by the extension.

Assume a partial payment of INR 400 actually occurred on 2 November. Select the invoice again → Mark selected invoices paid. Enter Actual payment date 2026-11-02, cash/bank ledger 1010, reference WALK-PAY-001, amount 400 and the training evidence basis. Leave Existing exact payment voucher blank because this payment has not already been posted. Confirm actual payment evidence, select Preview payment journal and Approve AP action. Expected Dr Trade payables 400 / Cr Bank 400. AP must show Part paid, paid 400, outstanding 600. Administration expense remains 1,000, not 1,400. The remaining 600 is a planned outflow for 10 November; it is not another actual payment.

**Step 7 — Import the bank statement, without posting the AP payment twice.** Open Bank reconciliation, select bank 1010 and New statement scope JP Nagar. Select Import statement and choose Worked-Example-Bank.csv. Enter statement From 2026-11-01, Through 2026-11-02, Opening bank balance 50,000 and Closing bank balance 51,400. Use the CSV headings for date, narration, reference, debit, credit and balance, with the header on row 1. Review and import using the screen's confirmation. Select this imported statement in Statement / reporting period and choose Load statement if needed.

| Bank date | Reference | Bank debit / money out | Bank credit / money in | Running balance |
| --- | --- | --- | --- | --- |
| 2026-11-02 | WALK-UPI-001 | 0 | 600 | 50,600 |
| 2026-11-02 | WALK-CARD-001 | 0 | 1,200 | 51,800 |
| 2026-11-02 | WALK-PAY-001 | 400 | 0 | 51,400 |

The bank statement's debit/credit headings describe the bank's statement convention. They are not a request to copy those same sides mechanically into your Bank ledger. Importing the statement does not create three new sales/expense entries.

**Step 8 — Transfer UPI/card clearing into the bank.** In Bank transactions select WALK-UPI-001 → Review UPI / card / cash settlement. Choose UPI, Load channel receipts and select the WALK-001 gross receipt line for 600. Enter fee 0, eligible fee GST 0 and treatment None. Select Review & post settlement and approve the displayed journal: Dr Bank 600 / Cr UPI clearing 600. It posts and matches this settlement. If the business-calendar suggestion is unavailable, select the actual source manually after verifying the training bank advice.

Repeat for WALK-CARD-001 using Card and its WALK-002 receipt for 1,200, again zero fees/tax. Expected Dr Bank 1,200 / Cr Card clearing 1,200. UPI and Card clearing must both now be zero. Revenue must still total 2,000: settlement is not a second sale. In real work, review actual provider fees and supporting fee GST instead of copying these zero-fee assumptions.

**Step 9 — Match the existing vendor payment and finish BRS.** For WALK-PAY-001 choose Suggest book matches and review the AP payment voucher, or select that bank row and the existing Bank credit 400 on Book movements, then Match selected bank + book rows. Do not choose Create reviewed adjustment for this payment, because AP already posted it. Open BRS / handover: statement closing and book bank closing should both be 51,400, with zero variance and no unmatched training rows. After checking the proof, use Finalise statement. A finalised bank period needs a reasoned reopen before later corrections.

**Step 10 — Review ledger and trial-balance checkpoints.** Open Ledger A/c or Financial reports → Trial balance. Select JP Nagar and dates From 2026-11-01 / Through 2026-11-02, then refresh. Read the Closing Dr/Cr columns, not just November movement. With unchanged starter accounts, the nonzero closing balances should be:

| Ledger | Closing debit INR | Closing credit INR |
| --- | --- | --- |
| 1000 Cash | 200 | 0 |
| 1010 Bank | 51,400 | 0 |
| 4590 Administration | 1,000 | 0 |
| 2000 Trade payables | 0 | 600 |
| 3000 Capital | 0 | 50,000 |
| 4000 Consultation revenue | 0 | 700 |
| 4010 Therapy revenue | 0 | 300 |
| 4020 IPD room revenue | 0 | 1,000 |
| TOTAL | 52,600 | 52,600 |

UPI/card clearing are zero and may still appear as zero-value rows. Trial-balance differences should be zero. AP register outstanding is 600 and should reconcile to Trade payables credit 600. An unexpected account, extra sale, wrong bank total or unregistered AP difference means an earlier step needs investigation before reports are delivered.

**Step 11 — Generate and export P&L.** Open Financial reports. Set Report to Profit and loss, From 2026-11-01, Through 2026-11-02 and global unit JP Nagar. Select Refresh. Expect Revenue 2,000, Expense 1,000 and Profit / (loss) 1,000. The unpaid supplier portion is still an expense under accrual accounting. The opening capital and clearing-to-bank transfers are not revenue. Select Export Excel (.xlsx) and Export PDF, save with unit/period in the filename and compare their totals to the screen. Repeat this selector/refresh/export procedure for the other reports below.

**Step 12 — Generate and export the balance sheet.** Set Report to Balance sheet with the same period and refresh. This report is a position through the end date, including the opening carried from April. Expect total assets 51,600 = Bank 51,400 + Cash 200. Expect liabilities 600 = unpaid vendor AP. Equity is Capital 50,000 + Unclosed accumulated result 1,000 = 51,000. Total liabilities/equity is 51,600 and the balance-sheet difference is zero. For this exercise, do not enter a year-end closing journal just to make the current profit appear in equity; the report includes the unclosed result automatically. Export Excel/PDF.

**Step 13 — Review cash-flow setup before generating cash flow.** Open Cash flow setup → New / revised policy. Use effective date 2026-04-01, cash/equivalent codes 1000,1010 and a clear training policy basis. Review the proposed classifications: these training service collections, administration expense, trade payables and UPI/card clearing belong to Operating; opening capital is an opening balance, not a November financing receipt. UPI/card are excluded from cash/equivalents in this example until settlement. Confirm and Save policy version. Never change the cash-definition policy just to force an unexplained difference to zero.

**Step 14 — Generate actual direct and indirect cash flow, then the separate AP forecast.** In Financial reports choose Cash flow - direct, the same November dates and JP Nagar, then Refresh. Operating receipts should be 2,000: cash receipt 200 plus actual UPI/card bank settlements 1,800. Operating payments are -400. Net operating cash is +1,600, investing/financing movements are zero, opening cash/bank is 50,000 and closing cash/bank is 51,600. The April opening is carried forward, not recorded as a November cash flow. Check both cash and direct/indirect reconciliation differences are zero; export Excel/PDF.

Choose Cash flow - indirect and refresh. Expect profit 1,000 plus the increase in trade payables 600 = operating cash 1,600. There are no outstanding clearing balances or other adjustments in this finished example. Export Excel/PDF. Cash differs from profit because 600 of the expense is still unpaid, not because the revenue was posted twice.

Now open AP Vendor Invoices, set As at 2026-11-02 and Forecast through 2026-11-30, then choose AP forecast Excel/PDF. Expect only -600 scheduled for 2026-11-10. Alternatively choose Financial reports → Cash flow - AP forecast, From 2026-11-02 / Through 2026-11-30. Its From date is the forecast as-of date. Do not add this planned -600 to the actual -400 paid: the two reports answer different questions.

**Step 15 — Produce the handover pack and preserve the evidence.** In Financial reports select Financial pack — Excel or Financial pack — PDF for the reviewed scope/period. For this November historical pack, the included AP forecast uses the report's From as its as-of date; use the separate AP forecast just described for the explicit 2 November planning position. Cash flow setup export uses its own actual reporting end and subsequent 90-day horizon. Label these horizons so the recipient cannot confuse historical actuals with a forward plan.

Save the source sales file, source bank statement, reviewed import summary, AP register/reconciliation, ledgers, BRS and the three financial statements. Compare your results with Worked-Example-Financial-Reports.xlsx/PDF. Confirm the external backup. For actual accountant-ready presentation, complete Statement review mappings/disclosures and other required tax, asset and source review; this small example demonstrates workflow and arithmetic, not complete statutory financial statements.

**Final check:** sales 2,000; administration expense 1,000; profit 1,000; bank 51,400; cash 200; AP 600; assets and liabilities/equity both 51,600; actual net operating cash 1,600; future AP outflow 600. If your figures differ, trace source vouchers and duplicate imports before posting any unsupported balancing journal. To replay the exercise, use another disposable book; importing the same receipts into this completed book must remain blocked as duplicates.

## 27. AP bulk invoices: upload the same fields instead of typing each invoice

In AP Vendor Invoices, Upload bulk invoices is next to Enter invoice. Download Bulk invoice Excel template or Bulk invoice CSV template. The Excel template has Invoices, Vendors, Units, Accounts and Instructions sheets. A template exported from your local book includes lookup snapshots of its active vendors/units/accounts; the public blank template contains no customer's vendor data. These lookups help selection but do not create or edit masters automatically.

One row is one vendor invoice. Preserve the column headings (case/spacing/punctuation are normalised; recognised prior headings are supported). Excel uses sheet Invoices; a single-sheet workbook is also accepted. If a different workbook has multiple sheets and no Invoices sheet, select the exact source sheet when asked. Use literal values, not formulas, with actual Excel dates or YYYY-MM-DD strings. Invoice IDs should be text to preserve leading zeros.

| Column | What to enter | Default / source rule |
| --- | --- | --- |
| Vendor Name | Saved vendor legal/source name | Must resolve to one active Vendor master record; no silent vendor creation |
| Vendor Invoice Number | Supplier's invoice reference | Same vendor/invoice fiscal-year duplicate check as manual entry, across units |
| Invoice Date | Date printed on supplier invoice | Required |
| Invoice Received Date | Actual receipt date | Required |
| Accrual Accounting Date | Reviewed booking date | Required; ordinary period/source guards apply |
| Credit Period Calendar Days | Agreed whole days | Blank uses vendor default captured at validation |
| Credit Period Starts At | Receipt date or Invoice date | Blank means Receipt date |
| Scheduled Payment Date | Planned date | Blank uses computed contractual due date |
| Operating Unit | Active code or exact unit name | Required |
| Net Amount Payable to Vendor INR | Net vendor liability | Positive INR, no more than two decimals |
| Trade Payables Ledger | Vendor liability code | Default 2000; it is not a GST/TDS payable ledger |
| New Accrual / Cost Asset Ledger | Genuine debit account | Required for a new accrual, e.g. 1100 for medicines kept in stock |
| Accounting Review Basis | Source/accounting/tax review evidence | Required per invoice |
| Existing GST/TDS/CWIP Accrual Voucher (optional) | Original unpaid source voucher ID | Blank creates a new simple accrual; a valid link registers its payable without reposting |

The earlier spreadsheet heading Tax payables ledger is recognised as the vendor Trade payables column with a warning. The actual ledger still must be grouped Trade payables; the importer will not treat a GST/TDS liability as vendor AP. For separately accounted GST/TDS/retention/CWIP, first post the correct source in its dedicated workflow and link it, as with manual entry. The import does not infer tax from the total amount or supplier name.

The XLSX pre-fills Receipt date and 2000 for 1,000 input rows. Those defaults alone are placeholders and are ignored until actual invoice fields are entered; no sample invoice is preloaded or posted. Credit days remain blank so each vendor's default can apply rather than forcing every supplier to 45 days. The cost ledger is deliberately blank so medicines are not accidentally booked to Administration. Add additional source rows if needed within normal import limits.

1. Add/correct vendors in Vendor master and check the intended cost, payable and unit mappings. Prepare the source file with the same values you would enter manually.
2. Select Upload bulk invoices and choose the XLSX/CSV. Upload retains source row, original field values, filename/digest and all valid/invalid/duplicate rows, but posts nothing.
3. Review valid totals and flagged issues. Select a row to read its error; use View selected invoice for every original/resolved field. Show flagged rows only helps isolate errors. The table includes named accounts, credit basis and contractual/scheduled dates.
4. Reject duplicates/invalid rows with a reason; no posting-review checkbox is needed for rejection. Keep them in history and correct the source, rather than changing an invoice number to bypass a duplicate. A cancelled prior invoice also retains its identity.
5. If a vendor/account/default was corrected, use Revalidate after master changes. Previous approvals clear for fresh review while explicit rejections stay rejected. Changed vendor defaults cannot silently change already-reviewed values at posting. Corrected external source data should be uploaded as a new file revision.
6. Tick the vendor/source/period/accounting/tax review confirmation, then Approve all valid invoices or approve selected rows with a reason. Bulk approval respects explicit rejections. Every source row needs an approval/rejection decision.
7. Select Preview invoice journals. Check account code/name and debit/credit amounts. New invoices post Dr cost/asset / Cr AP; existing source links do not repeat their accrual. Approve AP action registers the approved batch atomically. If a selected source becomes invalid or duplicated, no part of that attempted batch posts.
8. Confirm PROCESSED in Review bulk invoice batches. The AP register now lists the invoices and computes their due/overdue status and cash-outflow forecast using the same logic as manual entries. Uploading does not mark them paid or create a bank payment.
9. Export Review Excel/PDF if required and process actual payments later through Mark selected invoices paid. Import queue also routes these batches to their AP review screen. Cancel unused batch is available only before posting, with a reason; processed invoices use the normal AP/source correction controls.

Duplicate checks cover already registered/manual/cancelled invoices, repeated rows and other queued AP files using the same vendor and invoice fiscal year. A renamed file cannot force a second copy. Registering an existing source must fit its unregistered payable capacity. Never upload the same invoice as a new accrual if it was already posted elsewhere; link the original unpaid voucher once.


### Reading and correcting bulk invoice validation errors

Invalid rows are highlighted red and duplicates amber. Source row number, vendor, invoice, Validation and Reason / correction are the first columns, followed by the original payable amount. A summary above the table lists affected Excel/source rows. The first flagged row is selected automatically; its full reason remains above the table even when you scroll horizontally. Select Show flagged rows only to focus on corrections. Double-click or View selected invoice shows all original fields under readable labels and the full reason. Review Excel/PDF includes a separate validation reason column. An early vendor error no longer hides the entered dates, unit, ledger and amount; invalid amount text is displayed as entered rather than a misleading zero.

For example, if Synthetic Pharme Supplier is entered while Vendor master contains Synthetic Pharma Supplier, the app suggests the closest saved name but never substitutes it automatically. Check the invoice first. If it is a source typo, cancel the unused pending batch, correct the workbook and upload the corrected file. Revalidate only checks stored source rows; it does not reread a file edited outside the tool. If the source genuinely names a missing supplier, add that vendor in Vendor master and revalidate the pending batch. Revalidation clears approvals but retains explicit rejections. Never create a second vendor to bypass a spelling error or approve a duplicate without checking the original invoice. No upload or error review posts a journal.

## 28. T-form balance sheet and client report logos

Open Financial reports. Choose **Balance sheet - T form**, set From/Through using the calendars and select the operating unit or All operating units. Click Refresh. Liabilities and equity appear on the left, assets on the right. Account codes and names appear together. The final line shows both totals; Assets minus liabilities and equity must be zero. Accumulated loss and contra assets retain their negative signs. This uses exactly the same closing balances as the vertical Balance sheet; it does not post or alter a transaction. Both layouts are included in the financial pack.

Example: after importing daily sales, posting vendor invoices, recording actual payments and reconciling the bank as in the worked example, select Balance sheet - T form through 2026-11-02. Check that both sides total INR 51,600 and the difference is zero. Export Excel or PDF. Return to Profit and loss to check profit INR 1,000 and Cash flow - direct to check net movement INR 1,600. Changing the balance-sheet layout does not change these results.

Click **Report logos** in Financial reports, or **Report logos — client / AXIOM** in Settings & backup. Choose / replace Client logo (left) and AXIOM logo (right), then Done. Use PNG or JPEG, maximum 5 MB and 16 million pixels. A transparent PNG usually prints best. The app preserves image proportions. You can replace only the client logo when preparing a different client's book, retain AXIOM on the right, or remove either image. Check the preview and export a PDF before sharing.

Logos are embedded in this client book and its backups, not linked to the image's original location. They are not a global setting: configure them in each client's separate book. Refresh a report after changing images. Generated PDF headers repeat logos on every page; Excel sheets include them at the top. Financial report packs (including P&L, balance sheet, cash flow and reviewed statements) use the same branding. CSV is text only. Older exported files are unchanged; generate fresh files to apply replacements. Original logo files are not bundled in public downloads; choose your own images in the app.


## 29. Bulk upload the vendor master

Use this before importing AP invoices for a new client. Open **Vendor master** from the left navigation. Click **Vendor template — Excel** or **Vendor template — CSV**. Fill the template without changing its headings; for Excel, use the Vendors worksheet. There is no macro to install. The public blank template contains no client names.

| Column | What to enter |
|---|---|
| Vendor Name | Required. Exact legal/source name that will be used on invoices. |
| Default Credit Period Calendar Days | Whole calendar days, 0–3650. Blank defaults to 30; zero means immediate terms. |
| Vendor Code / Source Reference | Optional text identifier. Preserve leading zeroes by keeping this column formatted as text. |
| Active | Yes or No. Blank defaults to Yes. Inactive masters remain saved but cannot be used for new AP invoices. |

Example practice row: Training Medicine Supplier, 45, TRAIN-001, Yes. This creates one active vendor with a 45-day default credit period; it creates no opening balance, invoice, payment or journal.

Click **Upload bulk vendors**, select the CSV/XLSX, and review the source rows. NEW rows are eligible for creation. INVALID rows show a correction reason in red; DUPLICATE rows are amber. The selected row's full explanation is above the table. Duplicate checks include vendors already saved, their historical names and earlier rows in the same file. Spelling variants must not be used to create a second master for the same supplier.

Click **Select all new vendors**, or select specific NEW rows using Ctrl/Shift, then **Save selected new vendors**. Only the selected new vendors are saved; invalid and duplicate rows are not saved or overwritten. A late duplicate causes the whole selected group to stop without a partial save. The success message returns you to Vendor master, where new vendors are immediately visible and editable. Closing the preview without saving makes no changes.

This import creates new masters only. To change an existing vendor's terms, reference, name or active status, use **Edit selected vendor**. Posted invoice snapshots and credit terms stay intact. Correct invalid source rows in the file and upload again; previously saved vendors will appear as duplicates. No imported row creates or updates bank details, GST/TDS registrations or accounting balances. After the vendors are saved, use AP Vendor Invoices to enter or bulk-upload invoices; revalidate an already-pending invoice batch if it was blocked only by a missing master.


## 30. Petty cash expenses, cash funding and historical bulk reports

Open **Petty cash** on the left navigation. This page records actual cash disbursements and funding through 1000 Cash. It provides manual entry, standard Excel/CSV bulk upload, direct category-by-date matrix upload, saved batch review and a dated cash register with Excel/PDF exports. Cash funding and sales receipts are different events: never count the same cash twice.

### Choose the accounting treatment before posting

| Treatment | Debit | Credit | Reporting effect |
|---|---|---|---|
| Expense | Genuine reviewed expense ledger | 1000 Cash | Expense in P&L and lower cash |
| Stock purchase | Inventory asset, such as 1100 Medicine inventory | 1000 Cash | Inventory asset; no automatic medicine cost of sales |
| Staff advance | Reviewed Other assets staff-advance ledger | 1000 Cash | Advance asset, not salary expense |
| Liability settlement | Existing credited Other liabilities salary/payroll ledger | 1000 Cash | Clears an accrued liability; no second expense |
| Cash top-up | 1000 Cash | Genuine bank/cash, funding liability or equity source | Funding/transfer; not new sales or expense |

Use Chart of accounts to create/select suitable staff-advance and salaries-payable ledgers if they are missing. Account numbers in a customised book can differ. Salary settlement checks credited balances at the payment date and later recorded settlements, including combined bulk rows. If the salary was never accrued, review payroll recognition first; the report label alone is not proof of an existing liability. Vendor-invoice payments belong in AP Vendor Invoices, and GST/TDS settlements belong in their dedicated pages. This simple petty-cash workflow does not calculate GST/TDS or input-tax splits.

### Enter one actual cash transaction

Click **Record cash expense / top-up**. Select the actual historical payment/receipt date with the calendar; the date is blank initially so today's data-entry date is not assumed. Enter a stable unique voucher reference, operating unit, category, treatment, counterpart account, amount, description/payee and accounting review basis. Confirm the source/tax/no-duplicate review. Click **Preview petty cash journal**, inspect the named accounts and date, then **Approve petty cash journal**. The journal updates the cash ledger and financial reports, and the register refreshes. Corrections retain history through Vouchers reversal and a new correction reference.

Example training expense: 2026-09-01, PC-TRAIN-001, JP, Office, Expense, 4590 Administration, INR 100, Office supplies, with a reviewed cash-voucher basis. Journal: Dr Administration100, Cr Cash100. Example funding: actual INR1000 withdrawal transferred to petty cash: choose Cash top-up, counterpart1010 Bank; journal Dr Cash1000, Cr Bank1000. Match that bank movement to the withdrawal in bank reconciliation. Individual cash purchases do not each appear on the bank statement. If the withdrawal was already posted, do not post another top-up.

### Standard row-by-row bulk template

Click **Excel template** or **CSV template**. Excel uses the Expenses worksheet and includes Accounts/Units snapshots and Instructions; public blank templates contain no client data. Each row must contain all nine headings: Date, Voucher Reference, Operating Unit, Category, Treatment, Counterpart Ledger, Amount INR, Description, Accounting Review Basis. Use true Excel dates or YYYY-MM-DD, positive amounts and literal values. Blank rows are ignored. Each actual transaction/category/date needs its own stable reference; changing an amount or filename must not be used to bypass duplicate detection. Importing a previously manually entered unit/date/reference is blocked.

Click **Upload bulk petty cash**, choose the file and confirm review to stage it. Staging does not post. Rows already contain their unit/treatment/account/basis; the matrix defaults do not override them. Invalid/duplicate rows show their reasons in red/amber and a full explanation above the table. Reject flagged rows with a reason or cancel the unused batch, correct the source and reupload. Approve selected valid rows or **Approve all valid rows**, then **Preview cash journals** and approve. Every row must have an explicit approval/rejection; a late validation failure rolls back the entire selected group. Posted sources stay in the saved batch and change history.

### Upload the original category-by-date report

The supported matrix has a Date row containing actual dated columns, category labels in that row's Date-label column, Expense Details, category rows and Total. Each nonzero category/date cell becomes one cash-outflow source item. The exact cell coordinate is retained for tracing. The importer does not execute formulas; expense amount cells must be literal reviewed values. Formula summary cells, blank/zero cells, opening balance, Cash Received, daily totals, closing balance and cumulative expenses are excluded from journals.

Choose the operating unit explicitly, a stable report reference (for example PC-2026-09), and a shared accounting review basis. Review every proposed category treatment and counterpart ledger in the scrollable mapping panel. Suggestions are editable proposals, not a final accounting conclusion: provisions/food, consumables, medicines and salary labels require actual source review. Staff advances/salary-payable mappings stay blank until an appropriate ledger is selected. Confirm and stage. Review source cells and errors, reject or correct flagged rows, approve valid items and inspect journals before posting. Mapping corrections require cancelling the unused batch and reuploading; saved defaults help the next report but do not silently change an existing staged source.

### Reconcile physical cash and generate reports

The source warning shows its opening, receipts, computed cash outflow and closing when literal source controls can be checked. These controls never create funding/opening entries. A negative physical-cash opening/closing means custody/funding or staff-paid items need investigation; no balancing figure is invented. Starting a new book requires reviewed opening balances through the normal setup, not a second opening journal from the monthly report. If Cash Received is patient cash already recorded in Sales receipt, do not enter a top-up. If staff personally paid an expense, review the genuine reimbursement/funding liability instead of treating unsupported negative physical cash as normal.

Refresh the register for the correct dates/unit and export Excel/PDF. Expenses affect P&L; stock/advances remain assets; salary settlements reduce liabilities. All posted movements update Balance sheet/T form. Cash flow uses its reviewed cash/equivalent definition: a transfer from included bank to included cash nets to zero, while actual disbursements are classified by their genuine counterpart. Reconcile the cash custodian's records separately from bank reconciliation. Only real bank movements, such as a funding withdrawal, belong in bank matching.


## 31. Bank reconciliation with side-by-side checkboxes

Open **Bank reconciliation → Reconcile side by side** using the indented left-menu option or the Reconcile side by side button on the Bank reconciliation page. It opens a separate large comparison window: bank transactions on the left and selected sales/invoice-payment sources on the right. On Windows it opens maximized; the fallback uses approximately 90% of screen area, and its minimum size remains above 75% of screen area. The transaction panes expand with this window, independently of the main page. Each row has a visible Tick checkbox. Click the box, or select a row and press Space, to toggle it. Selections on one side do not clear the other side. The bank total, source total, fees and difference update immediately. The primary Automatically reconcile selected button and review confirmation sit above the lists. The centre divider is draggable, each list has its own scrollbars, and the amount is beside the date. The main Bank reconciliation page retains Bank transactions, Book movements, Match history, BRS / handover and Business calendar. The dedicated workspace has its own Bank, new-statement scope and Statement selectors; switching the main page does not switch its bank or statement. Reopening the workspace while it is open brings forward the same window and preserves checked rows. Close returns to the parent banking page without changing accounting records.

### Upload and choose the source

1. Select the correct INR bank ledger and new-statement scope. Shared statements use All operating units; exclusive statements use the genuine unit. Click **Upload bank statement**. CSV/XLSX/OFX parsing, saved layouts and verified opening/closing balances work as before. Original XLS requires conversion first. Check the exact dates: May2026 must end31May2026, not31May2027. Approve the bank import, then choose its Statement in the large window and click Load.
2. Click **Upload sales report** for the existing standard Sales receipt CSV/XLSX (Receipts worksheet). The template still contains receipt date/number, unit, party, earned service categories, payment splits and tax treatment. Select Sales receipts in Compare bank against. The file is loaded only for reconciliation review; uploading alone creates no receipt journal.
3. Alternatively click **Upload invoice payments** and choose the new payment template (Payments worksheet). Include paid amounts only; invoices still unpaid are omitted. Select Invoice payments in Compare bank against. The report never creates a new vendor invoice: the invoice must already be registered in AP.
4. Select the uploaded Source report and click **Load source / refresh**. All posted sources can be used without uploading the same records again. Exact file reupload reuses its saved source document. Source rows, errors, filename and SHA256 remain in local history. Source files do not become bank transactions, and uploading does not match/post anything.
5. Find text / amount searches dates, names, descriptions, references and amounts on both sides; click Find. Applying filters/refresh clears checks, so review the new visible selection. Clear checks removes all ticks. Unmatched/partial bank transactions and outstanding source rows are shown; fully reconciled items disappear from this working list and remain in Match history.

### Invoice payment report headers

| Header | Required content |
|---|---|
| Vendor Name | Exact saved legal/source vendor name or its saved historical name. |
| Invoice Number | Registered vendor invoice number, preserving leading zeroes as text. |
| Invoice Date | Actual invoice date, identifying the correct invoice/fiscal year. |
| Actual Payment Date | Historical transfer/payment date, not today's data-entry date. |
| Operating Unit | Code matching the registered invoice, e.g. JP or KM. |
| Bank Ledger | Actual selected INR bank account code, e.g.1010. |
| Paid Amount INR | Positive amount paid for this invoice, including actual partial payments. |
| Transfer Reference | Actual full bank UTR/cheque/transfer reference. |
| Accounting Review Basis | Payment evidence/source review explanation; the screen also records a reviewed reconciliation basis. |

Use true Excel dates or YYYY-MM-DD, literal values and the exact headings. Several invoices paid in a single transfer share payment date, bank and reference; select all related rows. A single invoice paid on separate dates uses separate rows and actual transfer references. Duplicate invoice/transfer identities within one file are blocked. Existing AP payment bank legs may represent several invoices and are displayed once with the related invoice references, preventing double selection of the same ledger movement.

### Tick and reconcile

Tick the bank transaction(s) on the left and corresponding receipt/payment transaction(s) on the right. One-to-one, one-to-many and many-to-many totals are supported. Work with deposits or withdrawals in one action; unrelated incoming/outgoing amounts must not be netted. Negative displayed values mean a withdrawal/payment; positive values mean a deposit/collection.

For example, one bank withdrawal INR1000 settling invoices400+600 is checked against both unrecorded invoice-payment rows. An existing combined AP transfer is instead one bank-ledger source row, labelled with its included invoices. A bank deposit INR1500 can be checked against several UPI/card receipts totalling1500. Already-posted bank receipts match directly. Unsettled UPI/card/cash receipt parts create a clearing-to-bank settlement on each actual bank date, preserving individual source allocations. Cash/clearing availability, units and receipt dates are checked; receipts cannot fund a bank deposit before they exist.

Click **Options / templates** to reveal settlement fees, the reconciliation review-basis field, timing overrides and template exports. These less frequent controls are initially hidden to leave more room for transactions. If the bank net is lower because of an actual documented settlement fee, enter the exact **Reviewed settlement fees INR**. Source gross minus fee must equal bank net. The fee posts to4560 Bank and payment processing charges, without guessed GST input. Do not use fees as a balancing plug. Fees on already-posted bank journals and tax-bearing fee splits use the existing reviewed adjustment/settlement workflows.

Tick the source/date/unit/accounting review confirmation and click **Automatically reconcile selected**. A preview shows the totals, exact zero difference, number of new journals and named debit/credit accounts. Check the actual dates and references, then **Confirm reconcile**. The action is atomic: a mismatch, locked period, missing invoice, insufficient payable/cash, duplicate, date conflict or changed book after preview saves no partial result. Posted-bank allocations prefer transfer references and dates rather than the order of mouse clicks. Matched rows disappear; undo/reopen remain in Match history and BRS / handover under existing date/period controls.

### Understand when journals will be created

- Existing posted bank movement: create match links only; no second sale, expense or payment journal.
- Selected sales receipt not recorded yet: after confirming earned-service/tax/payment review, create its normal complete Sales receipt entry once, including all its service/payment splits. Only the selected bank/clearing parts are reconciled; other parts remain outstanding. New receipts are posted together in one reviewed source batch. A pending Sales receipt import must be completed/corrected there first.
- UPI/card/cash collection already recorded but not banked: post only the reviewed clearing-to-bank settlement (plus explicit fees if supplied), not revenue again.
- Selected invoice payment not recorded yet: create the ordinary AP payment with the report's actual historical date and reference, then match its bank credit. The AP invoice must exist, be accrued before payment and have sufficient dated outstanding capacity. Several invoices in one transfer become a grouped AP payment.

Amber source rows need an accounting entry and are visible in the preview. Red rows are blocked; select a row to read the full reason above the lists. A previously recorded payment with a conflicting date must be corrected in AP rather than paid twice. If a bank journal exists but has not been allocated to AP, link the exact existing voucher in AP first. If existing manual sales use unrelated receipt references, do not upload them as new sales to force a match: use All posted sources/review the original receipt first, because the tool cannot infer that two unrelated reference numbers represent the same business event.

A book date outside the bank business-day tolerance needs review. Correct a mistaken data-entry date first. Genuine cheque/settlement timing differences can use **Options / templates → Allow a reviewed date/reference timing difference**, which is recorded in history; it does not rewrite the source date. Complete bank reconciliation in BRS / handover after reviewing all residual items and balances. This checkbox workflow matches selected transactions; it does not automatically classify every unmatched bank line or certify the monthly BRS.

## 32. Business Pulse — Monthly Performance

Open Financial reports → Business Pulse — Monthly Performance. This separate large window shows April–March monthly metrics with navy, blue, peach and coral heatmap cells. Select the financial year, through date, operating unit and display unit, then refresh. Click a metric cell to inspect its source and voucher references. Export Excel or PDF for client reporting; Report logos supplies the client logo on the left and AXIOM on the right.

Revenue is earned revenue from selected revenue ledgers. Cash, UPI and card are customer collections; advances, tax and credit collections can make them differ from revenue. Funding and transfers from clearing accounts to bank are excluded from customer collections.

Patient visits use receipt counts for now, once per receipt even when payment methods are split. This is a visit proxy, not a unique-patient count. ARPP is revenue divided by total visits. A zero or missing denominator gives N/A. New patients require a supplied registration count; they are never inferred from names or receipt numbers.

Use Monthly counts / review to enter new-patient counts, an optional actual-visit override and the source/review basis. Blank new patients means unavailable; zero means confirmed zero. Excel/CSV templates and bulk input review support one row per month and operating unit. ALL observations and individual unit observations are separate. Imported updates retain an audit revision and create no accounting journal. Full-month count inputs do not apply to a partial-month through date.

Review metric mappings before handover. Salary disbursed and staff overtime payments use reviewed dedicated ledgers and actual cash/bank payments. Shared salary/overtime ledgers cannot identify the split. Unmapped figures show N/A; mixed cash/noncash allocations that cannot be identified reliably require review. Compliance costs are mapped expenses, not GST/TDS remittances.

Petty cash defaults to all recorded petty-cash disbursements, including stock, advances and salary settlements, excluding cash top-ups. These figures can overlap salary or vendor-payment classifications: do not add the rows as an expense total. Vendor payments use actual AP payments and count an invoice once per month, including part-payments; reversals affect their posting month.

Each metric's colour compares it with its own observed history through that month: Q1 highest (navy), Q2 blue, Q3 peach, Q4 lowest (coral). Higher costs are not automatically good performance. Fewer than four observations or flat history use a neutral fill. Future/unavailable cells show N/A. Months with entries remain provisional until explicitly marked Books Reviewed; no-posting months are N/A unless reviewed as complete. Excel includes source details and mappings, with amounts in actual INR on the source sheet even when the display uses thousands/lakh. ARPP always uses INR.

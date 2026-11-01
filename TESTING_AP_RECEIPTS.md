# AP vendor invoices and standard sales receipt import — 0.29.0-dev

Use disposable books; the full newcomer workflow is in docs/USER_TRAINING_GUIDE.md, also distributed as the 29-page PDF plus Excel/CSV templates in the Windows build artifacts.

## Vendor AP acceptance

Open AP Vendor Invoices in the left navigation. Add vendor, enter source/reference/receipt/accounting dates, credit days/basis, planned date, unit, payable and cost. Preview and explicitly approve. Verify Dr cost/asset / Cr Trade payables at accounting date, no cash movement at invoice receipt or scheduled due. Due date = reviewed basis date + calendar credit days. Test zero days and overdue receipt. Payment plan must not masquerade as a future expense/bank journal.

Select outstanding invoice(s), record actual payment date, bank and reference, preview Dr AP / Cr bank and approve. Single partial/multiple full payments supported; multiple units, duplicate selections, overpayment and outgoing collection-clearing use blocked. Existing exact payment voucher can be linked once without reposting. Existing reviewed unpaid GST/TDS/CWIP accrual can be registered against remaining source payable without duplicating expense/tax. Keep retention/TDS liabilities separate from net vendor payable.

Extend a due invoice with effective date/later payment date and reason. Contractual due/history remains; no journal. App-open India-date banner refreshes periodically and offers AP processing; no OS/email/bank task is claimed while closed. Historical as-of positions/schedules remain correct. Cancel accrual only after dependent payments reversed; a shared multi-invoice source cannot be cancelled through one invoice row. Check reversal chains and future booked payment capacity against backdated duplicates.

Export AP register, payments, source reconciliation, extension history and forecast to Excel/PDF. Compare screen/source voucher amounts. Unregistered payable differences remain visible. Actual cash flow excludes unpaid invoices; actual AP settlement follows provable reviewed source classification. Financial reports' AP forecast uses From as as-of; AP export uses explicit As at/horizon; overdue items carry into start, partial payments reduce balance, full payments remove it after their date. Linked ambiguous sources require normal cash-flow classification review.

## Standard receipt acceptance

Sales receipt → Excel receipt template / CSV receipt template → Import sales receipt report. Workbook sheet Receipts; all 28 exact headings; blank template data so no sample can be posted accidentally. Use one earned no_separate_tax receipt per row. Preserve all 15 categories and five actual payment splits including explicit bank 1010 and Other clearing. Totals must agree; no formula/negative/extra-decimal values or advance/refund/tax inference.

Upload mixed valid/invalid/duplicate rows. Every row/error persists; nothing posts. Confirm source/tax review, approve valid rows in bulk, reject flagged rows with reason, then preview/approve journals. Unresolved rows block posting. Changed locks/masters during review must reject atomically. Reopening processed batch must not post it again. Check edited-date/renamed-file duplicates in same unit/FY and cross legacy/standard imports; other units/FYs remain independent. Correct rejected rows can be reimported. Receipts entered manually without source identity need manual duplicate review.

600-receipt regression proves one journal/source count per receipt, exact balanced category/payment totals and the local CPU budget. Native packaged self-test posts/roundtrips 100 standard receipts. Test Excel/PDF review reports, metadata, literal text, source filename/row/digest and work-volume counts. Test actual client report samples and the target Windows PC before live adoption.

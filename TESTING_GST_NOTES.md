# GST credit/debit notes — unpublished 0.11.0-dev

This draft continues B08 with invoice-linked domestic GST notes. Existing GST invoices, tax masters, history, bank reconciliation, FX and ledgers are preserved. No executable or environment publication is included. Windows/client acceptance remains pending; the public Windows executable remains 0.5.0.

## Upgrade

Format/schema 7 identifies signed GST note documents so an older executable cannot silently treat them as ordinary positive invoices. Formats 1–6 remain readable. The first upgraded save requires the existing original-format external-drive backup, byte verification and saved-state integrity checks before migration. Preserve that original backup.

## Test the workflow

1. In disposable books, prepare and post a domestic GST invoice using a reviewed rule as described in TESTING_GST_ACCOUNTING.md.
2. Open **GST accounting → Credit / debit note** and select the original invoice. Enter a note date on/after the invoice, Credit note or Debit note, unique note reference, adjustment base excluding GST, refund/balance-adjustment ledger and reason.
3. A credit note reduces billing; a debit note increases it. For sales credits, revenue/output tax are debited and the selected refund/control account credited. For purchase credits, eligible input tax and cost are credited; ineligible GST reverses through cost. Debit notes apply the opposite direction. The original branch, registration, supplier/customer reference, rule/rate/source and ITC treatment are retained; later master-rate changes do not rewrite these documents.
4. Select a bank ledger only when the note actually includes a refund/payment. Otherwise choose the correct receivable, payable or advance control. The application does not infer whether money moved. Prepare and review the complete journal, note amounts and original links before approving. Editing fields requires a new preview; cancelling approval must create nothing.
5. Try a partial credit and then the remaining balance. Total credit cannot exceed the balance after debit notes and existing credits. A full credit releases exact remaining tax paise, including prior rounding. Compare with the actual tax note. A backdated note that would invalidate a later posted credit is rejected, as are duplicate note references and notes on notes/reversed invoices.
6. Review the month/year and branch summaries. Credit movements are negative, debit movements positive, in their actual posting period. The original invoice period stays unchanged. CSV/JSON register exports include document type and original invoice reference; tax ledger proofs must remain zero-unclassified for these documents.
7. Reverse a note using the existing dated reversal workflow and check the signed register/ledger proof. Reversing a reversal also remains consistent. Reverse all dependent notes before cancelling the original invoice, including offsetting credit/debit notes; pending or later-dated notes must not be orphaned. Existing year/period/bank locks continue to apply.
8. For an already-linked purchase, post a note and inspect its normalized 2B review. The invoice is flagged as adjusted and cannot be newly approved as an unchanged exact match. Notes are not presented as positive 2B invoices. Reversing all active notes clears the adjustment flag. This is a review warning, not automatic legal ITC adjustment or return filing.
9. Open **Change history → Trace voucher** for either the original invoice or note. GST context shows the linked family and preserved snapshots. Restart and confirm notes, vouchers, links and signed totals persist. Exporting or tracing must not change the books.

## Remaining scope

This workflow supports GST-bearing domestic credit/debit notes using the original invoice treatment, including zero-tax domestic treatments already supported. It does not decide GST time-limit eligibility, recipient confirmations, commercial-only credit-note treatment, return amendments, changed tax rates or a different ITC assessment. Those require separate review/manual journals. Source 2B credit/debit-note import and matching remain pending; the normalized importer still accepts positive B2B invoices only. Adjusted source invoices stay flagged for review rather than being silently cleared.

Reverse charge, export/SEZ, mixed-rate invoices, raw portal-format extraction, payments/utilisation and filing remain unfinished. B08 therefore stays PARTIAL. The application is not certifying a return or legal treatment.

Automated tests cover partial/full credits, debit capacity, odd-paise release, eligible/ineligible purchase adjustments, retained original rates, duplicate/date/approval guards, future/backdated capacity, reversal ordering/chains, offsetting active notes, 2B adjustment warnings, bidirectional history trace, signed exports, format-6 external-backup preservation and desktop preview/approval/reload. Windows encryption and the extended packaged self-test still require a future authorized Windows build.

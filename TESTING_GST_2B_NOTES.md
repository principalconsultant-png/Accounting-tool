# GSTR-2B note matching — unpublished 0.12.0-dev

This draft extends B08's normalized GSTR-2B review to credit/debit notes already posted in GST accounting. Prior invoices, GST notes, rules, history, bank/FX workflows and statistics are preserved. No executable, GitHub push or environment publication is included. The public Windows download remains 0.5.0; Windows/client acceptance remains pending.

## Safe upgrade

Format/schema 8 identifies typed 2B documents so an older invoice-only matcher cannot misinterpret notes as positive invoices. Formats 1–7 remain readable. The first upgraded save retains the existing original-format external backup and byte verification; saved-state checks run before migration. Preserve that backup. Existing invoice-only rows/links remain unchanged and are interpreted as Invoice when the new type field is absent.

## Import template

Download **GST accounting → 2B CSV template**. CSV or a single-sheet XLSX supports:

| Column | Meaning |
|---|---|
| supplier_gstin | Actual supplier GSTIN |
| invoice | Invoice or credit/debit-note reference |
| date | Document date, YYYY-MM-DD |
| taxable, cgst, sgst, igst | Positive absolute INR amounts for that aggregate document; unused tax components are zero |
| itc_available | Source Y or N, retained unchanged |
| document_type | Invoice, Credit note or Debit note; absent/blank means Invoice for legacy compatibility |
| original_invoice, original_date | Required for notes: independently verified original invoice reference/date; blank for invoices |

Document type controls the sign: credit notes subtract; debit notes and invoices add. Negative amount inputs are rejected to prevent applying the credit sign twice. The file contains one aggregate row per document, not one row per tax-rate line. Reference punctuation is normalized only when proposing candidates. Notes without independently verified parent details must stay unresolved; do not invent linkage merely to clear a match. Keep the original portal records and verify any normalization/augmentation.

This is a normalized import workflow, not a raw GST portal JSON/XLSX adapter. RCM/imports and special source sections still require further work.

## Test sequence

1. In disposable books, post a reviewed purchase and a linked credit/debit note using TESTING_GST_NOTES.md. Create a normalized source row with the same supplier, document type, reference, date, base/tax and original invoice link.
2. Import for the actual recipient GSTIN and statement period. Preview the document count and approve. No journal is created. Invalid/missing parent details, unknown types, negative/formula amounts, inconsistent tax splits and exact duplicate document records are rejected atomically.
3. Open **Review 2B import**. Confirm the Type, Invoice / note, Original invoice, source availability, book candidate and match status. Approve only an exact candidate. Invoice rows cannot match book notes, and credit/debit types cannot be interchanged. A wrong original reference/date cannot match even when note amounts agree.
4. Link every active note belonging to an adjusted original invoice. Its adjustment warning remains until all those notes are linked. After that, the original invoice can be matched normally. Undoing a note link reopens the warning; reversing a linked note flags that note row for review. No automatic journal, ITC claim, reversal or return amendment is made.
5. Try reusing the same book document in a second row/period. Reuse must be rejected. Reused reference numbers in different financial years must not make an unrelated old/reversed candidate invalidate the actual newer linked document.
6. Check signed source totals and the CSV/JSON review exports. Matched totals count only currently matched rows; availability-N amounts remain separately visible and signed. Availability N never changes to Y because a row matches, and book ITC treatment is not silently changed. Matched bookkeeping amounts are not a legal credit claim.
7. Review both statement documents missing from books and book invoices/notes absent from the imported statement. Missing-2B checks cover book documents dated in that statement period; late reporting and other periods need separate review. The invoice-only legacy report field remains available, while the new missing-document list also includes notes.
8. Undo links with a reason and test cancellation of an unused mistaken import. Active links must be undone before voiding; source/history remains. Corrected data can then be imported. Review exports include source filename/digest and import status.
9. Reload the app and confirm typed rows, links, original references and signed totals survive. Posted journal/work counts must remain unchanged by import/matching/export. Test upgrading a separate invoice-only format-7 book and confirm its rows/links and original external backup remain intact.

## Remaining work

B08 stays PARTIAL: RCM, export/SEZ, mixed-rate invoice entry, raw portal-format extraction, special amendments, legal time-limit/ITC assessment, GST payments/utilisation and filing remain pending. Statement-note linking does not certify a GST return or decide statutory treatment.

Automated tests cover typed CSV/XLSX notes, legacy invoice headers/live rows, wrong-parent/type/date/amount rejection, positive/debit and negative/credit totals, missing notes, all-note coverage, undo/reversal/reuse, unavailable ITC flags, safe read-only CSV, invoice-number reuse across years, format-7 backup migration and desktop import/match/export/reload. Windows encryption and the extended packaged readiness test require a future authorized Windows build.

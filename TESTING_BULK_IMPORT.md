# B11 mapped bulk import (0.22.0-dev)

Use disposable sources. Open Bulk import review, choose Journal, Expense,
Petty cash or Opening, and download its CSV template. CSV and XLSX are supported;
XLSX requires an exact sheet name. The heading map is JSON with canonical keys
`date,reference,branch,narration,debit_account,credit_account,amount` and optional
`journal_id`, each mapped to a distinct exact source heading. Blank map uses
standard headings. Source file digest, headings, map, raw literals and row numbers
are retained. Formula amounts/data are rejected rather than evaluated.

Stage a valid row and an invalid row. No journals are posted. Select the batch,
open its rows, and explicitly approve/reject each with a reason. Invalid and
changed-file duplicate rows cannot be approved; reject them and correct/reimport
the original data. Unique source branch/date/reference identities prevent changed
amount/narration copies from being queued or posted twice. Cancel unposted batches
with a reason. Rejected rows are retained in history but do not consume a new
corrected source identity. Exact same-file batches remain visibly recorded.

Expense rows debit genuine expense ledgers and credit cash/bank/payable; petty
cash credits cash. Journal rows may use valid balanced accounts. Amounts are
positive paise-precise INR. All branch/year/ledger/period/active controls apply.
Opening rows must use actual opening-date balance-sheet ledgers; all approved
rows for one unit/date become one opening voucher so openings are counted once.
Explicit `journal_id` groups become compound vouchers; partly rejected compound
groups are blocked. Source row counts, IDs and permanent voucher links survive
posting and feed work-volume/history without inflating counts.

Post reviewed batch opens a frozen journal preview; approval rechecks current
books. A locked/inactive/duplicate/invalid row makes the entire selected batch
fail without any partial journals. Test changed books after preview, earlier
years, multiple branches, rejected rows and reload. Export Excel/PDF review packs
and compare numeric values, source references, decisions/reasons and voucher IDs;
exporting changes nothing.

Daily-sales XLSX remains available in Import queue with all 15 source modes. Use
Review sales rows individually for explicit approvals/rejections. Once individual
review starts, every sales row must have a decision before the batch posts. The
legacy whole-file approval remains an explicit review of all rows when no
individual decisions have been made. Rejected sales rows are not posted or counted
as processed work. Ordinary journal CSV entry now routes to mapped row review.
Historical pre-B11 queue entries remain readable through their original route.

Run the full regression/desktop suite and Windows packaged self-test, including
`bulk_import_review_passed`. No new vault schema beyond B10 format 16 is needed;
older versions must not be used to process the new queue shapes. Client source
mapping and actual opening/account classifications require acceptance separately.

# Draft testing — FX receipts and work-volume statistics

Status: implemented in the current environment draft as `0.6.0-dev`. Nothing has been published or pushed to GitHub for this change. The existing downloadable 0.5.0 release does not contain these draft features.

## Protect existing books

This draft introduces book format/schema 3 so older executables cannot silently edit foreign-currency records without preserving foreign units. Formats 1 and 2 are read and migrated in memory; before the first upgraded save the existing external-drive backup safeguard must succeed. Keep the original-format backup. Tests use disposable data; no customer transactions are posted by the development process.

## Daily rates

Open **FX receipts → Daily FX rates**. Rates mean **INR per one unit of foreign currency**, not the inverse. Enter the exact customer-payment date, supported currency, rate (up to eight decimal places) and source/bank-advice reference. No live rate is fetched, and no previous-day/weekend rate is guessed. Rates can be imported atomically using:

```csv
date,currency,inr_per_unit,source
2026-06-01,USD,83.25,Test bank advice 1 June
2026-06-01,EUR,90.50,Test bank advice 1 June
```

Correcting a dated rate creates a revision. Existing posted journals retain the original foreign amount, dated rate, source and INR values. Currency precision follows the supported currency's minor units, including zero-decimal JPY and three-decimal KWD/BHD/OMR.

## Receive a payment

1. Open **Receive payment**. These entries always belong to Vaikom; its branch name is shown on the screen and approval dialog independently of the global report selector.
2. Select date/currency and enter the original foreign amount. Enter a unique payment/bank reference; payer information is optional.
3. Choose the credit ledger: completed-service revenue, patient/package advances, or shared Patient A/C to settle an already recorded bill. While Vaikom is under construction the screen defaults to advances. For an existing bill, supply the original INR carrying amount being settled by this payment (the corresponding portion for a partial settlement); the receipt must not recognize that revenue twice.
4. For **Convert immediately to INR**, select an INR cash/bank account. Blank actual gross INR uses the dated conversion; if the bank advice provides a different gross amount, enter it explicitly. Enter INR bank fees separately. The preview distinguishes net bank amount, fees and realised FX difference rather than assuming every difference is a fee.
5. For **Hold foreign currency**, first create an unused dedicated currency account on the third tab. Select the matching account/currency and leave INR conversion/fee fields blank/zero. The receipt retains foreign units as well as INR carrying value.
6. Prepare, review and approve the FX journal. Changes to the inputs or rate require a refreshed preview. Duplicate active FX references, missing same-day rates, invalid precision and locked dates are blocked.
7. Inspect the voucher and Ledger A/c. The narration/export includes foreign amount, dated rate/source and INR value. Foreign assets contribute their INR book value to the overview cash/bank total.

Example: USD 100 at INR 83.25 gives INR 8,325. If actual bank gross is INR 8,350 and fees are INR 20, the journal debits bank INR 8,330 and fees INR 20, credits revenue/advance INR 8,325 and FX gain INR 25.

## Later conversion of a holding

Open **Foreign accounts & conversion**. Create separate unused bank/cash ledgers for each currency; a generic INR bank ledger must not be reused as a foreign account. Holdings show original units and INR book value.

Enter conversion date, currency account, units converted, INR bank account, actual gross INR proceeds, INR fees and a unique reference. Conversion releases proportional weighted-average INR carrying cost; a full conversion clears all remaining carrying value, avoiding rounding residue. Fees and realised FX gain/loss are separate lines. Foreign-account movements are chronological to prevent later entries from silently changing a previously booked conversion cost. Reversals retain the original FX link and cannot produce invalid negative holdings.

This draft covers receipts and later conversion, not automatic period-end monetary-item revaluation, outbound foreign payments/refunds, foreign-denominated fee deductions, or a full foreign-invoice/tax subledger. Remaining foreign balances are shown at book value. GST is not inferred; automated GST/TDS and complete statutory statement work remain in their existing build items.

## Work-volume records

Open **Work volume**, or see the lifetime summary on Overview. Filter by branch/entity, all-time or selected dates. Choose **Work performed (India dates)** to measure processing activity using audited posting times, or **Book transaction dates** to measure the accounting period. These date bases differ when earlier-year transactions are entered today.

- **Business transactions posted:** one record per ordinary posted voucher, excluding initial openings, year-end closes, reversals and bank-settlement journals. Compound debit/credit lines do not inflate this count. A manually posted aggregate is one record, not a claimed number of patients.
- **Journal vouchers created / posted:** permanent creation and posting are atomic, so these counts match. All successfully posted journals are included, with system/reversal/settlement breakdowns shown separately.
- **Saved drafts created:** unique saved draft IDs; edits/retries do not create extra drafts. Unposted previews are not saved records and do not count. Pending saved drafts are shown separately.
- **Import rows processed:** distinct source records actually linked to successful postings. They are a breakdown of work already represented in journal totals, not additional transactions to add to that total. Import files and pending rows are shown separately. Exact duplicates rejected by the app add no completed work.
- **Bank records imported/matched:** distinct imported/matched bank rows, separately identified from journal work. Matching a bank row does not create another patient receipt.
- **Legacy coverage warnings:** ambiguous old queue rows are disclosed and excluded rather than assigned invented voucher links or work dates. Scope-wide warnings about unlinked/undated records are not completed-work counts.

Reversals remain completed journal work; original activity is not erased. A cross-branch journal counts once entity-wide but can appear in both branch scopes, so do not add branch totals together. Counts derive from the saved journals/audit/source records and survive reopening; exports do not reset or increment them.

Export a **statistics CSV** for sales-pitch preparation. Client/branch names are omitted by default unless the checkbox is selected; patient names, references, bank details and transaction amounts are not included. Each customer must have separate books/vault; the report does not combine different clients' records.

## Suggested checks

- Enter USD 100 at 83.25, then revise the rate to 84: the posted receipt must remain 8,325 with its original source. New previews use 84.
- Try the same reference again or an absent payment-date rate: no voucher should be created.
- Hold USD 100 at 83 and another USD 100 at 85. Convert USD 50: carrying cost must be INR 4,200, leaving USD 150 / INR 12,600 before subsequent movements.
- Save and edit the same draft twice, then post it: one saved-draft creation and one posted journal; two edits must not mean two transactions.
- Import a receipt row and approve it: one business record, one source row and one journal, not three transactions.
- Restart and confirm all counts and FX metadata remain unchanged. Exporting a statistics file or FX ledger must not create postings.

Windows encryption and packaged-executable checks must be run when a Windows build is subsequently authorized. No Windows release or cloud environment publication was performed for this draft.

# B10 — service revenue (development 0.21.0-dev)

Use disposable invented books. Configure reviewed effective-dated GST service
rules first, including sourced exempt/outside/nil treatments where appropriate.
Do not assume all hospital or resort/package supplies are exempt. Existing 15
collection modes, direct sales receipts and XLSX layouts remain available.

1. Open Service revenue; choose branch/year and explicit as-of date. Create a
   direct earned receipt, advance or unpaid bill. Enter unique reference, optional
   package reference, correct service revenue account, source/tax review basis,
   applicable rule and actual payment split JSON. Bills use shared Patient A/C;
   advances credit the advance liability, not revenue. Taxable originals require
   supplying GSTIN and actual place of supply. Inclusive/exclusive amounts are
   explicit. For mixed services/treatments, create separately referenced service
   components against the same optional package reference; retain the 15 ledgers.
2. For a source already posted, enter its original voucher ID/date and exact
   reviewed journal amounts. Link existing original only: no duplicate cost,
   receipt, revenue, journal or GST entry is created. Existing GST totals must
   agree. No patient ledger or ageing is introduced.
3. Select an advance and earn only the gross part of services actually completed.
   This transfers base from liability to its original service revenue account.
   GST already booked at a taxable advance receipt is not booked again. Untaxed
   advances contribute service base to the GST working register when earned.
   Taxed advances contribute to the tax-point working base at receipt, which is
   explicitly distinct from earned financial revenue. These are working
   summaries; B08 return/utilisation limitations still apply.
4. Refund unearned advances only against their remaining source capacity and
   actual payment evidence. Original base/tax components are proportionally
   released with cumulative paise rounding. Changed tax treatment between receipt
   and service recognition is blocked for review/correction rather than silently
   replacing historical rates. Return eligibility, tax-point changes and legal
   treatment must be checked by the accountant; original tax is never guessed.
5. Select a direct earned receipt and use Refund earned receipt for an actual
   reviewed service cancellation/refund; it reverses only the remaining original
   service/tax components against actual payment evidence. Select a bill and collect part/all through actual INR cash/bank/payment
   clearing splits. This credits shared Patient A/C without recording revenue
   twice. Cancel part/all against original revenue/tax. If already paid,
   cancellation creates a source-backed credit; Refund bill pays only that
   available credit. Outstanding debit/credit is shown per bill reference as a
   source-capacity working, not an ageing or patient subledger.
6. Try duplicate references, cross-branch sources, over-earning, over-refunds,
   collecting cancelled bills, future/backdated reuse and locked/inactive
   controls. All failures must leave books unchanged. Reverse dependent actions
   before their original source; exact dated reversals retain historical reports.
   GST notes for these sources must use Service revenue so service capacities
   remain linked. Correct unsupported tax/contract changes through reviewed
   source reversals/rebooking, never by editing posted facts.
7. Compare advance/Patient A/C source positions with ledger proof; unallocated
   manual/existing workflow movements remain visible until explicitly linked.
   Export Excel/PDF from the same as-of date/scope; confirm numeric amounts,
   source/voucher/rule basis, bill outstanding, unearned gross and reconciliation.
   Export is read-only. Save/reload and confirm source and GST links persist.
8. Run the full regression suite, desktop workflow and packaged Windows self-test.
   Format 16 preserves earlier books through the original external-backup guard.
   Client source/tax and target-PC acceptance remain separate from build tests.

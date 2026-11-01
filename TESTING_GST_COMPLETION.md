# B08 — extended GST bookkeeping and source review (0.24.0-dev)

Use invented disposable books. Rates, HSN/SAC, taxability, place of supply,
eligibility, legal dates and actual filing facts require accountant/client review;
this build does not certify or submit returns. B10/B11 remain intact. B24 new
encryption/recovery and B28 mailbox ingestion are deferred by user. Existing
Windows DPAPI/demo storage behaviour is unchanged. Schema 18 preserves earlier
books using the original external-backup safeguard and blocks older consumers
from misreading new source-line, cash and partial-RCM records.

## Mixed rates and export/SEZ

1. Configure reviewed effective-dated rules. In GST accounting choose Mixed-rate /
   export / SEZ invoice. Enter common invoice date/reference, kind, branch/GSTIN,
   counterparty, place of supply and actual settlement ledger; enter separate
   JSON source lines for each revenue/cost account, rule, amount, inclusive choice,
   ITC choice and description. Taxable/exempt/mixed eligibility stays per line.
   The complete invoice is one balanced voucher with one aggregate GST document;
   register summaries include every source line exactly once.
2. For export under LUT select a zero-rated rule, non-India destination code,
   reviewed LUT/export evidence and place-of-supply code 96. For export with IGST
   select the reviewed taxable rate and actual tax-paid evidence. SEZ supplies
   require recipient GSTIN, reviewed authorized-operation/LUT/payment evidence
   and actual Indian place of supply; IGST treatment is explicit. No export/SEZ
   eligibility is inferred from a customer name or a zero rate.
3. Source-line credit/debit notes allocate base amounts to original line IDs.
   Original rates/ITC/branch/registration stay frozen. Full credits release exact
   remaining tax paise. Per-line and aggregate capacities include dated future
   notes and reversals; one line cannot borrow another line's credit capacity.
   Ordinary single-rate invoice/note forms remain supported. If a purchase note
   reverses ITC already used, explicitly review its conversion into GST payable
   and actual repayment basis; it must not silently create available credit.
   Current tax time limits/commercial-only changes require explicit professional
   review/manual supported corrections, not an automatic legal assertion.

## Partial RCM and eligibility changes

4. RCM Purchase now allows an eligible tax percentage. Eligible tax is pending
   review; ineligible tax adds to cost. Deposit funds electronic cash only.
   Discharge/Claim accept actual component amounts; all blank retains a reviewed
   remaining/full action. Multiple partial actions cannot reuse dated cash,
   paid tax or eligible source amounts. Source registration/branch/components
   remain isolated, including backdated/future reservations.
5. Review eligibility changes prospectively through Eligibility. Reverse already
   claimed ITC before reducing the eligible portion. Reverse ITC moves that source
   back to pending; credit already used elsewhere requires dependent utilisation
   review first. Original-rate RCM credit/debit notes adjust cost/payable/tax and
   eligible portions. A credit after discharge can leave an explicit overpayment;
   Restore cash records actual portal credit back into electronic cash, then Cash
   refund records actual bank receipt. Cash transfer requires actual source/dest
   component evidence. No money or portal action is inferred.
6. Reverse dependent source actions first, including later eligibility revisions.
   RCM stage/control and outstanding/overpaid/pending-ITC reports retain actual
   dates and exact reversal history. Ordinary GST input summaries derive actual
   RCM input movements, including explicit reversals; they never treat cash
   deposits as credit claims.

## Forward cash, credit and preparation

7. GST cash & filing has separate bank funding, cash utilisation, ITC utilisation,
   transfers/refunds, source-linked ITC reclassification and opening registration.
   Review actual amounts, legal credit order, eligibility, date, branch and GSTIN.
   Deposit alone does not pay tax. CGST/SGST credit cannot cross-utilise; IGST
   priority/own-head order are checked. Effective-dated reviewed credit-order
   policies support earlier years; pre-29-March-2019 periods require a sourced
   historical policy. Current default proposals are retained with each actual
   reviewed allocation and can be superseded by a reviewed effective policy.
8. Existing initial GST balances can be allocated from their exact original
   opening voucher without another journal. Existing electronic-cash controls
   can be explicitly bound before use, with exclusive registration/component
   ownership. Manual/unallocated cash/tax movements remain proof differences;
   they cannot be silently converted into source capacity. New sources, action
   references, actual ledger balances and future/reversal dependencies are
   checked atomically. Existing RCM/forward deposit references cannot be reused.
9. Reviewed preparation creates a frozen source snapshot for an ended month,
   registration and unit. Optional actual portal acknowledgement is a manually
   recorded fact, not an online check or submission. Subsequent source changes
   flag it STALE. Shared tax-ledger proof is branch-wide; selected registration
   source documents/positions remain explicitly identified. Unclassified tax,
   RCM or electronic-cash differences block preparation. File directly on the
   government portal through the client's existing process; this application
   neither sends nor certifies a return.

## Raw portal source and outputs

10. Import supported GSTR-2B JSON `data.docdata.b2b[].inv[]` and `cdnr[].nt[]`
    through GST cash & filing. GSTIN/period, supplier/reference/date, item base/tax,
    ITC availability and RCM flags are validated. Independently provide original
    invoice/date links for notes; missing parents are never guessed. Forward
    sources feed existing normalized 2B matching; RCM sources have a separate exact
    source matcher/undo. Availability N stays N and matching posts/claims nothing.
    Actual portal schema/client-file acceptance is required. Nonempty unsupported
    sections (including import/other amendment variants), cess and ambiguous
    shapes fail closed for separately reviewed normalization; they are not
    silently omitted. Normalized CSV/XLSX remains the supported general adapter.
11. Excel/PDF packs include invoice source lines, tax-control proof, RCM stage
    journals/control proof/outstanding and ITC, actual cash/credit positions,
    action history, RCM portal reconciliation and reviewed filing history. Verify
    numeric amounts, signed notes/reversals, branch/GSTIN scope, source/rule/basis,
    current/stale snapshots and pagination. Export is read-only; save/reopen must
    preserve all sources and metadata. GST/RCM screens both expose these outputs.
12. Run all regression/desktop checks and the native Windows executable self-test.
    `gst_extended_bookkeeping_passed` must be true. Client legal/configuration,
    actual portal layouts, printer/Excel and target-PC acceptance remain separate.

Reference proposals checked during development (no legal applicability inferred):
[GST Council CBIC Circular 98/17/2019-GST](https://gstcouncil.gov.in/node/4817),
[NACIN ITC handbook](https://www.nacin.gov.in/Documents/e-Books/ITC-V1-26-03-2025-F3.pdf),
and [official GSTR-2B FAQs](https://tutorial.gst.gov.in/userguide/returns/FAQ_gstr2b.htm).

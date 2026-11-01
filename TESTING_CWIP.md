# B18 — Vaikom CWIP and commissioning (0.20.0-dev)

Use invented disposable books for this script. This build is on
`codex/accounting-development-20261030`; do not merge to main or publish a release.
Functional and native build verification do not substitute for client source,
capitalization, tax, useful-life or target-PC acceptance.

## Project setup and planning

1. Open **CWIP & commissioning**, select Vaikom or All operating units and the
   financial year, and enter the explicit **CWIP as at** date. Refresh CWIP.
2. Create a project with a unique key, name, unit and reviewed source basis.
   Blank ledger fields create separate Civil, MEP, Architecture, Landscaping and
   Compliance CWIP accounts plus a retention control. To adopt historical books,
   explicitly select existing appropriately grouped ledgers (e.g. 1020 and 2010).
   Category/retention ledgers cannot belong to two projects.
3. Select the project and revise budgets/milestones. Enter effective date,
   optional category budgets, review basis and milestone CSV
   `key,name,due,completed`. A blank budget is unknown; explicit zero is zero.
   Revise the plan and confirm earlier as-of reports retain earlier plans. The
   project display name may be revised with the plan. Actual completed dates are
   displayed only at/after their recorded date. No fixed budget, beds, branch
   operating status or opening date is inferred. Branch setup remains in B02.

## Cost review and existing records

4. Review a project cost: supplier/reference/date, category, gross **cost**,
   eligible capital portion and operating expense ledger for the balance.
   Gross cost includes nonrecoverable taxes; exclude eligible input GST. Use the
   existing GST/RCM workflows to review actual tax and link source cost debits
   rather than duplicating GST accounting. Document why direct capital costs are
   eligible and why hospital/start-up/operating costs are expensed.
5. **Post cost** debits eligible CWIP and the operating expense balance, credits
   gross supplier payable, then separately holds any explicitly entered retention
   by moving payable to the project's retention control. Preview all journals
   and approve. Draft previews do not change the books.
6. **Link existing** allocates actual source CWIP/expense debits on the exact
   original journal date; it does not repost the cost. Enter zero new retention
   when retention was already posted, then use **Link existing retention** to
   allocate the original retention credit. This also supports compound historical
   journals with net payable, retention and TDS. A full-paid original cost may be
   linked; a new hold/deduction still requires actual payable source capacity.
   Use a distinct reviewed correction reference if an invoice was entered wrong.
7. Check all source allocations are bounded; duplicate supplier/reference within
   project/year, over-allocation, invalid ledger/unit, inactive masters,
   unreviewed input and locked/closed posting periods must fail atomically.

## Retention and B09 TDS

8. Select a cost and deduct project TDS using a reviewed effective-dated B09 rule
   and resident payee. Review tax point, section/base, thresholds/rate, applicability
   and any manual exception. This uses **Existing payable**: no cost is reposted.
   It produces the normal B09 deduction, eligible for its existing challan/CIN,
   allocation, partial payment, undo and reversal workflows.
9. For historical tax not in B09 yet, **Register existing deduction** allocates the
   original TDS-credit source without a new journal. If B09 already recorded the
   deduction (including an original B09 Expense), use **Link B09 deduction** with
   its record ID; do not register it twice. Review exact cost/unit/gross source.
10. Release part/all of retention to its original payable or pay through an INR
    cash/bank ledger. Review amount/date/source basis. Future releases also
    consume capacity, so backdating cannot reuse retention. Retention plus new
    withholding cannot exceed the original payable source. Ledger differences
    must be resolved before releasing, expensing or commissioning.

## Commissioning, corrections and reconciliation

11. Expense any remaining ineligible CWIP with a reasoned source basis; only the
    uncommissioned balance is available. Select a project and commission reviewed
    cost allocations using `cost_id,amount` CSV. Partial amounts and multiple
    categories can become a single asset/component; repeat with unique asset
    references for other components. Unready amounts remain CWIP.
12. Review the certificate/ready-for-use transfer date, actual put-to-use date,
    PPE/accumulated/expense accounts, category, useful-life months, residual and
    technical overrides. A transfer credits exact source category CWIP and debits
    PPE; the B16 asset links this same voucher, so cost appears once. Actual
    put-to-use cannot precede the transfer. Land uses zero life and full residual.
    Subsequent B16 depreciation starts at put-to-use; B17 tax cost/first use is a
    separate reviewed step, not an automatic book-to-tax assumption.
13. In Assets & depreciation, post monthly depreciation and verify PPE and
    accumulated-depreciation reconciliation. Test partial first month and no
    depreciation before put-to-use. Retention/TDS remain liabilities after
    commissioning and are not capitalized a second time when paid.
14. Reverse dependent depreciation/asset events before commissioning; reverse
    dependent commissioning, expense reclassifications, retention and TDS before
    the original cost source. Undo B09 challan allocations before reversing its
    deduction. Exact dated reversal chains preserve prior as-of reports and
    cannot restore allocations that overuse a subsequently consumed cost.
15. Project ledger proof compares source positions to actual CWIP and retention.
    Legacy/manual/unallocated movements, including 1020/2010 outside projects,
    remain explicit differences until source-linked. Such differences block new
    commissioning/expense transfers; they are not silently absorbed. Vouchers
    and Change history expose project sources and event links.

## Excel/PDF, storage and native build

16. Export Excel, PDF and optional JSON for the current selector date/scope.
    Reports are cumulative positions **as at** the selected date, with the
    financial-year period labelled. Packs contain category costs/budgets,
    original reviewed capital, commissioned cost, reclassified and total
    operating expenses, remaining CWIP, source/supplier/voucher/basis, outstanding
    retention and linked TDS, milestones, reconciliation and event history.
    Compare file totals with the displayed snapshot and source journals. Blank
    budgets must stay blank in Excel/PDF. Excel amounts are numeric INR and
    formula-like source text is literal. PDF includes repeated headings,
    pagination, scope/date, entity and preparation/review blocks.
17. Exporting must not change vouchers, sources or history. Save/reopen and
    confirm projects, plan revisions, source allocations, events, B09 links and
    B16 asset registration persist. Format 15 upgrades formats 1–14 with the
    existing original-byte external backup guard. Keep that verified original;
    older executables cannot open newer formats. DPAPI recovery portability
    remains the separate B24 gate.
18. Run `python scripts/run_tests.py` with a display (`DISPLAY=:99` on Linux, or
    `RIJU_GUI_TEST=1` on Windows), compile sources and run `git diff --check`.
    The development push's **Windows build** workflow runs the full native suite,
    PyInstaller and packaged executable self-test, including CWIP/retention/TDS,
    commissioning/depreciation, Excel/PDF and encrypted persistence. Download
    `RijuBooks-Windows` from that successful Actions run. Its artifact includes
    `RijuBooks.exe`, SHA256SUMS.txt and packaged-selftest.json. Confirm
    `cwip_commissioning_passed: true`. Main-only publication must be skipped.

# Financial reports: Excel and PDF — unpublished 0.14.0-dev

The Financial reports screen now exports all seven current working reports to **Excel (.xlsx), PDF and CSV**: trial balance, profit and loss, balance sheet, comparative P&L, comparative balance sheet, branch matrix and general ledger. Existing Ledger A/c Excel/PDF/printing options are preserved. No new executable or environment publication is included; Windows/client acceptance remains pending.

## Agreed output requirement

All future financial-reporting deliverables must offer Excel and PDF outputs, including completed financial statements, cash flow, depreciation/tax schedules and executive/MIS packs when those reports are built. This release implements the current Financial reports screen. It does not claim to have built those remaining reports or retrofitted every GST/RCM working-review export. Applicable Schedule III/Ind AS presentation, disclosures, inter-branch eliminations and the complete executive pack remain unfinished.

## Test sequence

1. Open **Financial reports**, select a report and the From/Through dates. Choose the branch/entity in the main selector. Preview the figures and controls; drafts must not appear. The branch matrix explicitly shows all units and the entity total, even when a single branch was selected globally.
2. Select **Export Excel (.xlsx)** and choose a destination. Open the workbook in Excel. Verify entity/registration details, report, branch/entity scope, dates, INR, preparation time in India and comparative-period labels. Amount cells must be numeric with two-decimal formatting, so they can be summed/analysed. Narrative/account text is stored literally, including text beginning with an equals sign. Check frozen headers, filters and landscape print setup.
3. Select **Export PDF**. Compare the same rows and figures against the screen/workbook. Verify wrapped narrations, repeated table headings, entity/period/scope footer, page numbers and preparation/review blocks. Long general ledgers should paginate; matrices with many branches split into column panels rather than dropping branches. The PDF uses locally installed fonts and no external service.
4. Change report or dates without clicking Refresh, then export. Export must refresh the display first and use that exact snapshot. Cancelling the save dialog must not post or modify anything.
5. Check a trial balance whose initial opening is dated on the start day: opening belongs in the opening columns once; period movements and closing must agree. Check brought-forward balances in an empty period and inactive historical accounts.
6. Check P&L profit = revenue minus expenses. Revenue and expense amounts use their natural signs. P&L excludes system opening/year-closing journals. Check the balance sheet: assets must equal liabilities plus equity including the unclosed accumulated result. After a year-end close, earnings already carried to retained earnings must not be counted again.
7. Compare earlier-year reports, branch-only data, reversals and leap-day comparatives. Comparative labels show the actual shifted dates. The branch matrix uses debit-positive/credit-negative signed closing balances and checks the branch sum against the entity.
8. Export the same reports to CSV if required. Verify metadata, currency, controls and safe literal text. Reload the app and confirm exports did not change vouchers or audit history.

## Scope and validation

This is a read-only report/export change. Vault format remains 9; it introduces no additional migration or backup requirement beyond an already-pending upgrade. All previous GST/RCM/history/bank/FX/ledger work is preserved. The public Windows executable remains 0.5.0; these changes are in source draft 0.14.0-dev.

Automated tests compare Excel numeric cells to report paise, check PDF text/pagination and wide matrices, test formula-like text, branch/date filtering, openings, prior-year profit, year-end closing and leap comparatives, and exercise all seven report modes through the desktop Excel/PDF buttons. Compilation/whitespace checks and earlier-module regressions are included. Target-PC Excel viewing, printer layout, Windows encryption and the extended packaged self-test require a future authorized Windows build/client review.

## Combined customer handover pack

Use **Financial pack — Excel** or **Financial pack — PDF** on the Financial reports screen to export all seven current working reports for the selected dates/branch. Excel provides Contents with internal links plus one report per tab; PDF provides a contents page and separate sections. The branch matrix remains entity-wide and is labelled All operating units, including when the other sections are branch-only. Mixed-scope PDF footers direct the reader to section headings. All sections share one preparation timestamp. This pack does not yet include the unfinished cash-flow, depreciation, statutory disclosures or MIS reports.

Verify the workbook's eight sheets (Contents plus seven reports), the combined PDF's section headings and the same balance/profit controls as the individual exports. Packing reports is read-only. The single-report options remain available when only one output is needed.

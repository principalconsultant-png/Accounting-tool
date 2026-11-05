# Daily Business Register — consolidated database

Financial reports → Daily Business Register — consolidated database creates a persistent SQLite database from the book's posted transactions and saved report sources. It uses underlying records shared by all modules rather than parsing generated PDF/Excel reports, which would count the same entry multiple times. It creates no accounting journals. The report follows the requested seven-column layout, one row per calendar date for the selected entity/unit.

| Column | Definition |
| --- | --- |
| Date | Accounting date; all calendar days in the selected period are shown. |
| Revenue | Net earned revenue credits across Revenue ledgers, excluding opening/year-close families and output tax. Reversals reduce revenue on their posting dates. |
| Sales Units / patients | One active posted customer sales-receipt entry, even when paid using several methods. Includes identifiable patient receipts/advances/bill collections from receipt/service workflows and explicitly typed clinical receipts. Bank settlement lines are not more patients. It is a receipt-count proxy, not unique patients; no patient IDs or manual monthly count overrides are inferred. Cancelled receipts are excluded as of Through, so later cancellation can restate the original receipt-date count. A receipt spanning two units counts once at entity level; unit counts are not necessarily additive. |
| Collections | Net customer receipts/refunds into cash, banks and recorded UPI/card/other-payment clearing, including collected tax/advances. Funding, loans, own-bank transfers and later clearing-to-bank settlements are excluded. Revenue may therefore differ from Collections. |
| Opex | Booked operating expenses, including salary accruals, overtime, medical/administration costs, cost of sales, depreciation and petty-cash expense. Salary-payable settlement is not a second salary expense. Finance costs and income tax are reported outside Opex. |
| Capex | Booked additions to PPE/CWIP, less acquisition reversals. Includes credit purchases; not just cash paid. Internal CWIP-to-PPE capitalisation, capital reclassifications and asset disposals are excluded from new additions. |
| Cash Balance | Closing cash in hand plus bank ledger balances, including openings and all dated movements. Unbanked UPI/card balances are outside Cash Balance even though customer receipts are Collections. Foreign cash/bank uses recorded INR carrying amounts. Closing balances are not added together across dates. |

The columns deliberately mix earned revenue, booked cost, collections and a balance. Revenue − Opex − Capex is not a cash reconciliation. Zero activity means zero posted activity, not a certification that all reports have been received or posted. Patient counts and financial amounts are stored as separate integer/count fields; monetary source values use integer paise.

## What is left out

The What is left out view lists each supporting ledger line excluded from Revenue/Opex/Capex/Collections, with date, unit, voucher, account and reason. A line may still affect Cash Balance or another balance-sheet account. This is an explanatory ledger-line list, not an additive expense report.

- Finance costs and income tax are outside Opex; depreciation is included.
- Medicine stock purchases remain Inventory until expensed/consumed/sold. They are neither Opex nor PPE/CWIP Capex merely because cash was paid.
- Staff advances, owner drawings, loan principal, recoverable GST and tax/payable settlements are balance-sheet movements, not fresh operating costs.
- Petty-cash top-ups, stock purchases, advances and salary-liability settlements are not added as petty-cash expenses. The actual expense portion is included once. This differs intentionally from Business Pulse's separate “all petty-cash disbursements” metric.
- Internal cash/bank transfers and UPI/card settlements do not generate additional revenue, collections or patients. Cash/bank legs of operating payments are not a second Opex charge.
- Opening balances and year-close/reversal families are excluded from daily operating activity; real cash/bank balances still include their recorded cash effects.
- Asset disposal/cost removals and internal capitalisation are not new Capex.

Source gaps separately reports unmatched bank rows, uploaded sales/invoice-payment report rows still awaiting posting or blocked, and pending/rejected/cancelled import batches. An imported bank line or uploaded report does not become an expense or receipt just by being loaded. Amounts in this view are informational and must not be added to the daily totals. A blank source date is retained for review rather than silently omitted. Posted accruals are included even when unpaid. Externally held reports that have never been uploaded cannot be detected by the tool.

## Use the screen

1. Post/review the source records using Sales receipt, AP, payroll journals, Petty cash, bank entries and other appropriate modules. Match existing records rather than reposting them.
2. Open Financial reports → Daily Business Register — consolidated database. Choose From and Through, then Build / refresh database. A maximum ten-year range is supported.
3. Select ALL or an operating-unit code. Daily table displays the seven columns. Switch to What is left out, Source gaps or Source drilldown for supporting voucher/ledger references. Load saved table reloads the saved snapshot.
4. If transactions, source imports or relevant setup change, the saved database is marked STALE when loaded. Rebuild before relying on/exporting current figures. Refresh replaces derived tables; it does not append duplicate transactions or post journals.
5. Excel exports all four views for the selected unit/range. CSV and PDF export the current view. Export full SQLite database includes all units plus supporting earlier history through the saved Through date; the chosen display unit/date filters do not limit that full database export.

The compressed SQLite database is stored inside the existing Windows-protected .riju book, covered by its integrity checkpoint and included in its backups. No separate database password or new book-format migration is introduced. An explicitly exported .sqlite file is outside that encrypted vault and contains financial information, like exported Excel reports.

## Database tables and example query

Tables are daily_metrics, ledger_lines, contributions, receipt_sources, exclusions, source_coverage and metadata. ledger_lines contains voucher/date/unit/account and integer debit/credit paise; contributions links those lines to metrics. Receipt identities and cancellation-aware counts are retained separately. metadata records the period, definitions and a fingerprint of source facts. A repeated refresh rebuilds a new snapshot from those same facts.

Example SQL against an exported SQLite file:

```sql
SELECT date,
       revenue_paise / 100.0 AS revenue_inr,
       sales_units AS patients,
       collections_paise / 100.0 AS collections_inr,
       opex_paise / 100.0 AS opex_inr,
       capex_paise / 100.0 AS capex_inr,
       cash_balance_paise / 100.0 AS cash_balance_inr
FROM daily_metrics
WHERE unit = 'ALL'
ORDER BY date;
```

The supplied sample workbook/PDF/SQLite database uses synthetic training figures only. It is not a consolidation of your live books or uploaded Windows backups.

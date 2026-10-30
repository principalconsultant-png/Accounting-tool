# Ledger A/c — version 0.5.0 test guide

Close the previous executable and open Riju Books 0.5.0. Existing 0.4.0 books use the same storage format; this release does not rewrite posted transactions. Upgrades from 0.3.1 still need an external-drive backup before the first upgraded save.

1. Check the left menu: **Ledger A/c** must appear immediately below **Overview**.
2. Open Ledger A/c. Search for an account name/code, or filter Cash book, Bank books, assets, liabilities, equity, revenue or expenses. Patient A/C is a shared control account; no per-patient ledger is required.
3. Select the branch at the top of the app, or All operating units for the whole entity. Select a financial year, or enter the From/Through dates on the ledger screen and click Refresh dates.
4. Open a bank/revenue/expense account with invented postings. Check opening balance, dated movements, voucher/reference, debit/credit totals, running balance and closing balance. Use the table's horizontal scrollbar to see additional reference/branch/department fields.
5. Double-click a transaction, or select it and choose View selected entry voucher. The original posted journal should open. Drafts must never appear in ledger books.
6. Select one ledger, Ctrl/Shift-click several, or click Select all shown. The screen shows the first selected account; the selected-account count states how many will be exported/printed.
7. Choose **Print / preview selected**, select where to save the offline HTML preview, then click **Print / Save as PDF** in the opened browser. Choose your printer or Microsoft Print to PDF. Each ledger has its own print section and repeating column headings. Printing requires no internet.
8. Alternatively choose **Save PDF**, **Save Excel** or **Save CSV**. These use the current selection, branch and dates. PDF packs start each account on a new page with company identity, period, balances and preparation/review lines. Excel puts each ledger on a separate code-named sheet and repeats its heading when printed. Registration numbers appear only when entered.
9. Check that a period without transactions still shows brought-forward and closing balances. Initial opening vouchers on the first selected day belong to Opening balance, not period movement. Opening vouchers later in the range remain dated movements. Year-end closing entries are included so ledger closing agrees with the trial balance; P&L reports still exclude closing journals from operating performance.
10. Open Financial reports → Trial balance with the same period/scope. Its opening, debit/credit movement and closing columns must agree with the ledger books. Entity-wide and individual-branch totals must balance.

Use a disposable Windows-encrypted test vault for invented postings if you do not want to affect existing books:

```powershell
.\RijuBooks.exe --data "$env:LOCALAPPDATA\RijuBooks\Ledger-test.riju"
```

Exports are customer handover documents, not encrypted backups. Save them in the intended handover folder. Printing/exporting does not create or change accounting entries. Statutory statement certification and later BRD modules remain outside this release.

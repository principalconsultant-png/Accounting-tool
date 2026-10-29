# B01–B05 test guide — Riju Books 0.4.0

Use invented transactions first. The normal executable opens the existing books for the current Windows profile. To keep testing separate, launch from PowerShell with an explicitly separate Windows-encrypted vault:

```powershell
.\RijuBooks.exe --data "$env:LOCALAPPDATA\RijuBooks\B01-B05-test.riju"
```

This test vault is encrypted with Windows DPAPI, just like the main books. Do not use `--demo` for customer information. Choose a folder on your external drive in Settings & backup.

| Build | What to test | Expected result |
|---|---|---|
| B01 | Open a copy of a 0.3.1 vault using `--data`; try saving before choosing the external backup folder. Then select a connected external folder and save. | Original file unchanged until backup is available. A byte-verified original-format backup precedes the upgraded save. Reopening preserves prior vouchers. |
| B01 | Open a second executable against the same vault; close the first and retry. | Second instance is blocked while the first owns the books; reopening works after it closes. |
| B01 | Back up, add an invented entry, and restore the earlier backup. | A safety copy of the active books is made on the external drive before restore; restored balances agree with the backup. |
| B02 | Setup & periods → Entity details: save with GSTIN/TAN/PAN/CIN blank. Add properly formatted details later. | Both saves work; normal posting does not require registrations. Format errors are explained. No online registration validation is claimed. |
| B02 | In Branches select JP, rename it, save, and reopen historical entries. Add a test branch. Deactivate it after posting a test entry. | Historical entries retain branch IDs; renamed labels update throughout. New branch appears in journals/reports. Inactive history remains visible and new postings are blocked. Existing branch codes cannot be edited. |
| B03 | Chart of accounts: New ledger → Asset code 1011, name Test bank, group Cash and bank. Add Expense 4591. Rename, deactivate and reactivate it. | Valid ledgers appear in manual journal selection. Codes must match classifications. Control ledgers cannot be deactivated. Used ledgers cannot be deleted. |
| B03 | Inspect Patient A/C and record patient bill/collection as two manual entries if desired. | One shared patient control ledger; no patient-wise ledger required. Collection clears the control balance without recognizing revenue twice. Upfront receipts can still post directly to revenue. |
| B04 | Add FY 2023; enter initial opening bank debit and capital credit on 2023-04-01. Inspect later periods. | Prior-year setup works and initial balances carry forward once. A second opening for the same branch is rejected. |
| B04 | Download the opening CSV template, change to test amounts, upload and review before approval. | Preview shows all lines; approval posts balanced branch vouchers atomically. Invalid rows cause no partial postings. |
| B04 | In a disposable test vault, record ₹1,000 revenue and ₹200 expense in FY 2023, then review and close that year. | Net ₹800 profit transfers into retained earnings. Closing income/expense balances are zero; FY 2023 P&L still shows the year's activity. Backdated posting is blocked. A second close is rejected. |
| B04 | Select Comparative P&L or Comparative balance sheet in Financial reports. | Current selected period and corresponding prior-year values appear side-by-side. These remain working reports, not final statutory statements. |
| B05 | Journal studio: choose type/reference/party; add and edit manual lines; save an unbalanced draft. Restart the app, open Saved drafts, fix it and review/post. | Draft persists without affecting balances. Unbalanced posting is blocked. A corrected saved draft posts once and disappears from Saved drafts. References are retained. |
| B05 | Enter a cash-to-bank transfer; patient advance to liability 2300; refund against that liability; cross-branch transfer with clearing 1130 on each side. | All journals must balance overall and per branch. Advances stay liabilities. No tax is guessed. Each branch's clearing entry balances its cash/bank entry. |
| B05 | Reverse a posted voucher, then attempt another reversal or an earlier reversal date. | Original entry remains unchanged; dated reversal swaps the exact lines. Duplicate and pre-original-date reversals are blocked. |

Year-end closing and period locks are intentionally irreversible in this build. Customer-ready individual ledger books/PDF/Excel packs are B19, not included in this release. The original 15-category sales import and pastel theme remain available. Full offline AI is B22; the current phrase assistant remains limited.

Record test results by B-ID, expected/actual outcome, app version and whether a separate test vault was used. Share error text and the steps to reproduce any failure; no real patient names are needed.

Riju Books 0.4.0 — Bookkeeping foundation B01–B05

- Optional registration details: enter GSTIN, TAN, PAN, CIN, address and state information now or later. Blank registration numbers never block normal bookkeeping.
- Setup & periods: edit the entity and branch details, rename branches without changing historical IDs, add/deactivate branches, set capacity/status and configure earlier financial years.
- Ledger masters: create/edit report and cash-flow groups, add individual bank accounts, use shared Patient A/C, deactivate unused ledgers and protect posted history/control accounts.
- Initial opening balances: manual or reviewed atomic CSV upload. Later years carry forward without duplicate openings. Revenue/expense accounts are excluded from initial balances.
- Prior-year comparative P&L/balance-sheet working reports; reviewed year-end close transfers results into retained earnings and locks the period. Closing and locks cannot be undone in this build.
- Journal studio: voucher types, optional party/reference/cash-bank metadata, edit individual lines, save/reopen unbalanced drafts and review before posting. Advances, refunds and inter-branch entries can be entered with manual compound lines. The offline phrase assistant has not been expanded into the full AI module.
- Single-instance protection, atomic writes with concurrent-change detection, original-file backup before upgrades, and safer restore handling.
- Scrollable workspace so actions remain accessible on smaller Windows screens.

TESTING AND UPGRADE
1. Close the previous application and run this executable. The title must show 0.4.0.
2. If existing books require an upgrade, choose your external-drive folder in Settings & backup. The original vault is backed up byte-for-byte before the first upgraded save. If the drive is unavailable, the original books remain unchanged.
3. Upgraded books use format version 2 and cannot be opened in version 0.3.1. Keep the original-format external backup. Windows DPAPI backups still require the original Windows account/keys; portable cross-computer recovery remains B24.
4. Follow TESTING_B01_B05.md. Test year-end closing only in disposable test books; it locks posting through year-end.

This unsigned application remains a development/test release. Customer-ready ledger PDF/Excel delivery is B19 and remains pending. Full tax automation, full BRS, statutory statements and offline language-model AI are later builds. No live customer report has been imported by this release process.

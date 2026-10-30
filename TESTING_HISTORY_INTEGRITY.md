# B06 history and integrity — unpublished 0.8.0-dev

This draft continues the published environment's bank-reconciliation/FX work. The public Windows executable remains 0.5.0. No new executable, GitHub push or environment publication is included. Windows packaging and client acceptance remain pending. Use disposable books for testing.

## What changed

**Change history** now shows the recorded user, India and UTC timestamps, action, description and full details. Search IDs, ledger codes, branches or text; filter by work date and action. These filters are independent of the global accounting year/branch selectors. Select an event to see readable before/after fields and the original JSON details. Export the filtered results to CSV or JSON; export does not change the books. Saved-state checkpoints are hidden by default but can be included.

New events identify the local OS user. Older events without a recorded user remain labelled legacy; missing historical before/after values are not invented. New successful desktop mutations record exact changes to mutable data, in addition to the existing business events. Posted journals already have their full immutable POST record. An unchanged save does not add another checkpoint. A failed save must not add a successful checkpoint to memory or disk.

Every successful save now hashes all book sections other than the separately hash-chained history. Load verifies that saved-state checkpoint before migration. This detects mismatches in masters, drafts, bank data, settings and other stored sections as well as posted journals. The current format remains 4; older books without checkpoints remain readable and establish their baseline at the next save. This is local consistency checking, not statutory certification or protection against an attacker rewriting both books and history. Existing backups and Windows-account protection remain necessary.

## Test sequence

1. Create an invented entity/ledger change and save. Open **Change history**, select CHANGE_SET and find the old/new values. Check that the OS user is recorded. Edit a saved draft and confirm its prior values remain unchanged in history.
2. Filter using today's work date in India and search the ledger code/entity text. Export CSV and JSON and compare the selected events, user, timestamps and recorded payload. Include checkpoints to export their hashes as well. Financial-year selection must not hide this month's work on an earlier accounting year.
3. Save and post a draft, select its POST or DRAFT_POSTED event and choose **Trace voucher**. Confirm the draft ID points to the posted voucher. Reverse the voucher using the normal workflow and trace both original and reversal. Posted history is preserved.
4. Trace an imported journal or daily-sales voucher. Confirm the explicit document/row link and filename where available. Trace a matched bank voucher and confirm the match/bank rows. Older vouchers without explicit links must remain disclosed as unlinked.
5. Choose **Check integrity**. Inspect journal/branch balance checks, ledger/branch references, duplicate voucher/source checks, exact reversals, bank allocation references/limits, audit hashes/sequences and the current saved-state checkpoint. Save the review JSON if needed.
6. Choose **Inspect backup file** and select an external backup. Confirm entity, recorded coverage and integrity result. Inspection must leave the active books unchanged. Use **Settings & backup → Restore backup** only when intending to replace active books; the existing external safety-copy requirement remains.
7. In an isolated demo vault only, save then alter a ledger name or bank row directly in the JSON file. Reopening must reject the mismatch. The startup recovery prompt must offer a trusted backup, validate it, request an external safety-copy folder and confirm replacement. Verify the original altered file survives byte-for-byte in that folder; the restored books must load with a new checkpoint and a recovery event referencing the source hash and safety copy. Cancelling must leave the active file unchanged. Never perform this experiment on real books.
8. Reload the application and verify saved history/source traces persist. No reset command is exposed in live books; desktop development tests use separate temporary demo vaults.

Recovery still depends on the original Windows DPAPI keys; portable recovery on a replacement PC remains B24. Restoring an older backup returns to that backup's history and records the restore; the external safety copy preserves the replaced file's later history. Source/draft links created before explicit linkage was implemented are not reconstructed by guessing. This module does not certify historical data as correct merely because local consistency checks pass.

## Automated checks

Tests cover immutable audit payloads, user attribution, sequence checks, before/after capture, India work dates, legacy coverage, persisted checkpoint roundtrips, master/bank tampering, atomic failed saves, draft/source/bank/reversal traces, allocation failures, CSV safety, read-only inspection/export, cancelled recovery and verified recovery with preservation of the altered original. Desktop tests cover navigation, detail display, filters, export, integrity review and persistence. Windows-only encryption and the updated packaged self-test must be run in a future authorized Windows build.

# B24 — external backups and portable encrypted recovery (0.23.0-dev)

Use invented disposable books first. This source/build does not authorize a main
merge, public release or replacement of actual client books before acceptance.
No application password is introduced.

## Encryption and upgrade

Native saves use authenticated AES-256-GCM with random nonces and a per-book
256-bit key. Windows DPAPI wraps that key for automatic normal opening. The book
key is never placed in book data, audit history, reports or ordinary backup
metadata. Demo JSON remains explicitly unencrypted and cannot export native
recovery material. Native envelope and schema 17 protect new queue/recovery shapes
from older executables. Formats 1–16 and legacy DPAPI remain readable in the
original Windows account. Before the first upgraded save, the original encrypted
file is copied byte-for-byte to the chosen external folder and verified. An
unavailable/unverified backup destination blocks upgrade without replacing the
original. Keep old backups: old DPAPI files still require their original Windows
account; only new AES-GCM backups support the new separate recovery material.

## External devices and enrollment

1. In Settings & backup choose a connected external USB/removable backup drive.
   Production checks reject the live-books volume, ordinary internal SATA/SAS
   disks and network paths. Removable media or separately identified USB/SD/MMC/
   1394 disk buses are accepted; unidentifiable hardware fails closed. External
   enclosures reported differently (for example some Thunderbolt/NVMe devices)
   require client hardware verification rather than an assumed bypass.
2. Save the upgraded books. Choose Export recovery key and save the key JSON on
   a **different separately held external device**, not the books/backup device.
   Export is exclusive: it never overwrites an existing older key file. The file
   is verified against actual saved authenticated books before enrollment is
   recorded. The key file grants full access to matching books: retain it offline,
   do not email it and do not include it in accounting export/backup folders.
3. Keep a separately stored copy of the same key material if desired. Key export
   does not rotate the per-book key, so it opens matching historical AES backups.
   Another book's recovery file must fail. The application stores only the key ID
   and verification event, never the recovery key itself or its file contents.

## Backups, retry and retention

4. Back up now creates a temporary destination, copies and byte-verifies before
   atomically naming the finished backup. Failed/partial copies do not count as
   successful daily backups. Native backup destinations are checked each time.
5. The startup/hourly check creates a routine backup if none exists for this book
   today. Existing daily backups are authenticated and integrity-checked rather
   than trusting filename presence alone. A disconnected/unverifiable drive shows
   BACKUP PENDING and is retried by the next check; reconnect and use Back up now
   to retry immediately. Backups are per book, not shared completed-work counts.
6. Set routine retention (1–3650; default 30). Only this book's tagged routine
   backups are pruned, only after a new verified copy succeeds. Other customers'
   books, pre-upgrade originals, restore safety copies and recovery key files are
   not pruned by routine retention. Source backups are never overwritten in place.

## Portable verification and restore drill

7. Choose Verify portable backup + key. Select an actual AES-GCM external backup
   and its separately held key. Authentication, saved-state fingerprint/hash chain
   and voucher/reference consistency must pass. No old Windows key is used for
   this verification. The source backup is unchanged; a verification event records
   only its digest, book key ID and voucher count.
8. On a replacement Windows installation, open empty books and choose Restore
   using recovery key, or use startup recovery when automatic unlocking fails.
   Select the trusted backup and matching recovery file. Inspect the entity and
   review the in-product confirmation before replacement. Select a current
   external destination for any existing active-file safety copy; an old drive
   letter from the recovered machine is not reused as the current backup setting.
9. Any active file is first byte-preserved in an external safety copy. Recovery
   decrypts/authenticates using the separate material, verifies books, rewraps the
   same book key for the replacement Windows account, and atomically saves. Normal
   reopening is automatic again. Source backup/key remain unchanged. Failed
   authentication, wrong key, tampering, stale concurrent writes, offline safety
   drive or failed destination save must preserve the active file and abort.
10. Reopen and compare actual entity/branch/year balances, voucher counts, drafts,
    import/reconciliation/asset/tax/revenue sources and change history. Ordinary
    same-account restore also preserves the source book's encryption-key identity.
    Original history stays intact and a recovery event is appended. A future
    separately held key export must still match the recovered book.

## Verification evidence and acceptance boundary

Automated tests exercise AES nonce/key/header authentication, wrong keys,
corrupted ciphertext, legacy-original backup, separate-key enforcement, failed
writes, retention/customer isolation, disconnected-drive retry and recovery under
simulated different Windows identities. Hardware policy has mocked bus cases;
portable desktop testing covers export/verify/restore/reload with disposable
identity stubs. Native Windows packaged self-test uses real AES/DPAPI, separate
transient test directories, full recovery/export/reload assertions and no client
books. Its temporary-folder exception is confined to the OS temporary directory
and is not exposed in the normal application UI. Confirm
`portable_encrypted_recovery_passed: true` in the downloaded executable self-test.

A real second-PC/Windows-account and the client's physical external-drive drill
remain client acceptance checks, not evidence inferred from a single CI machine.
Do not discard the original vault, verified backup or recovery material.

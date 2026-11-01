# ऋजु · Riju Books

**Development 0.29.0-dev — requested sequence B08/B10/B11 → B13/B20/B22/B23:** extended GST, service revenue and bulk review are retained. New pages deliver versioned offline Bengaluru banking calendar, reviewed statement presentation/disclosure/tax working, small offline statistical language interpretation and source-traced checks/questions. Excel/PDF packs and reviewed posting guards are included. Testing guides: [calendar](TESTING_BANK_CALENDAR.md), [statements](TESTING_STATEMENT_PRESENTATION.md), [offline language](TESTING_OFFLINE_LANGUAGE.md), [checks/questions](TESTING_ACCOUNTING_CHECKS.md), [GST](TESTING_GST_COMPLETION.md), [service revenue](TESTING_SERVICE_REVENUE.md), [bulk review](TESTING_BULK_IMPORT.md). See the [model card](MODEL_CARD_OFFLINE.md) for the authored classifier's scope and licence; it is not a generative LLM. Schema 20 protects installed calendar semantics and preserves original pre-upgrade backup safeguards. New encryption/recovery (B24) and mailbox ingestion (B28) remain deferred by user; existing Windows DPAPI/demo storage is retained. Changes stay on `codex/accounting-development-20261030`; no main merge or release publication. Actual source/legal applicability, customer language and target-PC acceptance remain review gates.

**New AP and sales import:** AP Vendor Invoices appears in the left navigation, with accruals, actual partial/batch payments, extensions/reminders, source proof and a separate cash-outflow forecast. Sales receipt has direct standard XLSX/CSV imports and templates. Start with the [detailed training/user guide](docs/USER_TRAINING_GUIDE.md) and [AP/receipt acceptance steps](TESTING_AP_RECEIPTS.md). The Windows build includes the printable PDF and both blank templates; new encryption and B28 remain deferred.

**Version 0.5.0:** **Ledger A/c** directly below Overview; individual and full ledger books with opening/running/closing balances; branch/date filters and voucher drilldown; offline printing plus PDF/Excel/CSV handover packs. Trial balance includes opening, movement and closing columns. See [ledger testing instructions](TESTING_LEDGERS.md) and [the build tracker](BUILD_TRACKER.md). B01–B05 foundations remain available.

Existing books are migrated in memory first. Before the first upgraded save, select your external-drive backup folder: the original-format vault is backed up and byte-verified. The published 0.5.0 build uses format version 2; the current development uses format 20. Keep the original backup because older executables cannot open newer-format books. Cross-computer DPAPI recovery remains pending.

An offline-first, single-user Windows bookkeeping application for one entity with three operating units: JP Nagar, Kammanahalli and Vaikom medical resort. Ivory, sage and pastel saffron interface. No cloud database, telemetry, external fonts, online AI calls or GPU dependency.

**Status: first development build, not production-ready accounting software.** This repository was empty. This implementation establishes an executable application and tested accounting core; it does not yet complete every requirement from the BRD.

## Run on Windows 11

Install Python 3.12 or newer (including Tcl/Tk), then from this folder:

```powershell
py -3 -m pip install -r requirements.txt
py -3 run_riju.py
```

Running from source requires openpyxl for XLSX imports/exports and ReportLab for PDF exports; packaged Windows builds include both. Data defaults to `%LOCALAPPDATA%\RijuBooks\books.riju`. The application has no password and protects the vault using Windows DPAPI under the current Windows account. It does not implement the original BRD's portable AES-GCM vault. Do not use real client data before Windows encryption, restoration and accounting acceptance testing.

Build an unsigned, standalone Windows executable on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\build-windows.ps1
```

Output: `dist\RijuBooks.exe`; end users do not need Python. The build script installs pinned PyInstaller into a project virtual environment. `.github/workflows/windows.yml` also builds and uploads an executable on Windows when run in GitHub Actions. The workflow runs Windows DPAPI tests, desktop tests, and a packaged-executable self-test (XLSX import, posting, encrypted save/load, backup restore). Development branches upload test artifacts without publishing a release; only main permits the publication step. Native Windows results and source commits are recorded in BUILD_TRACKER.md. Code signing and an installer are not included.

## Offline accounting workflow

1. Review the starter chart of accounts and legal entity name. All registration details remain unverified; this is one entity with branch reports, not separate-company consolidation.
2. Enter opening balances on 1 April with the **Opening balances** checkbox, using balanced asset/liability/equity lines. Earlier financial years are supported.
3. In Journal studio select the actual date and unit, then describe a supported payment or receipt, such as `Paid ₹5,000 rent by bank` or `Received ₹12,000 OPD consultation sales by UPI`.
4. Prepare a draft, review ledger selection, and approve posting. The local rules assistant supports a limited, visible set of templates; it is not a general-purpose language model. All 15 source report categories have receipt templates. It refuses ambiguous categories, missing payment methods, tax/deduction descriptions and unsupported treatments. Enter those through manual journal lines. No model download is required.
5. Every branch must balance independently. Use inter-branch clearing for cross-unit transactions. Posted vouchers are corrected through dated reversals; period locks block backdated posting.
6. Ledger A/c provides individual/all-account books with running balances, branch/date filters, voucher drilldown, local print preview and PDF/Excel/CSV exports. Financial reports provide a movement trial balance, working P&L and balance sheet, branch matrix and general ledger. Values use integer paise and avoid floating point for posting. Reports are accounting working statements, not certified Schedule III statements.
7. For mixed-service or split-payment receipts, use **Sales receipt**, enter the service and payment amounts, and prepare a compound draft. Alternatively choose **Import queue → Upload daily sales XLSX**, select the branch, review source rows and journal lines, and approve the whole report. There is no auto-posting on upload. The importer accepts the supplied H:V service headings, recomputes totals, validates payment splits and rejects duplicate receipts, inconsistent totals and formulas in source amount cells. Unknown nonempty sheets are rejected explicitly.
8. Import journal CSVs into the review queue, review rows and approve the whole file. Posting is atomic. Exact-file duplicate imports are blocked. A renamed or modified duplicate file still needs manual review.
9. In Bank reconciliation import an INR bank statement, review and match receipts/payments against books, or approve gross-to-net UPI/card/cash settlements and missing-entry adjustments. Verify bank balances and outstanding items, export the dated BRS, then complete the statement to protect its bank period. Every posting and match requires review.

### Import formats

Journal CSV, UTF-8, dates `YYYY-MM-DD`, amounts in rupees without currency symbols or unquoted separators:

```csv
date,narration,branch,debit_account,credit_account,amount
2026-04-02,Rent,JP,4530,1010,5000
```

Branch codes: `JP`, `KM`, `VK`. Each journal CSV row represents a simple two-line voucher; use manual entry for compound tax entries. CSVs imported on 1 April are ordinary transactions, not opening balances: use Journal studio for openings.

Bank deposit CSV:

```csv
date,narration,amount,reference
2026-04-02,UPI SETTLEMENT -AII125,11880,UTR123
```

Bank imports currently support **positive incoming deposits only**, one bank ledger, and UPI/card clearing settlement suggestions. Default tolerance is one business day after NBD. Sundays and second/fourth Saturdays are excluded; enter the applicable Bengaluru bank holidays by year in Settings. A holiday calendar is not automatically downloaded. Suggested grouping searches up to 31 consecutive eligible vouchers and does not claim exhaustive subset matching.

## Backups and security

Choose a folder on an external drive, then Back up now. The app also checks once after startup and hourly while running, creating a backup if no backup exists for that day. Disconnected drives produce a pending-backup status. Backups are byte-verified copies; restoration first saves a safety backup. Reports exported to CSV are unencrypted.

**Current DPAPI backups require the original Windows account and its cryptographic keys. They are not a portable disaster-recovery solution.** A separately held recovery key and portable encrypted backup format are required before live rollout. There is no application password. Anyone with access to the unlocked Windows account can access the application. Local SHA-256 history is useful traceability, not statutory audit-trail certification or protection against an administrator rewriting all records.

## Validation

```sh
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python -m compileall -q riju run_riju.py
```

Linux development can use `python run_riju.py --demo --data /tmp/riju-demo.json` with a graphical display. Demo storage is explicitly unencrypted; use only disposable, invented data. Real Windows storage refuses to run on other platforms.

## Remaining before production

- Confirm the GitHub Windows build and packaged self-test, then validate DPAPI and backup/restore on the target laptop; portable recovery and single-instance locking.
- Accountant-approved examples covering hospital/resort revenue recognition, taxes, opening balances, account mapping, and year-end behavior. Local language-model interpretation is not implemented; the offline assistant is rule-based.
- Full Schedule III statements/disclosures, direct/indirect cash flow, final statutory comparative statements/disclosures and the complete executive MIS/PDF pack. Movement trial balance, working comparatives and ledger printing/PDF exports are implemented.
- GST/TDS calculations with applicability, thresholds, editable effective-dated rates, registration configuration and tax summaries. Present tax settings are reference values only, not an automated tax engine.
- Full Companies Act schedules and income-tax block depreciation with asset additions/disposals and 180-day rules. Current asset screen only registers assets and illustrates SLM/WDV amounts; it does not post depreciation.
- General bank reconciliation including withdrawals, cash deposits, multiple bank accounts, adjustments, OFX/Excel and authoritative holiday calendars.
- Gmail OAuth and attachment downloading into the queue; no Gmail access or sending occurs. OAuth consent and credentials will be needed for that later integration.
- Departmental budgets, package advance recognition automation, full asset/CWIP schedules, inventory cost controls, broader import duplicate detection. Customer-ready ledger delivery is now available from Ledger A/c. Entity/branch metadata and capacity fields are now editable.

No cloud environment publication, remote push or client data import is performed by these instructions. Use the existing checkout in the isolated cloud task; do not create a worktree unless requested.

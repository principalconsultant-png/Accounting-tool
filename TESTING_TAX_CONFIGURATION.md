# B07 tax configuration — unpublished 0.9.0-dev

This draft adds **Tax setup** to the desktop navigation and preserves the prior history, bank, FX and ledger work. No executable or environment publication is included. The public Windows download remains 0.5.0. Use disposable books first; Windows and client acceptance remain pending.

## Upgrade

Tax configuration introduces vault format/schema 5. Formats 1–4 load in memory and retain the existing requirement to select an external backup folder before the first upgraded save. That save copies and byte-verifies the original-format vault before replacing it. Saved-state integrity checks run before migration. Older executables cannot open format 5; keep the original backup.

## What this module does

- Store GST/TDS rules with a stable key, effective date, rate, treatment, applicability conditions, source/reference, review status and optional ledger links.
- Keep every saved version. A later effective date creates a new version; a correction for the same date creates a new revision. Preview selects the latest revision of the latest effective date on or before the transaction date. It never falls back to an older reviewed rate when the selected newer version needs review.
- Distinguish GST taxable, exempt, nil-rated, zero-rated and outside-GST treatments. HSN/SAC can be entered now or left blank for later review. Rates are total percentages; GST splits/posting are B08.
- Configure TDS sections, party categories, single/annual INR thresholds and threshold basis. Blank means unknown, while zero is an explicit value. Rates permit up to four decimals; thresholds up to two.
- Store versioned payee/supplier names, categories and optional PAN/TAN/GSTIN/state/address details. No individual patient accounts or ageing are created. Format/state/PAN consistency is checked; registration validity is not checked with government services.
- Preview dated rule/party snapshots and missing-data/category warnings. Export all configuration versions and original legacy references to JSON. New changes are recorded in Change history.

These are configuration masters, not an automatic tax engine. Existing legacy TDS/GST reference values are displayed separately and are not silently turned into legally verified rules. No hospital-wide exemption, ITC entitlement, residency, place-of-supply treatment, PAN exception or transaction-specific deduction is guessed. A reviewed checkbox records the bookkeeper's review, not independent legal verification.

## Desktop test sequence

1. Open **Tax setup → New tax rule**. Create an invented GST rule with key `TEST-SERVICE`, an earlier effective date, a rate, label, specific applicability conditions and HSN/SAC. Leave reviewed unchecked initially. Save, then preview it on dates before and after its start. Before the start there must be no applicable rule.
2. Select the rule and choose **New version of selected rule**. Enter a later effective date and different test rate. Enter your source/reference and mark reviewed only after checking it. Preview the earlier date again: the old rate must remain. For a same-date correction, save another revision and verify both recorded revisions remain visible/exportable. Adding a backdated version may change historical previews; it does not rewrite any posted journal.
3. Create separate zero-rate test rules for exempt, nil-rated, zero-rated and outside-GST cases. Confirm the categories remain distinct. A taxable rule with zero rate or an exempt rule with a positive rate must be rejected.
4. Create a TDS rule: choose TDS family, Withholding treatment, section, party category, rate and threshold basis. Leave HSN/SAC blank. Configure only thresholds you have verified; leave others blank. The preview must distinguish missing thresholds from zero and disclose that cumulative threshold tests have not been performed. Use separate rule keys for distinct conditions/rates under the same section.
5. Choose **New party**. Save an invented supplier with unknown category and blank registration numbers. Later add a dated registration version or same-date correction. Confirm historical versions remain. Invalid GSTIN/PAN/TAN formats and conflicting GSTIN/state or GSTIN/PAN details must be rejected. You can leave details blank until available.
6. Preview a TDS rule against the party and transaction date. Confirm category mismatches, inactive parties and missing PAN are flagged. For GST, missing entity/party registrations or HSN/SAC remain visible. There is no claim that the rule applies solely because its date matches.
7. Export configuration JSON and inspect version IDs, revisions, dates, review/source information and optional details. Check Change history for added rule/party versions and desktop before/after details. Ledger codes referenced by historical rules cannot be deleted; deactivate unused ledgers instead.
8. Restart and confirm the versions persist. No tax journal or additional posted-transaction count should result from configuring or previewing rules.

## Boundaries

GST calculations, intra/inter-state splits, invoice rounding, ITC handling, GST summaries and GSTR-2B matching remain B08. TDS cumulative thresholds, deduction journals, challan reconciliation and section summaries remain B09. Actual rules must be verified for the relevant financial year and client circumstances; the illustrative test values above are not legal rates or thresholds. The preview is read-only and does not calculate liability or return filing data.

Automated checks cover effective dates and corrections, historical preservation, review flags, invalid rates/classifications, optional/versioned party details, threshold unknown/zero handling, ledger references, read-only exports, desktop entry/version/preview/reload and format-4 upgrade with original external backup preservation. Windows encryption and packaged executable checks require a future authorized Windows build.

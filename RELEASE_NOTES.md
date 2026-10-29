Riju Books 0.3.0 — Hospital daily sales

- All 15 hospital collection categories have distinct revenue mappings: Treatment, Consultation, Eye Check Up, Registration, Medicine Retail, Medicine Treatment, Consumables, Room Rent, Nursing Charges, Duty Doctor Charges, Food Charges, Swarnaprashna, Kalari, Treatment Payments Received, and Miscellaneous Charges.
- Treatment Payments Received represents earned treatment revenue, as confirmed. Other source posts to Other receipts clearing.
- Import the hospital's daily-sales XLSX directly into the local review queue. Review compound journal lines before approving the whole report.
- Independently checks every service and payment amount, including the Treatment column omitted by the source template's subtotal formula. Inconsistent source totals are blocked.
- Cash, UPI, card and Other source splits are supported without inventing allocations between services and payment methods.
- New Sales receipt screen for compound entries; English descriptions recognize all 15 categories. Descriptions with multiple services and one undivided amount still require a split.
- Existing accounts and vouchers are retained; new ledgers are added without overwriting custom codes. Exact and overlapping receipt imports are rejected.

Before upgrading: close the previous application and create a backup through Settings & backup. Replace the executable, not your data folder. The title should show 0.3.0. Your books remain under your existing Windows profile.

This executable is unsigned and remains a development build. No statutory reporting certification, automated GST allocation or general-purpose LLM is included. Windows-protected backups still require the original Windows account; portable recovery remains pending.

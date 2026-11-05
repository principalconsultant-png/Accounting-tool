# Bank transactions — accounting and Yathartha steps

A bank withdrawal is money leaving the bank; it is not automatically an expense. A deposit is money entering the bank; it is not automatically income. Standing instructions and transfers describe the payment method. Use the underlying purpose and evidence to select the ledger. The entries below are from the business's perspective, not the bank's debit/credit terminology.

Before posting, check Ledger A/c, AP payments and Book movements for an existing entry. If recorded, match it; do not create it again. Establish reviewed opening bank, cash, loan and payable balances at the bookkeeping start date. A bank statement import alone does not record revenue, expenses or opening balances.

| Statement item / actual purpose | Debit | Credit | Tool route |
| --- | --- | --- | --- |
| Loan recovery / EMI paid to lender | 2400 Bank loans for principal; 4580 Finance costs for interest; 4560 for genuine fees | Actual bank ledger, e.g. 1010, for total withdrawal | Record bank transaction → Loan repayment / EMI. Enter lender-confirmed principal, interest and fee breakup. |
| Recovery received of a loan previously given | Actual bank ledger | Dedicated loan-receivable asset under Other assets | Loan given recovered; book the opening receivable first. Interest received is separate. |
| Business cash withdrawal / ATM | 1000 Cash | Actual bank ledger | Cash withdrawal. Later petty-cash expenses are recorded separately when spent. |
| Deposit of business cash already recorded | Actual bank ledger | 1000 Cash | Cash deposit, or receipt-linked cash settlement. Never credit revenue a second time. |
| New loan proceeds deposited | Actual bank ledger | 2400 or the saved borrowing ledger for that lender | Loan proceeds received. Not sales income. |
| Owner capital introduced | Actual bank ledger | 3000 Capital or the reviewed owner-specific capital ledger | Other reviewed receipt; confirm entity/legal classification. |
| SMS charges / genuine card-processing charges / bank service charges | 4560 Bank and payment processing charges | Actual bank ledger | Bank / SMS / card charges. Card-settlement receipts are not card expenses. |
| Transfer between your own business bank accounts | Receiving bank | Sending bank | Own-bank transfer. Select the other saved INR bank ledger. Post once, then match the other statement to its existing book movement. |
| Standing instruction | Actual expense, advance, borrowing principal or liability, depending on purpose | Actual bank ledger | EMI: Loan repayment / EMI. Supplier invoice: AP payment. Other genuine non-tax payment: Standing instruction / other payment. |
| Transfer to vendor for a registered invoice | 2000 Trade payables (usual AP ledger) | Actual bank ledger | AP Vendor Invoices → Mark selected invoices paid, with actual payment date/reference/bank. Then match in reconciliation, or use the reviewed Invoice Payment Report workflow. |
| Transfer to employee as a recoverable advance | Dedicated staff-advance Asset ledger under Other assets | Actual bank ledger | Transfer to another person. Create the dedicated ledger in Chart of accounts if absent. It is not salary expense yet. |
| Salary already accrued | Saved salaries-payable liability | Actual bank ledger | Standing instruction / other payment, using the existing payable. If not previously accrued, use the reviewed salary expense/accounting workflow; do not expense both accrual and payment. |
| Owner's personal withdrawal | Reviewed drawings/current-account ledger appropriate to the legal entity | Actual bank ledger | Transfer to another person. A proprietor's drawings usually reduce equity; company/director withdrawals may be a receivable. They are not automatically business expenses. |
| Customer / patient collections deposited | Bank or collection clearing as applicable | Revenue, patient receivable or patient advance as supported by the original transaction | Sales receipt / Service revenue, then match or settle. Existing UPI/card receipts: settlement only, without reposting revenue. |
| GST/TDS remittance | Relevant tax payable | Actual bank ledger | Dedicated GST/TDS screens, then match the existing bank entry. A remittance is not a new expense. |

For loan-receivable recovery the exact entry is Dr Bank / Cr loan receivable. The asset must already represent the money lent. An incoming narration containing “loan recovery” must not be assumed to be repayment of your business's bank borrowing.

## Record a new bank-originated transaction

1. Open Bank reconciliation, load the actual bank and imported statement. Select an unmatched row and choose Record bank transaction. Alternatively open Reconcile side by side, tick exactly one bank row and choose Record bank transaction. Source rows are not required for this form.
2. Choose the accounting treatment and operating unit. Read the on-screen guidance. Choose the eligible counterpart ledger using its code and name. An SI/third-party transfer deliberately has no default expense ledger.
3. For EMI enter principal, interest and fees from the lender's statement/schedule. For example, principal10,000 + interest1,800 + fee200 against a12,000 withdrawal posts Dr2400 10,000 / Dr4580 1,800 / Dr4560 200 / Cr1010 12,000. Principal is not a P&L expense. Loan opening liability must already be recorded in the correct unit.
4. Enter the source/accounting review basis. Check purpose, unit, tax treatment and existing books, then tick the review confirmation.
5. Choose Preview journal. Check the actual bank date, each ledger, debit/credit and total. Confirm post and match only when correct. Preview alone changes no book entries. Posting creates one balanced voucher and matches that bank row's remaining amount.
6. Review the resulting entry in Ledger A/c and the link in Match history. Undo a guided posting from Match history if correction is needed: its owned journal reverses; records are not deleted. If an own-bank transfer has been matched on both statements, undo the counterpart match first before reversing the originating transfer.

The guided form does not infer a principal/interest split or GST credit from narration. It rejects ineligible ledger types, wrong direction/unit, already matched rows, unreconciled same-date/amount/reference book movements, and repayments/recoveries exceeding recorded loan/cash/liability capacity. Closed bank/financial periods still apply. Direct invoice/AP, patient and tax-control allocations remain in their dedicated workflows.

## Net settlements and GST on charges

For a recorded UPI/card receipt of1,000 deposited as990, tick the related source and bank deposit in Reconcile side by side → Use difference as bank charges → review10 → Automatically reconcile selected → inspect and confirm. This settles clearing and expenses the fee, without new revenue. For invoice payment1,000 / bank withdrawal1,010, the vendor payment stays1,000 and10 is a separate bank charge. Invoice/gross-book charge adjustments use one bank transfer at a time.

A separate SMS/bank-charge debit line is recorded as Bank / SMS / card charges, rather than netted against unrelated deposits. If already posted, match it instead. If “card charges” means an actual card purchase or repayment of a credit-card bill rather than a bank service fee, use the underlying expense/asset/payable treatment instead of4560.

If a valid bank tax invoice supports eligible GST input, separate the net fee and input tax through the existing reviewed GST/settlement workflow or Journal studio, then match the bank movement. For example, an eligible domestic118 charge may be Dr4560 100 + Dr1200 Input CGST9 + Dr1210 Input SGST9 / CrBank118. Use IGST1220 only when appropriate. Tax type, eligibility and invoice evidence must be reviewed; the guided gross-charge form does not claim GST input automatically. Ineligible/non-creditable GST forms part of the cost as applicable.

For transfers outside the same legal entity, do not use Own-bank transfer merely because the same person controls both businesses. Use the actual inter-entity loan, receivable/payable, capital or expense treatment supported by documents.

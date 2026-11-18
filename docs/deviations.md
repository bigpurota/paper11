# Differences, audit trail and interpretation

The dated design record precedes fitting. This page records source ambiguities, deliberate changes, and exploratory work.

| Item | Assigned paper | This project / implication |
|---|---|---|
| Empirical population | Spanish applications with randomly accepted real rejects | Taiwan financed accounts and Prosper first funded loans. We control selective label disclosure; historical profitability or losses for actual rejects are unidentified. |
| Target / prior | 3 consecutive months delinquent; bureau information | Next-month default or first recorded default within 12 payment cycles. Logistic prior uses only visible development outcomes. Its calibration can drift. |
| XGB | 100 trees synthetic, up to 10,000 with early stopping in Monedo | Fixed 100 depth-3 trees for all comparisons. No test-set hyperparameter selection. |
| Validation | 4 folds × 25 bootstraps on Monedo holdout | 4 cross-fitted tests on Taiwan; one chronological vintage test with label-maturity gaps on Prosper. Four errors versus one absolute error in the RMSE columns. |
| BASL stopping | Algorithm B.3 selects among augmented candidates | Main estimator starts with the first augmented round; guarded sensitivity may retain the original scorecard. Code review corrected an earlier baseline-eligible default, and we reran the analyses. |
| Other estimators | Reweighting including clustered variants, DR, Heckman, autoencoder, parceling and more | Logged-propensity IPW, hard cutoff, accepted-only XGB and logistic regression. True propensities are known only because we generated the issuance rule. |
| PAUC and ABR | FNR 0–.2; ABR integrated over 20–40% issued | Good-positive ROC, McClish-standardized pAUC. Exact continuous average of ABR with fractional score ties. The article does not fully specify numerical integration or standardization. |
| Profit | Historical loan size, cost distribution, and acceptance-rate optimization | Fixed unit principal and 10% income, LGD scenarios, validation-selected absolute cutoffs. Objective is margin per applicant; results also report per-issued-unit margin. It is not a forecast of revenue. |
| Inference | Original repeated random trial and CV inference | Independent simulation seeds. Paired empirical borrower bootstraps conditional on fits, splits, logged decisions and priors; no retraining or macro/vintage uncertainty. The main transfer comparison has one test vintage. A separate rolling extension analyzes twelve quarters with overlapping histories. |
| Additional outcomes | Confirmatory comparisons in assigned paper | Signed primary contrasts and intervals are shown even when unfavorable. Multiple other measures, LGDs and sensitivity variants are descriptive. No family of significance claims across secondary checks. |

**Exploratory randomized audit.** After inspecting the early baseline estimates, we added a fixed-budget diagnostic. At a frozen 30% validation policy, sample 10 or 50 historically rejected records. Compare drawing from all rejects versus from those the candidate would issue to. A Horvitz–Thompson expansion of sampled prior residuals estimates the default rate in the candidate portfolio. Report repeated-sampling RMSE against known validation truth. This is a retrospective experiment on masked labels. A real implementation would need funded random exploration and observed repayment; the audit does not create labels for real rejects.

**Source-data correction.** During independent review we found terminal Prosper defaults with cycle zero or missing. A terminal event of unknown age cannot be allocated to the one-year horizon. We exclude these cases before splitting and report both counts. The 12-cycle endpoint records the first event even when an account subsequently recovered.

**Uncovered questions.** The later Philippine analysis observes two real offer arms and cash receipts before costs. Unit economics after overhead, protected-group impacts and repayments under universal forced take-up remain unknown. A matched direction on public borrowers cannot substitute for the original randomized holdout.

**Follow-up scope.** The [dated design](extension-design.md) adds calendar forecasts, sensitivity bounds for a paired policy change, and a genuine experiment conducted by an independent team. The prior-transfer comparison using eight Philippine principal shortfalls was proposed after inspecting the four score-window/offer cells and has exploratory status. [Attribution and comparison](contributions.md)

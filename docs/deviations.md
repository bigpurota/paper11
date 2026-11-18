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

**Selection strength.** The simulated approval probability is $0.05+0.90\,\mathrm{expit}(\cdot)$ of pre-outcome features, so every applicant has a 5–95% chance. On Taiwan 63.7% are accepted, the 5th percentile of the approval probability is 0.23 and bad rates are 17.4% among accepts versus 30.4% among rejects. On Prosper 56.5% are accepted, 10% of applicants have a probability below 0.10 and the bad rates are 8.2% versus 16.5%. Overlap is therefore wide: logged-propensity IPW is valid, and accepted-only training already sees almost every region of the applicant space. This is the regime in which reject inference has least to add. An exploratory [hard-cutoff sensitivity](hard-selection.md) on the same index makes Bayesian evaluation clearly better on Taiwan and BASL clearly worse. Counts come from `load_population` in [the data module](../src/paper11/data.py).

**Source-data correction.** During independent review we found terminal Prosper defaults with cycle zero or missing. A terminal event of unknown age cannot be allocated to the one-year horizon. We exclude these cases before splitting and report both counts. The 12-cycle endpoint records the first event even when an account subsequently recovered.

**Uncovered questions.** The later Philippine analysis observes two real offer arms and cash receipts before costs. Unit economics after overhead, protected-group impacts and repayments under universal forced take-up remain unknown. A matched direction on public borrowers cannot substitute for the original randomized holdout.

**Follow-up scope.** The [dated design](extension-design.md) adds calendar forecasts, sensitivity bounds for a paired policy change, and a genuine experiment conducted by an independent team. The prior-transfer comparison using eight Philippine principal shortfalls was proposed after inspecting the four score-window/offer cells and has exploratory status. [Attribution and comparison](contributions.md)

**Identification and decision audit.** After reviewing the first policy frontiers we built paired completions of the same archive, compared minimax-regret policies and designed a group-sequential audit for the fixed 30% versus 50% comparison. These are exploratory analyses on the existing splits. The frozen audit uses observed validation outcomes for its boundaries and masked outcomes only to assess its operating characteristics. Its error guarantee is conditional on the finite population and random ordering. [Two-world construction](identification.md) · [Audit design](decision-audit.md)

**Two general questions.** After the finite-cohort audit we asked which linear measurements suffice to recover all payoff differences for a menu of policies, and when funding a marginal loan to learn its outcome could pay for itself. The algebraic criterion concerns arbitrary expected margins under additive lending payoffs; the dynamic model supplies a separate, explicitly assumed probability law and decision horizon. Parameters in that model are illustrative. [Policy information](policy-information.md) · [Dynamic experiment](exploration.md)

## Exploratory lending

We developed the general one-pilot threshold after studying the adaptive three-application example. The assumption that the lender receives only one additional outcome within the planning horizon defines a different policy class. We report both. Parameter-grid counts describe chosen combinations and carry no probability interpretation. The SBA 504 test uses an independent archive of financed loans and scenario payoffs. Its design and data-timing choices are documented with the replay. [Theory](information-value.md) · [Protocol](pilot-replay.md)

## Transfer and late payments

The 7(a) test keeps the 504 financial terms as its first specification, then recalibrates the same pricing formula on mature 7(a) outcomes before the decision period. The main US calculation uses a pre-specified borrower draw. Searching other possible branches after the fact illustrates existence. We report their probabilities separately. The Bondora study predefines a 36-month observation minimum and a broader 12-month cohort. Apparent cash gains in the broader cohort prompted a check on a later matched export. The 2024 results use identical loan identities and frozen decisions. Computing gains again restricts measurement error from early collections but does not remove remaining collections risk. [Details and cash components](lender-pilot.md)

## Size-aware rule and information access

The Estonian profiles and sensitivity to how much weight a lender gives a single observation were explored after viewing the original cash ledger. Both successes belong to one country, one customer group and neighboring months. The 2026 workbook lacks the earlier new/returning indicator, so the later-cohort protocol grouped by country and origination risk grade before outcomes were accessed. The comparison tests transport across both calendar time and the available segmentation. [Profiles](pilot-profiles.md) · [Information sensitivity](pilot-signal-sensitivity.md) · [Locked test](pilot-holdout.md)

Named Bondora grades first appeared in September 2023. This prevented any qualifying pilot in the primary window. We kept that zero-coverage result and the original rule. The subsequent Prosper check used a publicly fixed cross-lender protocol for new pilot endpoints on a previously used source. [Supplementary test](pilot-prosper.md)

## Information from an individual pilot

The known Finnish cases are retrospective. A subsequent experiment pools by country to bridge the grading change. Both banks share an ordinary risk update. We test two assumptions about visibility of the other loans in the pilot’s cohort. The archive gives no data-access log. The study forecasts defaults among historically financed loans under replayed decisions, with cash measured at a common ledger date. The Netherlands supplies all eight nonempty opportunities in the direct-loss subset and has no training episodes. We retained the frozen parameters and the positive, negative and zero results across all prespecified comparisons. [Protocol](pilot-signal-ml-protocol.md) · [Coverage](pilot-signal-panel.md) · [Paired results](pilot-signal-ml.md)

The frequency diagnosis is retrospective. The next chronological test used country groups after the previous grade screen had found no qualifying groups. Continuation loans are new; eight primary pilot positions had appeared in earlier books. Both ranks share the same future books. Four months across two quarters give descriptive comparisons only. [Dated design](frequency-protocol.md) · [Results](frequency-test.md)

## Dutch history and US transfer

The Dutch contract-mix explanation and reconstruction of the launch were prompted by the known forecast error. The externally fixed test uses a different product, geographic unit and outcome horizon. Wells Fargo state-quarter targets cover actual funded loans and three-year recorded charge-offs. The confirmation criterion compares the hybrid with both available alternatives, including the broader rate. Cutoffs and scenario returns describe replayed policies. [Dated test protocol](local-trust-protocol.md) · [External results and limits](local-trust-bank.md)

## Payment signals and target definitions

Bondora supplies dates of formal default and early payoff in separate vintages. The Dutch payment-and-arrears snapshot came after the eight forecasts. Czech transactions reconstruct cumulative instalment shortfall at monthly closes. Both applications share a forecasting rule, with different events and lead times. [Methods and limits](early-warning.md)

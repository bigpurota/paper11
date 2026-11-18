# Team 12 · Fighting Sampling Bias

Team 12 · Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox.

This report uses the assigned preprint and public borrower records. An approval scorecard is needed for everyone who applies, while repayment is usually observed only for the people actually financed. Training with inferred labels and evaluating on the complete applicant mix solve different problems.

## Synthetic replication of Figure 2

| statistic | paper_value | estimate | ci_low | ci_high |
|---|---|---|---|---|
| accept_eval_rmse | 0.2010 | 0.2433 | 0.2218 | 0.2648 |
| bayes_eval_rmse | 0.0929 | 0.0771 | 0.0618 | 0.0932 |
| oracle_gap | 0.0598 | 0.0715 | 0.0595 | 0.0846 |
| basl_recovery_fraction | 0.2482 | 0.2961 | 0.2122 | 0.3728 |

Twenty independent runs, 40 batches each. Intervals resample complete simulation seeds. Recovery is a fraction of the gap between accepted-only and full-label training. Evaluation error is measured against true holdout labels. The first four shared plotted checkpoints are displayed on identical axes. The published long-run summaries cover a longer experiment.

![Figure 2 comparison](simulation_fig2.png)

## Published Monedo versus our public-cohort experiments

Table 2 compares errors in prediction of a scorecard metric; smaller is better. Table 3 compares scorecards on held-out borrowers. Smaller Brier and ABR, higher AUC and pAUC are better. The reweighting rows compare different weight estimators. Targets, default rates and approval mechanisms differ across datasets.

| table | method | monedo | taiwan | prosper |
|---|---|---|---|---|
| 2 | accepts | 0.0356 | 0.0143 | 0.0135 |
| 2 | bayes | 0.0130 | 0.0135 | 0.0035 |
| 2 | ipw | 0.0315 | 0.0105 | 0.0068 |
| 3 | accepts | 0.2388 | 0.0720 | 0.0340 |
| 3 | basl | 0.2211 | 0.0737 | 0.0341 |
| 3 | hard_cutoff | 0.2458 | 0.0739 | 0.0402 |
| 3 | ipw | 0.2346 | 0.0723 | 0.0329 |

The complete four-metric comparison is in [paper_comparison.csv](paper_comparison.csv).

## Training, risk lift and calibration

| dataset | method | auc | brier | pauc | abr | lift10 |
|---|---|---|---|---|---|---|
| prosper | accepts | 0.6313 | 0.0596 | 0.5660 | 0.0340 | 1.9784 |
| prosper | basl | 0.6350 | 0.0596 | 0.5633 | 0.0341 | 2.0036 |
| prosper | basl_guarded | 0.6350 | 0.0596 | 0.5633 | 0.0341 | 2.0036 |
| prosper | hard_cutoff | 0.5984 | 0.0605 | 0.5487 | 0.0402 | 1.6547 |
| prosper | ipw | 0.6291 | 0.0598 | 0.5667 | 0.0329 | 1.8885 |
| prosper | logit | 0.6116 | 0.0599 | 0.5563 | 0.0367 | 1.7266 |
| taiwan | accepts | 0.7766 | 0.1357 | 0.6338 | 0.0720 | 3.1332 |
| taiwan | basl | 0.7768 | 0.1360 | 0.6317 | 0.0737 | 3.1349 |
| taiwan | basl_guarded | 0.7766 | 0.1360 | 0.6324 | 0.0731 | 3.1364 |
| taiwan | hard_cutoff | 0.7748 | 0.1433 | 0.6302 | 0.0739 | 3.1558 |
| taiwan | ipw | 0.7768 | 0.1361 | 0.6334 | 0.0723 | 3.1273 |
| taiwan | logit | 0.7218 | 0.1485 | 0.5659 | 0.1212 | 3.0487 |

Lift10 is the bad rate in the riskiest tenth divided by the population bad rate. The Taiwan test shows a modest increase in bad loans among the safest borrowers under BASL. The Prosper training contrast is small relative to its interval. The simulated training improvement does not transfer consistently.

![Calibration by risk group](calibration.png)

The diagonal represents perfect calibration. Each point represents an equal-frequency group (ties kept together); the cohorts have separate scales. Calibration measures agreement between predicted and observed frequencies, while AUC measures ordering.

## Exposure to the prior

| method | prosper | taiwan |
|---|---|---|
| accepts | 0.0135 | 0.0143 |
| bayes | 0.0035 | 0.0135 |
| bayes_odds_double | 0.0025 | 0.0370 |
| bayes_odds_half | 0.0068 | 0.0082 |
| ipw | 0.0068 | 0.0105 |

The central Bayesian prior is a logit trained only on observed training outcomes. Halving or doubling reject odds leaves the scorecard and its rankings unchanged. It changes which hidden outcomes are assumed when estimating performance. A stronger prior in one cohort can be worse in another. Taiwan RMSE uses four folds; the single chronological Prosper split yields an absolute error.

The complete labels in the validation cohort also allow a retrospective test that removes population transfer. On Taiwan the accepted-only and Bayesian errors are 0.0059 and 0.0179, respectively. On Prosper they are 0.0113 and 0.0013. Taiwan's small improvement on an independent same-vintage sample therefore cannot be attributed solely to correcting selection.

## Paired uncertainty

| dataset | contrast | estimate | ci_low | ci_high |
|---|---|---|---|---|
| taiwan | basl_minus_accepts_abr | 0.0016 | 0.0002 | 0.0030 |
| taiwan | bayes_minus_accepts_profit_at_lgd50 | 0.0000 | 0.0000 | 0.0000 |
| taiwan | basl_minus_accepts_brier | 0.0003 | 0.0000 | 0.0006 |
| taiwan | bayes_minus_accepts_rmse_abr | -0.0008 | -0.0095 | 0.0078 |
| prosper | basl_minus_accepts_abr | 0.0001 | -0.0022 | 0.0026 |
| prosper | bayes_minus_accepts_profit_at_lgd50 | 0.0000 | 0.0000 | 0.0000 |
| prosper | basl_minus_accepts_brier | 0.0000 | -0.0002 | 0.0002 |
| prosper | bayes_minus_accepts_rmse_abr | -0.0100 | -0.0133 | 0.0053 |

Training comparisons use the same test borrowers under both models. Evaluation-error comparisons assign each borrower one shared Poisson weight wherever it recurs across folds. Intervals are conditional on fitted models and logged decisions. Both empirical intervals for the change in ABR estimation error include zero. Zero conditional policy variance at the base LGD means the methods took the same decisions on these cases.

## Conditional lending policy

| dataset | lgd | accepts | bayes | ipw | bayes_minus_accepts |
|---|---|---|---|---|---|
| prosper | 0.2500 | 0.0431 | 0.0431 | 0.0431 | 0.0000 |
| prosper | 0.5000 | 0.0378 | 0.0378 | 0.0378 | 0.0000 |
| prosper | 0.7500 | 0.0325 | 0.0325 | 0.0325 | 0.0000 |
| prosper | 1.0000 | 0.0272 | 0.0272 | 0.0272 | 0.0000 |
| taiwan | 0.2500 | 0.0372 | 0.0372 | 0.0372 | 0.0000 |
| taiwan | 0.5000 | 0.0242 | 0.0242 | 0.0242 | 0.0000 |
| taiwan | 0.7500 | 0.0124 | 0.0118 | 0.0124 | -0.0006 |
| taiwan | 1.0000 | 0.0067 | 0.0062 | 0.0067 | -0.0006 |

The entries are margin in units of principal per arriving applicant using an assumed 10% return if repaid. Issuance rates, per-issued-unit margins and numerical cutoffs are in [policy.csv](policy.csv). At 50% LGD all three estimators select the upper end of the allowed rate grid, so the realized difference is exactly zero. The paper’s stated gain in profit depends on its pricing, approval decisions and Spanish borrower population.

## Can a small randomized audit improve ABR measurement?

| dataset | n_audited | design | audit_rmse | prior_only_rmse |
|---|---|---|---|---|
| prosper | 10 | all_rejects | 0.0289 | 0.0003 |
| prosper | 10 | policy_rejects | 0.0088 | 0.0003 |
| prosper | 50 | all_rejects | 0.0111 | 0.0003 |
| prosper | 50 | policy_rejects | 0.0031 | 0.0003 |
| taiwan | 10 | all_rejects | 0.0455 | 0.0188 |
| taiwan | 10 | policy_rejects | 0.0195 | 0.0188 |
| taiwan | 50 | all_rejects | 0.0201 | 0.0188 |
| taiwan | 50 | policy_rejects | 0.0086 | 0.0188 |

For a fixed proposed 30% approval policy, each audit reveals 10 or 50 funded outcomes under controlled masking. Both designs reveal the same number of outcomes. Financial exploration costs may differ. Targeting only previously declined borrowers whom this policy would approve lowers sampling variability. Compare against prior-only RMSE as well: a good prior can beat a noisy small audit on a given cohort. Random disclosure identifies the fixed-policy default rate in this finite validation cohort; small samples may still be imprecise. Each result pools squared error across 500 draws per split before taking the square root.

## Our extensions

### Which measurements recover every policy difference?

Consider five nested policies, with four nonempty groups entering between consecutive cutoffs. Their four unknown expected margins suffice for every exact pairwise comparison. When those margins can vary on an open set, four is the minimum number of independent linear measurements for that task. The sign alone can sometimes be learned with fewer. For general lending rules, the answer is the rank of the matrix of differences on the unknown margins.

| design | n_policy_pairs | pairs_exact_at_actual_binary_totals | decisions_settled_at_actual_binary_totals |
|---|---|---|---|
| expansion_bands | 50 | 50 | 50 |
| prior_deciles | 50 | 0 | 1 |

The rows above use the actual aggregate counts of masked outcomes, disclosed retrospectively on each validation split. Counts are comparisons across four Taiwan splits and one Prosper split. [Data-independent proof and finite-cohort check](../docs/policy-information.md)

### When can a lender pay to observe a repayment?

In the illustrative persistent-regime decision model, a loan of 100 has immediate expected margin -1.41. Starting with 3 applicants available, the lender first finds funding worthwhile: its optimal total expected margin is 0.79, versus zero under the best fixed decision. At ten opportunities the total reaches 19.37. If each new borrower draws an independent regime, a repayment has zero value for the next decision. The horizon counts all applicants, including the pilot. Repayment on a funded loan arrives before the next decision. These are illustrative monetary units, independent of the public datasets. [Decision tree, assumptions and tests](../docs/exploration.md)

![Expected value of lending to learn](exploration_value.png)

### The price of a single repayment observation

Compare the expected loss on the pilot with the discounted increase in the best future policy's value after observing that repayment. Both policies can use the same other information. On 100 units of principal the persistent example loses 1.4125 up front and adds 0.548125 per later decision. It clears break-even at 3 later applicants. With a 10% redraw probability the lifetime gain is bounded by 0.70889. [General criterion and analytic proof](../docs/information-value.md) · [Sharp bounds for different pilot and follow-up risks](../docs/pilot-dependence.md)

The grid spans 816,480 parameter combinations. Of the 437,400 with negative direct expected margin, a single pilot covers that loss in 9,017. Grid frequencies describe our design. [Aggregate stress results](information_value_stress.csv)

![Timing, persistence and the first profitable horizon](information_value_frontier.png)

### Does this signal change decisions on historical SBA 504 loans?

The administrative extract has 111,066 rows, with 92,410 eligible disbursements. We compare identical regional follow-up portfolios using a common updated risk estimate. Each episode evaluates the first 25 continuation positions. The future quarterly source pools contain 51,444 financed loans. Among 79 initially loss-making region-quarter episodes the plug-in rule selected 3 pilots. At disclosure the signal could change the decision in 0 of these. Including the pilot cash flow, the incremental margin was -0.022 per eligible episode, in units per 100 principal on one loan (95% moving-block interval -0.076 to +0.005).

Requiring a pilot in every eligible episode gave +0.019 in gross continuation gain and -0.364 in direct pilot margin. Net gain versus the updated no-pilot policy was -0.345 [-0.529, -0.194]. The financial terms are scenarios applied to three-year recorded charge-offs. Results concern historically financed loans and the specified decision rule. [Replay protocol, comparators and sensitivity](../docs/pilot-replay.md)

### Could the bank identify promising pilots in advance?

Each rule receives only information available at origination and pays the direct pilot margin once. A new forecast allows the public risk estimate to change while repayment is pending, using only earlier public updates that have already arrived. Both rules face the same future opportunities.

Bondora, at least three years of subsequent payments: the fixed-risk rule selected 2 of 100 eligible pilots. AUC for positive realized scenario gain was 0.609 (95% four-quarter block interval 0.478 to 0.734). Net versus skipping all pilots was +0.200 per eligible episode when one loan has principal 100. Positive net can also come from collecting the pilot itself.

SBA 7(a), using early local pricing: the fixed-risk rule selected 16 of 85 eligible pilots. AUC for positive realized scenario gain was 0.416 (95% four-quarter block interval 0.206 to 0.624). Net versus skipping all pilots was -0.691 per eligible episode when one loan has principal 100. Positive net can also come from collecting the pilot itself.

SBA 7(a) offers an existence example. In the West, one actual failed pilot from 2002 Q2 could have changed the rule from funding to declining the same 25 later loans. Using reported charge-off amounts and the hypothetical performing margin gives -98.00 on the pilot, +209.13 on subsequent decisions and +111.14 overall. We identified this branch after scoring. Its region-quarter was selected up front, but the precommitted borrower draw chose a different pilot. [Exact branches and calendar windows](../docs/pilot-transfer.md)

In the extended Bondora window, the October 2018 Estonian pilot lost €267.00. Relative to lending to all 25 subsequent borrowers in November 2019, the pilot-informed refusal would avoid €16,211.29 in cash shortfall as of May 24, 2024. The paired net is €15,944.29. Across the 3 selected pilots that changed a decision, 2 still covered their actual euro loss at this date. This follow-up uses the same loan identities, and outstanding collections could change the result. These decisions were replayed.

![Paired cumulative cash gains at the two valuation dates](lender_pilot_cash.png)

In Kenya the bank used its TOBOA experiment with previously rejected borrowers to revise the M-Shwari scorecard. The case study reports acceptance rising from 40% to 47%. It gives no incremental profit attributable to that change. [Field evidence](../docs/observed-pilot-evidence.md) · [European payment archives](../docs/lender-pilot.md) · [Forecasts, units and uncertainty](../docs/pilot-targeting.md)

### Can the archive identify which policy earns more?

Hold all visible outcomes fixed. Grant access to the actual number of defaults in each of ten groups of hidden applicants ranked by the frozen prior. The grouping is fixed before reading the true aggregate counts. On Taiwan, moving these same defaults within groups yields both negative and positive gains for the same 30% to 50% expansion in every split. The mean bounds are -0.82 to +0.99 pp of scenario margin per applicant. On Prosper these ten true counts are sufficient to determine a positive sign (+0.20 to +1.47 pp). These aggregates use retrospective information unavailable to the original lender. A second sensitivity case substitutes counts obtained by rounding the prior probabilities. We also solve the minimax-regret choice among five cutoffs and audit the frozen rule on holdout. [Construction, proof and results](../docs/identification.md)

### What would it take to resolve the decision?

For the Prosper validation pool, 160 repayments among the additional approvals were hidden. In the retrospective truth, 17 defaulted. The exact random-order audit uses 14.46 labels on average. At the last profitable and first unprofitable hidden default counts it uses 152.89 and 153.02. The prespecified review schedule bounds wrong-direction decisions by 5% for each fixed population. The required sample depends on how close that population is to break-even. [Stopping boundaries, proof, and sample-size distributions](../docs/decision-audit.md)

[What the authors did, what Team 12 added, and how the evidence compares with Paper 15](../docs/contributions.md)

### Correcting old labels versus predicting the next quarter

| method | quarters | masking_rmse | forecast_rmse | quarters_better_than_accepts |
|---|---|---|---|---|
| accepts | 12 | 0.7856 | 2.0751 | 0 |
| bayes | 12 | 0.2614 | 2.3566 | 7 |
| ipw | 12 | 0.1698 | 2.3915 | 7 |
| oracle_history | 12 | 0.0000 | 2.2677 | 7 |

Both RMSE columns above are in percentage points of integrated ABR. Bayesian evaluation improves historical measurement but produces larger next-quarter RMSE over twelve Prosper cohorts, despite winning in seven individual quarters. The historical oracle uses complete previous outcomes and still experiences temporal transfer error. [Period definitions and error decomposition](../docs/vintages.md)

![Twelve calendar forecasts](vintage_forecasts.png)

### Prior sensitivity at a lending decision

With 10% interest, 50% LGD and a fixed 30% incumbent, the validation lower bound for the 50% expansion's conditional expected margin stays nonnegative up to an odds multiplier of 1.85–2.30 in Taiwan and 13.19 on Prosper. Absolute cutoffs are frozen before testing. With unrestricted missing outcomes a zero-downside validation rule retains the incumbent. These are sensitivity endpoints, distinct from sampling confidence intervals. [Definitions, paired gains and held-out results](../docs/bounds.md)

![Policy selection under bounded uncertainty](bounds_frontier.png)

### Randomized offers and actual borrowing in the Philippines

The analytic extract contains 1,113 marginal applicants. Expanding offers from the high score window to both windows changes the funding rate by 8.02 percentage points and the lender cash margin by 4.19 PPP dollars per assigned applicant (95% bootstrap interval 3.02 to 5.45), before other costs. The result refers to this selected extract under within-window comparability. The underlying experiment was conducted by Karlan and Zinman.

The estimated share with a principal shortfall greater than one peso under hypothetical universal funding is only bounded between 0.97% and 28.84% if the non-takers’ repayment is unrestricted. This identified set has a different interpretation from a confidence interval. As a sparse check of a risk prior carried over from the high score window, the observed lower window has 2 shortfalls among 50 funded borrowers versus 0.50 expected. [Assumptions, primary sources and exact rare-event comparison](../docs/rct.md)

![Philippine randomized offers and partially observed risk](rct_policy.png)

### Did a cheaper pilot and an exposure-aware forecast transfer?

Both Estonian successes had €530 principal on a 36-month contract and five prior loans. July's €530 pilot left the follow-up action unchanged. The revised rule values the next up to 25 loans at an exposure estimated before origination. It also allows the bank's ordinary risk estimate to change while waiting. The expected cash gain sets the funding decision. A separate score ranks the chance that a change of action will cover a direct pilot loss.

| Cohort | Eligible | Old / new issued | Strict recoveries caught / available | New vs skip per eligible | New minus old per eligible |
|---|---|---|---|---|---|
| Bondora discovery, expanded | 228 | 10 / 17 | 2 / 2 | €76.69 | €5.05 |
| Bondora, June–September 2024 | 0 | 0 / 0 | — | — | — |
| Bondora, July 2020–September 2022 | 23 | 0 / 2 | 0 / 1 | €10.86 | €10.86 |
| Prosper, January 2008–January 2012 | 30 | 0 / 0 | 0 / 0 | $0.00 | $0.00 |

The two development cases were already known. The new rule selected 17 pilots, retained the unsuccessful February switch and added €5.05 per eligible opportunity over the old rule (95% block interval €-3.58 to €28.28). Doubling the effective strength of historical information or sharing the other matured same-month loans removed all three original switches.

The primary holdout had 62,903 funded loans and no comparable grade histories. In the more seasoned window the revised rule earned €10.86 per eligible opportunity (95% block interval €0.00 to €21.41). Every euro came from the pilot loans themselves. The missed Finnish pilot lost €386.82; its replayed refusal of 25 follow-ups would have yielded €3,716.92 net on cash recorded in the November 2026 release. Later collections can change that number.

The strict-recovery score had AUC 0.636 (95% interval 0.533 to 1.000 on 1,810 estimable draws of 2,500). This clears the prespecified numerical ranking criterion. There was one positive example. Its Finnish score beat seven of 15 comparable negatives (within-segment AUC 0.467). Average precision was 0.111 versus a prevalence of 0.043. No rule that issued a pilot on these dates captured the strict event.

The same decision rule selected 0 of 30 opportunities at US lender Prosper. The archive supplied no strict recoveries among those eligible opportunities and thus no estimable AUC. The two US policies tied at the archived cash cutoff. This supplementary cross-lender test was locked after the Bondora results and before computing the Prosper pilot contrasts.

![Historical contract size and the later ranking of all eligible candidates](pilot_forecast_validation.png)

[Origination profiles](../docs/pilot-profiles.md) · [Information sensitivity](../docs/pilot-signal-sensitivity.md) · [Frozen model](../docs/pilot-rule-protocol.md) · [Bondora](../docs/pilot-holdout.md) · [Prosper](../docs/pilot-prosper.md) · [All policy results, ablations and intervals](pilot_rule_summary.csv)

### Can the lender forecast what this particular pilot will teach it?

| Finnish pilot | Direct forecast (€) | Forecast value of learning (€) | Total forecast (€) | Paired ledger cash if issued (€) |
|---|---|---|---|---|
| 2021-03 | -86.93 | +6.73 | -80.19 | +3,716.92 |
| 2021-11 | -19.50 | +29.29 | +9.80 | +249.80 |
| 2022-02 | -14.81 | +38.99 | +24.18 | +0.00 |

In March 2021 the previous rule put a 1.20% chance on a changed decision for a nonempty portfolio. The later ordinary risk update brought the portfolio close to break-even. The pilot default then moved risk from 16.47% to 20.45%. In the alternative where both lenders could also see the other 473 loans from that month, the same default moved risk from 7.36% to 7.55% and both would lend. The ledger records funded loans. The extra cash in the table results from replaying the earlier information assumption. [Finnish case reconstruction](../docs/finnish-pilot-cases.md)

A frozen boosting model priced the two possible observations at issue, then predicted the same future portfolio with its actual pilot outcome hidden and revealed. It learned from 232 earlier country–months. Among 48 later nonempty portfolios, the ordinary update improved its Brier score by 0.00822 and adding other loans from the same cohort improved it by 0.03002. The simple historical-risk forecast scored 0.08550, ahead of the boosting model with peers (0.09284).

Revealing just the pilot changed Brier by -0.000097 in the direction of improvement (95% block interval -0.000469 to +0.000262). Of 19 initially loss-making opportunities, the model chose 0. The earlier selector chose 2 and its direct ledger cash summed to €-529.78. Neither selector captured a strict recovery. Only eight eligible cases had a nonempty continuation, all Dutch. The archive measures gross cash to its cutoff.

![Forecast error by information set and the extra value of a single pilot](pilot_signal_ml.png)

[Frozen design](../docs/pilot-signal-ml-protocol.md) · [Coverage and timing](../docs/pilot-signal-panel.md) · [Model and interpretation](../docs/pilot-signal-ml.md) · [All ablations, cash and intervals](pilot_signal_ml_metrics.csv)

### Why did a country default frequency beat boosting?

In the earlier 48 portfolios the historical estimate used a median of 28,603 mature loans; the boosted model learned from 232 portfolio outcomes. In Finland the realized future default exposure averaged 9.24%, the historical rate 8.90%, and boosting at issue 38.44%. The model had received the historical rate as an input. Holding all other Finnish test fields fixed and substituting the earlier Finnish median rate moved the mean prediction only to 39.28%.

Across all 48 portfolios the square of the mean forecast error explains 82.8% of the issue-time Brier gap. This describes a shift in the level of risk. The size of the historical sample varied sharply by country. [Country profiles and exact error decomposition](../docs/frequency_diagnosis.md)

### A frequency anchor on the next four months

Starting at the same historical rate, we trained three corrections on mature books and published their specification before scoring. In June–September 2024 the first-position candidate led to 12 supported books with 300 follow-up loans. The mean Brier loss at issue was 0.083211, after ordinary and peer updates 0.078720, and after revealing the pilot 0.078726. Directly pooling the peer frequencies scored 0.078538. A boosting model trained through the same cutoff scored 0.081877 with the pilot. All comparisons use the same subsequent portfolios.

In Netherlands, the 2024-06 pilot's ordinary news moved the bank from decline to lend. The book contained €67,808 of principal. It earned €6,780.80 at the fixed first-year terms. The cumulative cash margin was −€47,498.91 with €54,043.41 principal outstanding. Revealing the pilot changed zero actions. No pilot in either candidate rank defaulted within its first year. Four origin months support descriptive comparisons only.

![Finnish risk levels and forecast performance on the fresh portfolios](frequency_forecasts.png)

[Public protocol](../docs/frequency-protocol.md) · [Panel and overlap](../docs/frequency-panel.md) · [Model](../docs/frequency-model.md) · [Full test, thresholds and cash](../docs/frequency-test.md)

### A local market at launch and a test at a different bank

The Dutch first-year rate at issue averaged 27.19% across eight opportunities. Three forecasts used the same 245 loans disbursed in September and October 2022, the first two months of the market. Among later loans, 687 of 16,621 recorded a first-year default. In the first-25 portfolios 9 of 200 loans defaulted, for a mean defaulted share of principal of 4.79%. The change in risk across origination months accounts for 22.98 percentage points of the 22.40-point gap. [Calendar, contracts and decomposition](../docs/dutch-frequency.md)

The size of the recent local business and differences among other mature markets determine the weight placed on local data. The hybrid Dutch forecast averaged 22.29%, and the other-country rate 13.36%. The rule was designed after seeing these cases. For an independent test we fixed the same rule on Wells Fargo's SBA 7(a) state portfolios before opening a new approval archive. [Rule and test registration](../docs/local-trust-protocol.md)

Across 828 supported state-quarters and 23,849 loans, the hybrid's mean Brier improvement was +0.001684 over local (95% block interval +0.001131 to +0.002142) and +0.000014 over the outside-state rate (-0.000005 to +0.000046). Local was closer in 40 of 67 local-majority calls. Broader was closer in 449 of 761 other calls. This gives 489 correct choices against 476 for always choosing the outside-state rate. The hard choice and the continuous hybrid have distinct endpoints.

![Dutch launch forecasts and geographic choices at Wells Fargo](local_trust_transfer.png)

[Decision condition and assumptions](../docs/local-trust.md) · [Wells Fargo methods, scenarios and results](../docs/local-trust-bank.md) · [Paired accuracy](local_trust_bank_metrics.csv) · [Economic scenarios](local_trust_bank_policy.csv)

## Limits and a three-month follow-up

We can test label concealment among already funded borrowers. A randomized sample of actual would-be declines with mature repayment labels would identify the target population more directly. Collect such a sample under a fixed decision policy, estimate default and realized net revenue with funding costs, and repeat across time vintages and adequate overlap regions. Twelve Prosper quarters provide evidence on temporal transfer at one lender. Profit net of financing and servicing costs and transport to other macroeconomic conditions still require additional data.

[Data provenance](../docs/sources.md) · [Implementation](../docs/algorithm.md) · [Deviations](../docs/deviations.md) · [Simulation](../docs/simulation.md)

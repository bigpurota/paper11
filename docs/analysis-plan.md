# Analysis decisions before inspecting model results

Team 12 • DSBA Research Seminar • Round 3 • assigned arXiv:2407.13009v1, main text and appendix. This is a local, versioned design record, not a registered external protocol.

* Primary population-transfer experiment: UCI Default of Credit Card Clients, next-month default. Four disjoint test folds. Fit, BASL stopping, policy validation and final evaluation have separate records within each fold.
* Second cohort: Prosper US issued loans. One record per borrower, first origination in the file. Target is recorded first default in payment cycles 1–12. Use only origination cohorts whose 12-month outcomes could have matured by each next decision date and by the extract. No lifetime loss, servicing, or repayment variables among predictors.
* Both open datasets already consist of financed accounts. Generate a soft historical acceptance mechanism from pre-outcome features. Mask reject outcomes before training, stopping and estimating metrics. The holdout represents the underlying dataset, not actual declined loan applicants. The logit fitted on visible training labels provides an imperfect prior. Inverse propensity weighting uses logged design probabilities.
* Primary evaluation contrast: RMSE of the predicted integrated ABR (20–40% approved) against ABR on unseen applicants. Primary training contrast: BASL minus accepted-only integrated ABR on exactly the same test applicants. AUC, FNR-oriented standardized pAUC, Brier score and highest-risk decile lift are secondary. Report failures, ties and improvements.
* Candidate decision policies approve the lowest-risk 10–50% of the policy-validation population in steps of 5 percentage points. Freeze the numerical PD cutoff before testing. Normalize profit to one unit of principal offered per applicant, with issuer income 10% and base LGD 50%. Secondary LGDs 25%, 75% and 100%. These are scenarios, not observed lending profit. Apply the same tie rule to all policies.
* Perturb prior odds by factors 0.5 and 2, hold the evaluated scorecard fixed. Compare to logged IPW and hard pseudo-labeling, including calibration and effective sample size. Add a controlled simulation with known labels, a random-selection placebo and independent seeds.
* Paired test-set bootstrap for BASL and policy effects; condition on fitted models, respect folds, show intervals and a minimum detectable effect scale. Secondary diagnostics are exploratory; do not choose models or claims from a grid of test p-values.
* The original Monedo randomized approval labels are unavailable to this project. Transcribe reference estimates from Tables 2/3 and Section 7, never fill gaps in the paper with artificial author results.

## Follow-up on the value of an individual repayment

The prior three-application exercise motivated a subsequent one-pilot experiment. The theory specifies timing, dependence and the degree of later adaptation. The SBA extension uses another funded-loan archive to replay a dated one-pilot rule, a forced pilot and the same no-pilot decision with refreshed common information. Study choices and secondary specifications are described with the corresponding results. This extension is exploratory. [Theory and grid](information-value.md) · [Chronological SBA design](pilot-replay.md)

## Other lending archives

The transfer designs specify the information date, primary portfolio, candidate loan, policy threshold and comparison against newly available public risk estimates. Archive draws and parameters were fixed before scoring those cohorts. Conditional examples discovered during examination and subsequent attempts to follow the European cash flows for longer are labeled retrospective. [SBA 7(a)](pilot-transfer.md) · [Bondora](lender-pilot.md) · [Forecast and evaluation design](pilot-targeting.md)

## Rule redesign and temporal validation

The 2018 cases were known during development. The revised rule and success criteria were published in [0fda6dd](https://github.com/bigpurota/paper11/commit/0fda6dd), followed by the workbook, episode definitions and dates in [9110afd](https://github.com/bigpurota/paper11/commit/9110afd). Outcome evaluation followed both commits. The shorter holdout cannot identify uncertainty with four-quarter blocks. [Protocol](pilot-rule-protocol.md) · [Cohorts](pilot-holdout.md)

After the Bondora tests, we locked a supplementary test on a different lender in [11bf82d](https://github.com/bigpurota/paper11/commit/11bf82d). The existing Prosper archive had informed the earlier scorecard experiments. The pilot selection, decision changes and paired cash returns were first computed after this supplement was specified. [Design](pilot-prosper-protocol.md) · [Results](pilot-prosper.md)

## A dated test of the value of one private observation

The three known Finnish cases motivated a separate experiment on country-level portfolios. Before evaluating the new dates we published the issue and disclosure inputs, model and tuning values, decision rule, payoff and forecast comparisons and calendar-block interval. The full twenty-month test and the overlapping seven-month subset were chosen at that point. The latter's pilots and follow-up positions were all outside previously scored positions. [Protocol commit](https://github.com/bigpurota/paper11/commit/dc96e5e) · [Position and date audit](pilot-signal-panel.md) · [Results](pilot-signal-ml.md)

The later frequency diagnosis uses only the earlier 48 published books. Before computing new paired endpoints we published the anchored model, a fixed first/26th candidate rule, payoff definitions, missing-principal bounds and four-month holdout. [Protocol commit](https://github.com/bigpurota/paper11/commit/fff202a) · [Results](frequency-test.md)

## Local credibility at a different lender

The Dutch reconstruction is explanatory. The new test of the trust rule at Wells Fargo used one prespecified bank identifier, project states, the fiscal 2010–2019 approval release, and 19 calendar quarters. We published the local, outside-state, hybrid, hard and no-expansion comparisons, both decision cutoffs and the confirmation criterion before examining the new US targets. [Protocol commit](https://github.com/bigpurota/paper11/commit/99db60b) · [Results](local-trust-bank.md)

## Early payment evidence

We fixed the six-month conversion, the secondary three-month marker, the next external bank, two lending thresholds and paired calendar-block comparisons before reading Czech outcomes. The known eight Dutch books motivated the question. [Dated protocol](https://github.com/bigpurota/paper11/commit/e573d37)

## Selection strength, added after the main results

The review of the submitted results found that the simulated approval rule gives every applicant a 5–95% chance. We then added one sensitivity that replaces it with a hard cutoff on the same index and acceptance share, keeping every other choice. It was specified and run after the main results were known and is reported as exploratory. [Design and results](hard-selection.md)

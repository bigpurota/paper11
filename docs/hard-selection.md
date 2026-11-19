# What changes when the historical policy is a hard cutoff?

Status: exploratory sensitivity, added after the main results showed that the simulated approval rule was soft. The prespecified [selection-strength study](selection-strength.md) extends it to a grid of selection strengths and a random audit of rejects.

## Why this check

The main public-cohort design accepts each applicant with probability $0.05+0.90\,\mathrm{expit}(\text{index})$ of pre-outcome features. Every applicant has at least a 5% chance of acceptance, which permits reweighting by the logged probability. In the Monedo study, routine lending left repayment missing for rejects, and a separate randomized holdout provided outcomes for evaluation. A hard cutoff lets us check how the public-cohort result changes when entire ranges of the index lack repayment labels.

## Design

[The sensitivity module](../src/paper11/hard_selection.py) keeps the same index, folds, seeds, scorecards, logistic prior and metrics as [the main experiment](../src/paper11/empirical.py). The applicants with the highest index are accepted. Tied index values stay together on whichever side of the cutoff comes closest to the soft rule’s realized acceptance share. The known acceptance probabilities are exactly 0 or 1, and no index value appears on both sides. The accepted cases all receive unit inverse-probability weight, leaving no information with which to recover the missing outcomes by reweighting.

## Results

The table reports the macOS reference fit. A [second fit on Linux](platform-refit.md) gives the same Taiwan policy profile and a smaller increase in test ABR from BASL.

| Data | Historical policy | Accepted | Bad rate, accepted / rejected | ABR estimation error, pp (accepted-only → Bayesian) | Test ABR (accepted-only → BASL) |
|---|---|---|---|---|---|
| Taiwan | soft | 63.7% | 17.4% / 30.4% | 1.43 → 1.35 | 7.20% → 7.37% |
| Taiwan | hard | 67.3% | 12.2% / 42.4% | 3.27 → 2.33 | 8.53% → 11.50% |
| Prosper | soft | 56.5% | 8.2% / 16.5% | 1.35 → 0.35 | 3.40% → 3.41% |
| Prosper | hard | 56.4% | 6.5% / 18.6% | 1.43 → 0.50 | 3.62% → 3.77% |

| Paired difference at the hard cutoff (95% interval), pp | Taiwan | Prosper |
|---|---|---|
| Bayesian minus accepted-only ABR estimation RMSE | −0.93 [−1.19, −0.66] | −0.93 [−1.31, +0.50] |
| BASL minus accepted-only test ABR | +2.97 [+2.55, +3.33] | +0.14 [−0.09, +0.40] |

These intervals resample borrowers with the models held fixed. Across the four Taiwan folds, each fitted separately, BASL raised the default rate every time, by +2.14, +0.94, +0.97 and +7.83 pp. The fourth fold contributes most of the mean increase.

Ties in the Taiwan index leave its hard rule accepting 3.5 percentage points more applicants than the soft rule did.

## Interpretation

On Taiwan the Bayesian evaluator reduced error more under the hard cutoff than under the soft rule. Its accepts-trained logistic prior assigned 9.6% average risk to validation rejects, against 43.3% observed, and ranked them backwards (AUC 0.41). Accepted-only evaluation computes the approval ranks and bad rates among accepted borrowers. Bayesian evaluation instead ranks the whole validation pool and inserts the prior’s probabilities at missing outcomes. The difference between evaluators therefore combines changed ranks and imputed outcomes. Scoring against the same cohort's fully observed ABR isolates the evaluation error from a change of population. On that target, error fell from 2.74 to 1.80 pp on Taiwan and from 0.93 to almost zero on Prosper.

BASL increased the approved default rate on Taiwan by 2.97 pp on average. Even the guarded variant, which can keep the original scorecard, reached 10.96% ABR. A logistic scorecard trained on accepts had 32.4% integrated test ABR, against 8.5% for XGBoost trained on the same accepts. This makes poor extrapolation one plausible explanation. The reject AUC above measures the fitted L2 evaluation prior, while BASL refits an L1 labeler after each augmentation round. We did not measure the correctness of its individual pseudo-labels. On Prosper the BASL interval included zero.

Two cohorts, one index and one cutoff per cohort are a narrow test. The result changes the reading of the main tables: the null BASL result is not only an artifact of soft selection, while the Bayesian evaluation result becomes stronger once selection is strong.

## Reproduction

From the repository root run `PYTHONPATH=src .venv/bin/python -m paper11.hard_selection --out results --cache data/cache`. It writes [the summary](../results/hard_selection.csv), including the prior's mean and AUC on validation rejects under both designs, and [per-fold training metrics](../results/hard_selection_training.csv). [Tests](../tests/test_hard_selection.py) check that the cutoff separates accepts from rejects on the index and keeps tied values together.

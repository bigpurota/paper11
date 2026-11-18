# What changes when the historical policy is a hard cutoff?

Status: exploratory sensitivity, added after the main results showed that the simulated approval rule was soft.

## Why this check

The main public-cohort design accepts each applicant with probability $0.05+0.90\,\mathrm{expit}(\text{index})$ of pre-outcome features. Every applicant has at least a 5% chance, so the accepted sample covers almost the whole applicant space and logged-propensity reweighting is valid. Monedo's rejects were never observed. A null result for reject inference under soft selection therefore says little about the regime the paper studies.

## Design

[The sensitivity module](../src/paper11/hard_selection.py) keeps the same index, folds, seeds, scorecards, logistic prior and metrics as [the main experiment](../src/paper11/empirical.py). Only the historical decision changes: the applicants with the highest index are accepted. Tied index values stay on one side of the cutoff, and the side is chosen to match the soft rule's realized acceptance share as closely as possible. The known acceptance probabilities become exactly 0 or 1, so no historical reject resembles an accepted case on the index. Reweighting reduces to the accepted-only estimate and is not reported.

## Results

| Data | Historical policy | Accepted | Bad rate, accepted / rejected | ABR estimation error, pp (accepted-only → Bayesian) | Test ABR (accepted-only → BASL) |
|---|---|---|---|---|---|
| Taiwan | soft | 63.7% | 17.4% / 30.4% | 1.43 → 1.35 | 7.20% → 7.37% |
| Taiwan | hard | 67.3% | 12.2% / 42.4% | 3.27 → 2.33 | 8.53% → 11.50% |
| Prosper | soft | 56.5% | 8.2% / 16.5% | 1.35 → 0.35 | 3.40% → 3.41% |
| Prosper | hard | 56.4% | 6.5% / 18.6% | 1.43 → 0.50 | 3.62% → 3.77% |

Paired 95% intervals, conditional on the fitted models:

* Taiwan, Bayesian minus accepted-only ABR estimation error: −0.93 pp [−1.19, −0.66]. BASL minus accepted-only test ABR: +2.97 pp [+2.55, +3.33].

These intervals resample borrowers with the fitted models held fixed. That suits the evaluation contrast, which scores one fixed scorecard, but understates refitting variation in the training contrast. Across the four Taiwan folds, each fitted separately, BASL was worse every time, by +2.14, +0.94, +0.97 and +7.83 pp; the fourth fold drives the mean.
* Prosper, the same contrasts: −0.93 pp [−1.31, +0.50] and +0.14 pp [−0.09, +0.40].

Ties in the Taiwan index leave its hard rule accepting 3.5 percentage points more applicants than the soft rule did.

## Interpretation

Stronger selection makes the accepted-only estimate of a scorecard's bad rate worse, and Bayesian evaluation recovers more of the gap. It does so with a poor prior. On Taiwan's hard-cutoff validation rejects, the accepts-trained logistic prior averages 9.6% against an actual bad rate of 43.3%, and it ranks them backwards (AUC 0.41). Accepted-only evaluation treats the rejects inside a candidate's approval range as if they repaid like the accepts; even an understated prior adds part of their risk. A better prior should recover more. On Taiwan its improvement now excludes zero. On the same cohort, with no change of population, its error falls from 2.74 to 1.80 pp on Taiwan and from 0.93 to almost zero on Prosper. The paper's evaluation idea survives a selection regime closer to its own.

BASL does not. On Taiwan it raises the approved default rate in every fold, by about three percentage points on average, and the guarded variant that may keep the original scorecard still reaches 10.96%. Its pseudo-labels come from a logistic model fitted to the accepts, and the same kind of model ranks Taiwan's hard-cutoff rejects backwards (AUC 0.41; 0.77 under soft selection). BASL labels the rejects with the lowest predicted risk as good, so many of its new "good" labels belong to risky applicants. A logistic scorecard fitted the same way has test ABR 32.4% on the whole Taiwan population, against 8.5% for the accepted-only XGBoost. The diagnostic uses an L2 logistic model rather than BASL's L1 sampler, so it supports the mechanism without isolating it. On Prosper the BASL difference stays within noise.

Two cohorts, one index and one cutoff per cohort are a narrow test. The result changes the reading of the main tables: the null BASL result is not only an artifact of soft selection, while the Bayesian evaluation result becomes stronger once selection is strong.

## Reproduction

From the repository root run `PYTHONPATH=src .venv/bin/python -m paper11.hard_selection --out results --cache data/cache`. It writes [the summary](../results/hard_selection.csv), including the prior's mean and AUC on validation rejects under both designs, and [per-fold training metrics](../results/hard_selection_training.csv). [Tests](../tests/test_hard_selection.py) check that the cutoff separates accepts from rejects on the index and keeps tied values together.

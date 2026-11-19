# When does reject inference work? Selection strength, the reject model and a random audit

Bayesian evaluation uses a model to fill in missing repayment outcomes. BASL uses a separate model to assign pseudo-labels while training its scorecard. We vary the sharpness of simulated historical selection and reveal the outcomes of a random 5% of fitting-split rejects. Each audited outcome receives weight 20 when estimating the evaluation prior. The two audited scorecards learn from the same observed accepts and audited rejects, each with unit weight. [Protocol](selection-strength-protocol.md) · [Code](../src/paper11/selection_strength.py) · [Summary](../results/selection_strength.csv) · [Folds](../results/selection_strength_folds.csv)

## Taiwan

The grid and hypothesis assessments below use the macOS reference fits. The [Linux refit](platform-refit.md) shows which conclusions also hold in a second software environment.

Selection strength $s$ is the slope in $\mathrm{expit}(s(\text{index}-c_s))$. Its intercept targets the main design’s realized acceptance share in expectation. In Taiwan the finite-slope draws accepted 63.35–63.61%. The hard cutoff kept tied applicants together and accepted 67.27%. The original soft rule, reported as `main` in the CSV, accepted 63.73% and had a 5% floor and 95% ceiling. Running that separate reference reproduces the original baseline point estimates. Errors below are root mean squared errors across four folds, in percentage points. Test ABR averages the default rate over approval shares from 20% to 40%.

| | s = 0.5 | 1 | 2 | 4 | hard |
|---|---:|---:|---:|---:|---:|
| Bad rate, accepted / rejected | 19.2 / 27.2% | 16.8 / 31.3% | 14.4 / 35.6% | 13.1 / 37.8% | 12.2 / 42.4% |
| Evaluation error, accepted labels | 1.37 | 1.58 | 1.57 | 2.48 | 3.27 |
| Evaluation error, Bayesian, logistic prior | 1.77 | 1.45 | 1.05 | 1.09 | 2.33 |
| Evaluation error, Bayesian, audited prior | 1.74 | 1.52 | 1.26 | 0.91 | 1.29 |
| Logistic prior on rejects: mean / AUC | 25.3% / 0.77 | 25.7% / 0.77 | 18.5% / 0.70 | 13.1% / 0.40 | 9.6% / 0.41 |
| Audited prior on rejects: mean / AUC | 26.0% / 0.76 | 29.6% / 0.77 | 33.1% / 0.76 | 34.6% / 0.75 | 38.7% / 0.71 |
| Actual reject bad rate (validation) | 27.9% | 32.1% | 36.3% | 38.6% | 43.3% |
| ABR: accepted-only → BASL | 7.31 → 7.22% | 7.28 → 7.25% | 7.15 → 7.14% | 7.97 → 7.98% | 8.53 → 11.50% |
| Test ABR with audit, supervised → BASL | 7.15 → 7.08% | 7.14 → 7.16% | 7.08 → 7.05% | 7.26 → 7.20% | 7.07 → 7.20% |

Paired 95% intervals, borrower bootstrap with the fitted models held fixed; training contrasts also give the range over the four separately fitted folds:

| | s = 0.5 | 1 | 2 | 4 | hard |
|---|---|---|---|---|---|
| Bayesian (logistic) − accepted-only error | +0.40 [−0.52, +1.27] | −0.13 [−0.99, +0.70] | −0.51 [−1.17, +0.18] | −1.40 [−1.69, −0.92] | −0.93 [−1.20, −0.65] |
| Audited − logistic prior, Bayesian error | −0.03 [−0.08, +0.02] | +0.07 [0.00, +0.15] | +0.20 [+0.03, +0.33] | −0.18 [−0.58, +0.38] | −1.04 [−1.57, −0.42] |
| BASL − accepted-only ABR; folds | −0.09; −0.20 to +0.17 | −0.04; −0.19 to +0.39 | −0.01; −0.20 to +0.14 | +0.01; −0.53 to +1.34 | +2.97; +0.94 to +7.83 |
| Audit's change in that BASL gap; folds | +0.02; −0.51 to +0.35 | +0.06; −0.43 to +0.36 | −0.02; −0.29 to +0.13 | −0.07; −1.15 to +0.38 | −2.84; −7.93 to −0.39 |
| Training with the audit, accepted-only ABR | −0.16 [−0.31, +0.01] | −0.15 [−0.31, +0.01] | −0.07 [−0.22, +0.09] | −0.71 [−0.96, −0.46] | −1.45 [−1.74, −1.15] |

## Hypotheses

| Hypothesis | Result |
|---|---|
| H1. Accepted-label evaluation error rises with $s$ | Supported. 1.37 → 3.27 pp on Taiwan with one negligible dip (1.58 → 1.57); 1.20 at $s=0.5$ and 1.43 at the hard cutoff on Prosper. |
| H2. Bayesian evaluation with the logistic prior beats accepted labels at every $s$ on Taiwan, more so at $s=\infty$ than at $s=0.5$ | Not supported. It is worse at $s=0.5$ (1.77 against 1.37). It is better from $s=1$ upward, most clearly at $s=4$. |
| H3. The logistic prior ranks rejects worse as $s$ rises | The overall decline is substantial but has two reversals. In grid order AUC is 0.768, 0.775, 0.705, 0.403 and 0.408. |
| H4. BASL is no better than accepted-only training at every $s$ | The prespecified point-estimate criterion fails. BASL has a slightly lower mean ABR at $s=0.5,1,2$. Each finite-slope interval includes zero. BASL raises mean ABR under the hard cutoff. |
| H5a. The audit raises the prior's AUC on rejects for $s\ge2$ | Supported: 0.70 → 0.76, 0.40 → 0.75 and 0.41 → 0.71. |
| H5b. The audit lowers Bayesian evaluation error for $s\ge2$ | Not supported. It is worse at $s=2$ (+0.20 pp, interval excluding zero), better at $s=4$ (−0.18, uncertain) and clearly better at the hard cutoff (−1.04). |
| H5c. At the hard cutoff the audit shrinks BASL's gap in at least three of four folds | All four folds meet the criterion. The mean gap falls from +2.97 to +0.13 pp. |

## Interpretation

**Selection strength changed which evaluation worked better on Taiwan.** At $s=0.5$, replacing missing outcomes with logistic probabilities increased RMSE from 1.37 to 1.77 points. At $s=4$ it reduced RMSE by 1.40 points and at the hard cutoff by 0.93 points. Under the hard cutoff the accepted-only estimate understated test risk in all four folds, by 1.62–4.21 points.

**Extrapolating from accepts can reverse the ranking.** At $s=4$ and at the hard cutoff, the L2 logistic evaluation prior had AUC near 0.40 on validation rejects. Under the hard cutoff it forecast 9.6% defaults against 43.3% observed there. BASL's internal L1 logistic labeler is refitted after each round. The reported AUC measures the evaluation prior; pseudo-label accuracy was not measured. BASL worsened the scorecard under the hard cutoff and stayed close to the baseline at $s=4$. These two outcomes leave the mechanism open.

**On Taiwan’s hard cutoff, the audit helped evaluation and supervised training.** Revealing 219–224 rejects per fold raised the prior's AUC from 0.41 to 0.71 and its mean risk estimate from 9.6% to 38.7%, against 43.3% observed. Bayesian evaluation error fell from 2.33 to 1.29 points. The supervised scorecard trained on accepts plus audited rejects reduced test ABR by 1.45 points (paired 95% interval 1.15–1.74 lower). Adding BASL to those same labels changed ABR by +0.13 points [−0.07, +0.30]. The audit reduced BASL's gap by 2.84 points [2.44, 3.26]. Funding the audited loans has a cost, which the [pilot analysis](information-value.md) addresses separately.

**Prosper had smaller differences.** On its single chronological holdout, accepted-label error was 1.18–1.43 points. Bayesian evaluation with the logistic prior lowered it to 0.11–0.50 points. All five intervals for the unaudited BASL training gap included zero. At $s=2$, training the scorecard on accepts plus audited rejects lowered its ABR by 0.33 points (paired 95% interval 0.03–0.65 lower). This was the only grid point where that training contrast’s interval excluded zero. These intervals are pointwise across the grid.

## Limits

Both cohorts consist of historically financed borrowers. We impose a simulated decision on them using pre-outcome features. The threshold that matches acceptance uses the entire cohort's index values, including future-period features on Prosper. The chronological holdout therefore tests the scorecard under a retrospective policy simulation. The economic cost of funding audited loans is outside this experiment.

The protocol predates the finite-slope grid and all audited results. Unaudited main and hard-cutoff results on **both** datasets were already available from earlier experiments. Each fold uses one audit draw. The conditional intervals resample borrowers with the fitted models and audit draw held fixed. Fold ranges show how training contrasts vary across four Taiwan fits. Prosper has one chronological split.

In a post-run code audit we found that the audited BASL arm sorted the remaining rejects before random sampling. At a zero audit budget this alone changed the first Taiwan hard-cutoff fold’s ABR from 10.37% to 9.01%. The corrected implementation preserves the fitting-split order. Both arms now give identical individual predictions at zero budget across all four hard-cutoff folds. At the planned 5% budget the corrected residual BASL gap is +0.13 points, compared with +0.31 in the earlier implementation. The [order and prediction check](../tests/test_selection_strength.py) guards this comparison.

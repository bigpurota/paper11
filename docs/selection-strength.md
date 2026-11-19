# When does reject inference work? Selection strength, the reject model and a random audit

Both corrections in Kozodoi et al. rest on a model of the rejected applicants: Bayesian evaluation draws their outcomes from a prior, and BASL assigns them pseudo-labels. This study varies how sharply the historical policy selected, at a fixed acceptance share, and compares the paper's logistic reject model with one that also sees a random 5% audit of training rejects. [Protocol, published before the run](selection-strength-protocol.md) · [Code](../src/paper11/selection_strength.py) · [Summary](../results/selection_strength.csv) · [Folds](../results/selection_strength_folds.csv)

## Taiwan

Selection strength $s$ is the slope of the acceptance probability $\mathrm{expit}(s(\text{index}-c_s))$; "hard" is a deterministic cutoff. The main design's soft rule behaves like $s=1$ and reproduces the main results exactly. Errors are RMSE over four folds in percentage points; ABR is the approved default rate on test borrowers.

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
| ABR with audit: accepted-only → BASL | 7.15 → 7.03% | 7.14 → 7.14% | 7.08 → 7.14% | 7.26 → 7.30% | 7.07 → 7.39% |

Paired 95% intervals, borrower bootstrap with the fitted models held fixed; training contrasts also give the range over the four separately fitted folds:

| | s = 0.5 | 1 | 2 | 4 | hard |
|---|---|---|---|---|---|
| Bayesian (logistic) − accepted-only error | +0.40 [−0.52, +1.27] | −0.13 [−0.99, +0.70] | −0.51 [−1.17, +0.18] | −1.40 [−1.69, −0.92] | −0.93 [−1.20, −0.65] |
| Audited − logistic prior, Bayesian error | −0.03 [−0.08, +0.02] | +0.07 [0.00, +0.15] | +0.20 [+0.03, +0.33] | −0.18 [−0.58, +0.38] | −1.04 [−1.57, −0.42] |
| BASL − accepted-only ABR; folds | −0.09; −0.20 to +0.17 | −0.04; −0.19 to +0.39 | −0.01; −0.20 to +0.14 | +0.01; −0.53 to +1.34 | +2.97; +0.94 to +7.83 |
| Audit's change in that BASL gap; folds | −0.03; −0.44 to +0.22 | +0.04; −0.34 to +0.31 | +0.07; −0.07 to +0.16 | +0.03; −1.25 to +0.54 | −2.66; −7.64 to −0.56 |
| Training with the audit, accepted-only ABR | −0.16 [−0.31, +0.01] | −0.15 [−0.31, +0.01] | −0.07 [−0.22, +0.09] | −0.71 [−0.96, −0.46] | −1.45 [−1.74, −1.15] |

## Hypotheses

| Hypothesis | Result |
|---|---|
| H1. Accepted-label evaluation error rises with $s$ | Supported. 1.37 → 3.27 pp on Taiwan with one negligible dip (1.58 → 1.57); 1.20 at $s=0.5$ and 1.43 at the hard cutoff on Prosper. |
| H2. Bayesian evaluation with the logistic prior beats accepted labels at every $s$ on Taiwan, more so at $s=\infty$ than at $s=0.5$ | Not supported. It is worse at $s=0.5$ (1.77 against 1.37). It is better from $s=1$ upward, most clearly at $s=4$. |
| H3. The logistic prior ranks rejects worse as $s$ rises | Supported in substance, not strictly. Its AUC stays near 0.77 up to $s=1$, falls to 0.70 at $s=2$ and to about 0.40 at $s=4$ and the hard cutoff. |
| H4. BASL is no better than accepted-only training at every $s$ | Not supported. BASL is within noise of the baseline up to $s=4$; it is clearly worse only under the hard cutoff. |
| H5a. The audit raises the prior's AUC on rejects for $s\ge2$ | Supported: 0.70 → 0.76, 0.40 → 0.75 and 0.41 → 0.71. |
| H5b. The audit lowers Bayesian evaluation error for $s\ge2$ | Not supported. It is worse at $s=2$ (+0.20 pp, interval excluding zero), better at $s=4$ (−0.18, uncertain) and clearly better at the hard cutoff (−1.04). |
| H5c. At the hard cutoff the audit shrinks BASL's gap in at least three of four folds | Supported in all four folds; the mean gap falls from +2.97 to +0.31 pp. |

## Interpretation

**Selection strength decides whether evaluation needs correcting.** Under weak selection accepted labels already estimate a scorecard's bad rate well, and a logistic prior adds its own bias. Once rejects differ sharply from accepts, accepted labels understate risk by up to 3.3 points, and Bayesian evaluation removes much of that error.

**The reject model is the bottleneck.** An accepts-trained logistic model ranks rejects reasonably under soft selection and backwards under sharp selection, and it places their risk at a fraction of the truth (9.6% against 43.3% at the hard cutoff). That is when BASL, which labels the apparently safest rejects as good, damages the scorecard. It did not damage it at $s=4$, where the same model also ranked rejects backwards, so a backwards labeler is not sufficient on its own; the deterministic boundary matters too.

**A small random audit repairs the reject model, and its outcomes are worth more than either correction.** Revealing 5% of training rejects (221–247 loans per Taiwan fold) lifts the prior's ranking to 0.71–0.76 and its level close to the truth. Under the hard cutoff, Bayesian evaluation error halves and BASL's damage nearly disappears. Simply training on the audited outcomes lowers the approved default rate by 1.45 points, more than any reject-inference method achieves. Funding those loans costs money; whether that cost is repaid is the [pilot question](information-value.md).

**Prosper shows the same direction with weaker selection effects.** Its accepted-label error barely changes with $s$ (1.18–1.43 pp), Bayesian evaluation with the logistic prior lowers it to 0.11–0.50 pp at every strength, and neither BASL nor the audit moves the default rate beyond noise.

## Limits

Two cohorts, one selection index and one audit size. Intervals hold fitted models fixed; the fold ranges show that training contrasts vary widely across refits. Prosper has a single chronological split. The audit's cost is not priced here. The protocol was written after the hard-cutoff result with the logistic model was known; the other cells were run afterwards.

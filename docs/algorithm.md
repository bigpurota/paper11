# Reimplementing Kozodoi et al.

The assigned manuscript is the July 2024 preprint. Section 4 and Algorithm 1 describe evaluation with unknown outcomes. Sections 5.1–5.4 and Algorithms B.1–B.3 describe bias-aware self-learning (BASL). Tables E.8–E.9 report the model settings. The implementation uses these descriptions and general-purpose learners in scikit-learn and XGBoost. [Assigned version with appendices](https://arxiv.org/pdf/2407.13009v1)

## Two different uses of a rejected applicant

| Stage | Input available to the method | Treatment of each reject | Output |
|---|---|---|---|
| BASL training | Accepted training features and repayments, rejected training features, separate early-stopping set | Label only selected, high-confidence training examples 0 or 1 | A scorecard that predicts a probability of default (PD) |
| Bayesian evaluation | Fixed candidate PDs, observed accepted outcomes, prior PDs for rejected cases | Draw a separate Bernoulli outcome for every missing label in each repetition | Estimated population performance of the fixed candidate |
| Test audit in this replication | Fully observed outcomes from the public credit cohort or simulation | Reveal them only to the audit code | Actual holdout performance and error of its estimate |

A score is always the probability of default. A label of 1 means default. The prior is a forecast about a missing label and must be constructed without access to that person's eventual outcome. A prior that copies the candidate's own predictions can make that candidate look well calibrated by construction.

## Training

1. Fit the baseline XGBoost on accepted loans. Record it as the reference at round zero. It uses 100 trees, depth 3, learning rate 0.1, 80% row and feature subsampling (Table E.8 synthetic column). Using these settings on public data fixes the computational budget across training methods. The paper fitted up to 10,000 trees with early stopping on its proprietary data.
2. Fit the isolation forest on accepted training **features only**. Score the rejected training rows with that forest and retain rows inside the specified similarity quantiles of the rejected pool. Higher scores mean greater similarity. The framework permits filtering both ends. The selected parameter values in the paper keep the upper end.
3. Sample a fraction of the available pool without replacement and fit a standardized L1 logistic regression to the currently labeled training rows. At the first iteration save the PD quantiles at γ and 1−γθ of this sample. In every iteration label cases below the fixed lower cutoff as 0 and above the fixed upper cutoff as 1. Omit exact ties at the cutoff. θ=2 makes the high-risk tail twice as large by design in the first continuous-score sample. Class counts can differ thereafter.
4. Permanently remove the newly labeled rows from the pool and add them to the accepted training data with their inferred labels. Refit XGBoost with the same settings and seed. Compare its approval-range average bad rate (ABR) to the current best on an independent stopping set. Observe repayment only for previously accepted validation cases and use the supplied reject priors for the others.
5. Stop at the first non-improvement, on exhaustion of usable cases, or at the specified cap. Algorithm B.3 starts with an empty candidate list, so the first augmented candidate is eligible even if its validation ABR exceeds the baseline. From round two onward, return the lowest-validation-ABR augmented model. If no augmentation is possible, fall back to the baseline. The conservative variant, `allow_round_zero=True`, also makes the baseline eligible. A history records how many good/bad labels were added and whether a later proposal was rejected.

| Parameter | Synthetic protocol | Public-data protocol |
|---|---:|---:|
| Filtering quantiles β | 0.05 to 1.00 | 0.01 to 1.00 |
| Sampling fraction ρ | 0.80 | 0.30 |
| Good tail γ | 0.01 | 0.01 |
| Imbalance θ | 2 | 2 |
| Maximum rounds | 3 | 5 |

The stopping metric is our declared choice within the paper's general Bayesian stopping framework. For fixed scores, the (integrated) ABR is linear in the outcomes. Replacing each missing outcome by its prior PD gives the **exact** Bayesian expected ABR, avoiding a random difference between candidates. For AUC, replacing binary outcomes by fractional labels does not implement Algorithm 1.

## Evaluation

Let a target approval fraction be q. Rank candidate borrowers from lowest to highest PD and approve the lowest q fraction of the weighted population. At a tied score straddling the boundary, use the same fractional inclusion probability for each member of the tie. This estimates random tie-breaking and makes results invariant to input row order. ABR(q) is the expected number of bad loans issued divided by the mass of loans issued.

| Metric | Computation | Preferred direction |
|---|---|---|
| AUC | Probability a default receives a higher PD than a repayment, with half credit for ties | Higher |
| Brier | Mean squared error of PD against the realized 0/1 outcome | Lower |
| Partial AUC | ROC restricted to the fraction of defaulters approved (FNR) from 0 to 0.2. Standardized so a random ranking scores 0.5 and a perfect ranking scores 1 | Higher |
| ABR | Uniform average of ABR(q) over q from 0.2 to 0.4 | Lower |

For partial AUC, ranking good borrowers by 1−PD exchanges the class labels and converts the specified FNR limit into an FPR limit for the conventional partial AUC calculation. The implementation integrates linear segments between tied-score groups, truncates at 0.2 and applies the McClish standardization. The tests compare it against scikit-learn's independent implementation with the classes reversed. Applying the FPR limit directly to defaults evaluates a different region of the ROC curve.

For the integrated ABR, a score group occupying cumulative probability [l,h] is partially selected at q in [l,h]. Its inclusion fraction is (q−l)/(h−l). Integrating that fraction divided by q yields a closed-form weight for the group's share of defaults. The tests compare the result with numerical quadrature and a hand-computed example.

For general Bayesian evaluation, generate independent Bernoulli(prior PD) labels for missing outcomes, merge with the observed outcomes and calculate all four metrics. Repeat and average the metric values. The convergence check uses the absolute change of **every** running metric mean, a minimum number of draws and a hard maximum. Setting tolerance to zero fixes the draw budget. For a deterministic prior the integral reduces to one evaluation. AUC and partial AUC are undefined in a one-class realization and are averaged over defined draws. The number of draws controls simulation error conditional on a prior. Uncertainty about the prior itself requires separate experiments.

## Benchmarks and assumptions

The accepted-only and hard-cutoff scorecards use the same XGBoost architecture. Hard cutoff labels every training reject using the accepted model's PD at a 0.5 threshold and retrains on the union. Training IPW gives each accepted case weight proportional to the reciprocal of its supplied historical acceptance probability, floors that probability at 0.05 by default, then scales weights to mean one. For nonrandom missingness conditional on the model inputs, weighting may leave selection bias. With deterministic rejections in a covariate region, no observed outcome in that region can identify its default rate through weighting alone. Clipping limits variance and can introduce bias. This IPW comparator differs from the paper's selected cluster-density-ratio benchmark.

Examples and tests are in [methods.py](../src/paper11/methods.py) and [test_methods.py](../tests/test_methods.py).

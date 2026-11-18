# Protocol: selection strength, the reject model and a random audit

Status: fixed and published before the study below was run on the public cohorts. One point of the design is already known: under a hard cutoff on Taiwan, with the logistic reject model, Bayesian evaluation helped and BASL hurt ([hard-cutoff check](hard-selection.md)). Every other cell is new.

## Question

Kozodoi et al. correct sampling bias with a model of the rejected applicants: Bayesian evaluation needs a prior for their outcomes, and BASL needs a labeler to assign them pseudo-labels. When does that reject model work, and can a small random audit of rejects, a scaled-down version of the paper's randomized holdout, repair it?

## Design

* **Cohorts and splits.** Taiwan with its four borrower folds and Prosper with its chronological split, exactly as in the [main experiment](../src/paper11/empirical.py). Seeds 701 + fold.
* **Selection strength.** The historical acceptance probability is $\mathrm{expit}(s\,(\text{index}-c_s))$ on the main design's index, with $c_s$ set so the expected acceptance share equals the main design's realized share. $s\in\{0.5,1,2,4\}$, plus the hard cutoff of the earlier check ($s=\infty$) and the main soft rule itself as a reference. Acceptance draws reuse the main design's uniform numbers, so designs differ only through $s$.
* **Reject models.** *Logistic*: the accepts-trained logistic prior of the main experiment, which is also BASL's labeler. *Audited*: a random 5% of the fitting split's rejects have their outcomes revealed. The prior is then a logistic model trained on accepts plus audited rejects, each audited case weighted by 20. BASL starts from accepts plus audited rejects and uses this prior for stopping.
* **Scorecards.** Accepted-only XGBoost (A); BASL with the logistic reject model (B); XGBoost on accepts plus audit (A+); BASL with the audited reject model (B+). Settings as in the main experiment.
* **Evaluation.** The candidate A is evaluated on the validation split by accepted labels, Bayesian evaluation with the logistic prior and Bayesian evaluation with the audited prior. Errors are measured against A's integrated ABR on the test borrowers and, separately, against the validation truth.

## Outcomes

1. RMSE across folds of each ABR estimate, in percentage points.
2. Training gaps B − A and B+ − A+ in test integrated ABR, per fold and averaged, and A+ − A.
3. On validation rejects, each prior's mean against the actual bad rate, and its AUC.
4. Borrower-bootstrap 95% intervals (499 draws, models held fixed) for the evaluation contrasts and the training gaps. Training contrasts are also reported fold by fold, because refitting variation is not in these intervals.

## Hypotheses and criteria

* **H1.** Accepted-only evaluation error rises with $s$: on Taiwan the RMSE at $s=\infty$ exceeds that at $s=0.5$, with at most one decrease along the grid; on Prosper the $s=\infty$ value exceeds the $s=0.5$ value.
* **H2.** With the logistic prior, Bayesian evaluation has lower RMSE than accepted labels at every $s$ on Taiwan, and the difference at $s=\infty$ exceeds that at $s=0.5$.
* **H3.** The logistic prior's AUC on validation rejects falls as $s$ rises on Taiwan.
* **H4.** B − A is nonnegative in the Taiwan fold mean at every $s$.
* **H5, primary.** For $s\ge 2$ on Taiwan, the audit (a) raises the prior's AUC on validation rejects, (b) lowers Bayesian evaluation RMSE relative to the logistic prior, and (c) at $s=\infty$ makes B+ − A+ smaller than B − A in at least three of four folds. Prosper is reported as a second cohort without a separate criterion.

All cells are reported whether or not they support a hypothesis. The audit is priced only through its information; funding 5% of rejects would cost money, which the [pilot analysis](information-value.md) addresses separately.

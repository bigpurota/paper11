# Which selection results survive a second software environment?

The selection experiment was fitted twice, on Apple Silicon macOS and Linux x86-64. Both runs used the same source data, borrower splits, RNG seeds, model settings and pinned statistical packages. The borrowers and repayment outcomes are identical, so this tests sensitivity to the software environment. The original finite-slope grid and 5% training audit were prespecified. The platform comparison was added after a Linux reproduction check detected different estimates. [Protocol](selection-strength-protocol.md) · [macOS estimates](../results/selection_strength.csv) · [Linux estimates](refits/linux-x86_64/selection_strength.csv) · [Linux refit run and full tables](https://github.com/bigpurota/paper11/actions/runs/44525809986)

## What survived refitting

Under the hard cutoff on Taiwan, revealing a random 5% of training rejects helped both the bank’s risk evaluation and its supervised scorecard. Adding BASL after the audit gave a small difference whose 95% interval included zero on both platforms.

| Taiwan hard cutoff, difference in percentage points [paired 95% interval] | macOS | Linux |
|---|---:|---:|
| Evaluation RMSE, Bayesian logistic prior minus accepted labels | −0.93 [−1.20, −0.65] | −1.10 [−1.39, −0.81] |
| Evaluation RMSE, audited prior minus unaudited prior | −1.04 [−1.57, −0.42] | −1.26 [−1.70, −0.55] |
| Test ABR, BASL minus supervised, before audit | +2.97 [+2.59, +3.37] | +0.96 [+0.70, +1.19] |
| Test ABR, BASL minus supervised, after audit | +0.13 [−0.07, +0.30] | +0.14 [−0.05, +0.36] |
| Test ABR, supervised training with audit minus without audit | −1.45 [−1.74, −1.15] | −1.57 [−1.85, −1.22] |
| Change in BASL’s gap after audit | −2.84 [−3.26, −2.44] | −0.81 [−1.11, −0.50] |

The acceptance-error criterion (H1) held in both environments. Bayesian evaluation with the unaudited logistic prior lost to accepted-only evaluation at the weakest slope on both, so H2 failed. The prior’s reject AUC fell overall but had two small reversals on both grids (H3). Each platform also had finite slopes where the average test ABR of BASL was lower than supervised training, contrary to H4’s point-estimate criterion.

The audit increased the evaluation prior’s reject AUC at all three prespecified strengths ($s=2$, $s=4$, and hard) in both fits, meeting H5a. H5b required a lower Bayesian evaluation RMSE at all three strengths. At $s=2$ the audit raised error by 0.20 points on macOS and 0.23 on Linux, so both fits missed that criterion. H5c required the audit to reduce BASL’s hard-cutoff gap in at least three of four folds. It did so in four folds on macOS and three on Linux. Before the audit, BASL itself raised Taiwan’s hard-cutoff test ABR in four folds on macOS and three on Linux. Its increase of 7.83 points in the fourth macOS fold was 1.69 points on Linux.

Under Taiwan’s original soft mask, Bayesian evaluation changed RMSE by −0.08 points on macOS and +0.20 on Linux. Both intervals included zero. On the Prosper chronological holdout, Bayesian evaluation lowered the point estimate on both platforms, from 1.35 to 0.35 points and from 1.18 to 0.24, respectively. Both intervals also included zero. Prosper’s isolated training benefit from auditing at $s=2$ on macOS did not recur on Linux. On Linux the supervised audit benefit instead excluded zero at the hard cutoff.

At the primary 50% loss-given-default assumption, accepted-only, Bayesian and inverse-probability evaluation all picked the same lending cutoff within each of the five soft-policy folds, on both platforms. Their realised incremental profit was zero there. At 75% loss given default, the Bayesian rule issued fewer loans than accepted-only in three Taiwan folds on macOS and in all four on Linux. Two of those Linux folds earned a higher scenario margin per applicant and two earned less. [macOS policy decisions](../results/policy.csv) · [Linux policy decisions](refits/linux-x86_64/policy.csv)

## Where the estimates diverge

The policy masks agree on the acceptance shares and observed bad rates. Under Taiwan's hard policy, 67.27% of borrowers are accepted, with 12.24% defaults among accepts and 42.42% among rejects on both platforms. The accepts-trained logistic prior forecasts 9.59% on validation rejects against 43.33% observed. Its AUC rounds to 0.41 on both. Under Prosper’s hard policy, the integrated test ABR of a supervised logistic scorecard is 3.8642% on each platform.

The supervised XGBoost scorecard already diverges before BASL runs. With Prosper’s hard cutoff it gives 3.62% test ABR on macOS and 3.72% on Linux. BASL begins from such a scorecard and uses validation performance to select an augmentation round. [macOS hard cutoff](../results/hard_selection.csv) · [Linux hard cutoff](refits/linux-x86_64/hard_selection.csv)

The paper’s XGBoost configuration samples 80% of rows and 80% of features per tree. XGBoost 2.1.4 delegates CPU feature sampling to the C++ standard library’s `std::shuffle`. LLVM libc++ and GNU libstdc++ implement different shuffles. A controlled check on one machine compiled the same 19-feature draw with both libraries. With `mt19937(702)`, the engines gave the same first raw integer, but four of the fifteen retained features differed. This demonstrates how two seeded builds can select different tree inputs. The check does not attribute every fitted-tree difference to this operation. Rounding of nearly tied logistic scores can also affect the last digits of AUC. [Project settings](../src/paper11/methods.py) · [XGBoost feature sampler](https://github.com/dmlc/xgboost/blob/v2.1.4/src/common/random.cc#L29-L50) · [LLVM shuffle](https://github.com/llvm/llvm-project/blob/llvmorg-17.0.6/libcxx/include/__algorithm/shuffle.h#L129-L149) · [GNU shuffle](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13.2.0/libstdc%2B%2B-v3/include/bits/stl_algo.h#L3540-L3577)

## What the intervals cover

Test ABR averages the default rate among the lowest-risk borrowers at approval shares from 20% to 40%. Gaps are measured in percentage points. Within each environment a paired borrower bootstrap gives a pointwise 95% interval, holding that platform’s fitted models and audit draw fixed. The four Taiwan fits also show how the effects vary across folds. Neither comparison treats the two environments as independent samples for a pooled confidence interval. [macOS fold results](../results/selection_strength_folds.csv) · [Linux fold results](refits/linux-x86_64/selection_strength_folds.csv)

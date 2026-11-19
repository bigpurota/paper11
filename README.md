# Fighting Sampling Bias in Credit Scoring

HSE DSBA Research Seminar · Team 12 · Round 3 · Paper 11

Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox

A bank observes repayment only for the loans it approves, yet its scorecard must rank every applicant. Kozodoi et al. propose bias-aware self-learning (BASL) to train on rejected applications and Bayesian evaluation to measure a scorecard on the full applicant mix. We reimplement both, test them on public data and ask which missing outcomes are worth learning. [Assigned paper and appendix](https://arxiv.org/abs/2407.13009v1) · [Journal article](https://www.sciencedirect.com/science/article/pii/S0377221725000839)

[Defense PowerPoint](slides/paper11.pptx) · [PDF](slides/paper11.pdf) · [Research report](results/report.md) · [Contributions and methods](docs/contributions.md) · [All documents](docs/README.md)

## In short

The figures below come from the macOS arm64 release fit. Repeating the Taiwan hard-cutoff fit on Linux x86-64 reduced BASL’s unaudited penalty from 2.97 to 0.96 points. With the 5% audit the residual gap was 0.13 on macOS and 0.14 on Linux. Under the original soft rule, the small change in Taiwan evaluation error reversed sign across platforms. [Paired estimates, intervals and refit details](docs/platform-refit.md)

* **The simulation replicates.** Bayesian evaluation cuts the error in estimating the approved bad rate from 24.33 to 7.71 percentage points (paper: 20.10 to 9.29). BASL recovers 29.6% of the gap to full-label training, with a 95% interval of 21.2–37.3% that contains the paper's 24.8%.
* **Historical selection changes the value of Bayesian evaluation.** In Taiwan, accepted labels alone give an estimation error of 1.37 percentage points under weak selection and 3.27 under a hard cutoff. At slope 4 the Bayesian correction reduces error by 1.40 points (paired 95% interval 0.92–1.69). The finite slopes target the same expected approval rate. Keeping tied scores together at the hard cutoff raises actual approvals from 63.7% to 67.3%. [Selection grid](docs/selection-strength.md)
* **On Taiwan, real repayment labels help where pseudo-labels hurt.** Under the hard cutoff the evaluation prior predicts 9.6% defaults among validation rejects, who actually default at 43.3%. Revealing the outcomes of a random 5% of training rejects raises that prior’s AUC from 0.41 to 0.71 and cuts evaluation error from 2.33 to 1.29 points. Adding those labels to ordinary scorecard training lowers the approved default rate by 1.45 points (95% interval 1.15–1.74). Without the audit, BASL raises it in all four folds, by 0.94–7.83 points. [Paired comparisons](docs/selection-strength.md)
* **An audit is lending to learn.** It pays only through the later decisions its outcomes change: in our example after three later loans if risk persists, never if risk resets 10% of the time. And only borrowers between the cutoffs being compared decide a policy: their totals identify all 50 policy differences, totals by risk decile none.

The paper's randomized Monedo holdout is private. Our Taiwan and Prosper tests hide outcomes of loans that were funded, under a simulated historical policy, so every estimate can be checked against the truth.

## Replication

| Quantity | Paper | Ours |
|---|---:|---:|
| Simulation: error in the estimated approved bad rate, accepted-only → Bayesian | 20.10 → 9.29 pp | 24.33 → 7.71 pp |
| Simulation: share of the full-label gap recovered by BASL | 24.82% | 29.61% [21.22%, 37.28%] |
| Real data: same error, accepted-only → Bayesian | Monedo 3.56 → 1.30 pp | Taiwan 1.43 → 1.35 pp (soft), 3.27 → 2.33 pp (hard cutoff); Prosper 1.35 → 0.35 pp (soft), 1.43 → 0.50 pp (hard) |
| Real data: approved bad rate, accepted-only → BASL | Monedo 23.88% → 22.11% | Taiwan 7.20% → 7.37% (soft), 8.53% → 11.50% (hard); Prosper 3.40% → 3.41% (soft), 3.62% → 3.77% (hard) |
| Profit from choosing the cutoff by Bayesian evaluation | +$29.27 per $375 loan at 50% LGD | No difference at 50% LGD: every evaluator chose the same cutoff |

"Soft" gives every applicant a 5–95% chance of approval; "hard" accepts by a cutoff on the same index. Errors are root mean squared errors in percentage points (pp).

![Published and reproduced Figure 2](results/simulation_fig2.png)

[Simulation](docs/simulation.md) · [Implementation](docs/algorithm.md) · [Selection strength](docs/selection-strength.md) · [Deviations from the paper](docs/deviations.md)

## Extensions

Each extension applies a standard tool to the lending decision and tests it on dated data; the [contributions page](docs/contributions.md) names the tools and their sources.

* [Selection strength and a random audit](docs/selection-strength.md), with its [protocol](docs/selection-strength-protocol.md) and the earlier [hard-cutoff check](docs/hard-selection.md).
* [When one pilot loan pays for its information](docs/information-value.md) and [whether such pilots can be picked in advance](docs/pilot-holdout.md).
* [Which outcomes identify a policy comparison](docs/policy-information.md), [opposite decisions under identical totals](docs/identification.md) and [how many outcomes an audit needs](docs/decision-audit.md).
* Pooled rates were hard to beat: [early defaults as a warning](docs/early-warning.md), [local versus pooled rates](docs/local-trust.md) and [why a historical rate beat boosting](docs/frequency_diagnosis.md). Half of the correct Dutch warnings came from offsetting errors, and the rate from other regions matched or beat the refinements at the base margins.

## Reproduce

Python 3.12 and GNU Make. A CPU is sufficient. Downloading source data requires internet access. On macOS, install the OpenMP runtime if XGBoost needs it (`brew install libomp`).

```sh
git clone https://github.com/bigpurota/paper11.git
cd paper11
make all          # fetch verified sources and regenerate estimates, figures and report
make verify       # run reference, leakage and numerical checks on the submitted results
make reproduce    # rerun into an empty directory and compare each research artifact
make slides       # refresh PPTX and PDF using LibreOffice; the finished files are included
```

The submitted tables use the macOS arm64 fit. On another platform, use `make all OUT=.build/refit` followed by `make reproduce OUT=.build/refit` for a within-platform repeat. Linux CI also checks the selection tables and lending decisions against an independently archived Linux refit. [Platform details](docs/platform-refit.md)

Eleven fingerprinted source files total about 1.143 GB (decimal) in the ignored `data/cache/`. Use `PYTHON=/path/to/python3.12` for a differently named interpreter. [Dataset catalog](docs/sources.md) · [Analysis plan](docs/analysis-plan.md) · [Verification and CI](docs/verification.md)

Team 12 implemented the replication and its extensions with assistance from Codex and Claude. Kozodoi and coauthors developed the original methods and conducted the Monedo study.

# Fighting Sampling Bias in Credit Scoring

HSE DSBA Research Seminar · Team 12 · Round 3 · Paper 11

Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox

A bank observes repayment only for the loans it approves, yet its scorecard must rank every applicant. Kozodoi et al. propose bias-aware self-learning (BASL) to train on rejected applications and Bayesian evaluation to measure a scorecard on the full applicant mix. We reimplement both, test them on public data and ask which missing outcomes are worth learning. [Assigned paper and appendix](https://arxiv.org/abs/2407.13009v1) · [Journal article](https://www.sciencedirect.com/science/article/pii/S0377221725000839)

[Defense PowerPoint](slides/paper11.pptx) · [PDF](slides/paper11.pdf) · [Research report](results/report.md) · [Contributions and methods](docs/contributions.md) · [All documents](docs/README.md)

## In short

* **The simulation replicates.** Bayesian evaluation cuts the error in estimating the approved bad rate from 24.33 to 7.71 percentage points (paper: 20.10 to 9.29). BASL recovers 29.6% of the gap to full-label training, with a 95% interval of 21.2–37.3% that contains the paper's 24.8%.
* **On public data the evaluation idea holds and the training idea does not.** With a hard historical cutoff, Bayesian evaluation lowers Taiwan's error by 0.93 points (95% interval 0.66 to 1.19). BASL never lowered defaults, and under the hard cutoff it raised Taiwan's in all four folds, by 2.97 points on average.
* **Only outcomes that can change a decision matter.** Two approval cutoffs differ only on the borrowers between them. Outcome totals for those bands identify all 50 policy differences on our cohorts; totals by risk decile identify none.
* **A loss-making pilot loan pays only through later decisions.** In our example it pays back after three later loans if risk persists and never if risk resets 10% of the time. A rule chosen in advance missed the only later recovery.
* **Simple pooled rates are hard to beat.** Early defaults changed lending decisions in Dutch and Czech replays, but at the base margins the rate from other regions earned as much or more in both, and half of the correct Dutch warnings came from offsetting errors.

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

[Simulation](docs/simulation.md) · [Implementation](docs/algorithm.md) · [Hard-cutoff sensitivity](docs/hard-selection.md) · [Deviations from the paper](docs/deviations.md)

## Extensions

Each extension applies a standard tool to the lending decision and tests it on dated data; the [contributions page](docs/contributions.md) names the tools and their sources.

* [Which outcomes identify a policy comparison](docs/policy-information.md), [opposite decisions under identical totals](docs/identification.md) and [how many outcomes an audit needs](docs/decision-audit.md).
* [When one pilot loan pays for its information](docs/information-value.md) and [whether such pilots can be picked in advance](docs/pilot-holdout.md).
* [Early defaults as a warning](docs/early-warning.md), [local versus pooled rates](docs/local-trust.md) and [why a historical rate beat boosting](docs/frequency_diagnosis.md).

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

Eleven fingerprinted source files total about 1.143 GB (decimal) in the ignored `data/cache/`. Use `PYTHON=/path/to/python3.12` for a differently named interpreter. [Dataset catalog](docs/sources.md) · [Analysis plan](docs/analysis-plan.md) · [Verification and CI](docs/verification.md)

Team 12 implemented the replication and its extensions with Codex assistance. Kozodoi and coauthors developed the original methods and conducted the Monedo study.

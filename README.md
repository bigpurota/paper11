# Fighting Sampling Bias in Credit Scoring

HSE DSBA Research Seminar · Team 12 · Round 3 · Paper 11

Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox

A bank learns how people repay the loans it approves. How well can it then score *all* applicants? We implement the training and evaluation methods in Kozodoi et al., compare them with the assigned paper, and ask when issuing a loan to observe its outcome can pay for itself. [Assigned paper and appendix](https://arxiv.org/abs/2407.13009v1) · [Journal article](https://www.sciencedirect.com/science/article/pii/S0377221725000839)

[Defense PowerPoint with clickable Q&A](slides/paper11.pptx) · [Projection PDF](slides/paper11.pdf) · [Full evidence reference](slides/evidence.pdf) · [Research report](results/report.md) · [Team contributions and assessment](docs/contributions.md)

The first ten slides cover the talk in about 10¼ minutes, ending with a one-slide summary. At the end, open **slide 11** to jump to any of the sixteen backup pages and return to the menu with one click.

## Replicating the paper

| Experiment | Published result | Our result |
|---|---:|---:|
| Simulation, error estimating the average bad rate among low-risk approvals (accepted-only → Bayesian) | 0.2010 → 0.0929 | 0.2433 → 0.0771 |
| Simulation, share of the full-label training gap recovered by bias-aware self-learning (BASL) | 24.82% | 29.61% [21.22%, 37.28%] |
| Empirical bad-rate estimation error (accepted-only → Bayesian) | 0.0356 → 0.0130 on Monedo | 0.01434 → 0.01350 on Taiwan; 0.01351 → 0.00354 on Prosper |
| Margin from choosing the approval cutoff by Bayesian evaluation | Authors report +$29.27 per $375 loan at 50% loss given default | Zero difference at base pricing in both public cohorts. Each method chose the same cutoff. |

Our simulation reproduces the direction of the training and evaluation results. On Taiwan, BASL increases the default rate integrated over the lowest-risk 20–40% of applicants by 0.165 percentage points relative to accepted-only training (conditional 95% interval +0.018 to +0.300). The Prosper training difference is close to zero. On both cohorts Bayesian evaluation has a smaller point error, but the paired intervals for improvement include zero. The published Spanish randomized holdout is private. Our Taiwan and Prosper comparisons hide and then reveal outcomes of previously financed accounts. [Four-metric comparison](results/paper_comparison.csv) · [Simulation design and departures](docs/simulation.md) · [Prior, masking and implementation](docs/algorithm.md)

![Published and reproduced Figure 2](results/simulation_fig2.png)

## Three findings beyond the paper

| What does a bank need to learn? | Result |
|---|---|
| **Which missing outcomes can change the policy?** | For five nested approval cutoffs the four margin totals between adjacent cutoffs determine all ten comparisons. Concentrating a repayment audit on borrowers whose treatment would change reduces the number of labels needed. [Derivation](docs/policy-information.md) · [Sequential audit](docs/decision-audit.md) |
| **When is a loss-making pilot worth funding?** | The expected gain from later decisions changed by the pilot must cover its loss today, after allowing for information the bank obtains anyway. Two Estonian loans passed this test in a retrospective replay. The revised selector missed the only recovery in the later Bondora test. [Break-even condition](docs/information-value.md) · [Transfer and limits](docs/pilot-holdout.md) |
| **Can new payment information correct a stale risk estimate?** | Six-month defaults lowered the Dutch forecast from 27.19% to 7.17%. The later target realized 4.79% default exposure; the younger cohorts supplying the early signal eventually had 14.11% defaults by count. On a prespecified test at a Czech bank, the rule changed 16 of 143 decisions at the 18.18% cutoff relative to local history. The rate from other regions had lower forecast error and higher modeled payoff. [Advance warning condition](docs/early-warning.md) · [External test](docs/early-czech.md) |

[Detailed evidence across lenders](docs/extension-results.md) · [Figures, scenario margins and sensitivities](results/report.md)

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

Eleven fingerprinted source files total about 1.143 GB (decimal) in the ignored `data/cache/`. Use `PYTHON=/path/to/python3.12` for a differently named interpreter. The results directory contains aggregate research outputs, including paired episode-level receipts. [Dataset catalog](docs/sources.md) · [Analysis plan](docs/analysis-plan.md) · [Deviations](docs/deviations.md) · [Verification and CI](docs/verification.md)

Team 12 implemented the replication and its extensions with Codex assistance. Kozodoi and coauthors developed the original methods and conducted the Monedo study.

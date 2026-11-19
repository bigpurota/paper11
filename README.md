# Fighting Sampling Bias in Credit Scoring

A bank sees who repays only after it lends. How well can it judge a rule that would approve people it previously turned away? We replicate two methods for handling these missing outcomes and test when a lender gains from observing a real repayment.

**[Presentation · 14 slides](slides/talk.pdf)** · [Slides with Q&A](slides/paper11.pdf) · [Research report](results/report.md) · [Original paper](https://arxiv.org/abs/2407.13009v1)

*HSE DSBA Research Seminar · Team 12*<br>
Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox

## Replication

Kozodoi et al. use repayment estimates in two ways. **Bayesian evaluation** measures the default rate of a fixed scorecard. **Bias-aware self-learning (BASL)** assigns provisional labels to selected rejects and trains a new scorecard. Each arrow below starts with the baseline that uses only observed approvals. [Methods](docs/algorithm.md)

| Outcome at 20–40% approval | Monedo · paper | Taiwan | Prosper · later borrowers |
|:---|---:|---:|---:|
| Evaluation error with Bayesian evaluation¹ | 3.56 → 1.30 | 1.43 → 1.35 | 1.35 → 0.35 |
| Default rate after training with BASL | 23.88% → 22.11% | 7.20% → 7.37% | 3.40% → 3.41% |

¹ Root mean squared error in percentage points. Public-cohort estimates use the macOS fit. [Table values](results/paper_comparison.csv) · [Platform sensitivity](docs/platform-refit.md)

Monedo supplied the paper’s private randomized benchmark. On Taiwan and Prosper, we simulated the old approval rule and hid some known outcomes. This let us check each estimate against actual repayments. **BASL lowered defaults at Monedo. The ordinary scorecard had a slightly lower average default rate on both public cohorts.**

![Published results above and replication below. The left panels evaluate a fixed scorecard, and the right panels compare training methods.](results/simulation_fig2.png)

*Figure 2.* Bayesian evaluation reduced simulation error from **24.33 to 7.71 percentage points** in our runs and from 20.10 to 9.29 in the paper. BASL recovered **29.6%** of the gap to training with all outcomes visible, compared with 24.8% in the paper. [Simulation design and intervals](docs/simulation.md)

## Which repayments are worth observing?

**Random audit.** Under Taiwan’s hard cutoff, revealing outcomes for a random 5% of training rejects lowered the ordinary scorecard’s default rate by 1.45 percentage points on macOS and 1.57 on Linux. Adding BASL after the audit changed the rate by +0.13 and +0.14 points. Both 95% intervals include zero for this extra step. [Paired results](docs/platform-refit.md)

**Pilot lending.** Before issuing a pilot, the bank can compare its expected loss and costs with the discounted gain from later decisions its repayment might change. In an Estonian replay, an October 2018 pilot lost €267 but would have prevented €16,211 in later losses. A February 2019 pilot lost €8,672 overall under the same rule. These are hypothetical decisions applied to recorded cash flows. [Break-even condition](docs/information-value.md) · [Estonian cases](docs/pilot-profiles.md)

**Later test.** Across 12 later Bondora portfolios, routine risk updates changed one lending decision. Observing the pilot’s own repayment changed none. [Test results](docs/frequency-test.md) · [Experiments across lenders](docs/README.md)

## Reproduce

From the repository root, use Python 3.12 and GNU Make.

```sh
make verify                # Check the code and saved results
make all OUT=.build/refit  # Recompute from public data in a separate directory
```

[Data sources](docs/sources.md) · [Verification and setup](docs/verification.md) · [Research contributions](docs/contributions.md)

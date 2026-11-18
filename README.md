# Fighting Sampling Bias in Credit Scoring

**Andrey Tsember — implementation and computational experiments**

HSE DSBA Research Seminar · Team 12 · Round 3 · Paper 11

Team 12: **Andrey Tsember**, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox.

We independently implement the central methods in [Kozodoi et al., assigned preprint and appendix](https://arxiv.org/abs/2407.13009v1), published in [European Journal of Operational Research](https://www.sciencedirect.com/science/article/pii/S0377221725000839). When a lender observes repayment only after approving an application, how well can it train a scorecard and measure risk among all applicants?

[Presentation (PDF)](slides/paper11.pdf) · [Editable slides and speaker notes](slides/paper11.pptx) · [Research report](results/report.md) · [Published versus reproduced numbers](results/paper_comparison.csv)

## Main findings

| Experiment | Published study | Our result |
|---|---:|---:|
| Simulation: error estimating the bad rate among low-risk approvals (accepted-only → Bayesian RMSE) | 0.2010 → 0.0929 | 0.2433 → 0.0771 |
| Simulation: share of the full-label training gap recovered by BASL | 24.82% | 29.61% [21.22%, 37.28%] |
| Open data: accepted-only → Bayesian error in ABR | 0.0356 → 0.0130 on Monedo | 0.01434 → 0.01350 on Taiwan; 0.01351 → 0.00354 on later US loans |
| Margin change from Bayesian policy selection | Authors report +$29.27 per $375 loan at 50% LGD | Exactly zero on both public cohorts at base pricing: both methods chose the same cutoff |

The simulation supports the paper's main mechanism. The empirical evidence is mixed. On Taiwan, BASL raises integrated default risk among low-score borrowers by 0.165 percentage points (conditional 95% interval +0.018 to +0.300). On Prosper, the training contrast is close to zero. Point estimates of Bayesian evaluation error improve in both prospective comparisons, but both paired intervals include zero. The single Prosper test cohort produces one absolute error. The published percentage of profit improvement is specific to the original lending environment.

![Published and reproduced Figure 2](results/simulation_fig2.png)

## Design

* **Controlled simulation.** A lender repeatedly approves low-score borrowers, observes repayment and refits. Twenty independent populations, 40 batches each and a separate population holdout expose both the training loss and evaluation bias. A known conditional prior, shuffled prior and random-disclosure placebo give checks with interpretable answers. [Settings, authors' figure digitization and departures](docs/simulation.md)
* **Taiwan.** 30,000 credit-card clients, real next-month defaults and simulated historical approval. Four disjoint test folds. For each, model fitting, BASL stopping and policy selection use separate development subsets. The experiment asks about renewal of financed accounts.
* **Prosper, out of time.** Use first funded loans per borrower, origination-time features and first recorded default in 12 payment cycles. Train through 2007; stop in 2009; choose cutoffs on January–June 2011; test on July 2012–February 2013. Borrowers and label windows are separated. The later cohort contains 8,644 borrowers. [Data and hashes](docs/sources.md)
* **Independent extensions.** Test shifts in prior calibration, a baseline-eligible BASL stopping rule, a fixed lending-policy grid with four LGDs, and a budget of 10 or 50 random reject audits. Targeting audits at cases the new policy would finance reduces sampling error at equal cost. In the Prosper validation cohort, the original prior was already more precise than either small audit. The report includes logit, XGB, IPW, hard pseudo-labels, group calibration and top-decile lift. [Experiments and intervals](results/report.md)

The public cohorts consist of people who already received credit. We can hide selected outcomes and then measure the error against their real repayment. Monedo's original microdata and randomized approvals are unavailable here. Results concern controlled selection and transfer within each public dataset.

## Reproduce

Python 3.12, GNU Make and internet access on first download. macOS users need the OpenMP runtime for XGBoost (`brew install libomp` if absent). A CPU is sufficient. PDF and PPTX are included.

```sh
git clone https://github.com/bigpurota/paper11.git
cd paper11
make all          # install pinned environment, fetch verified sources, run experiments, build report
make verify       # unit/reference/noninterference tests and output checks
make reproduce    # second run in an empty output directory; compare every research artifact
```

`make all` never trains on final-test outcomes. The raw input CSVs (about 89 MB total) go to ignored `data/cache/`. Empirical and simulation results are generated locally. Independent targets are `make data`, `make empirical`, `make simulation`, `make report`, and `make slides`. For a machine with a differently named interpreter, set `PYTHON=/path/to/python3.12`. LibreOffice is needed to regenerate the presentation PDF. A different graphics stack can change rendered bytes; the strict repeat check is intended for a fixed environment.

## Code and evidence

| Location | Contents |
|---|---|
| [Methods](src/paper11/methods.py) | BASL, Monte Carlo Bayesian evaluation, weighted metrics, tail ties, baselines |
| [Empirical pipeline](src/paper11/empirical.py) | Honest splits, threshold selection, paired intervals and calibration |
| [Audit design](src/paper11/audit_design.py) | Equal-cost randomized label revelation and residual correction |
| [Simulation](src/paper11/simulation.py) | Gaussian mixtures, feedback loop, holdout truth and Figure 2 |
| [Tests](tests/) | Closed-form and library comparisons, regression tests and leakage checks |
| [Analysis plan](docs/analysis-plan.md) · [Deviations](docs/deviations.md) | Decisions before fitting, changes after inspection, limitations |
| [Assessment and checks](docs/verification.md) | Course evidence, test scope and independent rerun |

The implementation and empirical pipeline were developed by **Andrey Tsember** with Codex assistance. The paper's algorithms and original Monedo results are credited to Kozodoi and coauthors.

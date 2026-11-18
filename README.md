# Fighting Sampling Bias in Credit Scoring

HSE DSBA Research Seminar · Team 12 · Round 3 · Paper 11

Team 12: Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox.

We independently implement the central methods in [Kozodoi et al., assigned preprint and appendix](https://arxiv.org/abs/2407.13009v1), published in [European Journal of Operational Research](https://www.sciencedirect.com/science/article/pii/S0377221725000839). When a lender observes repayment only after approving an application, how well can it train a scorecard and measure risk among all applicants?

[Presentation (PDF)](slides/paper11.pdf) · [Editable slides and speaker notes](slides/paper11.pptx) · [Our contributions](docs/contributions.md) · [Research report](results/report.md) · [Published versus reproduced numbers](results/paper_comparison.csv)

## Main findings

| Experiment | Published study | Our result |
|---|---:|---:|
| Simulation: error estimating the bad rate among low-risk approvals (accepted-only → Bayesian RMSE) | 0.2010 → 0.0929 | 0.2433 → 0.0771 |
| Simulation: share of the full-label training gap recovered by BASL | 24.82% | 29.61% [21.22%, 37.28%] |
| Open data: accepted-only → Bayesian error in ABR | 0.0356 → 0.0130 on Monedo | 0.01434 → 0.01350 on Taiwan; 0.01351 → 0.00354 on later US loans |
| Margin change from Bayesian policy selection | Authors report +$29.27 per $375 loan at 50% LGD | Exactly zero on both public cohorts at base pricing: both methods chose the same cutoff |

The simulation supports the paper's main mechanism. The empirical evidence is mixed. On Taiwan, BASL raises integrated default risk among low-score borrowers by 0.165 percentage points (conditional 95% interval +0.018 to +0.300). On Prosper, the training contrast is close to zero. Point estimates of Bayesian evaluation error improve in both held-out comparisons, but both paired intervals include zero. The single Prosper test cohort produces one absolute error. The published percentage of profit improvement is specific to the original lending environment.

![Published and reproduced Figure 2](results/simulation_fig2.png)

## What did we add?

### What does the lender need to learn?

Suppose a bank can approve the lowest-risk 30%, 35%, 40%, 45% or 50% of applicants. Ask for the **total expected net margin in each of the four bands between consecutive cutoffs**. Adding those four numbers in the appropriate combinations gives the dollar difference between every pair of policies. The margin on the borrowers all five policies accept cancels. Under fixed terms and additive payoffs, the result holds for any scorecard and any distribution of applicant risk. When each band contains an unknown expected margin that can vary independently, four independent linear measurements are also necessary to recover *every exact difference*. Choosing a winner can take less information. In a separate retrospective check, the four realized band totals recover all 50 pairwise margins across five validation samples. Ten true default counts grouped by the model’s predicted risk settle the sign in one comparison and recover zero exact margins. [General result, proof and numerical checks](docs/policy-information.md)

### When should the bank lend to learn?

A bank can rationally fund a loan that it expects to lose money on. Compare that loss with the **discounted improvement in future lending decisions** made possible by observing repayment. The no-pilot bank also optimizes, using all information it would normally receive. A signal that changes estimated default probabilities but never changes the best action has zero decision value. [Decision rule and proof](docs/information-value.md)

For a pilot and future borrowers with different risks, the joint probability of default gives an exact one-signal value for each future decision. If only the two individual default probabilities are known, we derive the largest attainable gain over every compatible joint distribution. This can **rule out an exploratory loan even under the most favorable dependence**. Independence remains possible given only those marginals, so a positive gain needs additional evidence. [Sharp bounds and worked example](docs/pilot-dependence.md)

In the running example a loan of 100 costs **1.4125** in expectation. Each future loan that can use the one signal is worth **0.548125** more in expectation than under the best uninformed rule. Three follow-ups cover the loss. If a fresh independent risk regime replaces the old one with probability 10% per period, the signal is worth at most **0.70889** across *all* future loans. Increasing volume alone cannot pay for the pilot. A bank that can instead learn after *each* loan can lend already at three **total** opportunities in the persistent regime. We check the distinction across 816,480 parameter settings and compare two implementations of the sequential model. [Break-even frontier](results/information_value_frontier.csv) · [Adaptive benchmark](docs/exploration.md)

**A test on real US small-business loans.** The SBA 504 archive yielded 92,410 eligible disbursements. Across 30 quarters and four regions, we evaluated a preselected pilot rule on the same first 25 continuation loans per episode. Of 79 initially loss-making region-quarters the rule chose three pilots. When their outcomes matured three years later, updated common information already gave the same lending decision on both branches in all three. Net gain versus the updated no-pilot rule was **−0.022** per eligible episode (95% block interval **−0.076 to +0.005**). Forcing one pilot in all 79 produced **+0.019** in future decision gain and **−0.364** on the pilots, for **−0.345 net** (interval **−0.529 to −0.194**). Each scenario loan has principal 100. This replay measures one rule on previously financed borrowers at hypothetical terms. [Chronology, controls and results](docs/pilot-replay.md)

### Can the bank pick a profitable pilot in advance?

We froze the pilot rule and tested it in two further loan archives. SBA 7(a) contributes **886,287 eligible disbursements** from a different US guarantee program. Bondora contributes **179,235 European consumer loans**. Each rule sees the shared risk updates available to the no-pilot lender before the next decision. The additional forecast learns the historical variation in those updates using only public information that has already matured.

| Fixed-risk forecast | Chosen / eligible episodes | Subsequent decisions changed by the pilot | AUC for a positive realized scenario gain (95% block interval) |
|---|---:|---:|---:|
| SBA 7(a), locally calibrated early terms, fixed borrower draw | 16 / 85 | 4 | 0.416 [0.206, 0.624] |
| Bondora, primary cohort with at least 36 months of later receipts | 2 / 100 | 0 | 0.609 [0.478, 0.734] |

Both intervals include 0.50. Neither primary test provides a dependable way to rank where a pilot will earn back its cost. In the US replay, a failed pilot actually present in the West's 2002 Q2 cohort would have changed the rule to decline the same 25 later loans. Its recorded write-off corresponds to **−98.00** on a loan of 100, and the change in follow-up decisions yields **+209.13** under the stated cash-flow scenario. This example was found after the fact. The predetermined borrower draw chose a different loan. [Paired US replay](docs/pilot-transfer.md) · [Prospective scoring and limits](docs/pilot-targeting.md) · [European receipts](docs/lender-pilot.md)

**A European case in euros.** The preselected pilot in Estonia's returning-borrower group in October 2018 lost **€267.00**. Its default would have moved our November 2019 decision from funding to declining 25 later loans. By May 24, 2024 those same loans had paid **€16,211.29 less than principal** in aggregate, including interest and penalty receipts. Skipping them and taking the pilot loss would have added **€15,944.29** versus the refreshed no-pilot decision. This case belongs to the broader 12-month test. Two of its three early cash-coverage cases still met the criterion after remeasurement; one reversed. Additional portfolio collections of €15,944.29, or 53.74% of its remaining principal, would erase the apparent gain, holding the pilot fixed. Bondora actually funded the loans: the revised approval is the action of our rule. [Original protocol and matched payment snapshots](docs/lender-pilot.md)

![Cash gains in the three Bondora episodes with a changed funding decision](results/lender_pilot_cash.png)

**A bank that changed its underwriting.** Commercial Bank of Africa used knowledge from project TOBOA, which targeted roughly 100,000 previously rejected people, to revise its M-Shwari scorecard. Reported acceptance rose from **40% to 47%** and the nonperforming-loan rate fell to **2%**. The report gives the guarantee payout but leaves the later incremental cash profit undisclosed. [Primary field evidence and other lending experiments](docs/observed-pilot-evidence.md)

### Which missing outcomes would change the bank's decision?

Take the first Taiwan validation split. A 30% to 50% expansion would add 1,200 borrowers. At 10% interest and 50% loss given default, the expansion earns a positive incremental margin if **at most 218 of the 1,200 default**. Consider two completions of the archive. They agree on every observed repayment and on the same 699 hidden defaults, with the true count preserved in each of ten groups ranked by predicted risk. Allocating those defaults differently *within* groups produces **120** versus **315** defaults among the extra approvals. The very same group totals support **+0.900** and **−0.888** percentage points of scenario margin per applicant. Only the ten retrospective totals are disclosed in this thought experiment. Individual hidden repayments stay unknown. In the Prosper cohort, knowing its ten true counts does establish a positive margin (range **+0.195 to +1.468 pp**). The project also compares five policies under minimax regret. [Constructed worlds and proof](docs/identification.md)

What information would settle the sign? On Prosper, 160 repayments were hidden among the extra approvals. An audit randomly reveals them and checks a fixed set of sample sizes. With the 17 defaults that actually occurred, it needs **14.46 labels on average**. At 77 or 78 defaults, just either side of break-even, it needs **about 153 of 160**. The chance of declaring the wrong sign is bounded by 5% for each fixed cohort. These are expected counts conditional on the hidden truth and concern a fixed pair of cutoffs. [Exact audit and limits](docs/decision-audit.md)

### Further experiments

1. **Twelve calendar forecasts.** Did removing selection bias from historical evaluation improve next-quarter risk forecasts? On Prosper, historical estimation RMSE fell from **0.79 to 0.26 percentage points**, but next-quarter forecast RMSE rose from **2.08 to 2.36**. The sign survives removing any one quarter. [Forecasts and decomposition](docs/vintages.md)
2. **A decision that accounts for unknown repayments.** We identify which 30%→50% expansions retain a nonnegative worst-case conditional expected margin as reject default odds depart from the prior. The tipping multiplier is **1.85–2.30** across Taiwan splits and **13.19** on Prosper. With unrestricted outcomes and zero downside allowance both cohorts retain the 30% incumbent. [Policy bounds](docs/bounds.md)
3. **An independent randomized offer experiment.** Within the Philippine extract, moving from offers only in the high-score window to offers in both windows gives **+8.02 pp** funding and **+4.19 PPP dollars** in lender cash margin per applicant before costs. Randomized assignment leaves uncertainty about how the people who declined a loan would have repaid it. [Observed cash flows and limits](docs/rct.md)
4. **Where to spend an audit budget.** On Taiwan, drawing 50 hidden outcomes within the proposed policy's portfolio reduces ABR estimation error from **2.01 to 0.86 pp** compared with drawing 50 from all rejects. The designs use the same number of labels. [Audit results](results/audit_summary.csv)

[What belongs to the authors, the team's contribution and the limits of each claim](docs/contributions.md)

## Design

* **Controlled simulation.** A lender repeatedly approves low-score borrowers, observes repayment and refits. Twenty independent populations, 40 batches each and a separate population holdout expose both the training loss and evaluation bias. A known conditional prior, shuffled prior and random-disclosure placebo give checks with interpretable answers. [Settings, authors' figure digitization and departures](docs/simulation.md)
* **Taiwan.** 30,000 credit-card clients, real next-month defaults and simulated historical approval. Four disjoint test folds. For each, model fitting, BASL stopping and policy selection use separate development subsets. The experiment asks about renewal of financed accounts.
* **Prosper, out of time.** Use first funded loans per borrower, origination-time features and first recorded default in 12 payment cycles. Train through 2007; stop in 2009; choose cutoffs on January–June 2011; test on July 2012–February 2013. Borrowers and label windows are separated. The later cohort contains 8,644 borrowers. [Data and hashes](docs/sources.md)
* **Comparators and sensitivity.** Test prior calibration, a baseline-eligible BASL stopping rule and four LGDs. The original study also varied prior quality and LGD. The report includes logit, XGB, IPW, hard pseudo-labels, group calibration and top-decile lift. [Experiments and intervals](results/report.md)

The two controlled-masking cohorts consist of people who already received credit. We can hide selected outcomes and then measure the error against their real repayment. Monedo's original microdata and randomized approvals are unavailable here. The independent Philippine data contain real randomized offers, including applicants who took no loan. The analysis extract covers 1,113 of the original 1,601 marginal applicants. The trial took place at another lender and did not randomize BASL.

## Reproduce

Python 3.12, GNU Make and internet access on first download. macOS users need the OpenMP runtime for XGBoost (`brew install libomp` if absent). A CPU is sufficient. PDF and PPTX are included.

```sh
git clone https://github.com/bigpurota/paper11.git
cd paper11
make all          # install pinned environment, fetch verified sources, run experiments, build report
make verify       # unit/reference/noninterference tests and output checks
make reproduce    # second run in an empty output directory; compare every research artifact
```

`make all` never trains on final-test outcomes. The eight pinned source files (about 730 MB total) are downloaded to ignored `data/cache/`. The SBA and Bondora extensions add larger historical archives. [Download sources and release dates](docs/sources.md) Empirical and simulation results are generated locally. Independent targets are `make data`, `make empirical`, `make simulation`, `make extensions`, `make report`, and `make slides`. For a machine with a differently named interpreter, set `PYTHON=/path/to/python3.12`. LibreOffice is needed to regenerate the presentation PDF. A different graphics stack can change rendered bytes; the strict repeat check is intended for a fixed environment.

## Code and evidence

| Location | Contents |
|---|---|
| [Methods](src/paper11/methods.py) | BASL, Monte Carlo Bayesian evaluation, weighted metrics, tail ties, baselines |
| [Empirical pipeline](src/paper11/empirical.py) | Honest splits, threshold selection, paired intervals and calibration |
| [Policy information](src/paper11/policy_information.py) · [Dynamic exploration](src/paper11/exploration.py) | Minimum linear information for exact policy comparisons and the value of learning through lending |
| [One-pilot decision model](src/paper11/information_value.py) · [Bounds from marginal risks](src/paper11/pilot_dependence.py) · [SBA replay](src/paper11/pilot_replay.py) | Value of a repayment signal, break-even frontier and chronological test on a separate loan portfolio |
| [Policy identification](src/paper11/identification.py) · [Sequential decision audit](src/paper11/decision_audit.py) | Indistinguishable outcomes, minimax regret and exact stopping probabilities |
| [Quarterly forecasts](src/paper11/vintages.py) · [Policy bounds](src/paper11/bounds.py) · [Field experiment](src/paper11/rct.py) | Time transfer, partial identification and observed offer outcomes |
| [Audit design](src/paper11/audit_design.py) | Randomized audits with equal numbers of labels and residual correction |
| [Simulation](src/paper11/simulation.py) | Gaussian mixtures, feedback loop, holdout truth and Figure 2 |
| [Tests](tests/) | Closed-form and library comparisons, regression tests and leakage checks |
| [Analysis plan](docs/analysis-plan.md) · [Deviations](docs/deviations.md) | Decisions before fitting, changes after inspection, limitations |
| [Assessment and checks](docs/verification.md) | Course evidence, test scope and independent rerun |

The code and verification suite were developed with Codex assistance. Kozodoi and coauthors developed the paper’s algorithms and produced the original Monedo results.

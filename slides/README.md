# Paper 11 defense

Open the [defense PowerPoint](paper11.pptx) or [defense PDF](paper11.pdf) for the presentation. The fourteen talk slides take about **14 minutes** at the planned pace, inside the seminar's 15-minute slot, and follow lecture 1's order: problem, method, results and reproduction, critique, next steps. Slide 14 summarizes the talk. Select **Questions →** to open the topic index on slide 15, then choose a question. Every evidence slide has a **← Question index** link back. Typing the page number also works in PowerPoint slide show. A [fourteen-page rehearsal PDF](talk.pdf) contains the talk alone.

## Speaking plan

| Elapsed | Slide | Block | What to explain |
|---|---:|---|---|
| 0:00–0:15 | 1 | Problem | Introduce the lender’s missing-outcome problem. |
| 0:15–1:15 | 2 | Problem | Use Monedo’s 39% and 66% bad rates to show how the old policy selects the measured sample. |
| 1:15–1:55 | 3 | Problem | The paper in one sentence, its place in the literature and its weakest step. |
| 1:55–4:25 | 4 | Method | Trace training with pseudo-labels and evaluation with a fixed score. Use the three-applicant example in the notes to show how a prior changes the estimated default rate. |
| 4:25–5:20 | 5 | Results | The paper's figure and ours on the same axes. |
| 5:20–6:30 | 6 | Results | Paper against our cohorts under soft and hard simulated selection; which idea transfers. |
| 6:30–7:20 | 7 | Results | The lecture 3 minimum: out-of-time test, AUC, calibration, logit baseline, what the data cannot show. |
| 7:20–8:15 | 8 | Upgrade | The prespecified grid of selection strength: when evaluation needs correcting and when BASL fails. |
| 8:15–9:05 | 9 | Upgrade | How well the prior ranks rejected borrowers at Taiwan’s hard cutoff, and what adding a 5% random audit buys. |
| 9:05–9:45 | 10 | Upgrade | An audit is a pilot: its loss today against the later decisions its outcomes can change. |
| 9:45–11:05 | 11 | Critique | How the results could be overfit, and what the authors and we did about it. |
| 11:05–12:25 | 12 | Critique | Assumptions, a missing baseline, the profit claim and our position. |
| 12:25–13:30 | 13 | Next steps | What we would do with three more months. |
| 13:30–14:10 | 14 | Summary | Reject inference is only as good as its model of the rejects. |

The plan leaves 50 seconds before questions. It allocates 1:55 to the problem, 2:30 to the methods, 5:20 to results and extensions, 2:40 to critique and 1:45 to next steps and the closing slide.

## The question index in the defense file

| Pages | Questions |
|---|---|
| 16–19 | Which cohorts were held out? Did Tables 2 and 3 replicate? How do calibration and AUC compare? |
| 20–23 | Which outcomes decide a policy? Can the same risk totals imply opposite policies? How large an audit settles a choice? What do random credit offers establish? |
| 24–28 | When does a pilot break even? Which Estonian action changed? Did advance selection work? Why did the rule miss Finland and boosting lose to frequency? |
| 29–31 | Did pooling help at Wells Fargo? Were the Dutch early warnings right, and why? What did early arrears change at a Czech bank? |

## Questions to expect

| Question | Short answer | Page |
|---|---|---:|
| Taiwan and Prosper loans were all funded. How can they test sampling bias? | We impose a known approval rule on pre-outcome features and hide the outcomes of the simulated rejects, so every estimate can be checked against the truth. | 16 |
| Why did BASL raise defaults on Taiwan? | Not because selection was too mild: across the prespecified grid it is within noise up to strength 4 and worse in all four folds under the hard cutoff, by +0.94 to +7.83 pp. The evaluation prior ranks hard-cutoff rejects backwards (AUC 0.41). BASL uses a separate logistic labeler, so this diagnostic suggests an extrapolation problem without identifying the wrong pseudo-labels. Slide 9 shows the paired comparison with an audit. | 8, 9 |
| Did Bayesian evaluation really help on Taiwan? | Under soft selection, not as a selection correction: on the same cohort its error is 1.79 pp against 0.59 for accepted labels, because the logistic prior is weak. With a hard cutoff it clearly helps, −0.93 pp [−1.19, −0.66]. | 6, 17 |
| If the prior is that poor, why does Bayesian evaluation still help under the hard cutoff? | Accepted-only evaluation assumes the rejects inside the approval range repay like the accepts. The prior understates their risk (9.6% against 43.3%) but still adds part of it, so the error falls only partly, from 3.27 to 2.33 pp. A better prior would recover more. | 9 |
| Your intervals look very narrow. | They resample borrowers with the fitted models fixed. That is right for evaluating one scorecard, but for training comparisons look at the folds: BASL's hard-cutoff loss ranges from +0.94 to +7.83 pp across four separately fitted folds. | 8 |
| Is the selection-strength study post hoc? | The original soft-policy and hard-cutoff comparisons were already known. The finite-slope grid, the audit and the seven criteria were fixed in the [protocol](../docs/selection-strength-protocol.md) before the new comparisons. A [dated public CI run](https://github.com/bigpurota/paper11/actions/runs/44399280377) records the original revision. Three criteria held, three failed, and prior AUC fell overall without falling monotonically. | 8, 11 |
| Isn't revealing audited outcomes cheating? | No: an audit means actually lending to a random 5% of rejects and observing repayment, as the paper's randomized holdout did on a larger scale. Its lending cost is not priced in this study; slide 10 gives the break-even logic. | 9, 10 |
| Why 5%, and would a better model than logistic do? | One audit size was fixed in advance to keep the test honest. A boosted reject model is a natural next variant, but under a hard cutoff any model fitted only to accepts sees no rejects and must extrapolate. | 9 |
| Were the Dutch warnings skill or luck? | Partly luck. The conversion undershot the young cohorts it measured; with their exact year-one rate it would have warned on 4 dates, 3 correctly, instead of 7 and 6. The independent Czech test is weaker. | 30 |
| Are these methods new? | The tools are standard: expected value of sample information, partial identification, odds-ratio sensitivity, credibility weighting and chain-ladder development. The contribution is applying them to lending decisions and testing them on dated data. | — |
| Twenty seeds and forty batches are fewer than the paper's runs. | Intervals resample whole seeds, and the paper's 24.8% recovery lies inside our 21.2–37.3%. | 5 |
| Isn't the cutoff-band argument obvious? | The new part is the minimum and the contrast. Four band totals identify all 50 differences; ten risk-decile totals identify none, and page 21 shows identical decile totals with opposite decisions. | 20, 21 |
| How many outcomes would settle the 30% versus 50% choice? | On Prosper 14.46 audited labels in expectation, but about 153 of 160 near break-even. | 22 |
| Is the next-25-loans target reliable? | It has 9 defaults in 200 loans. The whole later Dutch book, 687 defaults among 16,621 loans, gives 4.13%. | 30 |
| Why a 1990s Czech bank? | It is the public ledger with dated scheduled and actual instalments. The rule was published before scoring (commit e573d37); the median book holds two loans. | 31 |
| How many analyses did you try before these? | The first hard-cutoff check, Estonian pilot profiles and targeted-audit diagnostic were exploratory. Subsequent grid, audit and lender holdouts had public protocols. See the [analysis plan](../docs/analysis-plan.md) and [deviations](../docs/deviations.md). | 11 |

## Full evidence reference

The [38-page evidence PDF](evidence.pdf) and [its editable PowerPoint](evidence.pptx) keep the original reference numbering for detailed follow-up.

| Evidence pages | Topic |
|---|---|
| 1–7, 18, 20–23 | Algorithms, original simulation and paper tables, out-of-time test, AUC, calibration, logistic baseline and reproduction commands. |
| 8–13, 15–17, 24–26 | Forecasting a later portfolio, which groups identify policy margins, random audits, bounds and overfitting. |
| 11, 19 | Philippine offer lottery, observed outcomes and assumptions behind financial comparisons. |
| 14, 27–32 | General break-even condition for a pilot, SBA and Bondora replays, Estonian pilot profiles and later validation. |
| 33–38 | Finnish pilot, boosting and frequency comparisons, Dutch launch cohorts and Wells Fargo external test of pooling. |

The [paper comparison](../results/paper_comparison.csv), [simulation](../docs/simulation.md), [policy-margin proof](../docs/policy-information.md), [pilot break-even condition](../docs/information-value.md) and [research report](../results/report.md) give the exact definitions behind the short talk. The evidence pages keep their original numbering so they can be located during questions.

## Updating the slides

Run `python3 slides/build.py` from the repository root after regenerating the aggregate results. The builder refreshes numeric fields and figures and exports the defense, rehearsal and reference PDFs using LibreOffice. The [defense assembly](defense.py) selects the reserve and adds internal page links. It reads [the short talk template](talk-template.pptx) and [the evidence template](template.pptx). Both remain editable. Keep a dynamic field's double braces and its name within a single PowerPoint text run. Update explanatory text if a rerun changes a conclusion.

Both presentations follow the cover, logo, running header and table rules from [the team’s Paper 15 slides](https://github.com/bigpurota/paper15-lou-shu/tree/0c5d43e18a5ef9134bc6fae656a29f204f31f7cb/slides). The figure bindings use the embedded image descriptions `simulation_fig2.png`, `calibration.png`, `vintage_forecasts.png` and `bounds_frontier.png`. The builder draws three charts at the size of their frames: `talk_strength.png` on slide 8 from `selection_strength.csv`, `talk_pilot.png` on slide 10 from the information-value model and `talk_dutch.png` on page 30 from `early_dutch_episodes.csv`; slide 7 binds `calibration.png`. Talk-template slides after the summary are not spoken; the assembler uses them as evidence pages 20, 30 and 31. The included tables and charts can be refreshed from the aggregate results without borrower records.

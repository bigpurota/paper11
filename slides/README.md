# Paper 11 defense

The [short presentation](talk.pdf) covers the research question, methods, replication and extensions in 14 slides. The [full PDF](paper11.pdf) and [PowerPoint](paper11.pptx) include a topic index on slide 15. Each supporting slide links back to the index.

## Speaking plan

| Elapsed | Slide | Block | What to explain |
|---|---:|---|---|
| 0:00–0:15 | 1 | Problem | Introduce the lender’s missing-outcome problem. |
| 0:15–1:15 | 2 | Problem | Use Monedo’s 39% and 66% bad rates to show how the old policy selects the measured sample. |
| 1:15–1:55 | 3 | Problem | The paper in one sentence, its place in the literature and its weakest step. |
| 1:55–4:25 | 4 | Method | Trace training with pseudo-labels and evaluation with a fixed score. Use the three-applicant example in the notes to show how a prior changes the estimated default rate. |
| 4:25–5:20 | 5 | Results | The paper's figure and ours on the same axes. |
| 5:20–6:30 | 6 | Results | Paper against our cohorts under soft and hard simulated selection; which idea transfers. |
| 6:30–7:20 | 7 | Results | Compare the logistic baseline with XGBoost and BASL on later Prosper borrowers. Read the calibration plot alongside AUC. |
| 7:20–8:15 | 8 | Extension | The prespecified grid of selection strength: when evaluation needs correcting and when BASL fails. |
| 8:15–9:05 | 9 | Extension | How well the evaluation prior ranks rejected borrowers, what a 5% audit changes, and how the measured training effect varies across two refits. |
| 9:05–9:45 | 10 | Extension | An audit is a pilot: its loss today against the later decisions its outcomes can change. |
| 9:45–11:05 | 11 | Critique | How the results could be overfit, and what the authors and we did about it. |
| 11:05–12:25 | 12 | Critique | Assumptions, a missing baseline, the profit claim and our position. |
| 12:25–13:30 | 13 | Next steps | What we would do with three more months. |
| 13:30–14:10 | 14 | Summary | Reject inference is only as good as its model of the rejects. |

Planned talk length is 14 minutes 10 seconds.

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
| Why did BASL raise defaults on Taiwan? | In the archived macOS fit, BASL raised the approved default rate in all four hard-cutoff folds, by +0.94 to +7.83 pp. The independent Linux fit also increased the mean rate, by less. The evaluation prior ranks hard-cutoff rejects backwards (AUC 0.41). BASL uses a separate logistic labeler, so this diagnostic suggests an extrapolation problem without identifying the wrong pseudo-labels. Slide 9 shows the paired comparison with an audit. | 8, 9 |
| Did Bayesian evaluation really help on Taiwan? | Under soft selection, not as a selection correction: on the same cohort its error is 1.79 pp against 0.59 for accepted labels, because the logistic prior is weak. With a hard cutoff it clearly helps, −0.93 pp [−1.19, −0.66]. | 6, 17 |
| If the prior is that poor, why does Bayesian evaluation still help under the hard cutoff? | Accepted-only evaluation assumes the rejects inside the approval range repay like the accepts. The prior understates their risk (9.6% against 43.3%) but still adds part of it, so the error falls only partly, from 3.27 to 2.33 pp. A better prior would recover more. | 9 |
| Your intervals look very narrow. | They resample borrowers with fitted scorecards held fixed. Refit the same hard-cutoff study and the mean increase in defaults from unaudited BASL is +2.97 pp on macOS and +0.96 pp on Linux. After the audit the gaps are +0.13 and +0.14 pp, respectively. Both within-platform intervals for this audited gap include zero. [Platform comparison and archived estimates](../docs/platform-refit.md) | 8, 9 |
| Is the selection-strength study post hoc? | The original soft-policy and hard-cutoff comparisons were already known. The finite-slope grid, the audit and the seven criteria were fixed in the [protocol](../docs/selection-strength-protocol.md) before the new comparisons. A [dated public CI run](https://github.com/bigpurota/paper11/actions/runs/44399280377) records the original revision. In the archived macOS fit, three criteria held, three failed, and prior AUC fell overall without falling monotonically. | 8, 11 |
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

The [evidence PDF](evidence.pdf) and [editable PowerPoint](evidence.pptx) give more detail on the experiments below. Page numbers in this table refer to that document.

| Evidence pages | Topic |
|---|---|
| 1–7, 18, 20–23 | Algorithms, original simulation and paper tables, out-of-time test, AUC, calibration, logistic baseline and reproduction commands. |
| 8–13, 15–17, 24–26 | Forecasting a later portfolio, which groups identify policy margins, random audits, bounds and overfitting. |
| 11, 19 | Philippine offer lottery, observed outcomes and assumptions behind financial comparisons. |
| 14, 27–32 | General break-even condition for a pilot, SBA and Bondora replays, Estonian pilot profiles and later validation. |
| 33–38 | Finnish pilot, boosting and frequency comparisons, Dutch launch cohorts and Wells Fargo external test of pooling. |

The [paper comparison](../results/paper_comparison.csv), [simulation](../docs/simulation.md), [policy-margin proof](../docs/policy-information.md), [pilot break-even condition](../docs/information-value.md) and [research report](../results/report.md) give the exact definitions behind the short talk.

## Updating the slides

Run `python3 slides/build.py` from the repository root after regenerating the aggregate results. The builder refreshes numeric fields and figures and exports the defense, rehearsal and reference PDFs using LibreOffice. The [defense assembly](defense.py) selects the reserve and adds internal page links. It reads [the short talk template](talk-template.pptx) and [the evidence template](template.pptx). Both remain editable. Keep a dynamic field's double braces and its name within a single PowerPoint text run. Update explanatory text if a rerun changes a conclusion.

The builder reads the simulation, calibration and portfolio figures from the results directory. It draws the figures on slides 8, 10 and 30 from the selection grid, the pilot model and the dated Dutch forecasts. Slide 9 uses the [two platform refits](../docs/refits/taiwan-hard-cutoff.csv) for its comparison.

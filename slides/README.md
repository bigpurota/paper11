# Paper 11 defense

Open the [defense PowerPoint](paper11.pptx) or [defense PDF](paper11.pdf) for the presentation. The first ten slides take about **9 minutes 55 seconds** at the planned pace. Slide 10 summarizes the talk. Select **Questions →** to open the topic index on slide 11, then choose a question. Every evidence slide has a **← Question index** link back. Typing the page number also works in PowerPoint slide show. A [ten-page rehearsal PDF](talk.pdf) contains the talk alone.

## Speaking plan

| Elapsed | Slide | What to explain |
|---|---:|---|
| 0:00–0:25 | 1 | Introduce the lender’s missing-outcome problem. |
| 0:25–1:20 | 2 | Use Monedo’s 39% and 66% bad rates to explain how the old policy selects the measured sample. |
| 1:20–2:25 | 3 | Distinguish learning a score from evaluating a fixed score; both need a model of the rejects. |
| 2:25–3:25 | 4 | Trace the same comparison through the paper figure and our simulation. |
| 3:25–4:50 | 5 | Compare Monedo, Taiwan and Prosper under soft and hard simulated selection. Say which idea transfers. |
| 4:50–6:00 | 6 | Walk along the prespecified grid of selection strength: when evaluation needs correcting and when BASL fails. |
| 6:00–7:10 | 7 | Show that the reject model is the bottleneck and that a random 5% audit repairs it. |
| 7:10–8:10 | 8 | An audit is a pilot: compare its loss today with the later decisions its outcomes can change. |
| 8:10–9:10 | 9 | Which outcomes to buy: only borrowers between the cutoffs being compared decide the policy. |
| 9:10–9:55 | 10 | Summarize: reject inference is only as good as its model of the rejects; state the main limitation. |

The seminar's 15-minute format leaves room to expand the same ten slides. Spend an extra 1:30 walking through the paper and simulation panels on slide 4, 1:15 on the two holdout designs on slide 5, 1:30 on the hypotheses that failed on slide 6, and 1:00 on why an ordinary update also reaches a lender that declines the pilot on slide 8. This makes a 15-minute talk before the seminar's question period.

## The question index in the defense file

| Pages | Questions |
|---|---|
| 12–16 | Which cohorts were held out? Did Tables 2 and 3 replicate? How were calibration, AUC and overfitting assessed? |
| 17–19 | Can the same risk totals imply opposite policies? How large an audit settles a choice? What do random credit offers establish? |
| 20–24 | When does a pilot break even? Which Estonian action changed? Did advance selection work? Why did the rule miss Finland and boosting lose to frequency? |
| 25–27 | Did pooling help at Wells Fargo? Were the Dutch early warnings right, and why? What did early arrears change at a Czech bank? |

## Questions to expect

| Question | Short answer | Page |
|---|---|---:|
| Taiwan and Prosper loans were all funded. How can they test sampling bias? | We impose a known approval rule on pre-outcome features and hide the outcomes of the simulated rejects, so every estimate can be checked against the truth. | 12 |
| Why did BASL raise defaults on Taiwan? | Not because selection was too mild: across the prespecified grid it is within noise up to strength 4 and worse in all four folds under the hard cutoff, by +0.94 to +7.83 pp. Its pseudo-labels come from a logistic model that ranks the hard-cutoff rejects backwards (AUC 0.41), so many "good" labels go to risky applicants. With a 5% audit the damage falls to +0.31 pp. | 6, 7 |
| Did Bayesian evaluation really help on Taiwan? | Under soft selection, not as a selection correction: on the same cohort its error is 1.79 pp against 0.59 for accepted labels, because the logistic prior is weak. With a hard cutoff it clearly helps, −0.93 pp [−1.19, −0.66]. | 5, 13 |
| If the prior is that poor, why does Bayesian evaluation still help under the hard cutoff? | Accepted-only evaluation assumes the rejects inside the approval range repay like the accepts. The prior understates their risk (9.6% against 43.3%) but still adds part of it, so the error falls only partly, from 3.27 to 2.33 pp. A better prior would recover more. | 5 |
| Your intervals look very narrow. | They resample borrowers with the fitted models fixed. That is right for evaluating one scorecard, but for training comparisons look at the folds: BASL's hard-cutoff loss ranges from +0.94 to +7.83 pp across four separately fitted folds. | 5 |
| Is the selection-strength study post hoc? | The grid, the audit and seven hypotheses were committed and pushed (ffc7579) before the study ran; only the hard-cutoff cell with the logistic model was known. Three hypotheses were not supported and are reported as such. | 6 |
| Isn't revealing audited outcomes cheating? | No: an audit means actually lending to a random 5% of rejects and observing repayment, as the paper's randomized holdout did on a larger scale. Its lending cost is not priced in this study; slide 8 gives the break-even logic. | 7, 8 |
| Why 5%, and would a better model than logistic do? | One audit size was fixed in advance to keep the test honest. A boosted reject model is a natural next variant, but under a hard cutoff any model fitted only to accepts sees no rejects and must extrapolate. | 7 |
| Were the Dutch warnings skill or luck? | Partly luck. The conversion undershot the young cohorts it measured; with their exact year-one rate it would have warned on 4 dates, 3 correctly, instead of 7 and 6. The independent Czech test is weaker. | 26 |
| Are these methods new? | The tools are standard: expected value of sample information, partial identification, odds-ratio sensitivity, credibility weighting and chain-ladder development. The contribution is applying them to lending decisions and testing them on dated data. | — |
| Twenty seeds and forty batches are fewer than the paper's runs. | Intervals resample whole seeds, and the paper's 24.8% recovery lies inside our 21.2–37.3%. | 4 |
| Isn't slide 9 obvious? | The new part is the minimum and the contrast. Four band totals identify all 50 differences; ten risk-decile totals identify none, and page 17 shows identical decile totals with opposite decisions. | 17 |
| How many outcomes would settle the 30% versus 50% choice? | On Prosper 14.46 audited labels in expectation, but about 153 of 160 near break-even. | 18 |
| Is the next-25-loans target reliable? | It has 9 defaults in 200 loans. The whole later Dutch book, 687 defaults among 16,621 loans, gives 4.13%. | 26 |
| Why a 1990s Czech bank? | It is the public ledger with dated scheduled and actual instalments. The rule was published before scoring (commit e573d37); the median book holds two loans. | 27 |
| How many analyses did you try before these? | Each extension's design was committed before its outcomes were opened. See the [analysis plan](../docs/analysis-plan.md) and [deviations](../docs/deviations.md). | — |

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

Both presentations follow the cover, logo, running header and table rules from [the team’s Paper 15 slides](https://github.com/bigpurota/paper15-lou-shu/tree/0c5d43e18a5ef9134bc6fae656a29f204f31f7cb/slides). The figure bindings use the embedded image descriptions `simulation_fig2.png`, `calibration.png`, `vintage_forecasts.png` and `bounds_frontier.png`. The builder draws three charts at the size of their frames: `talk_strength.png` on slide 6 from `selection_strength.csv`, `talk_pilot.png` on slide 8 from the information-value model and `talk_dutch.png` on page 26 from `early_dutch_episodes.csv`. Talk-template slides after the summary are not spoken; the assembler uses them as evidence pages 26–27. The included tables and charts can be refreshed from the aggregate results without borrower records.

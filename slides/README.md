# Paper 11 defense

Open the [defense PowerPoint](paper11.pptx) or [defense PDF](paper11.pdf) for the presentation. The first nine slides take about **9 minutes 30 seconds** at the planned pace. Slide 9 ends the talk. Select **Questions →** to open the topic index on slide 10, then choose a question. Every evidence slide has a **← Question index** link back. Typing the page number also works in PowerPoint slide show. A [nine-page rehearsal PDF](talk.pdf) contains the talk alone.

## Speaking plan

| Elapsed | Slide | What to explain |
|---|---:|---|
| 0:00–0:25 | 1 | Introduce the lender’s missing-outcome problem. |
| 0:25–1:20 | 2 | Use Monedo’s 39% and 66% bad rates to explain how the old policy selects the measured sample. |
| 1:20–2:25 | 3 | Distinguish learning a score from evaluating a fixed score. |
| 2:25–3:25 | 4 | Trace the same comparison through the paper figure and our simulation. |
| 3:25–4:50 | 5 | Compare evaluation error and approved default rates on Monedo, Taiwan and Prosper. Explain the holdout design and uncertainty. |
| 4:50–5:45 | 6 | Add the margins of the borrower groups between two approval cutoffs. |
| 5:45–6:45 | 7 | Compare the loss on one experimental loan with the future gains its repayment could unlock. |
| 6:45–8:05 | 8 | Use the early Dutch cohorts to distinguish an observable warning from a future default rate. |
| 8:05–9:30 | 9 | Explain the rule, its external test and whether an approval decision changed. |

The seminar's 15-minute format leaves room to expand the same nine slides. Spend an extra 1:30 walking through the paper and simulation panels on slide 4, 1:30 on the two holdout designs and their limitations on slide 5, 1:00 on why an ordinary update also reaches a lender that declines the pilot on slide 7, and 1:30 on the external signal's definition and uncertainty on slide 9. This makes a 15-minute talk before the seminar's question period.

## The question index in the defense file

| Pages | Questions |
|---|---|
| 11–15 | Which cohorts were held out? Did Tables 2 and 3 replicate? How were calibration, AUC and overfitting assessed? |
| 16–18 | Can the same risk totals imply opposite policies? How large an audit settles a choice? What do random credit offers establish? |
| 19–23 | When does a pilot break even? Which Estonian action changed? Did advance selection work? Why did the rule miss Finland and boosting lose to frequency? |
| 24–26 | Did pooling help at Wells Fargo? When did Dutch defaults arrive? Which decisions changed in the Czech ledger, and under what margins? |

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

Both presentations follow the cover, logo, running header and table rules from [the team’s Paper 15 slides](https://github.com/bigpurota/paper15-lou-shu/tree/0c5d43e18a5ef9134bc6fae656a29f204f31f7cb/slides). The figure bindings use the embedded image descriptions `simulation_fig2.png`, `calibration.png`, `vintage_forecasts.png` and `bounds_frontier.png`. The included tables and charts can be refreshed from the aggregate results without borrower records.

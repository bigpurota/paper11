# Paper 11 defense

The [nine-slide talk](paper11.pdf) takes about **9 minutes 30 seconds** at the planned pace. The [editable PowerPoint](paper11.pptx) has speaking notes for each slide. The detailed [evidence PDF](evidence.pdf) and [evidence PowerPoint](evidence.pptx) are separate files for questions.

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

## Evidence for questions

| Evidence pages | Topic |
|---|---|
| 1–7, 18, 20–23 | Algorithms, original simulation and paper tables, out-of-time test, AUC, calibration, logistic baseline and reproduction commands. |
| 8–13, 15–17, 24–26 | Forecasting a later portfolio, which groups identify policy margins, random audits, bounds and overfitting. |
| 11, 19 | Philippine offer lottery, observed outcomes and assumptions behind financial comparisons. |
| 14, 27–32 | General break-even condition for a pilot, SBA and Bondora replays, Estonian pilot profiles and later validation. |
| 33–38 | Finnish pilot, boosting and frequency comparisons, Dutch launch cohorts and Wells Fargo external test of pooling. |

The [paper comparison](../results/paper_comparison.csv), [simulation](../docs/simulation.md), [policy-margin proof](../docs/policy-information.md), [pilot break-even condition](../docs/information-value.md) and [research report](../results/report.md) give the exact definitions behind the short talk. The evidence pages keep their original numbering so they can be located during questions.

## Updating the slides

Run `python3 slides/build.py` from the repository root after regenerating the aggregate results. The builder refreshes numeric fields and figures and exports both PDFs using LibreOffice. It reads [the short talk template](talk-template.pptx) and [the evidence template](template.pptx). Both remain editable. Keep a dynamic field's double braces and its name within a single PowerPoint text run. Update explanatory text if a rerun changes a conclusion.

Both presentations follow the cover, logo, running header and table rules from [the team’s Paper 15 slides](https://github.com/bigpurota/paper15-lou-shu/tree/0c5d43e18a5ef9134bc6fae656a29f204f31f7cb/slides). The figure bindings use the embedded image descriptions `simulation_fig2.png`, `calibration.png`, `vintage_forecasts.png` and `bounds_frontier.png`. The included tables and charts can be refreshed from the aggregate results without borrower records.

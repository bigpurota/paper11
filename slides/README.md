# Paper 11 defense

The defense deck is one file: [PDF](paper11.pdf) and [PowerPoint with speaker notes](paper11.pptx). Slides 1–14 are the talk. Slide 15 is a question index, and each of the 16 supporting slides after it links back to the index. Every slide has speaker notes; on slides 1–14 they start with the planned duration.

## The question index in the defense file

| Pages | Questions |
|---|---|
| 16–19 | Which cohorts were held out? Did Tables 2 and 3 replicate? How do calibration and AUC compare? |
| 20–23 | Which outcomes decide a policy? Can the same risk totals imply opposite policies? How large an audit settles a choice? What do random credit offers establish? |
| 24–28 | When does a pilot break even? Which Estonian action changed? Did advance selection work? Why did the rule miss Finland and boosting lose to frequency? |
| 29–31 | Did pooling help at Wells Fargo? Were the Dutch early warnings right, and why? What did early arrears change at a Czech bank? |

## Definitions

The [paper comparison](../results/paper_comparison.csv), [simulation](../docs/simulation.md), [policy-margin proof](../docs/policy-information.md), [pilot break-even condition](../docs/information-value.md) and [research report](../results/report.md) give the exact definitions behind the short talk.

## Updating the slides

Run `python3 slides/build.py` from the repository root after regenerating the aggregate results. The builder refreshes numeric fields, figures and speaker notes and exports the defense PDF using LibreOffice. The [defense assembly](defense.py) adds the reserve slides and internal page links. It reads [the talk template](talk-template.pptx) and [the evidence template](template.pptx), the source of the reserve slides. Both remain editable. Keep a dynamic field's double braces and its name within a single PowerPoint text run. Update explanatory text if a rerun changes a conclusion.

The builder reads the simulation, calibration and portfolio figures from the results directory. It draws the figures on slides 8, 10 and 30 from the selection grid, the pilot model and the dated Dutch forecasts. Slide 9 uses the [two platform refits](../docs/refits/taiwan-hard-cutoff.csv) for its comparison.

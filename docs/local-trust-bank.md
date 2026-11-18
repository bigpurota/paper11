# When did Wells Fargo benefit from a state-specific rate?

Across 828 state–quarters with measured local and outside history, mixing the two rates reduced Brier loss by **0.001684** against the local rate alone. Its advantage over the bank's rate in the other states was **0.000014**, with a 95% quarter-block interval from **−0.000005 to +0.000046**. The prespecified criterion required positive lower bounds against both. On this test the broader rate alone remained competitive. [Protocol published before scoring](https://github.com/bigpurota/paper11/commit/99db60b) · [All scores and intervals](../results/local_trust_bank_metrics.csv)

## Which bank, dates and loans?

We took one US bank, Wells Fargo Bank, National Association, using FDIC certificate 3511. SBA administers the 7(a) guarantee program. The local area is the project state, and the broader history includes loans from the same bank in all other covered jurisdictions. The test covers loans disbursed in 2015 Q1–2019 Q3 from the previously unused FY2010–2019 approval archive. Every test loan had three years of follow-up. A recorded charge-off on or before the third anniversary of first disbursement defines the event. Regional case mix, guarantee terms and the length of the outcome horizon differ from the Bondora experiment. [Official SBA source and data dictionary](https://data.sba.gov/dataset/7a-504-foia) · [FDIC institution record](https://banks.data.fdic.gov/bankfind-suite/bankfind/details/3511)

Before each quarter t, the bank counts measured three-year events on disbursements in t−24 through t−13, twelve whole quarters. It can also count how many loans it issued during the following twelve completed quarters t−12 through t−1. Their outcomes cannot enter this forecast. The archive supplies event dates; any delay in recording them in a live system is unobserved. We use the approval archives FY1991–1999, FY2000–2009 and FY2010–2019 to reconstruct dated history. Some early test-quarter outcomes legitimately enter later forecasts after three years have passed. The rule and its constants never change. The new 255,300,948-byte official archive has SHA-256 `39aa32b71fb5dbb4bfb178c9b3d597c92bb6903622027c2f8360d13e57d0abb2`. [Dated archive](https://data.sba.gov/sites/default/files/uploaded_resources/FOIA_7a_FY2010_FY2019_asof_260930.csv) · [Source adapter](../src/paper11/local_trust_bank.py)

Across all three files the adapter keeps only certificate 3511, the 50 states and DC, consistent approval and disbursement dates, positive gross approval and mature observations. It removes any charge-off dated before disbursement. Five older records had terminal charge-off status without a measurable date. Their disbursements count toward volume, while their unknown flags are excluded from event rates. Two loans from older approval releases had disbursement dates in the test period. The test target excludes them under its approval-file restriction. The new archive supplied measured flags on all **23,873** test loans, with **728** three-year charge-offs. The population spans **848** nonempty state–quarters and **$6.798 billion** of gross approved principal. Twenty cells with 24 loans had no mature local history and used the outside rate directly. The 828 comparison cells contain 23,849 loans, 727 recorded events and $6.787 billion of gross approval. [Source reconciliation](../results/local_trust_bank_coverage.csv) · [Cell counts, principal and forecasts](../results/local_trust_bank_episodes.csv)

## What determines the weight?

The rule checks how much the other states' mature event rates differ after subtracting estimated binomial noise. It assigns more weight to its local history when variation across states is credible and when local precision is high. Expansion reduces the effective local count when the recent volume exceeds the volume with measurable outcomes. The returned weight, estimated between-state variance and effective count are observable before the quarter. Equal-weight donor variability and a loan-count-weighted outside mean are deliberate approximations. The expansion penalty expresses a concern that a rapidly changing book is less comparable with its predecessors. The observations alone cannot identify which borrowers changed or why. [Frozen equations](local-trust-protocol.md) · [Shared implementation](../src/paper11/local_trust.py)

| Rule | Equal state–quarters, Brier | Principal-weighted inside each book | Across state–quarters weighted by loan count |
|---|---:|---:|---:|
| Local frequency | 0.026439 | 0.011734 | 0.029924 |
| Other-state frequency | 0.024769 | 0.009747 | 0.029850 |
| Prespecified mixture | **0.024755** | 0.009743 | 0.029841 |
| Hard local-or-broader choice | 0.024763 | 0.009739 | 0.029848 |
| Mixture without discounting expansion | 0.024756 | 0.009747 | 0.029841 |

Within each cell, primary loss is the average squared probability error on the individual binary outcomes, weighted by loan count. Equal weighting across cells makes a small state's quarter as important as a large state's quarter. The uncertainty calculation resamples four contiguous quarters jointly across states, using 2,500 circular-block draws over 19 quarters. The local-minus-mixture interval was **[+0.001131, +0.002142]**. The primary mixture and the version without the expansion discount differed by only 0.00000124 in average Brier. The data chiefly support sharing information across states with thin histories. [Quarterly estimates and all three weightings](../results/local_trust_bank_metrics.csv)

## Did the rule know when the local rate would be closer?

| Issue-time choice | State–quarters | Median mature local loans | Local closer | Broader closer | Ties | Mean Brier advantage of local |
|---|---:|---:|---:|---:|---:|---:|
| Local weight above ½ | 67 | 412 | 40 (59.7%) | 27 | 0 | +0.000074 |
| Local weight at or below ½ | 761 | 82 | 312 (41.0%) | 449 | 0 | −0.001823 |

The direction of both subgroup comparisons matched the rule. In 576 of 828 cells the donor spread was too small to distinguish from estimated sampling noise and the mixture put its full weight on the broader rate. The 67 high-local-weight cases all fell in the last six test quarters. Differences between the two groups therefore include differences across time and states. In the remaining 20 cold-start cells the two operational forecasts coincide by construction. [Weight strata, accuracy and ties](../results/local_trust_bank_choices.csv)

The original Bondora country study required at least 50 measured local loans. As a post-test check of comparability, the Wells Fargo cells meeting that old coverage condition give a local-minus-mixture Brier difference of +0.000139 across 590 state–quarters. The 238 thinner cells account for 94% of the aggregate difference on the main weighting. Their history can be as small as one loan. This helps explain why the effect size transferred poorly to a question about Dutch histories of 59–693 loans. The sensitivity uses published forecasts directly and changes no weights. [State–quarter ledger](../results/local_trust_bank_episodes.csv)

## Would lending change?

Under the fixed +10%/−45% scenario the local rule would reject 15 state–quarter books that the mixture would fund; the broader rule would also fund every one. These books contained 28 issued loans and $14,396,900 of gross approval. No three-year charge-off was recorded on those loans, giving **+$1,439,690** of modeled incremental payoff against the local rule. Twelve of these 15 differences follow from a single measured historical loan with no charge-off. The prespecified half-count formula gives a local estimate of (0+0.5)/(1+1)=25%. The other three cells had one event in six or seven historical loans. These examples identify the consequence of relying on a small-sample point estimate at a lending threshold.

Under +3%/−50%, the mixture would fund 103 additional books containing 526 loans and $142,117,600 of approval, giving **+$4,102,143** against the local rule. At both prices the mixture and the broader policy make identical decisions on all 828 matched books. Gross approval provides the scenario exposure. Actual interest, guarantee proceeds, servicing costs, recoveries and the profit from lending to a rejected borrower remain unobserved. The analysis uses historical funded loans under replayed choices. [All changes in scenario margin and actions](../results/local_trust_bank_policy.csv)

An independent CSV reader reconstructed all 848 books, state and donor counts, local volume, weights and forecasts from the administrative records. It also reproduced both primary gains via the linear Brier difference and their interval endpoints using explicitly expanded calendar blocks. Regression tests check the exact maturity boundary, unresolved events, the future-data barrier and conditional payoff accounting. [Reference tests](../tests/test_local_trust_bank.py)

To reproduce the bank tables from the three pinned sources:

```sh
PYTHONPATH=src .venv/bin/python -m paper11.local_trust_bank --cache data/cache --out results
```

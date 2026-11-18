# When a loan outcome becomes available

A Bondora observation in this test is one country in one month. Take its first funded loan as the potential pilot. Thirteen months later, the bank decides whether to fund the first 25 loans in that country, or every loan if fewer than 25 are available. Country remains observable before and after the grading change. Restricting estimation to country–grade combinations would have excluded all 119 groups in the previous primary test. [Public protocol, frozen before the paired forecasts](pilot-signal-ml-protocol.md) · [Source and prior test](pilot-holdout.md)

| Date relative to issue month s | Observable inputs or measured target |
|---|---|
| Start of s, plus the pilot's offered contract | Principal, initial rate and original term. The twelve cohorts s−24 through s−13 supply the historical first-year risk. The twelve completed months s−12 through s−1 supply counts and principal of the first up to 25 loans in each month. Empty months have zero exposure. |
| Start of s+13, before the continuation decision | Both banks know the refreshed first-year risk from s−12 through s−1. Under the common peer-feed assumption they can also see the measured first-year flags of the other loans in the pilot's country and issue month. The pilot is removed from the peer numerator and denominator. Only a bank that funded the pilot receives its own first-year flag. |
| Start of s+26 | All loans in month s+13 have had a full year to produce a first-year default flag. The prediction target is the share of the continuation's original principal attributable to loans with such a flag. An empty book has zero financial exposure and no probability target. An unknown flag on a nonempty book keeps its default-exposure target missing. |
| Common ledger in the November 2026 workbook | Only evaluation and retrospective discovery rows receive cumulative cash and outstanding balances. Gross received cash sums principal, interest, extra interest and late fees, less issued principal. A missing component leaves the loan's cash unknown. Future receipts, servicing and funding costs remain outside the endpoint. |

The worksheet dictionary defines `loan_issued_at` as issue time, `issued_amount` as the amount issued to the customer, `initial_interest_rate` as the contract's initial rate and `initial_loan_duration` in months. The published interest-rate number is passed to the learner on its original scale. `has_default_within_12_months` records a measured first-year event; the dictionary reserves null for an unmeasurable flag. The tape supplies no history of which peer records the bank actually received. The peer-feed and no-peer analyses therefore test two explicit information environments. [Official data catalog](https://goandgrow.eu/en/public-statistics/) · [Dated workbook and checksum](pilot-holdout.md)

## Coverage

The training cutoff is the start of October 2022. An August 2020 pilot may enter because the continuation originates in September 2021 and its labels mature by October 2022. The 232 usable training episodes span 124 distinct months of origin and consist of 124 Estonian, 58 Finnish and 50 Spanish episodes. All 252 historically supported training rows are retained in the public panel, including 20 empty continuations. None contains the 2026 cash or balance columns as training data.

| Test country, October 2022–May 2024 | Issued loans | Nonempty country–months | At least 50 mature historical labels | Nonempty continuation | Eligible under the original direct-loss screen |
|---|---:|---:|---:|---:|---:|
| Estonia | 30,381 | 20 | 20 | 20 | 0 |
| Finland | 95,772 | 20 | 20 | 20 | 0 |
| Latvia | 438 | 6 | 0 | 0 | 0 |
| Netherlands | 9,467 | 18 | 8 | 8 | 8 |
| Spain | 2,898 | 13 | 11 | 0 | 11 |
| **Total** | **138,956** | **77** | **59** | **48** | **19** |

All 48 nonempty supported test continuations contain 25 loans, with measured first-year outcomes for all 1,200 loans. All 59 supported pilot signals and required cash amounts are available. Loss on the initially offered pilot is a stricter eligibility screen than sufficient historical data. The 19 eligible opportunities include eleven Spanish episodes with no continuation loan and eight Dutch episodes. The Netherlands accounts for all eligible episodes with a nonempty follow-up and has no training episode. These counts limit any inference about advances in strict recovery. [Support for every scheduled country–month](../results/pilot_signal_panel_coverage.csv) · [Episode dates, cash and earlier-rule benchmarks](../results/pilot_signal_panel.csv)

## Exactly which positions are new?

In the full twenty-month window, 29 of 59 pilot loans had previously appeared in a continuation portfolio in the earlier grade-based study (12 Estonian, 12 Finnish and five Spanish). **None of the 1,200 continuation loans** had previously appeared as a pilot or follow-up in the earlier scored country–grade episodes. This check reconstructs the earlier portfolios using the same workbook rows and the original grade-specific ordering. The July 2021 discovery tape ends even earlier. Loan identities used to establish the overlaps stay in the source adapter. The data do not establish uniqueness of individual people across distinct loans.

The predeclared November 2023–May 2024 subset includes 57,508 loans in 27 nonempty country–months. Of these, 21 are forecastable, all with a nonempty continuation, including seven opportunities passing the direct-loss screen. No pilot or continuation in this subset appeared in a previously scored position in the earlier study. The subset is part of the twenty-month analysis. Within the full new test itself, fourteen pilots had also appeared in the continuation of another new episode thirteen months earlier. Each paired comparison concerns one loan and its subsequent portfolio, conditional on a continuing external stream of ordinary lending records. Adding all episode gains does not reproduce the balance sheet of one bank running a single uninterrupted policy. [Scoring and cash definitions](pilot-signal-ml-protocol.md)

The original amount-aware policy is reconstructed on the same country stream through the published `predict` function, with only public risk-update pairs whose disclosure month is at or before the decision. Its issue choices and contingent actions are in the columns prefixed `structural_`. The comparison of whom to issue in the ML experiment gives both selection policies the same downstream ML rule. [Original policy](pilot-rule-protocol.md) · [Source adapter](../src/paper11/pilot_signal_panel.py) · [Timing, peer exclusion and missingness tests](../tests/test_pilot_signal_panel.py)

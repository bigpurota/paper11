# What was visible before the two Estonian pilots?

In October and November 2018, the first funded returning Estonian customer in each month's replay requested and received **€530** on a 36-month schedule. Each had five earlier Bondora loans. The median principal in that segment over the preceding three complete months was €1,060 on both dates. A €530 pilot therefore exposed only half the principal of a typical recent loan. The selected February 2019 pilot exposed more than five times its local median. All three signals changed the replay's next decision, but the February change lost money. [Selected loans and origin profiles](../results/pilot_profiles_selected.csv) · [Cash decomposition](../results/lender_pilot_followup.csv)

## The closest comparisons

The first five numeric columns below were observable at the funding decision, conditional on the contract terms being set. The last two columns use the later snapshot. “Segment PD” is the smoothed share of prior loans that defaulted within twelve months, estimated separately for returning Estonian customers. The historical median used in the size ratio is recalculated on each date.

| EE returning pilot | Principal | Principal / historical median | Original term, months | Previous loans | Segment PD | Replay decision changed? | Incremental recorded cash |
|---|---:|---:|---:|---:|---:|:---:|---:|
| Jul 2018 | €530 | 0.55 | 36 | 2 | 18.185% | No | +€93.96 |
| Oct 2018 | €530 | 0.50 | 36 | 5 | 18.732% | Yes | +€15,944.29 |
| Nov 2018 | €530 | 0.50 | 36 | 5 | 18.598% | Yes | +€8,706.30 |
| Dec 2018 | €2,230 | 2.10 | 60 | 2 | 18.806% | No | −€163.23 |
| Feb 2019 | €5,525 | 5.21 | 60 | 11 | 18.347% | Yes | −€8,672.42 |

July supplies an important near-match. Its principal and term equaled those of both successes. Its 16.26% recorded contract rate also equaled November's and February's. July's €93.96 came entirely from the pilot itself. In February the direct shortfall was €1,491.80 and declining the subsequent portfolio sacrificed €7,180.62. The October and November shortfalls were €267.00 and €207.33 respectively. Avoiding €16,211.29 and €8,913.63 of subsequent recorded losses more than covered them at the May 24, 2024 cut. These are replayed decisions on observed funded loans. Bondora's actual decision after seeing each signal is unknown. [Cash audit and outstanding principal](lender-pilot.md)

The early archive assigns different borrower handles to the two €530 pilots. Their two groups of 25 continuation loans contain 50 distinct handles. Although the two groups have no borrower handles in common, their cash histories still span adjacent origination months in the same credit market.

The two successes also had different prior borrowing totals (€5,625 and €10,520) and recorded interest rates (19.72% and 16.26%). Recent segment risk was rising by 1.01 and 1.38 percentage points, measured across adjacent six-month windows of fully seasoned originations. December's increase was larger at 1.94 points and its signal left the subsequent decision unchanged. The original forecast ranked November sixth and October eighth among the ten selected loans. It ranked February fourth. Origination risk, its trend and the original score alone give little grounds for separating these cases. [All ten selected profiles](../results/pilot_profiles_selected.csv)

## How unusual were the two loans?

Each row reports medians. The underlying unit is one predefined country × new/returning customer group × origination month. The first funded loan supplies the pilot contract. The peer groups overlap. The full comparison uses the expanded, at-least-12-month-seasoned panel. In that panel, 228 opportunities had a negative expected direct scenario margin and ten had positive predicted net value. The older, at-least-36-month-seasoned primary cohort had no switches. All eight eligible opportunities for returning Estonian customers were selected and occurred in consecutive months, July 2018 to February 2019.

| Discovery comparison | Episodes | Originally selected | Principal | Principal / historical median | Previous loans |
|---|---:|---:|---:|---:|---:|
| Two successful selected pilots | 2 | 2 | €530 | 0.50 | 5 |
| All other eligible opportunities | 226 | 8 | €2,125 | 1.04 | 0.5 |
| Other originally selected pilots | 8 | 8 | €3,092.50 | 2.55 | 2 |
| Other eligible returning Estonian customers | 6 | 6 | €4,355 | 4.11 | 3 |
| Other eligible segments in the same two months | 10 | 0 | €2,442.50 | 1.00 | 0.5 |

A small commitment relative to future lending gives the bank more principal on which to use the information for every euro put at risk. It says little by itself about which borrowers will default or which portfolios will benefit from changing a decision. July shows how a similarly small commitment can yield no decision change. Five earlier loans and the exact €530 amount describe two neighboring, outcome-selected episodes. They provide no independently tested cutoffs. The transferable hypothesis concerns the **value of future exposure relative to the cost of the pilot**. The new rule estimates that quantity from the contract and earlier segment history. [Peer distributions and nonmissing counts](../results/pilot_profiles_comparators.csv) · [Rule and evaluation protocol](pilot-rule-protocol.md)

## Did accounting for size separate the original cases?

The revised forecast ranked November second, October third and the unsuccessful February switch twelfth among 228 eligible opportunities by predicted strict-recovery probability. July, when the decision stayed the same, ranked first. The funding rule uses expected incremental **money**, so it still selected February. The estimated default probability at issue was 18.347%, only just above the 18.182% break-even level. At €5,525 principal the expected direct loss was €5.02; the expected information value for the future portfolio was €37.26. A large principal does not automatically imply a large expected loss at that threshold.

The revised rule funded 17 old opportunities and included all ten originally selected. Its two strict successes therefore accounted for 2/17 recommendations, compared with 2/10 before. Its mean cash gain over the previous rule was €5.05 per eligible opportunity (95% four-quarter interval −€3.58 to +€28.28). These rankings were obtained on the cases that suggested the change. [All development forecasts and paired outcomes](../results/pilot_rule_development.csv) · [Tests on later dates and another lender](../results/pilot_rule_summary.csv)

## Which fields could have been known?

The decision point is immediately before final funding on the given terms. The application amount, booked amount, original maturity date and contractual rate are assumed available then. An application-receipt decision would require earlier offers with timestamps. The counts and sums of previous loans explicitly refer to borrowing before the pilot. We use the calendar-month difference from origination to the **original** maturity date. A later schedule amendment can change duration and the latest maturity date. We exclude those fields, retrospective performance statuses, balances, collections and revised ratings from the profile.

The origin profiles come from the July 20, 2021 archive. The May 24, 2024 archive provides a separate field-agreement check and subsequent cash outcomes. Every one of the 347 scheduled candidates matched across releases on the nine checked contract and origination fields, with all values present. Agreement across two archived vintages cannot establish what the systems displayed before July 2021. Funded-only history also conditions which borrowers appear in every comparison. [Field-level check](../results/pilot_profiles_field_agreement.csv) · [Archived data and sampling](lender-pilot.md)

Historical loan volume and principal use the last three **complete** calendar months in the same segment. The twelve-month default rate uses loans issued 24 through 13 months before the pilot month, inclusive. Every loan in the most recent cohort has therefore had a full year for an event to occur. Each rate uses half a default and half a nondefault as smoothing. The trend subtracts the older six-cohort rate from the newer six-cohort rate. The profile code checks its maturity counts and rates against the original frozen replay. It joins the realized switch and pilot payoff only after constructing all contract and historical features. [Profile implementation](../src/paper11/pilot_profiles.py) · [Temporal boundary tests](../tests/test_pilot_profiles.py)

These two commands reproduce the sample schedule, cash ledger and profiles from the repository root.

```sh
PYTHONPATH=src .venv/bin/python -m paper11.lender_pilot --out results --cache data/cache
PYTHONPATH=src .venv/bin/python -m paper11.pilot_profiles --out results --cache data/cache
```

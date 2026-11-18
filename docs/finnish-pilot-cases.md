# Why the Finnish lending rule missed March 2021

The original amount-aware rule passed on the March 2021 Finnish pilot and funded the November 2021 and February 2022 pilots. All three were the first loan in a month in Finland’s unrated segment. March had the largest expected direct loss and the smallest portfolio on which a signal could pay. This is a retrospective explanation of three cases identified in the earlier holdout. [Original holdout](pilot-holdout.md) · [Case-level calculations](../results/finnish_pilot_cases.csv)

## What the bank could estimate at issue

| Frozen forecast | Mar 2021 | Nov 2021 | Feb 2022 |
|---|---:|---:|---:|
| Pilot principal | €1,141 | €726 | €2,075 |
| Default probability at issue | 32.03% | 23.06% | 19.48% |
| Previous 12 months with any comparable originations | 5 | 12 | 12 |
| Projected next portfolio, loans / principal | 9.50 / €28,116 | 24.08 / €67,072 | 25.00 / €69,093 |
| Expected direct margin | −€86.93 | −€19.50 | −€14.81 |
| Extra decision value via a pilot default | €6.35 | €22.97 | €33.53 |
| Extra decision value via a pilot with no 12-month default | €0.38 | €6.32 | €5.46 |
| Expected incremental total | **−€80.19** | **+€9.80** | **+€24.18** |
| Funding rank among 23 eligible seasoned episodes | 8 | 2 | 1 |
| Probability of changing a decision on a nonempty portfolio | 1.20% | 6.99% | 7.42% |
| Probability of a switch that covers a losing pilot, scenario | 0.385% | 1.508% | 1.754% |
| Rank by that strict-recovery probability | 9 | 2 | 1 |

The two decision-value rows include each outcome’s probability. At issue the bank cannot know the ordinary public risk estimate $u$ that both strategies will observe 13 months later. The frozen rule transfers 244, 254 and 260 previously disclosed public changes to the respective issue dates. It averages the extra decision value across those states, then multiplies by the projected portfolio principal. It uses the previous 12 complete months to project up to 25 originations, including empty months. The probability of changing a decision on a nonempty portfolio also accounts for those empty months. The rule maximises expected scenario money. The probability of recovering a direct loss describes a narrower event. [Frozen decision rule and assumptions](pilot-rule-protocol.md)

The signal can change a decision only near the lending threshold. With payoff margin $m(p)=0.10-0.55p$, the break-even probability is $b=18.18\%$. A pilot with first-year event $y$ changes the follow-up estimate from $u$ to $(20u+y)/21$. A default can block a previously profitable loan for public risks from 14.09% up to 18.18%. A pilot with no first-year default can enable lending from 18.18% up to 19.09%. At exact break-even the bank declines. These ranges refer to $u$ at disclosure. The table’s issue-time PD is the forecast mean of the later public states.

For each €1,000 in follow-up principal, the March signal was worth €0.24 in expectation, versus €0.44 and €0.56 for the later pilots. At these rates the three break-even follow-up portfolios were €362,943, €44,642 and €26,242 respectively. Even replacing March’s projected €28,116 with its eventual €62,876, while retaining its issue-time risk forecast, gives only €15.06 of expected information against an €86.93 expected loss. This last calculation uses hindsight solely to explain the volume effect.

## What happened at disclosure

| Replayed decision and cash through the workbook cut | Mar 2021 | Nov 2021 | Feb 2022 |
|---|---:|---:|---:|
| Later common public PD | 16.47% | 7.63% | 7.72% |
| PD if the pilot defaults | 20.45% | 12.03% | 12.11% |
| PD if the pilot has no first-year default | 15.68% | 7.27% | 7.35% |
| Observed first-year pilot default | Yes | No | No |
| Follow-up action without / with its signal | Lend / decline | Lend / lend | Lend / lend |
| Direct pilot cash | −€386.82 | +€249.80 | €0.00 |
| Incremental follow-up cash | +€4,103.74 | €0.00 | €0.00 |
| Incremental total cash if tried | **+€3,716.92** | **+€249.80** | **€0.00** |

March’s eventual public risk fell below 92.6% of its forecast states and inside the default switch band. The 25 later loans had €62,876 of principal and a recorded cash loss of €4,103.74. Skipping them after the pilot default would have covered its €386.82 cash loss. The same case loses €4,689.05 under the fixed two-payoff scenario. At the cash cut €17,950.05 remained outstanding on the follow-up loans. For November and February the eventual public risk fell so far below the threshold that *either* pilot outcome would have led to funding. The archive records issued loans. A policy replay supplies both decisions, and no claim about the lender’s historical motive follows. [Raw decision contrasts and coverage](../results/pilot_holdout_episodes.csv)

## If both strategies could see other loans from the pilot month

The original common update includes outcomes from earlier vintages and excludes loans from the pilot’s own origination month. An alternative information arrangement gives both strategies every measured one-year flag on the other loans in the same month and segment at the later decision. For $n$ other loans and $d$ defaults the common PD becomes $(20u+d)/(20+n)$. Only the pilot strategy adds its own flag, once. This calculation assumes that both strategies can obtain those other outcomes. An archive of funded loans establishes their measured flags but cannot establish what a particular lender could have purchased or observed then.

| Same-month peers at disclosure | Mar 2021 | Nov 2021 | Feb 2022 |
|---|---:|---:|---:|
| Peer defaults / measured peers | 33 / 473 | 307 / 4,082 | 310 / 3,393 |
| Common PD after peers | 7.362% | 7.521% | 9.128% |
| PD after also seeing this pilot | 7.549% | 7.520% | 9.126% |
| Incremental future cash | €0 | €0 | €0 |

With this wider common feed, the March decision stays at “lend” and trying the pilot costs €386.82. The same borrower default can be decisive when isolated and redundant when hundreds of similar outcomes are already known. This three-case sensitivity motivates evaluating the marginal information in a loan against a specified shared information set. [Implementation and reproducible output](../src/paper11/finnish_pilot_cases.py)

Regenerate the three cases after producing `results/pilot_holdout_episodes.csv` with the original holdout module.

```sh
PYTHONPATH=src .venv/bin/python -m paper11.finnish_pilot_cases --out results --cache data/cache
```

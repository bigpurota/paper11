# How much does one pilot tell the lender?

On 48 later Bondora portfolios, a lender that saw other borrowers’ repayment records forecast future defaults more accurately with the boosted model than it did with the same model family before those records arrived. Revealing **the pilot’s own first-year outcome** changed mean Brier loss from 0.093275 to 0.093372. The simple historical default rate available on the day of issue scored 0.085503 and beat every boosted specification. Among 19 opportunities where the historical rate implied a loss on the pilot, the ML rule purchased zero signals. [Locked protocol](pilot-signal-ml-protocol.md) · [All paired estimates](../results/pilot_signal_ml_metrics.csv)

## What can the bank know?

Consider the first funded loan in a country in a given month. At issue the lender knows its contract, the mature historical default rate and the volume of recent loans. Thirteen months later both lending strategies receive the ordinary refresh. In the primary comparison both also receive the measured first-year outcomes of other loans issued in the pilot’s country and month. Only the strategy that funded the pilot receives its own first-year default flag $Y$. The forecast concerns up to the first 25 loans in the disclosure month, weighted by original principal. A no-default flag means no recorded default within twelve months. [Calendar, definitions and coverage](pilot-signal-panel.md)

A histogram gradient boosted tree model estimates future default exposure from the shared information and $Y$. Given exactly the same public records, run **the same fitted model twice**. Entering zero for the pilot flag gives $m_0$. Entering one gives $m_1$. A second model estimates its default probability $\pi$ using only the shared records. Before revealing the flag, the internally consistent forecast is $m=(1-\pi)m_0+\pi m_1$. After revelation use the matching branch. All fits were frozen in October 2022 on 232 mature country-months across 124 months. Each country-month gets one vote. [Model and scoring code](../src/paper11/pilot_signal_ml.py) · [Estimator documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)

## A change in risk and a change in lending

For each euro lent, the scenario pays 10 cents on a performing loan and loses 45 cents on a default. The lender funds a book when its predicted default share is below 18.18%. Suppose the pilot has a 25% chance of default and a €1,000 follow-up book has conditional default risks of 10% and 40%. Without the flag the bank forecasts 17.5% and lends, expecting €3.75. With the flag it lends only on the 75% no-default branch, which earns €45 conditional on that branch. Expected follow-up margin rises to €33.75. A pilot with an expected direct loss of €20 would therefore leave **€10 in expected net value**. If the two branches instead forecast 20% and 40%, both imply decline and the same calculation values the flag at €0.

At issue even the later common records are unknown. We transfer paired historical changes in the ordinary and peer risks to the loan’s current risk on the log-odds scale. We average the two-branch decision gain across those possible updates and multiply by the projected book principal. The projection uses the previous 12 complete months, including empty months. Historical analogs come from the same country when at least 12 exist. Otherwise all training episodes supply them. This separates projected portfolio size from the per-euro value learned on historically nonempty portfolios. If book size and the value of information move together, their product can misprice the pilot. The ledger also gives the estimated reduction in binary entropy, measured in **bits per future euro’s default indicator**, and the chance that revealing the flag changes the lending action. These quantities answer different questions about a single candidate. [Per-episode forecasts](../results/pilot_signal_ml_episodes.csv)

## What improved on the new period?

The full holdout spans October 2022 to May 2024. Its 48 nonempty portfolios comprise 1,200 loans, with 20 portfolios from Estonia, 20 from Finland and eight from the Netherlands. Brier loss measures the squared error of a probability against each binary outcome. We average within portfolios by principal, then equally across portfolios. Lower is better. [Evaluation code](../src/paper11/pilot_signal_evaluation.py)

| Forecast available to the lender | Mean Brier loss |
|---|---:|
| Historical country default rate at issue | **0.085503** |
| Boosted model with issue-time fields | 0.131082 |
| Add ordinary risk refresh | 0.122864 |
| Add other borrowers’ outcomes | 0.092839 |
| Joint model, pilot outcome hidden by averaging branches | 0.093275 |
| Same joint model, actual pilot outcome revealed | 0.093372 |

The ordinary refresh improved Brier by 0.008218 within the boosted models. Peer outcomes improved it by a further 0.030025. The primary paired improvement attributable to the pilot was **−0.000097** with a 95% block interval of **[−0.000469, +0.000262]**. Against the independently fitted shared-only model it was −0.000533. Replacing the pilot flag by an independent draw with the same fitted default probability gave 0.093291 in expected Brier loss, slightly better than revealing the real flag. The observed log-loss improvement was −0.000789 bits [−0.002512, +0.000828]. The test did not establish private predictive lift. [Metrics and alternative specifications](../results/pilot_signal_ml_metrics.csv)

With peer records hidden from both lenders, the pilot contributed +0.000196 Brier [−0.000582, +0.000944]. The later November 2023–May 2024 subset, which had no positions in earlier scored samples, gave +0.000071 with peers across 21 portfolios. It spans only three calendar quarters, too few for the prespecified four-quarter block interval. The full interval uses 2,500 paired resamples from seven quarters. In that full test, 29 pilots had appeared in earlier follow-up books, while all 1,200 follow-up loans were new to the scored positions. [Overlap and sample audit](pilot-signal-panel.md)

## Did an extra signal pay for a loan?

All 19 initially loss-making opportunities had positive estimated statistical information at issue, ranging from 0.000019 to 0.000129 bits. In every one, the predicted decision-switch probability and expected euro gain from information were zero. Eleven Spanish opportunities ultimately had empty follow-ups. All eight others were Dutch, a country absent from training. Among those eight, revealing the pilot’s actual flag also left the downstream ML action unchanged. [Eligibility and selection counts](../results/pilot_signal_ml_coverage.csv)

The earlier amount-aware selection rule funded two Dutch pilots, in March and May 2024. Giving that selector and the ML selector the **same downstream decision rule** isolates the issue choice. Cumulative direct cash less principal at the common cutoff was €0.00 and −€529.78 on the two pilots. The ML selector tied skipping every pilot at €0 and came out €27.88 ahead per eligible opportunity against the earlier choice [€0.00, €70.64]. Under the fixed two-payoff scenario, the earlier selector earned €135.20 in total and the ML selector earned €0. The May loan still carried €690.94 outstanding. Neither predictive nor monetary confirmation met the prespecified criterion. [Episode cash and balances](../results/pilot_signal_ml_episodes.csv)

## Could the model have spotted the earlier Finnish case?

For this retrospective exercise we refit using only 205 mature episodes available by March 2021, with 51 Finnish analogs. The latest training pilot dates to January 2019. Each number under “branch PD” uses the common records that became available at disclosure. The expected pilot margin and expected information value use only what was available at issue. [Finnish ML ledger](../results/pilot_signal_ml_finnish.csv)

| Finnish pilot | Expected direct margin at issue | Expected value of information | Branch PD, no default / default | Observed future default exposure |
|---|---:|---:|---:|---:|
| March 2021 | −€209.26 | €0 | 48.05% / 48.05% | 6.11% |
| November 2021 | −€150.78 | €0 | 36.41% / 36.41% | 24.43% |
| February 2022 | −€267.55 | €0 | 36.15% / 36.15% | 7.21% |

With peers visible the fit returned the same risk estimate for either possible pilot outcome at each of the three disclosures. It overestimated future default exposure in all three. Even with the peers hidden, the two branch probabilities differed by only about 0.43 percentage points and stayed above break-even in every case. Thus the boosted model missed the March opportunity too. The earlier structural replay explains why its March signal would have avoided a cash loss and why that same decision lost under the two-payoff scenario. [Finnish decision and cash walkthrough](finnish-pilot-cases.md)

The fit also assigned a **zero** probability of pilot default to three of the 48 scored primary episodes after clipping predicted probabilities to [0, 1]. One of those pilots defaulted. Across all 48 it forecast 10.33% pilot defaults on average and observed 12.50%. That error matters when valuing an event before it happens. Other uncertainties concern the assumed access to peer records, transfer of historical public risk changes, and country-specific lending shifts. The archive contains funded loans and a common cash snapshot. It supports paired policy replays under explicit assumptions. It cannot establish the causal return from issuing an otherwise rejected application or the lender’s actual motive.

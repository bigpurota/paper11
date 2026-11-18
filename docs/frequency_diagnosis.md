# Why did the historical frequency beat boosting?

The historical forecast already incorporated the most important change in Finland. It averaged **8.90%** across the 20 Finnish portfolios, whose eventual first-year default exposure averaged **9.24%**. The issue-time boosted forecast still averaged **38.44%**. These 20 portfolios account for **77%** of the aggregate Brier gap between frequency and boosting at issue. This is a retrospective diagnosis of the already-scored October 2022–May 2024 pilot origins. [Forecast-by-forecast error accounting](../results/frequency_diagnosis.csv) · [Training ranges and model response](../results/frequency_diagnosis_support.csv)

## What the frequency measures

Each month the bank counts all first-year defaults and all measured loans in the same country over twelve completed origin cohorts. At pilot issue in month $s$, their origination dates range from $s-24$ to $s-13$, allowing full first-year outcomes to arrive. With $D$ defaults among $N$ loans it uses $(D+0.5)/(N+1)$. The median eligible history behind the 48 forecasts comprised **28,603 loans**. Many histories overlap. The formula applies the latest mature evidence directly and estimates no coefficients. Large counts can make the estimate stable even as the estimate moves from one month to the next. [Timing and source definitions](pilot-signal-panel.md)

Boosting also received that frequency as an input. Its training set contained 232 completed country–month portfolios, with the latest pilot issued in August 2020. The target in each case was the first-year default share of *principal* among the first up to 25 loans thirteen months later. Each book had equal weight. The fit learned how contract features, country and historical frequency predicted that target on earlier books. A later monthly frequency could enter the tree at a different point, but nothing required the fitted output to follow that change one for one. The frequency and the target differ in cohort, borrower selection and weighting. A large denominator alone cannot guarantee an accurate forecast of this target. [Original estimator and design](pilot-signal-ml-protocol.md)

For a borrower whose true default probability is $p$, a forecast $f$ has expected Brier loss $p(1-p)+(f-p)^2$. The first term is the same for every forecast. A local count that tracks the current risk level can therefore beat a more flexible predictor that carries forward an obsolete level. Shared economic shocks, overlapping windows and a change in the borrower mix can also make that count unreliable.

## Where the errors occurred

| Country | Old training books | Actual exposure in training | Old test books | Actual exposure on test | Frequency at issue | Boosting at issue |
|---|---:|---:|---:|---:|---:|---:|
| Estonia | 124 | 15.89% | 20 | 8.74% | 13.46% | 14.89% |
| Finland | 58 | 36.90% | 20 | 9.24% | 8.90% | 38.44% |
| Netherlands | 0 | — | 8 | 4.79% | 27.19% | 37.62% |
| Spain | 50 | 53.06% | 0 | — | — | — |
| **All books** | **232** | **29.15%** | **48** | **8.29%** | **13.85%** | **28.49%** |

The old Finnish training cases had issue-time frequencies from 19.86% to 52.61%. Every Finnish test frequency lay below that range, from 7.37% to 12.26%. A tree ensemble predicts a constant beyond the range of a feature seen in training, so the boosted model could not follow the rate below 19.86%; the historical rate itself has no such limit. We reproduced all 48 old boosted issue-time forecasts from the original training rows, then changed only the Finnish frequency input. Setting it to the Finnish training median of 30.05% for every test contract gave a mean forecast of 39.28%. Restoring each contract’s actual frequency, 8.90% on average, moved the mean forecast to 38.44%. **A 21.15 percentage-point drop in the model input moved its output by just 0.84 points.** This calculation measures the fitted model's response with the remaining inputs held fixed. The data do not establish what caused the decline in Finnish defaults. [Reproducible input-change calculation](../src/paper11/frequency_diagnosis.py)

The Netherlands shows the limit of the frequency rule. Its eight historical denominators ranged from 59 to 693, and its mean forecast overshot the later target by 22.40 percentage points. A newer historical frequency at disclosure forecast 7.79%. The available data cannot separate small-sample variation, changing credit conditions and changes in the types of borrowers or loan sizes. [Per-country errors and updated forecasts](../results/frequency_diagnosis.csv)

## How much came from getting the risk level wrong?

For portfolio $i$, write $d_i$ for the realized default share of principal and $p_i$ for a forecast applied to each loan. Its principal-weighted Brier score equals $d_i(1-d_i)+(p_i-d_i)^2$. The first term is shared by every forecast applied to this book. Across the same books the second term decomposes exactly into the square of the mean forecast error and the variance of the errors around that mean. This is an accounting identity for realized errors. It measures neither estimator variance across hypothetical training sets nor calibration separately at every probability level.

| Error component | Frequency at issue | Boosting at issue | Boosting minus frequency |
|---|---:|---:|---:|
| Shared within-book component | 0.069944 | 0.069944 | 0 |
| Squared mean error | 0.003092 | 0.040812 | +0.037720 |
| Variance of centered errors | 0.012467 | 0.020326 | +0.007859 |
| **Brier loss** | **0.085503** | **0.131082** | **+0.045579** |

Getting the overall risk level wrong accounts for **82.8%** of the issue-time gap. Boosting was closer to the realized rate in nine of the 48 portfolios. Its Brier disadvantage was +0.041965 in the first 27 books and +0.050226 in the last 21. The full paired four-quarter block interval was [+0.039227, +0.053214], from seven observed quarters. For peer-informed boosting the gap against the issue frequency narrowed to +0.007336. Its centered errors were less variable, improving that component by 0.002732, but its higher mean error added 0.010068. [Country, period and paired intervals](../results/frequency_diagnosis.csv)

## Comparing forecasts available at the same date

| Information available | Direct frequency, Brier | Boosting using those data, Brier |
|---|---:|---:|
| At issue | 0.085503 | 0.131082 |
| Ordinary refresh at disclosure | 0.076466 | 0.122864 |
| Ordinary refresh and same-month peers, excluding the pilot | 0.076410 | 0.092839 |

The disclosure-time peer frequency is $(D_{peer}+20q_{fresh})/(N_{peer}+20)$, the same public input supplied to the old tree. The two disclosure comparisons use more recent information than the first row. The large improvement from peers *inside boosting* therefore coexists with a much smaller gain from adding peers to a competitive direct frequency. These direct-frequency comparisons were added after seeing the original results. They motivate testing an anchored correction on a separate period. [Frozen boosted results](pilot-signal-ml.md) · [All comparisons and dates](../results/frequency_diagnosis.csv)

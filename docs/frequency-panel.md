# Four new months of country-level lending decisions

The November 2026 Bondora workbook allows four more pilot months after the preceding boosting study ended in May 2024. A June 2024 pilot informs the July 2025 portfolio, whose first-year flags are measurable by August 2026. A September 2024 pilot informs the October 2025 portfolio, whose flags are measurable by November 2026. Each country contributes the first up to 25 loans at disclosure. The exact origin and follow-up dates, two candidate positions and historical-information requirements were committed before computing these episode outcomes. [Public protocol](frequency-protocol.md) · [Workbook and source definitions](pilot-holdout.md)

## Training as of 1 June 2024

An episode qualifies for training when its subsequent cohort has reached the first day of month s+26, its pilot's first-year flag is known and its nonempty continuation has a complete principal-weighted target. The panel retains 297 country-months with sufficient historical support through April 2022. There are 277 eligible training books across 144 distinct issue months. Estonia contributes 144, Finland 76 and Spain 57. The 20 other supported training episodes had empty continuations. Training uses the first loan each month. All training cash and outstanding balances are withheld. The transported October 2022 boosting model uses its earlier 232 training episodes. [Public training and test panel](../results/frequency_panel.csv) · [Original training cutoff](pilot-signal-panel.md)

## What the four test months contain

| Pilot country, June–September 2024 | Loans originated | Country-months | Months with ≥50 measured historical loans | First 25 follow-ups measured | Follow-up principal |
|---|---:|---:|---:|---:|---:|
| Estonia | 9,729 | 4 | 4 | 100 / 100 | €178,893 |
| Finland | 41,686 | 4 | 4 | 100 / 100 | €224,579 |
| Latvia | 1,346 | 4 | 0 | — | — |
| Netherlands | 10,142 | 4 | 4 | 100 / 100 | €212,576 |
| **Total** | **62,903** | **16** | **12** | **300 / 300** | **€616,048** |

The previous grade-based study reported 4,400 missing first-year flags among 64,259 loans issued across all countries in the continuation months. The 300 particular positions selected by this portfolio rule have complete labels and cash. €53,056 of their original principal belongs to loans with measured first-year defaults. Within each book, scoring weights the 25 loans by original principal. The final average gives the twelve books equal weight. The public table includes the known default principal and the principal whose flag is missing separately, making both extreme completions computable for a partially observed book. [All scheduled country-months and candidate availability](../results/frequency_panel_coverage.csv) · [Earlier broad coverage table](../results/pilot_holdout_cohort.csv)

In each of the 12 supported country-months the 26th loan was available as a second possible pilot. **All 12 first loans and all 12 loans in position 26 had no recorded default within one year.** Both positions use the same 300 follow-ups. Each has 61,545 measured peer flags available across the 12 episodes, after excluding that specific pilot. The sensitivity estimates how the model treats a different actual loan in the same initial month and book. Its 12 comparisons add no independent follow-up portfolios. [Two candidate definitions and peer exclusion](../src/paper11/frequency_panel.py)

One opportunity met the original issue-time direct-loss criterion, the Netherlands in June 2024. Its country-level default probability was 20.86%, above the 18.18% break-even threshold. The first candidate had principal €2,704, cash of −€1,755.43 at the snapshot and €2,343.40 principal outstanding. The 26th had principal €936, cash of −€435.80 and €626.35 outstanding. The fixed legacy rule skipped the first and selected the 26th. Final cash profits on these still-open positions can differ from the archived balances. [Episode-level positions and outcomes](../results/frequency_panel.csv)

## What had appeared in earlier calculations?

The earlier grade-based analysis had already reported the counts and missingness of these four origin and continuation months. It could form zero comparable country–grade portfolios in the origin window. The subsequent country-level study had tested earlier origin months, with continuations through June 2025. We reconstructed the source positions of all earlier country and grade episodes recorded in their public panels. Source workbook order breaks exact contract ties after the original deterministic timestamp and contract-key ordering. Borrower identity across different positions is unknown. [Earlier country-level study](pilot-signal-panel.md) · [Earlier grade screen](pilot-holdout.md)

| Earlier records among the two later replays | First candidate | Candidate 26 |
|---|---:|---:|
| Candidates previously used as pilots | 0 / 12 | 0 / 12 |
| Candidates previously used in a continuation | 8 / 12 | 0 / 12 |
| Other loans in the pilot's cohort previously used as individual positions | 192 | 200 |
| New continuation positions previously used as pilot or continuation | 0 / 300 | 0 / 300 |

All eight repeated candidates came from Estonia or Finland, four in each. In those eight months the former top-25 portfolios contributed 24 other loans per month when the first candidate was held out, or 25 per month when the 26th was held out. No earlier grade episode contributed an overlapping position. The broader archive was available previously. The new information here consists of previously unevaluated portfolio targets and locked comparisons on the four later months. [Overlap audit and invariance tests](../tests/test_frequency_panel.py)

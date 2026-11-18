# What did the first payments tell a different bank?

The six-month signal changed 16 of 143 simulated issuance decisions at a risk cutoff of 18.18%. Its mean squared probability error was slightly lower than the historical regional rate and higher than the rate in the rest of the bank. Both paired confidence intervals included zero. The external test therefore did not establish a forecasting gain over both benchmarks. The rule, period, outcome, success criterion and payoff assumptions were [published before opening the Czech repayment outcomes](https://github.com/bigpurota/paper11/commit/e573d375231c034a1931909b053a33cf80d10742). [Original protocol](early-warning-protocol.md)

## Source and clock

The PKDD'99 archive contains dated account transactions and monthly instalments on 682 loans from one anonymized Czech bank. The unit of the test is all observed loans originated in an account region during one month. January 1996 through December 1997 contributed 313 loans, eight regions, 24 calendar months and 143 nonempty region–months. All 143 had local and outside history. Total original principal was 49,049,040 CZK. The median book contained two loans and the largest contained eight. [Czech Technical University's repository](https://relational.fel.cvut.cz/dataset/Financial) · [Originator's field dictionary](https://github.com/jlacko/berka-dataset/blob/77e9972a1ead107e5f42a91dd989d587bff055a4/Financial%20Data%20description.pdf) · [Counts and excluded books](../results/early_czech_coverage.csv)

The loan table gives the date granted, monthly instalment and original principal. Each loan links to a single account, and no account has two loans. The transaction purpose code UVER identifies a posted loan payment, and all 13,580 such transactions are VYDAJ debits. The archive contains 1,056,320 transactions in all. The permanent order table contains instructions to pay, so those orders do not count as receipts. The loan's eventual A–D account status is never loaded. [Data reader and date filters](../src/paper11/early_czech.py)

Month one is the first complete calendar month following origination. Payments from the day after origination through the end of each landmark count, including any posted in the remainder of the origination month. A two-instalment shortfall at month end k means the sum of posted payments is at most (k−2) scheduled instalments, with 0.005 CZK tolerance. A year-one event is any such shortfall at the ends of months 2 through 12. The primary early event uses months 2 through 6. The secondary marker flags at least one instalment short at the end of month three. These reconstruct cash shortfalls. Precise contractual due days, late notices and losses on default are unavailable. Eight test loans had no tagged debit by month three. One of the 1,005 early debits left the customer's account balance negative. A posted debit can draw on an overdraft.

By month six, 15 of the 24 loans that would ever reach the year-one shortfall had already done so. The three-month marker flagged 17 of 313 loans. Twelve of these 17 had a year-one shortfall, versus 12 of the other 296. Eleven of the twelve events among the flagged group had already occurred by the end of month three. A post-test landmark diagnostic excludes all eleven loans that already had the event: one of six remaining flagged loans and twelve of 296 unflagged loans went on to experience their first two-instalment shortfall in months 4–12. The small six-loan group limits interpretation of genuinely new events. These same-loan measurements differ from forecasting a future regional book. [Landmark event counts](../results/early_czech_coverage.csv)

## Can a new regional book be priced in advance?

Each issue date uses loans from 13–24 months ago to relate six-month to twelve-month shortfalls. Newer originations from 7–12 months ago supply only six-month signals. Across the evaluated books the median regional sample contained 12 mature loans and seven younger loans. No region had sufficient mature shortfalls of its own to fit the conversion. On 78 dates and regions combined, the prespecified fallback used the bank-wide conversion and the younger local experience. On the other 65 it retained the mature local frequency. The three-month estimator retained the local rate in 72 books with an empty local marker class or an empty newer sample. [All forecast inputs by issue date](../results/early_czech_episodes.csv)

| Forecast | Mean individual Brier, equal region–months | Mean forecast |
|---|---:|---:|
| Mature local region | 0.086055 | 10.98% |
| Mature other regions | **0.081057** | 7.22% |
| Six-month shortfall conversion, primary | 0.085173 | 9.56% |
| Three-month instalment marker, secondary | 0.085375 | 10.25% |

The realized event fraction averaged 8.82% across equally weighted region–months. Across individual loans it was 24/313 (7.67%). The six-month rule improved Brier by 0.000881 relative to the local rate (95% interval −0.001560 to +0.003414) and by −0.004117 relative to the rest of the bank (−0.009846 to +0.001886). Paired resampling used 2,500 circular draws of four-month calendar blocks, keeping all regions together. [Forecast scores and paired intervals](../results/early_czech_metrics.csv)

The rule flagged risk below both baselines in 43 of 143 books. This was correct 38 times and incorrect five times. Across all books 120 of 143 realized rates fell below both baselines, all 120 because the book contained zero shortfalls. Precision was 38/43 (88.4%) against a base rate of 120/143 (83.9%), and the rule captured 38/120 (31.7%) of those cases. The secondary marker raised 11 flags, nine correct. Small books and rare events make a high fraction of correct downward calls possible even with a weak risk model. [Flags, misses and base rates](../results/early_czech_direction.csv)

## Did it alter issuance?

| Margin on non-event / event | Comparator | Additional books | Dropped books | Additional / dropped loans | Change in modeled margin, CZK |
|---|---|---:|---:|---:|---:|
| +10% / −45% | Local | 13 | 3 | 24 / 13 | +10,581.00 |
| +10% / −45% | Other regions | 0 | 13 | 0 / 28 | −212,787.60 |
| +3% / −50% | Local | 10 | 5 | 18 / 25 | +108,534.48 |
| +3% / −50% | Other regions | 29 | 33 | 55 / 64 | −233,479.20 |

Two of the first switches occurred in May 1997. In east Bohemia the mature local history had two year-one shortfalls among 12 loans. None of five newer loans had a six-month shortfall. The risk estimate fell from 19.23% to 12.82% and the model switched to funding one loan of 50,112 CZK at the 18.18% cutoff. It subsequently avoided the year-one shortfall. In north Moravia, two six-month shortfalls among 12 young loans raised the estimate from 3.57% to 25.00%. The model would have declined four loans, all of which avoided the year-one shortfall. These two directions occur under the same rule on the same date. [Monthly replay inputs](../results/early_czech_episodes.csv)

The policy evaluates the same funded books under alternative probability forecasts, prices every event/non-event at the stated fractions of its original loan principal, and aggregates across loans. The two pricing scenarios and both benchmarks reuse the same loans. They are separate comparisons and their payoffs cannot be added. Actual bank choices for declined applicants, recovery, prices and funding costs are unobserved. [Every primary and secondary policy comparison](../results/early_czech_policy.csv)

The archived challenge copy and the pinned mirror contain all eight original ASC files byte for byte. An independent CSV reader and integer calendar reconstruction using the archived original reproduced all 143 books, classifications, individual-loan Brier differences, four-month confidence intervals and 16 signed policy contrasts. Tests vary future annual outcomes and immature landmarks while holding the issue-date observations fixed. [Original archive](https://web.archive.org/web/20070214120527id_/http://lisp.vse.cz/pkdd99/DATA/data_berka.zip) · [Downloadable mirror](https://github.com/jlacko/berka-dataset/tree/77e9972a1ead107e5f42a91dd989d587bff055a4) · [Reference tests](../tests/test_early_czech.py)

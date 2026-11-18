# When can early repayments reveal that both historical rates are too high?

Suppose the old local risk is L and the historical rate in other areas is G. Even perfect weighting cannot push their average below the smaller rate. A lender can instead ask a question about the new borrowers already on its books: *how many have reached a serious payment problem at the same age as earlier borrowers?*

## A threshold the lender can compute at issue

Let h be the estimated share of year-one events that were already visible at six months in mature loans. Let e out of n younger loans have the six-month event. The rule annualizes their event count, then averages that estimate with ten observations at the old local risk. Before clipping to one, the forecast is

$$p=\frac{e/h+10L}{n+10}.$$

Dividing by $h$ is the development-factor step of the chain-ladder method from loss reserving (Mack, 1993, *ASTIN Bulletin* 23(2)), applied to default counts; credit analysts draw the same curves as vintage or seasoning curves. The contribution here is the warning threshold and its external test, not the conversion itself.

With positive support and interior benchmark rates, the warning that both histories overstate risk is equivalent to

$$e<h\big[(n+10)\min(L,G)-10L\big].$$

For example, suppose the old forecasts are 25% and 15%, half of annual events used to be visible at month six, and 80 younger loans have reached that age. The bank flags both forecasts when it sees **five or fewer early events**. Five gives a forecast of 13.89%, whereas six gives 16.11%. The rule, support fallback, age windows and thresholds were fixed before opening the external outcomes. [Published protocol](https://github.com/bigpurota/paper11/commit/e573d37) · [Shared implementation](../src/paper11/early_warning.py)

The estimate assumes the fraction visible by six months transfers to younger cohorts. Later collection, an altered default definition or slower deterioration can delay recorded events. A low count can then coexist with unchanged year-one risk. Lending on the estimate also requires the new cohort to resemble the recently observed cohort. The Netherlands replay asks about a portfolio a further thirteen months away.

## What actually transferred?

The Dutch six-month curve predicted 7.17% on average against later default exposure of 4.79%. Old local and outside rates were 27.19% and 13.36%. Six of its seven warnings were correct. However, those younger cohorts that supplied the early indicators eventually had a mean first-year count rate of 14.11%; seven of the eight nowcasts undershot their own cohort. Had the conversion measured them exactly, it would have warned on four dates, three of them correctly, so half of the correct warnings came from the undershoot offsetting a further fall in risk. The later 4.79% target belongs to different loans. A separate signal based only on dated full payoff in the first 90 days gave 27.29%. In November the original calibration count suggested that 52 of 72 annual defaults were visible by month six. Only 25 of 86 annual defaults in the younger group were actually visible that early. The available payment snapshot can document cash and outstanding arrears at its own date, after these eight forecasts. [Dutch measurements and dates](early-dutch.md)

At the Czech bank the first three months of *the same loan* carried substantial information: twelve of seventeen loans a full instalment short at month three reached a two-instalment shortfall during the first year, compared with twelve of the other 296. Eleven of those twelve marked cases had already reached the serious event by month three. A post-test check restricted to loans still at risk gives one later event among six marked loans and twelve among 296 unmarked loans. The small marked group limits any claim about predicting a new problem. At origination the bank only has this information for *previous* borrowers. On 143 new region–month portfolios, six-month warnings identified 38 of 120 portfolios that finished below both rates, with five false alarms. The median portfolio held two loans. Few realized events and positive smoothed benchmarks explain the high base rate. The pooled historical forecast had the smallest Brier loss of the four methods on this population. [New lender and ledger audit](early-czech.md)

At an 18.18% assumed break-even risk, updating from the local Czech history changed sixteen decisions. Thirteen additional portfolios would be funded and three declined, improving the scenario payoff by CZK 10,581 relative to the local rule. Compared with the other-region rule it declined thirteen additional portfolios, lowering scenario payoff by CZK 212,788. The signal changed the policy; its financial value depended on which information the lender already used. Outcomes and amounts belong to issued loans and the assumed margins price a payment shortfall. [Paired scenario ledger](../results/early_czech_policy.csv)

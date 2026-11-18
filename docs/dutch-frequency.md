# Why the Dutch historical forecast was 27% and the next books were near 5%

The Dutch rate came from the first six active origination months available in the workbook. When the bank had to forecast, only one to six of those months had mature first-year outcomes. Three consecutive forecasts reused the same **73 defaults among 245 loans**, giving 29.88% after half-count smoothing. By the later test months the first-year default frequency of the country's entire financed book averaged **4.10%**. That decline accounts for almost the entire error. These are descriptive checks of the eight previously scored Dutch portfolios, selected for investigation after their forecast errors were known. [Earlier comparison](frequency_diagnosis.md) · [Reconstruction by forecast date](../results/dutch_frequency_episodes.csv)

## The two denominators

For each pilot origin month $s$, the historical forecast $(D+0.5)/(N+1)$ counts defaults among all Dutch loans with known first-year outcomes originated in months $s-24$ through $s-13$. Each loan counts once. The outcome is the default share of original principal among the first 25 funded loans in month $s+13$. The published 27.19% and 4.79% give the eight country-months equal weight. [Original date and sampling rules](pilot-signal-panel.md)

| Pilot month | Mature months with loans | Historical defaults / loans | Local forecast | Recent originations / historical originations¹ | First-year defaults among next 25 | Defaulted share of next principal |
|---|---:|---:|---:|---:|---:|---:|
| Oct 2023 | 1 | 16 / 59 | 27.50% | 71.4× | 2 | 5.88% |
| Nov 2023 | 2 | 73 / 245 | 29.88% | 18.1× | 0 | 0.00% |
| Dec 2023 | 2 | 73 / 245 | 29.88% | 19.5× | 2 | 3.34% |
| Jan 2024 | 2 | 73 / 245 | 29.88% | 21.3× | 2 | 8.08% |
| Feb 2024 | 3 | 75 / 265 | 28.38% | 21.6× | 0 | 0.00% |
| Mar 2024 | 4 | 86 / 337 | 25.59% | 18.7× | 1 | 2.40% |
| Apr 2024 | 5 | 107 / 460 | 23.32% | 15.2× | 0 | 0.00% |
| May 2024 | 6 | 160 / 693 | 23.13% | 11.2× | 2 | 18.63% |

¹ Both volume counts are available at issue. The numerator covers the preceding twelve complete origination months. The denominator covers the twelve-month range used for mature performance. September and October 2022 supplied the first 245 recorded Dutch loans. The archive contains no November or December 2022 Dutch originations. The earliest measured loans therefore kept disproportionate weight even as new lending grew. Across all eight overlapping historical windows there are 693 distinct recorded loans. [Monthly credit vintages, including empty months](../results/dutch_frequency_vintages.csv)

Bondora reported that it launched Dutch lending on **23 September 2022**, paused originations for further testing and reopened in January 2023. These dated announcements were available before the first forecast in October 2023. They establish that the first 245 contracts came from an opening run before a pause. They provide no estimate of how much a change in underwriting affected the later default rate. [Launch announcement](https://goandgrow.eu/en/blog/netherlands-is-live-celebrations-as-bondora-launches-new-market/) · [Quarterly account of the pause and reopening](https://goandgrow.eu/en/blog/2022-q4-go-grow-portfolio-review/)

The outcome months are November 2024 through June 2025. The eight capped portfolios contained 200 loans and nine first-year defaults. Defaulted loans accounted for €18,928 of €401,648 original principal, or 4.71% if all euros are pooled. Averaging the eight individual books' default exposure shares gives the original 4.79%. Among **all 16,621 Dutch loans** in these months, 687 defaulted within one year. All first-year flags were measured. The pooled count rate is 4.13%; the mean of the eight monthly count rates is 4.10%. The mean monthly default share by principal across the entire book is 4.63%. [Month-level counts, face values and losses](../results/dutch_frequency_episodes.csv)

## What explains the 22.40 percentage-point error?

Subtract one rate at a time, on the same eight months. Within each row, subtract the second rate from the first. The sum equals the published forecast minus its realized target.

| Component | Difference, percentage points |
|---|---:|
| Half-count smoothing of the historical frequency | +0.11 |
| Earlier entire Dutch book by count (27.08%) minus later entire book by count (4.10%) | **+22.98** |
| Later entire book by count minus the first 25 by count (4.50%) | −0.40 |
| First 25 by count minus the first 25 by principal (4.79%) | −0.29 |
| **Total, before rounding** | **+22.40** |

This identity compares two populations of issued loans separated in time. It makes no statistical independence assumption about the eight overlapping histories. Although the first 25 had only nine defaults, the much larger subsequent book confirms that the low rate extended beyond the chosen positions. [Exact unrounded components](../results/dutch_frequency_episodes.csv)

## Did loans simply become smaller or shorter?

Pool the 693 distinct historical loans across the six active mature months only once. These had 160 defaults (23.09%). This pooled percentage gives more weight to later, larger historical vintages than the eight forecasts above. All historical amounts exceeded €1,000, while 7,964 of the 16,621 subsequent loans had principal at most €1,000. Borrowers' contract terms changed as well. Among 60-month loans alone, which formed the largest earlier group, the first-year rate fell from **144/543 (26.52%)** to **341/7,247 (4.71%)**.

As a retrospective check use each exact historical contract term and face-value bands up to €1,000, €1,000–2,000, €2,000–5,000 and above €5,000. Each nonempty historical cell has later observations. Weight the seven later cell rates by the historical counts. At the historical term and amount mix, the later default rate would still be **4.60%**. Fixing those two visible dimensions leaves a large decline. Earlier loans had no recorded risk grade; all later loans did. The workbook does not identify which changes in customers, underwriting, economic conditions or reporting produced the remaining difference. [Stratum counts, weights and standardization](../results/dutch_frequency_contract_mix.csv)

## What was visible before the results?

The lender could see concentrated mature history, repeated vintages and an 11- to 71-fold expansion in issuance. These facts warn that the local history covers the startup book of a rapidly growing market. They do not reveal the direction of the next risk change. A donor-only forecast using the same mature window and half-count on measured loans from every other country averaged **13.36%**. It was closer on average, yet still roughly eight percentage points too high. Once later ordinary outcomes arrived, the refreshed Dutch frequency averaged **7.79%**. They were unavailable for the original issue decision. [Local, donor-only and disclosure-time series](../results/dutch_frequency_episodes.csv) · [Mature counts by donor country](../results/dutch_frequency_donors.csv)

The fixed weighting rule moves the mean historical forecast to **22.29%**. It assigns the local rate more than half the weight on seven of the eight dates. The broader rate was closer to the observed target on seven dates. The Dutch cases motivated the rule, so we tested the published rule separately on state portfolios of Wells Fargo. [Weighting rule](local-trust.md) · [Eight retrospective forecasts](../results/dutch_trust.csv) · [Wells Fargo test](local-trust-bank.md)

There is a limit to what changing the weights could have achieved. A weighted average with weights between zero and one always lies between the two forecasts. In seven of eight portfolios the realized share fell below both the Dutch and the other-country rate. Only the May pilot's later portfolio landed inside the interval, at 18.63%. Even choosing each month's weight after seeing the outcome leaves a mean absolute error of at least **9.14 percentage points**. To reproduce this lower bound, measure the distance of the later share to the interval between the two forecasts (zero inside) and average over the eight books. The lender could see how far apart the forecasts were at issue. Knowing that both would overshoot required future outcomes. [Monthly inputs](../results/dutch_trust.csv)

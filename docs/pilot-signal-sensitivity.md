# How much did the Estonian switches depend on one private signal?

The original Bondora rule selected ten pilots in its extended cohort. Three of their defaults changed the subsequent lending decision at the assumed prior strength of 20. Under two alternative information assumptions, the same ten pilots produced zero switches. This retrospective sensitivity keeps the ten origination choices fixed throughout. It varies only the information used for the follow-up decision in month 13. [Original ledger and design](lender-pilot.md)

## How much weight does the bank give one default?

The binary scenario pays 0.10 for repayment and −0.45 for default per unit of principal. Lending is profitable below the break-even default probability of 18.18%. Let $q$ be the refreshed historical rate and $S$ the effective prior strength for the follow-up cohort. A pilot default updates the rate to $(S q+1)/(S+1)$. If $q<b=0.10/0.55$, a default changes a lend decision to a decline when $S\le(1-b)/(b-q)$. The rule declines at exact break-even.

| Estonian returning customers | Historical loans behind refreshed rate | Refreshed PD | PD after default, S = 10 | S = 20 | S = 40 | Largest S for this switch |
|---|---:|---:|---:|---:|---:|---:|
| October 2018 | 10,008 | 15.76% | 23.42% | 19.77% | 17.82% | 33.80 |
| November 2018 | 10,466 | 15.45% | 23.14% | 19.48% | 17.52% | 29.99 |
| February 2019 | 11,317 | 15.01% | 22.73% | 19.05% | 17.08% | 25.77 |

The historical counts estimate risk in past cohorts. The effective strength sets how precisely those past cohorts describe the risk shared by today's pilot and future borrowers. Strength 20 assigns a single default a weight of 1/21. Strength 40 assigns it a weight of 1/41. The archive supplies the historical counts. The assumed strength determines how much a single signal can move the decision.

## What if other loans provide the same information?

By month 13 the other funded loans in the pilot's country, customer group and origination month have also aged twelve months. The original comparison makes this entire group unavailable to the baseline bank. Suppose both banks can instead see every peer's one-year default flag by the follow-up decision. They still differ only in access to the pilot. With $d$ defaults among $n$ peers, the baseline rate becomes $(S q+d)/(S+n)$. The informed lender also adds the pilot outcome to its numerator and one to its denominator. This common-feed scenario gives each peer one effective observation under the same shared-risk model. The date the banks could actually obtain these records is unknown.

| Same-month peer information shared by both banks | Switches at S = 10 | S = 20 | S = 40 |
|---|---:|---:|---:|
| No same-month peers | 3 / 10 | 3 / 10 | 0 / 10 |
| All other funded loans in the same cell | 0 / 10 | 0 / 10 | 0 / 10 |

At strength 20, the October cohort supplied 163 peer defaults in 1,156 loans. The future group's estimated risk moved from 14.13% to 14.20% when the bank learned of the pilot default. In November the corresponding move was 16.24% to 16.32% (157/966 peers), and in February it was 17.42% to 17.50% (186/1,065). Both banks would lend in all three cases. Each pilot's incremental information then contributed zero to the paired portfolio decision. The historical receipts from these loans stayed the same. The two recorded cash recoveries therefore depend on the information the baseline would have received under the counterfactual policy.

The six settings above are a sensitivity analysis on the discovery cohort. They supply neither a fitted strength nor an estimate of how often another bank has access to such a feed. The [episode-level results](../results/pilot_signal_sensitivity.csv) report all 60 comparisons. After generating the original Bondora episodes, run `PYTHONPATH=src .venv/bin/python -m paper11.pilot_signal_sensitivity` to recreate them.

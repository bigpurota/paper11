# Follow-up design, 18 November 2026

Implementation and experiments: Andrey Tsember. These extensions were designed after the initial replication and its public-cohort results were known. The initial release is commit 54af173. The additional comparisons are exploratory.

## How much forecast error comes from selection versus time?

Hold a Prosper scorecard and a reject prior fixed after fitting on observed outcomes for first loans originated through December 2007. Forecast all twelve full quarters from 2010 Q1 to 2012 Q4. For each forecast, take the latest twelve-month history that has completed a further twelve months of repayment follow-up by the forecast origin. No outcome of that forecast quarter enters a forecast. Eligibility, horizon, scorecard, approval rule and estimand stay fixed.

Estimate 20–40% integrated ABR on the mature history via accepted labels, Bayesian completion, and known-propensity reweighting. After forecasts are saved, split each error into masked-history estimation error and the change in full-label ABR from history to future. A full-history oracle is a retrospective benchmark. Report equal-quarter RMSE, counts of paired wins, leave-one-quarter-out ranges, and the covariance cross-term in the squared-error identity. Overlapping histories and only twelve calendar quarters do not support iid quarter p-values.

## Is a change in underwriting justified by the visible outcomes?

On the established Taiwan and Prosper splits, compare 35/40/45/50% approval targets to a fixed 30% incumbent. For a unit loan at 10% interest and 50% LGD, bound incremental margin per applicant using paired decisions. Historical outcomes stay fixed wherever observed. Compare unrestricted missing-label bounds with conditional expected values if individual default odds can vary within a factor of the prior. Use the fixed grid of Γ = 1, 1.25, 1.5, 2, 3, 5, 10 and unrestricted. Review zero and 0.25 percentage point downside allowances. Select with the validation sample and freeze the numerical cutoff before applying it to the test. Report dependence on assumptions and abstentions.

## What does an actual randomized offer identify?

The independent Philippine microcredit study supplies randomized offer assignment, actual loan receipt and lender cash flows among marginal applicants. Check denominators, noncompliance and the accounting definitions against the data producers. Compare offer arms within the original score windows, then standardize to the available analysis population. Report uncertainty and sample selection. Funding an account, incurring a cash shortfall, and defaulting under a contractual definition are separate outcomes. Published assignment/take-up aggregates provide external reference checks. This dataset tests interpretation of randomized access outside Monedo; it does not provide the Spanish applicant panel.

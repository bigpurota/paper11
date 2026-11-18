# Can better measurement of historical risk improve the next-quarter forecast?

## What the lender can know

Imagine standing at 1 January 2011. The validation history covers loans originated during 2009. All of those loans have had twelve months to produce the target before the forecast date. For this experiment 2010 originations are still inside the fixed one-year embargo. The forecast concerns 2011 Q1. Repeat the same rule at every quarter start from 2010 Q1 to 2012 Q4. Each test borrower appears in one forecast quarter. Later windows may use earlier cohorts once their outcomes mature.

The model and logistic prior were fit on artificially observed first Prosper loans originated through 2007. Both remain frozen to isolate changes in evaluation. The row filters, twelve-cycle default endpoint and underwriting model use the same conventions as the primary experiment. A seeded Bernoulli draw gives each historical record a fixed disclosure decision across all twelve origins. The longer calendar input includes intervening dates omitted by the primary four-way split, so its simulated decisions can differ on previously reported test borrowers. Evaluation is conditional on first funded accounts in the retrospective extract.

At each origin we predict the bad rate under a quota-based lending policy, averaged uniformly across acceptance rates of 20–40%. Each portfolio ranks its own population with the fixed scorecard. Its numerical score cutoff can change with the borrower mix. The forecast function sees only matured, visible historical outcomes and historical scores. It takes no future applicant features or labels. An accepted-only forecast reranks visible borrowers; the Bayesian calculation keeps the risk ranking of the full history and fills missing outcomes from the prior. Logged IPW uses the known disclosure probabilities in this controlled experiment.

## Accounting for the forecast error

Let E be the estimate from visible history, H the actual ABR of that same history if all hidden labels are revealed, and F the actual ABR of the subsequent test quarter. The error equals (E − H) + (H − F). The first term measures historical estimation error under selective disclosure. The second measures cohort-to-cohort variation in the full-label metric, including sample noise and changes in the borrower mix or outcomes. Only E would have been available to a lender. We reveal H and F for the audit.

An estimator can make a smaller first error yet make a larger total error. Across quarters, mean squared forecast error is mean squared historical estimation error plus mean squared historical-to-future change plus twice the mean product of the two errors. The last term can be negative. Calling all historical-to-future variation structural economic drift would require additional evidence.

## What happened

Using Bayesian completion lowers history RMSE from 0.786 to 0.261 percentage points. When forecasting the upcoming quarter, RMSE increases from 2.075 to 2.357 percentage points. The correction wins on absolute error in seven of twelve quarters. The remaining misses are large enough to reverse the overall RMSE ranking. Leaving out each quarter in turn preserves the sign of the squared-error comparison. IPW has the smallest history error (0.170 percentage points), but also fails to improve future RMSE.

Even knowing the exact historical ABR gives a future RMSE of 2.268 percentage points. Accepted-only error partly cancels subsequent cohort variation in this period. A bank cannot rely on that cancellation recurring. The quarterly exercise covers one lender, only twelve nonoverlapping target periods and overlapping histories. It is descriptive evidence about temporal transfer, not a universal ranking of evaluators or a calendar-independent significance test.

[All quarterly estimates](../results/vintage_forecasts.csv) · [Summary and leave-one-quarter-out checks](../results/vintage_summary.csv) · [Forecast chart](../results/vintage_forecasts.png)

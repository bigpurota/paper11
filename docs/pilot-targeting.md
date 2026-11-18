# Can the bank identify promising pilots before origination?

## Evaluation design

We fix the prediction evaluation before scoring the two transfer portfolios. For each eligible opportunity the candidate loan has negative expected direct margin at the decision date. Rank opportunities using the model's net pilot value computed with information available on that date. Choose a pilot exactly when that forecast is positive. The score and threshold are fixed before following up. No ranks or cut points from the evaluation portfolio determine actual selections.

The primary target for this diagnostic is the paired realized gain from a forced pilot relative to running the same updated lending strategy without a pilot. Each eligible observation is an opportunity to act. For scoring a policy, skipping a pilot contributes zero incremental margin. We compare net value per eligible opportunity against both skipping all and piloting all. The difference between the average realized gain on selected and skipped opportunities measures targeting. A rank AUC compares predicted scores for opportunities with positive and nonpositive net gain, giving ties half credit. Rank AUC grades relative ordering, while a positive policy gain grades the economic threshold. We report an undefined comparison when an arm or outcome class is empty.

The more demanding outcome asks whether a directly loss-making pilot changed the subsequent action and its incremental gain still exceeded the loss. The empirical studies record this separately. A positive net on a directly profitable pilot is insufficient evidence for the stronger claim. When randomized choices are integrated, an episode mean and a realized individual loan are different units. For cross-study comparisons we report the unit used for each study. Moving-block intervals resample calendar periods jointly across groups. The diagnostic is retrospective and the factual bank policy is generally absent from funded-loan archives.

## Forecasting the public information that arrives while the bank waits

Before reading either new holdout's results, we fixed a second forecast. At each pilot date, collect all earlier scheduled groups from the same archive whose public follow-up update was available by that date. Use one observed log-odds change per group (the change between its initial risk and its public updated risk). Once eight distinct earlier pilot dates have matured, apply that historical distribution of changes to today's starting odds. Recenter on the log-odds scale so the mean future risk equals today's risk; this enforces the forecasting model's marginal probability for the binary pilot outcome. Compute the one-label value separately at each possible public risk, optimized against the updated no-pilot action, and average. Before warm-up the second forecast uses the original fixed-risk model. It never uses earlier pilots' realized profits or later dates to fit or select its rule. The approach translates past variation in public estimates into a distribution for the risk facing the lender on the disclosure date. Changes in applicant mix or risk may make this distribution an imperfect forecast. We compare it on exactly the same opportunities, and report the number of eligible decisions with a mature history.

## What can be known at issuance?

For the fixed-risk rule, let the planned loan earn r on repayment and lose L on default. Its break-even default probability is b = r/(r+L). With a beta prior of strength S, a non-default on one pilot moves the forecast q to S q/(S+1). A loss-making pilot can change a later refusal to funding only when

$$
 b < q < b(1+1/S).
$$

Even inside this band the expected gain must pay for the pilot. With H separately selectable follow-up loans with the same updated risk estimate, no intervening public update and no discount, the exact inequality is

$$
 H (1-q) [b-Sq/(S+1)]_+ > q-b.
$$

For the Bondora scenario (+0.10 on repayment, −0.45 on default, S=20), the decision-change band starts at 18.18% and ends at 19.09%. This is a screen for the fixed-risk forecast at issuance. Future public data can move a borrower group into or out of the band before the pilot is observed. A pilot also cannot add value to decisions for which the lender receives no new applications.

## What the forecasts achieved

The US transfer covers 120 region-quarters. At the original 504 price the rule chose no 7(a) pilot. The table gives the separately specified price estimated using only early 7(a) disbursements. For Bondora it uses the primary cohort with at least three years of follow-up in the first snapshot. AUC labels refer to positive *total* margin from the pilot and subsequent switch. Net gain is the value of the selected policy relative to skipping all pilots, averaged across all eligible episodes (including those skipped), in units per 100 principal on one loan. US results here use the fixed borrower draw. Averaging over every permissible draw gives a different estimand.

| Archive | Forecast at issuance | Selected / eligible | AUC for positive net (95% block interval) | Mean policy gain vs no pilot |
|---|---|---:|---:|---:|
| US 7(a), early local terms | Fixed risk | 16 / 85 | 0.416 [0.206, 0.624] | −0.691 |
| US 7(a), early local terms | Future public updates | 24 / 85 | 0.418 [0.162, 0.636] | −0.529 |
| Bondora, primary scenario | Fixed risk | 2 / 100 | 0.609 [0.478, 0.734] | +0.200 |
| Bondora, primary scenario | Future public updates | 6 / 100 | 0.607 [0.477, 0.724] | −0.500 |

Neither forecast reliably discriminated profitable total outcomes in both primary tests. On the European primary test, both fixed-rule pilots produced positive direct margins, but neither pilot changed a later decision. Both forecasts had zero observed instances of recovering a direct scenario loss through a switch in these two tests. Improving the assumed model of the future public information did not remove this empirical limitation. Only 19 eligible US opportunities had eight mature prior dates for the new forecast. All 100 primary European opportunities had enough history.

In the broader EU panel, two of the ten pilots selected by the fixed rule covered a cash loss via a switch as of May 2024. They concern neighboring months in the same group of returning Estonian customers. A third earlier apparent win reversed as later borrowers made payments. The interval for the mean euro gain across all 228 eligible opportunities spans zero. A strong rank statistic on two events from one segment would give little basis for transport to another bank. The later date is a retrospective remeasurement of the original policies, not a new selection test. [Matched cash and collection sensitivity](lender-pilot.md) · [US outcome branches](pilot-transfer.md) · [All scores and selections](../results/pilot_targeting_forecasts.csv) · [AUC, policy value and estimable bootstrap counts](../results/pilot_targeting_summary.csv)

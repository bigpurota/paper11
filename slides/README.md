# Paper 11 presentation

Open [the PDF](paper11.pdf) for projection. The [PowerPoint](paper11.pptx) has editable tables and timed speaker notes. The talk takes 15 minutes across 14 slides. Slides 15–34 are for questions.

## Fifteen-minute speaking plan

| Elapsed time | Slide and subject |
|---|---|
| 0:00–0:35 | 1. Research question and credits |
| 0:35–1:30 | 2. Historical approvals and Monedo's randomized holdout |
| 1:30–2:40 | 3. BASL training and Bayesian evaluation |
| 2:40–3:40 | 4. Funded public cohorts and the outcome-maturity gap |
| 3:40–5:00 | 5. Simulation against Figure 2 on identical axes |
| 5:00–6:05 | 6. Evaluation RMSE against Table 2 |
| 6:05–7:10 | 7. Training ABR against Table 3 |
| 7:10–7:50 | 8. Which repayments matter for the choice of cutoff? |
| 7:50–9:20 | 9. Twelve prospective Prosper forecasts |
| 9:20–10:40 | 10. Four adjacent-band margins recover every difference between five cutoffs |
| 10:40–12:05 | 11. Random assignment of credit offers in the Philippines |
| 12:05–13:00 | 12. Two Taiwan histories match the same ten actual default counts and imply opposite decisions |
| 13:00–13:55 | 13. Overfitting checks and limits |
| 13:55–15:00 | 14. When does a loss-making test loan pay for itself? |

| Backup slide | Question or evidence |
|---|---|
| 15–18 | A 50-label audit, quarterly forecast trajectories, prior-odds bounds and calibration |
| 19–22 | Repayment in the offer lottery, risk-decile lift, BASL stopping rules and all four paper metrics |
| 23 | Sources and reproduction commands |
| 24 | Scenario margins from the validation-selected loan cutoff |
| 25 | Worst-case regret for five fixed or randomized approval cutoffs |
| 26 | Expected audit size for the Prosper expansion and two break-even cases |
| 27 | Can one recorded SBA repayment improve the next regional lending decision? |
| 28 | Break-even horizons with one label versus repeated learning and the parameter grid |
| 29 | Can the ex-ante ranking identify useful pilots on US and European funded loans? |
| 30 | Which Bondora switch covered a pilot loss, and which underwriting change actually occurred at M-Shwari? |
| 31 | Which origination facts distinguished the two Estonian cases, and how did information access affect the switches? |
| 32 | Did the revised rule recover losses in later Bondora cohorts or at Prosper? |
| 33 | Why did the rule pass over March 2021 and select the other two Finnish pilots? |
| 34 | How much did boosting learn from a single pilot beyond ordinary information and other loans? |

## Updating the deck

From the repository root, run the analytical pipeline first, then run `python3 slides/build.py`. The slide builder uses Python's standard library and LibreOffice's `soffice` executable to generate both delivered files. Raw loan data are unnecessary when the aggregate CSV and PNG files are already present in `results/`.

[template.pptx](template.pptx) is the editable source. Native table cells and figures are linked to the results by the public [build script](build.py). Keep each double-braced field in one PowerPoint text run when editing a dynamic cell, and retain the figure alt text (`simulation_fig2.png`, `calibration.png`, `vintage_forecasts.png`, `bounds_frontier.png`). As well as updating the numbers, review the explanatory sentences when running a different experiment.

Slide 12 uses the two-cutoff rows marked `oracle_decile_totals` in [witness worlds](../results/identification_worlds.csv) and [policy summaries](../results/identification_summary.csv). The group counts are disclosed retrospectively. Slide 26 takes the three Prosper sample-size expectations from [decision audit results](../results/decision_audit_summary.csv). Slide 25 uses the five-cutoff, unrestricted rows in the policy summaries.

Slide 10 uses an illustrative four-band example and checks the aggregate counts in [policy information](../results/policy_information_summary.csv). Slide 14 scales the [one-pilot frontier](../results/information_value_frontier.csv) to principal 100. Slide 27 uses the chronological, early-national terms in the [SBA replay](../results/pilot_replay_summary.csv). Slide 28 compares the one-pilot rule with [repeated learning](../results/exploration_values.csv) and reports [parameter-grid counts](../results/information_value_stress.csv).

Slide 29 uses the two principal tests in [pilot forecasting](../results/pilot_targeting_summary.csv). Slide 30 compares the October 2018 Estonian pilot on the [May 2024 ledger](../results/lender_pilot_followup.csv) with the TOBOA policy change documented in [field evidence](../docs/observed-pilot-evidence.md).

Slides 31–32 link origination profiles to later observed cash and compare the dated test with the US cross-lender supplement. Numeric fields come from [profiles](../results/pilot_profiles_selected.csv) and the [policy evaluation](../results/pilot_rule_summary.csv). The case-level cash is valued at the common cutoff within each lender.

Slides 33–34 use the [three Finnish cases](../results/finnish_pilot_cases.csv) and [paired model evaluation](../results/pilot_signal_ml_metrics.csv). Forecasts on these slides use information available at the date indicated. Gross cash uses the common workbook cutoff.

# Paper 11 presentation

Open [the PDF](paper11.pdf) for projection. The [PowerPoint](paper11.pptx) has editable tables and timed speaker notes. The final nine slides are for questions. Andrey Tsember led the implementation and experiments.

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
| 7:10–7:50 | 8. Our extensions and the questions they answer |
| 7:50–9:20 | 9. Twelve prospective Prosper forecasts |
| 9:20–10:40 | 10. Prior-odds tipping bound for a policy expansion |
| 10:40–12:05 | 11. Random assignment of credit offers in the Philippines |
| 12:05–13:00 | 12. Scenario margin under the original cutoff comparison |
| 13:00–13:55 | 13. Overfitting checks and limits |
| 13:55–15:00 | 14. What evidence should the lender collect next? |

Backup pages cover the 50-label audit, rolling trajectories, partial identification, calibration, repayment under randomized offers, lift, BASL stopping alternatives, the four paper metrics and reproduction commands.

## Updating the deck

From the repository root, run the analytical pipeline first, then run `python3 slides/build.py`. The slide builder uses Python's standard library and LibreOffice's `soffice` executable to generate both delivered files. Raw loan data are unnecessary when the aggregate CSV and PNG files are already present in `results/`.

[template.pptx](template.pptx) is the editable source. Native table cells and figures are linked to the results by the public [build script](build.py). Keep each double-braced field in one PowerPoint text run when editing a dynamic cell, and retain the figure alt text (`simulation_fig2.png`, `calibration.png`, `vintage_forecasts.png`, `bounds_frontier.png`). As well as updating the numbers, review the explanatory sentences when running a different experiment.

# Paper 11 presentation

Open [the PDF](paper11.pdf) for projection. The [PowerPoint](paper11.pptx) has editable tables and timed speaker notes. The final four slides are for questions. Andrey Tsember led the implementation and experiments.

## Fifteen-minute speaking plan

| Elapsed time | Slide and subject |
|---|---|
| 0:00–0:40 | 1. Research question and credits |
| 0:40–1:45 | 2. Historical approvals and Monedo's randomized holdout |
| 1:45–3:05 | 3. BASL training and Bayesian evaluation |
| 3:05–4:20 | 4. Public cohorts and the outcome-maturity gap |
| 4:20–5:50 | 5. Simulation against Figure 2 on identical axes |
| 5:50–7:05 | 6. Evaluation RMSE against Table 2 |
| 7:05–8:20 | 7. Training ABR against Table 3 |
| 8:20–9:20 | 8. Calibration and top-decile lift |
| 9:20–10:30 | 9. Reject-prior sensitivity |
| 10:30–11:35 | 10. Validation-selected policy and realized scenario margin |
| 11:35–12:45 | 11. Fixed-budget randomized audit |
| 12:45–14:00 | 12. Overfitting checks and limitations |
| 14:00–15:00 | 13. What would test the result prospectively? |

## Updating the deck

From the repository root, run the analytical pipeline first, then run `python3 slides/build.py`. The slide builder uses Python's standard library and LibreOffice's `soffice` executable to generate both delivered files. Raw loan data are unnecessary when the aggregate CSV and PNG files are already present in `results/`.

[template.pptx](template.pptx) is the editable source. Native table cells and figures are linked to the results by the public [build script](build.py). Keep each double-braced field in one PowerPoint text run when editing a dynamic cell, and retain the figure alt text (`simulation_fig2.png`, `calibration.png`). As well as updating the numbers, review the explanatory sentences when running a different experiment.

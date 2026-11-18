# What was checked

**Implementation and experiments · Andrey Tsember, Team 12**

The evaluation ladder in DSBA Research Seminar lecture 1 asks for presentation, independent implementation, reproduced results and research upgrades. Lecture 3, slide 41 requests an out-of-time split, AUC, a calibration plot, a logistic baseline and explicit limits. The public experiment uses both recorded repayments and deliberately generated selection. [Paper and appendix](https://arxiv.org/abs/2407.13009v1)

| Assessment item | Evidence |
|---|---|
| Algorithm fidelity | [Algorithms and estimands](algorithm.md); own implementation of B.1–B.3 and Algorithm 1; references and stress cases in [method tests](../tests/test_methods.py). |
| Similarity to published results | [Figure 2 on common axes](../results/simulation_fig2.png); original summaries with seed-level uncertainty in [simulation_comparison.csv](../results/simulation_comparison.csv); same metrics in [Tables 2 and 3 comparison](../results/paper_comparison.csv). |
| Known truth and placebo | Population posterior from the Gaussian mixture, calibrated and shuffled priors, equal-sized random disclosure, full-label training benchmark. |
| Training, stopping and look-ahead | A regression test flips all hidden development labels and requires identical scores, estimates and lending policies. Prosper uses first loans, maturity gaps, independent stopping and policy validation. A separate test checks the date windows. |
| Robustness and upgrades | Prior odds shifts; stopping rule; borrower transfer across time; IPW and pseudo-label baselines; 4 loss scenarios; randomized audit with 2 budgets. [Full report](../results/report.md) |
| Inference and sensitivity | 20 independent simulation seeds, bootstrap whole paths. Public cohorts use paired borrower resampling; primary contrasts, intervals and approximate effect-size resolution when applicable in [uncertainty.csv](../results/uncertainty.csv). No zero sampling error from identical realized decisions is presented as evidence of population equivalence. |
| Round-three minimum | Out-of-time US test on 8,644 borrowers; [AUC, Brier, pAUC, lift and ABR](../results/training.csv), [calibration diagram](../results/calibration.png), logistic baseline and stated limits. |
| Defense | 13 main slides with a 15-minute speaking plan, including the required overfitting discussion; four backup slides and editable speaker notes. [Presentation and timing](../slides/README.md). Actual delivery speed depends on the speakers. |

The [previous team project](https://github.com/bigpurota/paper15-lou-shu) used known-answer and reference tests, null controls, leakage checks, multiple specifications, sensitivity to small effects, data provenance, a clean rerun, and source-linked slides. Here the reference for rank metrics is scikit-learn on tied and weighted cases. Expected Bayesian metrics are also compared against exact enumeration. ABR integration is checked against independent numerical quadrature. Financial identities are checked at both per-applicant and per-issued-unit denominators. Key output checks read the CSVs independently of the models.

## Repeat these checks

* `make verify` runs the regression/reference tests, then checks numerical consistency across all public result tables. This includes invariants with known answers and permits research estimates to be unfavorable.
* `make all` downloads both fixed sources, checks their SHA-256 hashes, fits both empirical experiments, reruns the simulations, generates plots and the report, and checks the outputs.
* `make reproduce` writes all research results to a new temporary directory and compares against the submitted results; it reports the count that is byte-identical. The fixed graphics runtime matters for exact PNG comparisons.
* `make slides` updates the numeric fields and figures in the editable PowerPoint, then exports the presentation PDF using LibreOffice.
* The repository's [CI workflow](../.github/workflows/research.yml) tests the submitted artifacts and separately executes the pipeline from the public URLs on Linux. Source data and the original Monedo borrower records are not distributed here.

## Verified release run

On 18 November 2026, a fresh macOS ARM64 CPython 3.12.13 environment installed the lockfile and downloaded both input files into an empty cache. All 18 regenerated research artifacts matched the submitted files byte for byte. A second run using the cache and a fresh output directory also matched all 18. The 19 regression and reference tests passed. Both public presentation formats were opened for structural and rendered-page checks; the source template rebuilds its figures and tables from the submitted results. The original Spanish lender study and an in-person rehearsal are outside those checks.

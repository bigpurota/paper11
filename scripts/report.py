"""Build source-linked tables, cohort calibration plots and the research report."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"accepts":"#24568a", "basl":"#bb562d", "logit":"#14766e"}
LABELS = {"accepts":"Accepted-only XGB", "basl":"BASL", "logit":"Logit"}


def comparison(out):
    published = pd.read_csv(ROOT / "data/paper_tables.csv")
    ev = pd.read_csv(out / "evaluation_rmse.csv").set_index(["dataset","method","metric"])
    tr = pd.read_csv(out / "training.csv").groupby(["dataset","method"]).mean(numeric_only=True)
    rows = []
    for row in published.itertuples():
        for metric in ("auc", "brier", "pauc", "abr"):
            rec = dict(table=row.table, method=row.method, metric=metric, monedo=getattr(row,metric))
            for ds in ("taiwan", "prosper"):
                rec[ds] = ev.loc[(ds,row.method,metric),"rmse"] if row.table == 2 else tr.loc[(ds,row.method),metric]
            rows.append(rec)
    frame = pd.DataFrame(rows)
    frame.to_csv(out / "paper_comparison.csv",index=False,float_format="%.10g")
    return frame


def calibration_plot(out):
    frame = pd.read_csv(out / "calibration.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.5,4.5), layout="constrained")
    for ax, name, label in zip(axes, ["taiwan","prosper"], ["Taiwan · four test folds", "Prosper · later borrowers"]):
        sub = frame[frame.dataset == name]
        for method in COLORS:
            part = sub[sub.method == method].copy()
            # Average corresponding within-fold deciles, weighting by count.
            for k in ("predicted","observed"):
                part[k] *= part.n
            bins = part.groupby("bin")[["predicted","observed","n"]].sum()
            ax.plot(bins.predicted/bins.n, bins.observed/bins.n, marker="o", ms=4,
                    lw=1.7, color=COLORS[method], label=LABELS[method])
        limit = ax.get_ylim()[1]
        limit = max(limit, ax.get_xlim()[1])
        ax.plot([0, limit], [0, limit], color="#858b8f", ls=":", label="Perfect calibration")
        ax.set(xlim=(0,limit),ylim=(0,limit),title=label,xlabel="Mean predicted PD",ylabel="Observed default rate")
        ax.set_aspect("equal")
        ax.grid(alpha=.15)
        ax.spines[["top","right"]].set_visible(False)
    axes[0].legend(fontsize=8,frameon=False)
    fig.savefig(out/"calibration.png",dpi=155,facecolor="white",metadata={"Software":"Matplotlib"})
    plt.close(fig)


def table(frame):
    def fmt(v):
        return f"{v:.4f}" if isinstance(v,(float,np.floating)) else str(v)
    return "\n".join(["| "+" | ".join(frame.columns)+" |","|"+"---|"*len(frame.columns),
                       *["| "+" | ".join(map(fmt,row))+" |" for row in frame.itertuples(index=False,name=None)]])


def write_report(out, comp):
    sims = pd.read_csv(out/"simulation_comparison.csv")
    train = pd.read_csv(out/"training.csv").groupby(["dataset","method"],as_index=False)[["auc","brier","pauc","abr","lift10"]].mean()
    risk = pd.read_csv(out/"evaluation_rmse.csv")
    risk = risk[risk.metric=="abr"].pivot(index="method",columns="dataset",values="rmse").reset_index()
    within = pd.read_csv(out/"evaluation.csv").query("metric == 'abr' and method in ['accepts', 'bayes']").copy()
    within["squared"] = within.within_cohort_error**2
    same_cohort = within.groupby(["dataset","method"]).squared.mean().pow(.5).unstack()
    policy = pd.read_csv(out/"policy.csv").groupby(["dataset","lgd","method"]).mean(numeric_only=True)
    # Conditional on each test fold’s fitted score and chosen cutoff.
    contrast = pd.read_csv(out/"uncertainty.csv")
    audit = pd.read_csv(out/"audit_budget.csv")
    audit["squared_rmse"] = audit.audit_rmse**2
    audit["squared_prior_error"] = audit.prior_only_error**2
    audit = audit.groupby(["dataset","n_audited","design"],as_index=False)[["squared_rmse","squared_prior_error"]].mean()
    audit["audit_rmse"] = np.sqrt(audit.pop("squared_rmse"))
    audit["prior_only_rmse"] = np.sqrt(audit.pop("squared_prior_error"))
    audit.to_csv(out/"audit_summary.csv",index=False,float_format="%.10g")
    bp = policy.reset_index().pivot(index=["dataset","lgd"],columns="method",values="profit_per_applicant").reset_index()
    bp["bayes_minus_accepts"] = bp.bayes - bp.accepts
    gap = sims[(sims.metric=="abr") & sims.statistic.isin(["accept_eval_rmse","bayes_eval_rmse","oracle_gap","basl_recovery_fraction"])]
    cols = ["dataset","contrast","estimate","ci_low","ci_high"]
    sections = [
        "# Team 12 · Fighting Sampling Bias",
        "**Implementation and computational experiments · Andrey Tsember**\n\nTeam 12 · Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox.",
        "This report uses the assigned preprint and public borrower records. An approval scorecard is needed for everyone who applies, while repayment is usually observed only for the people actually financed. Training with inferred labels and evaluating on the complete applicant mix solve different problems.",
        "## Synthetic replication of Figure 2",
        table(gap[["statistic","paper_value","estimate","ci_low","ci_high"]]),
        "Twenty independent runs, 40 batches each. Intervals resample complete simulation seeds. Recovery is a fraction of the gap between accepted-only and full-label training. Evaluation error is measured against true holdout labels. The first four shared plotted checkpoints are displayed on identical axes. The published long-run summaries cover a longer experiment.",
        "![Figure 2 comparison](simulation_fig2.png)",
        "## Published Monedo versus our public-cohort experiments",
        "Table 2 compares errors in prediction of a scorecard metric; smaller is better. Table 3 compares scorecards on held-out borrowers. Smaller Brier and ABR, higher AUC and pAUC are better. The reweighting rows compare different weight estimators. Targets, default rates and approval mechanisms differ across datasets.",
        table(comp[comp.metric=="abr"][["table","method","monedo","taiwan","prosper"]]),
        "The complete four-metric comparison is in [paper_comparison.csv](paper_comparison.csv).",
        "## Training, risk lift and calibration",table(train),
        "Lift10 is the bad rate in the riskiest tenth divided by the population bad rate. The Taiwan test shows a modest increase in bad loans among the safest borrowers under BASL. The Prosper training contrast is small relative to its interval. The simulated training improvement does not transfer consistently.",
        "![Calibration by risk group](calibration.png)",
        "The diagonal represents perfect calibration. Each point represents an equal-frequency group (ties kept together); the cohorts have separate scales. Calibration measures agreement between predicted and observed frequencies, while AUC measures ordering.",
        "## Exposure to the prior",table(risk),
        "The central Bayesian prior is a logit trained only on observed training outcomes. Halving or doubling reject odds leaves the scorecard and its rankings unchanged. It changes which hidden outcomes are assumed when estimating performance. A stronger prior in one cohort can be worse in another. Taiwan RMSE uses four folds; the single chronological Prosper split yields an absolute error.",
        "The complete labels in the validation cohort also allow a retrospective test that removes population transfer. On Taiwan the accepted-only and Bayesian errors are "
        f"{same_cohort.loc['taiwan','accepts']:.4f} and {same_cohort.loc['taiwan','bayes']:.4f}, respectively. On Prosper they are "
        f"{same_cohort.loc['prosper','accepts']:.4f} and {same_cohort.loc['prosper','bayes']:.4f}. Taiwan's small prospective improvement therefore cannot be attributed solely to correcting selection.",
        "## Paired uncertainty",table(contrast[cols]),
        "Training comparisons use the same test borrowers under both models. Evaluation-error comparisons assign each borrower one shared Poisson weight wherever it recurs across folds. Intervals are conditional on fitted models and logged decisions. Both empirical intervals for the change in ABR estimation error include zero. Zero conditional policy variance at the base LGD means the methods took the same decisions on these cases.",
        "## Conditional lending policy",table(bp),
        "The entries are margin in units of principal per arriving applicant using an assumed 10% return if repaid. Issuance rates, per-issued-unit margins and numerical cutoffs are in [policy.csv](policy.csv). At 50% LGD all three estimators select the upper end of the allowed rate grid, so the realized difference is exactly zero. The paper’s stated gain in profit depends on its pricing, approval decisions and Spanish borrower population.",
        "## Can a small randomized audit improve ABR measurement?",table(audit),
        "For a fixed proposed 30% approval policy, each audit reveals 10 or 50 funded outcomes under controlled masking. Both sampling designs cost the same number of labels. Targeting only previously declined borrowers whom this policy would approve lowers sampling variability. Compare against prior-only RMSE as well: a good prior can beat a noisy small audit on a given cohort. Random disclosure identifies the fixed-policy default rate in this finite validation cohort; small samples may still be imprecise. Each result pools squared error across 500 draws per split before taking the square root.",
        "## Limits and a three-month follow-up",
        "We can test label concealment among already funded borrowers. A randomized sample of actual would-be declines with mature repayment labels would identify the target population more directly. Collect such a sample under a fixed decision policy, estimate default and realized net revenue with funding costs, and repeat across time vintages and adequate overlap regions. A single later Prosper cohort does not measure the distribution of future economic conditions.",
        "[Data provenance](../docs/sources.md) · [Implementation](../docs/algorithm.md) · [Deviations](../docs/deviations.md) · [Simulation](../docs/simulation.md)"
    ]
    (out/"report.md").write_text("\n\n".join(sections)+"\n")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    out=parser.parse_args().out
    calibration_plot(out)
    write_report(out, comparison(out))

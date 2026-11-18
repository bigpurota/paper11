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


def pilot_cash_plot(out):
    initial = pd.read_csv(out / "lender_pilot_episodes.csv")
    later = pd.read_csv(out / "lender_pilot_followup.csv")
    keys = ["pilot_month", "country", "customer"]
    switches = initial[initial.selected & initial.action_changed].merge(
        later[keys + ["euro_net"]], on=keys, validate="one_to_one", suffixes=("_early", "_late"))
    switches = switches.sort_values("pilot_month")
    fig, ax = plt.subplots(figsize=(8.1, 3.55), layout="constrained")
    y = np.arange(len(switches))[::-1]
    x1 = switches.euro_net_early.to_numpy() / 1000
    x2 = switches.euro_net_late.to_numpy() / 1000
    ax.axvline(0, lw=1, color="#667581")
    ax.hlines(y, np.minimum(x1,x2), np.maximum(x1,x2), color="#a7b6be", lw=2.5)
    for values, label, marker, color, offset in [(x1, "20 July 2021", "o", "#397a96", 11),
                                                 (x2, "24 May 2024", "D", "#963d31", -14)]:
        ax.scatter(values, y, marker=marker, s=65, color=color, label=label, zorder=3)
        for x, height in zip(values,y):
            ax.annotate(f"{x:+.1f}", (x,height), xytext=(0,offset), textcoords="offset points",
                        ha="center", va="center", color=color, fontsize=10)
    ax.set_yticks(y, labels=[f"{r.pilot_month}   {r.country}, {r.customer}" for r in switches.itertuples()])
    ax.set_ylim(-.56, max(len(switches)-1,0)+.55)
    ax.set_xlabel("Net cash gain versus the refreshed no-pilot rule (€ thousands)")
    ax.set_title("Bondora pilots that changed the next funding decision", loc="left", weight="bold", pad=32)
    ax.legend(loc="lower left", bbox_to_anchor=(0,1.0), ncol=2, frameon=False, borderaxespad=0)
    ax.spines[["top","right","left"]].set_visible(False)
    ax.tick_params(axis="y",length=0)
    fig.savefig(out / "lender_pilot_cash.png", dpi=160, metadata={"Software":"Matplotlib"})
    plt.close(fig)


def targeting_sections(out):
    target = pd.read_csv(out / "pilot_targeting_summary.csv")
    selected = target.query("forecast == 'fixed_risk' and outcome == 'scenario'")
    selected = selected[selected.terms.isin(["early_7a", "at_least_36m"])]
    draws = pd.read_csv(out / "pilot_transfer_episodes.csv")
    west = draws.query("terms == 'early_7a' and region == 'West' and pilot_quarter == '2002Q2'").iloc[0]
    lines = ["### Could the bank identify promising pilots in advance?",
             "Each rule receives only information available at origination and pays the direct pilot margin once. A new forecast allows the public risk estimate to change while repayment is pending, using only earlier public updates that have already arrived. Both rules face the same future opportunities."]
    for archive, data in selected.groupby("archive"):
        summary = data.set_index("metric")
        auc, gain = summary.loc["auc_positive"], summary.loc["rule_gain"]
        label = "SBA 7(a), using early local pricing" if archive == "sba_7a" else "Bondora, at least three years of subsequent payments"
        lines.append(f"{label}: the fixed-risk rule selected {auc.selected} of {auc.eligible} eligible pilots. "
                     f"AUC for positive realized scenario gain was {auc.estimate:.3f} "
                     f"(95% four-quarter block interval {auc.block4_low:.3f} to {auc.block4_high:.3f}). "
                     f"Net versus skipping all pilots was {100*gain.estimate:+.3f} per eligible episode "
                     f"when one loan has principal 100. Positive net can also come from collecting the pilot itself.")
    loss = west.fixed_future_first_failed_pilot_cash
    gross = west.fixed_future_recorded_gross_on_failure
    lines.append(f"SBA 7(a) offers an existence example. In the West, one actual failed pilot from 2002 Q2 "
                 f"could have changed the rule from funding to declining the same 25 later loans. Using reported "
                 f"charge-off amounts and the hypothetical performing margin gives {100*loss:+.2f} on the pilot, "
                 f"{100*gross:+.2f} on subsequent decisions and {100*(loss+gross):+.2f} overall. We identified "
                 f"this branch after scoring. Its region-quarter was selected up front, but the precommitted "
                 f"borrower draw chose a different pilot. [Exact branches and calendar windows](../docs/pilot-transfer.md)")
    eu = pd.read_csv(out / "lender_pilot_followup.csv")
    episode = eu.query("country == 'EE' and customer == 'returning' and pilot_month == '2018-10'").iloc[0]
    later = eu[eu.selected & eu.action_changed]
    lines.append(f"In the extended Bondora window, the October 2018 Estonian pilot lost €{-episode.euro_pilot:,.2f}. "
                 f"Relative to lending to all {episode.portfolio_n} subsequent borrowers in November 2019, "
                 f"the pilot-informed refusal would avoid €{episode.euro_gross:,.2f} in cash shortfall as of May 24, 2024. "
                 f"The paired net is €{episode.euro_net:,.2f}. Across the {len(later)} selected pilots that changed a decision, "
                 f"{later.euro_covered.sum()} still covered their actual euro loss at this date. This follow-up uses "
                 "the same loan identities, and outstanding collections could change the result. These decisions were replayed.")
    lines.append("![Paired cumulative cash gains at the two valuation dates](lender_pilot_cash.png)")
    lines.append("In Kenya the bank used its TOBOA experiment with previously rejected borrowers to revise the M-Shwari scorecard. The case study reports acceptance rising from 40% to 47%. It gives no incremental profit attributable to that change. [Field evidence](../docs/observed-pilot-evidence.md) · [European payment archives](../docs/lender-pilot.md) · [Forecasts, units and uncertainty](../docs/pilot-targeting.md)")
    return lines


def pilot_sections(out):
    frontier = pd.read_csv(out / "information_value_frontier.csv")
    model = frontier.query("discount == 1 and delay == 1 and fee == 0").set_index("reset")
    stable, decaying = model.loc[0.], model.loc[.10]
    stress = pd.read_csv(out / "information_value_stress.csv")
    cohort = pd.read_csv(out / "pilot_replay_cohort.csv").iloc[0]
    replay = pd.read_csv(out / "pilot_replay_summary.csv")
    primary = replay.query("sampling == 'chronological' and terms == 'early_national'")
    chosen = primary.query("strategy == 'model'").set_index("measure")
    forced = primary.query("strategy == 'forced'").set_index("measure")
    chosen_net, forced_net = chosen.loc["net"], forced.loc["net"]
    return [
        "### The price of a single repayment observation",
        f"Compare the expected loss on the pilot with the discounted increase in the best future policy's value after observing that repayment. Both policies can use the same other information. On 100 units of principal the persistent example loses {-100*stable.prior_margin:.4f} up front and adds {100*stable.evsi_at_ten/10:.6f} per later decision. It clears break-even at {int(stable.first_followups)} later applicants. With a 10% redraw probability the lifetime gain is bounded by {100*decaying.evsi_limit:.5f}. [General criterion and analytic proof](../docs/information-value.md) · [Sharp bounds for different pilot and follow-up risks](../docs/pilot-dependence.md)",
        f"The grid spans {stress.scenarios.sum():,} parameter combinations. Of the {stress.loss_making.sum():,} with negative direct expected margin, a single pilot covers that loss in {stress.strictly_worthwhile_loss_making.sum():,}. Grid frequencies describe our design. [Aggregate stress results](information_value_stress.csv)",
        "![Timing, persistence and the first profitable horizon](information_value_frontier.png)",
        "### Does this signal change decisions on historical SBA 504 loans?",
        f"The administrative extract has {cohort.source_rows:,} rows, with {cohort.retained:,} eligible disbursements. We compare identical regional follow-up portfolios using a common updated risk estimate. Each episode evaluates the first 25 continuation positions. The future quarterly source pools contain {cohort.continuation_pool_loans:,} financed loans. Among {chosen_net.eligible_cells} initially loss-making region-quarter episodes the plug-in rule selected {chosen_net.pilot_cells} pilots. At disclosure the signal could change the decision in {chosen_net.signal_sensitive_cells} of these. Including the pilot cash flow, the incremental margin was {100*chosen_net.mean_per_eligible_episode:+.3f} per eligible episode, in units per 100 principal on one loan (95% moving-block interval {100*chosen_net.ci_4q_low:+.3f} to {100*chosen_net.ci_4q_high:+.3f}).",
        f"Requiring a pilot in every eligible episode gave {100*forced.loc['gross','mean_per_eligible_episode']:+.3f} in gross continuation gain and {100*forced.loc['pilot_margin','mean_per_eligible_episode']:+.3f} in direct pilot margin. Net gain versus the updated no-pilot policy was {100*forced_net.mean_per_eligible_episode:+.3f} [{100*forced_net.ci_4q_low:+.3f}, {100*forced_net.ci_4q_high:+.3f}]. The financial terms are scenarios applied to three-year recorded charge-offs. Results concern historically financed loans and the specified decision rule. [Replay protocol, comparators and sensitivity](../docs/pilot-replay.md)",
    ]


def extension_sections(out):
    vintage = pd.read_csv(out/"vintage_summary.csv").copy()
    for col in ("masking_rmse","forecast_rmse"):
        vintage[col] *= 100
    thresholds = pd.read_csv(out/"bounds_tipping.csv")
    expansion = thresholds[(thresholds.target == .5) & (thresholds.budget == 0)].groupby("dataset").tipping_gamma
    values = pd.read_csv(out/"rct_contrasts.csv").set_index("estimand")
    transfer = pd.read_csv(out/"rct_prior_transfer.csv").iloc[0]
    gain = values.loc["offer_all_minus_high_only_cash_revenue"]
    funding = values.loc["offer_all_minus_high_only_funding"]
    lower = values.loc["all_funded_hypothetical_risk_lower","estimate"]
    upper = values.loc["all_funded_hypothetical_risk_upper","estimate"]
    ident = pd.read_csv(out/"identification_summary.csv")
    group_counts = ident[(ident.grid == "two") & (ident.constraint == "oracle_decile_totals")].set_index("dataset")
    audit = pd.read_csv(out/"decision_audit_summary.csv")
    prosper = audit[audit.dataset == "prosper"].set_index("scenario")
    info = pd.read_csv(out/"policy_information_summary.csv").groupby("design").sum(numeric_only=True)
    dynamic = pd.read_csv(out/"exploration_values.csv")
    persistent = dynamic[dynamic.reset == 0].set_index("horizon")
    first = int(persistent.index[persistent.first_action == "fund"].min())
    return [
        "## Our extensions",
        "### Which measurements recover every policy difference?",
        "Consider five nested policies, with four nonempty groups entering between consecutive cutoffs. Their four unknown expected margins suffice for every exact pairwise comparison. When those margins can vary on an open set, four is the minimum number of independent linear measurements for that task. The sign alone can sometimes be learned with fewer. For general lending rules, the answer is the rank of the matrix of differences on the unknown margins.",
        table(info[["n_policy_pairs","pairs_exact_at_actual_binary_totals","decisions_settled_at_actual_binary_totals"]].astype(int).reset_index()),
        "The rows above use the actual aggregate counts of masked outcomes, disclosed retrospectively on each validation split. Counts are comparisons across four Taiwan splits and one Prosper split. [Data-independent proof and finite-cohort check](../docs/policy-information.md)",
        "### When can a lender pay to observe a repayment?",
        f"In the illustrative persistent-regime decision model, a loan of 100 has immediate expected margin {100*persistent.iloc[0].immediate_margin:.2f}. Starting with {first} applicants available, the lender first finds funding worthwhile: its optimal total expected margin is {100*persistent.loc[first,'adaptive_value']:.2f}, versus zero under the best fixed decision. At ten opportunities the total reaches {100*persistent.loc[10,'adaptive_value']:.2f}. If each new borrower draws an independent regime, a repayment has zero value for the next decision. The horizon counts all applicants, including the pilot. Repayment on a funded loan arrives before the next decision. These are illustrative monetary units, independent of the public datasets. [Decision tree, assumptions and tests](../docs/exploration.md)",
        "![Expected value of lending to learn](exploration_value.png)",
        *pilot_sections(out),
        *targeting_sections(out),
        "### Can the archive identify which policy earns more?",
        f"Hold all visible outcomes fixed. Grant access to the actual number of defaults in each of ten groups of hidden applicants ranked by the frozen prior. The grouping is fixed before reading the true aggregate counts. On Taiwan, moving these same defaults within groups yields both negative and positive gains for the same 30% to 50% expansion in every split. The mean bounds are {100*group_counts.loc['taiwan','gain_30_to_50_lower']:+.2f} to {100*group_counts.loc['taiwan','gain_30_to_50_upper']:+.2f} pp of scenario margin per applicant. On Prosper these ten true counts are sufficient to determine a positive sign ({100*group_counts.loc['prosper','gain_30_to_50_lower']:+.2f} to {100*group_counts.loc['prosper','gain_30_to_50_upper']:+.2f} pp). These aggregates use retrospective information unavailable to the original lender. A second sensitivity case substitutes counts obtained by rounding the prior probabilities. We also solve the minimax-regret choice among five cutoffs and audit the frozen rule on holdout. [Construction, proof and results](../docs/identification.md)",
        "### What would it take to resolve the decision?",
        f"For the Prosper validation pool, {int(prosper.loc['retrospective_truth','hidden'])} repayments among the additional approvals were hidden. In the retrospective truth, {int(prosper.loc['retrospective_truth','hidden_defaults'])} defaulted. The exact random-order audit uses {prosper.loc['retrospective_truth','mean_labels']:.2f} labels on average. At the last profitable and first unprofitable hidden default counts it uses {prosper.loc['last_profitable','mean_labels']:.2f} and {prosper.loc['first_unprofitable','mean_labels']:.2f}. The prespecified review schedule bounds wrong-direction decisions by 5% for each fixed population. The required sample depends on how close that population is to break-even. [Stopping boundaries, proof, and sample-size distributions](../docs/decision-audit.md)",
        "[What the authors did, what Team 12 added, and how the evidence compares with Paper 15](../docs/contributions.md)",
        "### Correcting old labels versus predicting the next quarter",
        table(vintage[["method","quarters","masking_rmse","forecast_rmse","quarters_better_than_accepts"]]),
        "Both RMSE columns above are in percentage points of integrated ABR. Bayesian evaluation improves historical measurement but produces larger next-quarter RMSE over twelve Prosper cohorts, despite winning in seven individual quarters. The historical oracle uses complete previous outcomes and still experiences temporal transfer error. [Period definitions and error decomposition](../docs/vintages.md)",
        "![Twelve calendar forecasts](vintage_forecasts.png)",
        "### Prior sensitivity at a lending decision",
        f"With 10% interest, 50% LGD and a fixed 30% incumbent, the validation lower bound for the 50% expansion's conditional expected margin stays nonnegative up to an odds multiplier of {expansion.min()['taiwan']:.2f}–{expansion.max()['taiwan']:.2f} in Taiwan and {expansion.min()['prosper']:.2f} on Prosper. Absolute cutoffs are frozen before testing. With unrestricted missing outcomes a zero-downside validation rule retains the incumbent. These are sensitivity endpoints, distinct from sampling confidence intervals. [Definitions, paired gains and held-out results](../docs/bounds.md)",
        "![Policy selection under bounded uncertainty](bounds_frontier.png)",
        "### Randomized offers and actual borrowing in the Philippines",
        f"The analytic extract contains 1,113 marginal applicants. Expanding offers from the high score window to both windows changes the funding rate by {100*funding.estimate:.2f} percentage points and the lender cash margin by {gain.estimate:.2f} PPP dollars per assigned applicant (95% bootstrap interval {gain.ci_low:.2f} to {gain.ci_high:.2f}), before other costs. The result refers to this selected extract under within-window comparability. The underlying experiment was conducted by Karlan and Zinman.",
        f"The estimated share with a principal shortfall greater than one peso under hypothetical universal funding is only bounded between {100*lower:.2f}% and {100*upper:.2f}% if the non-takers’ repayment is unrestricted. This identified set has a different interpretation from a confidence interval. As a sparse check of a risk prior carried over from the high score window, the observed lower window has {int(transfer.low_events)} shortfalls among {int(transfer.low_funded)} funded borrowers versus {transfer.expected_low_events:.2f} expected. [Assumptions, primary sources and exact rare-event comparison](../docs/rct.md)",
        "![Philippine randomized offers and partially observed risk](rct_policy.png)",
    ]


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
        "Team 12 · Andrey Tsember, Sofia Shapovalova, Ksenia Stepanova, Marat Bineman and Alexia Fox.",
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
        f"{same_cohort.loc['prosper','accepts']:.4f} and {same_cohort.loc['prosper','bayes']:.4f}. Taiwan's small improvement on an independent same-vintage sample therefore cannot be attributed solely to correcting selection.",
        "## Paired uncertainty",table(contrast[cols]),
        "Training comparisons use the same test borrowers under both models. Evaluation-error comparisons assign each borrower one shared Poisson weight wherever it recurs across folds. Intervals are conditional on fitted models and logged decisions. Both empirical intervals for the change in ABR estimation error include zero. Zero conditional policy variance at the base LGD means the methods took the same decisions on these cases.",
        "## Conditional lending policy",table(bp),
        "The entries are margin in units of principal per arriving applicant using an assumed 10% return if repaid. Issuance rates, per-issued-unit margins and numerical cutoffs are in [policy.csv](policy.csv). At 50% LGD all three estimators select the upper end of the allowed rate grid, so the realized difference is exactly zero. The paper’s stated gain in profit depends on its pricing, approval decisions and Spanish borrower population.",
        "## Can a small randomized audit improve ABR measurement?",table(audit),
        "For a fixed proposed 30% approval policy, each audit reveals 10 or 50 funded outcomes under controlled masking. Both designs reveal the same number of outcomes. Financial exploration costs may differ. Targeting only previously declined borrowers whom this policy would approve lowers sampling variability. Compare against prior-only RMSE as well: a good prior can beat a noisy small audit on a given cohort. Random disclosure identifies the fixed-policy default rate in this finite validation cohort; small samples may still be imprecise. Each result pools squared error across 500 draws per split before taking the square root.",
        *extension_sections(out),
        "## Limits and a three-month follow-up",
        "We can test label concealment among already funded borrowers. A randomized sample of actual would-be declines with mature repayment labels would identify the target population more directly. Collect such a sample under a fixed decision policy, estimate default and realized net revenue with funding costs, and repeat across time vintages and adequate overlap regions. Twelve Prosper quarters provide evidence on temporal transfer at one lender. Profit net of financing and servicing costs and transport to other macroeconomic conditions still require additional data.",
        "[Data provenance](../docs/sources.md) · [Implementation](../docs/algorithm.md) · [Deviations](../docs/deviations.md) · [Simulation](../docs/simulation.md)"
    ]
    (out/"report.md").write_text("\n\n".join(sections)+"\n")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    out=parser.parse_args().out
    calibration_plot(out)
    pilot_cash_plot(out)
    write_report(out, comparison(out))

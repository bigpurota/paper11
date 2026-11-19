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


# Reader-facing names for result columns and coded values; anything unlisted is shown as stored.
NAMES = {
    "statistic": "Statistic", "paper_value": "Paper", "estimate": "Estimate", "ci_low": "95% low",
    "ci_high": "95% high", "table": "Paper table", "method": "Method", "monedo": "Monedo (paper)",
    "taiwan": "Taiwan", "prosper": "Prosper", "dataset": "Data", "auc": "AUC", "brier": "Brier",
    "pauc": "pAUC", "abr": "ABR", "lift10": "Top-decile lift", "contrast": "Contrast", "lgd": "LGD",
    "accepts": "Accepted-only", "bayes": "Bayesian", "ipw": "Reweighting", "basl": "BASL",
    "basl_guarded": "BASL, baseline eligible", "hard_cutoff": "Hard cutoff", "logit": "Logit",
    "oracle_history": "Complete history", "bayes_odds_double": "Bayesian, reject odds ×2",
    "bayes_odds_half": "Bayesian, reject odds ×½", "bayes_minus_accepts": "Bayesian − accepted-only",
    "accept_eval_rmse": "Accepted-only evaluation error (RMSE)", "bayes_eval_rmse": "Bayesian evaluation error (RMSE)",
    "oracle_gap": "ABR gap, accepted-only vs full-label training", "basl_recovery_fraction": "Share of that gap BASL recovers",
    "basl_minus_accepts_abr": "BASL − accepted-only: ABR", "basl_minus_accepts_brier": "BASL − accepted-only: Brier",
    "bayes_minus_accepts_profit_at_lgd50": "Bayesian − accepted-only: margin at 50% LGD",
    "bayes_minus_accepts_rmse_abr": "Bayesian − accepted-only: ABR estimation error",
    "n_audited": "Labels audited", "design": "Design", "audit_rmse": "Audit RMSE", "prior_only_rmse": "Prior-only RMSE",
    "all_rejects": "All past rejects", "policy_rejects": "Rejects the policy would fund",
    "expansion_bands": "Four bands between cutoffs", "prior_deciles": "Ten prior-risk deciles",
    "n_policy_pairs": "Policy pairs", "pairs_exact_at_actual_binary_totals": "Differences identified exactly",
    "decisions_settled_at_actual_binary_totals": "Decisions settled", "quarters": "Quarters",
    "masking_rmse": "Historical RMSE, pp", "forecast_rmse": "Next-quarter RMSE, pp",
    "quarters_better_than_accepts": "Quarters better than accepted-only",
}


def table(frame):
    def fmt(v):
        if isinstance(v, (float, np.floating)):
            return f"{v:.4f}"
        return NAMES.get(v, str(v)) if isinstance(v, str) else str(v)
    return "\n".join(["| "+" | ".join(NAMES.get(c, str(c)) for c in frame.columns)+" |","|"+"---|"*len(frame.columns),
                       *["| "+" | ".join(map(fmt,row))+" |" for row in frame.itertuples(index=False,name=None)]])


def euro(value):
    """Signed euro amount with the minus sign before the currency symbol."""
    return ("−" if value < 0 else "") + f"€{abs(value):,.2f}"


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


def early_payment_section(out):
    nl = pd.read_csv(out / "early_dutch_episodes.csv")
    cz = pd.read_csv(out / "early_czech_coverage.csv").iloc[0]
    action = pd.read_csv(out / "early_czech_policy.csv")
    base = action.loc[action.method.eq("six") & action.good.eq(.10)].set_index("reference")
    return [
        "## Can early payments reveal that two historical risk estimates are high?",
        f"Across eight Dutch dates the six-month default curve predicted {nl.six_month.mean():.2%}. "
        f"Later first-25 portfolios realized {nl.target.mean():.2%} default exposure, while the very cohorts supplying the six-month counts "
        f"eventually recorded {nl.revised_young_year_rate.mean():.2%} first-year defaults by count. "
        "The distinction matters because the later portfolios were issued thirteen months after the forecast. "
        "[Repayment clocks and sensitivity to archive revisions](../docs/early-dutch.md)",
        f"In the prespecified Czech transfer, {cz.already_short_by_month3:.0f} loans had already reached the two-instalment event by month three. "
        f"Among loans still at risk, {cz.incident_marked:.0f}/{cz.marked_at_risk:.0f} with a one-instalment shortfall at the landmark "
        f"and {cz.incident_unmarked:.0f}/{cz.unmarked_at_risk:.0f} among the others had an incident event by month twelve. "
        f"The six-month rule changed {base.loc['local','extra_books'] + base.loc['local','dropped_books']:.0f} of {cz.scored_books:.0f} simulated "
        f"funding decisions versus the local rate at 18.18%. Scenario margin differences were {base.loc['local','delta_margin_czk']:+,.0f} CZK relative to local "
        f"and {base.loc['other','delta_margin_czk']:+,.0f} CZK relative to the other regions. "
        "[External lender, uncertainty and case details](../docs/early-czech.md) · [Advance warning threshold](../docs/early-warning.md)",
    ]


def trust_sections(out):
    dutch = pd.read_csv(out / "dutch_trust.csv")
    cases = pd.read_csv(out / "dutch_frequency_episodes.csv")
    scores = pd.read_csv(out / "local_trust_bank_metrics.csv").query(
        "sample == 'matched' and group == 'all' and basis == 'equal_books'").set_index("method")
    choices = pd.read_csv(out / "local_trust_bank_choices.csv").query("sample == 'matched'").set_index("choice")
    high, low = choices.loc["local"], choices.loc["pooled"]
    base, broad = scores.loc["local_minus_hybrid"], scores.loc["pooled_minus_hybrid"]
    correct = int(high.local_closer + low.pooled_closer)
    majority = int(high.pooled_closer + low.pooled_closer)
    return [
        "### A local market at launch and a test at a different bank",
        f"The Dutch first-year rate at issue averaged {dutch.local.mean():.2%} across eight opportunities. Three forecasts used the same 245 loans disbursed in September and October 2022, the first two months of the market. Among later loans, {cases.future_defaults.sum():,} of {cases.future_labels.sum():,} recorded a first-year default. In the first-25 portfolios {cases.first25_defaults.sum()} of {cases.first25_labels.sum()} loans defaulted, for a mean defaulted share of principal of {dutch.outcome.mean():.2%}. The change in risk across origination months accounts for {100*cases.change_across_vintages.mean():.2f} percentage points of the {100*cases.forecast_gap.mean():.2f}-point gap. [Calendar, contracts and decomposition](../docs/dutch-frequency.md)",
        f"The size of the recent local business and differences among other mature markets determine the weight placed on local data. The hybrid Dutch forecast averaged {dutch.hybrid.mean():.2%}, and the other-country rate {dutch.pooled.mean():.2%}. The rule was designed after seeing these cases. For an independent test we fixed the same rule on Wells Fargo's SBA 7(a) state portfolios before opening a new approval archive. [Rule and test registration](../docs/local-trust-protocol.md)",
        f"Across {int(base.books)} supported state-quarters and {int(base.loans):,} loans, the hybrid's mean Brier improvement was {base['mean']:+.6f} over local (95% block interval {base.ci_low:+.6f} to {base.ci_high:+.6f}) and {broad['mean']:+.6f} over the outside-state rate ({broad.ci_low:+.6f} to {broad.ci_high:+.6f}). Local was closer in {int(high.local_closer)} of {int(high.books)} local-majority calls. Broader was closer in {int(low.pooled_closer)} of {int(low.books)} other calls. This gives {correct} correct choices against {majority} for always choosing the outside-state rate. The hard choice and the continuous hybrid have distinct endpoints.",
        "![Dutch launch forecasts and geographic choices at Wells Fargo](local_trust_transfer.png)",
        "[Decision condition and assumptions](../docs/local-trust.md) · [Wells Fargo methods, scenarios and results](../docs/local-trust-bank.md) · [Paired accuracy](local_trust_bank_metrics.csv) · [Economic scenarios](local_trust_bank_policy.csv)",
    ]


def trust_plot(out):
    frame = pd.read_csv(out / "dutch_trust.csv").sort_values("origin_month")
    bank = pd.read_csv(out / "local_trust_bank_choices.csv").query("sample == 'matched'").set_index("choice")
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.05), layout="constrained",
                                      gridspec_kw={"width_ratios": [1.55, 1]})
    time = np.arange(len(frame))
    for col, label, color, style in (("local", "Local at issue", "#9d482b", "-"),
                                     ("hybrid", "Weighted forecast", "#13746e", "-"),
                                     ("pooled", "Other countries", "#305b8a", "--")):
        left.plot(time, 100*frame[col], color=color, ls=style, lw=2, label=label)
    left.scatter(time, 100*frame.outcome, s=32, color="#23292e", label="Observed later", zorder=3)
    left.set_xticks(time[::2], frame.origin_month.iloc[::2])
    left.set_ylim(-1.2, 33)
    left.set_xlabel("Pilot issue month")
    left.set_ylabel("Default exposure (%)")
    left.set_title("Netherlands · eight future books", loc="left", weight="bold", fontsize=12)
    handles, labels = left.get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower left", ncols=4, frameon=False, fontsize=8)
    for i, group in enumerate(("local", "pooled")):
        row = bank.loc[group]
        percent = 100*row.local_closer/row.books
        right.barh(i, percent, height=.43, color="#13746e")
        right.barh(i, 100-percent, left=percent, height=.43, color="#dce4ea")
        right.text(percent/2, i, f"{row.local_closer:.0f} local", ha="center", va="center", color="white", fontsize=9)
        right.text((100+percent)/2, i, f"{row.pooled_closer:.0f} broader", ha="center", va="center", color="#243d55", fontsize=9)
    right.set(xlim=(0,100), ylim=(1.75,-.75), xlabel="Share of state-quarters (%)")
    right.set_yticks([0,1], ["Local weight > ½","Local weight ≤ ½"], fontsize=9)
    right.set_xticks([0, 25, 50, 75, 100])
    right.set_title("Wells Fargo · which rate was closer?", loc="left", weight="bold", fontsize=12)
    for ax in (left, right):
        ax.spines[["top","right"]].set_visible(False)
    left.grid(axis="y", alpha=.16)
    fig.savefig(out / "local_trust_transfer.png", dpi=170, facecolor="white", metadata={"Software":"Matplotlib"})
    plt.close(fig)


def frequency_sections(out):
    previous = pd.read_csv(out / "frequency_diagnosis_support.csv").set_index("country")
    old = pd.read_csv(out / "frequency_diagnosis.csv").query("country == 'ALL' and period == 'full'")
    errors = old.set_index("forecast")
    fresh = pd.read_csv(out / "frequency_evaluation.csv").query(
        "pilot_rank == 1 and feed == 'peers' and scope == 'all'").set_index("metric")
    test = pd.read_csv(out / "frequency_model_episodes.csv").query("pilot_rank == 1 and feed == 'peers'")
    switch = test.loc[test.q_initial.ge(2/11) & test.m_public.lt(2/11)].iloc[0]
    fin = previous.loc["Finland"]
    issue = errors.loc["issue_boost"]
    return [
        "### Why did a country default frequency beat boosting?",
        f"In the earlier 48 portfolios the historical estimate used a median of {int(previous.loc['ALL','test_history_size_median']):,} mature loans; the boosted model learned from {int(previous.loc['ALL','train_books'])} portfolio outcomes. In Finland the realized future default exposure averaged {fin.test_observed_rate:.2%}, the historical rate {fin.test_frequency:.2%}, and boosting at issue {fin.test_issue_boost:.2%}. The model had received the historical rate as an input. Holding all other Finnish test fields fixed and substituting the earlier Finnish median rate moved the mean prediction only to {fin.test_boost_with_training_country_median_q:.2%}.",
        f"Across all 48 portfolios the square of the mean forecast error explains {100*issue.squared_mean_error_gap/issue.brier_gap_vs_issue:.1f}% of the issue-time Brier gap. This describes a shift in the level of risk. The size of the historical sample varied sharply by country. [Country profiles and exact error decomposition](../docs/frequency_diagnosis.md)",
        "### A frequency anchor on the next four months",
        f"Starting at the same historical rate, we trained three corrections on mature books and published their specification before scoring. In June–September 2024 the first-position candidate led to {len(test)} supported books with {test.future_count.sum()} follow-up loans. The mean Brier loss at issue was {fresh.loc['brier_frequency','mean']:.6f}, after ordinary and peer updates {fresh.loc['brier_common','mean']:.6f}, and after revealing the pilot {fresh.loc['brier_revealed','mean']:.6f}. Directly pooling the peer frequencies scored {fresh.loc['brier_peer_frequency','mean']:.6f}. A boosting model trained through the same cutoff scored {fresh.loc['brier_hgb_seen','mean']:.6f} with the pilot. All comparisons use the same subsequent portfolios.",
        f"In {switch.country}, the {switch.origin_month} pilot's ordinary news moved the bank from decline to lend. The book contained €{switch.future_principal:,.0f} of principal. It earned €{switch.future_scenario:,.2f} at the fixed first-year terms. The cumulative cash margin was −€{abs(switch.future_cash):,.2f} with €{switch.future_balance:,.2f} principal outstanding. Revealing the pilot changed zero actions. No pilot in either candidate rank defaulted within its first year. Four origin months support descriptive comparisons only.",
        "![Finnish risk levels and forecast performance on the fresh portfolios](frequency_forecasts.png)",
        "[Public protocol](../docs/frequency-protocol.md) · [Panel and overlap](../docs/frequency-panel.md) · [Model](../docs/frequency-model.md) · [Full test, thresholds and cash](../docs/frequency-test.md)",
    ]


def frequency_plot(out):
    prior = pd.read_csv(out / "pilot_signal_ml_episodes.csv").query(
        "country == 'Finland' and feed == 'peers'").sort_values("origin_month")
    scores = pd.read_csv(out / "frequency_evaluation.csv").query(
        "pilot_rank == 1 and feed == 'peers' and scope == 'all'").set_index("metric")
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.1, 3.9), layout="constrained",
                                      gridspec_kw={"width_ratios": [1.2, 1]})
    time = pd.to_datetime(prior.origin_month)
    real = 100 * prior.future_default_principal / prior.future_principal
    left.scatter(time, real, s=24, color="#536170", label="Realized future default share", zorder=3)
    left.plot(time, 100*prior.q_initial, color="#14766e", lw=2.5, label="Historical frequency")
    left.plot(time, 100*prior.m_origin, color="#b45332", lw=2.2, label="Boosting at issue")
    left.set_xticks(time.iloc[[0, 5, 10, 15, 19]], prior.origin_month.iloc[[0, 5, 10, 15, 19]], fontsize=8)
    left.set_ylabel("Default share (%)")
    left.set_ylim(bottom=-1)
    handles, labels = left.get_legend_handles_labels()
    fig.legend(handles, labels, ncols=3, frameon=False, fontsize=9, loc="outside lower center")
    left.set_title("Finland on the earlier 20 books", loc="left", weight="bold", fontsize=11.5)
    names = [("Historical frequency", "frequency"), ("+ ordinary update", "public"),
             ("+ peers", "common"), ("+ own pilot", "revealed"),
             ("Direct peer frequency", "peer_frequency"), ("Refit boosting, pilot seen", "hgb_seen")]
    vals = [scores.loc["brier_"+key, "mean"] for _, key in names]
    right.scatter(vals, range(len(names)), color=["#536170", "#14766e", "#14766e", "#14766e",
                  "#536170", "#b45332"], s=37, zorder=3)
    right.set_yticks(range(len(names)), [name for name, _ in names], fontsize=9)
    right.invert_yaxis()
    for i, val in enumerate(vals):
        right.annotate(f"{val:.5f}", (val, i), xytext=(6, 0), textcoords="offset points",
                       va="center", fontsize=8)
    right.set_xlim(.0778, .085)
    right.set_xticks([.078, .080, .082, .084])
    right.set_title("Next period · 12 books, three countries", loc="left", weight="bold", fontsize=11.5)
    right.set_xlabel("Brier loss (lower is better)")
    right.margins(y=.12)
    for ax in (left, right):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x" if ax is right else "y", alpha=.14)
    fig.savefig(out / "frequency_forecasts.png", dpi=170, facecolor="white", metadata={"Software":"Matplotlib"})
    plt.close(fig)


def pilot_signal_plot(out):
    results = pd.read_csv(out / "pilot_signal_ml_metrics.csv")
    pooled = results[(results.subset == "full") & (results.country == "ALL")]
    primary = pooled[pooled.feed == "peers"].set_index("metric")
    fig, axes = plt.subplots(1, 2, figsize=(11.1, 4.2), layout="constrained")
    left, right = axes
    levels = [("Historical risk at issue", "brier_initial"), ("Boosting at issue", "brier_origin"),
              ("+ ordinary risk update", "brier_public"), ("+ cohort peers", "brier_peers")]
    for i, (label, metric) in enumerate(levels):
        row = primary.loc[metric]
        color = "#526477" if i == 0 else "#167268"
        left.plot([row.low, row.high], [i, i], color=color, lw=2)
        left.scatter(row["mean"], i, color=color, s=40, zorder=3)
    left.set_yticks(range(len(levels)), [l for l, _ in levels])
    left.set_xlabel("Brier loss (lower is better)")
    left.set_title("How well did each forecast do?", loc="left", weight="bold", fontsize=12)
    comparisons = [("Shared peers", "peers", "brier_private"),
                   ("Peers hidden", "no_peers", "brier_private"),
                   ("Real vs random label¹", "peers", "brier_real_vs_random")]
    for i, (_, feed, metric) in enumerate(comparisons):
        row = pooled[(pooled.feed == feed) & (pooled.metric == metric)].iloc[0]
        right.plot([row.low * 1000, row.high * 1000], [i, i], color="#24568a", lw=2)
        right.scatter(row["mean"] * 1000, i, s=40, color="#24568a", zorder=3)
    right.axvline(0, color="#78848f", ls="--", lw=1)
    right.set_yticks(range(len(comparisons)), [item[0] for item in comparisons])
    right.set_xlabel("Brier improvement × 1,000 (positive helps)")
    right.set_title("What did one pilot add?", loc="left", weight="bold", fontsize=12)
    for ax in axes:
        ax.invert_yaxis()
        ax.margins(y=.22)
        ax.grid(axis="x", alpha=.16)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
    layout = fig.get_layout_engine()
    layout.set(rect=(0, .12, 1, .86), wspace=.08)
    fig.suptitle("Forecasting the next 25 Bondora loans", x=.015, ha="left", weight="bold", fontsize=15)
    fig.text(.015, .04, "48 country–months · 1,200 later loans · 95% intervals from calendar-quarter blocks.  "
             "¹Independent draw using the same modeled default probability.", fontsize=8.2, color="#42556b")
    fig.savefig(out / "pilot_signal_ml.png", dpi=170, facecolor="white", metadata={"Software": "Matplotlib"})
    plt.close(fig)


def signal_sections(out):
    cases = pd.read_csv(out / "finnish_pilot_cases.csv")
    primary = pd.read_csv(out / "pilot_signal_ml_metrics.csv").query(
        "feed == 'peers' and subset == 'full' and country == 'ALL'").set_index("metric")
    c = pd.read_csv(out / "pilot_signal_ml_coverage.csv").query(
        "feed == 'peers' and subset == 'full' and country == 'ALL'").iloc[0]
    comparison = cases[["origin_month", "expected_direct", "expected_information", "expected_total",
                        "incremental_total_cash"]].copy()
    for key in comparison.columns[1:]:
        comparison[key] = comparison[key].map(lambda v: f"{v:+,.2f}")
    comparison.columns = ["Finnish pilot", "Direct forecast (€)", "Forecast value of learning (€)",
                          "Total forecast (€)", "Paired ledger cash if issued (€)"]
    gain = primary.loc["brier_private"]
    return [
        "### Can the lender forecast what this particular pilot will teach it?",
        table(comparison),
        "In March 2021 the previous rule put a 1.20% chance on a changed decision for a nonempty portfolio. The later ordinary risk update brought the portfolio close to break-even. The pilot default then moved risk from 16.47% to 20.45%. In the alternative where both lenders could also see the other 473 loans from that month, the same default moved risk from 7.36% to 7.55% and both would lend. The ledger records funded loans. The extra cash in the table results from replaying the earlier information assumption. [Finnish case reconstruction](../docs/finnish-pilot-cases.md)",
        f"A frozen boosting model priced the two possible observations at issue, then predicted the same future portfolio with its actual pilot outcome hidden and revealed. It learned from 232 earlier country–months. Among {c.scored} later nonempty portfolios, the ordinary update improved its Brier score by {primary.loc['brier_public_refresh','mean']:.5f} and adding other loans from the same cohort improved it by {primary.loc['brier_peer_feed','mean']:.5f}. The simple historical-risk forecast scored {primary.loc['brier_initial','mean']:.5f}, ahead of the boosting model with peers ({primary.loc['brier_peers','mean']:.5f}).",
        f"Revealing just the pilot changed Brier by {gain['mean']:+.6f} in the direction of improvement (95% block interval {gain.low:+.6f} to {gain.high:+.6f}). Of {c.eligible} initially loss-making opportunities, the model chose {c.new_selected}. The earlier selector chose {c.old_selected} and its direct ledger cash summed to {euro(primary.loc['old_cash','mean'] * c.eligible)}. Neither selector captured a strict recovery. Only eight eligible cases had a nonempty continuation, all Dutch. The archive measures gross cash to its cutoff.",
        "![Forecast error by information set and the extra value of a single pilot](pilot_signal_ml.png)",
        "[Frozen design](../docs/pilot-signal-ml-protocol.md) · [Coverage and timing](../docs/pilot-signal-panel.md) · [Model and interpretation](../docs/pilot-signal-ml.md) · [All ablations, cash and intervals](pilot_signal_ml_metrics.csv)",
    ]


def pilot_forecast_plot(out):
    profiles = pd.read_csv(out / "pilot_profiles_selected.csv").sort_values("pilot_month")
    test = pd.read_csv(out / "pilot_holdout_episodes.csv")
    test = test.loc[test.eligible & test["sample"].eq("seasoned")].sort_values(
        ["strict_probability", "origin_month"], ascending=[False, True])
    recovered = test.action_changed & test.pilot_cash.lt(0) & test.net_cash.gt(0)
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.4, 4.9), layout="constrained")
    muted, green, orange = "#75899b", "#087966", "#ba542e"
    y = np.arange(len(profiles))
    ratio = profiles.principal_to_recent_median
    left.hlines(y, 0, ratio, color="#d8e0e6", linewidth=2)
    left.axvline(1, color="#9ca9ae", linestyle=":", zorder=0)
    left.scatter(ratio, y, color=muted, s=36, label="No change of decision")
    for mask, color, marker, label in (
            (profiles.euro_covered, green, "D", "Pilot loss covered"),
            (profiles.action_changed & ~profiles.euro_covered, orange, "X", "Changed decision, net loss")):
        left.scatter(ratio[mask], y[mask], color=color, marker=marker, s=74, label=label)
    labels = (profiles.pilot_month + "   " + profiles.country + " " + profiles.customer)
    left.set_yticks(y, labels, fontsize=8)
    left.invert_yaxis()
    left.set_xlim(0, max(ratio) * 1.08)
    left.set_xlabel("Pilot principal / recent segment median")
    left.set_title("Original ten selected pilots", loc="left", weight="bold")
    left.legend(loc="upper right", fontsize=8, frameon=False)
    x = np.arange(1, len(test)+1)
    prob = 100 * test.strict_probability
    right.plot(x, prob, color="#ccd4db", zorder=0)
    right.scatter(x, prob, color=muted, s=28)
    right.scatter(x[test.selected], prob[test.selected], facecolors="none", edgecolors=orange,
                  linewidths=1.6, s=105, label="Selected by revised rule")
    right.scatter(x[recovered], prob[recovered], marker="D", color=green, s=75,
                  label="Pilot loss covered")
    right.set(xlabel="Rank at issue (highest forecast first)", ylabel="Forecast chance of recovery (%)")
    right.set_xticks([1, 5, 9, 15, 20, len(test)])
    right.set_title("Later Bondora test, eligible pilots", loc="left", weight="bold")
    right.legend(frameon=False, fontsize=8)
    for ax in (left, right):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=.10)
        ax.tick_params(length=3)
    fig.savefig(out / "pilot_forecast_validation.png", dpi=165, metadata={"Software": "Matplotlib"})
    plt.close(fig)


def frozen_rule_sections(out):
    summary = pd.read_csv(out / "pilot_rule_summary.csv").set_index("cohort")
    cells = pd.read_csv(out / "pilot_holdout_cohort.csv").set_index("sample")
    cohorts = [("expanded_12m", "Bondora discovery, expanded", "€"),
               ("primary", "Bondora, June–September 2024", "€"),
               ("seasoned", "Bondora, July 2020–September 2022", "€"),
               ("prosper", "Prosper, January 2008–January 2012", "$")]
    rows = []
    for key, label, unit in cohorts:
        row = summary.loc[key]
        def money(column):
            v = row[column]
            return "—" if pd.isna(v) else f"{unit}{v:,.2f}"
        rows.append({"Cohort": label, "Eligible": row.eligible, "Old / new issued":
                     f"{row.baseline_selected} / {row.selected}", "Strict recoveries caught / available":
                     f"{row.new_cash_tp} / {row.cash_recoveries}" if row.eligible else "—",
                     "New vs skip per eligible": money("new_cash"),
                     "New minus old per eligible": money("new_minus_baseline_cash")})
    dev, test, us = [summary.loc[x] for x in ["expanded_12m", "seasoned", "prosper"]]
    return ["### Did a cheaper pilot and an exposure-aware forecast transfer?",
            "Both Estonian successes had €530 principal on a 36-month contract and five prior loans. July's €530 pilot left the follow-up action unchanged. The revised rule values the next up to 25 loans at an exposure estimated before origination. It also allows the bank's ordinary risk estimate to change while waiting. The expected cash gain sets the funding decision. A separate score ranks the chance that a change of action will cover a direct pilot loss.",
            table(pd.DataFrame(rows)),
            f"The two development cases were already known. The new rule selected {dev.selected} pilots, retained the unsuccessful February switch and added {euro(dev.new_minus_baseline_cash)} per eligible opportunity over the old rule (95% block interval {euro(dev.new_minus_baseline_cash_low)} to {euro(dev.new_minus_baseline_cash_high)}). Doubling the effective strength of historical information or sharing the other matured same-month loans removed all three original switches.",
            f"The primary holdout had {cells.loc['primary', 'window_issued']:,} funded loans and no comparable grade histories. In the more seasoned window the revised rule earned {euro(test.new_cash)} per eligible opportunity (95% block interval {euro(test.new_cash_low)} to {euro(test.new_cash_high)}). Every euro came from the pilot loans themselves. The missed Finnish pilot lost €386.82; its replayed refusal of 25 follow-ups would have yielded €3,716.92 net on cash recorded in the November 2026 release. Later collections can change that number.",
            f"The strict-recovery score had AUC {test.auc_cash:.3f} (95% interval {test.auc_cash_low:.3f} to {test.auc_cash_high:.3f} on {test.auc_cash_draws:,} estimable draws of 2,500). This clears the prespecified numerical ranking criterion. There was one positive example. Its Finnish score beat seven of 15 comparable negatives (within-segment AUC {test.cash_segment_auc:.3f}). Average precision was {test.ap_cash:.3f} versus a prevalence of {test.cash_prevalence:.3f}. No rule that issued a pilot on these dates captured the strict event.",
            f"The same decision rule selected {us.selected} of {us.eligible} opportunities at US lender Prosper. The archive supplied no strict recoveries among those eligible opportunities and thus no estimable AUC. The two US policies tied at the archived cash cutoff. This supplementary cross-lender test was locked after the Bondora results and before computing the Prosper pilot contrasts.",
            "![Historical contract size and the later ranking of all eligible candidates](pilot_forecast_validation.png)",
            "[Origination profiles](../docs/pilot-profiles.md) · [Information sensitivity](../docs/pilot-signal-sensitivity.md) · [Frozen model](../docs/pilot-rule-protocol.md) · [Bondora](../docs/pilot-holdout.md) · [Prosper](../docs/pilot-prosper.md) · [All policy results, ablations and intervals](pilot_rule_summary.csv)"]


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
        "[Research contributions, methods and limitations](../docs/contributions.md)",
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


def hard_selection_section(out):
    """Soft versus hard historical acceptance on the same index, folds and models."""
    h = pd.read_csv(out / "hard_selection.csv")
    soft_eval = pd.read_csv(out / "evaluation_rmse.csv").query("metric == 'abr'").set_index(["dataset", "method"]).rmse
    soft_abr = pd.read_csv(out / "training.csv").groupby(["dataset", "method"]).abr.mean()
    rows = []
    for dataset in ("taiwan", "prosper"):
        def get(design, q, dataset=dataset):
            return h[(h.dataset == dataset) & (h.design == design) & (h.quantity == q)].estimate.iloc[0]
        for design in ("soft", "hard"):
            if design == "soft":
                ev = (soft_eval[(dataset, "accepts")], soft_eval[(dataset, "bayes")])
                tr = (soft_abr[(dataset, "accepts")], soft_abr[(dataset, "basl")])
            else:
                ev = (get("hard", "accepts_eval_rmse_abr"), get("hard", "bayes_eval_rmse_abr"))
                tr = (get("hard", "accepts_test_abr"), get("hard", "basl_test_abr"))
            rows.append([NAMES[dataset], design, f"{100 * get(design, 'accepted_share'):.1f}%",
                         f"{100 * get(design, 'bad_rate_accepted'):.1f}% / {100 * get(design, 'bad_rate_rejected'):.1f}%",
                         f"{100 * ev[0]:.2f} → {100 * ev[1]:.2f}", f"{100 * tr[0]:.2f}% → {100 * tr[1]:.2f}%"])
    def diag(quantity):
        return h[(h.dataset == "taiwan") & (h.design == "hard") & (h.quantity == quantity)].estimate.iloc[0]

    hard_folds = pd.read_csv(out / "hard_selection_training.csv").query("dataset == 'taiwan'").pivot(
        index="fold", columns="method", values="abr")
    raised_defaults = (hard_folds.basl > hard_folds.accepts).sum()
    frame = pd.DataFrame(rows, columns=["Data", "Historical policy", "Accepted", "Bad rate, accepted / rejected",
                                        "ABR estimation error, pp (accepted-only → Bayesian)",
                                        "Test ABR (accepted-only → BASL)"])
    return [
        "## Does a hard historical cutoff change the conclusions?",
        "The main design accepts each applicant with probability 0.05 + 0.90 expit(index), so every applicant can be "
        "observed. This sensitivity keeps the index, folds, seeds, models and priors, and accepts the applicants with the "
        "highest index, keeping tied values together and matching the acceptance share as closely as the ties allow. "
        "Historical rejects then never resemble accepts on the index, as under a scorecard cutoff.",
        table(frame),
        "Stronger selection makes accepted-only evaluation worse and Bayesian evaluation helps more; on Taiwan the paired "
        f"interval now excludes zero. BASL raises approved defaults in {raised_defaults} of {len(hard_folds)} Taiwan folds. The "
        "borrower-bootstrap intervals hold the fitted models fixed and omit variation across refits. On the hard-cutoff validation rejects the "
        f"accepts-trained logistic prior averages {100 * diag('reject_prior_mean'):.1f}% against an actual "
        f"{100 * diag('reject_bad_rate_validation'):.1f}% and ranks them with AUC {diag('reject_prior_auc'):.2f}. "
        "This measures the evaluation prior. BASL fits a separate labeler in each round, so the prior's AUC alone "
        "cannot identify the cause of BASL's higher default rate. The check was added after the main results and is exploratory. "
        "[Design and interpretation](../docs/hard-selection.md) · [All quantities](hard_selection.csv)",
    ]


STRENGTHS = ["0.5", "1", "2", "4", "hard"]


def strength_table(out):
    """Taiwan quantities from the prespecified selection-strength study, indexed by (strength, quantity)."""
    st = pd.read_csv(out / "selection_strength.csv")
    return st[st.dataset == "taiwan"].set_index(["strength", "quantity"])


def strength_bullet(out):
    st = strength_table(out)
    v = lambda s, q, col="estimate": st.loc[(s, q), col]
    signed = lambda x: f"{100 * x:+.2f}".replace("-", "−")
    ci = lambda s, q: f"{signed(v(s, q))} pp [{signed(v(s, q, 'ci_low'))}, {signed(v(s, q, 'ci_high'))}]"
    return [
        f"- **When reject inference works (prespecified).** Across the Taiwan selection grid, "
        f"the estimation error using only accepted labels ranges from {100 * v('0.5', 'accepts_rmse'):.2f} to "
        f"{100 * v('hard', 'accepts_rmse'):.2f} pp. Bayesian evaluation reduces error at the steepest finite slope "
        f"({ci('4', 'bayes_logistic_minus_accepts_rmse')} at s = 4). We evaluate the "
        f"accepts-trained logistic prior on validation rejects: AUC {v('1', 'logistic_reject_auc'):.2f} "
        f"at s = 1 and {v('hard', 'logistic_reject_auc'):.2f} under a hard cutoff, where BASL raises the default rate by "
        f"{signed(v('hard', 'B_minus_A'))} pp (folds {signed(v('hard', 'B_minus_A', 'fold_min'))} to "
        f"{signed(v('hard', 'B_minus_A', 'fold_max'))}). A random 5% audit of training rejects lifts that AUC to "
        f"{v('hard', 'audited_reject_auc'):.2f} and the audited BASL gap is {ci('hard', 'Bplus_minus_Aplus')}. Adding "
        f"audited outcomes to ordinary supervised training changes the approved default rate by {ci('hard', 'Aplus_minus_A')}. "
        "[Comparison with the independent Linux refit](../docs/platform-refit.md).",
    ]


def selection_strength_section(out):
    st = strength_table(out)
    v = lambda s, q, col="estimate": st.loc[(s, q), col]
    pp = lambda x: f"{100 * x:+.2f}".replace("-", "−")
    rows = [
        ["Bad rate, accepted / rejected"] + [f"{100 * v(s, 'bad_rate_accepted'):.1f} / {100 * v(s, 'bad_rate_rejected'):.1f}%" for s in STRENGTHS],
        ["Evaluation error, accepted labels, pp"] + [f"{100 * v(s, 'accepts_rmse'):.2f}" for s in STRENGTHS],
        ["Evaluation error, Bayesian with logistic prior"] + [f"{100 * v(s, 'bayes_logistic_rmse'):.2f}" for s in STRENGTHS],
        ["Evaluation error, Bayesian with audited prior"] + [f"{100 * v(s, 'bayes_audited_rmse'):.2f}" for s in STRENGTHS],
        ["Reject AUC, logistic / audited prior"] + [f"{v(s, 'logistic_reject_auc'):.2f} / {v(s, 'audited_reject_auc'):.2f}" for s in STRENGTHS],
        ["BASL − accepted-only ABR, pp (fold range)"] + [
            f"{pp(v(s, 'B_minus_A'))} ({pp(v(s, 'B_minus_A', 'fold_min'))} to {pp(v(s, 'B_minus_A', 'fold_max'))})"
            for s in STRENGTHS],
        ["Same with the audit"] + [pp(v(s, "Bplus_minus_Aplus")) for s in STRENGTHS],
        ["Training on audited outcomes, ABR change, pp"] + [pp(v(s, "Aplus_minus_A")) for s in STRENGTHS],
    ]
    frame = pd.DataFrame(rows, columns=["Taiwan", *[f"s = {s}" if s != "hard" else "hard" for s in STRENGTHS]])
    return [
        "## When does reject inference work?",
        "At finite slopes the simulation targets the same expected approval share. Under the hard cutoff, preserving tied scores raises the realized Taiwan approval share from 63.7% to 67.3%. We add a "
        "random 5% audit of training rejects to the reject model. Folds, seeds and scorecards follow the main experiment.",
        table(frame),
        "On Taiwan the Bayesian correction reduces estimation error at slope 4 and under the hard cutoff. Under that cutoff the "
        "accepts-trained evaluation prior ranks validation rejects poorly. Revealing outcomes for a random sample of "
        "training rejects improves its ranking, and adding the revealed labels to ordinary scorecard training lowers "
        "approved defaults. Prosper has one later-period holdout. The hypothesis table reports results across both cohorts. "
        "[Protocol](../docs/selection-strength-protocol.md) · [Results and hypotheses](../docs/selection-strength.md) · "
        "[All quantities](selection_strength.csv)",
    ]


def summary_section(out, sims, comp, contrast):
    """Headline results, recomputed from the same tables as the sections below."""
    sim = sims[sims.metric == "abr"].set_index("statistic")
    pp = lambda v: f"{100 * v:.2f}"
    ci = contrast.set_index(["dataset", "contrast"])
    t2 = comp[(comp.table == 2) & (comp.metric == "abr")].set_index("method")
    info = pd.read_csv(out / "policy_information_summary.csv").groupby("design").sum(numeric_only=True)
    frontier = pd.read_csv(out / "information_value_frontier.csv")
    base = frontier[(frontier.discount == 1) & (frontier.delay == 1) & (frontier.fee == 0)].set_index("reset")
    dutch = pd.read_csv(out / "early_dutch_episodes.csv")
    czech = pd.read_csv(out / "early_czech_metrics.csv").set_index("method")
    switch = pd.read_csv(out / "early_czech_policy.csv").query("method == 'six' and reference == 'local' and good == 0.1")
    rec = sim.loc["basl_recovery_fraction"]
    lower = dutch[["local", "broader"]].min(axis=1)
    hits = int((dutch.six_month_below_both & dutch.realized_below_both).sum())
    own_hits = int(((dutch.revised_young_year_rate < lower) & dutch.realized_below_both).sum())
    hard = pd.read_csv(out / "hard_selection.csv").set_index(["dataset", "quantity"])
    hard = hard[~hard.index.duplicated()]

    folds = pd.read_csv(out / "hard_selection_training.csv").query("dataset == 'taiwan'")
    folds = folds.pivot(index="fold", columns="method", values="abr")
    gaps = (100 * (folds.basl - folds.accepts)).tolist()
    worse = sum(g > 0 for g in gaps)

    def hard_interval(dataset, name):
        row = hard.loc[(dataset, name)]
        signed = lambda v: f"{100 * v:+.2f}".replace("-", "−")
        return f"{signed(row.estimate)} pp [{signed(row.ci_low)}, {signed(row.ci_high)}]"

    within = pd.read_csv(out / "evaluation.csv").query("metric == 'abr'").copy()
    within["squared"] = within.within_cohort_error ** 2
    same = within.groupby(["dataset", "method"]).squared.mean().pow(.5)

    def interval(dataset, name):
        row = ci.loc[(dataset, name)]
        signed = lambda v: f"{100 * v:+.2f}".replace("-", "−")
        return f"{signed(row.estimate)} pp [{signed(row.ci_low)}, {signed(row.ci_high)}]"

    return [
        "## Summary",
        f"- **Simulation.** Bayesian evaluation cuts the error in estimating ABR from {pp(sim.loc['accept_eval_rmse','estimate'])} "
        f"to {pp(sim.loc['bayes_eval_rmse','estimate'])} pp (paper: {pp(sim.loc['accept_eval_rmse','paper_value'])} to "
        f"{pp(sim.loc['bayes_eval_rmse','paper_value'])}). BASL recovers {rec.estimate:.1%} of the gap to full-label training "
        f"(95% interval {rec.ci_low:.1%} to {rec.ci_high:.1%}; paper {rec.paper_value:.1%}).",
        f"- **Public cohorts.** Bayesian evaluation lowers the ABR estimation error on Taiwan ({pp(t2.loc['accepts','taiwan'])} → "
        f"{pp(t2.loc['bayes','taiwan'])} pp) and Prosper ({pp(t2.loc['accepts','prosper'])} → {pp(t2.loc['bayes','prosper'])} pp), "
        f"but the paired changes, {interval('taiwan','bayes_minus_accepts_rmse_abr')} and {interval('prosper','bayes_minus_accepts_rmse_abr')}, "
        f"include zero. BASL changes ABR by {interval('taiwan','basl_minus_accepts_abr')} on Taiwan and "
        f"{interval('prosper','basl_minus_accepts_abr')} on Prosper. At 50% LGD every evaluator picks the same cutoff, "
        "so the paper's profit gain does not appear here. On the same Taiwan cohort, with no change of population, Bayesian "
        f"evaluation is worse ({pp(same['taiwan','bayes'])} versus {pp(same['taiwan','accepts'])} pp) because its logistic "
        f"prior is weak there; on Prosper it improves ({pp(same['prosper','accepts'])} → {pp(same['prosper','bayes'])} pp).",
        *strength_bullet(out),
        f"- **Which outcomes decide a policy.** Totals for the four bands between five cutoffs identify "
        f"{int(info.loc['expansion_bands','pairs_exact_at_actual_binary_totals'])} of {int(info.loc['expansion_bands','n_policy_pairs'])} "
        f"pairwise differences; totals for ten prior-risk deciles identify {int(info.loc['prior_deciles','pairs_exact_at_actual_binary_totals'])}.",
        f"- **Lending to learn.** In the illustrative model a pilot of principal 100 loses {-100 * base.loc[0, 'prior_margin']:.2f}; "
        f"with persistent risk its outcome pays back after {int(base.loc[0, 'first_followups'])} later loans, and with a 10% "
        f"chance of a reset per loan the total value is capped at {100 * base.loc[0.1, 'evsi_limit']:.2f}. In later Bondora "
        "loans the frozen selector missed the only recovery.",
        f"- **Early defaults.** On eight Dutch dates the six-month forecast averaged {dutch.six_month.mean():.2%} against "
        f"{dutch.target.mean():.2%} realized and histories of {dutch.local.mean():.2%} and {dutch.broader.mean():.2%}. At a "
        f"Czech bank the fixed rule changed {int(switch.extra_books.iloc[0] + switch.dropped_books.iloc[0])} of "
        f"{int(switch.books.iloc[0])} book decisions, but the other-region rate kept the lowest Brier loss "
        f"({czech.loc['other','brier']:.4f} versus {czech.loc['six','brier']:.4f}). Of the {hits} correct Dutch warnings, "
        f"{hits - own_hits} disappear if the young cohorts' own year-one rate replaces the six-month conversion, so the "
        "conversion's undershoot did part of the work.",
        "Outcomes on Taiwan and Prosper come from funded loans with simulated selection; the Monedo randomized holdout "
        "is private. Extension samples are small, and the sections below give each design and its uncertainty.",
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
        "This report uses the July 2024 preprint and public borrower records. An approval scorecard is needed for everyone who applies, while repayment is usually observed only for the people actually financed. Training with inferred labels and evaluating on the complete applicant mix solve different problems.",
        *summary_section(out, sims, comp, contrast),
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
        *hard_selection_section(out),
        *selection_strength_section(out),
        "## Can a small randomized audit improve ABR measurement?",table(audit),
        "For a fixed proposed 30% approval policy, each audit reveals 10 or 50 funded outcomes under controlled masking. Both designs reveal the same number of outcomes. Financial exploration costs may differ. Targeting only previously declined borrowers whom this policy would approve lowers sampling variability. Compare against prior-only RMSE as well: a good prior can beat a noisy small audit on a given cohort. Random disclosure identifies the fixed-policy default rate in this finite validation cohort; small samples may still be imprecise. Each result pools squared error across 500 draws per split before taking the square root.",
        *extension_sections(out),
        *frozen_rule_sections(out),
        *signal_sections(out),
        *frequency_sections(out),
        *trust_sections(out),
        *early_payment_section(out),
        "## Limits and a three-month follow-up",
        "We can test label concealment among already funded borrowers. A randomized sample of actual would-be declines with mature repayment labels would identify the target population more directly. Collect such a sample under a fixed decision policy, estimate default and realized net revenue with funding costs, and repeat across time vintages and adequate overlap regions. Twelve Prosper quarters provide evidence on temporal transfer at one lender. Profit net of financing and servicing costs and transport to other macroeconomic conditions still require additional data.",
        "[Data provenance](../docs/sources.md) · [Implementation](../docs/algorithm.md) · [Deviations](../docs/deviations.md) · [Simulation](../docs/simulation.md)"
    ]
    pilot_forecast_plot(out)
    pilot_signal_plot(out)
    frequency_plot(out)
    trust_plot(out)
    (out/"report.md").write_text("\n\n".join(sections)+"\n")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    out=parser.parse_args().out
    calibration_plot(out)
    pilot_cash_plot(out)
    write_report(out, comparison(out))

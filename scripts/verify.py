"""Verify deliverable consistency, without imposing a preferred empirical finding."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from numpy.testing import assert_allclose


def verify_extensions(out):
    history = pd.read_csv(out / "vintage_forecasts.csv")
    summary = pd.read_csv(out / "vintage_summary.csv").set_index("method")
    assert history.quarter.nunique() == 12 and len(history) == 48
    assert history.groupby("quarter").method.nunique().eq(4).all()
    assert_allclose(history.forecast_error, history.masking_error + history.historical_minus_future_abr,
                    atol=1e-10)
    assert_allclose(summary.forecast_rmse**2, summary.masking_rmse**2 + summary.drift_rmse**2
                    + summary.mean_cross_term, atol=1e-10)
    expected = history.assign(squared=history.forecast_error**2).groupby("method").squared.mean()
    assert_allclose(summary.forecast_rmse.sort_index()**2, expected, atol=1e-10)

    policy = pd.read_csv(out / "bounds_policy.csv")
    assert len(policy) == 5 * 8 * 2
    assert (policy.validation_worst_gain >= -policy.budget - 1e-9).all()
    assert (policy.realized_test_gain >= policy.test_binary_gain_lower - 1e-9).all()
    assert (policy.realized_test_gain <= policy.test_binary_gain_upper + 1e-9).all()
    frontier = pd.read_csv(out / "bounds_frontier.csv").sort_values("gamma")
    for _, path in frontier.groupby(["dataset","fold","target"]):
        assert (np.diff(path.delta_lower) <= 1e-9).all()
        assert (np.diff(path.delta_upper) >= -1e-9).all()
    agg = policy.groupby(["dataset","gamma","budget"]).realized_test_gain.mean()
    output = pd.read_csv(out / "bounds_summary.csv").set_index(["dataset","gamma","budget"])
    assert_allclose(agg, output.mean_realized_test_gain.sort_index(), atol=1e-9)

    rct = pd.read_csv(out / "rct_cells.csv")
    arms = rct.groupby("assigned_offer")[["n","funded"]].sum()
    assert arms.loc[1].tolist() == [891,650] and arms.loc[0].tolist() == [222,4]
    values = pd.read_csv(out / "rct_contrasts.csv").set_index("estimand").estimate
    # Only the low-score window changes when the bank expands the offer policy.
    low = rct[rct.window == "low"].set_index("assigned_offer")
    w = low.n.sum() / rct.n.sum()
    delta_cash = w * (low.loc[1,"mean_cash_revenue"] - low.loc[0,"mean_cash_revenue"])
    assert_allclose(delta_cash,values["offer_all_minus_high_only_cash_revenue"],atol=1e-8)
    bound_width = values["all_funded_hypothetical_risk_upper"]-values["all_funded_hypothetical_risk_lower"]
    assert_allclose(bound_width,1-values["funding_if_offer"],atol=1e-9)
    transfer = pd.read_csv(out / "rct_prior_transfer.csv").iloc[0]
    assert_allclose(transfer.expected_low_events,transfer.high_events/transfer.high_funded*transfer.low_funded)
    for figure in ("vintage_forecasts.png","bounds_frontier.png","rct_policy.png"):
        assert (out / figure).read_bytes().startswith(bytes.fromhex("89504e470d0a1a0a"))



def verify_identification_and_audit(out):
    worlds = pd.read_csv(out / "identification_worlds.csv")
    grid = worlds[(worlds.grid == "two") & (worlds.constraint != "unrestricted")]
    assert len(grid) == 20
    assert (grid.oracle_audit_only == grid.constraint.eq("oracle_decile_totals")).all()
    for _, pair in grid.groupby(["dataset", "fold", "constraint"]):
        assert len(pair) == 2
        for col in ("n_observed", "observed_defaults", "hidden_defaults_by_prior_decile"):
            assert pair[col].nunique() == 1
        assert_allclose(pair.change_30_to_50, (.10*pair.changed_cases - .55*pair.changed_defaults) / pair.n)
    deciles = pd.read_csv(out / "identification_deciles.csv")
    assert len(deciles) == 50
    # Counts alone pin down both endpoints within each prior band.
    min_hidden = np.maximum(0, deciles.oracle_hidden_defaults - (deciles.hidden_cases - deciles.hidden_switchers))
    max_hidden = np.minimum(deciles.hidden_switchers, deciles.oracle_hidden_defaults)
    assert_allclose(min_hidden, deciles.min_hidden_switcher_defaults)
    assert_allclose(max_hidden, deciles.max_hidden_switcher_defaults)
    actual = grid[grid.oracle_audit_only]
    for (dataset, fold), bands in deciles.groupby(["dataset", "fold"]):
        assert bands.prior_decile.nunique() == 10
        endpoints = actual[(actual.dataset == dataset) & (actual.fold == fold)].changed_defaults
        known = bands.known_switcher_defaults_fold.iloc[0]
        assert known + bands.min_hidden_switcher_defaults.sum() == endpoints.min()
        assert known + bands.max_hidden_switcher_defaults.sum() == endpoints.max()

    policies = pd.read_csv(out / "identification_policies.csv")
    groups = policies.groupby(["dataset", "fold", "grid", "constraint"])
    assert_allclose(groups.lottery_weight.sum(), 1., atol=1e-9)
    assert (policies.worst_lottery <= policies.worst_deterministic + 1e-10).all()
    assert (policies.lottery_weight >= 0).all()
    assert groups.pure_choice.sum().eq(1).all()
    paths = pd.read_csv(out / "decision_audit_paths.csv")
    audit = pd.read_csv(out / "decision_audit_summary.csv")
    assert len(audit) == 15
    oracle = grid[grid.oracle_audit_only].groupby(["dataset", "fold"]).changed_defaults
    truth = audit[audit.scenario == "retrospective_truth"].set_index(["dataset", "fold"])
    realized = truth.visible_defaults + truth.hidden_defaults
    assert realized.between(oracle.min().reindex(realized.index), oracle.max().reindex(realized.index)).all()
    for row in audit.itertuples():
        sub = paths[(paths.dataset == row.dataset) & (paths.fold == row.fold) &
                    (paths.scenario == row.scenario)].sort_values("labels")
        first_stop = sub.first_expand + sub.first_retain
        assert_allclose(1 - first_stop.cumsum(), sub.unresolved, atol=1e-10)
        assert_allclose((first_stop * sub.labels).sum(), row.mean_labels, atol=1e-8)
        assert_allclose(first_stop.sum(), 1., atol=1e-10)
        assert (2 * row.switchers > 11 * (row.visible_defaults + row.hidden_defaults)) == row.expand_profitable
        wrong = sub.first_retain if row.expand_profitable else sub.first_expand
        assert_allclose(wrong.sum(), row.p_wrong, atol=1e-10)
        assert row.p_wrong <= .05 + 1e-10



def verify_information_and_learning(out):
    pairs = pd.read_csv(out / "policy_information_pairs.csv")
    summaries = pd.read_csv(out / "policy_information_summary.csv")
    assert len(pairs) == 100 and len(summaries) == 10
    for row in summaries.itertuples():
        same = (pairs.dataset == row.dataset) & (pairs.fold == row.fold) & (pairs.design == row.design)
        sub = pairs.loc[same]
        assert len(sub) == row.n_policy_pairs
        assert sub.exact_at_actual_binary_totals.sum() == row.pairs_exact_at_actual_binary_totals
        assert sub.identified_for_all_expected_margins.sum() == row.pairs_identified_for_all_expected_margins
        assert sub.decision_at_actual_binary_totals.ne("undetermined").sum() == row.decisions_settled_at_actual_binary_totals
        assert (sub.fully_observed_gain >= sub.lower_gain - 1e-9).all()
        assert (sub.fully_observed_gain <= sub.upper_gain + 1e-9).all()
    aligned = pairs[pairs.design == "expansion_bands"]
    assert_allclose(aligned.lower_gain, aligned.upper_gain, atol=1e-9)
    # Consecutive policy gains must add up to every wider expansion on the same fold.
    for _, cohort in aligned.groupby(["dataset", "fold"]):
        target = sorted(set(cohort.from_target) | set(cohort.to_target))
        gains = cohort.set_index(["from_target", "to_target"]).fully_observed_gain
        prefix = np.r_[0., np.cumsum([gains.loc[(l,r)] for l,r in zip(target, target[1:])])]
        for (l,r), gain in gains.items():
            assert_allclose(gain, prefix[target.index(r)] - prefix[target.index(l)], atol=1e-9)

    policies = pd.read_csv(out / "exploration_values.csv").set_index(["reset", "horizon"]).sort_index()
    branches = pd.read_csv(out / "exploration_branches.csv")
    assert len(policies) == 80 and len(branches) == 2 * len(policies)
    resets = ["reset", "horizon"]
    assert_allclose(branches.groupby(resets).outcome_probability.sum(), 1., atol=1e-10)
    continuation = (branches.outcome_probability * branches.next_value).groupby(
        [branches.reset, branches.horizon]).sum()
    assert_allclose(policies.fund_value, policies.immediate_margin + continuation, atol=1e-10)
    assert_allclose(policies.adaptive_value, policies[["fund_value", "wait_value", "stop_value"]].max(axis=1))
    assert_allclose(policies.first_signal_value, continuation - policies.wait_value, atol=1e-10)
    assert (policies.adaptive_value <= policies.current_regime_oracle + 1e-9).all()
    assert (policies.adaptive_value >= policies.best_fixed - 1e-9).all()
    assert_allclose(policies.loc[1.].first_signal_value, 0., atol=1e-10)
    assert (out / "exploration_value.png").read_bytes().startswith(bytes.fromhex("89504e470d0a1a0a"))


def verify_cost_of_a_pilot(out):
    from paper11.pilot_dependence import signal_value

    frontier = pd.read_csv(out / "information_value_frontier.csv")
    assert not frontier.duplicated(["reset", "discount", "delay", "fee"]).any()
    p, variance = .55 * .05 + .45 * .40, .55 * .45 * (.40 - .05)**2
    margin = .10 - .55 * p
    for row in frontier.itertuples():
        # Reconstruct each feasible two-by-two table from its marginal risks and covariance.
        by_date = [row.discount**j * signal_value(
            p, p, p*p + variance*(1-row.reset)**j, .10, -.45) for j in range(row.delay, 11)]
        assert_allclose(row.net_at_ten, margin - row.fee + sum(by_date), atol=1e-10)
        assert row.ever_pays == pd.notna(row.first_followups)
    no_decay = frontier.query("reset == 0 and discount == 1 and delay == 1 and fee == 0")
    assert no_decay.first_followups.item() == 3
    assert_allclose(frontier[frontier.reset == 1].evsi_at_ten, 0.)
    stress = pd.read_csv(out / "information_value_stress.csv")
    assert not stress.duplicated(["reset", "discount", "delay", "fee", "followups"]).any()
    assert stress.scenarios.sum() == 816480
    assert stress.strictly_worthwhile_loss_making.between(0, stress.loss_making).all()
    assert stress.no_signal_value.between(0, stress.scenarios).all()
    assert stress.max_abs_posterior_error.max() < 1e-11
    assert (stress.mean_committed_evsi <= stress.mean_evsi + 1e-11).all()
    bellman = pd.read_csv(out / "information_value_bellman.csv")
    assert len(bellman) == 486
    assert (bellman.fully_adaptive + 1e-10 >= bellman.pilot_only).all()
    assert_allclose(bellman[bellman.horizon == 2].fully_adaptive,
                    bellman[bellman.horizon == 2].pilot_only, atol=1e-10)

    cohort = pd.read_csv(out / "pilot_replay_cohort.csv").iloc[0]
    exclusions = ("missing_disbursement", "disbursement_precedes_approval",
                  "outside_census_regions", "immature")
    assert cohort.source_rows == cohort.retained + sum(cohort[key] for key in exclusions)
    panel = pd.read_csv(out / "pilot_replay_episodes.csv")
    summary = pd.read_csv(out / "pilot_replay_summary.csv")
    keys = ["sampling", "terms", "pilot_quarter", "region"]
    assert not panel.duplicated(keys).any()
    periods = lambda column: pd.PeriodIndex(panel[column], freq="Q").asi8
    assert (periods("future_quarter") - periods("pilot_quarter") == panel.maturity_quarters).all()
    assert (periods("last_mature_at_pilot") + panel.maturity_quarters == periods("pilot_quarter")).all()
    assert (periods("last_common_at_followup") < periods("pilot_quarter")).all()
    primary = panel.query("sampling == 'chronological' and terms == 'early_national'")
    assert len(primary) == primary.region.nunique() * primary.pilot_quarter.nunique() == 120
    assert primary.future_pool.sum() == cohort.continuation_pool_loans
    assert (panel.future_capacity == 25).all() and (panel.future_pool >= panel.future_capacity).all()
    assert panel.sampling_pilot_rate.between(0, 1).all() and panel.sampling_future_rate.between(0, 1).all()
    assert not (panel.model_pilots & ~panel.eligible).any()
    for strategy, selection in (("model", panel.model_pilots), ("forced", panel.eligible)):
        pilot_margin = panel.interest - (panel.interest + panel.default_loss)*panel.sampling_pilot_rate
        future_margin = panel.future_capacity * (
            panel.interest - (panel.interest + panel.default_loss)*panel.sampling_future_rate)
        funded_share = (1 - panel.sampling_pilot_rate)*panel.lend_after_no_event + panel.sampling_pilot_rate*panel.lend_after_event
        gain = selection * panel.pilot_arrival_probability * (funded_share-panel.fresh_lend.astype(int)) * future_margin
        assert_allclose(panel[strategy+"_gross"], gain, atol=1e-9)
        assert_allclose(panel[strategy+"_pilot_margin"], selection*panel.pilot_arrival_probability*pilot_margin, atol=1e-10)
        assert_allclose(panel[strategy+"_total"] - panel.no_pilot_fresh, panel[strategy+"_net"], atol=1e-10)
        for name, sub in panel.groupby(["sampling", "terms"]):
            selected = sub[sub.eligible]
            rows = summary[(summary.sampling == name[0]) & (summary.terms == name[1]) &
                           (summary.strategy == strategy)]
            assert (rows.eligible_cells == len(selected)).all()
            for row in rows.itertuples():
                if row.measure == "no_pilot_decline":
                    actual = 0. if len(selected) else np.nan
                else:
                    col = row.measure if row.measure.startswith("no_pilot_") else strategy+"_"+row.measure
                    actual = selected[col].mean()
                assert_allclose(row.mean_per_eligible_episode, actual, atol=1e-9, equal_nan=True)


def verify(out):
    def read(name):
        return pd.read_csv(out / (name + ".csv"))
    t, e, b = read("training"), read("evaluation"), read("policy")
    assert set(t.dataset) == {"prosper","taiwan"}
    assert t.groupby(["dataset","fold"]).ngroups == 5
    assert t.groupby(["dataset","fold"]).size().eq(6).all()
    assert t[["auc","pauc","abr","brier"]].apply(lambda c:c.between(0,1).all()).all()
    assert ((b.cutoff >= 0) & (b.cutoff <= 1)).all()
    assert_allclose(b.profit_per_issued, .10-1.10*b.lgd*b.test_abr, atol=1e-9)
    assert_allclose(b.profit_per_applicant, b.profit_per_issued*b.test_approval, atol=1e-9)
    rms = read("evaluation_rmse").set_index(["dataset","method","metric"]).sort_index()
    expected = e.assign(sq=e.error**2).groupby(["dataset","method","metric"]).sq.mean().pow(.5)
    assert_allclose(rms.rmse, expected, atol=1e-9)
    assert_allclose(e.error, e.estimate-e.truth, atol=1e-9)
    assert_allclose(e.within_cohort_error, e.estimate-e.validation_oracle_audit, atol=1e-9)
    tr = read("simulation_trajectory")
    assert tr.seed.nunique() == 20 and len(tr) == 100
    assert len(read("simulation_fig2_digitized")) > 0
    for name in ("simulation_fig2.png","calibration.png"):
        assert (out/name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    cal = read("calibration").groupby(["dataset","fold","method"]).n.sum()
    parts = read("partitions")
    n_test = parts[parts.role=="test"].set_index(["dataset","fold"]).n
    for (ds,fold,_),n in cal.items():
        assert n == n_test.loc[(ds,fold)]
    ref = read("paper_comparison").set_index(["table","method","metric"])
    assert len(ref)==28
    by_model = t.groupby(["dataset","method"]).mean(numeric_only=True)
    for (table,method,metric),row in ref.iterrows():
        for ds in ("prosper","taiwan"):
            target = rms.loc[(ds,method,metric),"rmse"] if table==2 else by_model.loc[(ds,method),metric]
            assert_allclose(row[ds],target,atol=1e-9)
    audit = read("audit_budget")
    assert (audit.n_audited <= audit.n_pool).all() and audit.draws.eq(500).all()
    summary = read("audit_summary").set_index(["dataset","n_audited","design"]).sort_index()
    expected = audit.assign(square=audit.audit_rmse**2).groupby(["dataset","n_audited","design"]).square.mean()
    assert_allclose(summary.audit_rmse, np.sqrt(expected), atol=1e-9)
    diff = read("uncertainty").set_index(["dataset","contrast"])
    for ds in ("taiwan","prosper"):
        delta = by_model.loc[(ds,"basl"),"abr"]-by_model.loc[(ds,"accepts"),"abr"]
        assert_allclose(diff.loc[(ds,"basl_minus_accepts_abr"),"estimate"],delta,atol=1e-9)
    verify_extensions(out)
    verify_identification_and_audit(out)
    verify_information_and_learning(out)
    verify_cost_of_a_pilot(out)
    print("PASS: EVSI thresholds, binary joint laws, chronological SBA replay, information for policy comparisons, adaptive exploration, equivalent worlds, minimax regret, sequential audit, rolling decompositions, policy bounds, randomized offers, cohort counts, score ranges, calibration counts, RMSE, financial identities, paper comparisons, paired contrasts and randomized audit.")


def compare_pilot_tables(out, reference):
    for family in ("information_value", "pilot_replay"):
        actual = {p.name for p in out.glob(f"{family}_*.csv")}
        expected = {p.name for p in reference.glob(f"{family}_*.csv")}
        if not expected or actual != expected:
            raise ValueError(f"Different set of tables for {family}")
        for name in sorted(expected):
            pd.testing.assert_frame_equal(pd.read_csv(out / name), pd.read_csv(reference / name),
                                          check_exact=False, rtol=1e-8, atol=1e-10, obj=name)
    print("PASS: fresh pilot-model and SBA tables match submitted research tables.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    parser.add_argument("--pilot-reference", type=Path, help="compare regenerated theory and SBA tables with a release")
    args = parser.parse_args()
    verify(args.out)
    if args.pilot_reference is not None:
        compare_pilot_tables(args.out, args.pilot_reference)

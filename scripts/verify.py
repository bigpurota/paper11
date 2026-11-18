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


def verify_transfer(out):
    transfer = pd.read_csv(out / "pilot_transfer_episodes.csv")
    ledger = pd.read_csv(out / "lender_pilot_episodes.csv")
    late = pd.read_csv(out / "lender_pilot_followup.csv")
    stats = pd.read_csv(out / "pilot_targeting_summary.csv")
    forecasts = pd.read_csv(out / "pilot_targeting_forecasts.csv")
    keys = ["archive", "terms", "outcome", "forecast"]
    assert not stats.duplicated(keys+["metric"]).any()
    assert not forecasts.duplicated(keys+["group","origin"]).any()
    for label, raw in forecasts.groupby(keys):
        subset = stats
        for name, value in zip(keys, label):
            subset = subset[subset[name] == value]
        values = subset.set_index("metric")
        sample = raw[raw.eligible]
        assert values.selected.eq(sample.selected.sum()).all() and values.eligible.eq(len(sample)).all()
        assert values.strict_selected.eq((sample.selected & sample.strict).sum()).all()
        assert_allclose(values.loc["rule_gain","estimate"], (sample.selected*sample.net).mean(), atol=1e-9)
        assert_allclose(values.loc["pilot_all_gain","estimate"], sample.net.mean(), atol=1e-9)
        positive = sample.net > 1e-10
        if positive.nunique() == 2:
            from sklearn.metrics import roc_auc_score
            assert_allclose(values.loc["auc_positive","estimate"], roc_auc_score(positive,sample.score), atol=1e-9)
    for _, rows in transfer.groupby("terms"):
        assert len(rows) == 120 and not rows.duplicated(["region","pilot_quarter"]).any()
        assert_allclose(rows.seed_net, rows.seed_pilot_cash + rows.seed_gross, atol=1e-9)
        assert_allclose(rows.forced_net, rows.forced_pilot_margin + rows.forced_gross, atol=1e-9)
        assert ((rows.seed_pilot_cash.lt(0) & rows.seed_flip & rows.seed_net.gt(1e-10))
                == rows.seed_loss_recovered).all()
    episode_keys = ["country", "customer", "pilot_month", "future_month"]
    pair = ledger.merge(late, on=episode_keys, validate="one_to_one", suffixes=("_early","_late"))
    assert len(pair)==len(late)==len(ledger) and pair.complete.all()
    assert (pair.future_n==pair.matched_continuations).all() and pair.matched_pilot.all()
    assert (pair.action_changed_early == pair.action_changed_late).all()
    assert_allclose(pair.forced_pilot+pair.forced_gross, pair.forced_net, atol=1e-9)
    for date in ("early","late"):
        a, b, c = [pair[f"euro_{col}_{date}"] for col in ("pilot","gross","net")]
        assert_allclose(a+b,c,atol=1e-6)
        assert ((a.lt(0)&pair.action_changed_early&c.gt(1e-10))==pair[f"euro_covered_{date}"]).all()
    assert (out / "lender_pilot_cash.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def verify_frozen_policy(out):
    from sklearn.metrics import average_precision_score, roc_auc_score

    def read(name):
        return pd.read_csv(out / f"{name}.csv")

    stats = read("pilot_rule_summary").set_index("cohort")
    development = read("pilot_rule_development")
    old = read("lender_pilot_episodes")
    keys = ["country", "customer", "pilot_month"]
    reproduced = development.rename(columns={"origin_month": "pilot_month"}).merge(
        old, on=keys, validate="one_to_one", suffixes=("_new", "_old"))
    assert len(reproduced) == len(old) == len(development)
    assert reproduced.baseline_selected.eq(reproduced.selected_old).all()
    profiles = read("pilot_profiles_selected")
    assert len(profiles) == reproduced.selected_old.sum()
    assert_allclose(profiles.principal / profiles.recent_median_principal,
                    profiles.principal_to_recent_median, rtol=1e-10)
    stability = read("pilot_profiles_field_agreement")
    assert (stability.loans == len(development)).all() and (stability.discordant == 0).all()

    sensitivity = read("pilot_signal_sensitivity")
    delta = sensitivity.pd_without_pilot < sensitivity.decision_threshold
    updated = sensitivity.pd_with_pilot < sensitivity.decision_threshold
    assert (sensitivity.action_changed == (delta != updated)).all()
    assert not sensitivity.duplicated(keys + ["prior_strength", "peer_feed"]).any()
    assert sensitivity.groupby(keys).size().eq(6).all()
    assert sensitivity.groupby(keys).ngroups == len(profiles)

    panels = {"primary_36m": development.loc[development.primary], "expanded_12m": development}
    for source in ("holdout", "prosper"):
        episodes = read(f"pilot_{source}_episodes")
        metadata = read(f"pilot_{source}_cohort").set_index("sample")
        for sample, counts in metadata.iterrows():
            panel = episodes.loc[episodes["sample"].eq(sample)]
            assert len(panel) == counts.opportunities
            assert panel.future_count.sum() == counts.positions_in_continuations
            assert panel.future_count.between(0, 25).all() and panel.prior_n.ge(50).all()
            assert pd.PeriodIndex(panel.origin_month, freq="M").shift(13).equals(
                pd.PeriodIndex(panel.disclosure_month, freq="M"))
            direction = panel.informed_lend.astype(float) - panel.baseline_lend.astype(float)
            cash_shift = (direction * panel.future_cash).mask((direction == 0) | (panel.future_count == 0), 0.)
            assert_allclose(panel.pilot_cash + cash_shift, panel.net_cash, atol=1e-7, equal_nan=True)
            assert panel.loc[panel.future_count.eq(0), "action_changed"].eq(False).all()
            panels[sample] = panel
    support = read("pilot_holdout_support")
    audit = read("pilot_holdout_cohort").set_index("sample")
    assert support.estimable.eq(support.prior_n.ge(50)).all()
    assert support.groupby("sample").originated.sum().eq(audit.window_issued).all()
    assert support.groupby("sample").estimable.sum().eq(audit.opportunities).all()
    assert set(stats.index) == set(panels)

    for cohort, panel in panels.items():
        row = stats.loc[cohort]
        cases = panel.loc[panel.eligible]
        assert (row.scheduled, row.eligible, row.selected, row.baseline_selected) == (
            len(panel), len(cases), cases.selected.sum(), cases.baseline_selected.sum())
        if cases.empty:
            assert pd.isna(row.new_cash) and pd.isna(row.auc_cash)
            continue
        chosen = cases.net_cash.where(cases.selected, 0.)
        diff = cases.selected.astype(int) - cases.baseline_selected.astype(int)
        paired = (cases.net_cash * diff).where(diff != 0, 0.)
        assert_allclose([chosen.mean(), paired.mean()], [row.new_cash, row.new_minus_baseline_cash], atol=1e-8)
        labels = (cases.action_changed.astype("boolean") &
                  cases.pilot_cash.astype("Float64").lt(-1e-12) & cases.net_cash.astype("Float64").gt(1e-12))
        assert labels.count() == row.cash_event_known and labels.sum() == row.cash_recoveries
        assert labels[cases.selected].sum() == row.new_cash_tp
        known = labels.dropna().astype(int)
        if known.nunique() == 2:
            scores = cases.loc[known.index, "strict_probability"]
            assert_allclose([roc_auc_score(known, scores), average_precision_score(known, scores)],
                            [row.auc_cash, row.ap_cash], atol=1e-9)
        else:
            assert pd.isna(row.auc_cash) and pd.isna(row.ap_cash)
    assert (out/"pilot_forecast_validation.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def verify_signal_forecasts(rows, data, training):
    keys = ["country", "origin_month"]
    assert not rows.duplicated([*keys, "feed"]).any()
    assert set(rows.feed) == {"peers", "no_peers"}
    baseline = data.set_index(keys).sort_index()
    for feed, predictions in rows.groupby("feed"):
        forecast = predictions.set_index(keys).sort_index()
        pd.testing.assert_frame_equal(forecast[baseline.columns], baseline, check_dtype=False)
        assert forecast.model_scorable.all()
        assert forecast.train_n.eq(len(training)).all()
        assert forecast.train_months.eq(training.origin_month.nunique()).all()
        counts = forecast.index.get_level_values("country").map(training.country.value_counts()).fillna(0)
        assert np.array_equal(forecast.analog_n, np.where(counts >= 12, counts, len(training)))
        assert np.array_equal(forecast.analog_pooled, counts < 12)
        for field in ("pi_disclosure", "m_repay", "m_default", "m_blind", "m_seen", "pred_issue_pilot_pd",
                      "pred_switch_probability"):
            assert forecast[field].between(0, 1).all()
        pi = forecast.pi_disclosure
        assert_allclose(forecast.m_blind, forecast.m_repay + pi * (forecast.m_default - forecast.m_repay))
        assert_allclose(forecast.m_seen, np.where(forecast.pilot_default == 1, forecast.m_default, forecast.m_repay))
        ordinary = forecast.m_peers if feed == "peers" else forecast.m_public
        assert_allclose(forecast.m_independent_common, ordinary)
        assert np.array_equal(forecast.blind_lend, .10 - .55 * forecast.m_blind > 1e-12)
        assert np.array_equal(forecast.seen_lend, .10 - .55 * forecast.m_seen > 1e-12)
        assert (forecast.pred_info_money >= 0).all()
        direct = forecast.pilot_principal * (.10 - .55 * forecast.pred_issue_pilot_pd)
        assert_allclose(forecast.pred_direct_money, direct, atol=1e-7)
        assert_allclose(forecast.pred_net_money, direct + forecast.pred_info_money, atol=1e-7)
        tol = 1e-12 * forecast.pilot_principal
        assert np.array_equal(forecast.ml_selected, forecast.structural_eligible & (direct < -tol)
                              & (direct + forecast.pred_info_money > tol))


def verify_signal_metrics(episodes, table, counts):
    for cell in counts.itertuples(index=False):
        rows = episodes.loc[episodes.feed.eq(cell.feed)]
        if cell.subset == "later":
            rows = rows.loc[rows.origin_month.ge("2023-11")]
        if cell.country != "ALL":
            rows = rows.loc[rows.country.eq(cell.country)]
        scored = rows.loc[rows.future_count.gt(0)]
        eligible = rows.loc[rows.structural_eligible]
        metrics = table.loc[(cell.feed, cell.subset, cell.country)]
        assert (len(rows), rows.origin_month.nunique(), len(scored), len(eligible)) == (
            cell.scheduled, cell.months, cell.nonempty, cell.eligible)
        assert (eligible.ml_selected.sum(), eligible.structural_selected.sum()) == (
            cell.new_selected, cell.old_selected)

        # Expand the weighted binary Brier algebra directly in euro amounts.
        bad = scored.future_default_principal
        good = scored.future_principal - bad

        def loss(p):
            return (good * p**2 + bad * (1-p)**2) / scored.future_principal

        b, s = loss(scored.m_blind), loss(scored.m_seen)
        initial, origin, public = loss(scored.q_initial), loss(scored.m_origin), loss(scored.m_public)
        peers, common = loss(scored.m_peers), loss(scored.m_independent_common)
        random_loss = loss(scored.m_repay) * (1-scored.pi_disclosure) + loss(scored.m_default) * scored.pi_disclosure
        p_seen = scored.m_seen.clip(1e-12, 1-1e-12)
        p_blind = scored.m_blind.clip(1e-12, 1-1e-12)
        bits = (good * np.log2((1-p_seen)/(1-p_blind)) + bad * np.log2(p_seen/p_blind)) / scored.future_principal
        computed = {"brier_initial": initial, "brier_origin": origin, "brier_public": public, "brier_peers": peers,
                    "brier_common_fit": common, "brier_blind": b, "brier_seen": s,
                    "brier_contract_and_model": initial-origin, "brier_public_refresh": origin-public,
                    "brier_peer_feed": public-peers, "brier_private": b-s, "brier_private_refit": common-s,
                    "brier_real_vs_random": random_loss-s, "brier_randomized": random_loss,
                    "private_log_gain_bits": bits}
        assert cell.scored == (b - s).count()
        direction = eligible.seen_lend.astype(int) - eligible.blind_lend.astype(int)
        direction = direction.where(eligible.future_count.gt(0), 0)
        new = eligible.ml_selected.astype(int)
        old = eligible.structural_selected.astype(int)
        for basis in ["cash", "scenario"]:
            pilot = eligible["pilot_" + basis]
            change = eligible["future_" + basis].mul(direction).where(direction.ne(0), 0.)
            net = pilot + change
            strict = direction.ne(0) & pilot.lt(-1e-12) & net.gt(1e-12)
            computed.update({
                "new_direct_" + basis: pilot * new, "new_followup_" + basis: change * new,
                "new_" + basis: net * new, "old_" + basis: net * old,
                "new_minus_old_" + basis: net * (new-old), "forced_" + basis: net,
                "strict_forced_" + basis: strict, "strict_new_" + basis: strict * new})
            if basis == "cash":
                assert (strict.sum(), (strict * new).sum(), (net * new).count()) == (
                    cell.strict_available, cell.strict_caught, cell.cash_policy_known)
        switched = direction.ne(0)
        assert (switched.sum(), (switched * new).sum()) == (cell.forced_switches, cell.new_switches)
        computed["switch_forced"] = switched
        computed["switch_new"] = switched * new
        assert set(metrics.index) == set(computed)
        for name, values in computed.items():
            metric = metrics.loc[name]
            assert (len(values), values.count()) == (metric.population, metric.observed)
            assert_allclose(values.mean(), metric["mean"], atol=1e-9, equal_nan=True)
        if cell.subset == "full" and cell.country == "ALL":
            # Recreate both primary end points with countries paired within calendar quarters.
            grid = pd.period_range("2022Q4", "2024Q2", freq="Q")
            rng = np.random.default_rng(26011)
            starts = rng.integers(len(grid), size=(2500, 2))
            blocks = (starts[:, :, None] + np.arange(4)).reshape(2500, 8)[:, :len(grid)] % len(grid)
            for name in ("brier_private", "new_cash", "new_minus_old_cash"):
                values = computed[name]
                quarters = pd.PeriodIndex(rows.loc[values.index, "origin_month"], freq="M").asfreq("Q")
                sums = values.groupby(quarters).sum().reindex(grid, fill_value=0).to_numpy()
                sizes = values.groupby(quarters).count().reindex(grid, fill_value=0).to_numpy()
                denominator = sizes[blocks].sum(axis=1)
                draws = sums[blocks].sum(axis=1)[denominator > 0] / denominator[denominator > 0]
                target = metrics.loc[name]
                assert len(draws) == target.estimable_draws
                assert_allclose(np.quantile(draws, [.025, .975]), [target.low, target.high], atol=1e-9)
        else:
            assert metrics.low.isna().all() and metrics.high.isna().all()


def verify_signal_study(out):
    def read(name):
        return pd.read_csv(out / f"{name}.csv")

    panel = read("pilot_signal_panel")
    coverage = read("pilot_signal_panel_coverage")
    keys = ["sample", "country", "origin_month"]
    assert not coverage.duplicated(keys).any() and not panel.duplicated(keys).any()
    supported = coverage.loc[coverage.supported].set_index(keys).sort_index()
    exported = panel.set_index(keys).sort_index()
    pd.testing.assert_index_equal(supported.index, exported.index)
    assert np.array_equal(supported.issued - 1, exported.peer_total)
    assert np.array_equal(supported.origin_known_flags - exported.pilot_default.notna(), exported.peer_n)
    assert panel.peer_defaults.between(0, panel.peer_n).all() and panel.peer_n.le(panel.peer_total).all()
    origin = pd.PeriodIndex(panel.origin_month, freq="M")
    assert (origin + 13).equals(pd.PeriodIndex(panel.disclosure_month, freq="M"))
    assert (origin + 26).equals(pd.PeriodIndex(panel.target_ready_month, freq="M"))
    assert panel.prior_n.ge(50).all() and panel.future_count.between(0, 25).all()
    assert panel.future_event_n.le(panel.future_count).all()
    assert np.array_equal(panel.structural_eligible, .10 - .55 * panel.q_initial < -1e-12)
    assert_allclose(panel.pilot_scenario, panel.pilot_principal * (.10-.55*panel.pilot_default), atol=1e-8)
    assert_allclose(panel.future_scenario, .10*panel.future_principal-.55*panel.future_default_principal, atol=1e-7)
    train = panel.loc[panel["sample"].eq("train")]
    test = panel.loc[panel["sample"].eq("test")]
    discovery = panel.loc[panel["sample"].eq("discovery")]
    assert train.target_ready_month.le("2022-10").all()
    assert train[["pilot_cash", "future_cash", "pilot_balance", "future_balance"]].isna().all().all()
    assert sorted(test.origin_month.unique()) == list(pd.period_range("2022-10", "2024-05", freq="M").astype(str))
    assert test.future_in_previous_pilot_count.eq(0).all() and test.future_in_previous_continuation_count.eq(0).all()
    assert not test.loc[test.origin_month.ge("2023-11"), "pilot_in_previous_continuation"].any()
    assert len(discovery) == 3 and discovery.country.eq("Finland").all()
    assert sorted(discovery.origin_month) == ["2021-03", "2021-11", "2022-02"]
    fit = train.loc[train.pilot_default.notna() & train.future_count.gt(0)
                    & train.future_count.eq(train.future_event_n) & train.future_default_principal.notna()]
    episodes = read("pilot_signal_ml_episodes")
    verify_signal_forecasts(episodes, test, fit)
    verify_signal_forecasts(read("pilot_signal_ml_finnish"), discovery, fit.loc[fit.target_ready_month.le("2021-03")])
    metrics = read("pilot_signal_ml_metrics").set_index(["feed", "subset", "country", "metric"]).sort_index()
    counts = read("pilot_signal_ml_coverage")
    assert metrics.index.is_unique and not counts.duplicated(["feed", "subset", "country"]).any()
    cells = {(feed, "full", country) for feed in episodes.feed.unique()
             for country in ["ALL", *test.country.unique()]}
    cells.update((feed, "later", "ALL") for feed in episodes.feed.unique())
    assert cells == set(map(tuple, counts[["feed", "subset", "country"]].to_numpy()))
    assert cells == set(metrics.index.droplevel("metric"))
    verify_signal_metrics(episodes, metrics, counts)

    cases = read("finnish_pilot_cases").set_index("origin_month").sort_index()
    original = read("pilot_holdout_episodes").query("sample == 'seasoned' and eligible")
    original["money_rank"] = original.score.rank(ascending=False, method="min")
    original["recovery_rank"] = original.strict_probability.rank(ascending=False, method="min")
    reference = original.loc[original.country.eq("Finland") & original.grade.eq("(unrated)")].set_index("origin_month")
    reference = reference.loc[discovery.origin_month.sort_values()]
    pd.testing.assert_index_equal(cases.index, reference.index)
    assert_allclose(cases.funding_rank, reference.money_rank)
    assert_allclose(cases.strict_recovery_rank, reference.recovery_rank)
    assert_allclose(cases.expected_direct + cases.expected_info_after_default + cases.expected_info_after_repayment,
                    reference.score, atol=1e-8)
    assert_allclose(cases.expected_total, reference.score, atol=1e-8)
    assert_allclose(cases.strict_recovery_probability, reference.strict_probability, atol=1e-10)
    assert np.array_equal(cases.selected, reference.selected)
    assert_allclose(cases.incremental_total_cash, reference.net_cash, atol=1e-8)
    assert_allclose(cases.incremental_total_scenario, reference.net_scenario, atol=1e-8)
    peer_mass = 20 * cases.later_public_risk + cases.peer_defaults
    peer_n = 20 + cases.peer_flags_known
    assert_allclose(cases.later_peer_pd_without_pilot, peer_mass / peer_n)
    assert_allclose(cases.later_peer_pd_with_pilot, (peer_mass + cases.observed_default) / (peer_n + 1))
    direction = ((cases.later_peer_pd_with_pilot < 2/11).astype(int)
                 - (cases.later_peer_pd_without_pilot < 2/11).astype(int))
    assert_allclose(cases.incremental_future_cash_with_shared_peers, direction * cases.observed_future_cash)
    print("PASS: dated pilot cohorts, hidden versus observed forecasts, block interval, paired cash and Finnish decisions.")


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
    verify_transfer(out)
    verify_frozen_policy(out)
    verify_signal_study(out)
    print("PASS: locked cash contrasts, profile history, cross-lender signals, transfer predictions, matched Bondora receipts, SBA 7(a) outcomes, EVSI thresholds, binary joint laws, chronological SBA replay, information for policy comparisons, adaptive exploration, equivalent worlds, minimax regret, sequential audit, rolling decompositions, policy bounds, randomized offers, cohort counts, score ranges, calibration counts, RMSE, financial identities, paper comparisons, paired contrasts and randomized audit.")


def compare_pilot_tables(out, reference):
    for family in ("information_value", "pilot_replay", "pilot_transfer", "lender_pilot", "pilot_targeting",
                   "pilot_profiles", "pilot_signal", "pilot_rule", "pilot_holdout", "pilot_prosper", "finnish_pilot"):
        actual = {p.name for p in out.glob(f"{family}_*.csv")}
        expected = {p.name for p in reference.glob(f"{family}_*.csv")}
        if not expected or actual != expected:
            raise ValueError(f"Different set of tables for {family}")
        for name in sorted(expected):
            pd.testing.assert_frame_equal(pd.read_csv(out / name), pd.read_csv(reference / name),
                                          check_exact=False, rtol=1e-8, atol=1e-10, obj=name)
    print("PASS: regenerated pilot tables match the submitted theory, historical profiles, sensitivity and holdout results.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    parser.add_argument("--pilot-reference", type=Path, help="compare regenerated theory and SBA tables with a release")
    args = parser.parse_args()
    verify(args.out)
    if args.pilot_reference is not None:
        compare_pilot_tables(args.out, args.pilot_reference)

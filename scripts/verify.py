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


def verify_frequency_metrics(out, rows):
    """Independent arithmetic on the disclosed candidate rows and all report strata."""
    cols = ["pilot_rank", "feed", "country", "origin_month"]
    positions = rows.set_index(cols)
    ledger = pd.read_csv(out / "frequency_actions.csv")
    table = pd.read_csv(out / "frequency_evaluation.csv")
    actions = pd.read_csv(out / "frequency_action_summary.csv")
    policies = pd.read_csv(out / "frequency_policy.csv")
    metrics_keys = ["pilot_rank", "feed", "scope", "group"]
    assert not ledger.duplicated([*cols, "comparison"]).any()
    for frame, field in [(table, "metric"), (actions, "comparison"), (policies, "policy")]:
        assert not frame.duplicated([*metrics_keys, field]).any()
    pairs = {"frequency_to_public": ("q_initial", "m_public"), "public_to_common": ("m_public", "m_blind"),
             "frequency_to_common": ("q_initial", "m_blind"), "common_to_revealed": ("m_blind", "m_seen"),
             "frequency_to_revealed": ("q_initial", "m_seen"), "raw_peers_to_common": ("pi_disclosure", "m_blind"),
             "hgb_common_to_common": ("hgb_common", "m_blind"), "hgb_seen_to_revealed": ("hgb_seen", "m_seen")}
    assert set(ledger.comparison) == set(pairs)
    assert len(ledger) == len(rows) * len(pairs)
    for name, (left, right) in pairs.items():
        block = ledger.loc[ledger.comparison.eq(name)].set_index(cols).sort_index()
        obs = positions.sort_index()
        pd.testing.assert_index_equal(block.index, obs.index)
        # All actual test pilot flags are observed; no imputation enters this ledger check.
        assert obs.pilot_default.notna().all()
        d = (.10 - .55 * obs[right] > 1e-12).astype(int) - (.10 - .55 * obs[left] > 1e-12).astype(int)
        d = d.where(obs.future_count.gt(0), 0)
        assert_allclose(block.direction, d)
        cash = (d * obs.future_cash).where(d.ne(0), 0.)
        assert_allclose(block.cash, cash, atol=1e-7)
        good_case = .10 * obs.future_principal - .55 * obs.future_known_default_principal
        bad_case = good_case - .55 * obs.future_unknown_principal
        assert_allclose(block.scenario_lower, np.minimum(d * good_case, d * bad_case), atol=1e-7)
        assert_allclose(block.scenario_upper, np.maximum(d * good_case, d * bad_case), atol=1e-7)

    action_index = actions.set_index([*metrics_keys, "comparison"]).sort_index()
    policy_index = policies.set_index([*metrics_keys, "policy"]).sort_index()
    assert set(action_index.index.droplevel("comparison")) == set(policy_index.index.droplevel("policy"))
    for key, reports in table.groupby(metrics_keys):
        rank, feed, scope, label = key
        subset = rows.loc[rows.pilot_rank.eq(rank) & rows.feed.eq(feed)]
        if scope in {"country", "origin_month"}:
            subset = subset.loc[subset[scope].eq(label)]
        elif scope == "omit_month":
            subset = subset.loc[subset.origin_month.ne(label)]
        else:
            assert scope == "all" and label == "all"
        book = subset.loc[subset.future_count.gt(0)].set_index(cols)
        scores = reports.set_index("metric")
        valid = book.future_unknown_principal.eq(0) & book.pilot_default.notna()
        for name, column in [("frequency", "q_initial"), ("public", "m_public"), ("common", "m_blind"),
                             ("revealed", "m_seen"), ("hgb_common", "hgb_common"),
                             ("hgb_2022_seen", "hgb_2022_seen")]:
            d = book.future_known_default_principal.loc[valid]
            v = book.future_principal.loc[valid]
            p = book.loc[valid, column]
            loss = ((v - d) * p**2 + d * (1-p)**2) / v
            stat = scores.loc["brier_" + name]
            assert len(book) == stat.books and loss.count() == stat.observed
            assert_allclose(stat["mean"], loss.mean(), atol=1e-10)
        # Relative binary Brier loss is affine in the unknown defaulted principal.
        # Each portfolio can independently attain either endpoint.
        lo = book.future_known_default_principal / book.future_principal
        hi = lo + book.future_unknown_principal / book.future_principal
        for name in ("frequency_to_common", "common_to_revealed"):
            left, right = pairs[name]
            p, q = book[left], book[right]
            at_low, at_high = [(p - q) * (p + q - 2*z) for z in (lo, hi)]
            expected = [at_low.loc[valid].mean(), np.minimum(at_low, at_high).mean(),
                        np.maximum(at_low, at_high).mean()]
            stat = scores.loc["gain_" + name]
            assert_allclose(stat[["mean", "full_lower", "full_upper"]].astype(float), expected, atol=1e-10)
        group_actions = ledger.merge(subset[cols], on=cols, validate="many_to_one")
        for name, part in group_actions.groupby("comparison"):
            r = action_index.loc[(*key, name)]
            assert (len(part), part.direction.lt(0).sum(), part.direction.gt(0).sum()) == (
                r.scheduled, r.lend_to_skip, r.skip_to_lend)
            assert_allclose([r.total_cash, r.scenario_lower, r.scenario_upper],
                            [part.cash.sum(skipna=False), part.scenario_lower.sum(skipna=False),
                             part.scenario_upper.sum(skipna=False)], atol=1e-7)
        eligible = subset.loc[subset.structural_eligible].set_index(cols)
        private = group_actions.loc[group_actions.comparison.eq("common_to_revealed")].set_index(cols).loc[eligible.index]
        new, old = eligible.ml_selected.astype(int), eligible.structural_selected.astype(int)
        for name, w in [("force", new*0+1), ("skip", new*0), ("anchor", new), ("legacy", old),
                        ("anchor_minus_legacy", new-old)]:
            rp = policy_index.loc[(*key, name)]
            pilot = (w * eligible.pilot_cash).where(w.ne(0), 0.)
            future = (w * private.cash).where(w.ne(0), 0.)
            assert len(eligible) == rp.eligible and rp.known_cash == (pilot + future).count()
            assert_allclose([rp.direct_cash, rp.future_cash, rp.net_cash],
                            [x.sum(skipna=False) for x in (pilot, future, pilot+future)], atol=1e-7)
            if name != "anchor_minus_legacy":
                recoveries = (w.eq(1) & eligible.pilot_cash.lt(0) & (pilot + future).gt(0) & private.direction.ne(0))
                assert rp.recovered == recoveries.sum()
            base = eligible.pilot_principal * (.10 - .55 * eligible.pilot_default)
            a, b = w * (base + private.scenario_lower), w * (base + private.scenario_upper)
            assert_allclose([rp.scenario_lower, rp.scenario_upper],
                            [np.minimum(a, b).sum(skipna=False), np.maximum(a, b).sum(skipna=False)], atol=1e-7)


def verify_frequency_study(out):
    def read(name):
        return pd.read_csv(out / f"{name}.csv")

    diagnoses = read("frequency_diagnosis")
    assert_allclose(diagnoses.brier, diagnoses.within_book_component + diagnoses.squared_mean_error
                    + diagnoses.centered_error_variance, atol=1e-10)
    assert_allclose(diagnoses.brier_gap_vs_issue, diagnoses.adjustment_squared - diagnoses.adjustment_alignment,
                    atol=1e-10)
    assert_allclose(diagnoses.brier_gap_vs_issue,
                    diagnoses.squared_mean_error_gap + diagnoses.centered_error_variance_gap, atol=1e-10)
    old = read("pilot_signal_ml_metrics").query("feed == 'peers' and subset == 'full' and country == 'ALL'").set_index("metric")
    diag = diagnoses.query("period == 'full' and country == 'ALL'").set_index("forecast")
    for f, metric in [("issue_frequency", "brier_initial"), ("issue_boost", "brier_origin"),
                      ("peer_boost", "brier_peers"), ("pilot_revealed_boost", "brier_seen")]:
        assert_allclose(diag.at[f, "brier"], old.at[metric, "mean"], atol=1e-10)

    panel = read("frequency_panel")
    coverage = read("frequency_panel_coverage")
    keys = ["sample", "country", "origin_month", "pilot_rank"]
    assert not panel.duplicated(keys).any() and not coverage.duplicated(keys).any()
    covered = coverage.loc[coverage.supported].set_index(keys).sort_index()
    data = panel.set_index(keys).sort_index()
    pd.testing.assert_index_equal(covered.index, data.index)
    assert (coverage.rank_available == (coverage.issued >= coverage.pilot_rank)).all()
    assert not (coverage.supported & ~coverage.rank_available).any()
    assert np.array_equal(covered.issued, data.peer_total + 1)
    assert np.array_equal(covered.origin_known_flags, data.peer_n + data.pilot_default.notna().astype(int))
    assert data.peer_defaults.between(0, data.peer_n).all()
    assert data.future_count.between(0,25).all() and data.future_event_n.le(data.future_count).all()
    assert data.future_unknown_principal.between(0, data.future_principal).all()
    assert (data.future_known_default_principal + data.future_unknown_principal <= data.future_principal + 1e-7).all()
    complete = data.future_count.eq(data.future_event_n)
    assert np.array_equal(complete, data.future_unknown_principal.eq(0))
    assert np.array_equal(complete, data.future_default_principal.notna())
    assert_allclose(data.loc[complete, "future_default_principal"], data.loc[complete, "future_known_default_principal"])
    train = panel.loc[panel["sample"].eq("train")]
    test = panel.loc[panel["sample"].eq("test")]
    assert train.target_ready_month.le("2024-06").all() and train.pilot_rank.eq(1).all()
    assert test.origin_month.between("2024-06", "2024-09").all()
    assert train[["future_cash", "pilot_cash", "future_balance", "pilot_balance"]].isna().all().all()
    dates = pd.PeriodIndex(panel.origin_month, freq="M")
    assert (dates + 26).equals(pd.PeriodIndex(panel.target_ready_month, freq="M"))
    assert (dates + 13).equals(pd.PeriodIndex(panel.disclosure_month, freq="M"))
    assert test.future_in_previous_pilot_count.eq(0).all() and test.future_in_previous_continuation_count.eq(0).all()
    alt = test.loc[test.pilot_rank == 26]
    assert not (alt.pilot_in_previous_pilot | alt.pilot_in_previous_continuation).any()
    assert test.groupby(["country", "origin_month"]).future_principal.nunique().eq(1).all()
    for field in ["q_initial", "q_fresh", "prior_n", "refresh_n", "future_known_default_principal",
                  "future_unknown_principal", "future_cash", "future_count", "future_event_n"]:
        assert test.groupby(["country", "origin_month"])[field].nunique(dropna=False).eq(1).all()
    any_default = test.peer_defaults + test.pilot_default.fillna(0)
    assert any_default.groupby([test.country, test.origin_month]).nunique().eq(1).all()
    assert np.array_equal(test.pilot_in_previous_continuation, test.pilot_in_grade_book | test.pilot_in_country_book)

    coeff = read("frequency_model_coefficients").set_index("feed")
    rows = read("frequency_model_episodes")
    fit = train.loc[train.pilot_default.notna() & train.future_count.gt(0)
                    & train.future_count.eq(train.future_event_n)]
    assert set(coeff.index) == set(rows.feed) == {"peers", "no_peers"}
    assert coeff.index.is_unique and (coeff.train_n == len(fit)).all()
    assert coeff.train_months.eq(fit.origin_month.nunique()).all() and coeff.ridge_penalty.eq(1).all()
    baseline = test.set_index(keys).sort_index()
    for feed, forecast in rows.groupby("feed"):
        forecast = forecast.set_index(keys).sort_index()
        pd.testing.assert_frame_equal(forecast[baseline.columns], baseline, check_dtype=False)
        # Reconstruct the three training slopes by hand from their fitted scores.
        target = fit.future_default_principal / fit.future_principal
        def slope(x, residual):
            return (x * residual).sum() / (1 + (x * x).sum())
        innovation = fit.q_fresh - fit.q_initial
        a = np.clip(slope(innovation, target - fit.q_initial), 0, 1)
        public = fit.q_initial + a * innovation
        keep = int(feed == "peers")
        n, d = keep * fit.peer_n, keep * fit.peer_defaults
        peer_update = (d - n * public) / (n + 20)
        b = np.clip(slope(peer_update, target - public), 0, 1)
        pi = (d + 20 * fit.q_fresh) / (n + 20)
        gamma = slope(fit.pilot_default - pi, target - public - b * peer_update)
        assert_allclose([a, b, gamma], coeff.loc[feed, ["refresh_slope", "peer_slope", "pilot_slope"]].astype(float),
                        atol=1e-10)
        p = forecast.q_initial * (1-a) + a * forecast.q_fresh
        n, d = keep * forecast.peer_n, keep * forecast.peer_defaults
        c = (1 - b * n / (n+20)) * p + b * d / (n+20)
        pi = (d + 20 * forecast.q_fresh) / (n+20)
        assert_allclose(forecast.m_public, p, atol=1e-10)
        assert_allclose(forecast.m_blind, c, atol=1e-10)
        assert_allclose(forecast.pi_disclosure, pi, atol=1e-10)
        assert_allclose(c, pi * forecast.m_default + (1-pi) * forecast.m_repay, atol=1e-10)
        assert forecast.m_repay.between(0,1).all() and forecast.m_default.between(0,1).all()
        measured = forecast.pilot_default.notna()
        observed = np.where(forecast.pilot_default.eq(1), forecast.m_default, forecast.m_repay)
        assert_allclose(observed[measured], forecast.loc[measured, "m_seen"], atol=1e-10)
        assert forecast.loc[~measured, "m_seen"].isna().all()
        assert_allclose(forecast.pred_direct_money,
                        forecast.pilot_principal * (.10 - .55 * forecast.pred_issue_pilot_pd), atol=1e-7)
        assert_allclose(forecast.pred_net_money, forecast.pred_direct_money + forecast.pred_info_money, atol=1e-7)
        tol = forecast.pilot_principal * 1e-12
        chosen = forecast.structural_eligible & forecast.pred_direct_money.lt(-tol) & forecast.pred_net_money.gt(tol)
        assert np.array_equal(chosen, forecast.ml_selected)
    verify_frequency_metrics(out, rows)
    print("PASS: frequency baseline diagnosis, future-position audit, locked slope fits and sharp policy comparisons.")


def verify_local_trust(out):
    def read(name):
        return pd.read_csv(out / (name + ".csv"))

    cases = read("dutch_frequency_episodes").set_index("origin_month")
    replay = read("dutch_trust").set_index("origin_month")
    donors = read("dutch_frequency_donors")
    calendar = read("dutch_frequency_vintages").set_index("origin_month")
    assert not cases.index.has_duplicates and cases.index.equals(replay.index)
    for s, row in cases.iterrows():
        history = calendar.loc[row.historical_start:row.historical_end]
        later = calendar.loc[row.disclosure_month]
        assert history.labels.sum() == row.historical_labels and history.defaults.sum() == row.historical_defaults
        assert row.future_labels == later.labels and row.first25_labels == later.first25_labels
        raw = history.defaults.sum() / history.labels.sum()
        book = later.first25_default_principal / later.first25_known_principal
        assert_allclose([row.change_across_vintages, row.forecast_gap],
                        [raw - later.defaults/later.labels, row.local_forecast - book])
        w = replay.loc[s]
        other = donors.loc[donors.origin_month.eq(s)]
        assert int(other.historical_labels.sum()) == row.external_labels
        n = other.historical_labels
        q = (other.historical_defaults + .5)/(n+1)
        keep = n.ge(20)
        tau = max(0., q[keep].var() - (q[keep]*(1-q[keep])/(n[keep]+1)).mean()) if keep.sum() >= 3 else 0.
        assert_allclose(w.tau2, tau, atol=1e-10)
        assert_allclose(w.pooled, (other.historical_defaults.sum()+.5)/(n.sum()+1))
        effective = row.historical_labels * min(1., row.historical_labels / max(1., row.recent_issued))
        local = (row.historical_defaults + .5) / (row.historical_labels + 1)
        weight = tau / (tau + local*(1-local)/(effective+1))
        assert_allclose([w.local, w.effective_n, w.weight, w.outcome],
                        [local, effective, weight, book])
        assert_allclose(w.hybrid, w.local*w.weight + (1-w.weight)*w.pooled)
    lower = replay[["local", "pooled"]].min(axis=1)
    upper = replay[["local", "pooled"]].max(axis=1)
    hindsight_error = (replay.outcome.clip(lower=lower, upper=upper) - replay.outcome).abs()
    assert replay.outcome.lt(lower).sum() == 7 and replay.outcome.gt(upper).sum() == 0
    assert np.isclose(100 * hindsight_error.mean(), 9.14, atol=.005)
    assert_allclose(cases.forecast_gap, cases[["smoothing_effect", "change_across_vintages",
                                              "first25_selection_effect", "principal_weight_effect"]].sum(axis=1))
    mix = read("dutch_frequency_contract_mix")
    assert set(mix.original_term_months.astype(str)) and np.isclose(mix.early_weight.sum(), 1.)
    assert_allclose(mix.loc[mix.early_labels.gt(0), "later_rate_at_early_weights"],
                    (mix.early_weight * mix.later_defaults / mix.later_labels)[mix.early_labels.gt(0)])

    rows = read("local_trust_bank_episodes")
    assert not rows.duplicated(["state", "quarter"]).any()
    for field, lag in [("history_from", -24), ("history_to", -13), ("recent_from", -12), ("recent_to", -1)]:
        expected = pd.PeriodIndex(rows.quarter, freq="Q") + lag
        assert expected.equals(pd.PeriodIndex(rows[field], freq="Q"))
    assert rows.quarter.nunique() == 19 and rows.n.le(rows.issued).all() and rows.defaults.le(rows.n).all()
    coverage = read("local_trust_bank_coverage")
    exclusions = ["missing_or_reversed_origination", "outside_states", "invalid_principal",
                  "premature_chargeoff", "immature", "retained"]
    assert np.array_equal(coverage.bank_rows, coverage[exclusions].sum(axis=1))
    assert np.array_equal(coverage.retained, coverage.known_flags + coverage.unknown_flags)
    scored = rows.loc[rows.other_n.gt(0) & rows.n.gt(0)]
    forecasts = np.where(scored.local_n.gt(0), (scored.local_events+.5)/(scored.local_n+1), scored.pooled)
    assert_allclose(forecasts, scored.local)
    assert_allclose(scored.pooled, (scored.other_events+.5)/(scored.other_n+1))
    effective = scored.local_n*np.minimum(1., scored.local_n/scored.recent_n.clip(lower=1))
    variance = scored.local*(1-scored.local)/(effective+1)
    weight = np.where(scored.local_n.gt(0), scored.tau2/(scored.tau2+variance), 0.)
    assert_allclose(effective, scored.effective_n)
    assert_allclose(weight, scored.weight, atol=1e-10)
    assert_allclose(scored.hybrid, scored.local*weight + scored.pooled*(1-weight))
    assert_allclose(scored.hard, np.where(weight > .5, scored.local, scored.pooled))
    metrics = read("local_trust_bank_metrics")
    choices = read("local_trust_bank_choices")
    policy = read("local_trust_bank_policy")
    for sample, data in [("matched", scored.loc[scored.local_n.gt(0)]), ("operational", scored)]:
        for scope, group in [("all", data), *data.groupby("quarter", sort=True)]:
            table = metrics.loc[metrics["sample"].eq(sample) & metrics.group.eq(scope)]
            for basis, weights in [("equal_books", np.ones(len(group))),
                                   ("loan_weighted", group.n),
                                   ("dollars_within", np.ones(len(group)))]:
                target = group.defaults / group.n if basis != "dollars_within" else group.default_principal/group.known_principal
                values = {}
                for name in ("local", "pooled", "hybrid", "hard", "support_hybrid"):
                    p = group[name]
                    loss = p*p + target*(1-2*p)
                    values[name] = np.average(loss, weights=weights)
                for ref in ("local", "pooled"):
                    for name in ("hybrid", "hard", "support_hybrid"):
                        values[ref+"_minus_"+name] = values[ref]-values[name]
                reported = table.loc[table.basis.eq(basis)].set_index("method")["mean"]
                assert set(reported.index) == set(values)
                assert_allclose(reported, [values[k] for k in reported.index], atol=1e-11)
        # Independently choose the closer predictor from absolute forecast errors.
        z = data.defaults/data.n
        delta_errors = (data.pooled-z)**2 - (data.local-z)**2
        for g in choices.loc[choices["sample"].eq(sample)].itertuples():
            mask = data.weight.gt(.5) if g.choice == "local" else data.weight.le(.5)
            a = delta_errors[mask]
            assert (len(a), a.gt(1e-12).sum(), a.lt(-1e-12).sum()) == (g.books, g.local_closer, g.pooled_closer)
        for r in policy.loc[policy["sample"].eq(sample)].itertuples():
            signed = (data[r.method]<r.cutoff).astype(int) - (data[r.reference]<r.cutoff).astype(int)
            cash = r.bad*data.default_principal + r.good*(data.known_principal-data.default_principal)
            unknown = data.principal-data.known_principal
            assert (signed.gt(0).sum(), signed.lt(0).sum()) == (r.new_lending, r.new_declines)
            assert_allclose([r.known_delta, r.delta_lower, r.delta_upper],
                            [(signed*cash).sum(), (signed*cash+np.minimum(r.bad*signed*unknown,r.good*signed*unknown)).sum(),
                             (signed*cash+np.maximum(r.bad*signed*unknown,r.good*signed*unknown)).sum()], atol=1e-4)
    # Recreate resampled quarter lists directly, preserving all states within each quarter.
    matched = scored.loc[scored.local_n.gt(0)]
    quarter = pd.PeriodIndex(matched.quarter, freq="Q").asi8
    grid = np.arange(quarter.min(), quarter.max()+1)
    rng = np.random.default_rng(26011)
    start = rng.integers(len(grid), size=(2500, 5))
    indices = (start[:,:,None] + np.arange(4)) % len(grid)
    draws = indices.reshape(2500,-1)[:,:len(grid)]
    target = matched.defaults/matched.n
    for ref in ("local", "pooled"):
        diff = (matched[ref]-target)**2 - (matched.hybrid-target)**2
        sums = diff.groupby(quarter).sum().reindex(grid, fill_value=0).to_numpy()
        counts = diff.groupby(quarter).count().reindex(grid, fill_value=0).to_numpy()
        value = sums[draws].sum(axis=1)/counts[draws].sum(axis=1)
        record = metrics.query("sample == 'matched' and group == 'all' and basis == 'equal_books'")
        pair = record.set_index("method").loc[ref+"_minus_hybrid"]
        assert_allclose(np.quantile(value, [.025,.975]), [pair.ci_low,pair.ci_high], atol=1e-11)
    print("PASS: Dutch vintage decomposition, donor trust, external bank scores, choices, dated block intervals and policy scenarios.")


def verify_early_payments(out):
    nl = pd.read_csv(out / "early_dutch_episodes.csv")
    cz = pd.read_csv(out / "early_czech_episodes.csv")
    legacy = pd.read_csv(out / "dutch_frequency_episodes.csv").set_index("origin_month").loc[nl.origin_month]
    assert_allclose(nl.local, legacy.local_forecast)
    assert_allclose(nl.broader, legacy.other_countries_forecast)
    assert_allclose(nl.target, nl.future_default_principal / nl.future_principal)
    assert_allclose(nl.revised_young_year_rate, nl.revised_young_year_defaults / nl.revised_young_labels)
    assert (nl.young_mature_at_snapshot_e <= nl.young_mature_at_snapshot_y).all()
    common = cz.rename(columns={"old_e6":"old_e", "bank_e6":"bank_e", "young6_e":"young_e", "young6_n":"young_n",
                                "six":"six_month", "other":"broader"})
    for data, key, six_end in [(nl, "origin_month", "six_month_to"), (common, "month", "early6_end")]:
        assert pd.PeriodIndex(data[key], freq="M").shift(-7).equals(pd.PeriodIndex(data[six_end], freq="M"))
        local_ok = data.old_y.ge(5) & data.old_e.ge(1)
        bank_ok = data.bank_y.ge(5) & data.bank_e.ge(1)
        h = np.where(local_ok, (data.old_e+.5)/(data.old_y+1), (data.bank_e+.5)/(data.bank_y+1))
        h = np.where(local_ok | bank_ok, h, np.nan)
        expected = (data.young_e + 10 * h * data.local) / ((data.young_n + 10) * h)
        expected = np.where(np.isfinite(h) & data.young_n.gt(0), np.clip(expected, 0, 1), data.local)
        assert_allclose(data.six_month, expected, atol=1e-11)
        assert_allclose(data.capture, h, atol=1e-11, equal_nan=True)
        # Independent algebraic condition given the two mature rates.
        smaller = np.minimum(data.local, data.broader)
        boundary = h*((10+data.young_n)*(smaller-1e-12) - 10*data.local)
        assert np.array_equal(data.six_month.lt(smaller-1e-12), data.young_e.lt(boundary) & data.young_n.gt(0))

    snapshot = pd.read_csv(out / "early_dutch_snapshot.csv").iloc[0]
    assert pd.Timestamp(snapshot.snapshot_date) > pd.Period(nl.origin_month.max(), freq="M").start_time
    assert snapshot.positive_receipts + snapshot.zero_receipts == snapshot.issued
    assert snapshot.zero_cash_and_30dpd + snapshot.positive_cash_and_30dpd == snapshot.at_least_30dpd
    coverage = pd.read_csv(out / "early_czech_coverage.csv").iloc[0]
    assert (coverage.marked_at_risk + coverage.unmarked_at_risk + coverage.already_short_by_month3
            == coverage.test_loans == cz.loans.sum())
    assert (coverage.incident_marked + coverage.incident_unmarked + coverage.already_short_by_month3
            == coverage.test_events == cz.events.sum())
    truth = cz.events / cz.loans
    metrics = pd.read_csv(out / "early_czech_metrics.csv").set_index("method")
    for method in metrics.index:
        error = truth*(1-cz[method])**2 + (1-truth)*cz[method]**2
        assert_allclose(metrics.at[method, "brier"], error.mean(), atol=1e-11)
    flags = pd.read_csv(out / "early_czech_direction.csv").set_index("method")
    below = truth.lt(cz[["local", "other"]].min(axis=1) - 1e-12)
    for method, record in flags.iterrows():
        predicted = cz[method].lt(cz[["local", "other"]].min(axis=1) - 1e-12)
        assert tuple(record[["true_flags","false_flags","missed","true_unflagged"]]) == (
            (predicted & below).sum(), (predicted & ~below).sum(),
            (~predicted & below).sum(), (~predicted & ~below).sum())
    for dataset, ledger, principal, event_principal, reference, value in [
        ("czech", cz, cz.principal, cz.event_principal, "reference", "delta_margin_czk"),
        ("dutch", nl, nl.future_principal, nl.future_default_principal, "baseline", "scenario_difference"),
    ]:
        for row in pd.read_csv(out / f"early_{dataset}_policy.csv").to_dict("records"):
            cutoff = row["good"] / (row["good"]-row["bad"])
            switch = ledger[row["method"]].lt(cutoff).astype(int) - ledger[row[reference]].lt(cutoff).astype(int)
            cash = row["bad"]*event_principal + row["good"]*(principal-event_principal)
            assert_allclose(row[value], (switch*cash).sum(), atol=1e-6)
    print("PASS: dated early-payment conversions, new-cohort targets, warning flags, landmark counts and lending decisions.")


def verify_selection_grid(out):
    """Reconcile both published policies and each grid cell with its fitted folds."""
    grid = pd.read_csv(out / "selection_strength.csv").set_index(
        ["dataset", "strength", "quantity"], verify_integrity=True).sort_index()
    folds = pd.read_csv(out / "selection_strength_folds.csv").set_index(
        ["dataset", "strength", "fold"], verify_integrity=True).sort_index()
    hard = pd.read_csv(out / "hard_selection.csv").set_index(
        ["dataset", "design", "quantity"], verify_integrity=True).sort_index()
    training = {design: pd.read_csv(out / filename).pivot(
        index=["dataset", "fold"], columns="method", values="abr")
        for design, filename in [("main", "training.csv"), ("hard", "hard_selection_training.csv")]}
    expected_cells = {(d, s) for d in ("taiwan", "prosper") for s in ("main", "0.5", "1", "2", "4", "hard")}
    assert set(grid.index.droplevel("quantity")) == set(folds.index.droplevel("fold")) == expected_cells
    for dataset, strength in sorted(expected_cells):
        fitted = folds.loc[(dataset, strength)].sort_index()
        estimates = grid.loc[(dataset, strength)]
        assert list(fitted.index) == ([1, 2, 3, 4] if dataset == "taiwan" else [1])
        assert fitted.audited.gt(0).all()
        means = {col: fitted[col].mean() for col in fitted if col != "audited" and not col.endswith("_error")}
        for error in (col for col in fitted if col.endswith("_error")):
            means[error.removesuffix("_error") + "_rmse"] = np.sqrt(fitted[error].pow(2).mean())
        gaps = {"B_minus_A": fitted.B_test_abr - fitted.A_test_abr,
                "Bplus_minus_Aplus": fitted["B+_test_abr"] - fitted["A+_test_abr"],
                "Aplus_minus_A": fitted["A+_test_abr"] - fitted.A_test_abr}
        gaps["audit_change_in_basl_gap"] = gaps["Bplus_minus_Aplus"] - gaps["B_minus_A"]
        for name, values in gaps.items():
            means[name] = values.mean()
            assert_allclose(estimates.loc[name, ["fold_min", "fold_max"]], [values.min(), values.max()], atol=1e-9)
        means["bayes_logistic_minus_accepts_rmse"] = means["bayes_logistic_rmse"] - means["accepts_rmse"]
        means["bayes_audited_minus_logistic_rmse"] = means["bayes_audited_rmse"] - means["bayes_logistic_rmse"]
        assert set(estimates.index) == set(means)
        assert_allclose(estimates.loc[list(means), "estimate"], list(means.values()), atol=1e-9)
        contrasts = [*gaps, "bayes_logistic_minus_accepts_rmse", "bayes_audited_minus_logistic_rmse"]
        ci = estimates.loc[contrasts]
        assert ci.ci_low.le(ci.ci_high).all()
        if strength in training:
            ref = training[strength].loc[dataset].sort_index()
            assert_allclose(fitted[["A_test_abr", "B_test_abr"]], ref[["accepts", "basl"]], atol=1e-9)
            design = "soft" if strength == "main" else "hard"
            profile = hard.loc[(dataset, design), "estimate"]
            for name in ("accepted_share", "bad_rate_accepted", "bad_rate_rejected", "reject_bad_rate_validation"):
                assert_allclose(profile[name], means[name], atol=1e-9)
            assert_allclose(profile[["reject_prior_mean", "reject_prior_auc"]],
                            [means["logistic_reject_mean"], means["logistic_reject_auc"]], atol=1e-9)
            if strength == "hard":
                assert_allclose(profile[["accepts_eval_rmse_abr", "bayes_eval_rmse_abr"]],
                                [means["accepts_rmse"], means["bayes_logistic_rmse"]], atol=1e-9)
    print("PASS: all 12 selection designs reconcile with their folds and both reference policies.")


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
    verify_frequency_study(out)
    verify_local_trust(out)
    verify_early_payments(out)
    verify_selection_grid(out)
    print("PASS: locked cash contrasts, profile history, cross-lender signals, transfer predictions, matched Bondora receipts, SBA 7(a) outcomes, EVSI thresholds, binary joint laws, chronological SBA replay, information for policy comparisons, adaptive exploration, equivalent worlds, minimax regret, sequential audit, rolling decompositions, policy bounds, randomized offers, cohort counts, score ranges, calibration counts, RMSE, financial identities, paper comparisons, paired contrasts and randomized audit.")


def compare_pilot_tables(out, reference, selection_reference=None):
    for family in ("information_value", "pilot_replay", "pilot_transfer", "lender_pilot", "pilot_targeting",
                   "pilot_profiles", "pilot_signal", "pilot_rule", "pilot_holdout", "pilot_prosper", "finnish_pilot", "frequency", "dutch_frequency", "local_trust_bank", "early_dutch", "early_czech"):
        actual = {p.name for p in out.glob(f"{family}_*.csv")}
        expected = {p.name for p in reference.glob(f"{family}_*.csv")}
        if not expected or actual != expected:
            raise ValueError(f"Different set of tables for {family}")
        for name in sorted(expected):
            pd.testing.assert_frame_equal(pd.read_csv(out / name), pd.read_csv(reference / name),
                                          check_exact=False, rtol=1e-8, atol=1e-10, obj=name)
    pd.testing.assert_frame_equal(pd.read_csv(out / "dutch_trust.csv"), pd.read_csv(reference / "dutch_trust.csv"),
                                  check_exact=False, rtol=1e-8, atol=1e-10)
    selection_reference = reference if selection_reference is None else selection_reference
    for name in ("hard_selection.csv", "hard_selection_training.csv", "selection_strength.csv", "selection_strength_folds.csv", "policy.csv"):
        pd.testing.assert_frame_equal(pd.read_csv(out / name), pd.read_csv(selection_reference / name),
                                      check_exact=False, rtol=1e-7, atol=1e-9, obj=name)
    print(f"PASS: regenerated pilot tables match the release; selection refits match {selection_reference}.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    parser.add_argument("--pilot-reference", type=Path, help="compare regenerated pilot and selection tables with a release")
    parser.add_argument("--selection-reference", type=Path, help="platform-specific reference for selection and lending-policy tables; defaults to --pilot-reference")
    args = parser.parse_args()
    if args.selection_reference is not None and args.pilot_reference is None:
        parser.error("--selection-reference requires --pilot-reference")
    verify(args.out)
    if args.pilot_reference is not None:
        compare_pilot_tables(args.out, args.pilot_reference, args.selection_reference)

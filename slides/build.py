"""Refresh the editable PPTX from checked analysis outputs, then export its PDF."""
import csv
from pathlib import Path
import posixpath
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZipFile
from defense import assemble


HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
SOURCES = {"simulation_fig2.png", "calibration.png", "vintage_forecasts.png", "bounds_frontier.png"}
# Drawn here from the aggregate results at the size of their frames in the talk template.
TALK_FIGURES = {"talk_pilot.png", "talk_dutch.png"}
INK, MUTED, GRID, AXIS = "#0E2D69", "#52514e", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#8d8b85"
TOKEN = re.compile(rb"\{\{([a-z0-9_]+)\}\}")
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_table(name):
    with (RESULTS / (name + ".csv")).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def matching(rows, **keys):
    return [row for row in rows if all(row[k] == str(v) for k, v in keys.items())]


def one(rows, **keys):
    records = matching(rows, **keys)
    if len(records) != 1:
        raise ValueError(f"Expected exactly one source record for {keys}; found {len(records)}")
    return records[0]


def number(x):
    return f"{float(x) * 100:.2f}"


def percent(x):
    return number(x) + "%"


def signed(x):
    return f"{float(x) * 100:+.2f}"


def decision_fields():
    worlds = matching(read_table("identification_worlds"), grid="two", constraint="oracle_decile_totals")
    histories = matching(worlds, dataset="taiwan", fold=1)
    low_defaults = one(histories, witness_for="0.5")
    high_defaults = one(histories, witness_for="0.3")
    for key in ("n", "n_observed", "observed_defaults", "hidden_defaults",
                "hidden_defaults_by_prior_decile", "changed_cases"):
        if low_defaults[key] != high_defaults[key]:
            raise ValueError(f"Taiwan witness worlds disagree on {key}")

    def margin_pp(raw, places=3):
        return f"{float(raw) * 100:+.{places}f}".replace("-", "−")

    folds = {r["fold"] for r in matching(worlds, dataset="taiwan")}
    intervals = [[float(r["change_30_to_50"]) for r in matching(worlds, dataset="taiwan", fold=fold)]
                 for fold in folds]
    summary = read_table("identification_summary")
    prosper = one(summary, dataset="prosper", grid="two", constraint="oracle_decile_totals")
    fields = {
        "world_seen": f"{int(low_defaults['n_observed']):,}",
        "world_hidden": low_defaults["hidden_defaults"],
        "world_counts": ", ".join(low_defaults["hidden_defaults_by_prior_decile"].split()),
        "world_switch": f"{int(low_defaults['changed_cases']):,}",
        "world_low_d": low_defaults["changed_defaults"],
        "world_high_d": high_defaults["changed_defaults"],
        "world_high_gain": margin_pp(low_defaults["change_30_to_50"]),
        "world_low_gain": margin_pp(high_defaults["change_30_to_50"], 4),
        "world_ambig": str(sum(min(values) < 0 < max(values) for values in intervals)),
        "world_folds": str(len(folds)),
        "world_pr_lo": margin_pp(prosper["gain_30_to_50_lower"]),
        "world_pr_hi": margin_pp(prosper["gain_30_to_50_upper"]),
    }
    for prefix, ds in [("tw", "taiwan"), ("pr", "prosper")]:
        best = one(summary, dataset=ds, grid="five", constraint="unrestricted")
        for label, key in [("pure", "worst_deterministic"), ("mix", "worst_lottery")]:
            fields[f"regret_{prefix}_{label}"] = f"{100 * float(best[key]):.3f}"
    audit = matching(read_table("decision_audit_summary"), dataset="prosper", fold=1)
    for prefix, scenario in [("real", "retrospective_truth"), ("prof", "last_profitable"),
                             ("loss", "first_unprofitable")]:
        row = one(audit, scenario=scenario)
        fields[f"audit_{prefix}_k"] = row["hidden_defaults"]
        fields[f"audit_{prefix}_n"] = f"{float(row['mean_labels']):.2f}"
    fields["audit_hidden"] = one(audit, scenario="retrospective_truth")["hidden"]
    info = read_table("policy_information_summary")
    aligned = matching(info, design="expansion_bands")
    model_bins = matching(info, design="prior_deciles")
    fields["pi_pairs"] = str(sum(int(r["n_policy_pairs"]) for r in aligned))
    for name, rows in (("pi_exact", aligned), ("pi_prior", model_bins)):
        fields[name] = str(sum(int(r["pairs_exact_at_actual_binary_totals"]) for r in rows))
    experiment = matching(read_table("exploration_values"), reset=0)
    initial = one(experiment, horizon=1)
    fields.update(ex_prior=percent(initial["prior_good"]).replace(".00", ""),
                  ex_good=percent(initial["default_good"]).replace(".00", ""),
                  ex_bad=percent(initial["default_bad"]).replace(".00", ""),
                  ex_loss=f"{-100 * float(initial['immediate_margin']):.2f}")
    for h in (3, 10):
        row = one(experiment, horizon=h)
        fields[f"ex_h{h}"] = f"{100 * float(row['adaptive_value']):.2f}"
    return fields


def pilot_fields():
    base = matching(read_table("information_value_frontier"), discount=1, delay=1, fee=0)
    stable, fading = one(base, reset=0), one(base, reset="0.1")
    stress = read_table("information_value_stress")
    adaptive = matching(read_table("exploration_values"), reset=0, first_action="fund")
    cohort, = read_table("pilot_replay_cohort")
    primary = matching(read_table("pilot_replay_summary"), sampling="chronological", terms="early_national")
    model, forced = [one(primary, strategy=name, measure="net") for name in ("model", "forced")]
    def money(row, col):
        return f"{100*float(row[col]):+.3f}".replace("-", "−")
    return {
        "iv_loss": f"{-100*float(stable['prior_margin']):.4f}",
        "iv_per": f"{10*float(stable['evsi_at_ten']):.6f}",
        "iv_first": stable["first_followups"], "iv_total": str(int(stable["first_followups"])+1),
        "ex_first": str(min(int(row["horizon"]) for row in adaptive)),
        "iv_cap": f"{100*float(fading['evsi_limit']):.5f}",
        "iv_grid": f"{sum(int(row['scenarios']) for row in stress):,}",
        "iv_loss_cases": f"{sum(int(row['loss_making']) for row in stress):,}",
        "iv_pay_cases": f"{sum(int(row['strictly_worthwhile_loss_making']) for row in stress):,}",
        "sba_n": f"{int(cohort['continuation_pool_loans']):,}",
        "sba_label": "Pilots chosen in eligible region-quarters",
        "sba_result": f"{model['pilot_cells']} of {model['eligible_cells']}",
        "sba_label2": "Decisions sensitive to those pilot labels",
        "sba_result2": f"{model['signal_sensitive_cells']} of {model['pilot_cells']}",
        "sba_text": (f"Forcing a pilot in every eligible episode changed net margin by "
                     f"{money(forced, 'mean_per_eligible_episode')} per episode "
                     f"(95% block interval {money(forced, 'ci_4q_low')} to {money(forced, 'ci_4q_high')}). "
                     "One loan has principal 100."),
        "sba_notes": (f"Net gain under the model was {money(model, 'mean_per_eligible_episode')} "
                      f"[{money(model, 'ci_4q_low')}, {money(model, 'ci_4q_high')}], per eligible episode. "
                      "At origination the plug-in forecast holds background risk fixed. "
                      "Both policies receive updated common information before follow-up. "
                      "The matched no-pilot rule can fund or decline. The separate decline-all benchmark earns zero."),
    }


def transfer_fields():
    summary = matching(read_table("pilot_targeting_summary"), forecast="fixed_risk", outcome="scenario")
    fields = {}
    for label, archive, terms in [("sba", "sba_7a", "early_7a"), ("eu", "bondora", "at_least_36m")]:
        data = matching(summary, archive=archive, terms=terms)
        auc = one(data, metric="auc_positive")
        fields[f"t_{label}_count"] = f"{auc['selected']} / {auc['eligible']}"
        fields[f"t_{label}_auc"] = f"{float(auc['estimate']):.2f}"
        fields[f"t_{label}_gain"] = f"{100*float(one(data, metric='rule_gain')['estimate']):+.2f}".replace("-","−")
    fields["t_sba_flip"] = one(read_table("pilot_transfer_summary"), terms="early_7a", group="selected")["seed_flips"]
    fields["t_eu_flip"] = one(read_table("lender_pilot_summary"), seasoning="36m",
                              strategy="selected", valuation="forced")["changed"]
    key = dict(country="EE", customer="returning", pilot_month="2018-10")
    origin = one(read_table("lender_pilot_episodes"), **key)
    late = one(read_table("lender_pilot_followup"), **key)
    fields["x_before"] = percent(origin["q_fresh"])
    fields["x_after"] = percent(origin["q_with_pilot"])
    fields["x_cut"] = percent(float(origin["repay_margin"]) / (float(origin["repay_margin"]) - float(origin["default_margin"])))
    for label, column in (("loss","euro_pilot"), ("avoid","euro_gross"), ("net","euro_net")):
        fields["x_"+label] = f"{abs(float(late[column])):,.2f}"
    profiles = read_table("pilot_profiles_selected")
    for key, origin in [("jul", "2018-07"), ("oct", "2018-10"), ("nov", "2018-11"), ("feb", "2019-02")]:
        row = one(profiles, country="EE", customer="returning", pilot_month=origin)
        fields[f"p_{key}_amt"] = f"€{float(row['principal']):,.0f} · {float(row['principal_to_recent_median']):.2f}×"
        fields[f"p_{key}_prev"] = row["previous_loans"]
        fields[f"p_{key}_term"] = f"{row['original_term_calendar_months']} mo"
        value = float(row["euro_net"])
        fields[f"p_{key}_gain"] = ("+" if value >= 0 else "−") + f"€{abs(value):,.0f}"
    holdouts = read_table("pilot_rule_summary")
    for cohort, unit in [("primary", "€"), ("seasoned", "€"), ("prosper", "$")]:
        row = one(holdouts, cohort=cohort)
        fields[f"h_{cohort}_n"] = row["eligible"]
        fields[f"h_{cohort}_s"] = row["selected"]
        fields[f"h_{cohort}_hit"] = f"{row['new_cash_tp']} / {row['cash_recoveries']}"
        if row["new_cash"]:
            value = float(row["new_cash"])
            fields[f"h_{cohort}_cash"] = ("+" if value > 0 else "−" if value < 0 else "") + f"{unit}{abs(value):,.2f}"
    return fields


def signal_fields():
    fields = {}
    cases = read_table("finnish_pilot_cases")
    for prefix, origin in [("mar", "2021-03"), ("nov", "2021-11"), ("feb", "2022-02")]:
        row = one(cases, origin_month=origin)
        for name, key in [("direct", "expected_direct"), ("info", "expected_information"),
                          ("net", "expected_total"), ("cash", "incremental_total_cash")]:
            value = float(row[key])
            sign = "+" if value > 0 else "−" if value < 0 else ""
            fields[f"s_{prefix}_{name}"] = f"{sign}€{abs(value):,.2f}"
    primary = matching(read_table("pilot_signal_ml_metrics"), feed="peers", subset="full", country="ALL")
    for name, key in [("public", "brier_public_refresh"), ("peers", "brier_peer_feed"),
                      ("private", "brier_private")]:
        row = one(primary, metric=key)
        avg, low, high = [f"{float(row[k]):+.5f}".replace("-", "−") for k in ("mean", "low", "high")]
        fields[f"s_{name}"] = avg
        fields[f"s_{name}_ci"] = f"[{low}, {high}]"
    return fields


def frequency_fields():
    values = {}
    history = read_table("frequency_diagnosis_support")
    for name, country in [("all", "ALL"), ("fi", "Finland")]:
        row = one(history, country=country)
        for label, field in [("actual", "test_observed_rate"), ("rate", "test_frequency"),
                             ("boost", "test_issue_boost")]:
            values[f"fq_{name}_{label}"] = percent(row[field])
    definition = dict(feed="peers", pilot_rank=1, scope="all", group="all")
    scores = matching(read_table("frequency_evaluation"), **definition)
    for label, key in [("q", "frequency"), ("p", "public"), ("c", "common"),
                       ("y", "revealed"), ("raw", "peer_frequency")]:
        values[f"fq_{label}"] = f"{float(one(scores, metric='brier_' + key)['mean']):.6f}"
    actions = matching(read_table("frequency_action_summary"), **definition)
    for label, key in [("p", "frequency_to_public"), ("c", "public_to_common"),
                       ("y", "common_to_revealed")]:
        row = one(actions, comparison=key)
        values[f"fq_{label}switch"] = str(int(row["skip_to_lend"]) + int(row["lend_to_skip"]))
    return values


def local_trust_fields():
    episodes = read_table("dutch_frequency_episodes")
    forecasts = read_table("dutch_trust")
    values = {f"nl_{name}": percent(statistics.mean(float(r[name]) for r in forecasts))
              for name in ("local", "pooled", "hybrid", "outcome")}
    volume = [float(r["volume_ratio"]) for r in episodes]
    values.update(nl_lo=f"{min(volume):.1f}", nl_hi=f"{max(volume):.1f}")
    for label, column in [("small_d", "first25_defaults"), ("small_n", "first25_labels"),
                          ("total_d", "future_defaults"), ("total_n", "future_labels")]:
        values["nl_" + label] = format(sum(int(r[column]) for r in episodes), ",")
    values["nl_total_pct"] = percent(sum(int(r["future_defaults"]) for r in episodes)
                                     / sum(int(r["future_labels"]) for r in episodes))
    scores = matching(read_table("local_trust_bank_metrics"), sample="matched",
                      group="all", basis="equal_books")
    for method in ("local", "pooled", "hybrid"):
        row = one(scores, method=method)
        values["wf_" + method] = f"{float(row['mean']):.6f}"
    values["wf_books"] = row["books"]
    values["wf_loans"] = format(int(row["loans"]), ",")
    for method in ("local", "pooled"):
        contrast = one(scores, method=method + "_minus_hybrid")
        for label, key in (("gain", "mean"), ("low", "ci_low"), ("high", "ci_high")):
            values[f"wf_{method}_{label}"] = f"{float(contrast[key]):+.6f}".replace("-", "−")
    choices = matching(read_table("local_trust_bank_choices"), sample="matched")
    for method in ("local", "pooled"):
        choice = one(choices, choice=method)
        values["wf_" + method + "_correct"] = choice[method + "_closer"] + "/" + choice["books"]
    action = one(read_table("local_trust_bank_policy"), sample="matched", good="0.1",
                 bad="-0.45", method="hybrid", reference="local")
    values["wf_cut"] = percent(action["cutoff"])
    values["wf_add"] = action["new_lending"]
    return values


def early_payment_fields():
    dutch = read_table("early_dutch_episodes")
    flags = {r["origin_month"] for r in dutch if r["six_month_below_both"] == "True"}
    below = {r["origin_month"] for r in dutch if r["realized_below_both"] == "True"}
    snapshot, = read_table("early_dutch_snapshot")
    coverage, = read_table("early_czech_coverage")
    direction = one(read_table("early_czech_direction"), method="six")
    policy = matching(read_table("early_czech_policy"), good="0.1", bad="-0.45", reference="local")
    change = one(policy, method="six")
    november = one(dutch, origin_month="2023-11")
    young_events = int(november["young_mature_at_snapshot_y"])
    mature_early, mature_year = int(november["old_e"]), int(november["old_y"])
    young_early = int(november["young_mature_at_snapshot_e"])
    # Would an exact year-one rate for the measured young cohorts have warned on the same dates?
    own = {r["origin_month"] for r in dutch
           if float(r["revised_young_year_rate"]) < min(float(r["local"]), float(r["broader"]))}
    values = {
        "nl_own_flags": str(len(own)), "nl_own_hits": str(len(own & below)),
        "nl_books": str(len(dutch)), "nl_flags": str(len(flags)), "nl_hits": str(len(flags & below)),
        "nl_false": str(len(flags - below)), "nl_missed": str(len(below - flags)),
        "nl_six": percent(statistics.mean(float(r["six_month"]) for r in dutch)),
        "nl_three": percent(statistics.mean(float(r["three_month"]) for r in dutch)),
        "nl_young_year": percent(statistics.mean(float(r["revised_young_year_rate"]) for r in dutch)),
        "nl_young_under": str(sum(float(r["six_month"]) < float(r["revised_young_year_rate"])
                                  for r in dutch)),
        "nl_paid": snapshot["positive_receipts"], "nl_snapshot_n": snapshot["issued"],
        "nl_past_due": snapshot["at_least_30dpd"],
        "cz_mark_n": coverage["test_early3"], "cz_mark_y": coverage["test_early3_events"],
        "cz_already": coverage["already_short_by_month3"],
        "cz_still_marked": coverage["marked_at_risk"], "cz_new_marked": coverage["incident_marked"],
        "cz_still_unmarked": coverage["unmarked_at_risk"], "cz_new_unmarked": coverage["incident_unmarked"],
        "cz_rest_n": str(int(coverage["scored_loans"]) - int(coverage["test_early3"])),
        "cz_rest_y": str(int(coverage["test_events"]) - int(coverage["test_early3_events"])),
        "cz_n": coverage["scored_loans"], "cz_books": coverage["scored_books"],
        "cz_flags": direction["flags"], "cz_hits": direction["true_flags"],
        "cz_below": direction["actual_below"], "cz_cut": percent(change["cutoff"]),
        "cz_add": change["extra_books"], "cz_drop": change["dropped_books"],
        "nl_old_capture_n": f"{mature_early} / {mature_year}",
        "nl_young_capture_n": f"{young_early} / {young_events}",
        "nl_old_capture_share": f"{mature_early / mature_year:.1%}",
        "nl_young_capture_share": f"{young_early / young_events:.1%}",
        "nl_nov_forecast": percent(november["six_month"]),
        "nl_nov_actual": percent(young_events / int(november["young_mature_at_snapshot"])),
    }
    for baseline in ("local", "other"):
        row = one(read_table("early_czech_policy"), method="six", reference=baseline, good="0.1", bad="-0.45")
        values[f"cz_{baseline}_switch"] = row["extra_books"]+" / "+row["dropped_books"]
        values[f"cz_{baseline}_money"] = f"{float(row['delta_margin_czk']):+,.0f}".replace("-", "−")
        values[f"cz_{baseline}_drop"] = row["dropped_books"]
    scores = read_table("early_czech_metrics")
    for method in ("local", "six", "other"):
        values[f"cz_{method}_err"] = f"{float(one(scores, method=method)['brier']):.4f}"
        values[f"cz_{method}_funded"] = one(policy, method=method)["funded"]
    return values


def result_fields():
    comparison = read_table("paper_comparison")
    training = read_table("training")
    uncertainty = read_table("uncertainty")
    policy = read_table("policy")
    sensitivity = read_table("simulation_comparison")
    audits = read_table("audit_summary")
    cohort = read_table("cohort")
    fields = decision_fields()
    fields.update(pilot_fields())
    fields.update(transfer_fields())
    fields.update(signal_fields())
    fields.update(frequency_fields())
    fields.update(local_trust_fields())
    fields.update(early_payment_fields())
    fields["talk_iv_loss"] = f"{float(fields['iv_loss']):.2f}"
    fields["talk_iv_per"] = f"{float(fields['iv_per']):.2f}"
    fields["talk_iv_cap"] = f"{float(fields['iv_cap']):.2f}"
    for key, dataset in [("orig", "monedo"), ("tw", "taiwan"), ("pr", "prosper")]:
        for label, method in [("a", "accepts"), ("i", "ipw"), ("b", "bayes")]:
            fields[f"{key}_eval_{label}"] = number(one(comparison, table=2, method=method, metric="abr")[dataset])
        for metric in ("auc", "brier", "pauc", "abr"):
            a, b = [float(one(comparison, table=3, method=method, metric=metric)[dataset])
                    for method in ("accepts", "basl")]
            fields[f"{key}_pair_{metric}"] = f"{a:.4f} / {b:.4f}"
        baseline = float(one(comparison, table=3, method="accepts", metric="abr")[dataset])
        basl = float(one(comparison, table=3, method="basl", metric="abr")[dataset])
        fields[f"{key}_tr_a"] = percent(baseline)
        fields[f"{key}_tr_b"] = percent(basl)
        fields[f"{key}_delta"] = signed(basl - baseline)
        if dataset == "monedo":
            continue
        ci = one(uncertainty, dataset=dataset, contrast="basl_minus_accepts_abr")
        fields[f"{key}_ci"] = f"[{signed(ci['ci_low'])}, {signed(ci['ci_high'])}]"
        error = one(uncertainty, dataset=dataset, contrast="bayes_minus_accepts_rmse_abr")
        fields[f"{key}_eval_ci"] = f"[{signed(error['ci_low'])}, {signed(error['ci_high'])}]".replace("-", "−")
        fields[f"{dataset}_n"] = format(int(one(cohort, dataset=dataset)["population_rows"]), ",")
        guarded = matching(training, dataset=dataset, method="basl_guarded")
        fields[f"{key}_guard"] = percent(statistics.mean(float(r["abr"]) for r in guarded))
        selected = matching(policy, dataset=dataset, method="bayes", lgd="0.5")
        for label, metric in [("approval", "test_approval"), ("margin", "profit_per_applicant")]:
            fields[f"{key}_{label}"] = percent(statistics.mean(float(row[metric]) for row in selected))
        fields[f"{key}_profit_delta"] = number(
            one(uncertainty, dataset=dataset, contrast="bayes_minus_accepts_profit_at_lgd50")["estimate"])
        for label, design in [("all", "all_rejects"), ("target", "policy_rejects")]:
            fields[f"{key}_audit_{label}"] = number(one(audits, dataset=dataset, design=design,
                                                        n_audited=50)["audit_rmse"])
        fields[f"{key}_audit_prior"] = number(one(audits, dataset=dataset, design="all_rejects",
                                                  n_audited=50)["prior_only_rmse"])
    # Hard-cutoff sensitivity: same index, folds and models, deterministic historical acceptance.
    hard = read_table("hard_selection")
    for key, dataset in [("tw", "taiwan"), ("pr", "prosper")]:
        def value(q, dataset=dataset):
            return float(one(hard, dataset=dataset, design="hard", quantity=q)["estimate"])
        fields[f"{key}_hard_eval_a"] = number(value("accepts_eval_rmse_abr"))
        fields[f"{key}_hard_eval_b"] = number(value("bayes_eval_rmse_abr"))
        fields[f"{key}_hard_tr_a"] = percent(value("accepts_test_abr"))
        fields[f"{key}_hard_tr_b"] = percent(value("basl_test_abr"))
        for label, q in [("eval", "bayes_minus_accepts_rmse_abr"), ("basl", "basl_minus_accepts_abr")]:
            row = one(hard, dataset=dataset, design="hard", quantity=q)
            fields[f"{key}_hard_{label}_delta"] = signed(row["estimate"]).replace("-", "−")
            fields[f"{key}_hard_{label}_ci"] = f"[{signed(row['ci_low'])}, {signed(row['ci_high'])}]".replace("-", "−")
    # Same-cohort ABR estimation error: the selection correction without any population transfer.
    within = matching(read_table("evaluation"), metric="abr")
    for key, dataset in [("tw", "taiwan"), ("pr", "prosper")]:
        for label, method in [("a", "accepts"), ("b", "bayes")]:
            errors = [float(r["within_cohort_error"]) for r in matching(within, dataset=dataset, method=method)]
            fields[f"{key}_same_{label}"] = f"{100 * statistics.mean(e * e for e in errors) ** .5:.2f}"
    for label, method in [("a", "accepts"), ("b", "basl")]:
        row = one(training, dataset="prosper", method=method)
        fields[f"pr_auc_{label}"] = f"{float(row['auc']):.3f}"
    fields["pr_lift"] = f"{float(one(training, dataset='prosper', method='basl')['lift10']):.2f}"
    for key, stat in [("ignore", "accept_eval_rmse"), ("bayes", "bayes_eval_rmse"),
                      ("recovery", "basl_recovery_fraction"), ("guard", "basl_conservative_recovery_fraction")]:
        estimate = one(sensitivity, metric="abr", statistic=stat)["estimate"]
        fields["sim_" + key] = percent(estimate) if key in {"recovery", "guard"} else number(estimate)
    for key, stat in [("ignore", "accept_eval_rmse"), ("bayes", "bayes_eval_rmse")]:
        fields["sim_paper_" + key] = number(one(sensitivity, metric="abr", statistic=stat)["paper_value"])
    recovery = one(sensitivity, metric="abr", statistic="basl_recovery_fraction")
    fields["sim_paper_recovery"] = f"{100 * float(recovery['paper_value']):.1f}%"
    fields["sim_recovery_ci"] = f"{100 * float(recovery['ci_low']):.1f}–{100 * float(recovery['ci_high']):.1f}%"
    vintages = read_table("vintage_summary")
    bayes = one(vintages, method="bayes")
    fields.update(v_n=bayes["quarters"], v_wins=bayes["quarters_better_than_accepts"])
    for tag, method in [("a", "accepts"), ("b", "bayes")]:
        row = one(vintages, method=method)
        fields["v_h" + tag] = number(row["masking_rmse"])
        fields["v_f" + tag] = number(row["forecast_rmse"])
    fields["v_oracle"] = number(one(vintages, method="oracle_history")["forecast_rmse"])

    tipping = read_table("bounds_tipping")
    bounds = read_table("bounds_summary")
    for key, ds in [("tw", "taiwan"), ("pr", "prosper")]:
        radii = [float(r["tipping_gamma"]) for r in matching(tipping, dataset=ds, target="0.5", budget="0")]
        fields["gamma_" + key] = (f"{min(radii):.2f}–{max(radii):.2f}" if len(radii) > 1
                                   else f"{radii[0]:.2f}")
        for label, gamma in [("3", "3"), ("free", "inf")]:
            selected = one(bounds, dataset=ds, gamma=gamma, budget="0")["mean_target"]
            fields["gamma_" + key + label] = f"{float(selected):.0%}"

    cells = read_table("rct_cells")
    contrasts = read_table("rct_contrasts")
    fields["rct_n"] = format(sum(int(x["n"]) for x in cells), ",")
    for arm in ["0", "1"]:
        rows = matching(cells, assigned_offer=arm)
        fields["rct_n" + arm] = format(sum(int(r["n"]) for r in rows), ",")
        fields["rct_y" + arm] = format(sum(int(r["funded"]) for r in rows), ",")
    for tag, estimand, scale in [
            ("fund", "offer_minus_no_offer_funding", 100.),
            ("cash", "offer_minus_no_offer_cash_revenue", 1.),
            ("bothfund", "offer_all_minus_high_only_funding", 100.),
            ("bothcash", "offer_all_minus_high_only_cash_revenue", 1.)]:
        row = one(contrasts, estimand=estimand)
        fields["rct_" + tag] = f"{float(row['estimate']) * scale:+.2f}"
        fields["rct_" + tag + "ci"] = f"[{float(row['ci_low']) * scale:.2f}, {float(row['ci_high']) * scale:.2f}]"
    for tag, estimand in [
            ("short", "principal_shortfall_gt1php_among_funded_if_offer"),
            ("anyshort", "principal_shortfall_positive_among_funded_if_offer"),
            ("cashloss", "negative_cash_margin_among_funded_if_offer"),
            ("free_lo", "all_funded_hypothetical_risk_lower"),
            ("free_hi", "all_funded_hypothetical_risk_upper")]:
        fields["rct_" + tag] = percent(one(contrasts, estimand=estimand)["estimate"])
    return fields


def talk_figures(directory):
    """Draw the pilot break-even and Dutch forecast charts; return their paths by alt text."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    sys.path.insert(0, str(HERE.parent / "src"))
    from paper11.exploration import Model
    from paper11.information_value import Pilot, pilot_value

    from matplotlib import font_manager
    installed = {font.name for font in font_manager.fontManager.ttflist}
    family = next(name for name in ("Arial", "Liberation Sans", "DejaVu Sans") if name in installed)
    plt.rcParams.update({"font.family": family, "font.size": 13,
                         "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.edgecolor": AXIS, "legend.frameon": False})

    def frame(ax):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(length=0, pad=6)

    paths = {name: Path(directory) / name for name in TALK_FIGURES}

    pilot = Pilot.from_model(Model())
    later = list(range(7))
    loss = -100 * pilot.prior_margin
    fig, ax = plt.subplots(figsize=(4.3, 3.8), dpi=200, layout="constrained")
    ax.axhline(loss, color=MUTED, lw=1.2)
    ax.text(later[-1], loss - 0.08, f"Pilot’s expected loss {loss:.2f}", color=MUTED, fontsize=11.5,
            ha="right", va="top")
    for reset, color, marker, name, dy in [(0., BLUE, "o", "Risk persists", 8),
                                           (.1, ORANGE, "s", "Risk resets 10% per loan", -18)]:
        value = [100 * pilot_value(pilot, n, reset=reset) for n in later]
        ax.plot(later, value, color=color, lw=2, marker=marker, ms=6.5, mec="white", mew=1, label=name)
        ax.annotate(name, (later[-1], value[-1]), xytext=(0, dy), textcoords="offset points",
                    ha="right", color=INK, fontsize=11.5)
    first = next(n for n in later if 100 * pilot_value(pilot, n) > loss)
    ax.annotate(f"pays back after\n{first} later loans", (first, 100 * pilot_value(pilot, first)), xytext=(0.15, 2.2),
                ha="left", va="bottom", color=INK, fontsize=11.5, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1, shrinkB=6))
    ax.set(xticks=later, ylim=(0, 3.6), xlabel="Later loans that can use the outcome",
           ylabel="Expected gain from the outcome")
    ax.legend(loc="upper left", fontsize=11, handlelength=1.6, borderaxespad=0.1)
    frame(ax)
    fig.savefig(paths["talk_pilot.png"], facecolor="white")
    plt.close(fig)

    rows = read_table("early_dutch_episodes")
    x = list(range(len(rows)))
    ticks = []
    for r in rows:
        year, month = r["origin_month"].split("-")
        name = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(month)-1]
        ticks.append(name + ("\n" + year if r is rows[0] or month == "01" else ""))
    series = lambda key: [100 * float(r[key]) for r in rows]
    fig, ax = plt.subplots(figsize=(7.6, 4.1), dpi=200, layout="constrained")
    for key, name in [("local", "Dutch history"), ("broader", "Other countries")]:
        y = series(key)
        ax.plot(x, y, color=GRAY, lw=2)
        ax.text(x[-1] + 0.15, y[-1], name, va="center", color=MUTED, fontsize=12.5)
    ax.plot(x, series("revised_young_year_rate"), color=AQUA, lw=2, marker="s", ms=6.5, mec="white", mew=1)
    ax.plot(x, series("six_month"), color=BLUE, lw=2.2, marker="o", ms=7, mec="white", mew=1)
    ax.plot(x, series("target"), ls="none", color=ORANGE, marker="D", ms=7.5, mec="white", mew=1, clip_on=False,
            zorder=4)
    handles = [Line2D([], [], color=GRAY, lw=2, label="Mature histories"),
               Line2D([], [], color=BLUE, lw=2.2, marker="o", mec="white", label="Six-month forecast"),
               Line2D([], [], color=AQUA, lw=2, marker="s", mec="white", label="Young loans, own year-one rate"),
               Line2D([], [], ls="none", color=ORANGE, marker="D", mec="white", label="Next 25 loans, realized")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2, fontsize=12.5,
              handlelength=2, columnspacing=1.6, borderaxespad=0.2)
    ax.set_xticks(x, ticks)
    ax.set_xlim(-0.3, x[-1] + 1.9)
    ax.set_ylim(0, 32)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_ylabel("Default risk")
    ax.set_xlabel("Forecast date")
    frame(ax)
    fig.savefig(paths["talk_dutch.png"], facecolor="white")
    plt.close(fig)
    return paths


def image_paths(template, required):
    """Match a figure's slide alt text to its embedded media target."""
    assets = {}
    for slide in template.namelist():
        if not re.fullmatch(r"ppt/slides/slide\d+\.xml", slide):
            continue
        xml = ET.fromstring(template.read(slide))
        for pic in xml.findall(".//p:pic", NS):
            label = pic.find("p:nvPicPr/p:cNvPr", NS).get("descr")
            if label not in required:
                continue
            relid = pic.find("p:blipFill/a:blip", NS).get("{" + NS["r"] + "}embed")
            directory, name = posixpath.split(slide)
            rels = ET.fromstring(template.read(f"{directory}/_rels/{name}.rels"))
            target = next(r.get("Target") for r in rels if r.get("Id") == relid)
            item = posixpath.normpath(posixpath.join(directory, target)).lstrip("/")
            assets[item] = label
    if set(assets.values()) != required:
        raise ValueError("Missing figure alt text in slide template")
    return assets


def refresh_pptx(target, fields, template, figures):
    """figures maps each bound alt text to the image file that replaces it."""
    def substitute(match):
        return escape(fields[match.group(1).decode()]).encode("utf-8")

    with ZipFile(template) as src, ZipFile(target, "w") as out:
        assets = image_paths(src, set(figures))
        for item in src.infolist():
            payload = src.read(item)
            if item.filename in assets:
                payload = Path(figures[assets[item.filename]]).read_bytes()
            elif re.fullmatch(r"ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml", item.filename):
                payload = TOKEN.sub(substitute, payload)
                if b"{{" in payload or b"}}" in payload:
                    raise ValueError(f"Unresolved numeric field in {item.filename}")
            out.writestr(item, payload)


def main():
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        raise SystemExit("Install LibreOffice and make soffice available on PATH to export the PDF.")
    # A private LibreOffice profile also works while a desktop session is open.
    with tempfile.TemporaryDirectory(dir=HERE) as work, tempfile.TemporaryDirectory() as profile:
        tmp = Path(work)
        fields = result_fields()
        talk, evidence, defense = tmp / "talk.pptx", tmp / "evidence.pptx", tmp / "paper11.pptx"
        drawn = talk_figures(tmp)
        refresh_pptx(talk, fields, HERE / "talk-template.pptx",
                     {"simulation_fig2.png": RESULTS / "simulation_fig2.png", **drawn})
        refresh_pptx(evidence, fields, HERE / "template.pptx", {name: RESULTS / name for name in SOURCES})
        assemble(talk, evidence, defense, fields)
        subprocess.run([office, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(tmp), str(talk), str(evidence), str(defense)], check=True)
        outputs = (defense, defense.with_suffix(".pdf"), talk.with_suffix(".pdf"),
                   evidence, evidence.with_suffix(".pdf"))
        if not all(p.is_file() and p.stat().st_size for p in outputs):
            raise RuntimeError("LibreOffice did not produce all presentation PDFs")
        for output in outputs:
            output.replace(HERE / output.name)


if __name__ == "__main__":
    main()

"""Refresh the editable PPTX from checked analysis outputs, then export its PDF."""
import csv
from pathlib import Path
import posixpath
import re
import shutil
import statistics
import subprocess
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
SOURCES = {"simulation_fig2.png", "calibration.png", "vintage_forecasts.png", "bounds_frontier.png"}
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
    for label, method in [("a", "accepts"), ("b", "basl")]:
        row = one(training, dataset="prosper", method=method)
        fields[f"pr_auc_{label}"] = f"{float(row['auc']):.3f}"
    fields["pr_lift"] = f"{float(one(training, dataset='prosper', method='basl')['lift10']):.2f}"
    for key, stat in [("ignore", "accept_eval_rmse"), ("bayes", "bayes_eval_rmse"),
                      ("recovery", "basl_recovery_fraction"), ("guard", "basl_conservative_recovery_fraction")]:
        estimate = one(sensitivity, metric="abr", statistic=stat)["estimate"]
        fields["sim_" + key] = percent(estimate) if key in {"recovery", "guard"} else number(estimate)
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


def image_paths(template):
    """Match a figure's slide alt text to its embedded media target."""
    assets = {}
    for slide in template.namelist():
        if not re.fullmatch(r"ppt/slides/slide\d+\.xml", slide):
            continue
        xml = ET.fromstring(template.read(slide))
        for pic in xml.findall(".//p:pic", NS):
            label = pic.find("p:nvPicPr/p:cNvPr", NS).get("descr")
            if label not in SOURCES:
                continue
            relid = pic.find("p:blipFill/a:blip", NS).get("{" + NS["r"] + "}embed")
            directory, name = posixpath.split(slide)
            rels = ET.fromstring(template.read(f"{directory}/_rels/{name}.rels"))
            target = next(r.get("Target") for r in rels if r.get("Id") == relid)
            item = posixpath.normpath(posixpath.join(directory, target)).lstrip("/")
            assets[item] = label
    if set(assets.values()) != SOURCES:
        raise ValueError("Missing figure alt text in slide template")
    return assets


def refresh_pptx(target, fields):
    def substitute(match):
        return fields[match.group(1).decode()].encode("utf-8")

    with ZipFile(HERE / "template.pptx") as src, ZipFile(target, "w") as out:
        assets = image_paths(src)
        for item in src.infolist():
            payload = src.read(item)
            if item.filename in assets:
                payload = (RESULTS / assets[item.filename]).read_bytes()
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
        pptx = tmp / "paper11.pptx"
        refresh_pptx(pptx, result_fields())
        subprocess.run([office, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(tmp), str(pptx)], check=True)
        pdf = tmp / "paper11.pdf"
        if not pdf.exists() or not pdf.stat().st_size:
            raise RuntimeError("LibreOffice did not produce a PDF")
        for output in (pptx, pdf):
            output.replace(HERE / output.name)


if __name__ == "__main__":
    main()

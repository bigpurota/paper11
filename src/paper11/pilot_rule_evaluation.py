"""Evaluate the frozen pilot policy with paired cash and calendar-block uncertainty."""
import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from . import lender_pilot
from .pilot_rule import CAPACITY, DEFAULT, REPAY, TOL, predict
from .pilot_targeting import weighted_auc


KEYS = ["country", "customer", "pilot_month"]


def development_history(loans):
    """Every nonempty segment/month with 50 mature prior loans can supply a public update."""
    history = []
    portfolios = {}
    for key, group in loans.groupby(["Country", "customer"], sort=True):
        monthly = group.groupby("month").event.agg(["sum", "size"]).sort_index()
        first = group.groupby("month", sort=False).head(CAPACITY)
        portfolios[key] = first.groupby("month").Amount.agg(["size", "sum"])
        for origin in monthly.index:
            events, count = lender_pilot.windows(monthly, origin-24, origin-13)
            if count < 50:
                continue
            initial = (events + .5) / (count + 1)
            events, count = lender_pilot.windows(monthly, origin-12, origin-1)
            fresh = (events + .5) / (count + 1) if count else initial
            history.append((*key, origin.ordinal, (origin+13).ordinal, initial, fresh))
    return pd.DataFrame(history, columns=["country", "customer", "origin", "disclosure", "initial", "fresh"]), portfolios


def forecast_inputs(history, nominal_portfolios, origin):
    """Pass only fully elapsed portfolio months and already disclosed public updates."""
    past = history.loc[history.disclosure <= origin.ordinal]
    months = pd.period_range(origin-12, origin-1, freq="M")
    available = nominal_portfolios.reindex(months, fill_value=0)
    return (available["size"].to_numpy(), available["sum"].to_numpy(),
            past.initial.to_numpy(), past.fresh.to_numpy(), past.origin.to_numpy())


def development_panel(out, cache):
    loans = lender_pilot.prepare(lender_pilot.fetch_bondora(cache))
    frozen = pd.read_csv(out/"lender_pilot_episodes.csv", usecols=KEYS + [
        "q_initial", "q_fresh", "eligible", "selected", "predicted_net", "primary", "baseline_lend",
        "pilot_lend", "action_changed"])
    cash = pd.read_csv(out/"lender_pilot_followup.csv", usecols=KEYS + ["euro_net", "euro_pilot"])
    data = frozen.merge(cash, on=KEYS, validate="one_to_one", how="left")
    history, portfolios = development_history(loans)
    recorded_risks = history.set_index(["country", "customer", "origin"])
    batches = dict(tuple(loans.groupby(["Country", "customer", "month"], sort=False)))
    empty = loans.iloc[:0]
    rows = []
    for case in data.itertuples(index=False):
        origin = pd.Period(case.pilot_month, "M")
        group = (case.country, case.customer)
        pilot = batches[(*group, origin)].iloc[0]
        args = forecast_inputs(history, portfolios[group], origin)
        pair = recorded_risks.loc[(*group, origin.ordinal)]
        if not np.allclose([pair.initial, pair.fresh], [case.q_initial, case.q_fresh], rtol=0, atol=1e-11):
            raise ValueError("reconstructed public risk differs from the original Bondora replay")
        forecast = predict(pair.initial, pilot.Amount, *args)
        if (forecast.baseline_selected != case.selected or forecast.eligible != case.eligible
                or not np.isclose(forecast.baseline_score, case.predicted_net, rtol=0, atol=1e-11)):
            raise ValueError("frozen baseline differs from the original Bondora decision")
        later = batches.get((*group, origin+13), empty).iloc[:CAPACITY]
        switch = int(case.pilot_lend) - int(case.baseline_lend)
        scenario_pilot = float(pilot.Amount * (DEFAULT if pilot.event else REPAY))
        scenario_future = np.dot(later.Amount, np.where(later.event, DEFAULT, REPAY))
        rows.append(dict(country=case.country, customer=case.customer, origin_month=str(origin),
                         primary=case.primary, principal=pilot.Amount, q_initial=pair.initial,
                         historical_count=args[0].mean(), historical_exposure=args[1].mean(),
                         disclosed_pairs=len(args[4]), disclosed_dates=np.unique(args[4]).size,
                         **asdict(forecast), future_count=len(later), would_change_action=case.action_changed,
                         action_changed=bool(case.action_changed and len(later)),
                         net_cash=case.euro_net, pilot_cash=case.euro_pilot,
                         net_scenario=scenario_pilot + switch*scenario_future,
                         pilot_scenario=scenario_pilot))
    return pd.DataFrame(rows)


def ranking(scores, flags, weights):
    """Tie-aware AUC and noninterpolated average precision with exact score ties."""
    if not weights[flags].sum() or not weights[~flags].sum():
        return np.nan, np.nan
    auc = weighted_auc(scores, flags, weights)
    _, levels = np.unique(scores, return_inverse=True)
    count = np.bincount(levels, weights=weights)[::-1]
    positives = np.bincount(levels, weights=weights*flags, minlength=len(count))[::-1]
    encountered = np.cumsum(count)
    precision = np.divide(np.cumsum(positives), encountered, out=np.zeros_like(encountered), where=encountered > 0)
    return auc, np.dot(precision, positives) / positives.sum()


def within_segment_auc(cases, scores, events):
    """Descriptive comparison of positives with negatives in the same lending segment."""
    segment = next((name for name in ("customer", "grade") if name in cases), None)
    if segment is None:
        return np.nan, 0, 0
    geography = "region" if "region" in cases else "country"
    groups = cases.groupby([geography, segment], dropna=False).indices
    concordance = 0.
    pairs = positives = 0
    for indices in groups.values():
        known = indices[np.isfinite(events[indices])]
        flags = events[known].astype(bool)
        pair_count = int(flags.sum() * (~flags).sum())
        if pair_count:
            auc = weighted_auc(scores[known], flags, np.ones(len(known)))
            concordance += auc * pair_count
            pairs += pair_count
            positives += int(flags.sum())
    return concordance / pairs if pairs else np.nan, pairs, positives


def strict_labels(data, valuation):
    switch = data.action_changed.astype("boolean")
    loss = data["pilot_"+valuation].astype("Float64") < -TOL
    gain = data["net_"+valuation].astype("Float64") > TOL
    return (switch & loss & gain).to_numpy(dtype=float, na_value=np.nan)


def block_weights(quarters, grid_size, draws, seed):
    """A four-quarter circular moving block, preserving blank quarters and shared dates."""
    rng = np.random.default_rng(seed)
    starts = rng.integers(grid_size, size=(draws, (grid_size+3)//4))
    picks = ((starts[:, :, None] + np.arange(4)) % grid_size).reshape(draws, -1)[:, :grid_size]
    for pick in picks:
        yield np.bincount(pick, minlength=grid_size)[quarters]


def summarize(sample, cohort, panel, draws=2500, seed=26011, calendar=None):
    dates = pd.PeriodIndex(panel.origin_month, freq="M").asfreq("Q")
    if calendar is None:
        first, last = dates.min(), dates.max()
    else:
        first, last = (pd.Period(month, "M").asfreq("Q") for month in calendar)
        if len(dates) and (dates.min() < first or dates.max() > last):
            raise ValueError("panel contains origins outside its committed window")
    grid_size = last.ordinal - first.ordinal + 1
    keep = panel.eligible.to_numpy(dtype=bool)
    cases = panel.loc[keep]
    quarters = dates.asi8[keep] - first.ordinal
    selected = cases.selected.to_numpy(dtype=bool)
    baseline = cases.baseline_selected.to_numpy(dtype=bool)
    if (panel.selected & ~panel.eligible).any() or (panel.baseline_selected & ~panel.eligible).any():
        raise ValueError("policy selected an ineligible loan")
    switches = cases.action_changed.astype("boolean").to_numpy(dtype=float, na_value=np.nan)
    probabilities = cases.strict_probability.to_numpy(dtype=float)
    if not np.isfinite(probabilities).all() or np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("missing or invalid issue-time forecast")
    n = len(cases)
    result = dict(sample=sample, cohort=cohort, currency="USD" if sample == "prosper" else "EUR",
                  scheduled=len(panel), quarters=grid_size,
                  occupied_quarters=dates.nunique(), eligible=n, quarters_with_eligible=len(set(quarters)),
                  selected=int(selected.sum()), baseline_selected=int(baseline.sum()),
                  common_selected=int((selected & baseline).sum()), known_action=int(np.isfinite(switches).sum()),
                  switches=int(np.nansum(switches)), selected_switches=int(np.nansum(switches[selected])),
                  baseline_switches=int(np.nansum(switches[baseline])),
                  selected_action_known=int(np.isfinite(switches[selected]).sum()))
    if "future_count" in cases:
        result["empty_continuations"] = int(cases.future_count.eq(0).sum())
    if "would_change_action" in cases:
        result["contingent_switches"] = int(cases.would_change_action.astype("boolean").sum())
    strategies = {"new": selected, "baseline": baseline}
    for name in ("exposure_only", "risk_only"):
        column = name+"_net"
        if column in cases:
            strategies[name] = cases[column].to_numpy() > TOL * cases.principal.to_numpy()
            result[name+"_selected"] = int(strategies[name].sum())
    amounts = {}
    labels = {}
    for valuation in ("cash", "scenario"):
        net = cases["net_"+valuation].to_numpy(dtype=float)
        amounts["forced_"+valuation] = net
        event = strict_labels(cases, valuation)
        valid = np.isfinite(event)
        labels[valuation] = (valid, event[valid].astype(bool))
        result[valuation+"_event_known"] = int(valid.sum())
        result[valuation+"_recoveries"] = int(np.nansum(event))
        result[valuation+"_prevalence"] = event[valid].mean() if valid.any() else np.nan
        auc, pairs, positives = within_segment_auc(cases, probabilities, event)
        result[valuation+"_segment_auc"] = auc
        result[valuation+"_segment_pairs"] = pairs
        result[valuation+"_segment_positives"] = positives
        for name, issued in strategies.items():
            amounts[name+"_"+valuation] = np.where(issued, net, 0.)
            if name not in ("new", "baseline"):
                continue
            tp = int(np.nansum(event[issued]))
            count = int(valid[issued].sum())
            result[name+"_"+valuation+"_tp"] = tp
            result[name+"_"+valuation+"_fp"] = count-tp
            result[name+"_"+valuation+"_precision"] = tp/count if count else np.nan
        delta = selected.astype(int)-baseline.astype(int)
        amounts["new_minus_baseline_"+valuation] = np.where(delta == 0, 0., delta*net)
    for name, values in amounts.items():
        result[name+"_known"] = int(np.isfinite(values).sum())
    def estimate(weights):
        values = {}
        for name, amounts_for_policy in amounts.items():
            valid = np.isfinite(amounts_for_policy)
            mass = weights[valid].sum()
            values[name] = np.dot(weights[valid], amounts_for_policy[valid])/mass if mass else np.nan
        for valuation, (valid, event) in labels.items():
            auc, ap = ranking(probabilities[valid], event, weights[valid])
            values["auc_"+valuation], values["ap_"+valuation] = auc, ap
        return values

    result.update(estimate(np.ones(n)))
    interval_names = [key for key in result if key.startswith(("auc_", "ap_"))]
    interval_names += ["new_cash", "new_minus_baseline_cash", "new_scenario", "new_minus_baseline_scenario"]
    samples = {key: [] for key in interval_names}
    if draws > 0 and dates.nunique() > 4:
        for weights in block_weights(quarters, grid_size, draws, seed):
            for key, value in estimate(weights).items():
                if key in samples and np.isfinite(value):
                    samples[key].append(value)
    for key, values in samples.items():
        lo, hi = np.quantile(values, [.025,.975]) if values else (np.nan, np.nan)
        result[key+"_low"], result[key+"_high"], result[key+"_draws"] = lo, hi, len(values)
    result["cash_gain_supported"] = bool(n and result["new_cash_known"] == n and
        result["new_minus_baseline_cash_known"] == n and result["new_cash_low"] > 0 and
        result["new_minus_baseline_cash_low"] > 0)
    result["cash_ranking_supported"] = bool(n and result["cash_event_known"] == n and result["auc_cash_low"] > .5)
    return result


def run(out, cache):
    development = development_panel(out, cache)
    development.to_csv(out/"pilot_rule_development.csv", index=False, float_format="%.12g")
    archive_month = lender_pilot.SNAPSHOT.to_period("M")
    rows = [summarize("development", "primary_36m", development[development.primary],
                      calendar=(lender_pilot.FIRST, archive_month-37-13)),
            summarize("development", "expanded_12m", development,
                      calendar=(lender_pilot.FIRST, archive_month-13-13))]
    for source, cohorts in (("holdout", ("primary", "seasoned")), ("prosper", ("prosper",))):
        episodes = pd.read_csv(out/f"pilot_{source}_episodes.csv").rename(columns={"pilot_principal": "principal"})
        meta = pd.read_csv(out/f"pilot_{source}_cohort.csv").set_index("sample")
        for cohort in cohorts:
            data = episodes.loc[episodes["sample"] == cohort]
            calendar = meta.loc[cohort, ["origin_start", "origin_end"]]
            if len(data) != meta.loc[cohort, "opportunities"]:
                raise ValueError("episode count differs from the source audit")
            rows.append(summarize(source, cohort, data, calendar=calendar))
    summary = pd.DataFrame(rows)
    summary.to_csv(out/"pilot_rule_summary.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    options = parser.parse_args()
    run(options.out, options.cache)

"""Trace the 27% Dutch historical forecast to the vintages that supplied it."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .pilot_holdout import fetch_holdout, order_positions, read_positions
from .pilot_rule import CAPACITY
from .pilot_signal_panel import country_order


def jeffreys(defaults, measured):
    return (defaults + .5) / (measured + 1) if measured else np.nan


def divide(numerator, denominator):
    return numerator / denominator if denominator else np.nan


def monthly_books(loans):
    """Count missing outcome amounts separately, including on the first 25."""
    block = loans.assign(known_principal=loans.principal.where(loans.event.notna(), 0.),
                         default_principal=loans.principal.where(loans.event.eq(1), 0.))
    fields = dict(issued=("principal", "size"), labels=("event", "count"), defaults=("event", "sum"),
                  principal=("principal", "sum"), known_principal=("known_principal", "sum"),
                  default_principal=("default_principal", "sum"))
    all_month = block.groupby("origin", sort=True).agg(**fields)
    first = block.groupby("origin", sort=False).head(CAPACITY)
    first_month = first.groupby("origin", sort=True).agg(**fields).add_prefix("first25_")
    return all_month.join(first_month)


def diagnose(months, others, episodes):
    output = []
    for s in pd.PeriodIndex(episodes.origin_month, freq="M"):
        prior = months.loc[s-24:s-13]
        history = prior.sum()
        recent = months.loc[s-12:s-1].sum()
        future = months.loc[s+13]
        external = others.loc[s-24:s-13].sum()
        n = int(history.labels)
        raw = divide(history.defaults, n)
        q = jeffreys(history.defaults, n)
        later = divide(future.defaults, future.labels)
        capped = divide(future.first25_defaults, future.first25_labels)
        target = (divide(future.first25_default_principal, future.first25_principal)
                  if future.first25_labels == future.first25_issued else np.nan)
        full = divide(future.default_principal, future.known_principal)
        output.append(dict(
            origin_month=str(s), disclosure_month=str(s+13),
            historical_start=str(s-24), historical_end=str(s-13),
            observed_historical_months=int(prior.labels.gt(0).sum()),
            historical_issued=int(history.issued), historical_labels=n, historical_defaults=int(history.defaults),
            largest_historical_vintage_share=divide(prior.labels.max(), n),
            effective_historical_months=divide(n**2, np.square(prior.labels).sum()),
            historical_count_rate=raw, local_forecast=q,
            historical_principal_rate=divide(history.default_principal, history.known_principal),
            external_labels=int(external.labels), external_defaults=int(external.defaults),
            other_countries_forecast=jeffreys(external.defaults, external.labels),
            recent_issued=int(recent.issued), volume_ratio=divide(recent.issued, history.issued),
            recent_labels_at_disclosure=int(recent.labels), recent_defaults_at_disclosure=int(recent.defaults),
            refreshed_forecast=jeffreys(recent.defaults, recent.labels),
            future_issued=int(future.issued), future_labels=int(future.labels),
            future_defaults=int(future.defaults), future_principal=future.principal,
            future_known_principal=future.known_principal, future_default_principal=future.default_principal,
            future_all_count_rate=later, future_all_principal_rate=full,
            first25_issued=int(future.first25_issued), first25_labels=int(future.first25_labels),
            first25_defaults=int(future.first25_defaults), first25_principal=future.first25_principal,
            first25_known_principal=future.first25_known_principal,
            first25_default_principal=future.first25_default_principal,
            first25_count_rate=capped, first25_principal_rate=target,
            smoothing_effect=q-raw, change_across_vintages=raw-later,
            first25_selection_effect=later-capped, principal_weight_effect=capped-target,
            forecast_gap=q-target,
        ))
    return pd.DataFrame(output)


def contract_mix(loans, episodes):
    """Standardize later first-year rates to the unique historical loans' contract mix."""
    schedule = pd.PeriodIndex(episodes.origin_month, freq="M")
    older_dates = {s-lag for s in schedule for lag in range(13, 25)}
    later_dates = set(schedule + 13)
    if older_dates & later_dates:
        raise ValueError("contract mix comparison requires non-overlapping source vintages")
    observed = loans.loc[loans.origin.isin(older_dates | later_dates)].copy()
    older = observed.origin.isin(older_dates)
    observed["cohort"] = np.where(older, "early", "later")
    term = pd.to_numeric(observed.initial_loan_duration).astype("Int64").astype("string").fillna("missing")
    observed["original_term_months"] = term.where(term.isin(term[older]), "other")
    observed["amount_eur"] = pd.cut(observed.principal, [0, 1000, 2000, 5000, np.inf],
                                    labels=["up_to_1000", "1000_to_2000", "2000_to_5000", "above_5000"])
    observed["grade_recorded"] = observed.grade.ne("(unrated)")
    keys = ["original_term_months", "amount_eur"]
    cells = observed.groupby([*keys, "cohort"], observed=True).agg(
        issued=("event", "size"), labels=("event", "count"), defaults=("event", "sum"),
        grade_recorded=("grade_recorded", "sum")).unstack("cohort", fill_value=0)
    cells.columns = [f"{cohort}_{name}" for name, cohort in cells.columns]
    cells = cells.reset_index()
    cells["later_rate"] = cells.later_defaults / cells.later_labels.replace(0, np.nan)
    cells["early_weight"] = cells.early_labels / cells.early_labels.sum()
    cells["later_rate_at_early_weights"] = np.where(cells.early_weight.eq(0), 0.,
                                                    cells.early_weight * cells.later_rate)
    return cells


def donor_history(positions, episodes):
    other = positions.loc[positions.country.ne("Netherlands")]
    by_month = other.groupby(["origin", "country"]).event.agg(historical_labels="count",
                                                               historical_defaults="sum")
    rows = []
    for s in pd.PeriodIndex(episodes.origin_month, freq="M"):
        history = by_month.loc[slice(s-24, s-13), :]
        counts = history.groupby("country").sum().astype(int)
        counts.insert(0, "origin_month", str(s))
        rows.append(counts.reset_index())
    return pd.concat(rows, ignore_index=True)


def run(out, cache):
    out = Path(out)
    ref = pd.read_csv(out / "pilot_signal_panel.csv")
    episodes = ref.loc[ref["sample"].eq("test") & ref.country.eq("Netherlands")].sort_values("origin_month")
    positions = order_positions(read_positions(fetch_holdout(cache)))
    is_dutch = positions.country.eq("Netherlands")
    loans = country_order(positions.loc[is_dutch])
    months = monthly_books(loans)
    others = positions.loc[~is_dutch].groupby("origin").event.agg(labels="count", defaults="sum")
    cases = diagnose(months, others, episodes)
    for calculated, original in [("local_forecast", "q_initial"), ("historical_labels", "prior_n"),
                                 ("refreshed_forecast", "q_fresh"), ("first25_principal", "future_principal"),
                                 ("first25_default_principal", "future_default_principal")]:
        np.testing.assert_allclose(cases[calculated], episodes[original], rtol=1e-9)
    windows = pd.PeriodIndex(episodes.origin_month, freq="M")
    calendar = pd.period_range(windows.min()-24, windows.max()+13, freq="M")
    months = months.reindex(calendar, fill_value=0).rename_axis("origin_month")
    donors = donor_history(positions, episodes)
    donors.to_csv(out / "dutch_frequency_donors.csv", index=False)
    mix = contract_mix(loans, episodes)
    mix.to_csv(out / "dutch_frequency_contract_mix.csv", index=False, float_format="%.12g")
    months.to_csv(out / "dutch_frequency_vintages.csv", float_format="%.12g")
    cases.to_csv(out / "dutch_frequency_episodes.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)

"""Dated country-month episodes for evaluating the incremental value of a pilot label."""
import argparse
from collections import defaultdict
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .lender_pilot import after_signal, margin
from .pilot_holdout import fetch_holdout, order_positions, read_positions
from .pilot_rule import CAPACITY, TOL, predict


TRAIN_START = pd.Period("2009-02", "M")
TEST_START = pd.Period("2022-10", "M")
TEST_END = pd.Period("2024-05", "M")
DISCOVERY_MONTHS = tuple(pd.Period(month, "M") for month in ("2021-03", "2021-11", "2022-02"))
TRAIN_END = TEST_START - 26
WINDOWS = {"train": (TRAIN_START, TRAIN_END), "test": (TEST_START, TEST_END)}
ORIGIN_CONTRACT = ("country", "grade", "loan_issued_at", "issued_amount",
                   "initial_interest_rate", "initial_loan_duration")


def country_order(loans):
    """Keep the archived intraday ordering, extending contract-key tie breaks across grades."""
    tied = loans.duplicated(["country", "date"], keep=False)
    if tied.any():
        loans = loans.copy()
        loans.loc[tied, "order_key"] = [
            hashlib.sha256("\x1f".join(map(str, row)).encode()).hexdigest()
            for row in loans.loc[tied, list(ORIGIN_CONTRACT)].itertuples(index=False, name=None)
        ]
    return loans.sort_values(["date", "order_key", "source_order"], kind="stable")


def previous_positions(loans, previous, *, by_grade=True):
    """Recover issued and follow-up positions from the earlier schedule and its original ordering."""
    if previous.empty:
        return set(), set()
    groups = ["country", "grade", "origin"] if by_grade else ["country", "origin"]
    capped = loans.groupby(groups, sort=False).head(CAPACITY)
    by_group = capped.groupby(groups, sort=False).source_order.agg(list).to_dict()
    pilot_ids, continuation_ids = set(), set()
    for row in previous.itertuples(index=False):
        segment = (row.country, row.grade) if by_grade else (row.country,)
        pilot = by_group[(*segment, pd.Period(row.origin_month, "M"))]
        batch = by_group.get((*segment, pd.Period(row.disclosure_month, "M")), [])
        if len(batch) != row.future_count:
            raise ValueError("previous continuation count differs from the dated source")
        pilot_ids.add(pilot[0])
        continuation_ids.update(batch)
    return pilot_ids, continuation_ids


def country_cells(loans):
    """Aggregate the full public book and the first up-to-25 continuation positions separately."""
    groups = ["country", "origin"]
    monthly = loans.groupby(groups, sort=False).event.agg(issued="size", labels="count", defaults="sum")
    capped = loans.groupby(groups, sort=False).head(CAPACITY).copy()
    capped["default_principal"] = capped.event * capped.principal
    batches = capped.groupby(groups, sort=False)
    columns = ["principal", "default_principal", "scenario", "cash", "principal_balance"]
    sums = batches[columns].sum().where(batches[columns].count().eq(batches.size(), axis="index"))
    sums["count"] = batches.size()
    sums["event_n"] = batches.event.count()
    sums["old_pilots"] = batches.old_pilot.sum()
    sums["old_continuations"] = batches.old_continuation.sum()
    pilots = capped.drop_duplicates(groups).set_index(groups)
    return monthly, sums, pilots


def ordinary_history(monthly):
    """Build each estimate from twelve fully mature origin months at its own disclosure date."""
    estimates = {}
    releases = defaultdict(list)
    for country, group in monthly.groupby(level="country", sort=True):
        group = group.droplevel("country").sort_index()
        dates = pd.period_range(group.index.min(), group.index.max(), freq="M")
        history = group[["labels", "defaults"]].reindex(dates, fill_value=0)
        rolling = history.rolling(12, min_periods=1).sum()
        initial, refresh = rolling.shift(13), rolling.shift(1).fillna(0)
        for origin in group.index:
            if not initial.loc[origin, "labels"] >= 50:
                continue
            n, defaults = initial.loc[origin]
            n1, defaults1 = refresh.loc[origin]
            q = (defaults + .5) / (n + 1)
            u = (defaults1 + .5) / (n1 + 1) if n1 else q
            estimates[(country, origin)] = (q, u, int(n), int(n1))
            releases[origin + 13].append((q, u, origin.ordinal))
    return estimates, releases


def make_signal_panel(loans, previous=None, windows=None, *, pilot_rank=1):
    """Cash is withheld from training, including on loans whose one-year labels have matured."""
    if pilot_rank < 1:
        raise ValueError("pilot rank starts at one")
    include_discovery = windows is None
    windows = WINDOWS if windows is None else windows
    previous = pd.DataFrame() if previous is None else previous
    old_pilots, old_continuations = previous_positions(loans, previous)
    loans = country_order(loans).assign(old_pilot=lambda d: d.source_order.isin(old_pilots),
                                        old_continuation=lambda d: d.source_order.isin(old_continuations))
    monthly, totals, pilots = country_cells(loans)
    if pilot_rank != 1:
        groups = ["country", "origin"]
        ordered_index = loans.groupby(groups, sort=False).cumcount()
        pilots = loans.loc[ordered_index.eq(pilot_rank - 1)].set_index(groups)
    estimates, releases = ordinary_history(monthly)
    books = totals.to_dict("index")
    zero = dict(count=0, principal=0., event_n=0, default_principal=0., scenario=0.,
                cash=0., principal_balance=0., old_pilots=0, old_continuations=0)
    periods = {date: name for name, (a, b) in windows.items()
               for date in pd.period_range(a, b, freq="M")}
    if include_discovery:
        periods.update({date: "discovery" for date in DISCOVERY_MONTHS})
    country_dates = defaultdict(list)
    for country, origin in monthly.index:
        country_dates[origin].append(country)
    past_updates, rows, support = [], [], []
    for date in sorted(set(periods) | set(releases)):
        past_updates.extend(releases.get(date, []))
        if date not in periods:
            continue
        sample = periods[date]
        old, updated, origin_dates = zip(*past_updates) if past_updates else ((), (), ())
        for country in sorted(country_dates[date]):
            if sample == "discovery" and country != "Finland":
                continue
            key = (country, date)
            cell = monthly.loc[key]
            support_row = dict(sample=sample, country=country, origin_month=str(date),
                               issued=int(cell.issued), origin_known_flags=int(cell.labels),
                               supported=key in estimates and cell.issued >= pilot_rank)
            support.append(support_row)
            if not support_row["supported"]:
                continue
            q, u, n0, n1 = estimates[key]
            pilot = pilots.loc[key]
            history = [books.get((country, date - lag), zero) for lag in range(12, 0, -1)]
            counts = np.asarray([lot["count"] for lot in history], dtype=int)
            volumes = np.asarray([lot["principal"] for lot in history])
            old_rule = predict(q, pilot.principal, counts, volumes, old, updated, origin_dates)
            followup = books.get((country, date + 13), zero)
            measured = pd.notna(pilot.event)
            ordinary_lends = bool(margin(u) > TOL)
            informed_lends = bool(margin(after_signal(u, pilot.event)) > TOL) if measured else np.nan
            rows.append(dict(
                sample=sample, country=country, origin_month=str(date), disclosure_month=str(date + 13),
                target_ready_month=str(date + 26), q_initial=q, q_fresh=u, prior_n=n0, refresh_n=n1,
                pilot_principal=pilot.principal, pilot_rate=pd.to_numeric(pilot.initial_interest_rate),
                pilot_term=pd.to_numeric(pilot.initial_loan_duration), mean_prior_count=counts.mean(),
                mean_prior_exposure=volumes.mean(), peer_total=int(cell.issued)-1,
                peer_n=int(cell.labels)-int(measured),
                peer_defaults=int(cell.defaults)-(int(pilot.event) if measured else 0),
                pilot_default=pilot.event, future_count=int(followup["count"]),
                future_event_n=int(followup["event_n"]), future_principal=followup["principal"],
                future_default_principal=followup["default_principal"], pilot_scenario=pilot.scenario,
                future_scenario=followup["scenario"], pilot_cash=pilot.cash if sample != "train" else np.nan,
                future_cash=followup["cash"] if sample != "train" else np.nan,
                pilot_balance=pilot.principal_balance if sample != "train" else np.nan,
                future_balance=followup["principal_balance"] if sample != "train" else np.nan,
                structural_eligible=old_rule.eligible, structural_selected=old_rule.selected,
                structural_net=old_rule.net_money, structural_probability=old_rule.strict_probability,
                structural_lend_common=ordinary_lends, structural_lend_signal=informed_lends,
                pilot_in_previous_continuation=bool(pilot.old_continuation),
                future_in_previous_pilot_count=int(followup["old_pilots"]),
                future_in_previous_continuation_count=int(followup["old_continuations"]),
            ))
    return pd.DataFrame(rows), pd.DataFrame(support)


def run(out, cache):
    out = Path(out)
    previous = pd.read_csv(out / "pilot_holdout_episodes.csv", usecols=[
        "country", "grade", "origin_month", "disclosure_month", "future_count"])
    loans = order_positions(read_positions(fetch_holdout(cache)))
    panel, support = make_signal_panel(loans, previous)
    panel.to_csv(out / "pilot_signal_panel.csv", index=False, float_format="%.12g")
    support.to_csv(out / "pilot_signal_panel_coverage.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)

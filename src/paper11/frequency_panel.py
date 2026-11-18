"""Mature country-months and position overlap for the locked frequency-anchored test."""
import argparse
from pathlib import Path

import pandas as pd

from .pilot_holdout import fetch_holdout, order_positions, read_positions
from .pilot_rule import CAPACITY
from .pilot_signal_panel import TRAIN_START, country_order, make_signal_panel, previous_positions


TEST_START = pd.Period("2024-06", "M")
TEST_END = pd.Period("2024-09", "M")
WINDOWS = {"train": (TRAIN_START, TEST_START - 26), "test": (TEST_START, TEST_END)}
MONTH_KEYS = ["country", "origin"]


def position_audit(loans, grade_schedule, country_schedule):
    """Keep IDs inside the adapter; report role overlaps and missing target exposure."""
    grade_pilots, grade_books = previous_positions(loans, grade_schedule)
    ordered = country_order(loans)
    old_pilots, old_books = previous_positions(ordered, country_schedule, by_grade=False)
    data = ordered[["country", "origin", "principal", "event", "source_order"]].copy()
    data["in_grade_pilot"] = data.source_order.isin(grade_pilots)
    data["in_grade_book"] = data.source_order.isin(grade_books)
    data["in_country_pilot"] = data.source_order.isin(old_pilots)
    data["in_country_book"] = data.source_order.isin(old_books)
    data["in_previous_pilot"] = data.in_grade_pilot | data.in_country_pilot
    data["in_previous_continuation"] = data.in_grade_book | data.in_country_book
    data["previous_position"] = data.in_previous_pilot | data.in_previous_continuation
    data["known_default_principal"] = data.principal.where(data.event.eq(1), 0.)
    data["unknown_principal"] = data.principal.where(data.event.isna(), 0.)
    by_month = data.groupby(MONTH_KEYS, sort=False)
    data["pilot_rank"] = by_month.cumcount() + 1
    data["peer_in_previous_scored_count"] = by_month.previous_position.transform("sum") - data.previous_position
    origin_flags = [k for k in data if k.startswith("in_")]
    candidates = data.loc[data.pilot_rank.isin([1, 26]),
                          [*MONTH_KEYS, "pilot_rank", "peer_in_previous_scored_count", *origin_flags]]
    candidates = candidates.rename(columns={f: "pilot_" + f for f in origin_flags})
    sums = data.loc[data.pilot_rank.le(CAPACITY)].groupby(MONTH_KEYS, sort=False)[
        [*origin_flags, "known_default_principal", "unknown_principal"]].sum()
    names = {f: "future_" + f + "_count" for f in origin_flags}
    sums = sums.rename(columns=names | {x: "future_" + x for x in ("known_default_principal", "unknown_principal")})
    return candidates, sums


def assemble_panels(loans, grade_schedule, country_schedule, windows=WINDOWS):
    candidates, books = position_audit(loans, grade_schedule, country_schedule)
    panels, coverage = [], []
    for rank in [1, 26]:
        run_windows = windows if rank == 1 else {"test": windows["test"]}
        table, support = make_signal_panel(loans, windows=run_windows, pilot_rank=rank)
        support["pilot_rank"] = rank
        support["rank_available"] = support.issued.ge(rank)
        coverage.append(support)
        if table.empty:
            continue
        table["pilot_rank"] = rank
        table["origin"] = pd.PeriodIndex(table.origin_month, freq="M")
        table["continuation_origin"] = table.origin + 13
        # The previous adapter's three overlap fields describe only a grade stream.
        # Replace these with the union of previous country and grade positions.
        table = table.drop(columns=["pilot_in_previous_continuation", "future_in_previous_pilot_count",
                                    "future_in_previous_continuation_count"])
        table = table.merge(candidates, on=[*MONTH_KEYS, "pilot_rank"], how="left", validate="many_to_one")
        if table.pilot_in_previous_pilot.isna().any():
            raise ValueError("missing origination position")
        future = books.rename_axis(index={"origin": "continuation_origin"})
        table = table.join(future, on=["country", "continuation_origin"], validate="many_to_one")
        if table.loc[table.future_count.gt(0), future.columns].isna().any().any():
            raise ValueError("nonempty continuation missing its position or exposure audit")
        table[future.columns] = table[future.columns].fillna(0)
        for key in future.columns:
            if key.endswith("_count"):
                table[key] = table[key].astype(int)
        panels.append(table.drop(columns=["origin", "continuation_origin"]))
    return pd.concat(panels, ignore_index=True), pd.concat(coverage, ignore_index=True)


def run(out, cache):
    out = Path(out)
    dates = ["country", "origin_month", "disclosure_month", "future_count"]
    grades = pd.read_csv(out / "pilot_holdout_episodes.csv", usecols=[*dates, "grade"])
    earlier = pd.read_csv(out / "pilot_signal_panel.csv", usecols=dates)
    loans = order_positions(read_positions(fetch_holdout(cache)))
    panel, coverage = assemble_panels(loans, grades, earlier)
    panel.to_csv(out / "frequency_panel.csv", index=False, float_format="%.12g")
    coverage.to_csv(out / "frequency_panel_coverage.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)

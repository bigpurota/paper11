"""Test the local frequency credibility rule on a locked set of Wells Fargo vintages."""
import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .data import fetch
from .local_trust import trust_forecast
from .pilot_replay import AS_OF, STATE_REGION
from .pilot_signal_evaluation import brier, block_counts

SOURCES = ("sba7a_1991_1999", "sba7a_2000_2009", "sba7a_2010_2019")
DATES = pd.period_range("2015Q1", "2019Q3", freq="Q")
FIELDS = ["AsOfDate", "ApprovalFY", "BankFDICNumber", "ProjectState", "FirstDisbursementDate",
          "ApprovalDate", "ChargeOffDate", "LoanStatus", "GrossApproval"]
METHODS = ("local", "pooled", "hybrid", "hard", "support_hybrid")


def load_cohorts(paths):
    """Only aggregate counts, approvals and three-year events leave the adapter."""
    batches, audit = [], []
    for source, path in zip(SOURCES, paths, strict=True):
        loans, source_rows = [], 0
        for part in pd.read_csv(path, usecols=FIELDS, dtype=str, chunksize=100000):
            if not pd.to_datetime(part.AsOfDate, format="mixed").eq(AS_OF).all():
                raise ValueError("unexpected SBA archive snapshot")
            source_rows += len(part)
            loans.append(part.loc[pd.to_numeric(part.BankFDICNumber, errors="coerce").eq(3511)])
        bank = pd.concat(loans, ignore_index=True)
        day = pd.to_datetime(bank.FirstDisbursementDate, format="mixed")
        approval = pd.to_datetime(bank.ApprovalDate, format="mixed")
        charge = pd.to_datetime(bank.ChargeOffDate, format="mixed")
        amount = pd.to_numeric(bank.GrossApproval, errors="raise")
        terminal = bank.LoanStatus.str.strip().str.upper().eq("CHGOFF")
        consistent = approval.notna() & day.notna() & day.ge(approval)
        state = bank.ProjectState.isin(STATE_REGION)
        matured = day + pd.DateOffset(years=3)
        bad_charge = charge.notna() & charge.lt(day)
        keep = consistent & state & amount.gt(0) & ~bad_charge & matured.le(AS_OF)
        flag = charge.notna() & charge.le(matured)
        known = ~(terminal & charge.isna())
        fiscal = pd.to_numeric(bank.ApprovalFY, errors="raise")
        lower, upper = map(int, source.split("_")[-2:])
        if not fiscal.between(lower, upper).all():
            raise ValueError("approval fiscal year outside source segment")
        rows = pd.DataFrame(dict(quarter=day.dt.to_period("Q"), state=bank.ProjectState, issued=1,
                                 n=known.astype(int), defaults=(flag & known).astype(int),
                                 principal=amount, known_principal=amount.where(known, 0.),
                                 default_principal=amount.where(flag & known, 0.))).loc[keep]
        cells = rows.groupby(["quarter", "state"]).sum().reset_index()
        cells["source"] = source
        batches.append(cells)
        audit.append(dict(source=source, file_rows=source_rows, bank_rows=len(bank),
                          missing_or_reversed_origination=int((~consistent).sum()),
                          outside_states=int((consistent & ~state).sum()),
                          invalid_principal=int((consistent & state & ~amount.gt(0)).sum()),
                          premature_chargeoff=int((consistent & state & amount.gt(0) & bad_charge).sum()),
                          immature=int((consistent & state & amount.gt(0) & ~bad_charge & matured.gt(AS_OF)).sum()),
                          retained=len(rows), known_flags=rows.n.sum(), unknown_flags=len(rows) - rows.n.sum()))
    return pd.concat(batches, ignore_index=True), pd.DataFrame(audit)


def score_books(cells, dates=DATES):
    states = sorted(STATE_REGION)
    history = cells.drop(columns="source").groupby(["quarter", "state"]).sum().reset_index()
    target = cells[cells.source.eq(SOURCES[-1])]
    by_date = target.set_index(["quarter", "state"]).sort_index()
    rows = []
    for t in dates:
        mature = history.loc[history.quarter.between(t-24, t-13)].groupby("state")[["n", "defaults"]].sum()
        mature = mature.reindex(states, fill_value=0)
        recent = history.loc[history.quarter.between(t-12, t-1)].groupby("state").issued.sum()
        if t not in by_date.index.get_level_values("quarter"):
            continue
        for state, outcome in by_date.loc[t].iterrows():
            own = mature.loc[state]
            donors = mature.drop(index=state)
            r = int(recent.get(state, 0))
            outside = int(donors.n.sum())
            fields = asdict(trust_forecast(own.defaults, own.n, r, donors.defaults, donors.n)) if outside else {
                k: np.nan for k in ("local", "pooled", "tau2", "effective_n", "weight", "hybrid",
                                    "support_weight", "support_hybrid", "hard")}
            rows.append(dict(quarter=str(t), state=state, history_from=str(t-24), history_to=str(t-13),
                             recent_from=str(t-12), recent_to=str(t-1), local_n=int(own.n),
                             local_events=int(own.defaults), recent_n=r, other_n=outside,
                             other_events=int(donors.defaults.sum()), variance_donors=int(donors.n.ge(20).sum()),
                             **fields, **outcome.drop(labels="source").to_dict()))
    return pd.DataFrame(rows)


def scores(part, basis):
    rate = (part.default_principal / part.known_principal if basis == "dollars_within"
            else part.defaults / part.n)
    result = pd.DataFrame({name: brier(rate, part[name]) for name in METHODS}, index=part.index)
    for ref in ("local", "pooled"):
        for name in ("hybrid", "hard", "support_hybrid"):
            result[f"{ref}_minus_{name}"] = result[ref] - result[name]
    return result


def metrics_for(part, sample, group):
    grid, draws = block_counts("2015-01", "2019-09")
    quarter = pd.PeriodIndex(part.quarter, freq="Q").asi8 - grid[0].ordinal
    for basis in ("equal_books", "dollars_within", "loan_weighted"):
        frame = scores(part, basis)
        weights = part.n.to_numpy() if basis == "loan_weighted" else np.ones(len(part))
        for name, loss in frame.items():
            estimate = np.average(loss, weights=weights) if len(loss) else np.nan
            lo = hi = np.nan
            n_draws = 0
            if (sample == "matched" and group == "all" and basis == "equal_books"
                    and name in ("local_minus_hybrid", "pooled_minus_hybrid") and len(part)):
                mass = draws @ np.bincount(quarter, minlength=len(grid))
                totals = draws @ np.bincount(quarter, weights=loss, minlength=len(grid))
                good = mass > 0
                lo, hi = np.quantile(totals[good] / mass[good], [.025, .975])
                n_draws = int(good.sum())
            yield dict(sample=sample, group=group, basis=basis, method=name, mean=estimate,
                       ci_low=lo, ci_high=hi, draws=n_draws, books=len(part), loans=part.n.sum())


def summarize(rows):
    metrics, choices, policies = [], [], []
    operational = rows.loc[(rows.other_n > 0) & (rows.n > 0)]
    for sample, part in (("matched", operational.loc[operational.local_n.gt(0)]),
                         ("operational", operational)):
        for group, sub in [("all", part), *part.groupby("quarter", sort=True)]:
            metrics.extend(metrics_for(sub, sample, group))
        for label, sub in (("local", part.loc[part.weight.gt(.5)]),
                           ("pooled", part.loc[part.weight.le(.5)])):
            gain = scores(sub, "equal_books").eval("pooled-local")
            choices.append(dict(sample=sample, choice=label, books=len(sub), loans=sub.n.sum(),
                                local_closer=gain.gt(1e-12).sum(), pooled_closer=gain.lt(-1e-12).sum(),
                                ties=gain.abs().le(1e-12).sum(), mean_local_gain=gain.mean(),
                                mean_weight=sub.weight.mean(), median_local_n=sub.local_n.median(),
                                median_recent_n=sub.recent_n.median()))
        for good, bad in ((.10, -.45), (.03, -.50)):
            threshold = good / (good-bad)
            payoff = good * part.known_principal + (bad-good) * part.default_principal
            unknown = part.principal - part.known_principal
            for name in METHODS:
                lend = part[name].lt(threshold)
                for ref in ("local", "pooled"):
                    base = part[ref].lt(threshold)
                    delta = lend.astype(int) - base.astype(int)
                    change = delta * payoff
                    low = np.minimum(delta * good * unknown, delta * bad * unknown)
                    high = np.maximum(delta * good * unknown, delta * bad * unknown)
                    policies.append(dict(sample=sample, good=good, bad=bad, cutoff=threshold,
                                    method=name, reference=ref, books=len(part), chosen=lend.sum(),
                                    new_lending=(delta > 0).sum(), new_declines=(delta < 0).sum(),
                                    absolute_positions=(part.issued*delta.abs()).sum(),
                                    absolute_principal=(part.principal*delta.abs()).sum(),
                                    known_delta=change.sum(), delta_lower=(change + low).sum(),
                                    delta_upper=(change + high).sum()))
    return pd.DataFrame(metrics), pd.DataFrame(choices), pd.DataFrame(policies)


def run(out, cache):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cells, audit = load_cohorts([fetch(source, cache) for source in SOURCES])
    rows = score_books(cells)
    metrics, choices, policies = summarize(rows)
    for name, table in [("episodes", rows), ("coverage", audit), ("metrics", metrics),
                        ("choices", choices), ("policy", policies)]:
        table.to_csv(out/f"local_trust_bank_{name}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)

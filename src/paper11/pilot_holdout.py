"""Re-run the locked pilot rule on the November 2026 Bondora workbook."""
import argparse
from collections import defaultdict
import hashlib
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .data import fetch_pinned
from .lender_pilot import after_signal, margin
from .pilot_rule import CAPACITY, TOL, predict

URL = ("https://sabanners001.blob.core.windows.net/statistics/public/loan_dataset_investor.xlsx"
       "?versionid=2026-11-04T11%3A36%3A30.9618009Z")
SHA256 = "463277de6f9c2aae2a726b8064bd8d36682222bc02424a30321c824fd2ef763f"
FILE = "bondora-20261104.xlsx"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
CASH = ["principal_paid_total", "interest_paid_total", "extra_interest_paid_total", "late_fee_paid_total"]
FIELDS = ["loan_issued_at", "country", "customer_risk_rating", "issued_amount",
          "initial_interest_rate", "initial_loan_duration", "has_default_within_12_months",
          "principal_balance", *CASH]
WINDOWS = {
    "primary": ("2024-06", "2024-09"),
    "seasoned": ("2020-07", "2022-09"),
}


def fetch_holdout(cache):
    return fetch_pinned(URL, SHA256, Path(cache) / FILE, headers={"x-ms-version": "2023-11-03"})


def read_positions(path):
    """Stream only needed cells. Excel omits empty cells, so bind by column address."""
    rows = []
    with ZipFile(path) as archive:
        strings_xml = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(node.itertext()) for node in strings_xml]
        with archive.open("xl/worksheets/sheet1.xml") as sheet:
            columns = {}
            row_tag, value_tag = NS + "row", NS + "v"
            for _, node in ET.iterparse(sheet, events=("end",)):
                if node.tag != row_tag:
                    continue
                header = node.get("r") == "1"
                values = [None] * len(FIELDS)
                for cell in node:
                    letter = cell.get("r").rstrip("0123456789")
                    if not header and letter not in columns:
                        continue
                    raw = cell.findtext(value_tag)
                    if raw is None:
                        continue
                    value = strings[int(raw)] if cell.get("t") == "s" else raw
                    if header and value in FIELDS:
                        columns[letter] = FIELDS.index(value)
                    elif not header:
                        values[columns[letter]] = value
                if header:
                    if len(columns) != len(FIELDS):
                        raise ValueError("missing required workbook headers")
                else:
                    rows.append(values)
                node.clear()
    return pd.DataFrame(rows, columns=FIELDS)


def order_positions(frame):
    loans = frame.copy()
    serial = pd.to_numeric(loans.loan_issued_at, errors="coerce")
    if serial.notna().all():
        dates = pd.to_datetime(serial, unit="D", origin="1899-12-30")
    else:
        dates = pd.to_datetime(loans.loan_issued_at, format="mixed", errors="raise")
    if dates.isna().any() or loans.country.isna().any():
        raise ValueError("missing origination time or country")
    loans["origin"] = dates.dt.to_period("M")
    loans["date"] = dates
    loans["grade"] = loans.customer_risk_rating.fillna("(unrated)")
    loans["principal"] = pd.to_numeric(loans.issued_amount, errors="raise")
    if not loans.principal.gt(0).all():
        raise ValueError("missing or nonpositive principal")
    for field in [*CASH, "principal_balance"]:
        loans[field] = pd.to_numeric(loans[field], errors="raise")
    loans["cash"] = loans[CASH].sum(axis=1, min_count=len(CASH)) - loans.principal
    flags = loans.has_default_within_12_months.astype("string").str.lower()
    if not flags.dropna().isin(["0", "1", "true", "false"]).all():
        raise ValueError("unexpected first-year event encoding")
    loans["event"] = flags.map({"0": 0., "1": 1., "true": 1., "false": 0.}).astype(float)
    tie_fields = ["country", "grade", "loan_issued_at", "issued_amount", "initial_interest_rate",
                  "initial_loan_duration"]
    tied = loans.duplicated(["country", "grade", "date"], keep=False)
    loans["order_key"] = ""
    loans.loc[tied, "order_key"] = [
        hashlib.sha256("\x1f".join(str(v) for v in row).encode()).hexdigest()
        for row in loans.loc[tied, tie_fields].itertuples(index=False, name=None)
    ]
    loans["residual_tie"] = loans.duplicated(["country", "grade", "date", "order_key"], keep=False)
    loans["source_order"] = np.arange(len(loans))
    loans["scenario"] = loans.principal * margin(loans.event)
    return loans.sort_values(["date", "order_key", "source_order"], kind="stable")


def monthly(loans):
    """One ordinary-history observation and one capped continuation portfolio per cell."""
    group = ["country", "grade", "origin"]
    labels = loans.groupby(group, sort=False).event.agg(n="count", d="sum")
    capped = loans.groupby(group, sort=False).head(CAPACITY)
    batches = capped.groupby(group, sort=False)
    fields = ["principal", "cash", "scenario", "principal_balance", "event"]
    totals = batches[fields].sum()
    complete = batches[fields].count().eq(batches.size(), axis="index")
    totals = totals.where(complete)
    totals["count"] = batches.size()
    pilot = capped.drop_duplicates(group).set_index(group)
    return labels, totals, pilot


def risk_pairs(labels, pilot_index):
    """A refresh for origin s may enter the training history only from month s+13."""
    available = defaultdict(list)
    estimates = {}
    for (country, grade), cell in labels.groupby(level=["country", "grade"], sort=True):
        counts = cell.droplevel(["country", "grade"])
        dates = pd.period_range(counts.index.min(), counts.index.max(), freq="M")
        counts = counts.reindex(dates, fill_value=0)
        matured = counts.rolling(12, min_periods=1).sum()
        initial = matured.shift(13)
        fresh = matured.shift(1).fillna(0)
        for date in initial.index[initial.n.ge(50)]:
            key = (country, grade, date)
            if key not in pilot_index:
                continue
            n0, d0 = initial.loc[date, ["n", "d"]]
            n1, d1 = fresh.loc[date, ["n", "d"]]
            q = (d0 + .5) / (n0 + 1)
            u = (d1 + .5) / (n1 + 1) if n1 else q
            estimates[key] = (q, u, int(n0), int(n1))
            available[date + 13].append((q, u, date.ordinal))
    return estimates, available


PANEL_COLUMNS = (
    "sample origin_month disclosure_month country grade q_initial q_fresh prior_n refresh_n "
    "public_pairs distinct_public_origin_months pilot_principal mean_prior_count mean_prior_exposure "
    "eligible baseline_selected selected strict_probability score exposure_only_net risk_only_net "
    "pilot_default baseline_lend informed_lend would_change_action action_changed future_count future_defaults "
    "future_principal future_cash pilot_cash net_cash pilot_scenario net_scenario "
    "pilot_balance future_balance pilot_tie"
).split()


def make_panel(loans, windows=WINDOWS):
    labels, totals, pilots = monthly(loans)
    estimates, releases = risk_pairs(labels, pilots.index)
    zero = {"count": 0, "principal": 0., "cash": 0., "scenario": 0., "principal_balance": 0., "event": 0.}
    portfolios = totals.to_dict("index")
    groups_by_date = defaultdict(list)
    for (country, grade, date), estimate in estimates.items():
        groups_by_date[date].append((country, grade, *estimate))
    history, rows = [], []
    samples = {date: name for name, (a, b) in windows.items()
               for date in pd.period_range(a, b, freq="M")}
    for date in sorted(set(samples) | set(releases)):
        history.extend(releases.get(date, ()))
        if date not in samples:
            continue
        old, updated, dates = zip(*history) if history else ((), (), ())
        for country, grade, q, u, n0, n1 in sorted(groups_by_date[date]):
            pilot = pilots.loc[(country, grade, date)]
            past = [portfolios.get((country, grade, date - lag), zero) for lag in range(12, 0, -1)]
            counts = [int(x["count"]) for x in past]
            amounts = [x["principal"] for x in past]
            forecast = predict(q, pilot.principal, counts, amounts, old, updated, dates)
            future = date + 13
            batch = portfolios.get((country, grade, future), zero)
            baseline = margin(u) > TOL
            after = margin(after_signal(u, pilot.event)) > TOL if pd.notna(pilot.event) else np.nan
            switch = int(after) - int(baseline) if pd.notna(after) else np.nan
            would_change = bool(switch) if pd.notna(switch) else np.nan
            action_changed = would_change if batch["count"] else False
            unchanged = batch["count"] == 0 or switch == 0
            cash_gain = 0. if unchanged else switch * batch["cash"]
            scenario_gain = 0. if unchanged else switch * batch["scenario"]
            rows.append(dict(sample=samples[date], origin_month=str(date), disclosure_month=str(future),
                             country=country, grade=grade, q_initial=q, q_fresh=u, prior_n=n0, refresh_n=n1,
                             public_pairs=len(history), distinct_public_origin_months=len(set(dates)),
                             pilot_principal=pilot.principal, mean_prior_count=np.mean(counts),
                             mean_prior_exposure=np.mean(amounts), eligible=forecast.eligible,
                             baseline_selected=forecast.baseline_selected, selected=forecast.selected,
                             strict_probability=forecast.strict_probability, score=forecast.net_money,
                             exposure_only_net=forecast.exposure_only_net, risk_only_net=forecast.risk_only_net,
                             pilot_default=pilot.event, baseline_lend=baseline, informed_lend=after,
                             would_change_action=would_change, action_changed=action_changed,
                             future_count=int(batch["count"]), future_defaults=batch["event"],
                             future_principal=batch["principal"], future_cash=batch["cash"],
                             pilot_cash=pilot.cash, net_cash=pilot.cash + cash_gain,
                             pilot_scenario=pilot.scenario, net_scenario=pilot.scenario + scenario_gain,
                             pilot_balance=pilot.principal_balance, future_balance=batch["principal_balance"],
                             pilot_tie=bool(pilot.residual_tie)))
    return pd.DataFrame(rows, columns=PANEL_COLUMNS).sort_values(["origin_month", "country", "grade"]).reset_index(drop=True)


def run(out, cache):
    path = fetch_holdout(cache)
    loans = order_positions(read_positions(path))
    panel = make_panel(loans)
    origin_groups = ["country", "grade", "origin"]
    all_counts = loans.groupby(origin_groups, sort=False).event.agg(["count", "size"])
    support = []
    for (country, grade), cell in all_counts.groupby(level=["country", "grade"], sort=True):
        history = cell.droplevel(["country", "grade"]).sort_index()
        counts = history["count"].reindex(pd.period_range(history.index.min(), history.index.max(), freq="M"), fill_value=0)
        prior = counts.rolling(12, min_periods=1).sum().shift(13).fillna(0)
        for name, (first, last) in WINDOWS.items():
            for date, item in history.loc[first:last].iterrows():
                support.append(dict(sample=name, origin_month=str(date), country=country, grade=grade,
                                    originated=int(item["size"]), prior_n=int(prior[date]),
                                    estimable=bool(prior[date] >= 50)))
    support = pd.DataFrame(support).sort_values(["origin_month", "country", "grade"])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    support.to_csv(out / "pilot_holdout_support.csv", index=False)
    panel.to_csv(out / "pilot_holdout_episodes.csv", index=False, float_format="%.12g")
    audit = []
    for sample, (first, last) in WINDOWS.items():
        a, b = pd.Period(first, "M"), pd.Period(last, "M")
        local = loans[loans.origin.between(a, b)]
        future = loans[loans.origin.between(a + 13, b + 13)]
        p = panel[panel["sample"].eq(sample)]
        audit.append(dict(sample=sample, source_loans=len(loans), source_min_issue=loans.date.min(),
                          source_max_issue=loans.date.max(), origin_start=a, origin_end=b,
                          window_issued=len(local), window_missing_labels=local.event.isna().sum(),
                          window_missing_cash=local.cash.isna().sum(), followup_issued=len(future),
                          followup_missing_labels=future.event.isna().sum(),
                          followup_missing_cash=future.cash.isna().sum(), opportunities=len(p),
                          positions_in_continuations=p.future_count.sum(), residual_pilot_ties=p.pilot_tie.sum(),
                          missing_net_cash=p.net_cash.isna().sum(), missing_net_scenario=p.net_scenario.isna().sum()))
    pd.DataFrame(audit).to_csv(out / "pilot_holdout_cohort.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    run(args.out, args.cache)

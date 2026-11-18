"""Chronological single-pilot decisions on Bondora's funded consumer loans."""
import argparse
from hashlib import file_digest
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from zlib import error as DecompressionError

import numpy as np
import pandas as pd

from .data import fetch_pinned
from .pilot_replay import clustered_interval

URL = ("https://api.kaggle.com/v1/datasets/download/sid321axn/"
       "bondora-peer-to-peer-lending-loan-data?datasetVersionNumber=1")
SHA256 = "e43140cfad03b2d498f11c9bcee32502d3e420a7193df755f4b55f0e9cfbeac9"
LATER_URL = ("https://api.kaggle.com/v1/datasets/download/marcobeyer/"
             "bondora-loans?datasetVersionNumber=24")
LATER_SHA256 = "fb815086a85881d14b58634664fd51a502d0adfde18b3248c389814cbc6ee25b"
LATER_SNAPSHOT = pd.Timestamp("2024-05-24")
SNAPSHOT = pd.Timestamp("2021-07-20")
FIRST = pd.Period("2013-01", freq="M")
HORIZON = 25
STRENGTH = 20
REPAID = .10
DEFAULT = -.45
TOL = 1e-12


def _same_csv(archive_path, member, size, sha):
    """A publisher may regenerate a ZIP around exactly the same published CSV."""
    try:
        with ZipFile(archive_path) as zip_file:
            entries = zip_file.infolist()
            if len(entries) != 1 or entries[0].filename != member or entries[0].file_size != size:
                return False
            with zip_file.open(entries[0]) as raw:
                return file_digest(raw, "sha256").hexdigest() == sha
    except (BadZipFile, DecompressionError, EOFError, OSError, RuntimeError):
        return False


def _fetch_tape(cache, filename, url, sha, member, size, member_sha):
    alternate = url.replace("https://api.kaggle.com/", "https://www.kaggle.com/api/")
    return fetch_pinned(url, sha, Path(cache) / filename, alternates=(alternate,),
                        equivalent=lambda path: _same_csv(path, member, size, member_sha))


def fetch_bondora(cache):
    return _fetch_tape(cache, "bondora-v1.zip", URL, SHA256, "LoanData_Bondora.csv", 149586306,
                       "465abbefd71dc58afa5f293fdbff5a0300aa6cd43c6bd5736edad4c5c31fa460")


def fetch_bondora_followup(cache):
    return _fetch_tape(cache, "bondora-24-exact.zip", LATER_URL, LATER_SHA256, "LoanData.csv", 332297270,
                       "74741d5cd7b4ddc9711632189a9f47d4c48b5b7c230ea74c5015adf49039e40b")


def prepare(path):
    cols = ["ReportAsOfEOD", "LoanId", "LoanNumber", "LoanDate", "MaturityDate_Original", "DefaultDate",
            "Country", "NewCreditCustomer", "Amount", "PrincipalPaymentsMade", "InterestAndPenaltyPaymentsMade"]
    with ZipFile(path) as file, file.open("LoanData_Bondora.csv") as stream:
        a = pd.read_csv(stream, usecols=cols)
    if not a.ReportAsOfEOD.eq(str(SNAPSHOT.date())).all() or not a.LoanNumber.is_unique:
        raise ValueError("unexpected Bondora snapshot or duplicate loan")
    if a.drop(columns=["DefaultDate","MaturityDate_Original"]).isna().any().any() or not a.Amount.gt(0).all():
        raise ValueError("missing source fields, payments or principal")
    a["date"] = pd.to_datetime(a.LoanDate)
    default = pd.to_datetime(a.DefaultDate)
    if (default < a.date).any() or (default > SNAPSHOT).any():
        raise ValueError("invalid recorded default date")
    a["event"] = default.notna() & (default <= a.date + pd.DateOffset(years=1))
    a["cash"] = a.PrincipalPaymentsMade + a.InterestAndPenaltyPaymentsMade - a.Amount
    a["cash_unit"] = a.cash / a.Amount
    a["past_original_maturity"] = pd.to_datetime(a.MaturityDate_Original).le(SNAPSHOT)
    a["month"] = a.date.dt.to_period("M")
    a["customer"] = np.where(a.NewCreditCustomer, "new", "returning")
    return a.sort_values(["date","LoanNumber"])


def later_receipts(loans, path):
    """Attach the later ledger only after making the original decisions."""
    keys = ["LoanId", "LoanNumber"]
    cols = keys + ["ReportAsOfEOD", "LoanDate", "Amount", "Status", "PrincipalBalance", "PrincipalWriteOffs",
                   "PrincipalPaymentsMade", "InterestAndPenaltyPaymentsMade"]
    with ZipFile(path) as archive, archive.open("LoanData.csv") as stream:
        later = pd.read_csv(stream, usecols=cols)
    if not later.ReportAsOfEOD.eq(str(LATER_SNAPSHOT.date())).all() or later.duplicated(keys).any():
        raise ValueError("unexpected later report or duplicate key")
    if later[["PrincipalPaymentsMade","InterestAndPenaltyPaymentsMade","PrincipalBalance"]].isna().any().any():
        raise ValueError("incomplete cash collection data")
    later["later_cash"] = later.PrincipalPaymentsMade + later.InterestAndPenaltyPaymentsMade - later.Amount
    later["later_principal_balance"] = later.PrincipalBalance
    later["later_status"] = later.Status
    later["later_principal_paid"] = later.PrincipalPaymentsMade
    later["later_income_paid"] = later.InterestAndPenaltyPaymentsMade
    later["later_writeoffs"] = later.PrincipalWriteOffs
    fields = ["later_cash","later_principal_balance","later_status","later_principal_paid",
              "later_income_paid","later_writeoffs"]
    matched = loans.merge(later[keys + ["LoanDate","Amount"] + fields], on=keys+["LoanDate","Amount"],
                          how="left", sort=False, validate="one_to_one")
    return matched


def rescore_later(loans, panel):
    """Use original positions and actions, requiring full linkage of affected loans."""
    batches = dict(tuple(loans.groupby(["Country","customer","month"], sort=False)))
    empty = loans.iloc[:0]
    rows = []
    for ep in panel.itertuples():
        group = (ep.country,ep.customer)
        pilot = batches[(*group,pd.Period(ep.pilot_month,"M"))].iloc[0]
        batch = batches.get((*group,pd.Period(ep.future_month,"M")),empty).iloc[:HORIZON]
        switch = int(ep.pilot_lend)-int(ep.baseline_lend)
        complete = bool(pd.notna(pilot.later_cash) and batch.later_cash.notna().all())
        # For non-switching portfolios the matched gross contrast is exactly zero,
        # even if an unrelated continuation loan lacks a later record.
        enough = pd.notna(pilot.later_cash) and (complete or switch == 0)
        net_pilot, net_gross, bounded = np.nan, np.nan, np.nan
        euro_pilot, euro_gross = np.nan, np.nan
        if enough:
            euro_pilot = pilot.later_cash
            net_pilot = euro_pilot/pilot.Amount
            net_gross = switch*(batch.later_cash/batch.Amount).sum()
            euro_gross = switch*batch.later_cash.sum()
            bounded = net_pilot+net_gross+min(0,switch)*(batch.later_principal_balance/batch.Amount).sum()
        rows.append(dict(country=ep.country,customer=ep.customer,pilot_month=ep.pilot_month,
                         future_month=ep.future_month,primary=ep.primary,eligible=ep.eligible,selected=ep.selected,
                         action_changed=ep.action_changed,portfolio_n=ep.future_n,
                         matched_continuations=int(batch.later_cash.notna().sum()),matched_pilot=pd.notna(pilot.later_cash),
                         pilot_status=pilot.later_status,complete=complete,scorable=bool(enough),
                         pilot_amount=pilot.Amount,pilot_principal_received=pilot.later_principal_paid,
                         pilot_interest_penalties_received=pilot.later_income_paid,pilot_remaining=pilot.later_principal_balance,
                         pilot_principal_written_off=pilot.later_writeoffs,
                         future_amount=batch.Amount.sum(),future_received=(batch.Amount+batch.later_cash).sum() if complete else np.nan,
                         future_remaining=batch.later_principal_balance.sum() if complete else np.nan,
                         future_repaid=int((batch.later_status=="Repaid").sum()),
                         pilot_margin=net_pilot,gross=net_gross,net=net_pilot+net_gross,
                         euro_pilot=euro_pilot,euro_gross=euro_gross,euro_net=euro_pilot+euro_gross,
                         cash_covered=bool(enough and switch and net_pilot < -TOL and net_pilot+net_gross > TOL),
                         euro_covered=bool(enough and switch and euro_pilot < -TOL and euro_pilot+euro_gross > TOL),
                         net_if_declined_portfolio_recovers_principal=bounded))
    return pd.DataFrame(rows)


def margin(q):
    return REPAID + (DEFAULT - REPAID) * q


def after_signal(q, outcome):
    return (STRENGTH*q + outcome) / (STRENGTH + 1)


def forecast(q):
    direct = margin(q)
    gross = HORIZON * ((1-q)*max(0., margin(after_signal(q,0))) +
                       q*max(0., margin(after_signal(q,1))) - max(0., direct))
    return direct, max(0., gross)


def windows(history, first, last):
    window = history.loc[first:last]
    return int(window["sum"].sum()), int(window["size"].sum())


def score(pilot, batch, initial, fresh):
    predicted, value = forecast(initial)
    event = int(pilot.event)
    fresh_action = margin(fresh) > TOL
    updated_q = after_signal(fresh, event)
    informed_action = margin(updated_q) > TOL
    switch = int(informed_action) - int(fresh_action)
    scenario_pilot = margin(event)
    scenario_batch = float(margin(batch.event.astype(float)).sum())
    cash_batch, euro_batch = batch.cash_unit.sum(), batch.cash.sum()
    row = dict(q_initial=initial, q_fresh=fresh, q_with_pilot=updated_q, predicted_immediate=predicted,
               predicted_gross=value, predicted_net=predicted+value, eligible=predicted < -TOL,
               selected=predicted < -TOL and predicted+value > TOL, pilot_default_12m=event,
               baseline_lend=fresh_action, pilot_lend=informed_action, action_changed=bool(switch),
               future_n=len(batch), future_events=int(batch.event.sum()), forced_pilot=scenario_pilot,
               forced_gross=switch*scenario_batch, forced_net=scenario_pilot+switch*scenario_batch,
               cash_pilot=pilot.cash_unit, cash_gross=switch*cash_batch, cash_net=pilot.cash_unit+switch*cash_batch,
               euro_pilot=pilot.cash, euro_gross=switch*euro_batch, euro_net=pilot.cash+switch*euro_batch,
               past_original_maturity=bool(pilot.past_original_maturity),
               future_past_original_maturity=int(batch.past_original_maturity.sum()))
    for family in ["forced", "cash", "euro"]:
        row[family+"_covered"] = (bool(switch) and row[family+"_pilot"] < -TOL
                                  and row[family+"_net"] > TOL)
    return row


def episodes(loans):
    latest_future = SNAPSHOT.to_period("M") - 13
    primary_future = SNAPSHOT.to_period("M") - 37
    rows = []
    for (country, customer), data in loans.groupby(["Country","customer"], sort=True):
        counts = data.groupby("month").event.agg(["sum","size"]).sort_index()
        batches = dict(tuple(data.groupby("month", sort=False)))
        empty = data.iloc[:0]
        for s in pd.period_range(FIRST, latest_future-13, freq="M"):
            if s not in batches:  # No candidate arrived in this segment that month.
                continue
            past_events, past_n = windows(counts,s-24,s-13)
            if past_n < 50:
                continue
            initial = (past_events+.5)/(past_n+1)
            future = s + 13
            fresh_events, fresh_n = windows(counts,s-12,s-1)
            fresh = (fresh_events+.5)/(fresh_n+1) if fresh_n else initial
            pilot = batches[s].iloc[0]
            next_batch = batches.get(future,empty).iloc[:HORIZON]
            row = score(pilot,next_batch,initial,fresh)
            rows.append(dict(country=country,customer=customer,pilot_month=str(s),pilot_quarter=str(s.asfreq("Q")),
                             future_month=str(future),primary=future <= primary_future,prior_n=past_n,
                             fresh_n=fresh_n,prior_strength=STRENGTH,repay_margin=REPAID,default_margin=DEFAULT,
                             planned_followups=HORIZON,**row))
    return pd.DataFrame(rows).sort_values(["pilot_month","country","customer"]).reset_index(drop=True)


def summary(panel):
    rows = []
    for label, population in [("36m",panel[panel.primary]), ("12m",panel)]:
        quarter_grid = pd.period_range(population.pilot_quarter.min(), population.pilot_quarter.max(), freq="Q").astype(str)
        cases = population[population.eligible]
        for name in ("selected", "forced"):
            run = cases.selected if name == "selected" else pd.Series(True,index=cases.index)
            acted = cases[run]
            for metric in ("forced", "cash", "euro"):
                outcomes = cases[metric+"_net"] * run
                quarter = outcomes.groupby(cases.pilot_quarter).agg(["sum","size"]).reindex(quarter_grid,fill_value=0)
                low,high = clustered_interval(quarter["sum"].to_numpy(),quarter["size"].to_numpy(),4)
                rows.append(dict(seasoning=label,strategy=name,valuation=metric,opportunities=len(population),
                                 eligible=len(cases),issued=len(acted),changed=int(acted.action_changed.sum()),
                                 loss_pilots=int((acted[metric+"_pilot"] < -TOL).sum()),
                                 changed_and_covered=int(acted[metric+"_covered"].sum()),
                                 mean_pilot=(cases[metric+"_pilot"]*run).mean(),
                                 mean_gross=(cases[metric+"_gross"]*run).mean(),mean_net=outcomes.mean(),
                                 net_ci_low=low,net_ci_high=high))
    return pd.DataFrame(rows)


def run(out,cache):
    data = prepare(fetch_bondora(cache))
    panel = episodes(data)
    later = later_receipts(data,fetch_bondora_followup(cache))
    followup = rescore_later(later,panel)
    out.mkdir(parents=True,exist_ok=True)
    counts = dict(source_loans=len(data),countries=data.Country.nunique(),min_date=data.date.min().date(),
                  max_date=data.date.max().date(),snapshot=SNAPSHOT.date(),later_snapshot=LATER_SNAPSHOT.date(),
                  reidentified_loans=int(later.later_cash.notna().sum()),
                  candidate_episodes=len(panel),primary_episodes=int(panel.primary.sum()))
    for tag, frame in [("cohort",pd.DataFrame([counts])),("episodes",panel),("summary",summary(panel)),
                       ("followup",followup)]:
        frame.to_csv(out / f"lender_pilot_{tag}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=Path("results"))
    parser.add_argument("--cache",type=Path,default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out,args.cache)

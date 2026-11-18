"""Cross-lender application of the precommitted pilot rule on the Prosper 2014 tape."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .data import fetch
from .lender_pilot import margin
from .pilot_holdout import make_panel
from .pilot_replay import STATE_REGION

WINDOW = {"prosper": ("2008-01", "2012-01")}
PAYMENTS = ["LP_CustomerPayments", "LP_GrossPrincipalLoss", "LP_NetPrincipalLoss", "LP_NonPrincipalRecoverypayments"]
FIELDS = ["LoanKey", "LoanNumber", "LoanOriginationDate", "LoanStatus", "LoanMonthsSinceOrigination",
          "LoanFirstDefaultedCycleNumber", "LoanOriginalAmount", "TotalProsperLoans", "BorrowerState", *PAYMENTS]


def prepare(source):
    raw = source.copy()
    valid = raw.LoanStatus.ne("Cancelled") & raw.LoanOriginalAmount.gt(0) & raw.LoanOriginationDate.notna()
    raw = raw.loc[valid].copy()
    if raw.LoanKey.isna().any() or raw.LoanNumber.isna().any():
        raise ValueError("a funded listing is missing its loan key or sequence number")
    repeated = raw[raw.duplicated("LoanKey", keep=False)].groupby("LoanKey")
    if repeated[FIELDS[1:]].nunique(dropna=False).gt(1).any().any():
        raise ValueError("duplicate funded loan with inconsistent cash, event or origination fields")
    raw["source_order"] = np.arange(len(raw))
    loans = raw.sort_values(["LoanOriginationDate", "LoanNumber", "source_order"]).drop_duplicates("LoanKey").copy()
    loans["date"] = pd.to_datetime(loans.LoanOriginationDate)
    loans["origin"] = loans.date.dt.to_period("M")
    loans["country"] = loans.BorrowerState.map(STATE_REGION).fillna("(unknown region)")
    loans["grade"] = np.where(loans.TotalProsperLoans.fillna(0).gt(0), "returning", "new")
    cycle = loans.LoanFirstDefaultedCycleNumber
    measured = cycle.between(1, 12)
    terminal = loans.LoanStatus.isin(["Chargedoff", "Defaulted"])
    unknown = terminal & (cycle.isna() | cycle.le(0))
    immature = loans.LoanMonthsSinceOrigination.lt(12) | loans.LoanMonthsSinceOrigination.isna()
    loans["event"] = measured.astype(float).mask(unknown | (immature & ~measured))
    loans["principal"] = loans.LoanOriginalAmount
    loans["cash"] = (loans.LP_CustomerPayments + loans.LP_GrossPrincipalLoss - loans.LP_NetPrincipalLoss
                     + loans.LP_NonPrincipalRecoverypayments - loans.principal)
    loans["scenario"] = loans.principal * margin(loans.event)
    # A principal outstanding field at the common snapshot is unavailable here.
    loans["principal_balance"] = np.nan
    loans["residual_tie"] = loans.duplicated(["date", "LoanNumber"], keep=False)
    audit = dict(source_rows=len(source), valid_funded_listings=len(raw), unique_funded_loans=len(loans),
                 duplicate_listing_rows=len(raw) - len(loans), repeated_loan_keys=len(repeated),
                 unresolved_reported_defaults=int(unknown.sum()), missing_cash_source=int(loans.cash.isna().sum()))
    return loans, audit


def run(out, cache):
    loans, audit = prepare(pd.read_csv(fetch("prosper", cache), usecols=FIELDS))
    panel = make_panel(loans, WINDOW).rename(columns={"country": "region", "grade": "customer"})
    panel = panel.drop(columns=["pilot_balance", "future_balance"])
    start, end = [pd.Period(s, "M") for s in WINDOW["prosper"]]
    origin = loans[loans.origin.between(start, end)]
    future = loans[loans.origin.between(start + 13, end + 13)]
    audit.update(sample="prosper", origin_start=start, origin_end=end, opportunities=len(panel),
                 nonempty_cells=origin.groupby(["country", "grade", "origin"]).ngroups,
                 window_issued=len(origin), window_missing_labels=origin.event.isna().sum(),
                 window_missing_cash=origin.cash.isna().sum(), followup_issued=len(future),
                 followup_missing_labels=future.event.isna().sum(), followup_missing_cash=future.cash.isna().sum(),
                 positions_in_continuations=panel.future_count.sum(), missing_pilot_signal=panel.pilot_default.isna().sum(),
                 missing_net_cash=panel.net_cash.isna().sum(), missing_net_scenario=panel.net_scenario.isna().sum())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out / "pilot_prosper_episodes.csv", index=False, float_format="%.12g")
    pd.DataFrame([audit]).to_csv(out / "pilot_prosper_cohort.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    run(args.out, args.cache)

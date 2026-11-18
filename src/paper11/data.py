"""Pinned public inputs and historical-policy emulation."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.model_selection import KFold

SOURCES = {
    "philippines_offers": (
        "https://raw.githubusercontent.com/bfava/ensembleHTE/"
        "1a64d156edf7aa8c97bc9e928b4cda6e706cc9de/data-raw/microcredit.csv",
        "7ca62db2649bf59450cd58cc8be274201eca26096a51b4259b88f54209229054",
    ),
    "taiwan": ("https://archive.ics.uci.edu/static/public/350/data.csv",
               "45bcf4df62ff2e237a74eb155cabfb4bbbc171219a0637daef44fdad07503dd0"),
    "prosper": ("https://s3.amazonaws.com/udacity-hosted-downloads/ud651/prosperLoanData.csv",
                "71c1c1931f65bc4d2e3a8f3603d865e074e327b2271590f3a06829197b9cce0f"),
}
PROSPER_FEATURES = [
    "CreditScoreRangeLower", "StatedMonthlyIncome", "InquiriesLast6Months",
    "CurrentDelinquencies", "DelinquenciesLast7Years", "DebtToIncomeRatio",
    "AvailableBankcardCredit", "BankcardUtilization", "OpenCreditLines",
    "TotalCreditLinespast7years", "AmountDelinquent", "EmploymentStatusDuration",
    "TradesNeverDelinquent (percentage)",
]
TAIWAN_FEATURES = ["X1", *(f"X{i}" for i in range(6, 24))]
# All date intervals are closed on the left and open on the right.
PERIODS = [("2005-01-01", "2008-01-01"), ("2009-01-01", "2010-01-01"),
           ("2011-01-01", "2011-07-01"), ("2012-07-01", "2013-03-01")]


def checksum(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(name, cache):
    url, expected = SOURCES[name]
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (name + ".csv")
    if path.exists() and checksum(path) == expected:
        return path
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as f:
        tmp = Path(f.name)
    try:
        request = Request(url, headers={"User-Agent": "Paper11-academic-replication/1.0"})
        with urlopen(request, timeout=120) as source, tmp.open("wb") as sink:
            shutil.copyfileobj(source, sink)
        if checksum(tmp) != expected:
            raise ValueError(f"{name} source bytes differ from the published fingerprint")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


@dataclass
class Population:
    X: np.ndarray
    y: np.ndarray
    propensity: np.ndarray
    accepted: np.ndarray
    splits: list
    features: list
    audit: dict


def first_prosper_loans(path):
    """One funded loan per member, with a usable recorded default horizon."""
    cols = PROSPER_FEATURES + ["MemberKey", "LoanKey", "LoanStatus", "LoanOriginationDate",
                               "LoanFirstDefaultedCycleNumber", "LoanMonthsSinceOrigination"]
    df = pd.read_csv(path, usecols=cols)
    audit = {"source_rows": len(df)}
    df = df.loc[df.LoanStatus != "Cancelled"].dropna(subset=["MemberKey", "LoanOriginationDate"])
    df = df.sort_values(["LoanOriginationDate", "LoanKey"], kind="stable").drop_duplicates("MemberKey")
    audit["first_issued_per_member"] = len(df)
    # A reported default without its cycle cannot be timed against a 12-cycle horizon.
    terminal = df.LoanStatus.isin(["Defaulted", "Chargedoff"])
    cycle = df.LoanFirstDefaultedCycleNumber
    unknown = terminal & (cycle.isna() | cycle.lt(1))
    audit["missing_default_cycle_first_loans"] = int((terminal & cycle.isna()).sum())
    audit["nonpositive_default_cycle_first_loans"] = int((terminal & cycle.lt(1)).sum())
    audit["unresolved_default_cycle_first_loans"] = int(unknown.sum())
    df = df.loc[~unknown].reset_index(drop=True)
    return df, audit


def prosper_approval_probability(df):
    bureau = (df.CreditScoreRangeLower.fillna(640) - 640).clip(-180, 160) / 50
    risk = .55 * df.CurrentDelinquencies.fillna(0).clip(0, 5)
    return .05 + .90 * expit(.25 + .85 * bureau - risk)


def load_population(name, cache, seed=1011):
    if name not in ("taiwan", "prosper"):
        raise ValueError(f"Unknown masked borrower cohort: {name}")
    path = fetch(name, cache)
    rng = np.random.default_rng(seed)
    if name == "taiwan":
        df = pd.read_csv(path)
        assert len(df) == df.ID.nunique() == 30000 and df.Y.sum() == 6636
        # At a September-end renewal decision, these six months of history exist.
        features = TAIWAN_FEATURES
        risk = .95 * df.X6.clip(0, 4) + .24 * df.X7.clip(0, 3)
        wealth = .42 * np.log1p(df.X1 / 50000)
        propensity = .05 + .90 * expit(.55 + wealth - risk)
        y = df.Y.to_numpy(dtype=int)
        splits = []
        for others, test in KFold(4, shuffle=True, random_state=seed).split(df):
            fit, stop, val = np.split(rng.permutation(others), [13500, 16500])
            splits.append((fit, stop, val, test))
        audit = {"source_rows": len(df), "population_rows": len(df), "defaults": int(y.sum())}
    else:
        df, audit = first_prosper_loans(path)
        date = pd.to_datetime(df.LoanOriginationDate)
        periods = [((date >= start) & (date < stop)).to_numpy() for start, stop in PERIODS]
        df = df.loc[np.logical_or.reduce(periods)].reset_index(drop=True)
        date = pd.to_datetime(df.LoanOriginationDate)
        splits = [tuple(np.flatnonzero((date >= start) & (date < stop)) for start, stop in PERIODS)]
        features = PROSPER_FEATURES
        y = df.LoanFirstDefaultedCycleNumber.between(1, 12).to_numpy(dtype=int)
        propensity = prosper_approval_probability(df)
        audit.update(population_rows=len(df), defaults=int(y.sum()), unique_borrowers=df.MemberKey.nunique())
    p = propensity.to_numpy(dtype=float)
    accepted = np.random.default_rng(seed + 1).random(len(df)) < p
    return Population(df[features].to_numpy(dtype=float), y, p, accepted, splits, features, audit)

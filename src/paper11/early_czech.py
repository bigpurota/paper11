"""Reconstruct first instalments and one-year payment shortfalls in the PKDD'99 bank ledger."""
import argparse
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .data import fetch_pinned
from .early_warning import curve_forecast, payment_forecast

ARCHIVE = "https://codeload.github.com/jlacko/berka-dataset/zip/77e9972a1ead107e5f42a91dd989d587bff055a4"
FINGERPRINT = "f0e784e20a9b242f6c1a010080fb1315a3968cf7266945335c836c94326286eb"
AS_OF = pd.Period("1998-12", freq="M")
TEST_MONTHS = pd.period_range("1996-01", "1997-12", freq="M")


def fetch_archive(cache):
    return fetch_pinned(ARCHIVE, FINGERPRINT, Path(cache) / "berka-pkdd99.zip")


def load_ledger(path):
    with ZipFile(path) as archive:
        def read(name, fields):
            member, = [part for part in archive.namelist() if part.endswith("/" + name + ".asc")]
            with archive.open(member) as file:
                return pd.read_csv(file, sep=";", encoding="cp1250", usecols=fields)

        loans = read("loan", ["loan_id", "account_id", "date", "amount", "duration", "payments"])
        accounts = read("account", ["account_id", "district_id"])
        districts = read("district", ["A1", "A3"]).rename(columns={"A1": "district_id", "A3": "region"})
        tx = read("trans", ["trans_id", "account_id", "date", "type", "k_symbol", "amount", "balance"])
    if not tx.trans_id.is_unique:
        raise ValueError("transaction identifier is not unique")
    loans = loans.merge(accounts, on="account_id", validate="one_to_one", how="left")
    loans = loans.merge(districts, on="district_id", validate="many_to_one", how="left")
    if (not loans.loan_id.is_unique or loans.region.isna().any() or loans.payments.le(0).any()
            or loans.amount.le(0).any() or loans.duration.lt(12).any()):
        raise ValueError("invalid origination or geography in the bank ledger")
    tagged = tx.loc[tx.k_symbol.eq("UVER")].copy()
    if not tagged.type.eq("VYDAJ").all() or tagged.amount.lt(0).any():
        raise ValueError("unexpected sign or type on a tagged loan payment")
    loans["origin"] = pd.to_datetime(loans.date.astype(str), format="%y%m%d")
    tagged["paid_on"] = pd.to_datetime(tagged.date.astype(str), format="%y%m%d")
    tagged = tagged.rename(columns={"amount": "paid"})
    return loans, tagged, len(tx)


def label_loans(loans, tagged, as_of=AS_OF):
    """Ages are completed calendar months following origination; include later origin-month cash."""
    loans = loans.set_index("account_id").copy()
    loans["month"] = loans.origin.dt.to_period("M")
    tx = tagged.join(loans[["origin", "month"]], on="account_id", how="inner")
    age = tx.paid_on.dt.to_period("M").astype("int64") - tx.month.astype("int64")
    eligible = tx.paid_on.gt(tx.origin) & age.between(0, 12) & tx.paid_on.dt.to_period("M").le(as_of)
    payments = tx.loc[eligible].copy()
    payments["age"] = age[eligible]
    by_age = payments.groupby(["account_id", "age"]).paid.sum().unstack(fill_value=0)
    by_age = by_age.reindex(index=loans.index, columns=range(13), fill_value=0.)
    cumulative = by_age.cumsum(axis=1)
    instalment = loans.payments
    loans["e3"] = cumulative[3].le(2 * instalment + .005)
    thresholds = np.outer(instalment, np.arange(2, 13) - 2)
    shortfalls = cumulative.loc[:, 2:12].to_numpy() <= thresholds + .005
    loans["short_by_month3"] = np.any(shortfalls[:, :2], axis=1)
    loans["e6"] = np.any(shortfalls[:, :5], axis=1)
    loans["y12"] = np.any(shortfalls, axis=1)
    for field, months in (("e3", 3), ("short_by_month3", 3), ("e6", 6), ("y12", 12)):
        loans[field] = loans[field].astype("Int64").where(loans.month.add(months).le(as_of))
    early_cash = payments.loc[payments.age.le(3)]
    counts = early_cash.groupby("account_id").size()
    negative = early_cash.loc[early_cash.balance.lt(0)].groupby("account_id").size()
    loans["early_tagged_debits"] = counts.reindex(loans.index, fill_value=0)
    loans["early_overdraft_debits"] = negative.reindex(loans.index, fill_value=0)
    return loans.reset_index()


def episode_counts(loans, dates=TEST_MONTHS):
    """Build risk inputs strictly from vintages that had completed the stated landmark by issue."""
    records = []
    for t in dates:
        mature = loans.loc[loans.month.between(t-24, t-13)]
        recent6 = loans.loc[loans.month.between(t-12, t-7)]
        recent3 = loans.loc[loans.month.between(t-9, t-4)]
        target = loans.loc[loans.month.eq(t)]
        if (mature[["e6", "e3", "y12"]].isna().any().any() or recent6.e6.isna().any()
                or recent3.e3.isna().any() or target.y12.isna().any()):
            raise ValueError("landmark or outcome incomplete in a scheduled observation window")
        for region, book in target.groupby("region", sort=True):
            local = mature.loc[mature.region.eq(region)]
            donor = mature.loc[mature.region.ne(region)]
            young6 = recent6.loc[recent6.region.eq(region)]
            young3 = recent3.loc[recent3.region.eq(region)]
            records.append(dict(month=str(t), region=region, old_start=str(t-24), old_end=str(t-13),
                                early6_start=str(t-12), early6_end=str(t-7),
                                early3_start=str(t-9), early3_end=str(t-4),
                                old_n=len(local), old_y=int(local.y12.sum()), old_e6=int(local.e6.sum()),
                                old_e3=int(local.e3.sum()), old_e3_y=int((local.e3 * local.y12).sum()),
                                other_n=len(donor), other_y=int(donor.y12.sum()),
                                bank_n=len(mature), bank_y=int(mature.y12.sum()), bank_e6=int(mature.e6.sum()),
                                young6_n=len(young6), young6_e=int(young6.e6.sum()),
                                young3_n=len(young3), young3_e=int(young3.e3.sum()), loans=len(book),
                                events=int(book.y12.sum()), principal=float(book.amount.sum()),
                                event_principal=float(book.amount.mul(book.y12).sum())))
    return pd.DataFrame.from_records(records)


def forecast(episodes):
    rows = episodes.loc[episodes.old_n.gt(0) & episodes.other_n.gt(0)].copy()
    output = []
    for r in rows.itertuples():
        local = (r.old_y + .5) / (r.old_n + 1)
        pooled = (r.other_y + .5) / (r.other_n + 1)
        six = curve_forecast(local, r.old_e6, r.old_y, r.bank_e6, r.bank_y, r.young6_e, r.young6_n)
        three = payment_forecast(local, r.old_n, r.old_y, r.old_e3, r.old_e3_y, r.young3_e, r.young3_n)
        output.append(dict(local=local, other=pooled, six=six.risk, three=three,
                           capture=six.capture, source=six.source))
    return rows.join(pd.DataFrame(output, index=rows.index))


def block_intervals(months, paired, dates=TEST_MONTHS):
    """Sample four consecutive months circularly; align all regions and contrasts."""
    m = pd.PeriodIndex(months, freq="M").asi8 - dates[0].ordinal
    length = len(dates)
    rng = np.random.default_rng(110618)
    starts = rng.integers(length, size=(2500, (length+3)//4))
    draws = ((starts[:, :, None] + np.arange(4)) % length).reshape(2500, -1)[:, :length]
    counts = np.bincount(m, minlength=length)[draws].sum(axis=1)
    intervals = {}
    for key, values in paired.items():
        totals = np.bincount(m, weights=values, minlength=length)[draws].sum(axis=1)
        intervals[key] = np.quantile(totals[counts > 0] / counts[counts > 0], [.025, .975])
    return intervals


def summaries(book):
    rate = book.events / book.loans
    lower = book[["local", "other"]].min(axis=1)
    below = rate.lt(lower - 1e-12)
    methods = ("local", "other", "six", "three")
    loss = {name: book[name]**2 + rate*(1 - 2*book[name]) for name in methods}
    paired = {ref: loss[ref] - loss["six"] for ref in ("local", "other")}
    ci = block_intervals(book.month, paired)
    metrics, choices, policies = [], [], []
    for name in methods:
        metrics.append(dict(method=name, books=len(book), loans=int(book.loans.sum()),
                            brier=loss[name].mean(), mean_forecast=book[name].mean(),
                            mean_book_event=rate.mean()))
        for ref in ("local", "other"):
            rec = metrics[-1]
            rec[ref + "_gain"] = (loss[ref] - loss[name]).mean()
            lo, hi = ci[ref] if name == "six" else (np.nan, np.nan)
            rec[ref + "_ci_low"], rec[ref + "_ci_high"] = lo, hi
        if name in ("six", "three"):
            flag = book[name].lt(lower - 1e-12)
            choices.append(dict(method=name, books=len(book), flags=int(flag.sum()),
                                actual_below=int(below.sum()), true_flags=int((flag & below).sum()),
                                false_flags=int((flag & ~below).sum()), missed=int((~flag & below).sum()),
                                true_unflagged=int((~flag & ~below).sum())))
        for good, bad in ((.10, -.45), (.03, -.50)):
            cutoff = good / (good - bad)
            lend = book[name].lt(cutoff)
            payoff = good*book.principal + (bad-good)*book.event_principal
            for ref in ("local", "other"):
                original = book[ref].lt(cutoff)
                delta = lend.astype(int) - original.astype(int)
                policies.append(dict(method=name, reference=ref, good=good, bad=bad, cutoff=cutoff,
                                     books=len(book), funded=int(lend.sum()), original_funded=int(original.sum()),
                                     extra_books=int(delta.gt(0).sum()), dropped_books=int(delta.lt(0).sum()),
                                     extra_loans=int(book.loans[delta.gt(0)].sum()),
                                     dropped_loans=int(book.loans[delta.lt(0)].sum()),
                                     extra_principal=book.principal[delta.gt(0)].sum(),
                                     dropped_principal=book.principal[delta.lt(0)].sum(),
                                     delta_margin_czk=(delta*payoff).sum()))
    return pd.DataFrame(metrics), pd.DataFrame(choices), pd.DataFrame(policies)


def run(out, cache):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    loans, tx, tx_n = load_ledger(fetch_archive(cache))
    labelled = label_loans(loans, tx)
    cases = episode_counts(labelled)
    scored = forecast(cases)
    metrics, choices, policies = summaries(scored)
    test = labelled.loc[labelled.month.isin(TEST_MONTHS)]
    # Descriptive landmark check: count only incident events after the month-three signal.
    at_risk = test.loc[test.short_by_month3.eq(0)]
    marked = at_risk.loc[at_risk.e3.eq(1)]
    unmarked = at_risk.loc[at_risk.e3.eq(0)]
    support = pd.DataFrame([dict(source_loans=len(loans), source_tx=tx_n, tagged_tx=len(tx),
                                 regions=test.region.nunique(), months=test.month.nunique(),
                                 test_books=len(cases), scored_books=len(scored), test_loans=len(test),
                                 scored_loans=int(scored.loans.sum()), test_events=int(test.y12.sum()),
                                 test_early6=int(test.e6.sum()), test_early3=int(test.e3.sum()),
                                 test_early3_events=int((test.e3 * test.y12).sum()),
                                 already_short_by_month3=int(test.short_by_month3.sum()),
                                 marked_at_risk=len(marked), incident_marked=int(marked.y12.sum()),
                                 unmarked_at_risk=len(unmarked), incident_unmarked=int(unmarked.y12.sum()),
                                 early_tagged_debits=int(test.early_tagged_debits.sum()),
                                 early_negative_balance_debits=int(test.early_overdraft_debits.sum()),
                                 missing_early_debits=int(test.early_tagged_debits.eq(0).sum()),
                                 test_principal=test.amount.sum())])
    for name, frame in (("episodes", scored), ("coverage", support), ("metrics", metrics),
                        ("direction", choices), ("policy", policies)):
        frame.to_csv(out / ("early_czech_" + name + ".csv"), index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)

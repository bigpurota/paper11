import numpy as np
import pandas as pd
import pytest

from paper11.pilot_prosper import prepare


def loan(key="loan-a", **overrides):
    row = dict(LoanKey=key, LoanNumber=10, LoanOriginationDate="2009-01-01",
               LoanStatus="Chargedoff", LoanMonthsSinceOrigination=18, LoanFirstDefaultedCycleNumber=9,
               LoanOriginalAmount=1000, TotalProsperLoans=0, BorrowerState="CA",
               LP_CustomerPayments=375, LP_GrossPrincipalLoss=900, LP_NetPrincipalLoss=800,
               LP_NonPrincipalRecoverypayments=25)
    row.update(overrides)
    return row


def test_count_funded_loan_and_recoveries_once():
    good = loan()
    result, audit = prepare(pd.DataFrame([good, good, loan("cancel", LoanStatus="Cancelled")]))
    assert len(result) == 1 and audit["duplicate_listing_rows"] == 1
    assert result.iloc[0].cash == -500 and result.iloc[0].event == 1
    assert result.iloc[0].grade == "new" and result.iloc[0].country == "West"


def test_ambiguous_default_cycle_and_immature_control():
    records = [loan("unknown", LoanFirstDefaultedCycleNumber=0),
               loan("late", LoanFirstDefaultedCycleNumber=15, TotalProsperLoans=1),
               loan("young", LoanStatus="Current", LoanMonthsSinceOrigination=5, LoanFirstDefaultedCycleNumber=np.nan),
               loan("clean", LoanStatus="Completed", LoanFirstDefaultedCycleNumber=np.nan,
                    LP_CustomerPayments=np.nan)]
    book, _ = prepare(pd.DataFrame(records))
    book = book.set_index("LoanKey")
    assert pd.isna(book.loc["unknown", "event"]) and pd.isna(book.loc["young", "event"])
    assert book.loc["late", "event"] == 0 and book.loc["late", "grade"] == "returning"
    assert book.loc["clean", "event"] == 0 and pd.isna(book.loc["clean", "cash"])


def test_inconsistent_duplicate_fails():
    with pytest.raises(ValueError, match="inconsistent"):
        prepare(pd.DataFrame([loan(), loan(LP_CustomerPayments=0)]))

import numpy as np
import pandas as pd
import pytest

from paper11.pilot_holdout import CASH, make_panel, order_positions


def record(date, amount=100, flag="0", received=110, rate=18):
    return dict(loan_issued_at=str(date), country="Estonia", customer_risk_rating="B",
                issued_amount=amount, initial_loan_duration=36, initial_interest_rate=rate,
                has_default_within_12_months=flag, principal_balance=0,
                **dict(zip(CASH, [received, 0, 0, 0])))


def fixture():
    origin = pd.Period("2024-06", "M")
    positions = [record((origin - 24).start_time + pd.Timedelta(minutes=i), flag=str(int(i < 11)))
                 for i in range(60)]
    positions.extend(record((origin - 12).start_time + pd.Timedelta(minutes=i), flag=str(int(i < 8)))
                     for i in range(50))
    positions.append(record(origin.start_time, amount=50, flag="1", received=25))
    future = (origin + 13).start_time
    positions.extend(record(future + pd.Timedelta(minutes=i), flag="1", received=50) for i in range(28))
    return pd.DataFrame(positions)


def one(frame):
    return make_panel(order_positions(frame), {"test": ("2024-06", "2024-06")}).iloc[0]


def test_origin_forecast_and_matched_cash_at_actual_principals():
    original = fixture()
    a = one(original)
    assert a.q_initial == pytest.approx(11.5 / 61)
    assert a.q_fresh == pytest.approx(8.5 / 51)
    assert a.mean_prior_exposure == pytest.approx(25 * 100 / 12)
    assert a.mean_prior_count == pytest.approx(25 / 12)
    assert a.future_count == 25 and a.action_changed
    assert a.pilot_cash == -25 and a.net_cash == 1225
    assert a.net_scenario == pytest.approx(-22.5 + 25 * 45)
    altered = original.copy()
    altered.loc[altered.loan_issued_at >= "2024-06", "has_default_within_12_months"] = "0"
    altered["principal_paid_total"] = 500
    b = one(altered)
    assert a.score == b.score and a.strict_probability == b.strict_probability
    assert a.selected == b.selected and b.net_cash != a.net_cash


def test_missing_cash_and_unknown_signals_are_not_zero():
    original = fixture()
    original.loc[original.loan_issued_at >= "2025-07", "interest_paid_total"] = np.nan
    a = one(original)
    assert a.action_changed and np.isnan(a.net_cash)
    original.loc[original.loan_issued_at.eq("2024-06-01 00:00:00"), "has_default_within_12_months"] = "0"
    b = one(original)
    assert not b.action_changed and b.net_cash == -25
    original.loc[original.loan_issued_at.eq("2024-06-01 00:00:00"), "has_default_within_12_months"] = None
    b = one(original)
    assert np.isnan(b.net_cash) and pd.isna(b.action_changed)


def test_empty_continuation_and_zero_prior_months_remain():
    original = fixture()
    a = one(original.loc[original.loan_issued_at < "2025-07"])
    assert a.future_count == 0 and a.would_change_action and not a.action_changed
    assert a.net_cash == a.pilot_cash and a.net_scenario == a.pilot_scenario


def test_tied_rows_order_independent_of_repayment():
    loans = pd.DataFrame([record("2022-01-01", amount=a) for a in [20, 10, 30]])
    ordered = order_positions(loans).principal.to_list()
    loans["principal_paid_total"] = [3000, 1, 0]
    assert order_positions(loans.iloc[::-1]).principal.to_list() == ordered


def test_empty_holdout_retains_public_analysis_schema():
    p = make_panel(order_positions(fixture()), {"no_support": ("2010-01", "2010-01")})
    assert p.empty and {"eligible", "selected", "net_cash", "origin_month"}.issubset(p.columns)


def test_missing_signal_on_an_empty_book_leaves_observed_pilot_cash():
    frame = fixture()
    frame = frame.loc[frame.loan_issued_at < "2025-07"].copy()
    frame.loc[frame.loan_issued_at.eq("2024-06-01 00:00:00"), "has_default_within_12_months"] = None
    a = one(frame)
    assert pd.isna(a.would_change_action) and not a.action_changed
    assert a.net_cash == a.pilot_cash and pd.isna(a.net_scenario)


def test_sparse_xlsx_keeps_empty_cells_and_maps_column_addresses(tmp_path):
    from xml.etree import ElementTree as ET
    from zipfile import ZipFile

    from paper11.pilot_holdout import FIELDS, NS, read_positions

    sheet = ET.Element(NS + "worksheet")
    sheet_data = ET.SubElement(sheet, NS + "sheetData")
    headers = ET.SubElement(sheet_data, NS + "row", r="1")
    data = ET.SubElement(sheet_data, NS + "row", r="2")
    strings = ET.Element(NS + "sst")
    for index, field in enumerate(FIELDS):
        column = chr(ord("A") + index)
        text = ET.SubElement(strings, NS + "si")
        ET.SubElement(text, NS + "t").text = field
        label = ET.SubElement(headers, NS + "c", r=column + "1", t="s")
        ET.SubElement(label, NS + "v").text = str(index)
        if field in {"issued_amount", "principal_paid_total"}:
            cell = ET.SubElement(data, NS + "c", r=column + "2")
            ET.SubElement(cell, NS + "v").text = "75" if field == "issued_amount" else "0"
    path = tmp_path / "tape.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(sheet))
        archive.writestr("xl/sharedStrings.xml", ET.tostring(strings))
    row = read_positions(path).iloc[0]
    assert row.issued_amount == "75" and row.principal_paid_total == "0"
    assert pd.isna(row.has_default_within_12_months) and pd.isna(row.interest_paid_total)

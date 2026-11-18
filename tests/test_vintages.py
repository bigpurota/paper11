from datetime import date

import numpy as np
import pandas as pd
import pytest

from paper11.methods import integrated_bad_rate
from paper11.vintages import ORIGINS, forecasts, summarize, windows


def test_all_maturity_gaps_and_nonoverlapping_forecast_windows():
    assert len(ORIGINS) == 12
    previous_end = None
    for origin in ORIGINS:
        start, end, test, stop = windows(origin)
        assert start.date() >= date(2008, 1, 1)
        assert end + pd.DateOffset(years=1) == test
        assert stop + pd.DateOffset(years=1) <= pd.Timestamp("2014-03-11")
        assert previous_end is None or previous_end == test
        previous_end = stop


def test_observed_label_forecasts_agree_with_revealed_truth_in_known_case():
    y = np.array([1., 0., 0., 1., 1., 0., 1., 0.])
    s = np.linspace(.1,.8,len(y))
    p = np.repeat(.4,len(y))
    truth = integrated_bad_rate(y,s)
    assert all(np.isclose(v,truth) for v in forecasts(y,s,1-y,p).values())
    masked = y.copy()
    masked[[0,2,5]] = np.nan
    assert forecasts(masked,s,y,p)["bayes"] == pytest.approx(truth)


def test_error_components_can_reverse_the_ranking_of_forecasts():
    cases = []
    for q, truth in enumerate([.04, .06, .08]):
        history = truth + .02
        for method, selection in (("accepts",-.02),("bayes",0.)):
            cases.append(dict(quarter=q,method=method,forecast_error=history+selection-truth,
                              masking_error=selection,historical_minus_future_abr=history-truth))
    agg = summarize(pd.DataFrame(cases)).set_index("method")
    assert agg.loc["bayes","masking_rmse"] < agg.loc["accepts","masking_rmse"]
    assert agg.loc["bayes","forecast_rmse"] > agg.loc["accepts","forecast_rmse"]
    np.testing.assert_allclose(agg.mean_squared_error,agg.masking_rmse**2 +
                               agg.drift_rmse**2 + agg.mean_cross_term, atol=1e-12)

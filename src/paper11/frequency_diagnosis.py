"""Explain forecast errors on the already-released October 2022–May 2024 Bondora test."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from .pilot_signal_evaluation import WINDOWS, brier, estimates
from .pilot_signal_ml import CUTOFF, fit_tree, issue_features, mature_training, peer_risk, prob


def error_components(prediction, actual, baseline):
    """An exact decomposition across equally weighted, principal-weighted portfolios."""
    prediction, actual, baseline = (np.asarray(x, dtype=float) for x in (prediction, actual, baseline))
    error = prediction - actual
    base_error = baseline - actual
    adjustment = prediction - baseline
    return dict(
        observed_rate=actual.mean(), predicted_rate=prediction.mean(), mean_error=error.mean(),
        within_book_component=(actual * (1 - actual)).mean(),
        squared_mean_error=error.mean() ** 2, centered_error_variance=error.var(),
        brier=brier(actual, prediction).mean(), brier_gap_vs_issue=(error**2 - base_error**2).mean(),
        squared_mean_error_gap=error.mean()**2 - base_error.mean()**2,
        centered_error_variance_gap=error.var() - base_error.var(),
        adjustment_squared=np.mean(adjustment**2),
        adjustment_alignment=2 * np.mean(adjustment * (actual - baseline)),
        closer_than_issue=int((abs(error) < abs(base_error)).sum()),
    )


def score_groups(test):
    full_start, full_stop = WINDOWS["full"]
    split = WINDOWS["later"][0]
    groups = [("full", "ALL", test), ("earlier", "ALL", test.loc[test.origin_month < split]),
              ("later", "ALL", test.loc[test.origin_month >= split])]
    groups.extend(("full", country, frame) for country, frame in test.groupby("country", sort=True))
    rows = []
    for period, country, group in groups:
        actual = group.future_default_principal / group.future_principal
        gap = {}
        group_rows = []
        for name, prediction in [
            ("issue_frequency", group.q_initial), ("issue_boost", group.m_origin),
            ("refresh_frequency", group.q_fresh), ("refresh_boost", group.m_public),
            ("peer_frequency", peer_risk(group)), ("peer_boost", group.m_peers),
            ("pilot_revealed_boost", group.m_seen),
        ]:
            components = error_components(prediction, actual, group.q_initial)
            group_rows.append(dict(period=period, country=country, forecast=name, books=len(group), **components))
            gap[name] = (prediction - actual)**2 - (group.q_initial - actual)**2
        paired = pd.DataFrame(gap)
        for record, interval in zip(group_rows, estimates(paired, group.origin_month, (full_start, full_stop),
                                                          period == "full" and country == "ALL"), strict=True):
            rows.append(dict(**record, gap_low=interval["low"], gap_high=interval["high"],
                             gap_draws=interval["estimable_draws"]))
    return pd.DataFrame(rows)


def support_and_response(fit, test):
    """Rebuild the old issue model and vary only the historical-rate input for the same contracts."""
    countries = sorted(fit.country.unique())
    target = fit.future_default_principal / fit.future_principal
    rows = []
    with threadpool_limits(limits=1):
        model = fit_tree(issue_features(fit, countries), target)
        issued = prob(model, issue_features(test, countries))
        np.testing.assert_allclose(issued, test.m_origin, atol=1e-10, rtol=0)
        for country in ["ALL", *sorted(set(countries) | set(test.country))]:
            train = fit if country == "ALL" else fit.loc[fit.country == country]
            part = test if country == "ALL" else test.loc[test.country == country]
            q = train.q_initial
            probe = outside = np.nan
            if country != "ALL" and not train.empty and not part.empty:
                probe = prob(model, issue_features(part.assign(q_initial=q.median()), countries)).mean()
                outside = int((~part.q_initial.between(q.min(), q.max())).sum())
            rows.append(dict(
                country=country, train_books=len(train), train_origin_first=train.origin_month.min(),
                train_origin_last=train.origin_month.max(),
                train_observed_rate=(train.future_default_principal / train.future_principal).mean(),
                train_frequency_min=q.min(), train_frequency_median=q.median(), train_frequency_max=q.max(),
                old_test_books=len(part), test_observed_rate=(part.future_default_principal / part.future_principal).mean(),
                test_frequency=part.q_initial.mean(), test_frequency_min=part.q_initial.min(),
                test_frequency_max=part.q_initial.max(), test_history_size_median=part.prior_n.median(),
                test_history_size_min=part.prior_n.min(), test_history_size_max=part.prior_n.max(),
                test_q_outside_country_train_range=outside, test_issue_boost=part.m_origin.mean(),
                test_boost_with_training_country_median_q=probe,
            ))
    return pd.DataFrame(rows)


def run(out):
    published = pd.read_csv(out / "pilot_signal_ml_episodes.csv")
    test = published.loc[(published.feed == "peers") & published.origin_month.between(*WINDOWS["full"])
                         & (published.future_count > 0) & published.model_scorable
                         & published.pilot_default.notna() & published.future_default_principal.notna()].copy()
    if test.empty or test.duplicated(["country", "origin_month"]).any():
        raise ValueError("the old test requires distinct, measured country-months")
    panel = pd.read_csv(out / "pilot_signal_panel.csv")
    fit = mature_training(panel.loc[panel["sample"] == "train"], CUTOFF)
    score_groups(test).to_csv(out / "frequency_diagnosis.csv", index=False, float_format="%.12g")
    support_and_response(fit, test).to_csv(out / "frequency_diagnosis_support.csv", index=False,
                                          float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    run(parser.parse_args().out)

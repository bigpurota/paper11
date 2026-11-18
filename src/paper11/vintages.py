"""Twelve out-of-time ABR forecasts and an ex-post decomposition of their errors."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import PROSPER_FEATURES, fetch, first_prosper_loans, prosper_approval_probability
from .methods import fit_scorecard, integrated_bad_rate

ORIGINS = pd.date_range("2010-01-01", "2012-10-01", freq="QS")


def windows(origin):
    """[history start, history end), one maturity year, [test start, test end)."""
    end = origin - pd.DateOffset(years=1)
    return end - pd.DateOffset(years=1), end, origin, origin + pd.DateOffset(months=3)


def forecasts(observed, scores, prior, propensity):
    """Issue forecasts before reading hidden or future outcomes."""
    a = np.isfinite(observed)
    return {
        "accepts": integrated_bad_rate(observed[a], scores[a]),
        "bayes": integrated_bad_rate(np.where(a, observed, prior), scores),
        "ipw": integrated_bad_rate(observed[a], scores[a], 1 / propensity[a]),
    }


def summarize(frame):
    rows = []
    reference = frame[frame.method == "accepts"].set_index("quarter").forecast_error
    for method, group in frame.groupby("method", sort=False):
        errors = group.forecast_error.to_numpy()
        selection = group.masking_error.to_numpy()
        drift = group.historical_minus_future_abr.to_numpy()
        base = reference.loc[group.quarter].to_numpy()
        squared = errors**2
        mse_difference = squared - base**2
        # Positive difference means more forecast error. This range measures influence.
        loo = (mse_difference.sum() - mse_difference) / (len(group)-1)
        rows.append(dict(method=method, quarters=len(group), forecast_rmse=np.sqrt(squared.mean()),
                         masking_rmse=np.sqrt(np.mean(selection**2)), drift_rmse=np.sqrt(np.mean(drift**2)),
                         mean_cross_term=2*np.mean(selection*drift), mean_squared_error=squared.mean(),
                         quarters_better_than_accepts=int((np.abs(errors)<np.abs(base)).sum()),
                         quarters_tied=int(np.isclose(errors,base,rtol=0,atol=1e-12).sum()),
                         loo_mse_delta_min=loo.min(), loo_mse_delta_max=loo.max()))
    return pd.DataFrame(rows)


def draw(frame, target):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9.8, 4.3), layout="constrained")
    x = np.arange(len(ORIGINS))
    for method, name, color, marker in [
        ("oracle_history", "Fully labeled mature history (audit)", "#737d85", "s"),
        ("accepts", "Accepted labels", "#29658b", "o"), ("bayes", "Bayesian estimate", "#b45534", "D"),
    ]:
        part = frame[frame.method == method]
        ax.plot(x, 100*part.forecast, label=name, color=color, marker=marker, ms=4, linewidth=1.5,
                linestyle="--" if method=="oracle_history" else "-")
    ax.plot(x, 100*part.future_abr, label="Realized next-quarter ABR", color="#16362d",
            marker="o", ms=5, linewidth=2.5)
    ax.set(xticks=x, xticklabels=part.quarter.tolist(), ylabel="Bad rate among low-risk approvals (%)")
    ax.grid(axis="y",alpha=.18)
    ax.spines[["top","right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2, loc="best", fontsize=9)
    ax.tick_params(axis="x",labelrotation=30)
    fig.savefig(target, dpi=155, metadata={"Software":"Matplotlib"})
    plt.close(fig)


def run(out, cache):
    df, _ = first_prosper_loans(fetch("prosper", cache))
    dates = pd.to_datetime(df.LoanOriginationDate)
    x = df[PROSPER_FEATURES].to_numpy(dtype=float)
    outcome = df.LoanFirstDefaultedCycleNumber.between(1, 12).to_numpy(dtype=int)
    p = prosper_approval_probability(df).to_numpy()
    visible = np.random.default_rng(1012).random(len(df)) < p
    observed = np.where(visible, outcome, np.nan)
    fit = (dates < "2008-01-01").to_numpy()
    imputer = SimpleImputer(strategy="median", keep_empty_features=True).fit(x[fit])
    x = imputer.transform(x)
    train = fit & visible
    scorecard = fit_scorecard(x[train], observed[train], seed=702)
    prior_model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1500)).fit(x[train], observed[train])
    scores = scorecard.predict_proba(x)[:, 1]
    prior = prior_model.predict_proba(x)[:, 1]
    rows = []
    for origin in ORIGINS:
        start, end, t0, t1 = windows(origin)
        hist = ((dates >= start) & (dates < end)).to_numpy()
        test = ((dates >= t0) & (dates < t1)).to_numpy()
        if not hist.any() or not test.any() or (fit & (hist | test)).any():
            raise ValueError("Empty or overlapping vintage")
        if df.loc[test, "LoanMonthsSinceOrigination"].min() < 12:
            raise ValueError("Immature test outcomes")
        predicted = forecasts(observed[hist], scores[hist], prior[hist], p[hist])
        # Hidden mature labels and future repayments are accessed only for the audit.
        oracle = integrated_bad_rate(outcome[hist], scores[hist])
        truth = integrated_bad_rate(outcome[test], scores[test])
        predicted["oracle_history"] = oracle
        for method, value in predicted.items():
            rows.append(dict(quarter=str(origin.to_period("Q")), history_start=str(start.date()),
                             history_end_exclusive=str(end.date()), forecast_origin=str(t0.date()),
                             forecast_end_exclusive=str(t1.date()), n_history=int(hist.sum()),
                             n_observed_history=int(visible[hist].sum()), n_test=int(test.sum()), method=method,
                             forecast=value, full_history_abr=oracle, future_abr=truth,
                             masking_error=value-oracle, historical_minus_future_abr=oracle-truth,
                             forecast_error=value-truth))
    out.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(out/"vintage_forecasts.csv", index=False, float_format="%.12g")
    summarize(frame).to_csv(out/"vintage_summary.csv", index=False, float_format="%.12g")
    draw(frame, out/"vintage_forecasts.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = ap.parse_args()
    run(args.out, args.cache)

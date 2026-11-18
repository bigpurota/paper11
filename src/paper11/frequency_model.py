"""Freeze a frequency forecast and learn only the effect of subsequent risk updates."""
import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit

from .pilot_rule import REPAY, SPREAD, TOL
from .pilot_signal_ml import (
    CUTOFF as OLD_CUTOFF, MIN_COUNTRY_ANALOGS, MIN_EPISODES, MIN_MONTHS, PEER_PRIOR,
    branch_value, mature_training, score_panel as boosted_forecasts,
)


CUTOFF = pd.Period("2024-06", freq="M")
RIDGE = 1.
KEYS = ["country", "origin_month", "feed"]
HGB_FIELDS = {"m_origin": "origin", "m_public": "public", "m_independent_common": "common",
              "m_blind": "blind", "m_seen": "seen", "blind_lend": "blind_lend",
              "seen_lend": "seen_lend", "ml_selected": "selected"}
ISSUE_FIELDS = ["analog_n", "analog_pooled", "pred_issue_pilot_pd", "pred_direct_money",
                "pred_info_money", "pred_net_money", "pred_information_bits",
                "pred_switch_probability", "ml_selected"]
DISCLOSURE_FIELDS = ["m_public", "m_blind", "m_repay", "m_default", "m_seen", "pi_disclosure",
                     "pilot_slope_effective", "blind_lend", "seen_lend"]


@dataclass(frozen=True)
class Slopes:
    refresh: float
    peers: float
    pilot: float


def ridge_slope(innovation, residual):
    return np.dot(innovation, residual) / (np.dot(innovation, innovation) + RIDGE)


def visible_peers(data, feed):
    if feed == "peers":
        return data.peer_n.to_numpy(dtype=float), data.peer_defaults.to_numpy(dtype=float)
    if feed == "no_peers":
        return np.zeros(len(data)), np.zeros(len(data))
    raise ValueError(f"unknown common feed {feed}")


def fit_slopes(data, feed):
    """Nested one-dimensional fits. A zero slope preserves the preceding forecast."""
    q, fresh = data.q_initial.to_numpy(), data.q_fresh.to_numpy()
    target = (data.future_default_principal / data.future_principal).to_numpy()
    refresh = np.clip(ridge_slope(fresh - q, target - q), 0., 1.)
    public = q + refresh * (fresh - q)
    n, defaults = visible_peers(data, feed)
    peer_innovation = (defaults - n * public) / (n + PEER_PRIOR)
    peers = np.clip(ridge_slope(peer_innovation, target - public), 0., 1.)
    common = public + peers * peer_innovation
    pi = (defaults + PEER_PRIOR * fresh) / (n + PEER_PRIOR)
    pilot = ridge_slope(data.pilot_default.to_numpy() - pi, target - common)
    return Slopes(refresh, peers, pilot)


def bounded_branches(common, pi, slope):
    """Keep both possible forecasts in [0,1] with their mixture equal to common."""
    common, pi = np.broadcast_arrays(common, pi)
    lower, upper = np.full(pi.shape, -np.inf), np.full(pi.shape, np.inf)
    lo_repay = np.divide(common - 1., pi, out=lower.copy(), where=pi > 0.)
    hi_repay = np.divide(common, pi, out=upper.copy(), where=pi > 0.)
    lo_default = np.divide(-common, 1.-pi, out=lower, where=pi < 1.)
    hi_default = np.divide(1.-common, 1.-pi, out=upper, where=pi < 1.)
    effective = np.clip(slope, np.maximum(lo_repay, lo_default), np.minimum(hi_repay, hi_default))
    repaid = np.clip(common - pi * effective, 0., 1.)
    default = np.clip(common + (1.-pi) * effective, 0., 1.)
    return effective, repaid, default


def conditional_forecasts(q, fresh, n, defaults, slopes):
    public = q + slopes.refresh * (fresh - q)
    common = public + slopes.peers * (defaults - n * public) / (n + PEER_PRIOR)
    pi = (defaults + PEER_PRIOR * fresh) / (n + PEER_PRIOR)
    effective, repaid, default = bounded_branches(common, pi, slopes.pilot)
    return public, common, pi, effective, repaid, default


def issue_forecasts(train, candidates, feed, slopes):
    """Integrate over historical common contexts; future test disclosures never enter."""
    forecast = []
    for row in candidates.itertuples(index=False):
        own = train.loc[train.country.eq(row.country)]
        pooled = len(own) < MIN_COUNTRY_ANALOGS
        analogs = train if pooled else own
        n, defaults = visible_peers(analogs, feed)
        old_fresh = analogs.q_fresh.to_numpy()
        old_peer_rate = np.divide(defaults, n, out=old_fresh.copy(), where=n > 0)
        shift = logit(row.q_initial) - logit(analogs.q_initial.to_numpy())
        fresh = expit(logit(old_fresh) + shift)
        peer_rate = expit(logit(old_peer_rate) + shift)
        _, _, pi, _, repaid, default = conditional_forecasts(
            row.q_initial, fresh, n, n * peer_rate, slopes)
        _, gain, bits, switch = branch_value(pi, repaid, default)
        gain = np.where(switch == 0, 0., gain)
        direct = row.pilot_principal * (REPAY - SPREAD * pi.mean())
        info = row.mean_prior_exposure * gain.mean()
        net = direct + info
        threshold = row.pilot_principal * TOL
        selected = row.structural_eligible and direct < -threshold and net > threshold
        forecast.append((len(analogs), pooled, pi.mean(), direct, info, net,
                         bits.mean(), switch.mean(), selected))
    return pd.DataFrame(forecast, columns=ISSUE_FIELDS, index=candidates.index)


def score_anchored(train, candidates, feed, slopes):
    test = candidates.reset_index(drop=True)
    n, defaults = visible_peers(test, feed)
    public, common, pi, effective, repaid, default = conditional_forecasts(
        test.q_initial.to_numpy(), test.q_fresh.to_numpy(), n, defaults, slopes)
    y = test.pilot_default.to_numpy(dtype=float)
    seen = np.where(y == 1, default, np.where(y == 0, repaid, np.nan))
    seen_lend = pd.Series(REPAY - SPREAD * seen > TOL, dtype="boolean").mask(np.isnan(seen))
    predictions = test.assign(feed=feed, train_n=len(train), train_months=train.origin_month.nunique(),
                              model_scorable=True, m_public=public, m_blind=common,
                              m_repay=repaid, m_default=default, m_seen=seen, pi_disclosure=pi,
                              pilot_slope_effective=effective, blind_lend=REPAY - SPREAD * common > TOL,
                              seen_lend=seen_lend)
    return pd.concat([predictions, issue_forecasts(train, test, feed, slopes)], axis=1)


def score_experiment(panel, older_train):
    train = panel.loc[panel["sample"].eq("train")]
    if not train.pilot_rank.eq(1).all():
        raise ValueError("the slope training unit is one first pilot per country-month")
    fit = mature_training(train, CUTOFF)
    test = panel.loc[panel["sample"].eq("test")]
    if test.duplicated(["country", "origin_month", "pilot_rank"]).any():
        raise ValueError("duplicate test pilot within a candidate rank")
    if (pd.PeriodIndex(test.origin_month, freq="M") < CUTOFF).any():
        raise ValueError("test pilot originates before the frequency-model freeze")
    n_months = fit.origin_month.nunique()
    supported = len(fit) >= MIN_EPISODES and n_months >= MIN_MONTHS
    forecasts, coefficients = [], []
    slopes = {}
    for feed in ("peers", "no_peers"):
        slopes[feed] = fit_slopes(fit, feed) if supported else Slopes(np.nan, np.nan, np.nan)
        fitted = slopes[feed]
        coefficients.append(dict(feed=feed, training_cutoff=str(CUTOFF), train_n=len(fit),
                                 train_months=n_months, refresh_slope=fitted.refresh,
                                 peer_slope=fitted.peers, pilot_slope=fitted.pilot, ridge_penalty=RIDGE))
    for _, candidates in test.groupby("pilot_rank", sort=True):
        candidates = candidates.sort_values(["origin_month", "country"]).reset_index(drop=True)
        by_feed = []
        for feed, fitted in slopes.items():
            if supported:
                by_feed.append(score_anchored(fit, candidates, feed, fitted))
            else:
                by_feed.append(candidates.assign(feed=feed, train_n=len(fit), train_months=n_months,
                               model_scorable=False, **{k: np.nan for k in ISSUE_FIELDS + DISCLOSURE_FIELDS}))
        score = pd.concat(by_feed, ignore_index=True)
        for prefix, pool, cutoff in [("hgb_", train, CUTOFF), ("hgb_2022_", older_train, OLD_CUTOFF)]:
            boosted = boosted_forecasts(pool, candidates, cutoff)[KEYS + list(HGB_FIELDS)]
            renamed = {key: prefix + name for key, name in HGB_FIELDS.items()}
            score = score.merge(boosted.rename(columns=renamed), on=KEYS, validate="one_to_one")
        forecasts.append(score)
    return pd.concat(forecasts, ignore_index=True), pd.DataFrame(coefficients)


def run(out):
    panel = pd.read_csv(out / "frequency_panel.csv")
    older = pd.read_csv(out / "pilot_signal_panel.csv")
    rows, coeff = score_experiment(panel, older.loc[older["sample"].eq("train")])
    rows.to_csv(out / "frequency_model_episodes.csv", index=False, float_format="%.12g")
    coeff.to_csv(out / "frequency_model_coefficients.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    run(parser.parse_args().out)

"""Price a single repayment observation with a frozen conditional portfolio model."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit, xlogy
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from .pilot_rule import REPAY, SPREAD, TOL

CUTOFF = pd.Period("2022-10", freq="M")
MIN_EPISODES = 80
MIN_MONTHS = 12
MIN_COUNTRY_ANALOGS = 12
PEER_PRIOR = 20.0
BASE_FIELDS = ["q_initial", "prior_n", "pilot_principal", "pilot_rate", "pilot_term",
               "mean_prior_exposure", "mean_prior_count"]
LOG_FIELDS = ["prior_n", "pilot_principal", "mean_prior_exposure"]
ISSUE_OUTPUTS = ["pred_issue_pilot_pd", "pred_direct_money", "pred_info_money", "pred_net_money",
                 "pred_information_bits", "pred_switch_probability", "ml_selected"]
DISCLOSURE_OUTPUTS = ["m_origin", "m_public", "m_peers", "m_independent_common", "pi_disclosure",
                      "m_repay", "m_default", "m_blind", "m_seen", "blind_lend", "seen_lend"]


def peer_risk(frame):
    """One peer group excludes the pilot; ordinary risk supplies the shrinkage target."""
    return ((frame.peer_defaults + PEER_PRIOR * frame.q_fresh) / (frame.peer_n + PEER_PRIOR)).to_numpy()


def issue_features(frame, countries):
    base = frame[BASE_FIELDS].copy()
    base[LOG_FIELDS] = np.log1p(base[LOG_FIELDS])
    country = frame.country.to_numpy()[:, None] == np.asarray(countries)[None, :]
    return np.column_stack([country, base.to_numpy(dtype=float)])


def contexts(at_issue, fresh, peers, peer_n):
    public = np.column_stack([at_issue, fresh])
    return public, np.column_stack([public, np.log1p(peer_n), peers])


def fit_tree(x, y):
    return HistGradientBoostingRegressor(
        loss="squared_error", max_iter=80, learning_rate=.05, max_leaf_nodes=7,
        min_samples_leaf=20, l2_regularization=5, early_stopping=False,
        random_state=1103).fit(x, y)


def prob(model, x):
    return np.clip(model.predict(x), 0., 1.)


def entropy(p):
    return -(xlogy(p, p) + xlogy(1-p, 1-p)) / np.log(2.)


def branch_value(pi, m_repay, m_default):
    """Average a *single* conditional model over both outcomes of the pilot."""
    blind = (1-pi)*m_repay + pi*m_default
    r0, r1 = REPAY - SPREAD*m_repay, REPAY - SPREAD*m_default
    rb = REPAY - SPREAD*blind
    extra = (1-pi)*np.maximum(r0, 0.) + pi*np.maximum(r1, 0.) - np.maximum(rb, 0.)
    bits = entropy(blind) - (1-pi)*entropy(m_repay) - pi*entropy(m_default)
    change = (1-pi)*((r0 > TOL) != (rb > TOL)) + pi*((r1 > TOL) != (rb > TOL))
    # Exact nulls avoid a machine-epsilon entropy gain on identical branches.
    informative = (m_repay != m_default) & (pi > 0) & (pi < 1)
    return (blind, np.where(informative, np.maximum(0., extra), 0.),
            np.where(informative, np.maximum(0., bits), 0.), change)


def branch_predictions(models, common):
    n = len(common)
    case_r, case_d = (np.column_stack([common, np.full(n, y)]) for y in (0., 1.))
    return prob(models["pilot"], common), prob(models["future"], case_r), prob(models["future"], case_d)


def mature_training(train, cutoff):
    """Targets are measurable only 13 months after each continuation book originates."""
    origins = pd.PeriodIndex(train.origin_month, freq="M")
    if (origins + 26 > cutoff).any():
        raise ValueError("training includes a continuation whose outcome is not yet mature")
    if train.duplicated(["country", "origin_month"]).any():
        raise ValueError("duplicate training country-month")
    required = ["q_initial", "q_fresh", "prior_n", "pilot_principal", "mean_prior_count",
                "mean_prior_exposure", "peer_n", "peer_defaults", "pilot_default",
                "future_count", "future_principal", "future_default_principal"]
    measured = train[required].notna().all(axis=1) & (train.future_count > 0) & (train.future_principal > 0)
    fit = train.loc[measured].sort_values(["origin_month", "country"]).reset_index(drop=True)
    if (not fit.pilot_default.isin([0, 1]).all()
            or not fit.future_default_principal.between(0, fit.future_principal).all()
            or not fit.q_initial.between(0., 1., inclusive="neither").all()
            or not fit.q_fresh.between(0., 1., inclusive="neither").all()
            or not fit.peer_defaults.between(0, fit.peer_n).all()):
        raise ValueError("training targets or historical rates are outside their domain")
    return fit


def fit_models(fit, countries):
    base = issue_features(fit, countries)
    public, with_peers = contexts(base, fit.q_fresh, peer_risk(fit), fit.peer_n)
    target = (fit.future_default_principal / fit.future_principal).to_numpy()
    pilot = fit.pilot_default.to_numpy()
    models = {"origin": fit_tree(base, target)}
    for feed, common in [("no_peers", public), ("peers", with_peers)]:
        models[feed] = {
            "common": fit_tree(common, target),
            "pilot": fit_tree(common, pilot),
            "future": fit_tree(np.column_stack([common, pilot]), target),
        }
    return models


def issue_forecasts(test, base, fit, models, feed):
    historical_shock = logit(fit.q_fresh.to_numpy()) - logit(fit.q_initial.to_numpy())
    peer_shock = logit(peer_risk(fit)) - logit(fit.q_fresh.to_numpy())
    results = []
    for i, loan in enumerate(test.itertuples(index=False)):
        own = fit.country.eq(loan.country).to_numpy()
        pooled = own.sum() < MIN_COUNTRY_ANALOGS
        analogs = np.ones(len(fit), dtype=bool) if pooled else own
        fresh = expit(logit(loan.q_initial) + historical_shock[analogs])
        peer = expit(logit(loan.q_initial) + historical_shock[analogs] + peer_shock[analogs])
        public, with_peers = contexts(np.repeat(base[i:i+1], len(fresh), axis=0), fresh,
                                      peer, fit.peer_n.to_numpy()[analogs])
        common = with_peers if feed == "peers" else public
        pi, repaid, default = branch_predictions(models, common)
        _, extra, bits, switch = branch_value(pi, repaid, default)
        direct = loan.pilot_principal * (REPAY - SPREAD*pi.mean())
        info = loan.mean_prior_exposure * extra.mean()
        net = direct + info
        selected = (loan.structural_eligible and direct < -TOL * loan.pilot_principal
                    and net > TOL * loan.pilot_principal)
        results.append((int(analogs.sum()), pooled, pi.mean(), direct, info, net, bits.mean(),
                        switch.mean(), bool(selected)))
    return pd.DataFrame(results, columns=["analog_n", "analog_pooled", *ISSUE_OUTPUTS], index=test.index)


def score_panel(train, test, cutoff=CUTOFF):
    fit = mature_training(train, cutoff)
    if test.duplicated(["country", "origin_month"]).any():
        raise ValueError("duplicate evaluation country-month")
    if (pd.PeriodIndex(test.origin_month, freq="M") < cutoff).any():
        raise ValueError("evaluation must start at or after the model freeze")
    test = test.sort_values(["origin_month", "country"]).reset_index(drop=True)
    countries = sorted(fit.country.unique())
    n_months = fit.origin_month.nunique()
    if len(fit) < MIN_EPISODES or n_months < MIN_MONTHS or test.empty:
        rows = [test.assign(feed=feed, train_n=len(fit), train_months=n_months, model_scorable=False,
                            analog_n=0, analog_pooled=pd.NA,
                            **{key: np.nan for key in ISSUE_OUTPUTS + DISCLOSURE_OUTPUTS})
                for feed in ("peers", "no_peers")]
        return pd.concat(rows, ignore_index=True)

    # Small country-month sample. A single CPU thread avoids parallel startup costs
    # and gives the same frozen fit in the CLI, unit tests and CI.
    with threadpool_limits(limits=1):
        models = fit_models(fit, countries)
        base = issue_features(test, countries)
        public, with_peers = contexts(base, test.q_fresh.to_numpy(), peer_risk(test), test.peer_n.to_numpy())
        base_pd = prob(models["origin"], base)
        public_pd = prob(models["no_peers"]["common"], public)
        peer_pd = prob(models["peers"]["common"], with_peers)
        rows = []
        for feed, common in [("peers", with_peers), ("no_peers", public)]:
            issue = issue_forecasts(test, base, fit, models[feed], feed)
            pi, repaid, default = branch_predictions(models[feed], common)
            blind, _, _, _ = branch_value(pi, repaid, default)
            pilot = test.pilot_default.to_numpy(dtype=float)
            seen = np.where(pilot == 1, default, np.where(pilot == 0, repaid, np.nan))
            scored = test.assign(feed=feed, train_n=len(fit), train_months=n_months, model_scorable=True,
                                 m_origin=base_pd, m_public=public_pd, m_peers=peer_pd,
                                 m_independent_common=peer_pd if feed == "peers" else public_pd,
                                 pi_disclosure=pi, m_repay=repaid, m_default=default,
                                 m_blind=blind, m_seen=seen, blind_lend=(REPAY-SPREAD*blind > TOL),
                                 seen_lend=pd.array(np.where(np.isnan(seen), np.nan, REPAY-SPREAD*seen > TOL),
                                                    dtype="boolean"))
            rows.append(pd.concat([scored, issue], axis=1))
    return pd.concat(rows, ignore_index=True)


def run(out):
    out = Path(out)
    panel = pd.read_csv(out / "pilot_signal_panel.csv")
    train = panel.loc[panel["sample"].eq("train")]
    scored = score_panel(train, panel.loc[panel["sample"].eq("test")])
    scored.to_csv(out / "pilot_signal_ml_episodes.csv", index=False, float_format="%.12g")

    # The three previously discussed Finnish cases are an after-the-fact walkthrough.
    # Freeze the model before the earliest of them, separately from the formal test.
    earlier_cutoff = pd.Period("2021-03", freq="M")
    ready = pd.PeriodIndex(train.origin_month, freq="M") + 26 <= earlier_cutoff
    cases = panel.loc[panel["sample"].eq("discovery")]
    finnish = score_panel(train.loc[ready], cases, cutoff=earlier_cutoff)
    finnish.to_csv(out / "pilot_signal_ml_finnish.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    run(parser.parse_args().out)

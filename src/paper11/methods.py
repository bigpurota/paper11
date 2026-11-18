"""Scorecards, reject inference and performance measures for the assigned paper.

All scores are probabilities of default (one = bad). An unobserved outcome is
represented by NaN. Only the evaluator receives population outcomes for audits.
"""
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


_METRICS = ("auc", "brier", "pauc", "abr")


def _vector(values, name):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    return values


def _probability(values, name):
    if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError(f"{name} must be finite and between 0 and 1")


def _labels(values):
    if not np.isin(values, [0, 1]).all():
        raise ValueError("observed outcomes must be binary, with 1 for default")


class _ScoreOrder:
    """Cache score ordering, tie groups and policy weights across label draws."""

    def __init__(self, score, sample_weight=None):
        score = _vector(score, "score")
        _probability(score, "score")
        weight = np.ones_like(score) if sample_weight is None else _vector(sample_weight, "weight")
        if weight.shape != score.shape or not np.isfinite(weight).all() or np.any(weight < 0):
            raise ValueError("weights must be aligned, finite and nonnegative")
        if not np.any(weight > 0):
            raise ValueError("evaluation requires an observation with positive weight")

        self.size = len(score)
        self.order = np.argsort(score, kind="stable")
        self.order = self.order[weight[self.order] > 0]
        self.score = score[self.order]
        self.weight = weight[self.order] / weight[self.order].sum()
        self.starts = np.r_[0, np.flatnonzero(np.diff(self.score)) + 1]
        self.mass = np.add.reduceat(self.weight, self.starts)
        self.hi = np.cumsum(self.mass)
        self.hi[-1] = 1.0
        self.lo = np.r_[0, self.hi[:-1]]
        self.abr_coef = self._integrated_policy_weights()

    def _integrated_policy_weights(self):
        # At approval fraction q, each group's selected share is
        # clip((q-lo)/(hi-lo),0,1). Integrate that share / q over [.2,.4].
        # This gives the exact uniform-rate average, even for tied PDs.
        a, b = 0.2, 0.4
        start = np.maximum(self.lo, a)
        end = np.maximum(np.minimum(self.hi, b), start)
        within = (end - start - self.lo * np.log(end / start)) / self.mass
        fully = np.log(b / np.clip(self.hi, a, b))
        return (within + fully) / (b - a)

    def group_defaults(self, y):
        return np.add.reduceat(y[self.order] * self.weight, self.starts)

    def abr_at(self, y, acceptance):
        if not 0 < acceptance <= 1:
            raise ValueError("acceptance must be in (0,1]")
        admitted = np.clip((acceptance - self.lo) / self.mass, 0., 1.)
        return float(np.dot(self.group_defaults(y), admitted) / acceptance)

    def values(self, y):
        grouped = self.group_defaults(y)
        abr = np.dot(grouped, self.abr_coef)
        brier = np.dot(self.weight, (y[self.order] - self.score) ** 2)
        bad, good = grouped.sum(), (self.mass - grouped).sum()
        if bad <= 0 or good <= 0:
            return np.array([np.nan, brier, np.nan, abr])

        # Ascending default probability: x = fraction of bads accepted (FNR),
        # y = fraction of goods accepted. Grouping ties produces linear ROC
        # segments with half-credit for concordance ties.
        dx = grouped / bad
        dy = (self.mass - grouped) / good
        y_left = np.r_[0., np.cumsum(dy[:-1])]
        auc = np.dot(dx, y_left + dy / 2)
        cap = .2
        x_left = np.r_[0., np.cumsum(dx[:-1])]
        width = np.clip(cap - x_left, 0., dx)
        fraction = np.divide(width, dx, out=np.zeros_like(width), where=dx > 0)
        area = np.dot(width, y_left + .5 * dy * fraction)
        chance = cap**2 / 2
        pauc = .5 + .5 * (area - chance) / (cap - chance)
        return np.array([auc, brier, pauc, abr])


def bad_rate(y_or_conditional_pd, score, acceptance=.3, sample_weight=None):
    """Expected defaults among the lowest-risk approval fraction, sharing ties."""
    pd_or_label = _vector(y_or_conditional_pd, "outcome or conditional PD")
    _probability(pd_or_label, "outcome or conditional PD")
    order = _ScoreOrder(score, sample_weight)
    if len(pd_or_label) != order.size:
        raise ValueError("outcomes and scores must be aligned")
    return order.abr_at(pd_or_label, acceptance)


def integrated_bad_rate(y_or_conditional_pd, score, sample_weight=None):
    """Average policy ABR for a uniform approval fraction between .2 and .4."""
    pd_or_label = _vector(y_or_conditional_pd, "outcome or conditional PD")
    _probability(pd_or_label, "outcome or conditional PD")
    order = _ScoreOrder(score, sample_weight)
    if len(pd_or_label) != order.size:
        raise ValueError("outcomes and scores must be aligned")
    return float(np.dot(order.group_defaults(pd_or_label), order.abr_coef))


def metrics(y, score, sample_weight=None):
    """AUC, Brier, standardized partial AUC (FNR ≤ .2), mean ABR over 20–40%."""
    y = _vector(y, "outcomes")
    _labels(y)
    order = _ScoreOrder(score, sample_weight)
    if len(y) != order.size:
        raise ValueError("outcomes and scores must be aligned")
    return dict(zip(_METRICS, map(float, order.values(y))))


def _partially_observed(y_observed, prior):
    y = _vector(y_observed, "observed outcomes")
    prior = _vector(prior, "prior")
    if len(prior) != len(y):
        raise ValueError("prior must be aligned with observed outcomes")
    missing = np.isnan(y)
    _labels(y[~missing])
    _probability(prior[missing], "prior on missing outcomes")
    return y, missing, prior


def bayesian_metrics(y_observed, score, prior, *, seed=11, min_draws=100,
                     max_draws=512, tol=1e-6):
    """Algorithm 1, drawing only unknown outcomes independently from their priors.

    Stop when the largest absolute change across running metric means is <= tol
    after min_draws, or when max_draws is reached. tol=0 requests a fixed budget.
    If a realization is single-class, only its Brier and ABR are defined.
    """
    if not 1 <= min_draws <= max_draws or not np.isfinite(tol) or tol < 0:
        raise ValueError("use 1 <= min_draws <= max_draws and nonnegative tolerance")
    y, missing, prior = _partially_observed(y_observed, prior)
    order = _ScoreOrder(score)
    if order.size != len(y):
        raise ValueError("outcomes and scores must be aligned")
    prior_missing = prior[missing]
    completed = np.where(missing, prior, y)
    if np.isin(prior_missing, [0, 1]).all():
        return dict(zip(_METRICS, map(float, order.values(completed))))

    rng = np.random.default_rng(seed)
    totals = np.zeros(4)
    counts = np.zeros(4, dtype=int)
    previous = np.full(4, np.nan)
    for draw in range(1, max_draws + 1):
        completed[missing] = rng.random(len(prior_missing)) < prior_missing
        values = order.values(completed)
        valid = np.isfinite(values)
        counts[valid] += 1
        totals[valid] += values[valid]
        means = np.divide(totals, counts, out=np.full(4, np.nan), where=counts > 0)
        if tol > 0 and draw >= min_draws and np.all(np.abs(means - previous) <= tol):
            break
        previous = means
    return dict(zip(_METRICS, map(float, means)))


def fit_scorecard(X, y, *, seed=11, sample_weight=None):
    """CPU XGBoost, using the assigned Appendix E.8 synthetic specification."""
    y = _vector(y, "training outcomes")
    _labels(y)
    if np.unique(y).size != 2:
        raise ValueError("scorecard training requires both default and repayment")
    model = XGBClassifier(
        n_estimators=100, max_depth=3, learning_rate=.1, subsample=.8,
        colsample_bytree=.8, tree_method="hist", n_jobs=1, random_state=seed,
        objective="binary:logistic", eval_metric="logloss",
    )
    return model.fit(X, y, sample_weight=sample_weight)


def fit_ipw(X_accept, y_accept, propensity_accept, *, seed=11, floor=.05):
    """Self-normalized inverse acceptance propensity weights, clipped at 1/floor."""
    propensity = _vector(propensity_accept, "acceptance propensity")
    _probability(propensity, "acceptance propensity")
    if not 0 < floor <= 1 or len(propensity) != len(y_accept):
        raise ValueError("check propensity length and clipping floor in (0,1]")
    weight = 1. / np.maximum(propensity, floor)
    return fit_scorecard(X_accept, y_accept, seed=seed, sample_weight=weight / weight.mean())


def fit_hard_cutoff(X_accept, y_accept, X_reject, *, seed=11):
    """HCA baseline, assigning all rejects the baseline score's .5 cutoff label."""
    model = fit_scorecard(X_accept, y_accept, seed=seed)
    if len(X_reject) == 0:
        return model
    pseudo = model.predict_proba(X_reject)[:, 1] >= .5
    return fit_scorecard(np.vstack([X_accept, X_reject]), np.r_[y_accept, pseudo], seed=seed)


@dataclass(frozen=True)
class BASLConfig:
    beta_low: float = .05
    beta_high: float = 1.
    rho: float = .8
    gamma: float = .01
    theta: float = 2.
    max_rounds: int = 3
    allow_round_zero: bool = False

    @classmethod
    def empirical(cls):
        """Selected real-data BASL parameters in Table E.9."""
        return cls(beta_low=.01, rho=.3, max_rounds=5)

    def __post_init__(self):
        if not 0 <= self.beta_low < self.beta_high <= 1 or not 0 < self.rho <= 1:
            raise ValueError("invalid filtering quantiles or sampling fraction")
        if not self.gamma > 0 or not self.theta > 0 or not self.gamma * (1 + self.theta) < 1:
            raise ValueError("good and bad tails must have disjoint percentile ranges")
        if not isinstance(self.max_rounds, int) or self.max_rounds < 0:
            raise ValueError("max_rounds must be a nonnegative integer")


@dataclass
class BASLResult:
    model: XGBClassifier
    best_round: int
    history: list
    stop_reason: str


def fit_basl(X_accept, y_accept, X_reject, X_val, y_val_observed, prior_val,
             *, seed=11, config=BASLConfig()):
    """Appendix B, with conditional mean integrated ABR for early stopping.

    No rejected training outcome, test outcome, or test feature enters this API.
    Algorithm B.3 starts selection at the first augmented candidate. Set
    allow_round_zero=True to include the unmodified baseline in selection.
    Without any possible augmentation, return the unmodified scorecard.
    """
    xa = np.asarray(X_accept, dtype=float)
    pool = np.asarray(X_reject, dtype=float)
    xv = np.asarray(X_val, dtype=float)
    if xa.ndim != 2 or pool.ndim != 2 or xv.ndim != 2 or not xa.shape[1] == pool.shape[1] == xv.shape[1]:
        raise ValueError("training, rejects and stop-validation require matching feature columns")
    ya = _vector(y_accept, "accepted outcomes")
    observed, missing, prior = _partially_observed(y_val_observed, prior_val)
    if len(xv) != len(observed) or not len(xv):
        raise ValueError("stop-validation labels must align with a nonempty validation sample")
    expected_default = np.where(missing, prior, observed)

    def expected_abr(model):
        return integrated_bad_rate(expected_default, model.predict_proba(xv)[:, 1])

    model = fit_scorecard(xa, ya, seed=seed)
    best_abr = expected_abr(model)
    if len(pool) and config.max_rounds:
        forest = IsolationForest(n_estimators=100, random_state=seed, n_jobs=1).fit(xa)
        similarity = forest.score_samples(pool)
        lo, hi = np.quantile(similarity, [config.beta_low, config.beta_high])
        pool = pool[(similarity >= lo) & (similarity <= hi)]

    history = [dict(round=0, n_good=0, n_bad=0, remaining=len(pool), validation_abr=best_abr)]
    result = BASLResult(model, 0, history, "max_rounds")
    rng = np.random.default_rng(seed)
    for j in range(1, config.max_rounds + 1):
        if not len(pool):
            result.stop_reason = "empty_pool"
            break
        n_sample = max(1, int(np.ceil(config.rho * len(pool))))
        sampled = rng.choice(len(pool), n_sample, replace=False)
        weak = make_pipeline(StandardScaler(), LogisticRegression(
            solver="liblinear", penalty="l1", C=1., max_iter=500, random_state=seed,
        )).fit(xa, ya)
        risk = weak.predict_proba(pool[sampled])[:, 1]
        if j == 1:
            low, high = np.quantile(risk, [config.gamma, 1 - config.gamma * config.theta])
        good, bad = risk < low, risk > high
        chosen = good | bad
        if not chosen.any():
            result.stop_reason = "no_confident_labels"
            break

        rows = sampled[chosen]
        xa = np.vstack([xa, pool[rows]])
        ya = np.r_[ya, bad[chosen]]
        pool = np.delete(pool, rows, axis=0)
        candidate = fit_scorecard(xa, ya, seed=seed)
        candidate_abr = expected_abr(candidate)
        history.append(dict(round=j, n_good=int(good.sum()), n_bad=int(bad.sum()),
                            remaining=len(pool), validation_abr=candidate_abr,
                            low=float(low), high=float(high)))
        if (j > 1 or config.allow_round_zero) and candidate_abr >= best_abr - 1e-12:
            result.stop_reason = "no_validation_improvement"
            break
        result.model = candidate
        result.best_round = j
        best_abr = candidate_abr
    return result

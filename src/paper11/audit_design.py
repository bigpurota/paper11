"""Post-plan extension: where should a lender spend a fixed randomized audit budget?"""
import numpy as np


def randomized_audit(y, observed, score, prior, *, seed, budgets=(10, 50), draws=500):
    """Compare equal-cost designs for a *fixed* 30% policy on the validation cohort.

    The audit officer may reveal outcomes only for sampled, historically declined
    accounts. The full truth is used only as a reference after estimating.
    """
    y, observed, score, prior = map(np.asarray, (y, observed, score, prior))
    target = score <= np.quantile(score, .3, method="inverted_cdf")
    missing = ~np.isfinite(observed)
    eligible = np.flatnonzero(missing & target)
    all_rejects = np.flatnonzero(missing)
    n_issued = target.sum()
    predicted = np.where(missing, prior, observed)[target].mean()
    truth = y[target].mean()
    for budget in budgets:
        n = min(budget, len(eligible))
        if not n:
            continue
        for strategy, pool in (("all_rejects", all_rejects), ("policy_rejects", eligible)):
            rng = np.random.default_rng(seed + budget)
            errors = []
            for _ in range(draws):
                chosen = rng.choice(pool, n, replace=False)
                residual = (y[chosen] - prior[chosen]) * target[chosen]
                # Expand observed residuals by the known inclusion probability n/N.
                correction = len(pool) * residual.mean() / n_issued
                errors.append(predicted + correction - truth)
            yield dict(design=strategy, n_audited=n, n_pool=len(pool), n_target=n_issued,
                       n_missing_in_target=len(eligible), prior_estimate=predicted, truth=truth,
                       prior_only_error=predicted-truth, audit_bias=np.mean(errors),
                       audit_rmse=np.sqrt(np.mean(np.square(errors))), draws=draws)

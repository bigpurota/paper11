"""Randomized offers, actual funding and repayment in two Philippine credit-score windows."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, fisher_exact

from .data import fetch

COLUMNS = ["lower_window", "treat", "prop_score", "loan_size", "prinpaid", "intpaid",
           "penalty", "paid_total", "net_revenue", "default_value"]
OUTCOMES = ["funded", "net_revenue", "loan_size", "any_shortfall", "material_shortfall",
            "cash_loss"]
CURRENCY_FACTOR = 16.0


def prepare(raw):
    d = raw[COLUMNS].copy()
    if not d.treat.isin([0, 1]).all() or not d.lower_window.isin([0, 1]).all():
        raise ValueError("assignment and randomization windows must be binary")
    if d[["loan_size", "net_revenue", "default_value", "prop_score"]].isna().any().any():
        raise ValueError("loan size, net revenue, cash loss and assignment shares must be observed")
    d["funded"] = d.loan_size > 0
    if (d.loan_size < 0).any() or not d.prinpaid.notna().equals(d.funded):
        raise ValueError("positive disbursements must have recorded principal repayments")
    funded = d.funded
    if d.loc[funded, ["paid_total", "intpaid", "penalty"]].isna().any().any():
        raise ValueError("funded accounts must have complete payment records")
    if not np.allclose(d.paid_total.fillna(0) / CURRENCY_FACTOR - d.loan_size,
                       d.net_revenue, rtol=0, atol=1e-6):
        raise ValueError("inconsistent cash flow or principal/repayment currency conversion")
    if not np.allclose(d.loc[funded, ["prinpaid", "intpaid", "penalty"]].sum(axis=1),
                       d.paid_total[funded], rtol=0, atol=.011):
        raise ValueError("total repayments do not match principal, interest and penalties")
    if not np.allclose(d.default_value, (-d.net_revenue).clip(lower=0), rtol=0, atol=1e-6):
        raise ValueError("the released default_value does not match cash loss")
    # Amounts paid in the source are pesos, whereas loan size is in PPP dollars.
    # Comparisons use integer centavos to avoid binary floating-point thresholds.
    unpaid_centavos = np.rint(100 * (d.loan_size * CURRENCY_FACTOR - d.prinpaid.fillna(0)))
    d["any_shortfall"] = d.funded & (unpaid_centavos > 0)
    d["material_shortfall"] = d.funded & (unpaid_centavos > 100)
    d["cash_loss"] = d.funded & (d.default_value > 0)
    return d


def ratio(a, b):
    return a / b if b > 0 else np.nan


def summarize_cells(means, low_weight):
    """Poststratified arm means; array indices are [window (high,low), arm, outcome]."""
    weights = np.array([1 - low_weight, low_weight])
    arms = np.einsum("s,szo->zo", weights, means)
    takeup, revenue, capital, any_short, material, loss = arms.T
    effects = arms[1] - arms[0]
    low = means[1]
    policy = (1 - low_weight) * means[0, 1] + low_weight * low[0]
    offer = arms[1]
    # Under the reference policy only the high window gets the offer.
    # The low window keeps its empirical control-arm crossover behavior.
    return {
        "funding_if_offer": takeup[1],
        "funding_if_no_offer": takeup[0],
        "offer_minus_no_offer_funding": effects[0],
        "cash_revenue_if_offer": revenue[1],
        "cash_revenue_if_no_offer": revenue[0],
        "offer_minus_no_offer_cash_revenue": effects[1],
        "cash_revenue_per_induced_disbursement_wald": ratio(effects[1], effects[0]),
        "portfolio_margin_per_unit_lent_if_offer": ratio(revenue[1], capital[1]),
        "principal_shortfall_gt1php_among_funded_if_offer": ratio(material[1], takeup[1]),
        "principal_shortfall_positive_among_funded_if_offer": ratio(any_short[1], takeup[1]),
        "negative_cash_margin_among_funded_if_offer": ratio(loss[1], takeup[1]),
        # Potential forced-lending outcome of non-takers remains unconstrained.
        "all_funded_hypothetical_risk_lower": material[1],
        "all_funded_hypothetical_risk_upper": material[1] + 1 - takeup[1],
        "cash_revenue_high_only_policy": policy[1],
        "offer_all_minus_high_only_cash_revenue": offer[1] - policy[1],
        "funding_high_only_policy": policy[0],
        "offer_all_minus_high_only_funding": offer[0] - policy[0],
        "funded_shortfall_high_only_extrapolation": ratio(means[0, 1, 4], means[0, 1, 0]),
        "high_only_extrapolation_minus_offer_all_funded_risk":
            ratio(means[0, 1, 4], means[0, 1, 0]) - ratio(material[1], takeup[1]),
    }


def run_experiment(raw, *, draws=1999, seed=8837):
    d = prepare(raw)
    if draws < 2:
        raise ValueError("At least two bootstrap replications are required")
    means = np.zeros((2, 2, len(OUTCOMES)))
    boot = np.empty((draws, *means.shape))
    rng = np.random.default_rng(seed)
    cells = []
    for (window, assigned), cell in d.groupby(["lower_window", "treat"]):
        values = cell[OUTCOMES].to_numpy(dtype=float)
        n = len(cell)
        means[window, assigned] = values.mean(axis=0)
        # Sample within each actual randomized arm and score window. Keep all
        # outcomes for each borrower together; window weights stay fixed.
        for start in range(0, draws, 50):
            stop = min(draws, start + 50)
            indices = rng.integers(n, size=(stop - start, n))
            boot[start:stop, window, assigned] = values[indices].mean(axis=1)
        cells.append(dict(window="low" if window else "high", assigned_offer=assigned, n=n,
                          documented_offer_probability=.60 if window else .85,
                          extract_offer_share=cell.prop_score.iloc[0],
                          funded=int(cell.funded.sum()), cash_losses=int(cell.cash_loss.sum()),
                          residual_gt1php=int(cell.material_shortfall.sum()),
                          residual_positive=int(cell.any_shortfall.sum()),
                          mean_cash_revenue=cell.net_revenue.mean(),
                          mean_principal=cell.loan_size.mean()))
    if len(cells) != 4:
        raise ValueError("both offer arms must be observed in each score window")
    low_weight = float(d.lower_window.mean())
    point = summarize_cells(means, low_weight)
    samples = pd.DataFrame([summarize_cells(rep, low_weight) for rep in boot])
    results = []
    for name, value in point.items():
        lo, hi = samples[name].quantile([.025, .975])
        results.append(dict(estimand=name, estimate=value, ci_low=lo, ci_high=hi,
                            bootstrap_draws=draws, n=len(d)))
    return pd.DataFrame(cells), pd.DataFrame(results)


def transfer_audit(cells):
    """Estimate a high-window constant prior, then compare it to low-window outcomes."""
    offered = cells.loc[cells.assigned_offer == 1].set_index("window")
    high, low = offered.loc["high"], offered.loc["low"]
    h, hn = int(high.residual_gt1php), int(high.funded)
    l, ln = int(low.residual_gt1php), int(low.funded)
    if not (hn and ln):
        raise ValueError("both offered windows must contain funded accounts for the audit")
    prior = h / hn
    source_ci = binomtest(h, hn).proportion_ci(method="exact")
    target_ci = binomtest(l, ln).proportion_ci(method="exact")
    fisher = fisher_exact([[h, hn - h], [l, ln - l]], alternative="two-sided")
    return dict(prior_source="high_window_funded_after_offer", validation="low_window_funded_after_offer",
                high_events=h, high_funded=hn, prior=prior, prior_ci_low=source_ci.low,
                prior_ci_high=source_ci.high, low_events=l, low_funded=ln,
                expected_low_events=prior*ln, observed_low_rate=l/ln, low_ci_low=target_ci.low,
                low_ci_high=target_ci.high, observed_minus_expected_rate=l/ln-prior,
                fisher_two_sided_p=fisher.pvalue)


def draw_rct(contrasts, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    v = contrasts.set_index("estimand")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), layout="constrained")
    left, right = axes
    for i, key in enumerate(["funding_if_offer", "funding_if_no_offer"]):
        x = v.loc[key]
        left.errorbar(x.estimate, 1-i, xerr=[[x.estimate-x.ci_low], [x.ci_high-x.estimate]],
                      fmt="o", color="#175d78", lw=2, capsize=5)
        left.annotate(f"{x.estimate:.1%}", (x.estimate, 1-i), xytext=(0, 12),
                      textcoords="offset points", ha="center")
    left.set(yticks=[1, 0], yticklabels=["Offer assigned", "No offer assigned"],
             xlim=(0, .85), xlabel="Fraction funded", title="Assignment and actual funding")

    key = "principal_shortfall_gt1php_among_funded_if_offer"
    x = v.loc[key]
    right.errorbar(x.estimate, 1, xerr=[[x.estimate-x.ci_low], [x.ci_high-x.estimate]],
                   fmt="o", color="#175d78", lw=2, capsize=5)
    right.annotate(f"{x.estimate:.2%}", (x.estimate, 1), xytext=(4, 12),
                   textcoords="offset points", ha="left")
    lo, hi = (v.loc["all_funded_hypothetical_risk_" + bound, "estimate"]
              for bound in ["lower", "upper"])
    right.hlines(0, lo, hi, linewidth=6, color="#b65832")
    right.annotate(f"{lo:.2%} to {hi:.2%}", ((lo+hi)/2, 0), xytext=(0, 12),
                   textcoords="offset points", ha="center")
    right.set(yticks=[1, 0], yticklabels=["Funded after offer", "If everyone borrowed"],
              xlim=(0, .32), xlabel="Fraction with >1 peso principal unpaid",
              title="Repayment and missing outcomes")
    for ax in axes:
        ax.set_ylim(-.65, 1.6)
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.grid(axis="x", alpha=.15)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
    fig.suptitle("Philippines randomized credit offers · 1,113 retained applicants",
                 fontweight="bold", fontsize=14)
    fig.supxlabel("Whiskers show 95% conditional bootstrap intervals. "
                  "The orange segment shows identification bounds.", fontsize=9)
    fig.savefig(path, dpi=160, metadata={"Software": "Matplotlib"})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    raw = pd.read_csv(fetch("philippines_offers", args.cache), usecols=COLUMNS)
    if len(raw) != 1113 or int(raw.treat.sum()) != 891:
        raise ValueError("assigned sample does not match the authors' published Table 1")
    cells, results = run_experiment(raw)
    # prop_score in this follow-up extract is the realized arm share, while
    # the original assignment protocol documents probabilities of .60 and .85.
    for window, cell in raw.groupby("lower_window"):
        if not np.allclose(cell.prop_score, cell.treat.mean()):
            raise ValueError(f"unexpected archived prop_score in window {window}")
    args.out.mkdir(exist_ok=True, parents=True)
    cells.to_csv(args.out / "rct_cells.csv", index=False, float_format="%.10g")
    results.to_csv(args.out / "rct_contrasts.csv", index=False, float_format="%.10g")
    pd.DataFrame([transfer_audit(cells)]).to_csv(args.out / "rct_prior_transfer.csv",
                                                index=False, float_format="%.10g")
    draw_rct(results, args.out / "rct_policy.png")


if __name__ == "__main__":
    main()

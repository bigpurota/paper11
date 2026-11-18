# How much weight should a bank give its own local history?

A local rate has two advantages when a market consistently differs from its neighbors. The geography matches and the bank can update it directly as repayments arrive. A broader rate has more observations. It can be closer when local history is thin or when the local market changes before the old loans mature.

## A break-even condition for forecast error

Let L be the dated local forecast, G the broader forecast from other areas, and p the expected future event rate for the portfolio being scored, given the information available at issue. For an individual binary event, expected Brier loss at forecast f is p(1−p)+(f−p)². The difference in favor of using local is therefore

$$E[\mathrm{Brier}(G)-\mathrm{Brier}(L)\mid\mathcal I]=(L-G)(2p-L-G).$$

If L exceeds G, the local forecast is preferable when the expected risk exceeds their midpoint. The midpoint is known in advance; the expected future risk is exactly what needs estimating. A large historical sample by itself cannot settle which side the next cohort will fall on.

One way to approximate that choice is to average the forecasts. In a simple model where the local estimate has unbiased sampling error with variance V, the local market deviates from the broad center by a mean-zero amount of variance T, and those errors are independent, the excess mean squared error of wL+(1−w)G is w²V+(1−w)²T. Minimizing it gives **w=T/(T+V)**, the credibility weight of Bühlmann (1967, *ASTIN Bulletin* 4(3)) and the shrinkage factor of empirical Bayes (Efron and Morris, 1973, *JASA* 68(341)). A majority local weight requires **T>V**. A broader estimate that is itself noisy, correlated markets or a common change in risk can invalidate that approximation.

## The information the rule uses

At the forecast date we count measured local outcomes, current issuance and mature events in every other market. Between-market dispersion is estimated using only the other markets and adjusted for their sampling noise. At least three donor markets with twenty measured loans each are required to estimate that dispersion. The broader forecast pools all measured donor loans. A rapidly expanding local book discounts effective sample size. For example, 120 mature loans against 1,200 recent issues give 12 effective observations for the weighting calculation. The historical rate itself still uses all 120 outcomes.

Writing L for the smoothed local rate and n_eff for effective local support, the hard choice gives the local forecast more weight when n_eff+1 exceeds L(1−L)/T, for T>0. This threshold changes with the local rate and the historical heterogeneity among the other markets. The expansion penalty and the three-market minimum are fixed modeling choices. The no-expansion comparator measures whether the penalty added predictive value under the same test. [Precommitted definition and endpoints](local-trust-protocol.md) · [Implementation](../src/paper11/local_trust.py)

The Dutch reconstruction describes a known miss. The independent test transfers these exact weights to states of one US bank, with forecasts issued each quarter. It evaluates the actual local-versus-broader choice separately from the average forecast and reports the lending decision under two margin assumptions. [Dutch history](dutch-frequency.md) · [Eight reconstructed forecasts](../results/dutch_trust.csv) · [Wells Fargo transfer](local-trust-bank.md)

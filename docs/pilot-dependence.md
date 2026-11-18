# How much can a single repayment possibly be worth?

Suppose the bank knows the default probabilities of the pilot and a future loan but is unsure how strongly one predicts the other. It can bound what the signal is worth *before* fitting a shared-risk model. The following calculation is for a one-pilot policy. After seeing the pilot the bank can lend to or decline each eligible future borrower. Future repayments supply no additional learning within this comparison.

## A formula from the joint default table

Let p and q be the two default probabilities, conditional on everything already known to the bank. Let t be the probability that both loans default if funded at the specified terms. For the future loan let r be margin on repayment and let r−c be margin on default. Declining earns zero. If the pilot defaults, the probability-weighted future margin from lending is p r − c t. If the pilot repays, it is (1−p)r − c(q−t). The uninformed lender can already earn the positive part of r−cq.

Writing [x]₊ = max(0,x), the incremental value of the pilot's information for this borrower, in money at the follow-up decision date, is

$$
g(t)=[p r-c t]_+ + [(1-p)r-c(q-t)]_+ - [r-cq]_+.
$$

This follows by taking the better action separately on each signal branch. The expression also handles a pilot with deterministic repayment. Under independence, t = pq and g(t) = 0. Dependence alone need not give value: the signal must change a decision with a strictly positive payoff difference. A negative association can carry useful information too.

## A ceiling using only the two marginal risks

The four cells of the binary table are nonnegative precisely for $t$ between $\max(0,p+q-1)$ and $\min(p,q)$. Both endpoints are attainable. The function g is convex and piecewise linear in t. Its maximum is therefore the larger of its values at those two endpoints. Independence attains its minimum of zero. This gives a sharp signal-value range without a latent regime or a fitted correlation parameter.

For distinct future borrowers, sum the eligible values with their appropriate discount and exposure weights. This sum is exact when future actions can be chosen separately, terms and cash flows are additive, the pilot produces only this binary signal and the no-pilot lender has the same other information. The upper endpoint is jointly attainable with only marginal constraints: specify each future borrower's conditional default probabilities by its two-by-two table with the pilot, then draw the future outcomes independently conditional on that pilot outcome. Coupled lending limits or pre-existing constraints on correlations between future borrowers can narrow it.

**An impossibility check.** Let pilot default probability be 2%, and each future applicant's default probability 30%. A unit future loan earns 0.10 if repaid and loses 0.45 at default. At t=0, a pilot default guarantees that this particular future borrower would repay. That unusually strong signal arrives with probability just 0.02, and the other branch still leads the bank to decline. Thus g(0)=0.002. At the other endpoint t=0.02 the decision stays decline and g=0. Across four future loans, even the most favorable joint law is worth at most 0.008. If today's pilot has an all-in expected loss of 0.010, no possible dependence consistent with these marginal probabilities can cover it. This is an upper bound under the stated experiment. Individual PDs alone never guarantee a positive gain because independence is compatible with them.

**Connection with the running example.** With persistent PD of 0.05 or 0.40, weighted 0.55 and 0.45, the pilot and next loan both have q=0.2075. Conditional independence within each regime gives $t=0.55(0.05)^2+0.45(0.40)^2$. Substitution yields 0.00548125 per eligible follow-up. With no discount, an initial loss of 0.014125 is covered by three follow-ups that use this single signal. Repeated learning can change the subsequent policy after each additional repayment and has a different threshold. [General decision rule](information-value.md) · [Fully adaptive example](exploration.md)

## Apply the bound to another portfolio

For each future borrower, estimate default risk conditional on the information available to both lenders at the decision date. Express repayment and default margins in money for that borrower’s actual exposure. Set the discount weight to zero for any decision made before the pilot outcome arrives. The following example computes the ceiling in today's money. If the pilot costs more than the ceiling, the proposed one-label design cannot recover its cost. A ceiling above the loss leaves the question open. To calculate an expected gain at a specified joint law, replace the endpoint maximum with `signal_value` and supply the joint default probability for each borrower.

```python
from paper11.pilot_dependence import maximum_signal_value

pilot_pd = 0.02
pilot_loss = 0.010
# Each row is (future PD, repayment margin, default margin, discount weight).
future_loans = [(0.30, 0.10, -0.45, 1.0)] * 4
ceiling = sum(weight * maximum_signal_value(pilot_pd, q, repay, default)
              for q, repay, default, weight in future_loans)
print(f"At most {ceiling:.3f} in future gains for a pilot costing {pilot_loss:.3f}.")
```

For random common information arriving between the pilot and a later decision, apply the calculation conditional on each possible common update and average over those updates. The general decision rule gives the corresponding conditional value-of-information identity.

[Calculator](../src/paper11/pilot_dependence.py) · [Enumeration over feasible joint tables and all four contingent actions](../tests/test_pilot_dependence.py)

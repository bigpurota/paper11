# Which repayment totals determine the value of five approval policies?

Suppose a lender can request an exact aggregate from a credit registry. It has five fixed approval cutoffs. Which totals should it request to compare the money earned under every pair of policies? On our five validation cohorts, four totals for borrowers between consecutive cutoffs recover all ten pairwise differences. Ten totals by prior-risk decile recover none exactly. On Prosper those ten totals still settle the direction of one decision.

## Information needed for a fixed policy menu

There are $N$ applicants. Let $x_i$ be the unknown expected margin from lending to hidden applicant $i$ at the specified loan terms. Each candidate policy fixes its lending decisions before the disclosures. The $j$th row of $D$ contains the decisions of policy $j$ on the hidden applicants. The visible records contribute known total margin $b_j$. Policy $j$'s margin per applicant is $(b_j+D_jx)/N$. This comparison holds the loan terms and the applicant's outcome under lending fixed across policies.

Let $C$ contain the rows $D_k-D_j$ for the pairs of interest. The known terms and the common denominator can be added at the end. A registry supplies $s=Ax$, with known, fixed rows for the linear aggregates. Assume that the vector of unknown expected margins can vary freely over a nonempty open box in the hidden coordinates. For example, in the unit-principal scenario each default probability can vary independently between 0 and 1, so its expected margin ranges between −0.45 and +0.10.

**Criterion.** Every pairwise difference is determined for every admissible $x$ if and only if every row of $C$ belongs to the row space of $A$. Equivalently, all directions in $\ker A$ must also belong to $\ker C$. This is an application of the standard row-space/null-space identity. [Gilbert Strang, MIT OpenCourseWare, *The Four Fundamental Subspaces and Least Squares*](https://ocw.mit.edu/courses/res-18-010-a-2020-vision-of-linear-algebra-spring-2020/resources/res-18010-strang-part-1-version-2_mp4/)

* If $C=BA$, then $Cx=Bs$. The coefficients in $B$ reconstruct every requested difference.
* If a contrast $c$ lies outside the row space, subtract its orthogonal projection onto that space. The residual $h$ satisfies $Ah^T=0$ and $ch^T=\lVert h\rVert^2>0$. Start at any interior $x_0$ and add or subtract a sufficiently small multiple of $h^T$. The two possibilities have the same disclosures and different values of this contrast. Even a nonlinear decoder sees identical input in these two cases.

With freely chosen linear measurements, **the minimum number of independent sums is $\operatorname{rank}(C)$**. A basis of its rows attains the minimum. If some aggregates are already known, the minimum number of *additional* independent measurements is the rank of the matrix formed by stacking $A$ over $C$, less the rank of $A$. The count measures scalars disclosed. Obtaining a true group sum can require learning the outcome of every person in that group.

For five nested cutoffs, subtract each policy from the next. The resulting rows indicate four disjoint expansion bands. The indicator rows with at least one hidden borrower are linearly independent. Every wider expansion is the sum of consecutive rows. Hence four totals suffice when all four hidden bands are populated. If one band has only known outcomes, three totals suffice. For policies that cross, the same row-space test applies to their signed decision differences.

### An example with no dataset

Two hidden borrowers are in the same risk group. A new policy lends only to the first of them, and the registry gives their combined expected margin of +0.08. Individual margins of (+0.03, +0.05) and (+0.05, +0.03) both match the disclosure. Their difference, a multiple of $(1,-1)$, lies in the null space of the registry question. The expansion earns different positive amounts in these two worlds. A failure to identify the exact amount alone provides no guarantee of a sign reversal. The current registry answer might also constrain the sign, once the bounds on feasible margins are accounted for.

The minimum applies to uniform recovery on a continuous open box. If the target were a vector of three binary labels and the registry could choose arbitrary infinite-precision weights, a single total $y_1+2y_2+4y_3$ would encode all eight possibilities. Ordinary group counts impose a different measurement restriction. At particular realized binary totals, even an uninformative-looking partition can sometimes resolve a decision exactly, for example when an audited group has zero defaults.

## What happens on Taiwan and Prosper?

We used the same five validation cutoffs (30%, 35%, 40%, 45%, 50%), historical approval mask and prior ranking as the [policy experiments](identification.md). Both sets of questions are chosen using scores and the mask. The row-space calculation sees no hidden outcomes. We then requested the **actual binary default totals** in each group in a separate retrospective audit. With common terms, group size $m$ and default count $k$ give the realized group margin $0.10m-0.55k$. All margins refer to the finite validation population.

| Exact totals disclosed | Independent sums | Further independent sums needed | Exact amounts across 50 pair comparisons | Decisions settled at the actual binary totals |
|---|---:|---:|---:|---:|
| Ten groups of historically hidden applicants ranked by the logistic prior | 10 | 4 | 0 | 1 |
| Four bands of historically hidden applicants between consecutive candidate cutoffs | 4 | 0 | 50 | 50 |

Each design was evaluated on ten pairs in each of four Taiwan folds and one Prosper cohort. Under the ten actual decile totals, **Prosper's 30% to 50% expansion is the only decision settled**. Its sharp modeled gain is +0.195 to +1.468 percentage points of principal per applicant. Its exact gain when the individual outcomes are opened for evaluation is +1.145 pp. Both signs remain feasible on the other nine Prosper pairs and all forty Taiwan pairs. These are related comparisons within five validations.

For each pair of nested cutoffs, take a group with $m$ hidden members, $t$ of whom switch decision, and $k$ actual hidden defaults. Between $\max(0,k-m+t)$ and $\min(k,t)$ switchers can default. Assigning defaults inside or outside the band attains each endpoint. We add the endpoints across the disjoint groups and then add known switcher defaults. The decision is to expand for a strictly positive gain and to retain the incumbent at exact break-even. This separate binary calculation checks whether the realized **signal** settles the decision, even when the **design** cannot reconstruct every expected margin difference. Every bound was cross-checked against the fully revealed outcomes. Four aligned totals say nothing about the cost of acquiring repayments, borrowing take-up or a later cohort.

## Reproduction

From the repository root, run `PYTHONPATH=src .venv/bin/python -m paper11.policy_information --out results --cache data/cache`. The [summary](../results/policy_information_summary.csv) has one row per fold and design. The [pair results](../results/policy_information_pairs.csv) give both conditional endpoints, the fully observed gain, and the decision. CSV monetary values are fractions of unit principal per validation applicant. Multiply by 100 for percentage points.

The [code](../src/paper11/policy_information.py) computes orthonormal row-space bases by singular-value decomposition and uses exact rational arithmetic for break-even decisions. The [tests](../tests/test_policy_information.py) cover crossing decisions, a null-space witness, empty bands, a binary encoding counterexample and exhaustive enumeration of outcomes for an independent small cohort.

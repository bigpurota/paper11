"""Verify deliverable consistency, without imposing a preferred empirical finding."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from numpy.testing import assert_allclose


def verify(out):
    def read(name):
        return pd.read_csv(out / (name + ".csv"))
    t, e, b = read("training"), read("evaluation"), read("policy")
    assert set(t.dataset) == {"prosper","taiwan"}
    assert t.groupby(["dataset","fold"]).ngroups == 5
    assert t.groupby(["dataset","fold"]).size().eq(6).all()
    assert t[["auc","pauc","abr","brier"]].apply(lambda c:c.between(0,1).all()).all()
    assert ((b.cutoff >= 0) & (b.cutoff <= 1)).all()
    assert_allclose(b.profit_per_issued, .10-1.10*b.lgd*b.test_abr, atol=1e-9)
    assert_allclose(b.profit_per_applicant, b.profit_per_issued*b.test_approval, atol=1e-9)
    rms = read("evaluation_rmse").set_index(["dataset","method","metric"]).sort_index()
    expected = e.assign(sq=e.error**2).groupby(["dataset","method","metric"]).sq.mean().pow(.5)
    assert_allclose(rms.rmse, expected, atol=1e-9)
    assert_allclose(e.error, e.estimate-e.truth, atol=1e-9)
    assert_allclose(e.within_cohort_error, e.estimate-e.validation_oracle_audit, atol=1e-9)
    tr = read("simulation_trajectory")
    assert tr.seed.nunique() == 20 and len(tr) == 100
    assert len(read("simulation_fig2_digitized")) > 0
    for name in ("simulation_fig2.png","calibration.png"):
        assert (out/name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    cal = read("calibration").groupby(["dataset","fold","method"]).n.sum()
    parts = read("partitions")
    n_test = parts[parts.role=="test"].set_index(["dataset","fold"]).n
    for (ds,fold,_),n in cal.items():
        assert n == n_test.loc[(ds,fold)]
    ref = read("paper_comparison").set_index(["table","method","metric"])
    assert len(ref)==28
    by_model = t.groupby(["dataset","method"]).mean(numeric_only=True)
    for (table,method,metric),row in ref.iterrows():
        for ds in ("prosper","taiwan"):
            target = rms.loc[(ds,method,metric),"rmse"] if table==2 else by_model.loc[(ds,method),metric]
            assert_allclose(row[ds],target,atol=1e-9)
    audit = read("audit_budget")
    assert (audit.n_audited <= audit.n_pool).all() and audit.draws.eq(500).all()
    summary = read("audit_summary").set_index(["dataset","n_audited","design"]).sort_index()
    expected = audit.assign(square=audit.audit_rmse**2).groupby(["dataset","n_audited","design"]).square.mean()
    assert_allclose(summary.audit_rmse, np.sqrt(expected), atol=1e-9)
    diff = read("uncertainty").set_index(["dataset","contrast"])
    for ds in ("taiwan","prosper"):
        delta = by_model.loc[(ds,"basl"),"abr"]-by_model.loc[(ds,"accepts"),"abr"]
        assert_allclose(diff.loc[(ds,"basl_minus_accepts_abr"),"estimate"],delta,atol=1e-9)
    print("PASS: cohort counts, score ranges, calibration counts, RMSE, financial identities, paper comparisons, paired contrasts and randomized audit.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    verify(parser.parse_args().out)

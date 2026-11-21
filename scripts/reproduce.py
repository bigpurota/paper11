"""Regenerate all research outputs into an empty scratch folder and compare."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import pandas as pd


def run(reference, cache):
    with TemporaryDirectory(prefix="paper11-repeat-") as tmp:
        dest=Path(tmp)
        env=dict(os.environ, PYTHONPATH="src", OMP_NUM_THREADS="1",
                 OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
        for command in (["-m","paper11.empirical","--cache",str(cache)], ["-m","paper11.simulation"],
                        ["-m","paper11.vintages","--cache",str(cache)],
                        ["-m","paper11.bounds_experiment","--cache",str(cache)],
                        ["-m","paper11.identification","--cache",str(cache)],
                        ["-m","paper11.decision_audit","--cache",str(cache)],
                        ["-m","paper11.policy_information","--cache",str(cache)],
                        ["-m","paper11.exploration"],
                        ["-m","paper11.information_value"],
                        ["-m","paper11.pilot_replay","--cache",str(cache)],
                        ["-m","paper11.pilot_transfer","--cache",str(cache)],
                        ["-m","paper11.lender_pilot","--cache",str(cache)],
                        ["-m","paper11.pilot_targeting"],
                        ["-m","paper11.pilot_profiles","--cache",str(cache)],
                        ["-m","paper11.pilot_signal_sensitivity","--cache",str(cache)],
                        ["-m","paper11.pilot_holdout","--cache",str(cache)],
                        ["-m","paper11.pilot_prosper","--cache",str(cache)],
                        ["-m","paper11.pilot_rule_evaluation","--cache",str(cache)],
                        ["-m","paper11.finnish_pilot_cases","--cache",str(cache)],
                        ["-m","paper11.pilot_signal_panel","--cache",str(cache)],
                        ["-m","paper11.pilot_signal_ml"],
                        ["-m","paper11.pilot_signal_evaluation"],
                        ["-m","paper11.frequency_diagnosis"],
                        ["-m","paper11.frequency_panel","--cache",str(cache)],
                        ["-m","paper11.frequency_model"],
                        ["-m","paper11.frequency_evaluation"],
                        ["-m","paper11.dutch_frequency","--cache",str(cache)],
                        ["-m","paper11.dutch_trust"],
                        ["-m","paper11.local_trust_bank","--cache",str(cache)],
                        ["-m","paper11.early_dutch","--cache",str(cache)],
                        ["-m","paper11.early_czech","--cache",str(cache)],
                        ["-m","paper11.rct","--cache",str(cache)],
                        ["-m","paper11.hard_selection","--cache",str(cache)],
                        ["-m","paper11.selection_strength","--cache",str(cache)],
                        ["-m","paper11.diagnostics","--cache",str(cache)],
                        ["scripts/report.py"], ["scripts/verify.py"]):
            subprocess.run([sys.executable,*command,"--out",tmp],env=env,check=True)
        actual={f.name for f in dest.iterdir()}
        expected={f.name for f in reference.iterdir() if f.is_file() and not f.name.startswith(".")}
        if actual!=expected:
            raise ValueError(f"Differing output list: {actual ^ expected}")
        exact=0
        for name in sorted(expected):
            a,b=reference/name,dest/name
            if a.read_bytes()==b.read_bytes():
                exact+=1
            elif a.suffix==".csv":
                pd.testing.assert_frame_equal(pd.read_csv(a),pd.read_csv(b),rtol=1e-7,atol=1e-9)
            else:
                raise ValueError(f"{name} differs from reference bytes (graphics may vary by renderer)")
        print(f"Reproduced {len(expected)} artifacts; {exact} byte-identical.")


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference",type=Path,default=Path("results"))
    ap.add_argument("--cache",type=Path,default=Path("data/cache"))
    args=ap.parse_args(); run(args.reference,args.cache)

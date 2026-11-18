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
                        ["-m","paper11.rct","--cache",str(cache)],
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

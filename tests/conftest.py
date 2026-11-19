"""Single-threaded numerical libraries, as in the Makefile, so a bare `pytest` behaves like `make test`.

Multithreaded OpenMP in XGBoost can deadlock in child processes on macOS; the thread counts
must be fixed before any numerical library is imported.
"""
import os

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(name, "1")
os.environ.setdefault("MPLBACKEND", "Agg")

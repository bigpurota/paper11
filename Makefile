PYTHON ?= python3.12
VENV ?= .venv
PY := $(VENV)/bin/python
OUT ?= results
CACHE ?= data/cache
export PYTHONPATH := src
export OMP_NUM_THREADS := 1
export OPENBLAS_NUM_THREADS := 1
export VECLIB_MAXIMUM_THREADS := 1
export MPLBACKEND := Agg

.PHONY: all setup data empirical simulation extensions report test verify reproduce slides

all: setup
	$(PY) -m paper11.empirical --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.simulation --out "$(OUT)"
	$(PY) -m paper11.vintages --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.bounds_experiment --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.identification --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.decision_audit --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.policy_information --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.exploration --out "$(OUT)"
	$(PY) -m paper11.information_value --out "$(OUT)"
	$(PY) -m paper11.pilot_replay --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_transfer --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.lender_pilot --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_targeting --out "$(OUT)"
	$(PY) -m paper11.pilot_profiles --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_signal_sensitivity --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_holdout --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_prosper --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_rule_evaluation --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.rct --out "$(OUT)" --cache "$(CACHE)"
	$(PY) scripts/report.py --out "$(OUT)"
	$(PY) scripts/verify.py --out "$(OUT)"
setup: $(VENV)/.paper11-installed

$(VENV)/.paper11-installed: requirements.txt requirements-lock.txt
	$(PYTHON) -m venv "$(VENV)"
	$(PY) -m pip install --disable-pip-version-check -r requirements-lock.txt
	@touch "$@"
data: setup
	$(PY) -c "from paper11.data import fetch, SOURCES; [fetch(s, '$(CACHE)') for s in SOURCES]"
	$(PY) -c "from paper11.lender_pilot import fetch_bondora, fetch_bondora_followup; fetch_bondora('$(CACHE)'); fetch_bondora_followup('$(CACHE)')"
	$(PY) -c "from paper11.pilot_holdout import fetch_holdout; fetch_holdout('$(CACHE)')"
empirical: setup
	$(PY) -m paper11.empirical --out "$(OUT)" --cache "$(CACHE)"
simulation: setup
	$(PY) -m paper11.simulation --out "$(OUT)"
extensions: setup
	$(PY) -m paper11.vintages --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.bounds_experiment --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.identification --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.decision_audit --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.policy_information --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.exploration --out "$(OUT)"
	$(PY) -m paper11.information_value --out "$(OUT)"
	$(PY) -m paper11.pilot_replay --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_transfer --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.lender_pilot --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_targeting --out "$(OUT)"
	$(PY) -m paper11.pilot_profiles --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_signal_sensitivity --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_holdout --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_prosper --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.pilot_rule_evaluation --out "$(OUT)" --cache "$(CACHE)"
	$(PY) -m paper11.rct --out "$(OUT)" --cache "$(CACHE)"
report: setup
	$(PY) scripts/report.py --out "$(OUT)"
test: setup
	$(PY) -m pytest -q
verify: test
	$(PY) scripts/verify.py --out "$(OUT)"
reproduce: setup
	$(PY) scripts/reproduce.py --reference "$(OUT)" --cache "$(CACHE)"
slides: setup
	$(PY) slides/build.py

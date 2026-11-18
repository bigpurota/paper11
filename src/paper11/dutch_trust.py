"""Apply the locked local-frequency credibility rule to the eight Dutch discovery books."""
import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .local_trust import trust_forecast
from .pilot_signal_evaluation import brier


def evaluate(books, donors):
    if donors.duplicated(["origin_month", "country"]).any() or donors.country.eq("Netherlands").any():
        raise ValueError("expected distinct outside countries per forecast month")
    donor_sets = dict(tuple(donors.groupby("origin_month")))
    cases = []
    for row in books.itertuples(index=False):
        reference = donor_sets[row.origin_month]
        estimate = trust_forecast(row.historical_defaults, row.historical_labels, row.recent_issued,
                                  reference.historical_defaults, reference.historical_labels)
        if not np.isclose(estimate.pooled, row.other_countries_forecast):
            raise ValueError("donor counts disagree with the archived pooled rate")
        cases.append(dict(origin_month=row.origin_month, n=row.historical_labels, recent_n=row.recent_issued,
                          mature_months=row.observed_historical_months,
                          eligible_donors=reference.historical_labels.ge(20).sum(),
                          outcome=row.first25_principal_rate, count_outcome=row.first25_count_rate,
                          **asdict(estimate)))
    frame = pd.DataFrame(cases)
    for name in ("local", "pooled", "hybrid", "hard", "support_hybrid"):
        frame["brier_"+name] = brier(frame.outcome, frame[name])
    return frame


def run(out):
    books = pd.read_csv(out / "dutch_frequency_episodes.csv")
    donors = pd.read_csv(out / "dutch_frequency_donors.csv")
    result = evaluate(books, donors)
    result.to_csv(out / "dutch_trust.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    run(parser.parse_args().out)

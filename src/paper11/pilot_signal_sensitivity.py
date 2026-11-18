"""Replay follow-up decisions for the original ten selected Bondora pilots."""
import argparse
from pathlib import Path

import pandas as pd

from .lender_pilot import DEFAULT, REPAID, TOL, fetch_bondora, margin, prepare


def signal_sensitivity(episodes, loans):
    """Hold selection fixed and vary prior precision and shared same-month information."""
    selected = episodes.loc[episodes.selected]
    if selected.duplicated(["country", "customer", "pilot_month"]).any():
        raise ValueError("duplicate selected pilot")
    cohorts = loans.sort_values(["date", "LoanNumber"]).groupby(["Country", "customer", "month"])
    threshold = REPAID / (REPAID - DEFAULT)
    rows = []
    for ep in selected.itertuples(index=False):
        month = pd.Period(ep.pilot_month, "M")
        batch = cohorts.get_group((ep.country, ep.customer, month))
        pilot = int(batch.event.iloc[0])
        if pd.Period(ep.future_month, "M") != month + 13 or pilot != ep.pilot_default_12m:
            raise ValueError("pilot label or decision month differs from the original replay")
        # Keep the pilot private. Only the other members can enter the common feed.
        peers = batch.event.iloc[1:]
        for strength in (10, 20, 40):
            for source, count, defaults in (("none", 0, 0), ("all_peers", len(peers), int(peers.sum()))):
                public_events = strength * ep.q_fresh + defaults
                public_strength = strength + count
                q_base = public_events / public_strength
                q_pilot = (public_events + pilot) / (public_strength + 1)
                base_lend, pilot_lend = margin(q_base) > TOL, margin(q_pilot) > TOL
                rows.append(dict(country=ep.country, customer=ep.customer, pilot_month=ep.pilot_month,
                                 fresh_history_n=ep.fresh_n, historical_pd=ep.q_fresh, prior_strength=strength,
                                 peer_feed=source, peer_n=count, peer_defaults=defaults, pilot_default=pilot,
                                 decision_threshold=threshold, pd_without_pilot=q_base, pd_with_pilot=q_pilot,
                                 lend_without_pilot=base_lend, lend_with_pilot=pilot_lend,
                                 action_changed=base_lend != pilot_lend))
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    episodes = pd.read_csv(args.out / "lender_pilot_episodes.csv")
    loans = prepare(fetch_bondora(args.cache))
    rows = signal_sensitivity(episodes, loans)
    rows.to_csv(args.out / "pilot_signal_sensitivity.csv", index=False, float_format="%.10g")


if __name__ == "__main__":
    main()

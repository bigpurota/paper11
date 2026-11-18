import numpy as np
import pandas as pd
import pytest

from paper11.methods import integrated_bad_rate
from paper11.simulation import Mixture, Pool, approve, one_trial, summarize


def test_mixture_fixed_counts_positive_covariance_and_posterior():
    rng = np.random.default_rng(802)
    population = Mixture.create(rng)
    x, y = population.sample(30000, rng)
    assert x.shape == (30000, 4)
    assert y.sum() == 21000
    assert (np.linalg.eigvalsh(population.covs) > 0).all()
    p = population.exact_pd(x)
    assert abs(p.mean() - .7) < .007
    # Check calibration conditionally across risk bins on independent draws.
    for group in np.array_split(np.argsort(p), 5):
        assert abs(y[group].mean() - p[group].mean()) < .024
    noisy = x.copy()
    noisy[:, 2:] += 1000
    np.testing.assert_array_equal(population.exact_pd(noisy), p)


def test_approval_uses_application_features_and_exact_quota():
    rng = np.random.default_rng(31)
    x = np.arange(400).reshape(100, 4)
    y = rng.integers(2, size=100)
    a, b = Pool(), Pool()
    a.append((x, y), None, np.random.default_rng(3))
    b.append((x, 1 - y), None, np.random.default_rng(3))
    np.testing.assert_array_equal(a.arrays()[2], b.arrays()[2])
    assert np.array_equal(np.flatnonzero(a.arrays()[2]), np.arange(15))
    random = approve(np.zeros(200), .15, rng)
    assert random.sum() == 30 and not random[:30].all()


def test_random_disclosure_placebo_and_oracle_under_selection():
    rng = np.random.default_rng(17)
    population = Mixture.create(rng)
    x, y = population.sample(50000, rng)
    scores = population.exact_pd(x)
    selected = approve(x[:, 0], .15, rng)
    random = approve(np.zeros(len(x)), .15, rng)
    truth = integrated_bad_rate(y, scores)
    perfect_prior = integrated_bad_rate(np.where(selected, y, scores), scores)
    assert abs(perfect_prior - truth) < .012
    assert abs(integrated_bad_rate(y[random], scores[random]) - truth) < .025
    assert integrated_bad_rate(y[selected], scores[selected]) < truth - .05


def test_feedback_checkpoints_reproducible_and_oracle_gap_formula():
    p = (27, 6, 3, 100, 800, 8)
    first = pd.DataFrame(one_trial(p))
    pd.testing.assert_frame_equal(first, pd.DataFrame(one_trial(p)))
    assert first.n_accepted.tolist() == [45, 90]
    evidence = summarize(first).set_index(["statistic", "metric"])
    expected = np.mean(first.truth_abr - first.oracle_model_abr)
    assert evidence.loc[("oracle_gap", "abr"), "estimate"] == pytest.approx(expected)
    errors = first.bayes_eval_abr - first.truth_abr
    assert evidence.loc[("bayes_eval_rmse", "abr"), "estimate"] == pytest.approx(np.mean(errors**2)**.5)


def test_cli_regenerates_figure_and_tables_from_empty_directory(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    output = tmp_path / "unpopulated" / "results"
    env = dict(os.environ, PYTHONPATH=str(src), MPLCONFIGDIR=str(tmp_path / "mpl"))
    subprocess.run([sys.executable, "-m", "paper11.simulation", "--out", str(output),
                    "--seeds", "2", "--batches", "4", "--interval", "4", "--holdout", "200",
                    "--draws", "4", "--workers", "1"], cwd=tmp_path, env=env, check=True,
                   capture_output=True)
    assert {p.name for p in output.iterdir()} == {
        "simulation_trajectory.csv", "simulation_comparison.csv",
        "simulation_fig2_digitized.csv", "simulation_fig2.png",
    }
    points = pd.read_csv(output / "simulation_fig2_digitized.csv")
    assert len(points) == 24
    point = points.query('panel == "training" and method == "oracle_model_abr" and batch == 40')
    assert point.paper_abr.item() == pytest.approx(.15262)
    assert (output / "simulation_fig2.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

import numpy as np
import pandas as pd
import pytest

from adskills import stats


def test_wilson_known_values():
    lo, hi = stats.wilson(10, 100)
    assert lo == pytest.approx(0.0552, abs=1e-3)
    assert hi == pytest.approx(0.1744, abs=1e-3)
    assert stats.wilson(0, 10)[0] == 0.0
    assert stats.wilson(10, 10)[1] == pytest.approx(1.0)
    assert all(np.isnan(stats.wilson(0, 0)))


def test_bh_matches_hand_calculation():
    p = [0.01, 0.04, 0.03, 0.20]
    # sorted: .01,.03,.04,.20 -> .04,.06,.0533,.20 -> monotone: .04,.0533,.0533,.20
    np.testing.assert_allclose(stats.benjamini_hochberg(p), [0.04, 0.05333333, 0.05333333, 0.20])


def test_cluster_bootstrap_point_estimate_and_wider_interval_with_clusters():
    rng = np.random.default_rng(1)
    # 40 employers x 10 ads; skill use is decided per employer -> strong clustering
    emp = np.repeat(np.arange(40), 10)
    uses = np.repeat(rng.random(40) < 0.3, 10)
    df = pd.DataFrame({"emp": emp, "sql": uses, "year": 2020})
    out = stats.cluster_bootstrap_shares(df, ["sql"], "emp", "year", n_boot=1000, seed=0)
    r = out.iloc[0]
    assert r["share"] == pytest.approx(uses.mean())
    assert r["lo"] <= r["share"] <= r["hi"]
    w_lo, w_hi = stats.wilson(int(uses.sum()), len(uses))
    assert (r["hi"] - r["lo"]) > 1.8 * (w_hi - w_lo)  # clustering widens the interval
    assert r["design_effect"] > 5


def test_cluster_bootstrap_independent_data_close_to_wilson():
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"emp": np.arange(2000), "x": rng.random(2000) < 0.2})
    r = stats.cluster_bootstrap_shares(df, ["x"], "emp", n_boot=2000, seed=0).iloc[0]
    w = stats.wilson(int(df["x"].sum()), 2000)
    assert r["lo"] == pytest.approx(w[0], abs=0.006)
    assert r["hi"] == pytest.approx(w[1], abs=0.006)


def test_precision_recall():
    pred = pd.Series([1, 1, 0, 0, 1])
    gold = pd.Series([1, 0, 1, 0, 1])
    r = stats.precision_recall(pred, gold)
    assert (r["tp"], r["fp"], r["fn"]) == (2, 1, 1)
    assert r["precision"] == pytest.approx(2 / 3) and r["recall"] == pytest.approx(2 / 3)

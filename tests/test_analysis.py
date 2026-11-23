import numpy as np
import pandas as pd
import pytest

from adskills import analysis


def synth(n_emp=300, seed=0):
    """Employers post 1-4 ads; SQL rises with year, Excel flat; employer-level effects."""
    rng = np.random.default_rng(seed)
    rows = []
    for e in range(n_emp):
        base = rng.normal(0, 1)
        for _ in range(rng.integers(1, 5)):
            year = int(rng.integers(2016, 2026))
            p_sql = 1 / (1 + np.exp(-(-1 + 0.25 * (year - 2020.5) + 0.5 * base)))
            rows.append({"employer_key": f"e{e}", "year": year, "s_sql": rng.random() < p_sql, "s_excel": rng.random() < 0.3})
    return pd.DataFrame(rows)


def test_add_skills_and_groups():
    df = pd.DataFrame({"headline": ["Dataanalytiker", "BI"], "description": ["Power BI och Azure", "Python"]})
    out = analysis.add_skills(df)
    assert out.loc[0, "power_bi"] and out.loc[0, "any_bi_tool"] and out.loc[0, "any_cloud"]
    assert out.loc[1, "python_or_r"] and not out.loc[1, "any_cloud"]
    assert set(analysis.all_keys()) <= set(out.columns)


def test_period():
    p = analysis.period(pd.Series([2016, 2018, 2019, 2023, 2025]))
    assert list(p.fillna("na")) == ["early", "early", "na", "late", "late"]


def test_cluster_bootstrap_diff_detects_rise_not_flat():
    df = synth()
    df["period"] = analysis.period(df["year"])
    out = analysis.cluster_bootstrap_diff(df, ["s_sql", "s_excel"], "employer_key", "period", "early", "late", n_boot=500).set_index("skill")
    assert out.loc["s_sql", "diff"] > 0.15 and out.loc["s_sql", "lo"] > 0
    assert out.loc["s_excel", "lo"] < 0 < out.loc["s_excel", "hi"]


def test_logistic_trend_recovers_slope():
    pytest.importorskip("statsmodels")
    df = synth(n_emp=1500, seed=3)
    tr = analysis.trends(df, ["s_sql", "s_excel"]).set_index("skill")
    # population-average slope is attenuated from 0.25 by the employer effect; check direction and CI
    assert tr.loc["s_sql", "or_per_year"] > 1.15 and tr.loc["s_sql", "lo"] > 1
    assert tr.loc["s_excel", "lo"] < 1 < tr.loc["s_excel", "hi"]
    assert tr.loc["s_sql", "p_bh"] < 0.001

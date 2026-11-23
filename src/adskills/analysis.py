"""Prevalence and trends (M5). Pre-registered in docs/decisions.md (D10)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import skills, stats

# Derived groups, defined before results (D10).
GROUPS = {
    "any_cloud": ["azure", "aws", "gcp", "snowflake", "databricks", "cloud_any"],
    "any_bi_tool": ["power_bi", "tableau", "qlik", "looker"],
    "python_or_r": ["python", "r"],
}
EARLY = (2016, 2018)
LATE = (2023, 2025)


def add_skills(df: pd.DataFrame) -> pd.DataFrame:
    text = (df["headline"].fillna("") + "\n" + df["description"].fillna("")).tolist()
    m = skills.skill_matrix(text)
    m.index = df.index
    for g, members in GROUPS.items():
        m[g] = m[members].any(axis=1)
    return pd.concat([df, m], axis=1)


def add_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Derived groups from skill flags that are already columns (features file, D16)."""
    out = df.copy()
    for g, members in GROUPS.items():
        out[g] = out[members].any(axis=1)
    out["any_cloud_vendor"] = out[["azure", "aws", "gcp", "snowflake", "databricks"]].any(axis=1)
    return out


def all_keys() -> list[str]:
    return list(skills.SKILL_KEYS) + list(GROUPS)


def period(year: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=year.index, dtype="object")
    out[year.between(*EARLY)] = "early"
    out[year.between(*LATE)] = "late"
    return out


def cluster_bootstrap_diff(
    df: pd.DataFrame, cols: list[str], cluster_col: str, split_col: str, a, b, n_boot: int = 2000, seed: int = 0
) -> pd.DataFrame:
    """Share(b) - share(a) with an interval from resampling employers once for both groups.

    Employers that post in both groups are resampled together, so the dependence
    between the two shares is kept.
    """
    d = df[df[split_col].isin([a, b])]
    clusters = d[cluster_col].unique()
    idx = {c: i for i, c in enumerate(clusters)}
    ci = d[cluster_col].map(idx).to_numpy()
    m = len(clusters)
    vals = d[cols].to_numpy(dtype=float)
    is_b = (d[split_col] == b).to_numpy()
    # per-cluster sums for each group
    def sums(mask):
        n = np.bincount(ci[mask], minlength=m).astype(float)
        k = np.vstack([np.bincount(ci[mask], weights=vals[mask, j], minlength=m) for j in range(len(cols))]).T
        return n, k

    na, ka = sums(~is_b)
    nb, kb = sums(is_b)
    rng = np.random.default_rng(seed)
    diffs = np.empty((n_boot, len(cols)))
    for t in range(n_boot):
        w = np.bincount(rng.integers(0, m, m), minlength=m).astype(float)
        diffs[t] = (w @ kb) / (w @ nb) - (w @ ka) / (w @ na)
    pa, pb = ka.sum(0) / na.sum(), kb.sum(0) / nb.sum()
    lo, hi = np.quantile(diffs, [0.025, 0.975], axis=0)
    # two-sided bootstrap p-value for H0: diff = 0 (share of draws on the other side, x2)
    p = np.minimum(1.0, 2 * np.minimum((diffs <= 0).mean(0), (diffs >= 0).mean(0)))
    return pd.DataFrame(
        {"skill": cols, "share_a": pa, "share_b": pb, "diff": pb - pa, "lo": lo, "hi": hi, "p_boot": p,
         "n_a": int(na.sum()), "n_b": int(nb.sum())}
    )


def logistic_trend(df: pd.DataFrame, col: str, cluster_col: str = "employer_key", extra: str = "") -> dict:
    """Logit(mention) ~ year (centred) [+ extra], employer-clustered SEs. Needs statsmodels."""
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    d = df.assign(y=df[col].astype(int), year_c=df["year"].astype(float) - 2020.5)
    if d["y"].nunique() < 2:
        return {"skill": col, "or_per_year": np.nan, "lo": np.nan, "hi": np.nan, "p": np.nan, "n": len(d)}
    formula = "y ~ year_c" + (f" + {extra}" if extra else "")
    groups = pd.factorize(d[cluster_col])[0]
    fit = smf.glm(formula, data=d, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": groups}
    )
    b, se = fit.params["year_c"], fit.bse["year_c"]
    return {
        "skill": col,
        "or_per_year": float(np.exp(b)),
        "lo": float(np.exp(b - 1.96 * se)),
        "hi": float(np.exp(b + 1.96 * se)),
        "p": float(fit.pvalues["year_c"]),
        "n": int(len(d)),
    }


def trends(df: pd.DataFrame, cols: list[str], extra: str = "") -> pd.DataFrame:
    out = pd.DataFrame([logistic_trend(df, c, extra=extra) for c in cols])
    ok = out["p"].notna()
    out.loc[ok, "p_bh"] = stats.benjamini_hochberg(out.loc[ok, "p"])
    return out

"""Statistics helpers: Wilson intervals, employer-cluster bootstrap, BH correction."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as st


def wilson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = st.norm.ppf(0.5 + level / 2)
    p = k / n
    den = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def cluster_bootstrap_shares(
    df: pd.DataFrame,
    value_cols: list[str],
    cluster_col: str,
    group_col: str | None = None,
    n_boot: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> pd.DataFrame:
    """Share of rows with value == True, with a percentile interval from resampling clusters.

    Ads from the same employer are not independent (same template, same stack), so
    whole employers are resampled within each group (e.g. year). Returns one row
    per (group, value_col): n, k, share, lo, hi, n_clusters, design_effect.
    """
    rng = np.random.default_rng(seed)
    groups = [(None, df)] if group_col is None else list(df.groupby(group_col, sort=True))
    alpha = (1 - level) / 2
    rows = []
    for g, d in groups:
        # Sum per cluster once; a bootstrap draw is then a weighted sum of clusters.
        agg = d.groupby(cluster_col)[value_cols].sum()
        size = d.groupby(cluster_col).size().reindex(agg.index).to_numpy()
        sums = agg.to_numpy(dtype=float)
        m = len(size)
        draws = rng.integers(0, m, size=(n_boot, m))
        counts = np.zeros((n_boot, m))
        for b in range(n_boot):
            counts[b] = np.bincount(draws[b], minlength=m)
        boot_n = counts @ size
        boot_k = counts @ sums  # n_boot x n_values
        boot_share = boot_k / boot_n[:, None]
        n = int(size.sum())
        for j, col in enumerate(value_cols):
            k = int(sums[:, j].sum())
            p = k / n if n else float("nan")
            lo, hi = np.quantile(boot_share[:, j], [alpha, 1 - alpha])
            var_srs = p * (1 - p) / n if n else float("nan")
            var_boot = float(np.var(boot_share[:, j], ddof=1))
            rows.append(
                {
                    "group": g,
                    "skill": col,
                    "n": n,
                    "k": k,
                    "share": p,
                    "lo": float(lo),
                    "hi": float(hi),
                    "n_clusters": m,
                    "design_effect": var_boot / var_srs if var_srs and var_srs > 0 else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def benjamini_hochberg(pvals) -> np.ndarray:
    """BH-adjusted p-values (monotone, capped at 1)."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(adj, 1.0)
    return out


def precision_recall(pred: pd.Series, gold: pd.Series) -> dict:
    """Precision and recall with Wilson intervals for one skill."""
    pred = pred.astype(bool)
    gold = gold.astype(bool)
    tp = int((pred & gold).sum())
    fp = int((pred & ~gold).sum())
    fn = int((~pred & gold).sum())
    out = {"tp": tp, "fp": fp, "fn": fn, "n": int(len(pred)), "gold_pos": tp + fn, "pred_pos": tp + fp}
    out["precision"] = tp / (tp + fp) if tp + fp else float("nan")
    out["precision_ci"] = wilson(tp, tp + fp)
    out["recall"] = tp / (tp + fn) if tp + fn else float("nan")
    out["recall_ci"] = wilson(tp, tp + fn)
    return out

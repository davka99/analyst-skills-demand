"""Static figures for the README (matplotlib).

Style follows the dataviz reference palette: one hue for a single series, fixed
categorical order (blue, orange) for two, recessive grid, thin marks, text in ink
colours (never the series colour), source and unit in every figure.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"  # categorical slot 1
ORANGE = "#eb6834"  # categorical slot 2
NEUTRAL = "#a3a29c"
SOURCE = "Source: JobTech/Arbetsförmedlingen historical ads (Platsbanken), own analysis."


def _setup():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK2,
            "xtick.color": INK2,
            "ytick.color": INK,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlecolor": INK,
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
        }
    )
    return plt


def _wrap(t: str, width: int = 70) -> str:
    return "\n".join(textwrap.wrap(t, width))


def _finish(fig, ax, path: Path, subtitle: str):
    ax.text(0, 1.01, _wrap(subtitle, 95), transform=ax.transAxes, color=INK2, fontsize=9, va="bottom")
    fig.text(0.01, -0.01, SOURCE, color=INK2, fontsize=7.5, ha="left", va="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)


def ranked_shares(df: pd.DataFrame, labels: dict, path: Path, title: str, subtitle: str, top: int = 20):
    """Horizontal dot + CI plot of shares, largest first (one series)."""
    plt = _setup()
    d = df.sort_values("share", ascending=False).head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(d) + 1.3))
    y = np.arange(len(d))
    ax.hlines(y, d["lo"] * 100, d["hi"] * 100, color=BLUE, linewidth=2, alpha=0.45)
    ax.scatter(d["share"] * 100, y, s=36, color=BLUE, zorder=3, edgecolor=SURFACE, linewidth=1.5)
    for yi, (s, hi) in enumerate(zip(d["share"], d["hi"])):
        ax.text(hi * 100 + 1, yi, f"{s * 100:.0f} %", va="center", fontsize=8, color=INK2)
    ax.set_yticks(y, [labels.get(k, k) for k in d["skill"]])
    ax.set_xlim(0, min(100, d["hi"].max() * 100 + 10))
    ax.set_xlabel("Share of ads mentioning the skill (%), 95 % employer-cluster bootstrap interval")
    ax.grid(axis="y", visible=False)
    ax.set_title(_wrap(title), pad=8 + 13 * len(textwrap.wrap(subtitle, 95)))
    _finish(fig, ax, path, subtitle)
    plt.close(fig)


def dumbbell(df: pd.DataFrame, labels: dict, path: Path, title: str, subtitle: str, a_label: str, b_label: str):
    """Early vs late share per skill (two series: neutral early, blue late), sorted by change."""
    plt = _setup()
    d = df.sort_values("diff").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7.5, 0.3 * len(d) + 1.4))
    y = np.arange(len(d))
    ax.hlines(y, d["share_a"] * 100, d["share_b"] * 100, color=GRID, linewidth=2.5, zorder=1)
    ax.scatter(d["share_a"] * 100, y, s=30, color=NEUTRAL, zorder=3, label=a_label, edgecolor=SURFACE, linewidth=1.2)
    ax.scatter(d["share_b"] * 100, y, s=36, color=BLUE, zorder=4, label=b_label, edgecolor=SURFACE, linewidth=1.2)
    for yi, r in d.iterrows():
        mark = "" if r.get("verdict", "") in ("", "no clear change") else ("  ▲" if r["diff"] > 0 else "  ▼")
        x = max(r["share_a"], r["share_b"]) * 100 + 1
        ax.text(x, yi, f"{r['diff'] * 100:+.0f} pp{mark}", va="center", fontsize=8, color=INK2)
    ax.set_yticks(y, [labels.get(k, k) for k in d["skill"]])
    ax.set_xlim(0, min(100, max(d["share_a"].max(), d["share_b"].max()) * 100 + 15))
    ax.set_xlabel("Share of ads mentioning the skill (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    ax.set_title(_wrap(title), pad=8 + 13 * len(textwrap.wrap(subtitle, 95)))
    _finish(fig, ax, path, subtitle)
    plt.close(fig)


def small_multiples(yearly: pd.DataFrame, keys: list[str], labels: dict, path: Path, title: str, subtitle: str, ncols: int = 4):
    """Yearly share with interval band, one panel per skill, shared y axis."""
    plt = _setup()
    nrows = int(np.ceil(len(keys) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(2.3 * ncols, 1.9 * nrows + 0.8), sharey=True, sharex=True)
    axes = np.atleast_1d(axes).ravel()
    ymax = min(100, yearly[yearly["skill"].isin(keys)]["hi"].max() * 100 + 5)
    for ax, k in zip(axes, keys):
        d = yearly[yearly["skill"] == k].sort_values("group")
        x = d["group"].astype(int)
        ax.fill_between(x, d["lo"] * 100, d["hi"] * 100, color=BLUE, alpha=0.15, linewidth=0)
        ax.plot(x, d["share"] * 100, color=BLUE, linewidth=2)
        ax.set_title(labels.get(k, k), fontsize=9.5, loc="left", pad=3)
        ax.set_ylim(0, ymax)
        ax.set_xticks([2016, 2020, 2025])
        ax.tick_params(labelsize=8)
    for ax in axes[len(keys):]:
        ax.set_visible(False)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.text(0.01, 0.985, _wrap(title, 90), ha="left", va="top", fontsize=12, fontweight="bold", color=INK)
    fig.text(0.01, 0.935, subtitle, color=INK2, fontsize=9, ha="left", va="top")
    fig.text(0.01, -0.01, SOURCE + " Share of ads (%), band = 95 % employer-cluster interval.", color=INK2, fontsize=7.5, ha="left", va="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def two_group_dots(df: pd.DataFrame, labels: dict, path: Path, title: str, subtitle: str, a: str, b: str):
    """Stockholm vs rest (blue vs orange) per skill, with intervals."""
    plt = _setup()
    d = df.sort_values("share_b").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7.5, 0.3 * len(d) + 1.4))
    y = np.arange(len(d))
    off = 0.17
    ax.hlines(y + off, d["lo_a"] * 100, d["hi_a"] * 100, color=ORANGE, linewidth=1.6, alpha=0.5)
    ax.hlines(y - off, d["lo_b"] * 100, d["hi_b"] * 100, color=BLUE, linewidth=1.6, alpha=0.5)
    ax.scatter(d["share_a"] * 100, y + off, s=26, color=ORANGE, label=a, zorder=3, edgecolor=SURFACE, linewidth=1.2)
    ax.scatter(d["share_b"] * 100, y - off, s=26, color=BLUE, label=b, zorder=3, edgecolor=SURFACE, linewidth=1.2)
    ax.set_yticks(y, [labels.get(k, k) for k in d["skill"]])
    ax.set_xlabel("Share of ads mentioning the skill (%), 95 % employer-cluster interval")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    ax.set_title(_wrap(title), pad=8 + 13 * len(textwrap.wrap(subtitle, 95)))
    _finish(fig, ax, path, subtitle)
    plt.close(fig)


def bars(x, y, path: Path, title: str, subtitle: str, ylabel: str, annotate_fmt: str = "{:.1f}"):
    plt = _setup()
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.bar(x, y, color=BLUE, width=0.6, edgecolor=SURFACE, linewidth=2)
    for xi, yi in zip(x, y):
        ax.text(xi, yi, annotate_fmt.format(yi), ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_ylim(0, max(y) * 1.15)
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)
    ax.set_xticks(list(x))
    ax.set_title(_wrap(title), pad=8 + 13 * len(textwrap.wrap(subtitle, 95)))
    _finish(fig, ax, path, subtitle)
    plt.close(fig)


VARIANT_LABELS = {
    "primary": "Primary",
    "no_agencies": "Without staffing/recruitment firms",
    "dedup_60_days": "Reposts within 60 days removed",
    "one_ad_per_employer_year": "One ad per employer and year",
    "narrow_titles": "Data/BI analyst titles only",
    "broad_titles": "Incl. BI developers and statisticians",
    "swedish_ads": "Swedish-language ads",
    "english_ads": "English-language ads",
}


def robustness_grid(rob: pd.DataFrame, keys: list[str], variants: list[str], labels: dict, path: Path, title: str, subtitle: str, ncols: int = 7):
    """One panel per skill: change (pp) with interval for each analysis variant."""
    plt = _setup()
    nrows = int(np.ceil(len(keys) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(2.1 * ncols + 2.2, 0.28 * len(variants) * nrows + 1.6), sharey=True)
    axes = np.atleast_1d(axes).ravel()
    y = np.arange(len(variants))[::-1]
    for ax, k in zip(axes, keys):
        d = rob[rob["skill"] == k].set_index("variant").reindex(variants)
        col = [BLUE if v == "primary" else NEUTRAL for v in variants]
        ax.axvline(0, color=INK2, linewidth=0.8)
        ax.hlines(y, d["lo"] * 100, d["hi"] * 100, color=col, linewidth=1.6, alpha=0.7)
        ax.scatter(d["diff"] * 100, y, s=16, color=col, zorder=3)
        ax.set_title(labels.get(k, k), fontsize=9, loc="left", pad=3)
        ax.tick_params(labelsize=7.5)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, [VARIANT_LABELS.get(v, v) for v in variants])
    if nrows > 1:
        axes[ncols].set_yticks(y, [VARIANT_LABELS.get(v, v) for v in variants])
    for ax in axes[len(keys):]:
        ax.set_visible(False)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.text(0.01, 0.985, _wrap(title, 110), ha="left", va="top", fontsize=12, fontweight="bold", color=INK)
    fig.text(0.01, 0.94, subtitle, color=INK2, fontsize=9, ha="left", va="top")
    fig.text(0.01, -0.01, SOURCE, color=INK2, fontsize=7.5, ha="left", va="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)

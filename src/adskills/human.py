"""Human check of the annotation (README limitation "annotation was AI-assisted").

The repository owner labels a random subsample of the *test* sample blind, using only
`docs/annotation_guide.md` and the ad text, for the main skills below. The labels are then
compared with (a) the adjudicated AI-assisted reference and (b) the frozen dictionary.

Ad text is never committed (D16): the kit with texts is built in GitHub Actions and
downloaded as a short-lived artifact; only the 0/1 labels are committed.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from . import validation

N_HUMAN = 40
HUMAN_SKILLS = (
    "sql", "python", "r", "excel", "power_bi", "tableau", "sas", "looker",
    "azure", "aws", "gcp", "statistics", "visualization", "communication", "degree",
)
LABELS_FILE = "human_labels.csv"


def draw(sample_ids: pd.DataFrame, n: int = N_HUMAN, seed: int = 0) -> pd.DataFrame:
    """Random subsample of the test sample, in a shuffled order (years mixed)."""
    test = sample_ids[sample_ids["sample"] == "test"].sort_values("ann_id").reset_index(drop=True)
    if len(test) < n:
        raise ValueError(f"test sample has {len(test)} ads, need {n}")
    rng = np.random.default_rng(seed)
    return test.iloc[rng.permutation(len(test))[:n]].reset_index(drop=True)


def write_kit(sample: pd.DataFrame, texts: pd.DataFrame, folder: Path) -> Path:
    """Two files for the annotator: the texts (read) and an empty label sheet (fill in).

    `texts` is indexed by ad id with columns headline, description. The label sheet is a
    semicolon-separated CSV with a BOM so that Excel with Swedish settings opens it in
    columns.
    """
    folder.mkdir(parents=True, exist_ok=True)
    missing = sorted(set(sample["id"]) - set(texts.index))
    if missing:
        raise KeyError(f"no text for {len(missing)} sampled ads, e.g. {missing[:3]}")
    with open(folder / "human_texts.md", "w", encoding="utf-8") as fh:
        fh.write("# Ads to label (do not commit this file)\n\n")
        for r in sample.itertuples():
            t = validation.ad_text(texts.loc[r.id, "headline"], texts.loc[r.id, "description"])
            fh.write(f"## {r.ann_id}\n\n{t}\n\n")
    sheet = folder / LABELS_FILE
    with open(sheet, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["ann_id", *HUMAN_SKILLS, "note"])
        for r in sample.itertuples():
            w.writerow([r.ann_id, *[""] * len(HUMAN_SKILLS), ""])
    return sheet


def load_labels(path: Path) -> pd.DataFrame:
    """Filled label sheet -> boolean frame indexed by ann_id. Every cell must be 0 or 1."""
    df = pd.read_csv(path, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    missing_cols = set(HUMAN_SKILLS) - set(df.columns)
    if missing_cols:
        raise ValueError(f"label sheet lacks columns {sorted(missing_cols)}")
    df = df.set_index("ann_id")[list(HUMAN_SKILLS)].apply(lambda s: s.str.strip())
    bad = ~df.isin(["0", "1"])
    if bad.any().any():
        where = [(i, c) for i, c in zip(*np.where(bad.to_numpy()), strict=True)][:5]
        cells = [(df.index[i], df.columns[c]) for i, c in where]
        raise ValueError(f"cells must be 0 or 1; first problems: {cells}")
    return df.astype(int).astype(bool)


def cohen_kappa(a: pd.Series, b: pd.Series) -> float | None:
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    po = float(np.mean(a == b))
    pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def agreement(human: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """Per skill on the common ann_ids: positives, raw agreement and Cohen's kappa."""
    common = human.index.intersection(other.index)
    rows = []
    for k in HUMAN_SKILLS:
        h, o = human.loc[common, k], other.loc[common, k]
        rows.append({"skill": k, "n": int(len(common)), "human_pos": int(h.sum()),
                     "other_pos": int(o.sum()), "agree_pct": round(100 * float((h == o).mean()), 1),
                     "kappa": cohen_kappa(h, o)})
    return pd.DataFrame(rows)


def summary(table: pd.DataFrame) -> dict:
    """Pooled agreement over all skill x ad cells, and the skills below kappa 0.6."""
    n_cells = int(table["n"].sum())
    agree = float((table["agree_pct"] * table["n"]).sum() / max(n_cells, 1))
    low = table[(table["kappa"].notna()) & (table["kappa"] < 0.6)]["skill"].tolist()
    return {"cells": n_cells, "agree_pct": round(agree, 1),
            "median_kappa": float(table["kappa"].dropna().median()) if table["kappa"].notna().any()
            else None,
            "skills_kappa_below_0_6": low}

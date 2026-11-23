"""Skill-extraction validation (M4): samples, annotation batches and metrics."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import skills, stats

_WS = re.compile(r"\s+")


def draw_sample(df: pd.DataFrame, per_year: int, seed: int, exclude=()) -> pd.DataFrame:
    """Simple random sample of `per_year` ads within each publication year."""
    rng = np.random.default_rng(seed)
    pool = df[~df["id"].isin(set(exclude))]
    parts = []
    for _, g in pool.groupby("year", sort=True):
        take = min(per_year, len(g))
        idx = rng.choice(len(g), size=take, replace=False)
        parts.append(g.iloc[np.sort(idx)])
    return pd.concat(parts).reset_index(drop=True)


def ad_text(headline, description, limit: int = 7000) -> str:
    t = f"{headline or ''}\n\n{description or ''}"
    t = _WS.sub(" ", t).strip()
    return t if len(t) <= limit else t[:limit] + " [...]"


def export_batch(sample: pd.DataFrame, prefix: str, path: Path, start: int = 0) -> pd.DataFrame:
    """Write ann_id + text for annotators; return the id mapping (ann_id -> ad id)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = [f"{prefix}{start + i + 1:03d}" for i in range(len(sample))]
    with open(path, "w", encoding="utf-8") as fh:
        for ann_id, (_, r) in zip(ids, sample.iterrows()):
            fh.write(json.dumps({"ann_id": ann_id, "text": ad_text(r["headline"], r["description"])}, ensure_ascii=False) + "\n")
    return pd.DataFrame({"ann_id": ids, "id": sample["id"].to_numpy(), "year": sample["year"].to_numpy()})


def load_annotations(paths) -> pd.DataFrame:
    """Annotation JSON lines -> boolean matrix indexed by ann_id (unknown keys raise)."""
    rows = {}
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            unknown = set(r["skills"]) - set(skills.SKILL_KEYS)
            if unknown:
                raise ValueError(f"{r['ann_id']}: unknown skill keys {sorted(unknown)}")
            rows[r["ann_id"]] = set(r["skills"])
    return pd.DataFrame({k: [k in v for v in rows.values()] for k in skills.SKILL_KEYS}, index=list(rows), dtype=bool)


def dictionary_labels(batch_path: Path) -> pd.DataFrame:
    """Dictionary output on exactly the text the annotators saw."""
    recs = [json.loads(x) for x in Path(batch_path).read_text(encoding="utf-8").splitlines() if x.strip()]
    m = skills.skill_matrix([r["text"] for r in recs])
    m.index = [r["ann_id"] for r in recs]
    return m


def evaluate(pred: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    """Precision/recall per skill on the common ann_ids."""
    common = pred.index.intersection(gold.index)
    rows = []
    for k in skills.SKILL_KEYS:
        r = stats.precision_recall(pred.loc[common, k], gold.loc[common, k])
        rows.append({"skill": k, **r})
    return pd.DataFrame(rows)


def disagreements(pred: pd.DataFrame, gold: pd.DataFrame, batch_path: Path | None = None, width: int = 80) -> list[dict]:
    """Every (ad, skill) where dictionary and annotation differ.

    With a batch file (ad text, only available after `fetch`), the matched text is
    added as context; the committed report has no ad text (D16).
    """
    recs = {}
    if batch_path is not None:
        recs = {json.loads(x)["ann_id"]: json.loads(x)["text"] for x in Path(batch_path).read_text(encoding="utf-8").splitlines() if x.strip()}
    out = []
    common = pred.index.intersection(gold.index)
    if recs:
        common = common.intersection(list(recs))
    for ann_id in common:
        for k in skills.SKILL_KEYS:
            p, g = bool(pred.loc[ann_id, k]), bool(gold.loc[ann_id, k])
            if p == g:
                continue
            row = {"ann_id": ann_id, "skill": k, "dictionary": p, "annotator": g}
            if recs:
                ctx = []
                if p:
                    t = recs[ann_id].lower()
                    for m in skills._BY_KEY[k].pattern.finditer(t):
                        ctx.append(t[max(0, m.start() - width) : m.end() + width])
                row["context"] = ctx[:3]
            out.append(row)
    return out


def apply_adjudication(gold: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Override annotator labels with adjudicated ones (every override has a reason)."""
    adj = pd.read_csv(path, dtype={"ann_id": str})
    out = gold.copy()
    for r in adj.itertuples():
        if bool(out.loc[r.ann_id, r.skill]) != bool(r.annotator):
            raise ValueError(f"{r.ann_id}/{r.skill}: annotator label in file does not match the annotation")
        out.loc[r.ann_id, r.skill] = bool(r.adjudicated)
    return out

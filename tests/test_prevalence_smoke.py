"""Offline smoke test of the prevalence stage on synthetic ads (needs statsmodels)."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from adskills import config

ROOT = Path(__file__).resolve().parents[1]


def test_prevalence_stage_runs_on_synthetic_data(tmp_path, monkeypatch):
    pytest.importorskip("statsmodels")
    from adskills import skills

    rng = np.random.default_rng(0)
    rows = []
    for i in range(600):
        year = int(rng.integers(2016, 2026))
        row = {"id": str(i), "year": year, "pub_date": f"{year}-03-01", "category": rng.choice(["data_analyst", "analytics_analyst"]),
               "employer_key": f"e{rng.integers(0, 120)}", "area": rng.choice(["Stockholm", "Rest of Sweden", "Unknown"], p=[0.6, 0.35, 0.05]),
               "desc_len": 400, "agency": 0, "genai_terms": ""}
        row.update({k: 0 for k in skills.SKILL_KEYS})
        row.update({"sql": int(rng.random() < 0.2 + 0.03 * (year - 2016)), "excel": int(rng.random() < 0.3),
                    "power_bi": int(rng.random() < 0.15), "communication": int(rng.random() < 0.5)})
        rows.append(row)
    proc = tmp_path / "processed"
    proc.mkdir()
    pd.DataFrame(rows).to_csv(proc / "analyst_ads.csv.gz", index=False)
    rep = tmp_path / "reports"
    rep.mkdir()
    val = [{"skill": k, "precision": 1.0, "recall": 1.0, "pred_pos": 1, "gold_pos": 1} for k in
           __import__("adskills.skills", fromlist=["x"]).SKILL_KEYS]
    (rep / "validation.json").write_text(json.dumps({"test": {"adjudicated": val}}), encoding="utf-8")
    monkeypatch.setattr(config, "DATA_PROCESSED", proc)
    monkeypatch.setattr(config, "REPORTS", rep)
    monkeypatch.setattr(config, "FIGURES", rep / "figures")
    spec = importlib.util.spec_from_file_location("rp", ROOT / "scripts" / "run_pipeline.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    rp.prevalence()
    out = json.loads((rep / "prevalence.json").read_text(encoding="utf-8"))
    sql = {r["skill"]: r for r in out["change"]["pooled"]}["sql"]
    assert sql["diff"] > 0 and sql["or_per_year"] > 1
    assert len(list((rep / "figures").glob("*.png"))) == 4

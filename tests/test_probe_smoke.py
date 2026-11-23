"""Offline smoke test of the probe stage with a fake HTTP session."""

import importlib.util
import json
from pathlib import Path

import pytest

from adskills import config

from test_jobtech import ad, write_zip

ROOT = Path(__file__).resolve().parents[1]


def load_pipeline():
    spec = importlib.util.spec_from_file_location("run_pipeline", ROOT / "scripts" / "run_pipeline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeResp:
    def __init__(self, status=200, text="", body=b"", headers=None, json_obj=None):
        self.status_code = status
        self.ok = status < 400
        self.text = text
        self._body = body
        self.headers = headers or {}
        self._json = json_obj

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            yield self._body[i : i + n]

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeSession:
    def __init__(self, zip_bytes):
        self.zip_bytes = zip_bytes
        self.headers = {}

    def get(self, url, **kw):
        if url.endswith("historiska/"):
            return FakeResp(text='<a href="../">..</a><a href="2023.zip">a</a><a href="2024.zip">b</a><a href="berikade/">c</a>')
        if url.endswith("berikade/"):
            return FakeResp(text='<a href="2024_enriched.zip">x</a>')
        if url.endswith(".zip"):
            return FakeResp(body=self.zip_bytes)
        if "/search" in url:
            return FakeResp(json_obj={"total": {"value": 3}, "hits": []})
        return FakeResp(status=404)

    def head(self, url, **kw):
        return FakeResp(headers={"content-length": "123"})


def test_probe_offline(tmp_path, monkeypatch):
    recs = [ad(1, "Dataanalytiker", desc="SQL, Python och Power BI"), ad(2, "Busschaufför", occupation={"label": "Busschaufför"}, occupation_group={"label": "Buss"}), ad(3, "Analytiker")]
    z = write_zip(tmp_path / "src.zip", recs, "jsonl").read_bytes()
    rp = load_pipeline()
    monkeypatch.setattr(rp, "_session", lambda: FakeSession(z))
    monkeypatch.setattr(config, "DATA_RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "DATA_TMP", tmp_path / "tmp")
    rp.probe()
    s = json.loads((tmp_path / "raw" / "_probe" / "probe_summary.json").read_text(encoding="utf-8"))
    assert s["probe_year"] == 2024
    assert s["schema_ok"] is True
    assert s["scan"]["n_records"] == 3
    assert s["population_n"] == 1
    assert s["skill_share_v0_probe_year"]["power_bi"] == 1.0
    assert s["historical_api"]["status"] == 200
    assert s["candidates_sample_headlines"] == ["Analytiker"]
    assert sorted(s["year_file_sizes"]) == ["2023", "2024"]


def test_fetch_offline_writes_extract_and_resumes(tmp_path, monkeypatch, capsys):
    import gzip

    recs = [
        ad(2, "BI-analytiker", desc="Power BI"),
        ad(1, "Dataanalytiker", desc="SQL"),
        ad(3, "Analytiker"),
        ad(4, "Busschaufför", occupation={"label": "Busschaufför"}, occupation_group={"label": "Buss"}),
    ]
    z = write_zip(tmp_path / "src.zip", recs, "jsonl").read_bytes()
    rp = load_pipeline()
    monkeypatch.setattr(rp, "_session", lambda: FakeSession(z))
    monkeypatch.setattr(config, "DATA_RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "DATA_TMP", tmp_path / "tmp")
    rp.fetch(years=(2024,))
    ext = tmp_path / "raw" / "extract"
    rows = [json.loads(line) for line in gzip.open(ext / "ads_2024.jsonl.gz", "rt", encoding="utf-8")]
    assert [r["id"] for r in rows] == ["1", "2"]  # sorted by id, only classified headlines
    assert rows[0]["description"] == "SQL" and rows[0]["category"] == "data_analyst"
    cand = gzip.open(ext / "candidates_2024.csv.gz", "rt", encoding="utf-8").read().splitlines()
    assert len(cand) == 2 and "Analytiker" in cand[1]
    m = json.loads((tmp_path / "raw" / "fetch_manifest.json").read_text(encoding="utf-8"))
    assert m["years"]["2024"]["n_records"] == 4
    assert m["years"]["2024"]["records_outside_year"] == 0
    assert not list((tmp_path / "tmp").glob("*.zip"))  # download deleted
    capsys.readouterr()
    rp.fetch(years=(2024,))
    assert "already fetched" in capsys.readouterr().out


def test_build_and_quality_stage_offline(tmp_path, monkeypatch):
    import gzip

    recs = [ad(1, "Dataanalytiker", desc="SQL"), ad(2, "Dataanalytiker", desc="SQL"), ad(3, "BI-utvecklare"), ad(4, "Kundanalytiker", region=None)]
    z = write_zip(tmp_path / "src.zip", recs, "jsonl").read_bytes()
    rp = load_pipeline()
    monkeypatch.setattr(rp, "_session", lambda: FakeSession(z))
    monkeypatch.setattr(config, "DATA_RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "DATA_TMP", tmp_path / "tmp")
    monkeypatch.setattr(config, "DATA_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(config, "REPORTS", tmp_path / "reports")
    rp.fetch(years=(2024,))
    rp.build()
    feats = gzip.open(tmp_path / "processed" / "ads_features.csv.gz", "rt", encoding="utf-8").read()
    assert "SQL och Python" not in feats and "description" not in feats.splitlines()[0]  # no ad text (D16)
    rp.quality_stage()
    s = json.loads((tmp_path / "reports" / "data_quality_summary.json").read_text(encoding="utf-8"))
    # ads 1 and 2: same org. number, headline and text -> repost
    assert s["dropped_in_window"] == {"repost": 1}
    assert s["rows_final"] == 2
    assert s["denominators"]["total_by_year"] == {"2024": 4}
    assert s["denominators"]["by_year_area"] == {"2024|Stockholm": 3, "2024|Unknown": 1}
    import pandas as pd

    final = pd.read_csv(tmp_path / "processed" / "analyst_ads.csv.gz")
    assert set(final["area"]) == {"Stockholm", "Unknown"}
    assert final.loc[final["category"] == "data_analyst", "sql"].tolist() == [1]
    # building twice gives byte-identical files
    b1 = (tmp_path / "processed" / "ads_features.csv.gz").read_bytes()
    rp.build()
    assert (tmp_path / "processed" / "ads_features.csv.gz").read_bytes() == b1


def test_file_list_uses_enriched_files():
    rp = load_pipeline()
    base, files = rp._file_list(None)
    assert files[0] == ("2016", "/annonser/historiska/berikade/kompletta/2016_beta1_jsonl.zip")
    assert files[-1] == ("2026-Q1", "/annonser/historiska/berikade/kompletta/2026-Q1_beta1_jsonl.zip")
    assert len(files) == 11

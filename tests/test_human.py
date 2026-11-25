"""Human-check helpers (adskills.human). All data in this file are synthetic."""

import pandas as pd
import pytest

from adskills import human


def _ids(n=60):
    return pd.DataFrame({"ann_id": [f"T{i:03d}" for i in range(1, n + 1)],
                         "id": [f"ad{i}" for i in range(1, n + 1)],
                         "year": 2020, "sample": "test", "batch": 1})


def test_draw_is_reproducible_and_from_test_only():
    ids = pd.concat([_ids(), _ids(10).assign(sample="dev", ann_id=lambda d: "D" + d["ann_id"])])
    a, b = human.draw(ids, n=40, seed=1), human.draw(ids, n=40, seed=1)
    assert a["ann_id"].tolist() == b["ann_id"].tolist()
    assert len(set(a["ann_id"])) == 40 and a["ann_id"].str.startswith("T").all()
    with pytest.raises(ValueError):
        human.draw(_ids(10), n=40)


def test_kit_round_trip(tmp_path):
    sample = human.draw(_ids(), n=5, seed=0)
    texts = pd.DataFrame({"headline": "Data analyst", "description": "SQL och Python"},
                         index=[f"ad{i}" for i in range(1, 61)])
    sheet = human.write_kit(sample, texts, tmp_path)
    assert (tmp_path / "human_texts.md").read_text(encoding="utf-8").count("## T") == 5
    df = pd.read_csv(sheet, sep=";", encoding="utf-8-sig", dtype=str)
    df[list(human.HUMAN_SKILLS)] = "0"
    df.loc[0, "sql"] = "1"
    df.to_csv(sheet, sep=";", index=False, encoding="utf-8-sig")
    lab = human.load_labels(sheet)
    assert lab.shape == (5, len(human.HUMAN_SKILLS))
    assert lab["sql"].sum() == 1


def test_load_labels_rejects_blank_cells(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("ann_id;" + ";".join(human.HUMAN_SKILLS) + ";note\nT001;" +
                 ";".join(["0"] * (len(human.HUMAN_SKILLS) - 1)) + ";;\n", encoding="utf-8")
    with pytest.raises(ValueError):
        human.load_labels(p)


def test_kappa_and_agreement():
    a = pd.Series([1, 1, 0, 0, 1, 0, 0, 0], dtype=bool)
    assert human.cohen_kappa(a, a) == 1.0
    assert human.cohen_kappa(a, ~a) == pytest.approx(-0.882, abs=1e-3)  # po = 0, pe = 30/64
    idx = [f"T{i}" for i in range(8)]
    h = pd.DataFrame({k: a.to_numpy() for k in human.HUMAN_SKILLS}, index=idx)
    o = h.copy()
    o.loc["T0", "sql"] = False
    t = human.agreement(h, o).set_index("skill")
    assert t.loc["sql", "agree_pct"] == 87.5
    assert t.loc["python", "kappa"] == 1.0
    s = human.summary(t.reset_index())
    assert s["skills_kappa_below_0_6"] == []

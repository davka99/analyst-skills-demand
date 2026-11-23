import json

import pandas as pd
import pytest

from adskills import validation


def frame():
    return pd.DataFrame({"id": [str(i) for i in range(30)], "year": [2016] * 10 + [2017] * 20,
                         "headline": ["Dataanalytiker"] * 30, "description": ["SQL och Python"] * 30})


def test_draw_sample_stratified_and_disjoint():
    df = frame()
    a = validation.draw_sample(df, 5, seed=1)
    b = validation.draw_sample(df, 5, seed=1, exclude=a["id"])
    assert a.groupby("year").size().tolist() == [5, 5]
    assert not set(a["id"]) & set(b["id"])
    assert a["id"].tolist() == validation.draw_sample(df, 5, seed=1)["id"].tolist()  # reproducible


def test_export_and_evaluate_roundtrip(tmp_path):
    df = frame().head(3)
    df.loc[2, "description"] = "Excellent R&D team"
    mapping = validation.export_batch(df, "D", tmp_path / "batch.jsonl")
    assert mapping["ann_id"].tolist() == ["D001", "D002", "D003"]
    ann = tmp_path / "ann.jsonl"
    ann.write_text("\n".join(json.dumps(r) for r in [
        {"ann_id": "D001", "skills": ["sql", "python"]},
        {"ann_id": "D002", "skills": ["sql"]},  # annotator missed python
        {"ann_id": "D003", "skills": []},
    ]), encoding="utf-8")
    gold = validation.load_annotations([ann])
    pred = validation.dictionary_labels(tmp_path / "batch.jsonl")
    ev = validation.evaluate(pred, gold).set_index("skill")
    assert ev.loc["sql", "precision"] == 1.0 and ev.loc["sql", "recall"] == 1.0
    assert ev.loc["python", "fp"] == 1
    dis = validation.disagreements(pred, gold, tmp_path / "batch.jsonl")
    assert dis == [{"ann_id": "D002", "skill": "python", "dictionary": True, "annotator": False,
                    "context": [dis[0]["context"][0]]}]
    assert "python" in dis[0]["context"][0]


def test_unknown_skill_key_raises(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text(json.dumps({"ann_id": "X", "skills": ["kotlin"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="kotlin"):
        validation.load_annotations([p])

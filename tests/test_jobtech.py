import json
import zipfile

import pytest

from adskills import jobtech


def ad(i, headline="Dataanalytiker", region="Stockholms län", desc="SQL och Python", **extra):
    rec = {
        "id": str(i),
        "headline": headline,
        "publication_date": "2024-03-01T10:00:00",
        "description": {"text": desc},
        "employer": {"name": f"Employer {i % 3}", "organization_number": "5560000000"},
        "occupation": {"label": "Dataanalytiker", "concept_id": "abc"},
        "occupation_group": {"label": "Analytiker"},
        "workplace_address": {"region": region, "municipality": "Stockholm"},
        "number_of_vacancies": 1,
    }
    rec.update(extra)
    return rec


def write_zip(path, records, fmt):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if fmt == "jsonl":
            zf.writestr("2024.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
        else:
            zf.writestr("2024.json", "  \n" + json.dumps(records, ensure_ascii=False))
    return path


@pytest.mark.parametrize("fmt", ["jsonl", "array"])
def test_iter_records_both_formats(tmp_path, fmt):
    if fmt == "array":
        pytest.importorskip("ijson")
    recs = [ad(i) for i in range(5)]
    p = write_zip(tmp_path / f"2024_{fmt}.zip", recs, fmt)
    got = list(jobtech.iter_records(p))
    assert [r["id"] for r in got] == [str(i) for i in range(5)]
    assert got[0]["description"]["text"] == "SQL och Python"


def test_iter_records_plain_jsonl(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text("\n".join(json.dumps(ad(i)) for i in range(3)), encoding="utf-8")
    assert len(list(jobtech.iter_records(p))) == 3


def test_zip_without_json_fails_loudly(tmp_path):
    p = tmp_path / "bad.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("readme.txt", "hello")
    with pytest.raises(jobtech.SchemaError):
        list(jobtech.iter_records(p))


def test_get_path_and_flatten():
    rec = ad(1)
    assert jobtech.get_path(rec, "workplace_address.region") == "Stockholms län"
    assert jobtech.get_path(rec, "workplace_address.nope") is None
    assert jobtech.get_path(rec, "headline.x") is None
    row = jobtech.flatten(rec)
    assert row["description"] == "SQL och Python"
    assert row["employer_name"] == "Employer 1"
    assert row["remote"] is None


def test_list_valued_taxonomy_fields_use_first_concept():
    # 2024 files store occupation as a list of concepts (M1 probe).
    rec = ad(1, occupation=[{"label": "Dataanalytiker", "concept_id": "a"}, {"label": "X"}], occupation_group=[])
    row = jobtech.flatten(rec)
    assert row["occupation"] == "Dataanalytiker"
    assert row["occupation_group"] is None


def test_flatten_accepts_plain_string_description():
    rec = ad(1)
    rec["description"] = "plain text"
    assert jobtech.flatten(rec)["description"] == "plain text"


def test_check_schema_raises_when_required_missing():
    recs = [{"id": "1", "headline": "x"} for _ in range(10)]
    with pytest.raises(jobtech.SchemaError, match="publication_date"):
        jobtech.check_schema(recs)
    shares = jobtech.check_schema([ad(i) for i in range(10)])
    assert shares["headline"] == 1.0


def test_key_paths():
    paths = jobtech.key_paths({"a": {"b": 1}, "c": [{"d": 2}]})
    assert paths == ["a", "a.b", "c", "c[].d"]


def test_listing_and_year_files():
    html = (
        '<a href="../">../</a><a href="?C=N;O=D">sort</a><a href="2016.zip">2016.zip</a>'
        '<a href="2017.zip">2017.zip</a><a href="2017_beta1.zip">x</a><a href="berikade/">berikade/</a>'
        '<a href="README.txt">README</a>'
    )
    links = jobtech.parse_listing(html)
    assert "../" not in links and "2016.zip" in links and "berikade/" in links
    yf = jobtech.year_files(links)
    assert sorted(yf) == [2016, 2017]
    assert jobtech.pick_year_file(yf[2017]) == "2017.zip"
    assert jobtech.pick_year_file(["2020_b.zip", "2020_beta1_x.zip"]) == "2020_b.zip"


def test_listing_with_absolute_paths_as_on_jobtech():
    # Real layout seen in the M1 probe (data/raw/_probe/listings/).
    html = (
        '<a href="/">Start</a><a href="/annonser">annonser</a>'
        '<a href="/annonser/historiska/berikade/index.html">berikade</a>'
        '<a href="/annonser/historiska/2018.jsonl.zip">x</a>'
        '<a href="/annonser/historiska/2018_municipality_patched.zip">x</a>'
        '<a href="/annonser/historiska/2026-Q1.jsonl.zip">x</a>'
        '<a href="https://gitlab.com/x">code</a>'
    )
    links = jobtech.parse_listing(html)
    assert "/" not in links
    yf = jobtech.year_files(links)
    assert sorted(yf) == [2018, 2026]
    assert jobtech.pick_year_file(yf[2018]) == "/annonser/historiska/2018.jsonl.zip"


def test_old_schema_fallbacks():
    # Raw 2016 layout (schema stage): id null, region null, municipality code present.
    rec = ad(1, workplace_address={"region": None, "municipality_code": "0180"})
    rec["id"] = None
    row = jobtech.flatten(rec)
    assert row["id"].startswith("h:") and row["id_source"] == "hash"
    assert row["id"] == jobtech.flatten(rec)["id"]  # stable
    assert row["region"] == "Stockholms län" and row["region_source"] == "municipality_code"
    row2 = jobtech.flatten(ad(2))
    assert row2["id_source"] == "id" and row2["region_source"] == "region"
    rec3 = ad(3, workplace_address={"region": None, "municipality_code": None})
    assert jobtech.flatten(rec3)["region"] is None


def test_text_fallbacks():
    rec = ad(1)
    rec["description"] = {"text": None, "text_formatted": "<p>SQL</p>", "needs": "x"}
    row = jobtech.flatten(rec)
    assert row["description"] == "<p>SQL</p>" and row["text_source"] == "text_formatted"
    rec["description"] = {"text": None, "text_formatted": None, "company_information": "Om oss", "requirements": "Python"}
    row = jobtech.flatten(rec)
    assert row["description"] == "Om oss\nPython" and row["text_source"] == "parts"
    rec["description"] = {"text": None}
    assert jobtech.flatten(rec)["text_source"] is None


def test_check_schema_tolerates_partial_gaps():
    recs = [ad(i) for i in range(10)]
    for r in recs[:3]:
        r["description"] = {"text": None}
    assert jobtech.check_schema(recs)["description"] == 0.7

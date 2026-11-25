import gzip
import json

import pandas as pd

from adskills import quality


def row(i, headline="Dataanalytiker", date="2020-03-01", employer="Acme AB", orgnr="556000-0001", desc="SQL och Python", region="Stockholms län", category="data_analyst", file_order=0, **kw):
    r = dict(id=str(i), headline=headline, publication_date=f"{date}T09:00:00", employer_name=employer, employer_orgnr=orgnr,
             description=desc, region=region, category=category, file_order=file_order, language="sv", vacancies=1)
    r.update(kw)
    return r


def frame(rows):
    return quality.prepare(pd.DataFrame(rows))


def test_keys_and_flags():
    assert quality.headline_key("Data-Analytiker!") == "data analytiker"
    assert quality.text_hash("SQL  och <b>Python</b>") == quality.text_hash("sql och python")
    assert quality.employer_key("Acme", "556000-0001") == "org:5560000001"
    assert quality.employer_key("Acme AB", None) == "name:acme ab"
    assert quality.is_agency("Academic Work Sweden AB")
    assert quality.is_agency("Teknikbemanning i Norr AB")
    assert not quality.is_agency("Framework Consulting AB")
    assert not quality.is_agency("Region Stockholm")


def test_prepare_area_and_year():
    df = frame([row(1), row(2, region=None), row(3, region="Skåne län", date="2019-12-31")])
    assert df["area"].tolist() == ["Stockholm", "Unknown", "Rest of Sweden"]
    assert df["year"].tolist() == [2020, 2020, 2019]


def test_deduplicate_same_id_and_repost():
    rows = [
        row(1, file_order=0),
        row(1, file_order=1),  # same id in the next file
        row(2, date="2020-05-01"),  # repost: same employer, headline, text, same year
        row(3, date="2021-01-10"),  # same content but next year: kept by the primary rule
        row(4, desc="Annan text"),  # different text: kept
        row(5, employer="Other AB", orgnr=None),  # other employer: kept
    ]
    d = quality.deduplicate(frame(rows))
    reasons = dict(zip(d["id"] + "_" + d["file_order"].astype(str), d["drop_reason"]))
    assert reasons["1_0"] is None and reasons["1_1"] == "same_id"
    assert reasons["2_0"] == "repost"
    assert reasons["3_0"] is None and reasons["4_0"] is None and reasons["5_0"] is None


def test_deduplicate_window_variant():
    rows = [row(1, date="2020-01-01"), row(2, date="2020-02-15"), row(3, date="2020-06-01"), row(4, date="2020-06-20")]
    d = quality.deduplicate(frame(rows), window_days=60).set_index("id")
    assert d.loc["2", "drop_reason"] == "repost"  # 45 days after 1
    assert d.loc["3", "drop_reason"] is None  # 152 days after 1: new chain
    assert d.loc["4", "drop_reason"] == "repost"  # 19 days after 3


def test_analysis_frame_and_summary():
    rows = [row(1), row(2, headline="BI-utvecklare", category="bi_developer"), row(3, date="2015-12-30"), row(4, date="2020-07-01", desc="x")]
    d = quality.deduplicate(frame(rows))
    final = quality.analysis_frame(d)
    assert sorted(final["id"]) == ["1", "4"]
    s = quality.summary(d, final)
    assert s["rows_final"] == 2 and s["final_by_year"] == {2020: 2}
    assert s["top10_employer_share"] == 1.0


def test_load_extract(tmp_path):
    for label, ids in (("2016", ["a"]), ("2017", ["a", "b"])):
        with gzip.open(tmp_path / f"ads_{label}.jsonl.gz", "wt", encoding="utf-8") as fh:
            for i in ids:
                fh.write(json.dumps(row(i)) + "\n")
    df = quality.load_extract(tmp_path)
    assert df["file_label"].tolist() == ["2016", "2017", "2017"]
    assert df["file_order"].tolist() == [0, 1, 1]


def test_public_employer_name_hides_sole_traders():
    from adskills.quality import PRIVATE_EMPLOYER, public_employer_name

    assert public_employer_name("Acme AB", "556559-5450") == "Acme AB"
    assert public_employer_name("Region Stockholm", "232100-0016") == "Region Stockholm"
    # A sole trader's org. number is the owner's personal identity number.
    assert public_employer_name("Anna Andersson", "850101-1234") == PRIVATE_EMPLOYER
    assert public_employer_name("Okänd", None) == "Okänd"

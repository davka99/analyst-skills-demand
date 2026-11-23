import subprocess
import sys
from pathlib import Path

from adskills import scan

from test_jobtech import ad

ROOT = Path(__file__).resolve().parents[1]


def test_scan_counts_and_extract():
    recs = [
        ad(1, "Dataanalytiker"),
        ad(2, "BI-utvecklare"),
        ad(3, "Busschaufför", region=None, occupation={"label": "Busschaufför"}, occupation_group={"label": "Buss"}),
        ad(4, "Analytiker"),  # unclassified headline, analytical occupation -> candidate
        ad(5, "Kundanalytiker", publication_date="2024-04-02"),
    ]
    res = scan.scan(recs)
    assert res.n_records == 5
    assert res.by_category["data_analyst"] == 1
    assert res.by_category["(none)"] == 2
    assert res.by_region["(none)"] == 1
    assert res.by_month == {"2024-03": 4, "2024-04": 1}
    assert [r["id"] for r in res.extract] == ["1", "2", "5"]
    assert [c["id"] for c in res.candidates] == ["4"]
    assert res.missing["region"] == 1
    s = res.summary()
    assert s["n_extract"] == 3 and s["n_candidates"] == 1


def test_scan_keep_filter():
    res = scan.scan([ad(1, "Dataanalytiker"), ad(2, "BI-utvecklare")], keep={"data_analyst"})
    assert [r["category"] for r in res.extract] == ["data_analyst"]


def test_vacancies_fallback():
    res = scan.scan([ad(1, number_of_vacancies=3), ad(2, number_of_vacancies=None), ad(3, number_of_vacancies="x")])
    assert res.vacancies_total == 5


def test_cli_unknown_stage():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "nope"], capture_output=True, text=True)
    assert r.returncode == 2
    assert "unknown stage" in r.stdout


def test_scan_tracks_ids_seen_in_earlier_files():
    seen = set()
    first = scan.scan([ad(1), ad(2)], seen=seen)
    second = scan.scan([ad(2), ad(3, publication_date="2025-01-05")], seen=seen)
    assert first.n_seen_before == 0 and second.n_seen_before == 1
    assert second.by_month == {"2024-03": 1, "2025-01": 1}
    assert second.by_month_new == {"2025-01": 1}
    assert [r["seen_in_earlier_file"] for r in second.extract] == [True, False]
    assert seen == {"1", "2", "3"}
    assert second.by_year_region_new == {"2025|Stockholms län": 1}
    assert second.by_year_language_new == {"2025|(none)": 1}


def test_multi_occupation_counted():
    res = scan.scan([ad(1, occupation=[{"label": "a"}, {"label": "b"}]), ad(2)])
    assert res.n_multi_occupation == 1

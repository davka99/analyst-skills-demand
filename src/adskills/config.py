"""Paths and fixed settings. Change nothing here silently: see docs/decisions.md."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_TMP = ROOT / "data" / "tmp"  # git-ignored; yearly downloads live here
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

# Download host for the yearly files (D1). The second URL is the older alias.
BASE_URLS = (
    "https://data.arbetsformedlingen.se/annonser/historiska/",
    "https://data.jobtechdev.se/annonser/historiska/",
)
HISTORICAL_API = "https://historical.api.jobtechdev.se"

# Study window (D3): complete years only.
YEARS = tuple(range(2016, 2026))

# Files appear to be grouped by when an ad ended, not when it was published (the 2024 file
# holds ads published from mid-2023; M1 probe). Ads published in late 2025 can
# therefore sit in the first 2026 file, which is scanned as a boundary file and
# only contributes ads published inside the window.
BOUNDARY_FILES = ("2026-Q1",)

# D8: the enriched ("berikade/kompletta") files are used for every year. The raw
# 2016-2020 files lack ids, region names and occupation labels; the enriched files
# have them (or a municipality code to derive the county from), a detected
# language and JobTech's own skill extraction for comparison.
FILE_TEMPLATE = "/annonser/historiska/berikade/kompletta/{label}_beta1_jsonl.zip"

# Alternative files inspected in M2 because the raw 2016-2020 files lack ids,
# regions and occupation labels (schema stage output in data/raw/_probe/schema/).
ALT_FILES = {
    "2016-enriched": "/annonser/historiska/berikade/kompletta/2016_beta1_jsonl.zip",
    "2019-enriched": "/annonser/historiska/berikade/kompletta/2019_beta1_jsonl.zip",
    "2020-enriched": "/annonser/historiska/berikade/kompletta/2020_beta1_jsonl.zip",
    "2024-enriched": "/annonser/historiska/berikade/kompletta/2024_beta1_jsonl.zip",
    "2018-patched": "/annonser/historiska/2018_municipality_patched.zip",
    "2019-patched": "/annonser/historiska/2019_municipality_patched.zip",
}

# Year used by the probe to inspect the file format.
PROBE_YEAR = 2024

SEED = 20261120
USER_AGENT = "analyst-skills-demand (portfolio project; github.com/davka99)"

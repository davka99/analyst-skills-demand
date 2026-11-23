"""Reading the JobTech historical ad files.

The exact file names, inner format (JSON array or JSON lines) and field names are
verified by the probe stage before the full fetch. The reader therefore accepts
both formats and the flattening step fails loudly if the core fields are missing,
instead of silently producing empty columns.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Fields we extract, as dotted paths into one ad record (JobSearch schema).
FIELDS: dict[str, str] = {
    "id": "id",
    "headline": "headline",
    "publication_date": "publication_date",
    "application_deadline": "application_deadline",
    "description": "description.text",
    "employer_name": "employer.name",
    "employer_orgnr": "employer.organization_number",
    "occupation": "occupation.label",
    "occupation_id": "occupation.concept_id",
    "occupation_group": "occupation_group.label",
    "occupation_field": "occupation_field.label",
    "region": "workplace_address.region",
    "region_code": "workplace_address.region_code",
    "municipality": "workplace_address.municipality",
    "municipality_code": "workplace_address.municipality_code",
    "vacancies": "number_of_vacancies",
    "employment_type": "employment_type.label",
    "remote": "remote_work",
    "original_id": "original_id",
    "last_publication_date": "last_publication_date",
    "removed_date": "removed_date",
    "source_type": "source_type",
    "language": "detected_language",
    "experience_required": "experience_required",
    "jobtech_skills": "keywords.enriched.skill",
}
REQUIRED = ("id", "headline", "publication_date", "description")


class SchemaError(ValueError):
    """Raised when records do not contain the fields this project relies on."""


def get_path(obj: Any, path: str) -> Any:
    """Follow a dotted path through nested dicts; None if any step is missing.

    Taxonomy fields such as `occupation` are lists of concepts in the files (seen in
    the M1 probe); the first concept is used, which is the employer's main choice.
    """
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# County (län) from the first two digits of the municipality code. Used when an
# older file has the municipality code but no region name (D8).
COUNTY_BY_CODE = {
    "01": "Stockholms län", "03": "Uppsala län", "04": "Södermanlands län", "05": "Östergötlands län",
    "06": "Jönköpings län", "07": "Kronobergs län", "08": "Kalmar län", "09": "Gotlands län",
    "10": "Blekinge län", "12": "Skåne län", "13": "Hallands län", "14": "Västra Götalands län",
    "17": "Värmlands län", "18": "Örebro län", "19": "Västmanlands län", "20": "Dalarnas län",
    "21": "Gävleborgs län", "22": "Västernorrlands län", "23": "Jämtlands län", "24": "Västerbottens län",
    "25": "Norrbottens län",
}


def synthetic_id(ad: dict) -> str:
    """Stable id for records without one (the raw 2016 file has id = null)."""
    parts = [
        str(get_path(ad, "headline") or ""),
        str(get_path(ad, "publication_date") or ""),
        str(get_path(ad, "employer.name") or ""),
        str(get_path(ad, "description.text") or "")[:1000],
    ]
    return "h:" + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def flatten(ad: dict, fields: dict[str, str] = FIELDS) -> dict[str, Any]:
    out = {name: get_path(ad, path) for name, path in fields.items()}
    if "description" in out and out["description"] is None and isinstance(ad.get("description"), str):
        out["description"] = ad["description"]
    if fields is FIELDS:
        # Text fallback (D8): part of 2020 has description.text = null.
        out["text_source"] = "text" if out["description"] else None
        if not out["description"]:
            fmt = get_path(ad, "description.text_formatted")
            parts = [get_path(ad, f"description.{k}") for k in ("company_information", "needs", "requirements")]
            parts = [p for p in parts if isinstance(p, str) and p.strip()]
            if isinstance(fmt, str) and fmt.strip():
                out["description"], out["text_source"] = fmt, "text_formatted"
            elif parts:
                out["description"], out["text_source"] = "\n".join(parts), "parts"
        out["id_source"] = "id"
        if out["id"] in (None, ""):
            out["id"] = synthetic_id(ad)
            out["id_source"] = "hash"
        out["region_source"] = "region" if out["region"] else None
        code = str(out.get("municipality_code") or "")
        if not out["region"] and len(code) == 4 and code[:2] in COUNTY_BY_CODE:
            out["region"] = COUNTY_BY_CODE[code[:2]]
            out["region_code"] = code[:2]
            out["region_source"] = "municipality_code"
    return out


def check_schema(records: list[dict], fields: dict[str, str] = FIELDS, min_share: float = 0.5) -> dict[str, float]:
    """Share of records with each field present; raise if a required field is mostly missing.

    The threshold catches a changed schema (a field renamed or moved, share ~0), not
    ordinary gaps: 2020 has a description for only ~78 % of ads, which is a data gap
    handled and reported in M3.
    """
    if not records:
        raise SchemaError("no records to check")
    flat = [flatten(r, fields) for r in records]  # after fallbacks (synthetic id, region from code)
    shares = {name: sum(f.get(name) is not None for f in flat) / len(flat) for name in fields}
    missing = [f for f in REQUIRED if shares[f] < min_share]
    if missing:
        raise SchemaError(f"required fields mostly missing: {missing} (shares {[round(shares[f], 3) for f in missing]})")
    return shares


def key_paths(obj: Any, prefix: str = "", depth: int = 3) -> list[str]:
    """Dotted key paths of a nested record (lists are marked with [])."""
    paths: list[str] = []
    if isinstance(obj, dict) and depth > 0:
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            paths.append(p)
            paths.extend(key_paths(v, p, depth - 1))
    elif isinstance(obj, list) and obj and depth > 0:
        paths.extend(key_paths(obj[0], prefix + "[]", depth - 1))
    return paths


def _iter_stream(fh: io.BufferedReader) -> Iterator[dict]:
    """Yield records from a JSON array or a JSON-lines stream."""
    first = fh.peek(256).lstrip()[:1]
    if first == b"[":
        import ijson

        yield from ijson.items(fh, "item", use_float=True)
    else:
        for line in io.TextIOWrapper(fh, encoding="utf-8"):
            line = line.strip().rstrip(",")
            if line and line not in ("[", "]"):
                yield json.loads(line)


def iter_records(path: Path | str) -> Iterator[dict]:
    """Yield ad records from a yearly file (.zip with .json/.jsonl inside, or plain)."""
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            members = [m for m in zf.infolist() if not m.is_dir() and re.search(r"\.jsonl?$", m.filename, re.I)]
            if not members:
                raise SchemaError(f"no .json/.jsonl member in {path.name}: {zf.namelist()[:10]}")
            for m in sorted(members, key=lambda m: m.filename):
                with zf.open(m) as raw:
                    yield from _iter_stream(io.BufferedReader(raw))
    else:
        with open(path, "rb") as raw:
            yield from _iter_stream(io.BufferedReader(raw))


# --- directory listing --------------------------------------------------------------

_HREF = re.compile(r'href="([^"?#]+)"', re.I)


def parse_listing(html_text: str) -> list[str]:
    """Return the links of a directory index page, minus parent and sort links.

    The JobTech index uses absolute paths ("/annonser/historiska/2024.jsonl.zip"),
    so links are resolved later with urljoin against the page URL.
    """
    out = []
    for h in _HREF.findall(html_text):
        if h in ("/", "") or h.startswith(("..", "mailto:")):
            continue
        out.append(h)
    return out


def year_files(links: list[str]) -> dict[int, list[str]]:
    """Group zip links by the year in their name."""
    out: dict[int, list[str]] = {}
    for link in links:
        name = link.rsplit("/", 1)[-1]
        m = re.match(r"^(\d{4})\D.*\.zip$|^(\d{4})\.zip$", name, re.I)
        if m:
            year = int(m.group(1) or m.group(2))
            out.setdefault(year, []).append(link)
    return out


def pick_year_file(candidates: list[str]) -> str:
    """Prefer the plain YYYY.zip / YYYY.jsonl.zip, else the shortest name (raw over variants)."""
    plain = [c for c in candidates if re.fullmatch(r"\d{4}(?:\.jsonl?)?\.zip", c.rsplit("/", 1)[-1], re.I)]
    return (plain or sorted(candidates, key=len))[0]


def counter_top(c: Counter, n: int = 25) -> list[list]:
    return [[k, v] for k, v in c.most_common(n)]

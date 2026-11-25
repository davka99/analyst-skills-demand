"""Pipeline entry point. Usage: python scripts/run_pipeline.py <stage> [<stage> ...]

Stages
  probe  List the download folders, download one year (config.PROBE_YEAR), record
         zip members, inner format, field names, a few sample records and a full
         headline-classification pass to data/raw/_probe/. Also pings the
         historical search API. Used to verify the source before the full fetch.

  fetch  For every year in config.YEARS: download the yearly file to data/tmp/,
         stream it once, write the classified-headline extract with text
         (data/raw/extract/ads_<year>.jsonl.gz), analytical-occupation candidates
         without text (candidates_<year>.csv.gz), yearly denominators and a
         manifest (data/raw/fetch_manifest.json), then delete the download.
         All years run in one job (ids are tracked across files to find ads that
         appear in two yearly files); nothing is done if all years are present.

  schema_alt  Same for config.ALT_FILES (enriched and municipality-patched files),
         on the first 20,000 records.
  schema For every file fetch would read: download, record key paths and field
         presence of the first 2,000 records and two truncated sample records to
         data/raw/_probe/schema/<label>.json, then delete the download.

  build  Needs the fetched extract (with ad text). Turns each ad into one row of
         metadata, hashes and 0/1 skill flags: data/processed/ads_features.csv.gz.
         This is the only stage that reads ad text; the text itself is not
         committed (D16).
  reconcile  Yearly ad totals from the JobTech historical search API (an independent
         count of the same source) to data/raw/api_yearly_totals.json.
  quality  Offline. From the features file: data/processed/analyst_ads.csv.gz
         (population, window, de-duplicated) and reports/data_quality_summary.json.

  annotate_prep  Needs the fetched extract. Draw the development sample (10 ads/year)
         and the test sample (15 ads/year, disjoint) and write the annotation
         batches with text to data/annotation/texts/ (not committed).
  validate  Offline. Compare dictionary flags (features file) with the committed
         annotations: reports/validation.json.

  prevalence  M5 (D10, D11). Skill shares 2023-2025 with employer-cluster bootstrap
         intervals, late-vs-early change, logistic trends (pooled, title-adjusted,
         data-analyst titles only) with BH, Stockholm vs rest. Needs statsmodels.
         Writes reports/prevalence.json and figures.

  bundles  M6. Volume (analyst ads per 10,000 Platsbanken ads, by year and area,
         Wilson intervals), neighbouring roles, skill co-occurrence (lift, phi) in
         2023-2025 and every generative-AI match (id, year, matched terms).
         Writes reports/bundles.json and a figure.

  robustness  M7. Late-vs-early change and trend for the main skills under other
         population, de-duplication, agency, language and per-employer choices;
         the Stockholm gap adjusted for title; English requirement within
         Swedish-language ads; comparison with JobTech's own skill tags.
         Writes reports/robustness.json and a figure. Needs statsmodels.

Network access is only needed for `probe`, `schema`, `fetch` and `reconcile`.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from adskills import config, jobtech, scan, skills, titles  # noqa: E402


def _session():
    import requests

    s = requests.Session()
    s.headers["User-Agent"] = config.USER_AGENT
    return s


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _gz_text(path: Path, newline=None):
    """Gzip text writer with a fixed header time, so reruns are byte-identical."""
    import gzip
    import io

    raw = gzip.GzipFile(filename=str(path), mode="wb", mtime=0, compresslevel=9)  # owns and closes the file
    return io.TextIOWrapper(raw, encoding="utf-8", newline=newline)


def _truncate(obj, n: int = 300):
    if isinstance(obj, str):
        return obj if len(obj) <= n else obj[:n] + f"... [{len(obj)} chars]"
    if isinstance(obj, dict):
        return {k: _truncate(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate(v, n) for v in obj[:5]]
    return obj


def download(sess, url: str, dest: Path, chunk: int = 1 << 20) -> dict:
    """Stream a file to disk; return size, sha256 and seconds."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    h = hashlib.sha256()
    size = 0
    with sess.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for block in r.iter_content(chunk):
                fh.write(block)
                h.update(block)
                size += len(block)
    return {"url": url, "bytes": size, "sha256": h.hexdigest(), "seconds": round(time.time() - t0, 1)}


def probe() -> None:
    out = config.DATA_RAW / "_probe"
    sess = _session()
    summary: dict = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "listings": {}}

    # 1. Folder listings (raw and enriched) on both hosts.
    chosen_base, chosen_links = None, []
    for base in config.BASE_URLS:
        for sub in ("", "berikade/"):
            url = base + sub
            entry: dict = {"url": url}
            try:
                r = sess.get(url, timeout=60)
                entry["status"] = r.status_code
                if r.ok:
                    links = jobtech.parse_listing(r.text)
                    entry["links"] = links[:300]
                    entry["n_links"] = len(links)
                    entry["year_files"] = jobtech.year_files(links)
                    if sub == "" and chosen_base is None and entry["year_files"]:
                        chosen_base, chosen_links = base, links
                    (out / "listings").mkdir(parents=True, exist_ok=True)
                    name = base.split("//")[1].split("/")[0] + ("_berikade" if sub else "")
                    (out / "listings" / f"{name}.html").write_text(r.text[:200_000], encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 - record and continue
                entry["error"] = repr(exc)
            summary["listings"][url] = entry
    summary["chosen_base"] = chosen_base

    # Sub-folders of the enriched files (one level), to see what exists for later.
    sub_listings = {}
    for link in chosen_links:
        if "/berikade/" in link and link.endswith("index.html") and link.count("/") >= 5:
            url = urljoin(chosen_base, link)
            try:
                r = sess.get(url, timeout=60)
                sub_listings[url] = [h for h in jobtech.parse_listing(r.text) if "/berikade/" in h][:100] if r.ok else r.status_code
            except Exception as exc:  # noqa: BLE001
                sub_listings[url] = repr(exc)
    berikade_url = chosen_base + "berikade/"
    try:
        r = sess.get(berikade_url, timeout=60)
        for link in jobtech.parse_listing(r.text):
            if "/berikade/" in link and link.endswith("index.html") and link.rstrip("/") != "/annonser/historiska/berikade/index.html":
                url = urljoin(berikade_url, link)
                r2 = sess.get(url, timeout=60)
                sub_listings[url] = [h for h in jobtech.parse_listing(r2.text) if "/berikade/" in h][:100] if r2.ok else r2.status_code
    except Exception as exc:  # noqa: BLE001
        sub_listings["error"] = repr(exc)
    summary["berikade_sublistings"] = sub_listings
    if chosen_base is None:
        _write_json(out / "probe_summary.json", summary)
        raise SystemExit("probe: no listing with yearly zip files found (see probe_summary.json)")

    # 2. File sizes for every year in the window (HEAD, cheap).
    yf = jobtech.year_files(chosen_links)
    sizes = {}
    for year in sorted(yf):
        link = jobtech.pick_year_file(yf[year])
        url = urljoin(chosen_base, link)
        try:
            h = sess.head(url, timeout=60, allow_redirects=True)
            sizes[year] = {"file": link, "status": h.status_code, "bytes": int(h.headers.get("content-length", 0) or 0)}
        except Exception as exc:  # noqa: BLE001
            sizes[year] = {"file": link, "error": repr(exc)}
    summary["year_file_sizes"] = sizes
    missing_years = [y for y in config.YEARS if y not in yf]
    summary["missing_years_in_window"] = missing_years

    # 3. Download the probe year and inspect it.
    year = config.PROBE_YEAR if config.PROBE_YEAR in yf else max(y for y in yf if y <= max(config.YEARS))
    link = jobtech.pick_year_file(yf[year])
    dest = config.DATA_TMP / link.rsplit("/", 1)[-1]
    summary["probe_year"] = year
    summary["download"] = download(sess, urljoin(chosen_base, link), dest)
    if zipfile.is_zipfile(dest):
        with zipfile.ZipFile(dest) as zf:
            summary["zip_members"] = [[m.filename, m.file_size, m.compress_size] for m in zf.infolist()][:50]
            first = zf.infolist()[0]
            with zf.open(first) as fh:
                summary["first_bytes"] = fh.read(400).decode("utf-8", "replace")

    first_records, paths = [], Counter()
    for i, rec in enumerate(jobtech.iter_records(dest)):
        if i < 3:
            first_records.append(_truncate(rec))
        paths.update(set(jobtech.key_paths(rec)))
        if i >= 1999:
            break
    _write_json(out / "sample_records.json", first_records)
    summary["key_paths_first_2000"] = {k: v for k, v in sorted(paths.items())}
    try:
        recs = []
        for i, rec in enumerate(jobtech.iter_records(dest)):
            recs.append(rec)
            if i >= 1999:
                break
        summary["field_shares_first_2000"] = jobtech.check_schema(recs)
        summary["schema_ok"] = True
    except jobtech.SchemaError as exc:
        summary["schema_ok"] = False
        summary["schema_error"] = str(exc)

    # 4. Full pass: denominators and headline classification for the probe year.
    t0 = time.time()
    res = scan.scan(jobtech.iter_records(dest))
    summary["scan_seconds"] = round(time.time() - t0, 1)
    summary["scan"] = res.summary()
    by_cat: dict[str, list] = {}
    occ_by_cat: dict[str, Counter] = {}
    desc_len: dict[str, list[int]] = {}
    skill_counts: Counter = Counter()
    n_pop = 0
    for row in res.extract:
        cat = row["category"]
        by_cat.setdefault(cat, [])
        if len(by_cat[cat]) < 40:
            by_cat[cat].append(row["headline"])
        occ_by_cat.setdefault(cat, Counter())[row.get("occupation") or "(none)"] += 1
        desc_len.setdefault(cat, []).append(len(row.get("description") or ""))
        if cat in titles.PRIMARY:
            n_pop += 1
            skill_counts.update(skills.find_skills(f"{row.get('headline') or ''}\n{row.get('description') or ''}"))
    summary["headlines_by_category"] = by_cat
    summary["occupation_by_category"] = {k: jobtech.counter_top(v, 15) for k, v in occ_by_cat.items()}
    summary["description_length_quantiles"] = {
        k: [sorted(v)[int(q * (len(v) - 1))] for q in (0, 0.1, 0.5, 0.9, 1)] for k, v in desc_len.items() if v
    }
    summary["population_n"] = n_pop
    summary["skill_share_v0_probe_year"] = {k: round(v / max(n_pop, 1), 3) for k, v in skill_counts.most_common()}
    cand_occ = Counter(c.get("occupation") or "(none)" for c in res.candidates)
    summary["candidates_top_occupations"] = jobtech.counter_top(cand_occ, 30)
    summary["candidates_sample_headlines"] = [c["headline"] for c in res.candidates[:60]]

    # 5. Historical search API (alternative access path).
    try:
        r = sess.get(f"{config.HISTORICAL_API}/search", params={"q": "dataanalytiker", "limit": 1}, timeout=60)
        api = {"status": r.status_code, "content_type": r.headers.get("content-type")}
        try:
            j = r.json()
            api["keys"] = list(j)[:20] if isinstance(j, dict) else type(j).__name__
            api["total"] = j.get("total") if isinstance(j, dict) else None
        except ValueError:
            api["body"] = r.text[:300]
    except Exception as exc:  # noqa: BLE001
        api = {"error": repr(exc)}
    summary["historical_api"] = api

    _write_json(out / "probe_summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("chosen_base", "probe_year", "download", "schema_ok", "population_n")}, indent=2))

def _listing(sess) -> tuple[str, dict[int, list[str]]]:
    for base in config.BASE_URLS:
        try:
            r = sess.get(base, timeout=60)
        except Exception:  # noqa: BLE001
            continue
        if r.ok:
            yf = jobtech.year_files(jobtech.parse_listing(r.text))
            if yf:
                return base, yf
    raise SystemExit("fetch: no listing with yearly files found")


def _file_list(sess, years=None) -> tuple[str, list[tuple[str, str]]]:
    """(label, link) for every file in the window plus the boundary files (D8: enriched files)."""
    years = tuple(years or config.YEARS)
    labels = [str(y) for y in years]
    if years == tuple(config.YEARS):
        labels += list(config.BOUNDARY_FILES)
    return config.BASE_URLS[0], [(lab, config.FILE_TEMPLATE.format(label=lab)) for lab in labels]


def _head(path: Path, n: int = 2000) -> list[dict]:
    head = []
    for i, rec in enumerate(jobtech.iter_records(path)):
        head.append(rec)
        if i >= n - 1:
            break
    return head


def _schema_report(head: list[dict]) -> dict:
    paths = Counter()
    for rec in head:
        paths.update(set(jobtech.key_paths(rec)))
    shares = {name: round(sum(jobtech.flatten(r, {name: p})[name] is not None for r in head) / len(head), 4)
              for name, p in jobtech.FIELDS.items()}
    return {"n": len(head), "key_paths": dict(sorted(paths.items())), "field_shares": shares,
            "samples": [_truncate(r, 200) for r in head[:2]]}


def schema(alt: bool = False, n: int = 2000) -> None:
    sess = _session()
    if alt:
        base, files = config.BASE_URLS[0], list(config.ALT_FILES.items())
    else:
        base, files = _file_list(sess)
    out = config.DATA_RAW / "_probe" / "schema"
    for label, link in files:
        dest = config.DATA_TMP / link.rsplit("/", 1)[-1]
        dl = download(sess, urljoin(base, link), dest)
        rep = {"file": link, **dl, **_schema_report(_head(dest, n))}
        _write_json(out / f"{label}.json", rep)
        dest.unlink()
        print(label, {k: v for k, v in rep["field_shares"].items() if v < 0.9})


def fetch(years=None) -> None:
    import gzip
    import csv

    sess = _session()
    base, files = _file_list(sess, years)
    out = config.DATA_RAW / "extract"
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = config.DATA_RAW / "fetch_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"years": {}}
    if all(label in manifest["years"] and (out / f"ads_{label}.jsonl.gz").exists() for label, _ in files):
        print(f"already fetched: {[f[0] for f in files]}; delete data/raw/fetch_manifest.json to re-fetch")
        return
    # All files are scanned in one run, oldest first, so that ids seen in an
    # earlier file can be detected (ads that appear in two files).
    seen: set[str] = set()
    for label, link in files:
        year = label
        url = urljoin(base, link)
        dest = config.DATA_TMP / link.rsplit("/", 1)[-1]
        print(f"{year}: downloading {url}")
        dl = download(sess, url, dest)
        t0 = time.time()
        head = _head(dest)
        try:
            field_shares = jobtech.check_schema(head)  # raises on a changed schema
        except jobtech.SchemaError:
            _write_json(config.DATA_RAW / "_probe" / "schema" / f"{label}_failed.json", _schema_report(head))
            raise
        del head
        res = scan.scan(jobtech.iter_records(dest), seen=seen)
        n_bad_year = sum(v for k, v in res.by_month.items() if not k.startswith(year[:4]))
        with _gz_text(out / f"ads_{year}.jsonl.gz") as fh:
            for row in sorted(res.extract, key=lambda r: str(r["id"])):
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        cand_cols = ["id", "headline", "publication_date", "employer_name", "occupation", "occupation_group", "region"]
        with _gz_text(out / f"candidates_{year}.csv.gz", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cand_cols)
            w.writeheader()
            for row in sorted(res.candidates, key=lambda r: str(r["id"])):
                w.writerow(row)
        manifest["years"][label] = {
            **dl,
            "file": link,
            "scan_seconds": round(time.time() - t0, 1),
            "records_outside_year": n_bad_year,
            "field_shares_first_2000": field_shares,
            **res.summary(),
        }
        manifest["fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
        _write_json(manifest_path, manifest)  # checkpoint after every year
        dest.unlink()
        print(f"{year}: {res.n_records} records, {len(res.extract)} kept, {len(res.candidates)} candidates")


def reconcile() -> None:
    sess = _session()
    out: dict = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "api": config.HISTORICAL_API, "years": {}}
    for year in config.YEARS:
        params = {"historical-from": f"{year}-01-01T00:00:00", "historical-to": f"{year}-12-31T23:59:59", "limit": 0}
        try:
            r = sess.get(f"{config.HISTORICAL_API}/search", params=params, timeout=120)
            entry = {"status": r.status_code, "params": params}
            if r.ok:
                j = r.json()
                tot = j.get("total")
                entry["total"] = tot.get("value") if isinstance(tot, dict) else tot
            else:
                entry["body"] = r.text[:300]
        except Exception as exc:  # noqa: BLE001
            entry = {"error": repr(exc), "params": params}
        out["years"][str(year)] = entry
        print(year, entry.get("total"), entry.get("status"))
    totals = [e.get("total") for e in out["years"].values()]
    # If the date filter were ignored, every year would return the same total.
    out["filter_works"] = len(set(totals)) > 1
    _write_json(config.DATA_RAW / "api_yearly_totals.json", out)


def reconcile_monthly() -> None:
    """Locate the 2025 shortfall (data_quality.md section 2): API totals per month for
    2024-2025 next to the files' counts per publication month, plus a probe of whether
    the API counts ads the files may lack (by source and removal status)."""
    sess = _session()
    manifest = json.loads((config.DATA_RAW / "fetch_manifest.json").read_text(encoding="utf-8"))
    files: dict = {}
    for entry in manifest["years"].values():
        for month, n in entry["by_month_new"].items():
            files[month] = files.get(month, 0) + n
    out: dict = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "api": config.HISTORICAL_API,
                 "months": {}}
    import calendar

    for year in (2024, 2025):
        for m in range(1, 13):
            last = calendar.monthrange(year, m)[1]
            params = {"historical-from": f"{year}-{m:02d}-01T00:00:00",
                      "historical-to": f"{year}-{m:02d}-{last}T23:59:59", "limit": 0}
            key = f"{year}-{m:02d}"
            try:
                r = sess.get(f"{config.HISTORICAL_API}/search", params=params, timeout=120)
                tot = r.json().get("total") if r.ok else None
                api = tot.get("value") if isinstance(tot, dict) else tot
                out["months"][key] = {"api": api, "files": files.get(key), "status": r.status_code}
            except Exception as exc:  # noqa: BLE001
                out["months"][key] = {"error": repr(exc), "files": files.get(key)}
            e = out["months"][key]
            if e.get("api") and e.get("files"):
                e["diff_pct"] = round(100 * (e["files"] - e["api"]) / e["api"], 2)
            print(key, e)
    # Decisive check: are ads that the API counts for 2025 present in the 2025 file?
    # The first page of a month is not a random sample (run 1 found all of them), so one
    # page of 100 ads at a random offset is drawn for every day of the months with the
    # largest gaps (Jan-Apr, Jul) and two control months (May, Aug), and membership is
    # tested against all ids in the file.
    import calendar as _cal

    rng = __import__("random").Random(config.SEED)
    sample = []
    for m in (1, 2, 3, 4, 5, 7, 8):
        for d in range(1, _cal.monthrange(2025, m)[1] + 1):
            day = f"2025-{m:02d}-{d:02d}"
            base_params = {"historical-from": f"{day}T00:00:00", "historical-to": f"{day}T23:59:59"}
            try:
                r = sess.get(f"{config.HISTORICAL_API}/search", params={**base_params, "limit": 0},
                             timeout=120)
                tot = r.json().get("total") if r.ok else None
                n_day = (tot.get("value") if isinstance(tot, dict) else tot) or 0
                if n_day == 0:
                    continue
                offset = rng.randrange(0, max(1, min(n_day, 2000) - 100) + 1)
                r = sess.get(f"{config.HISTORICAL_API}/search",
                             params={**base_params, "limit": 100, "offset": offset}, timeout=120)
                hits = r.json().get("hits", []) if r.ok else []
                sample += [(f"2025-{m:02d}", h) for h in hits]
                for h in hits:
                    h["_queried_day"] = day
            except Exception as exc:  # noqa: BLE001
                out.setdefault("sample_errors", []).append(f"{day}: {exc!r}")
    base, files = _file_list(sess, [2025])
    label, link = files[0]
    dest = config.DATA_TMP / link.rsplit("/", 1)[-1]
    download(sess, urljoin(base, link), dest)
    # Enriched files carry a hashed `id` and the Platsbanken number in `original_id`;
    # the API may return either, so both are collected.
    ids: set[str] = set()
    for rec in jobtech.iter_records(dest):
        ids.add(str(rec.get("id")) if rec.get("id") is not None else jobtech.synthetic_id(rec))
        if rec.get("original_id") is not None:
            ids.add(str(rec.get("original_id")))
    dest.unlink()

    def describe(h: dict) -> dict:
        return {"source_type": str(h.get("source_type")), "removed": str(h.get("removed")),
                "has_description": bool((h.get("description") or {}).get("text")),
                "publication_date": str(h.get("publication_date"))[:10],
                "last_publication_date": str(h.get("last_publication_date"))[:10],
                "removed_date": str(h.get("removed_date"))[:10]}

    def in_file(h: dict) -> bool:
        return any(str(h.get(k)) in ids for k in ("id", "original_id") if h.get(k) is not None)

    found = [h for _, h in sample if in_file(h)]
    missing = [h for _, h in sample if not in_file(h)]
    by_month = Counter(mo for mo, h in sample if not in_file(h))
    sampled_by_month = Counter(mo for mo, _ in sample)
    # Does the API's date filter use the publication date? Share of hits whose
    # publication_date is not the queried day, and repeated ids, per month.
    date_check = {}
    for mo in sorted(sampled_by_month):
        hs = [h for m_, h in sample if m_ == mo]
        off = [h for h in hs if str(h.get("publication_date"))[:10] != h["_queried_day"]]
        date_check[mo] = {
            "hits": len(hs), "unique_ids": len({str(h.get("id")) for h in hs}),
            "pubdate_not_queried_day": len(off),
            "pubdate_month_differs": sum(str(h.get("publication_date"))[:7] != mo for h in hs),
            "examples": [[h["_queried_day"], str(h.get("publication_date")),
                          str(h.get("last_publication_date")), str(h.get("timestamp"))]
                         for h in off[:3]]}
    out["date_check"] = date_check
    out["membership_2025"] = {
        "file_ids": len(ids), "sampled": len(sample), "found": len(found), "missing": len(missing),
        "missing_share": round(len(missing) / max(len(sample), 1), 4),
        "missing_by_month": dict(sorted(by_month.items())),
        "sampled_by_month": dict(sorted(sampled_by_month.items())),
        "keys_in_api": sorted({k for _, h in sample for k in h})[:80],
        "missing_profile": {k: dict(Counter(describe(h)[k] for h in missing))
                            for k in ("source_type", "removed", "has_description")},
        "missing_pubdate_vs_file": "see missing_examples",
        "missing_occupation_field": dict(Counter(
            str((h.get("occupation_field") or {}).get("label")) for h in missing).most_common(10)),
        "found_profile": {k: dict(Counter(describe(h)[k] for h in found))
                          for k in ("source_type", "removed", "has_description")},
        "api_id_examples": [[str(h.get("id")), str(h.get("original_id"))] for _, h in sample[:3]],
        "missing_examples": [{"id": str(h.get("id")), **describe(h)} for h in missing[:25]],
    }
    print(json.dumps(out["membership_2025"], indent=1)[:3000])
    _write_json(config.DATA_RAW / "api_monthly_totals.json", out)


def denominators(manifest: dict) -> dict:
    """Ads per publication year (unique ids across files), overall and by area."""
    from adskills.quality import STOCKHOLM

    years = {str(y) for y in config.YEARS}
    total, area = Counter(), Counter()
    for entry in manifest["years"].values():
        for month, n in entry["by_month_new"].items():
            if month[:4] in years:
                total[month[:4]] += n
        for key, n in entry.get("by_year_region_new", {}).items():
            y, region = key.split("|", 1)
            if y in years:
                a = "Stockholm" if region == STOCKHOLM else ("Unknown" if region == "(none)" else "Rest of Sweden")
                area[f"{y}|{a}"] += n
    return {"total_by_year": dict(sorted(total.items())), "by_year_area": dict(sorted(area.items()))}


def build() -> None:
    from adskills import quality

    raw = quality.load_extract(config.DATA_RAW / "extract")
    feats = quality.build_features(quality.prepare(raw))
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with _gz_text(config.DATA_PROCESSED / quality.FEATURES_FILE, newline="") as fh:
        feats.sort_values(["file_order", "id"], kind="mergesort").to_csv(fh, index=False, lineterminator="\n")
    print(f"features: {len(feats):,} rows, {feats.shape[1]} columns")


def quality_stage() -> None:
    from adskills import quality

    manifest = json.loads((config.DATA_RAW / "fetch_manifest.json").read_text(encoding="utf-8"))
    df = quality.deduplicate(quality.load_features(config.DATA_PROCESSED / quality.FEATURES_FILE))
    final = quality.analysis_frame(df)
    summ = quality.summary(df, final)
    summ["denominators"] = denominators(manifest)
    summ["manifest_years"] = {
        k: {f: v.get(f) for f in ("n_records", "n_seen_in_earlier_file", "records_outside_year", "n_multi_occupation", "missing_share")}
        for k, v in manifest["years"].items()
    }
    summ["neighbour_categories_by_year"] = {
        f"{int(y)}|{c}": int(n)
        for (y, c), n in df[df["drop_reason"].isna() & df["year"].between(min(config.YEARS), max(config.YEARS))]
        .groupby(["year", "category"]).size().items()
    }
    out = final.sort_values(["pub_date", "id"], kind="mergesort").drop(columns=["drop_reason", "in_population"])
    out["pub_date"] = out["pub_date"].dt.strftime("%Y-%m-%d")
    for c in out.columns:
        if out[c].dtype == bool:
            out[c] = out[c].astype(int)
    with _gz_text(config.DATA_PROCESSED / "analyst_ads.csv.gz", newline="") as fh:
        out.to_csv(fh, index=False, lineterminator="\n")
    _write_json(config.REPORTS / "data_quality_summary.json", summ)
    print(json.dumps({k: summ[k] for k in ("rows_final", "final_by_year", "dropped_in_window")}, indent=1))


def load_analysis_ads():
    from adskills import quality

    return quality.load_features(config.DATA_PROCESSED / "analyst_ads.csv.gz")


def annotate_prep() -> None:
    from adskills import validation

    from adskills import quality

    df = load_analysis_ads()
    df = df[df["desc_len"] >= 200]  # D12
    text = quality.load_extract(config.DATA_RAW / "extract").drop_duplicates("id").set_index("id")
    df = df.assign(headline=df["id"].map(text["headline"]), description=df["id"].map(text["description"]))
    out = config.ROOT / "data" / "annotation" / "texts"
    dev = validation.draw_sample(df, 10, seed=config.SEED)
    test = validation.draw_sample(df, 15, seed=config.SEED + 1, exclude=dev["id"])
    maps = []
    for name, sample, size in (("dev", dev, 50), ("test", test, 50)):
        sample = sample.sample(frac=1, random_state=config.SEED).reset_index(drop=True)  # mix years within batches
        prefix = "D" if name == "dev" else "T"
        for b, start in enumerate(range(0, len(sample), size), 1):
            part = sample.iloc[start : start + size]
            m = validation.export_batch(part, prefix, out / f"{name}_batch_{b}.jsonl", start=start)
            m["sample"], m["batch"] = name, b
            maps.append(m)
    import pandas as pd

    pd.concat(maps).to_csv(out.parent / "sample_ids.csv", index=False)
    print({n: int(len(x)) for n, x in (("dev", dev), ("test", test))})


def human_prep() -> None:
    """Needs the fetched extract. Kit for the owner's blind human check (adskills.human):
    texts + an empty label sheet in data/annotation/texts/human/ (never committed)."""
    import pandas as pd

    from adskills import human, quality

    ids = pd.read_csv(config.ROOT / "data" / "annotation" / "sample_ids.csv", dtype={"id": str})
    sample = human.draw(ids, seed=config.SEED + 7)
    text = quality.load_extract(config.DATA_RAW / "extract").drop_duplicates("id").set_index("id")
    sheet = human.write_kit(sample, text[["headline", "description"]],
                            config.ROOT / "data" / "annotation" / "texts" / "human")
    print(f"kit written: {sheet.parent} ({len(sample)} ads, {len(human.HUMAN_SKILLS)} skills)")


def human_check() -> None:
    """Offline. Agreement of the owner's labels (data/annotation/human_labels.csv) with the
    adjudicated reference and with the dictionary: reports/human_check.json."""
    import pandas as pd

    from adskills import human, validation

    ann = config.ROOT / "data" / "annotation"
    labels = ann / human.LABELS_FILE
    if not labels.exists():
        print(f"no {labels.name} yet: build the kit with the annotation-kit workflow first")
        return
    h = human.load_labels(labels)
    gold = validation.load_annotations([ann / f"ann_test_batch_{i}.jsonl" for i in (1, 2, 3)])
    gold = validation.apply_adjudication(gold, ann / "adjudication_test.csv")
    ids = pd.read_csv(ann / "sample_ids.csv", dtype={"id": str}).set_index("ann_id")["id"]
    feats = load_analysis_ads().set_index("id")
    pred = feats.loc[ids.loc[h.index].to_numpy(), list(human.HUMAN_SKILLS)].astype(bool)
    pred.index = h.index
    vs_ref = human.agreement(h, gold)
    vs_dict = human.agreement(h, pred)
    out = {"n_ads": int(len(h)), "skills": list(human.HUMAN_SKILLS),
           "vs_adjudicated_reference": {"summary": human.summary(vs_ref),
                                        "by_skill": vs_ref.to_dict("records")},
           "vs_dictionary": {"summary": human.summary(vs_dict), "by_skill": vs_dict.to_dict("records")}}
    _write_json(config.REPORTS / "human_check.json", out)
    print(json.dumps({k: v["summary"] for k, v in out.items() if isinstance(v, dict)}, indent=1))


def validate() -> None:
    import hashlib

    import pandas as pd

    from adskills import validation

    ann = config.ROOT / "data" / "annotation"
    sha = hashlib.sha256((config.ROOT / "src" / "adskills" / "skills.py").read_bytes()).hexdigest()
    out = {"dictionary_sha256": sha}
    from adskills import skills

    feats = load_analysis_ads().set_index("id")
    ids = pd.read_csv(ann / "sample_ids.csv", dtype={"id": str})
    for name, n_batches in (("dev", 2), ("test", 3)):
        gold_raw = validation.load_annotations([ann / f"ann_{name}_batch_{i}.jsonl" for i in range(1, n_batches + 1)])
        m = ids[ids["sample"] == name].set_index("ann_id")["id"]
        pred = feats.loc[m.loc[gold_raw.index].to_numpy(), list(skills.SKILL_KEYS)]
        pred.index = gold_raw.index
        res = {"n_ads": int(len(gold_raw)), "raw": validation.evaluate(pred, gold_raw).to_dict("records")}
        adj_path = ann / f"adjudication_{name}.csv"
        gold = validation.apply_adjudication(gold_raw, adj_path) if adj_path.exists() else gold_raw
        if adj_path.exists():
            res["adjudicated"] = validation.evaluate(pred, gold).to_dict("records")
            res["n_adjudicated"] = int(len(pd.read_csv(adj_path)))
        res["disagreements"] = validation.disagreements(pred, gold)
        out[name] = res
    _write_json(config.REPORTS / "validation.json", out)
    print("validation written; dictionary", sha[:12])


def analysis_frame_with_skills():
    from adskills import analysis

    df = load_analysis_ads()
    n_all = len(df)
    df = df[df["desc_len"] >= 200].copy()  # D12
    df = analysis.add_groups(df)
    df["year"] = df["year"].astype(int)
    return df, n_all - len(df)


def prevalence() -> None:
    import numpy as np
    import pandas as pd

    from adskills import analysis, figures, skills, stats

    df, n_short = analysis_frame_with_skills()
    keys = analysis.all_keys() + ["any_cloud_vendor"]
    labels = {s.key: s.label for s in skills.SKILLS}
    labels.update({"any_cloud": "Any cloud (incl. generic 'cloud')", "any_cloud_vendor": "Any cloud vendor",
                   "any_bi_tool": "Any BI tool", "python_or_r": "Python or R"})
    val = json.loads((config.REPORTS / "validation.json").read_text(encoding="utf-8"))["test"]["adjudicated"]
    val = {r["skill"]: r for r in val}
    gate_fail = sorted(k for k, r in val.items() if r["pred_pos"] and r["precision"] < 0.80)
    unmeasured = sorted(k for k, r in val.items() if r["gold_pos"] == 0 and r["pred_pos"] == 0)
    seed = config.SEED
    out: dict = {"n_ads": int(len(df)), "n_excluded_short_text": int(n_short), "gate_fail": gate_fail,
                 "unmeasured": unmeasured, "labels": labels}

    # 1. Latest three years: shares with employer-cluster intervals (headline ranking).
    late = df[df["year"].between(*analysis.LATE)]
    lt = stats.cluster_bootstrap_shares(late, keys, "employer_key", n_boot=2000, seed=seed)
    lt["recall"] = lt["skill"].map(lambda k: val.get(k, {}).get("recall"))
    lt["precision"] = lt["skill"].map(lambda k: val.get(k, {}).get("precision"))
    out["late"] = {"years": list(analysis.LATE), "n": int(len(late)), "n_employers": int(late["employer_key"].nunique()),
                   "shares": lt.drop(columns="group").to_dict("records")}

    # 2. Yearly shares (all keys).
    yr = stats.cluster_bootstrap_shares(df, keys, "employer_key", "year", n_boot=1000, seed=seed)
    out["yearly"] = yr.to_dict("records")

    # 3. Late vs early change and logistic trends: pooled, title-adjusted, data-analyst only (D11).
    df["period"] = analysis.period(df["year"])
    variants = {
        "pooled": (df, ""),
        "title_adjusted": (df, "C(category)"),
        "data_analyst_only": (df[df["category"] == "data_analyst"], ""),
    }
    changes = {}
    for name, (d, extra) in variants.items():
        diff = analysis.cluster_bootstrap_diff(d, keys, "employer_key", "period", "early", "late", n_boot=2000, seed=seed)
        tr = analysis.trends(d, keys, extra=extra)
        m = diff.merge(tr[["skill", "or_per_year", "lo", "hi", "p", "p_bh"]].rename(columns={"lo": "or_lo", "hi": "or_hi"}), on="skill")
        if name == "title_adjusted":
            # the adjusted model answers "within title"; the bootstrap diff stays pooled
            m["note"] = "diff columns are pooled; trend is adjusted for title category"
        clear = (m["p_bh"] < 0.05) & (m["diff"].abs() >= 0.05) & ((m["lo"] > 0) | (m["hi"] < 0))
        m["verdict"] = np.where(clear, np.where(m["diff"] > 0, "rising", "falling"), "no clear change")
        changes[name] = m.to_dict("records")
    out["change"] = changes

    # 4. Stockholm vs rest of Sweden, latest three years (ads with known region).
    lk = late[late["area"].isin(["Stockholm", "Rest of Sweden"])]
    sd = analysis.cluster_bootstrap_diff(lk, keys, "employer_key", "area", "Rest of Sweden", "Stockholm", n_boot=2000, seed=seed)
    by_area = stats.cluster_bootstrap_shares(lk, keys, "employer_key", "area", n_boot=2000, seed=seed)
    adj = []
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    for k in keys:
        d = df[df["area"].isin(["Stockholm", "Rest of Sweden"])].assign(y=lambda x: x[k].astype(int), sthlm=lambda x: (x["area"] == "Stockholm").astype(int))
        if d["y"].nunique() < 2:
            adj.append({"skill": k, "or_stockholm": np.nan, "lo": np.nan, "hi": np.nan, "p": np.nan})
            continue
        fit = smf.glm("y ~ sthlm + C(year)", data=d, family=sm.families.Binomial()).fit(
            cov_type="cluster", cov_kwds={"groups": pd.factorize(d["employer_key"])[0]})
        b, se = fit.params["sthlm"], fit.bse["sthlm"]
        adj.append({"skill": k, "or_stockholm": float(np.exp(b)), "lo": float(np.exp(b - 1.96 * se)),
                    "hi": float(np.exp(b + 1.96 * se)), "p": float(fit.pvalues["sthlm"])})
    adj = pd.DataFrame(adj)
    ok = adj["p"].notna()
    adj.loc[ok, "p_bh"] = stats.benjamini_hochberg(adj.loc[ok, "p"])
    # Simpson check: does the sign of the Stockholm gap hold in most years?
    yr_area = stats.cluster_bootstrap_shares(df[df["area"].isin(["Stockholm", "Rest of Sweden"])].assign(
        ya=lambda x: x["year"].astype(str) + "|" + x["area"]), keys, "employer_key", "ya", n_boot=200, seed=seed)
    yr_area[["year", "area"]] = yr_area["group"].str.split("|", expand=True)
    piv = yr_area.pivot_table(index=["skill", "year"], columns="area", values="share").reset_index()
    piv["gap"] = piv["Stockholm"] - piv["Rest of Sweden"]
    sign = piv.groupby("skill")["gap"].apply(lambda g: int((np.sign(g) == np.sign(g.mean())).sum())).rename("years_same_sign")
    out["stockholm"] = {
        "n_stockholm": int((lk["area"] == "Stockholm").sum()), "n_rest": int((lk["area"] == "Rest of Sweden").sum()),
        "diff_late": sd.to_dict("records"), "shares_late": by_area.to_dict("records"),
        "adjusted_all_years": adj.merge(sign, left_on="skill", right_index=True, how="left").to_dict("records"),
    }
    _write_json(config.REPORTS / "prevalence.json", out)

    # Figures (titles generated from results).
    fig = config.FIGURES
    rank = lt[~lt["skill"].isin(gate_fail + ["any_cloud"])]
    rank = rank[rank["skill"].isin(list(skills.SKILL_KEYS))]
    top3 = rank.sort_values("share", ascending=False).head(3)
    t = ", ".join(f"{labels[k]} ({s * 100:.0f} %)" for k, s in zip(top3["skill"], top3["share"]))
    figures.ranked_shares(rank, labels, fig / "skills_2023_2025.png",
                          f"Most mentioned in 2023–2025: {t}",
                          f"Data/BI/analytics analyst ads on Platsbanken, 2023–2025, n = {len(late):,} ads, "
                          f"{late['employer_key'].nunique():,} employers", top=22)
    tools = [k for k in ["sql", "python", "excel", "power_bi", "r", "tableau", "qlik", "sas", "azure", "gcp", "statistics",
                         "machine_learning", "ai_any", "english_req", "swedish_req", "degree"] if k not in gate_fail]
    # The hero chart also shows the two clearest rising trends and the most-mentioned skill (README findings 2–3).
    hero = tools + [k for k in ["visualization", "any_cloud_vendor", "communication"] if k not in gate_fail]
    ch = pd.DataFrame(changes["pooled"])
    ch = ch[ch["skill"].isin(hero)]
    da_verdict = {r["skill"]: r["verdict"] for r in changes["data_analyst_only"]}

    def tag(k):  # dagger = not a clear change within data-analyst titles (D11)
        return labels[k] + ("†" if da_verdict.get(k) != ch.set_index("skill").loc[k, "verdict"] else "")

    rising = [tag(k) for k in ch[ch["verdict"] == "rising"].sort_values("diff", ascending=False)["skill"]][:3]
    falling = [tag(k) for k in ch[ch["verdict"] == "falling"].sort_values("diff")["skill"]][:3]
    title = "Clearly rising: " + (", ".join(rising) or "none") + " · falling: " + (", ".join(falling) or "none")
    figures.dumbbell(ch, labels, fig / "change_early_late.png", title,
                     "Share of ads 2016–2018 vs 2023–2025, all analyst titles; ▲/▼ = clear change (BH-adjusted trend "
                     "p < 0.05 and ≥ 5 pp); † = not a clear change within data-analyst titles (title-mix effect)",
                     "2016–2018", "2023–2025")
    sm_keys = [k for k in ["sql", "python", "excel", "power_bi", "r", "tableau", "qlik", "sas", "statistics",
                           "machine_learning", "ai_any", "english_req"] if k not in gate_fail]
    figures.small_multiples(pd.DataFrame(out["yearly"]), sm_keys, labels, fig / "trends_by_year.png",
                            "Skill mentions by year, 2016–2025",
                            f"Data/BI/analytics analyst ads; yearly samples are small ({yr['n'].min():,}–{yr['n'].max():,} ads)")
    s_late = by_area.pivot(index="skill", columns="group", values=["share", "lo", "hi"])
    sdf = pd.DataFrame({"skill": s_late.index,
                        "share_a": s_late[("share", "Rest of Sweden")].values, "lo_a": s_late[("lo", "Rest of Sweden")].values,
                        "hi_a": s_late[("hi", "Rest of Sweden")].values, "share_b": s_late[("share", "Stockholm")].values,
                        "lo_b": s_late[("lo", "Stockholm")].values, "hi_b": s_late[("hi", "Stockholm")].values})
    sdf = sdf[sdf["skill"].isin(tools)]
    adjd = adj.set_index("skill")
    sig = [labels[k] for k in sdf["skill"] if k in adjd.index and adjd.loc[k, "p_bh"] < 0.05]
    figures.two_group_dots(sdf, labels, fig / "stockholm_vs_rest.png",
                           "Stockholm vs rest of Sweden: " + (("clear gaps for " + ", ".join(sig[:4])) if sig else "no clear gaps"),
                           "2023–2025 shares; clear = BH-adjusted p < 0.05 in a model with year fixed effects, all years",
                           "Rest of Sweden", "Stockholm")
    print(json.dumps({"n": out["n_ads"], "late_n": out["late"]["n"], "gate_fail": gate_fail}, indent=1))


def bundles() -> None:
    import numpy as np
    import pandas as pd

    from adskills import analysis, figures, skills, stats

    dq = json.loads((config.REPORTS / "data_quality_summary.json").read_text(encoding="utf-8"))
    den = dq["denominators"]
    labels = {s.key: s.label for s in skills.SKILLS}
    out: dict = {}

    # 1. Volume per 10,000 ads (all population ads, incl. short texts).
    ads = load_analysis_ads()
    vol = []
    for y in config.YEARS:
        k = int((ads["year"] == y).sum())
        n = int(den["total_by_year"][str(y)])
        lo, hi = stats.wilson(k, n)
        row = {"year": y, "ads": k, "all_ads": n, "per_10k": k / n * 1e4, "lo": lo * 1e4, "hi": hi * 1e4}
        for area in ("Stockholm", "Rest of Sweden"):
            ka = int(((ads["year"] == y) & (ads["area"] == area)).sum())
            na = int(den["by_year_area"].get(f"{y}|{area}", 0))
            row[f"{area}_per_10k"] = ka / na * 1e4 if na else None
        vol.append(row)
    out["volume"] = vol
    out["neighbours_by_year"] = dq["neighbour_categories_by_year"]
    v = pd.DataFrame(vol)
    peak = v.loc[v["per_10k"].idxmax()]
    figures.bars(v["year"].tolist(), v["per_10k"].round(1).tolist(), config.FIGURES / "volume_per_10k.png",
                 f"Analyst ads per 10,000 Platsbanken ads: {v['per_10k'].iloc[0]:.1f} in 2016, "
                 f"{peak['per_10k']:.1f} in {int(peak['year'])}, {v['per_10k'].iloc[-1]:.1f} in 2025 "
                 f"({v['per_10k'].iloc[-1] / v['per_10k'].iloc[0]:.1f}× 2016)",
                 "Data/BI/analytics analyst ads per 10,000 ads published on Platsbanken; 2025 total is 6.5 % below the API count",
                 "Ads per 10,000")

    # 2. Co-occurrence of tools in 2023-2025.
    df, _ = analysis_frame_with_skills()
    late = df[df["year"].between(*analysis.LATE)]
    tools = ["sql", "python", "r", "excel", "power_bi", "tableau", "qlik", "looker", "sas", "azure", "aws", "gcp",
             "dbt", "statistics", "machine_learning", "etl_dw", "visualization", "experimentation", "ai_any"]
    pairs = []
    n = len(late)
    for i, a in enumerate(tools):
        for b in tools[i + 1:]:
            pa, pb = late[a].mean(), late[b].mean()
            pab = (late[a] & late[b]).mean()
            if pa == 0 or pb == 0:
                continue
            phi = (pab - pa * pb) / np.sqrt(pa * (1 - pa) * pb * (1 - pb))
            pairs.append({"a": a, "b": b, "n_both": int((late[a] & late[b]).sum()), "p_b_given_a": pab / pa,
                          "lift": pab / (pa * pb), "phi": float(phi)})
    pairs = pd.DataFrame(pairs).sort_values("phi", ascending=False)
    out["cooccurrence_late"] = {"n": n, "pairs": pairs.to_dict("records")}
    cond = {}
    for a in ("sql", "python", "power_bi", "excel"):
        sub = late[late[a]]
        cond[a] = {"n": int(len(sub)), **{b: float(sub[b].mean()) for b in tools if b != a}}
    out["conditional_late"] = cond

    # 3. Generative AI: list every match so precision can be checked by reading (D14: unmeasured).
    gen = df[df["genai"]]
    out["genai_matches"] = [{"id": r.id, "year": int(r.year), "terms": r.genai_terms.split(";")} for r in gen.itertuples()]
    out["genai_by_year"] = {int(y): int(c) for y, c in df.groupby("year")["genai"].sum().items()}
    out["ai_any_by_year"] = {int(y): float(c) for y, c in df.groupby("year")["ai_any"].mean().items()}
    _write_json(config.REPORTS / "bundles.json", out)
    print(pairs.head(8).to_string())


ROBUST_KEYS = ["sql", "python", "excel", "power_bi", "r", "sas", "tableau", "azure", "any_cloud_vendor", "statistics",
               "visualization", "ai_any", "degree", "english_req"]
JOBTECH_TAGS = {"sql": {"sql"}, "python": {"python"}, "excel": {"excel"}, "power_bi": {"powerbi", "power bi"},
                "tableau": {"tableau"}, "sas": {"sas"}, "r": {"r"}}


def _variant_frame(name, base, raw_dedup60=None):
    import numpy as np

    from adskills import titles

    if name == "primary":
        return base
    if name == "no_agencies":
        return base[~base["agency"]]
    if name == "swedish_ads":
        return base[base["language"] == "sv"]
    if name == "english_ads":
        return base[base["language"] == "en"]
    if name == "narrow_titles":
        return base[base["category"].isin(["data_analyst", "bi_analyst"])]
    if name == "one_ad_per_employer_year":
        rng = np.random.default_rng(config.SEED)
        return base.assign(_r=rng.random(len(base))).sort_values("_r").drop_duplicates(["employer_key", "year"]).drop(columns="_r")
    if name == "dedup_60_days":
        return raw_dedup60
    if name == "broad_titles":
        return raw_dedup60  # replaced by caller
    raise ValueError(name)


def robustness() -> None:
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    from adskills import analysis, figures, quality, skills, titles

    base, _ = analysis_frame_with_skills()
    base["period"] = analysis.period(base["year"])
    # Variants that need a different extract: 60-day de-duplication and broad titles.
    raw = quality.load_features(config.DATA_PROCESSED / quality.FEATURES_FILE)

    def from_raw(d, keep_cats):
        d = d[d["drop_reason"].isna() & d["category"].isin(keep_cats) & d["year"].between(min(config.YEARS), max(config.YEARS))]
        d = d[d["desc_len"] >= 200].copy()
        d = analysis.add_groups(d)
        d["year"] = d["year"].astype(int)
        d["period"] = analysis.period(d["year"])
        return d

    d60 = from_raw(quality.deduplicate(raw, window_days=60), titles.PRIMARY)
    broad = from_raw(quality.deduplicate(raw), titles.BROAD)
    names = ["primary", "no_agencies", "dedup_60_days", "one_ad_per_employer_year", "narrow_titles", "broad_titles",
             "swedish_ads", "english_ads"]
    rows = []
    for name in names:
        d = broad if name == "broad_titles" else _variant_frame(name, base, d60)
        diff = analysis.cluster_bootstrap_diff(d, ROBUST_KEYS, "employer_key", "period", "early", "late", n_boot=1000, seed=config.SEED)
        tr = analysis.trends(d, ROBUST_KEYS)
        m = diff.merge(tr[["skill", "or_per_year", "p_bh"]], on="skill")
        m["variant"] = name
        m["n"] = len(d)
        rows.append(m)
    rob = pd.concat(rows)
    out = {"variants": rob.to_dict("records")}

    # Stockholm gap adjusted for title category (and year).
    st = []
    d = base[base["area"].isin(["Stockholm", "Rest of Sweden"])].assign(sthlm=lambda x: (x["area"] == "Stockholm").astype(int))
    for k in ROBUST_KEYS + ["gcp", "looker", "experimentation", "machine_learning", "dbt"]:
        dd = d.assign(y=d[k].astype(int))
        fit = smf.glm("y ~ sthlm + C(year) + C(category)", data=dd, family=sm.families.Binomial()).fit(
            cov_type="cluster", cov_kwds={"groups": pd.factorize(dd["employer_key"])[0]})
        b, se = fit.params["sthlm"], fit.bse["sthlm"]
        st.append({"skill": k, "or_stockholm": float(np.exp(b)), "lo": float(np.exp(b - 1.96 * se)),
                   "hi": float(np.exp(b + 1.96 * se)), "p": float(fit.pvalues["sthlm"])})
    out["stockholm_title_adjusted"] = st
    out["category_mix_by_area_late"] = {
        f"{a}|{c}": int(n) for (a, c), n in base[base["year"].between(*analysis.LATE)].groupby(["area", "category"]).size().items()}

    # English requirement within Swedish-language ads (is the fall just more English-language ads?).
    sv = base[base["language"] == "sv"]
    out["english_req_in_swedish_ads"] = {int(y): {"n": int(len(g)), "share": float(g["english_req"].mean())} for y, g in sv.groupby("year")}
    out["english_ads_share_by_year"] = {int(y): float((g["language"] == "en").mean()) for y, g in base.groupby("year")}

    # JobTech's own skill tags vs the dictionary (independent extraction, same ads).
    comp = {}
    for k in JOBTECH_TAGS:
        jt = base[f"jt_{k}"]
        by_year = pd.DataFrame({"year": base["year"], "dict": base[k], "jobtech": jt}).groupby("year").mean()
        agree = float((jt == base[k]).mean())
        comp[k] = {"agreement": agree, "by_year": {int(y): {"dictionary": float(r["dict"]), "jobtech": float(r["jobtech"])}
                                                   for y, r in by_year.iterrows()}}
    out["jobtech_tags_comparison"] = comp
    _write_json(config.REPORTS / "robustness.json", out)

    labels = {s.key: s.label for s in skills.SKILLS} | {"any_cloud_vendor": "Any cloud vendor"}
    figures.robustness_grid(rob, ROBUST_KEYS, names, labels, config.FIGURES / "robustness.png",
                            "Change 2016–18 → 2023–25 under eight analysis choices",
                            "Percentage-point change with 95 % employer-cluster interval; first row = primary analysis")
    print(rob[rob["skill"].isin(["sql", "python", "excel"])][["variant", "skill", "diff", "lo", "hi"]].round(3).to_string())


STAGES = {"probe": probe, "schema": schema, "schema_alt": lambda: schema(alt=True, n=20000), "fetch": fetch, "build": build, "reconcile": reconcile, "quality": quality_stage, "annotate_prep": annotate_prep, "validate": validate, "prevalence": prevalence, "bundles": bundles, "robustness": robustness, "reconcile_monthly": reconcile_monthly, "human_prep": human_prep, "human_check": human_check}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    unknown = [a for a in argv if a not in STAGES]
    if unknown:
        print(f"unknown stage(s): {unknown}; known: {sorted(STAGES)}")
        return 2
    for stage in argv:
        t0 = time.time()
        print(f"== {stage}")
        STAGES[stage]()
        print(f"== {stage} done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

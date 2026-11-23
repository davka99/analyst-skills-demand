"""Data quality and the analysis dataset (M3).

Rule: flag, don't delete silently. Every row dropped from the analysis dataset
gets a reason that is counted in the data-quality summary.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from . import config, titles
from .text import normalize

# Staffing and recruitment firms (D9). Matched on the employer name.
AGENCY = re.compile(
    # Compound-friendly words (Swedish compounds such as "Teknikbemanning").
    r"bemanning|rekrytering|recruit|staffing"
    # Named staffing/recruitment/consultant-broker firms, whole words.
    r"|\b(?:academic work|manpower|randstad|adecco|experis|poolia|proffice|uniflex|lernia|"
    r"studentconsulting|student consulting|jefferson wells|wise professionals|hays|michael page|"
    r"robert half|novare|clear people|perido|ework|cinode|keyman|a-hub|brightby|incluso|dfind|"
    r"pe accounting|level recruitment|tng|talent partner|talent solutions)\b",
    re.I,
)
STOCKHOLM = "Stockholms län"
_NON_ALNUM = re.compile(r"[^0-9a-zåäöéü]+")


def load_extract(extract_dir: Path) -> pd.DataFrame:
    """All rows of every ads_<label>.jsonl.gz, in file order (oldest first)."""
    files = sorted(extract_dir.glob("ads_*.jsonl.gz"), key=lambda p: p.name)
    rows = []
    for order, path in enumerate(files):
        label = path.name[len("ads_") : -len(".jsonl.gz")]
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                r["file_label"] = label
                r["file_order"] = order
                rows.append(r)
    return pd.DataFrame(rows)


def headline_key(h: str | None) -> str:
    return _NON_ALNUM.sub(" ", normalize(h)).strip()


def text_hash(t: str | None) -> str:
    return hashlib.sha1(_NON_ALNUM.sub(" ", normalize(t)).strip().encode("utf-8")).hexdigest()[:16]


def employer_key(name: str | None, orgnr: str | None) -> str:
    o = re.sub(r"\D", "", str(orgnr or ""))
    if len(o) == 10:
        return f"org:{o}"
    return f"name:{headline_key(name)}" if name else "unknown"


def is_agency(name: str | None) -> bool:
    return bool(name) and bool(AGENCY.search(str(name)))


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns used by de-duplication and analysis."""
    out = df.copy()
    out["pub_date"] = pd.to_datetime(out["publication_date"].astype(str).str[:10], errors="coerce")
    out["year"] = out["pub_date"].dt.year.astype("Int64")
    out["headline_key"] = out["headline"].map(headline_key)
    out["text_hash"] = out["description"].map(text_hash)
    out["employer_key"] = [employer_key(n, o) for n, o in zip(out["employer_name"], out["employer_orgnr"])]
    out["agency"] = out["employer_name"].map(is_agency)
    out["desc_len"] = out["description"].fillna("").str.len()
    reg = out["region"].fillna("")
    out["area"] = (reg == STOCKHOLM).map({True: "Stockholm", False: "Rest of Sweden"})
    out.loc[reg == "", "area"] = "Unknown"
    out["in_population"] = out["category"].isin(titles.PRIMARY)
    return out


def deduplicate(df: pd.DataFrame, window_days: int | None = None) -> pd.DataFrame:
    """Mark duplicates in a `drop_reason` column (None = kept).

    1. `same_id`: the same ad id in two files (keep the first file).
    2. `repost`: same employer, same normalised headline and identical normalised
       text, published in the same calendar year (keep the earliest). With
       `window_days` set, a repost must also be within that many days of the kept
       ad instead of the same year (sensitivity variant, M7).
    """
    out = df.sort_values(["file_order", "pub_date", "id"], kind="mergesort").copy()
    out["drop_reason"] = None
    dup_id = out.duplicated("id", keep="first")
    out.loc[dup_id, "drop_reason"] = "same_id"
    live = out["drop_reason"].isna()
    keys = ["employer_key", "headline_key", "text_hash"]
    sub = out[live].sort_values(["pub_date", "id"], kind="mergesort")
    if window_days is None:
        rep = sub.duplicated(keys + ["year"], keep="first")
    else:
        rep = pd.Series(False, index=sub.index)
        for _, g in sub.groupby(keys, sort=False):
            last_kept = None
            for idx, date in zip(g.index, g["pub_date"]):
                if last_kept is not None and pd.notna(date) and (date - last_kept).days <= window_days:
                    rep[idx] = True
                else:
                    last_kept = date
    out.loc[rep[rep].index, "drop_reason"] = "repost"
    return out


def analysis_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Population ads in the window, after de-duplication."""
    d = df[df["drop_reason"].isna() & df["in_population"]]
    return d[d["year"].between(min(config.YEARS), max(config.YEARS))].copy()


def summary(df: pd.DataFrame, final: pd.DataFrame) -> dict:
    pop = df[df["in_population"]]
    win = pop[pop["year"].between(min(config.YEARS), max(config.YEARS))]
    by_year = final.groupby("year").size()
    top_emp = final.groupby("employer_name").size()
    top_emp = top_emp.reset_index(name="n").sort_values(["n", "employer_name"], ascending=[False, True]).set_index("employer_name")["n"]
    share_top10 = float(top_emp.head(10).sum() / max(len(final), 1))
    return {
        "rows_extract": int(len(df)),
        "rows_population_any_year": int(len(pop)),
        "rows_population_in_window": int(len(win)),
        "dropped_in_window": win["drop_reason"].value_counts().to_dict(),
        "rows_final": int(len(final)),
        "final_by_year": {int(k): int(v) for k, v in by_year.items()},
        "final_by_year_category": {
            f"{int(y)}|{c}": int(n) for (y, c), n in final.groupby(["year", "category"]).size().items()
        },
        "final_by_area": final["area"].value_counts().to_dict(),
        "final_by_year_area": {f"{int(y)}|{a}": int(n) for (y, a), n in final.groupby(["year", "area"]).size().items()},
        "language": final["language"].fillna("(none)").value_counts().to_dict(),
        "language_by_year": {
            f"{int(y)}|{lang}": int(n)
            for (y, lang), n in final.assign(language=final["language"].fillna("(none)")).groupby(["year", "language"]).size().items()
        },
        "agency_share": round(float(final["agency"].mean()), 4) if len(final) else None,
        "agency_by_year": {int(y): round(float(v), 4) for y, v in final.groupby("year")["agency"].mean().items()},
        "desc_len_quantiles": {str(q): int(final["desc_len"].quantile(q)) for q in (0, 0.01, 0.1, 0.5, 0.9, 1)} if len(final) else {},
        "n_desc_under_300": int((final["desc_len"] < 300).sum()),
        "n_employers": int(final["employer_key"].nunique()),
        "top10_employer_share": round(share_top10, 4),
        "top_employers": [[k, int(v)] for k, v in top_emp.head(15).items()],
        "vacancies_total": int(pd.to_numeric(final["vacancies"], errors="coerce").fillna(1).sum()),
        "region_missing_share": round(float((final["area"] == "Unknown").mean()), 4) if len(final) else None,
    }


# --- features file (D16): everything downstream of `build` works without ad text ----

FEATURES_FILE = "ads_features.csv.gz"
JOBTECH_TAGS = {"sql": {"sql"}, "python": {"python"}, "excel": {"excel"}, "power_bi": {"powerbi", "power bi"},
                "tableau": {"tableau"}, "sas": {"sas"}, "r": {"r"}}


def _short_hash(s: str) -> str:
    return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:16]


def build_features(prepared: pd.DataFrame) -> pd.DataFrame:
    """One row per extract ad: ids, metadata, hashes and 0/1 skill flags; no ad text.

    The employer key and normalised headline are hashed (an org. number can be a
    personal identity number for a sole trader); equality is all de-duplication needs.
    """
    from . import skills

    d = prepared
    text = (d["headline"].fillna("") + "\n" + d["description"].fillna("")).tolist()
    m = skills.skill_matrix(text).astype(int)
    m.index = d.index
    tags = d["jobtech_skills"].apply(lambda v: {str(t).lower() for t in v} if isinstance(v, list) else set())
    out = pd.DataFrame(
        {
            "id": d["id"].astype(str),
            "file_label": d["file_label"],
            "file_order": d["file_order"],
            "pub_date": d["pub_date"].dt.strftime("%Y-%m-%d"),
            "year": d["year"],
            "category": d["category"],
            "employer_name": d["employer_name"],
            "employer_key": d["employer_key"].map(lambda k: "e:" + _short_hash(k)),
            "agency": d["agency"].astype(int),
            "region": d["region"],
            "area": d["area"],
            "language": d["language"],
            "vacancies": d["vacancies"],
            "desc_len": d["desc_len"],
            "headline_key": d["headline_key"].map(_short_hash),
            "text_hash": d["text_hash"],
        },
        index=d.index,
    )
    for k, tagset in JOBTECH_TAGS.items():
        out[f"jt_{k}"] = tags.apply(lambda t: int(bool(t & tagset)))
    out["genai_terms"] = [";".join(sorted(set(skills.matches("genai", t)))) if f else "" for t, f in zip(text, m["genai"])]
    return pd.concat([out, m], axis=1)


def load_features(path: Path) -> pd.DataFrame:
    """Read the features file and restore the columns de-duplication and analysis use."""
    from . import skills

    df = pd.read_csv(path, dtype={"id": str, "employer_key": str, "headline_key": str, "text_hash": str,
                                  "genai_terms": str, "file_label": str})
    df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce")
    df["year"] = df["year"].astype("Int64")
    for c in list(skills.SKILL_KEYS) + [c for c in df.columns if c.startswith("jt_")] + ["agency"]:
        df[c] = df[c].astype(bool)
    df["genai_terms"] = df["genai_terms"].fillna("")
    df["in_population"] = df["category"].isin(titles.PRIMARY)
    return df

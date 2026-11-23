"""One streaming pass over a yearly file: denominators + the analyst-ad extract.

Kept small and pure so that it can be tested offline on a fixture file and reused
by both the probe (one year) and the full fetch (all years).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from . import titles
from .jobtech import FIELDS, flatten

# Ads whose occupation coding looks analytical but whose headline is not classified.
# Kept (without text) so M3 can estimate how many analyst ads the headline rule misses.
CANDIDATE_OCC = re.compile(r"analy|statisti|business intelligence|data", re.I)


@dataclass
class ScanResult:
    n_records: int = 0
    by_month: Counter = field(default_factory=Counter)
    by_month_new: Counter = field(default_factory=Counter)  # ids not seen in an earlier file
    n_seen_before: int = 0
    # Publication-year x region / language counts for ads not seen in an earlier file:
    # the denominators for regional volume and language checks.
    by_year_region_new: Counter = field(default_factory=Counter)
    by_year_language_new: Counter = field(default_factory=Counter)
    n_multi_occupation: int = 0
    text_source: Counter = field(default_factory=Counter)
    by_region: Counter = field(default_factory=Counter)
    by_category: Counter = field(default_factory=Counter)
    vacancies_total: int = 0
    missing: Counter = field(default_factory=Counter)
    extract: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "n_records": self.n_records,
            "by_month": dict(sorted(self.by_month.items())),
            "by_month_new": dict(sorted(self.by_month_new.items())),
            "n_seen_in_earlier_file": self.n_seen_before,
            "by_year_region_new": dict(sorted(self.by_year_region_new.items())),
            "by_year_language_new": dict(sorted(self.by_year_language_new.items())),
            "n_multi_occupation": self.n_multi_occupation,
            "text_source": dict(self.text_source),
            "by_region": dict(self.by_region.most_common()),
            "by_category": dict(self.by_category.most_common()),
            "vacancies_total": self.vacancies_total,
            "missing_share": {k: round(v / max(self.n_records, 1), 4) for k, v in sorted(self.missing.items())},
            "n_extract": len(self.extract),
            "n_candidates": len(self.candidates),
        }


def _month(date: Any) -> str:
    s = str(date or "")
    return s[:7] if re.match(r"\d{4}-\d{2}", s) else "unknown"


def scan(records: Iterable[dict], keep: frozenset[str] | set[str] | None = None, seen: set | None = None) -> ScanResult:
    """Count every record and keep flattened records whose headline category is in `keep`.

    `keep` defaults to every classified category (population, neighbours and context).
    `seen` is a set of ids from files scanned earlier; ids found there are counted in
    `n_seen_before` and left out of `by_month_new`, and the set is updated in place.
    """
    res = ScanResult()
    for ad in records:
        row = flatten(ad, FIELDS)
        res.n_records += 1
        rid = str(row.get("id"))
        if seen is not None:
            if rid in seen:
                res.n_seen_before += 1
                row["seen_in_earlier_file"] = True
            else:
                seen.add(rid)
                m = _month(row["publication_date"])
                res.by_month_new[m] += 1
                res.by_year_region_new[f"{m[:4]}|{row.get('region') or '(none)'}"] += 1
                res.by_year_language_new[f"{m[:4]}|{row.get('language') or '(none)'}"] += 1
                row["seen_in_earlier_file"] = False
        res.text_source[row.get("text_source") or "(none)"] += 1
        occ = ad.get("occupation")
        if isinstance(occ, list) and len(occ) > 1:
            res.n_multi_occupation += 1
        for k in ("headline", "publication_date", "description", "region", "employer_name", "occupation"):
            if row.get(k) in (None, ""):
                res.missing[k] += 1
        res.by_month[_month(row["publication_date"])] += 1
        res.by_region[row.get("region") or "(none)"] += 1
        try:
            res.vacancies_total += int(row.get("vacancies") or 1)
        except (TypeError, ValueError):
            res.vacancies_total += 1
        cat = titles.classify_headline(row.get("headline"))
        res.by_category[cat or "(none)"] += 1
        if cat is not None and (keep is None or cat in keep):
            row["category"] = cat
            res.extract.append(row)
        elif cat is None:
            occ = " ".join(str(row.get(k) or "") for k in ("occupation", "occupation_group"))
            if CANDIDATE_OCC.search(occ):
                res.candidates.append(
                    {k: row.get(k) for k in ("id", "headline", "publication_date", "employer_name", "occupation", "occupation_group", "region")}
                )
    return res

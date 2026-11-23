"""Check that the key numbers quoted in README.md match the result files.

Usage: python scripts/check_readme.py          (exit code 1 on any mismatch)
       python scripts/check_readme.py --print  (show the expected strings)
Each check formats a value from reports/*.json the way the README writes it and
asserts that exact text occurs in README.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))


def pct(x: float) -> str:
    return f"{x * 100:.0f} %"


def pp(x: float) -> str:
    return f"{x * 100:+.0f} pp".replace("-", "−")


def ci(lo: float, hi: float) -> str:
    return f"{lo * 100:.0f}–{hi * 100:.0f} %"


def checks() -> list[tuple[str, str]]:
    prev = load("prevalence.json")
    bun = load("bundles.json")
    rob = load("robustness.json")
    dq = load("data_quality_summary.json")
    late = {r["skill"]: r for r in prev["late"]["shares"]}
    ch = {r["skill"]: r for r in prev["change"]["pooled"]}
    da = {r["skill"]: r for r in prev["change"]["data_analyst_only"]}
    var = {(r["variant"], r["skill"]): r for r in rob["variants"]}
    st = {r["skill"]: r for r in rob["stockholm_title_adjusted"]}
    sdiff = {r["skill"]: r for r in prev["stockholm"]["diff_late"]}
    vol = {r["year"]: r for r in bun["volume"]}
    out = [
        ("population", f"{dq['rows_final']:,} ads"),
        ("employers", f"{dq['n_employers']:,} employers"),
        ("late n", f"{prev['late']['n']:,} ads from {prev['late']['n_employers']} employers"),
        ("vol 2016", f"{vol[2016]['per_10k']:.1f} per 10,000"),
        ("vol 2025", f"{vol[2025]['per_10k']:.1f} in 2025"),
        ("vol sthlm", f"{vol[2016]['Stockholm_per_10k']:.1f} → {vol[2025]['Stockholm_per_10k']:.1f}"),
        ("vol rest", f"{vol[2016]['Rest of Sweden_per_10k']:.1f} → {vol[2025]['Rest of Sweden_per_10k']:.1f}"),
        ("genai", f"{sum(bun['genai_by_year'].values())} of {prev['n_ads']:,} ads"),
        ("python given sql", f"{pct(bun['conditional_late']['python']['sql'])} of ads that mention Python"),
        ("power bi given sql", f"{pct(bun['conditional_late']['power_bi']['sql'])} of Power BI ads"),
    ]
    for k in ("sql", "python", "excel", "power_bi", "r", "tableau", "azure", "gcp", "statistics", "visualization",
              "communication", "reporting", "degree", "ai_any"):
        r = late[k]
        out.append((f"late {k}", f"{pct(r['share'])} ({ci(r['lo'], r['hi'])})"))
    for k in ("excel", "sas", "any_cloud_vendor", "visualization", "python", "sql", "english_req"):
        r = ch[k]
        out.append((f"change {k}", f"{pct(r['share_a'])} → {pct(r['share_b'])}"))
    out.append(("sql within da", f"{pct(da['sql']['share_a'])} → {pct(da['sql']['share_b'])}"))
    r = var[("narrow_titles", "sql")]
    out.append(("sql narrow", f"{pp(r['diff'])} (CI {r['lo'] * 100:.0f} to {r['hi'] * 100:+.0f} pp)".replace("-", "−")))
    r = var[("narrow_titles", "python")]
    out.append(("python narrow", f"{pp(r['diff'])} (CI {r['lo'] * 100:+.0f} to {r['hi'] * 100:+.0f} pp)".replace("-", "−")))
    out.append(("eng en", f"{pp(var[('english_ads', 'english_req')]['diff'])} in English-language ads"))
    out.append(("eng sv", f"{pp(var[('swedish_ads', 'english_req')]['diff'])} in Swedish-language ads"))
    for k in ("sql", "tableau", "gcp", "machine_learning"):
        r = st[k]
        out.append((f"sthlm {k}", f"OR {r['or_stockholm']:.2f} ({r['lo']:.2f}–{r['hi']:.2f})"))
    r = sdiff["sql"]
    out.append(("sthlm sql shares", f"{pct(r['share_b'])} vs {pct(r['share_a'])}"))
    return out


def main(show: bool = False) -> int:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    bad = 0
    for name, expected in checks():
        ok = expected in text
        if show or not ok:
            print(("OK   " if ok else "MISS ") + f"{name}: {expected}")
        bad += not ok
    print(f"{len(checks()) - bad}/{len(checks())} README numbers match")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main("--print" in sys.argv))

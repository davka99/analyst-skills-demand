"""Skill dictionary v1.1 (D4, D13, D14). Frozen in M4 after the development sample; any
later change is logged in docs/decisions.md as a post-result change.

Matching runs on normalised text (see text.normalize). Swedish compounds mean that
many patterns only need a left boundary: "excelkunskaper", "pythonprogrammering",
"sql-kunskaper". Where a short token is ambiguous (R, SAS, AI, ML) the pattern asks
for context; precision is measured per skill in M4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .text import normalize

L = r"(?<![a-zåäö0-9])"  # left boundary that also works inside Swedish text
R = r"(?![a-zåäö0-9])"  # right boundary
_LANGS = r"(?:python|sas|spss|stata|sql|matlab|julia|scala|java|c\+\+|excel|vba)"
_SEP = r"\s*(?:[/,&]|och|and|eller|or)(?:\s*(?:[/,&]|och|and|eller|or))*\s*"  # "python, or r"


@dataclass(frozen=True)
class Skill:
    key: str
    label: str
    group: str
    pattern: re.Pattern[str]


def _s(key: str, label: str, group: str, *patterns: str) -> Skill:
    return Skill(key, label, group, re.compile("|".join(f"(?:{p})" for p in patterns)))


SKILLS: tuple[Skill, ...] = (
    # Tools and languages
    _s("excel", "Excel", "tool", L + r"excel(?!l)", L + r"ms[- ]?excel"),
    _s("sql", "SQL", "tool", L + r"(?:t-|pl/|my|ms )?sql", L + r"postgres(?:ql)?" + R),
    _s("python", "Python", "tool", L + r"python"),
    _s(
        "r",
        "R",
        "tool",
        _LANGS + _SEP + r"r" + r"(?![a-zåäö0-9&+'])",
        L + r"r" + _SEP + _LANGS,
        L + r"rstudio",
        L + r"r-?(?:programmering|programming|kod|code|paket|package|script|skript)",
        r"(?:programmeringsspråk\w*|programming languages?)\s+(?:som|such as|like|t\.?\s?ex\.?|exempelvis|e\.g\.)?\s*r" + R,
    ),
    _s("sas", "SAS", "tool", L + r"sas" + R + r"(?!\s*(?:airlines|scandinavian|group|koncernen))"),
    _s("spss", "SPSS", "tool", L + r"spss" + R),
    _s("stata", "Stata", "tool", L + r"stata" + R),
    _s("vba", "VBA", "tool", L + r"vba" + R),
    _s("power_bi", "Power BI", "bi_tool", L + r"power\s*-?\s*bi" + R, L + r"pbi" + R),
    _s("dax", "DAX", "bi_tool", L + r"dax" + R),
    _s("tableau", "Tableau", "bi_tool", L + r"tableau"),
    _s("qlik", "Qlik", "bi_tool", L + r"qlik"),
    _s("looker", "Looker / Data Studio", "bi_tool", L + r"looker", r"google data studio"),
    # Data platforms
    _s("azure", "Azure", "platform", L + r"azure"),
    _s("aws", "AWS", "platform", L + r"aws" + R, r"amazon web services"),
    _s("gcp", "Google Cloud / BigQuery", "platform", r"google cloud", L + r"gcp" + R, L + r"big\s*query"),
    _s("snowflake", "Snowflake", "platform", L + r"snowflake"),
    _s("databricks", "Databricks", "platform", L + r"databricks"),
    _s("dbt", "dbt", "platform", L + r"dbt" + R),
    _s("spark", "Spark", "platform", L + r"(?:py)?spark" + R),
    _s("git", "Git", "platform", L + r"git" + R, L + r"github", L + r"gitlab"),
    _s("cloud_any", "Cloud (generic mention)", "platform", L + r"cloud" + R, L + r"moln(?:et|tjänst|baserad|plattform)"),
    # Methods
    # Any mention, incl. compounds such as "webbstatistik" and "statistik" meaning
    # figures (v1, D13): the regex cannot tell method from figures reliably.
    _s("statistics", "Statistics (any mention)", "method", r"statisti(?:k|sk|cs|cal)"),
    _s("machine_learning", "Machine learning", "method", r"machine\s*-?\s*learning", r"maskininlärning", L + r"ml" + R),
    _s("forecasting", "Forecasting", "method", L + r"forecast", r"prognos", L + r"prediktiv", L + r"predict", L + r"förutse"),
    _s(
        "experimentation",
        "A/B testing",
        "method",
        L + r"a\s*/\s*b" + R,
        L + r"ab[- ]?test",
        r"split[- ]?test",
        L + r"experimentation",
        r"experimentdesign",
        r"controlled experiment",
    ),
    _s(
        "etl_dw",
        "ETL / data warehouse",
        "method",
        L + r"etl" + R,
        L + r"elt" + R,
        r"data\s*-?\s*warehous",
        r"datalager",
        L + r"dwh" + R,
        r"datamodell",
        r"data\s*model",
        r"modellering av data",
        r"data\s*vault",
    ),
    _s("visualization", "Data visualisation", "method", r"visuali[sz]", L + r"dashboard", r"data\W+(?:\w+\W+){0,2}visuell", r"visuell\w*\W+(?:\w+\W+){0,6}data"),
    # Reports as a task or deliverable; not a reporting line ("reports to the CTO",
    # "rapporterar till marknadschefen") (v1).
    _s(
        "reporting",
        "Reporting",
        "method",
        # v1.1 (D14): the word must be complete before the look-ahead, otherwise the
        # regex backtracks ("report|ing to the head") and the exclusion never fires.
        r"rapport(?!er(?:ar|a)\s+(?:\w+\s+){0,2}till)",
        L + r"report(?:s|ing|ed)?(?![a-z])(?!\s+(?:directly\s+|direct\s+)?(?:to|in to|into)\b)",
    ),
    # AI
    _s(
        "ai_any",
        "AI (any mention)",
        "ai",
        L + r"ai" + R,
        r"artificiell intelligens",
        r"artificial intelligence",
    ),
    _s(
        "genai",
        "Generative AI / LLM",
        "ai",
        r"generativ\w*\s+ai",
        r"generative\s+ai",
        L + r"genai" + R,
        L + r"llms?" + R,
        r"large language model",
        r"språkmodell",
        L + r"chatgpt",
        L + r"gpt-?\d",
        L + r"copilot",
    ),
    # Requirements
    _s(
        "degree",
        "University degree",
        "requirement",
        r"högskoleexamen",
        r"universitetsexamen",
        r"kandidatexamen",
        r"masterexamen",
        r"magisterexamen",
        r"civilingenjörsexamen",
        L + r"examen",
        r"högskoleutbildning",
        r"universitetsutbildning",
        r"högskolenivå",
        r"(?:kandidat|magister|master)(?:-|\s+eller\s+\w+)?utbildning",
        L + r"msc" + R,
        r"master of science",
        L + r"ph\.?d" + R,
        r"doktorsexamen",
        L + r"degree(?!\s+of)",
        r"akademisk (?:utbildning|examen)",
        r"eftergymnasial utbildning",
        L + r"bachelor",
        r"master'?s",
        r"university degree",
        r"academic degree",
    ),
    _s("yh", "Vocational (YH) education", "requirement", L + r"yrkeshögskol", L + r"yh" + R, r"kvalificerad yrkesutbildning"),
    _s(
        "english_req",
        "English required",
        "requirement",
        r"engelska i (?:både )?tal och skrift",
        r"svenska\s*(?:och|samt|&|,)\s*engelska",
        r"(?:kunskaper|språkkunskaper|flytande|obehindrat?|behärskar|talar|skriver|kommunicera\w*)[^.;•*]{0,60}engelska",
        r"engelska[^.;•*]{0,40}(?:tal och skrift|krav|meriterande|obehindrat|flytande)",
        r"(?:fluen\w*|proficien\w*|command of|skills? in|speak\w*|verbal|written)[^.;•*]{0,40}english",
        r"english(?![^.;•*]{0,15}\bnot\b)[^.;•*]{0,30}(?:skills|fluen\w*|proficien\w*|required|requirement|is a must)",
        r"swedish\s*(?:and|&|,)\s*english",
        r"engelska\s+(?:och|samt|&)\s+svenska\s+i\s+(?:både\s+)?tal och skrift",
        r"(?:swedish|svenska) (?:and|och) english",
        r"english (?:and|och) (?:swedish|svenska)",
        r"(?:flytande|god|goda|mycket god|mycket goda|obehindrad)\s+(?:kunskaper i\s+)?engelska",
        r"fluent (?:in )?english",
        r"english,? (?:both )?(?:written and spoken|spoken and written|in speech and writing)",
        r"proficien\w* in english",
    ),
    _s(
        "swedish_req",
        "Swedish required",
        "requirement",
        r"svenska i (?:både )?tal och skrift",
        r"engelska\s*(?:och|samt|&|,)\s*svenska",
        r"svenska\s*(?:och|samt|&|,)\s*engelska",  # v1.1 (D14): was only in english_req
        r"(?:kunskaper|språkkunskaper|flytande|obehindrat?|behärskar|talar|skriver|kommunicera\w*)[^.;•*]{0,60}svenska(?!\s+(?:bostad|marknad|företag|verksamhet|myndighet|ambassad|kund))",
        r"svenska(?:\s+språket)?[^.;•*]{0,40}(?:tal och skrift|krav|meriterande|obehindrat|flytande)",
        r"(?:fluen\w*|proficien\w*|command of|skills? in|speak\w*|verbal|written|learning of|knowledge (?:of|in))[^.;•*]{0,40}swedish",
        r"swedish(?![^.;•*]{0,15}\bnot\b)[^.;•*]{0,30}(?:skills|fluen\w*|proficien\w*|required|requirement|is a must|is a merit|desirable)",
        r"english\s*(?:and|&|,)\s*swedish",
        r"svenska\s+(?:och|samt|&)\s+engelska\s+i\s+(?:både\s+)?tal och skrift",
        r"(?:flytande|god|goda|mycket god|mycket goda|obehindrad)\s+(?:kunskaper i\s+)?svenska",
        r"fluent (?:in )?swedish",
        r"swedish,? (?:both )?(?:written and spoken|spoken and written|in speech and writing)",
        r"proficien\w* in swedish",
    ),
    # Soft skills
    _s(
        "communication",
        "Communication / stakeholders",
        "soft",
        r"kommunikativ",
        r"kommunikationsförmåga",
        r"communication skills",
        r"communicat\w+ (?:insights|results|findings)",
        r"communicator",
        r"(?:good|excellent|strong|clear|great) (?:\w+ )?communicat",
        r"communicate",
        r"kommunicera",
        r"(?:presentera|present)\w*\s+(?:\w+\s+){0,3}(?:insikter|insights|resultat|results|findings|slutsatser|statistik|data|analys)",
        r"förklara\w*\s+(?:\w+\s+){0,3}(?:insikter|resultat|data|statistik)",
        L + r"stakeholder",
        L + r"intressent",
    ),
)

SKILL_KEYS: tuple[str, ...] = tuple(s.key for s in SKILLS)
_BY_KEY = {s.key: s for s in SKILLS}


def find_skills(text: str | None, *, normalized: bool = False) -> set[str]:
    """Return the set of skill keys mentioned in a text."""
    t = text if normalized else normalize(text)
    if not t:
        return set()
    return {s.key for s in SKILLS if s.pattern.search(t)}


def matches(key: str, text: str | None) -> list[str]:
    """All matched substrings for one skill (used for audit and annotation)."""
    t = normalize(text)
    return [m.group(0) for m in _BY_KEY[key].pattern.finditer(t)]


def skill_matrix(texts, *, normalized: bool = False):
    """Boolean DataFrame: one row per text, one column per skill key."""
    import pandas as pd

    rows = [find_skills(t, normalized=normalized) for t in texts]
    return pd.DataFrame({k: [k in r for r in rows] for k in SKILL_KEYS}, dtype=bool)

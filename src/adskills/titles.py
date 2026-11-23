"""Headline classifier that defines the study population (D2).

Rules are checked in order and the first match wins. Only the categories in
PRIMARY form the population; the others are kept so that later milestones can
report a broader sensitivity population and compare neighbouring roles.

Swedish job titles are compounds ("dataanalytiker", "BI-analytiker"), so most
patterns have no word boundary between the parts.
"""

from __future__ import annotations

import re

from .text import normalize

_ANALYST = r"analy(?:tiker|st)"

RULES: list[tuple[str, re.Pattern[str]]] = [
    # Excluded look-alikes found in the M1 probe (D5), checked first:
    # "Online Data Analyst" ads are crowd-work search-rating gigs, and
    # "Master Data Analyst" is master-data management (ERP data upkeep).
    ("online_rater", re.compile(r"online\s+data\s*-?\s*analy")),
    ("master_data", re.compile(r"master\s*-?\s*data\s*-?\s*analy")),
    # "Data Analyst", "Dataanalytiker", "Data-analytiker", "Senior data analyst",
    # and "Analytiker inom data/BI" written the other way round.
    (
        "data_analyst",
        re.compile(
            rf"data\s*-?\s*{_ANALYST}"
            rf"|\b{_ANALYST}\b[^,;|/()]{{0,25}}\b(?:inom|within|for|för|i|in|mot)\s+(?:data|bi)\b"
        ),
    ),
    # "BI-analytiker", "BI Analyst", "Business Intelligence Analyst/-analytiker".
    (
        "bi_analyst",
        re.compile(rf"(?<![a-zåäö])bi\s*-?\s*{_ANALYST}|business\s+intelligence\s*-?\s*{_ANALYST}"),
    ),
    # Analytics-type analyst roles that are data-analyst work under another name.
    (
        "analytics_analyst",
        re.compile(
            r"(?<![a-zåäö])(?:analytics|insights?|reporting|rapport|web|webb|digital|marketing|"
            r"marknads|product|produkt|customer|kund|sales|försäljnings|commercial|people|hr|"
            r"e-?commerce|e-?handels|crm)\s*-?\s*" + _ANALYST
        ),
    ),
    # Neighbouring roles: not in the population, counted for context.
    (
        "bi_developer",
        re.compile(
            r"(?<![a-zåäö])bi\s*-?\s*(?:developer|utvecklare|konsult|consultant|specialist|engineer|ingenjör|arkitekt|architect)"
            r"|business\s+intelligence\s*-?\s*(?:developer|utvecklare|konsult|consultant|specialist)"
        ),
    ),
    ("data_scientist", re.compile(r"data\s*-?\s*scien")),
    ("data_engineer", re.compile(r"data\s*-?\s*(?:engineer|ingenjör)")),
    ("statistician", re.compile(r"statistiker|statistician")),
]

PRIMARY = frozenset({"data_analyst", "bi_analyst", "analytics_analyst"})
BROAD = PRIMARY | {"bi_developer", "statistician"}


def classify_headline(headline: str | None) -> str | None:
    """Return the first matching category for a headline, or None."""
    t = normalize(headline)
    if not t:
        return None
    for name, pattern in RULES:
        if pattern.search(t):
            return name
    return None


def in_population(headline: str | None) -> bool:
    return classify_headline(headline) in PRIMARY

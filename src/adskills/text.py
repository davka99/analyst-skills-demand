"""Text normalisation shared by the title classifier and the skill dictionary."""

from __future__ import annotations

import html
import re
import unicodedata

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def normalize(text: str | None) -> str:
    """Lower-case, strip HTML tags/entities, unify dashes and whitespace.

    Swedish letters are kept (å, ä, ö) because many skill words are Swedish
    compounds such as "excelkunskaper" or "statistikkunskaper".
    """
    if not text:
        return ""
    t = html.unescape(str(text))
    t = _TAGS.sub(" ", t)
    t = unicodedata.normalize("NFC", t)
    t = t.translate(_DASHES).replace("\u00a0", " ")
    return _WS.sub(" ", t).strip().lower()


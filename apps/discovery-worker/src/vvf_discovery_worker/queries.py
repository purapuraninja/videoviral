"""Query variation generation.

Creates 3-8 query variations from the keyword and admin research prompt so the
discovery worker can fan out parallel wigolo searches (section 8, step 1).
"""

from __future__ import annotations

import itertools


VARIATION_TEMPLATES = [
    "{kw} terkini",
    "{kw} hari ini",
    "{kw} terbaru",
    "berita {kw}",
    "{kw} viral",
    "{kw} terbaru 2026",
    "kabar {kw}",
    "{kw} update",
]


def build_query_variations(keyword: str, research_prompt: str = "") -> list[str]:
    """Return 3-8 distinct query variations for a keyword."""
    keyword = keyword.strip()
    if not keyword:
        return []
    base = {t.format(kw=keyword) for t in VARIATION_TEMPLATES}
    variations = list(base)
    # If the admin prompt adds extra terms, fold them in as one more query.
    if research_prompt.strip():
        variations.append(f"{keyword} {research_prompt.strip()[:80]}")
    # Keep a deterministic, bounded set of 3-8.
    variations = variations[:8]
    return variations if len(variations) >= 3 else variations + [keyword]

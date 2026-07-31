"""Group source documents that cover the same story (IMPLEMENTATION_PLAN.md §8.6).

With mock data, grouping by publisher was adequate. Against real wigolo results it
is wrong: one outlet publishes many unrelated articles, so publisher-grouping
collapses distinct stories into a single candidate and hides others.

Instead we group by **title similarity**, which is what "the same story" actually
means across outlets: the same event reported by BMKG, Detik, and Kompas shares
most of its significant title words even though the publishers differ.

The algorithm is deliberately simple and deterministic (no LLM, no embeddings):

1. Reduce each title to a set of significant tokens (lowercased, stopwords and
   single characters dropped, digits kept because magnitudes/dates matter).
2. Compare with the **overlap coefficient** — ``|A∩B| / min(|A|,|B|)`` — not
   Jaccard. Jaccard punishes headlines of different lengths, which is exactly
   what happens across outlets ("Gempa M5.2 guncang Bali" vs "Gempa Bali
   magnitudo 5,2 kedalaman 10 km"): the shared subject is the signal, the extra
   detail in the longer headline should not count against it.
3. Require at least ``_MIN_SHARED_TOKENS`` tokens in common so a single
   coincidental word (e.g. "Bali") cannot merge unrelated stories.
4. Single-link agglomeration; anything matching nothing forms its own group.

Deterministic ordering (highest quality first) keeps runs reproducible.
"""

from __future__ import annotations

import re
from typing import Iterable, Protocol

# Indonesian + English function words that carry no topical signal.
_STOPWORDS = frozenset(
    {
        # Indonesian
        "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "adalah",
        "ini", "itu", "atau", "juga", "akan", "tidak", "sudah", "telah", "usai",
        "saat", "karena", "oleh", "dalam", "para", "bagi", "agar", "namun",
        "tapi", "tetapi", "hingga", "sampai", "kata", "soal", "jadi", "lebih",
        "bisa", "ada", "apa", "siapa", "kapan", "mengapa", "bagaimana",
        "terkini", "terbaru", "hari", "berita", "video",
        # English
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
        "is", "are", "was", "were", "be", "been", "at", "by", "from", "as",
        "that", "this", "it", "its", "after", "over", "new", "latest", "news",
        "says", "said", "how", "why", "what", "when", "who",
    }
)

_TOKEN_RE = re.compile(r"[0-9a-z]+", re.IGNORECASE)

# Overlap coefficient threshold for "the same story".
_MIN_OVERLAP = 0.5
# Absolute floor so one shared word cannot merge unrelated stories.
_MIN_SHARED_TOKENS = 2
# Single characters are noise (e.g. the "2" split out of "M5.2").
_MIN_TOKEN_LEN = 2


class _HasTitle(Protocol):
    title: str | None
    canonical_url: str
    source_quality_score: float | None


def title_tokens(title: str | None) -> frozenset[str]:
    """Significant, comparable tokens of a headline."""
    if not title:
        return frozenset()
    tokens = {t.lower() for t in _TOKEN_RE.findall(title) if len(t) >= _MIN_TOKEN_LEN}
    return frozenset(t for t in tokens if t not in _STOPWORDS)


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    """Overlap coefficient — ``|A∩B| / min(|A|,|B|)`` (0.0 when either is empty).

    Chosen over Jaccard because news headlines for the same event differ wildly
    in length; the shared subject matters, the extra detail should not dilute it.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def group_by_story(docs: Iterable[_HasTitle]) -> list[list[_HasTitle]]:
    """Cluster documents that report the same story.

    Returns groups ordered by their best source-quality score, each group's
    members likewise ordered, so candidate ranking is deterministic.
    """
    ordered = sorted(
        docs, key=lambda d: (-(d.source_quality_score or 0.0), d.canonical_url)
    )

    groups: list[list[_HasTitle]] = []
    group_tokens: list[frozenset[str]] = []

    for doc in ordered:
        tokens = title_tokens(doc.title)
        best_index, best_score = -1, 0.0
        for index, existing in enumerate(group_tokens):
            shared = len(tokens & existing)
            if shared < _MIN_SHARED_TOKENS:
                continue
            score = similarity(tokens, existing)
            if score > best_score:
                best_index, best_score = index, score

        if best_index >= 0 and best_score >= _MIN_OVERLAP:
            groups[best_index].append(doc)
            # Union keeps the group's vocabulary growing as coverage widens,
            # so a third article matching either headline still joins.
            group_tokens[best_index] = group_tokens[best_index] | tokens
        else:
            groups.append([doc])
            group_tokens.append(tokens)

    return groups


__all__ = ["group_by_story", "similarity", "title_tokens"]

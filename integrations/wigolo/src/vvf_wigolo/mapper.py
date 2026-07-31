"""Normalize wigolo results into VVF ``SourceDocumentRaw`` contracts.

Canonicalizes URLs, deduplicates by canonical URL, and computes a basic
content hash so downstream dedup/caching is deterministic. Never relies solely
on an LLM summary — raw excerpts are always preserved.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

from vvf_contracts.research import SourceDocumentRaw
from vvf_wigolo.client import WigoloSearchHit, WigoloSearchResult


def canonicalize_url(url: str) -> str:
    """Lowercase host, strip fragment, drop common tracking query params."""
    if not url:
        return ""
    url = urldefrag(url.strip())[0]
    # urlparse treats "example.com/p" as a path with no host; fix that first.
    parsed = urlparse(url)
    if not parsed.scheme and not parsed.netloc:
        parsed = urlparse("https://" + url)
    if not parsed.scheme:
        parsed = parsed._replace(scheme="https")
    host = (parsed.netloc or "").lower()
    drop = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid"}
    if parsed.query:
        kept = [p for p in parsed.query.split("&") if p.split("=", 1)[0].lower() not in drop]
        parsed = parsed._replace(query="&".join(kept))
    return parsed._replace(netloc=host).geturl()


def _content_hash(url: str, title: str, snippet: str) -> str:
    blob = f"{url}|{title}|{snippet}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def hit_to_source(hit: WigoloSearchHit, fetched_at: datetime | None = None) -> SourceDocumentRaw:
    canonical = canonicalize_url(hit.url)
    excerpt = hit.snippet or ""
    return SourceDocumentRaw(
        canonical_url=canonical,
        title=hit.title,
        publisher=hit.publisher,
        published_at=_parse_dt(hit.published_at),
        fetched_at=fetched_at,
        excerpt=excerpt,
        content_hash=_content_hash(canonical, hit.title, excerpt),
        source_quality_score=hit.score,
    )


def normalize_search_results(
    result: WigoloSearchResult,
    *,
    fetched_at: datetime | None = None,
) -> list[SourceDocumentRaw]:
    """Map + deduplicate a wigolo search result into source documents."""
    seen: dict[str, SourceDocumentRaw] = {}
    for hit in result.hits:
        src = hit_to_source(hit, fetched_at=fetched_at)
        if src.canonical_url in seen:
            # Prefer the higher-quality snippet/publisher.
            existing = seen[src.canonical_url]
            if (src.source_quality_score or 0) > (existing.source_quality_score or 0):
                seen[src.canonical_url] = src
        else:
            seen[src.canonical_url] = src
    return list(seen.values())

"""Discovery pipeline: run a research run end-to-end (section 8)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vvf_contracts.research import SourceDocumentRaw
from vvf_database.models import (
    CandidateSource,
    ContentCandidate,
    ResearchQuery,
    ResearchRun,
    SourceDocument,
)
from vvf_discovery_worker.queries import build_query_variations
from vvf_discovery_worker.scoring import score_candidate
from vvf_shared.logging import get_logger
from vvf_wigolo import WigoloClientProtocol, normalize_search_results

_MAX_CANDIDATES = 5


def _candidate_signals(run: ResearchRun, title: str, docs: list[SourceDocument]):
    snippet = " ".join(d.excerpt for d in docs if d.excerpt)[:600]
    published = min((d.published_at for d in docs if d.published_at), default=None)
    quality = max((d.source_quality_score or 0.0) for d in docs)
    return score_candidate(
        keyword=run.keyword,
        title=title,
        snippet=snippet,
        published_at=published,
        source_quality=quality,
        risk_flags=[],
    )


def run_discovery(
    run: ResearchRun,
    db: Session,
    wigolo: WigoloClientProtocol,
) -> list[ContentCandidate]:
    """Execute discovery for one run and persist up to five candidates."""
    log = get_logger()
    log.info(f"discovery: run={run.id} keyword='{run.keyword}'")

    variations = build_query_variations(run.keyword, run.research_prompt)
    log.info(f"discovery: {len(variations)} variations -> {variations}")

    all_sources: dict[str, SourceDocumentRaw] = {}
    for q in variations:
        try:
            result = wigolo.search(q, language=run.language, limit=20)
        except Exception as exc:  # pragma: no cover - network path
            log.warning(f"wigolo search failed for '{q}': {exc}")
            continue
        for src in normalize_search_results(result, fetched_at=datetime.now(timezone.utc)):
            if src.canonical_url not in all_sources:
                all_sources[src.canonical_url] = src
        db.add(
            ResearchQuery(
                research_run_id=run.id, query_text=q, result_count=len(result.hits)
            )
        )

    # Persist deduped source documents.
    url_to_doc: dict[str, SourceDocument] = {}
    for raw in all_sources.values():
        doc = SourceDocument(
            research_run_id=run.id,
            canonical_url=raw.canonical_url,
            title=raw.title,
            publisher=raw.publisher,
            published_at=raw.published_at,
            fetched_at=raw.fetched_at,
            excerpt=raw.excerpt,
            content_hash=raw.content_hash,
            source_quality_score=raw.source_quality_score,
        )
        db.add(doc)
        url_to_doc[raw.canonical_url] = doc
    db.flush()

    # Group sources by publisher (story grouping proxy).
    groups: dict[str, list[SourceDocument]] = defaultdict(list)
    for doc in url_to_doc.values():
        groups[doc.publisher or doc.canonical_url].append(doc)

    scored: list[tuple[float, list[SourceDocument]]] = []
    for docs in groups.values():
        lead = max(docs, key=lambda d: d.source_quality_score or 0.0)
        signals = _candidate_signals(run, lead.title or "Untitled", docs)
        scored.append((signals.final, docs))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:_MAX_CANDIDATES]

    candidates: list[ContentCandidate] = []
    for rank, (final_score, docs) in enumerate(top, start=1):
        lead = max(docs, key=lambda d: d.source_quality_score or 0.0)
        s = _candidate_signals(run, lead.title or "Untitled", docs)
        candidate = ContentCandidate(
            research_run_id=run.id,
            title=lead.title or "Untitled",
            summary=" ".join(d.excerpt for d in docs if d.excerpt)[:600],
            facts_json=[d.excerpt for d in docs if d.excerpt][:5],
            source_links=[
                {
                    "url": d.canonical_url,
                    "title": d.title,
                    "publisher": d.publisher,
                    "published_at": d.published_at.isoformat() if d.published_at else None,
                }
                for d in docs
            ],
            virality_score=s.virality,
            freshness_score=s.freshness,
            source_score=s.source,
            relevance_score=s.relevance,
            risk_score=s.risk,
            final_score=final_score,
            rank=rank,
            risk_flags=[],
            language=run.language,
            status="proposed",
        )
        db.add(candidate)
        db.flush()
        for d in docs:
            db.add(
                CandidateSource(
                    candidate_id=candidate.id,
                    source_document_id=d.id,
                    relevance=d.source_quality_score or 0.0,
                )
            )
        candidates.append(candidate)

    run.status = "completed"
    db.commit()
    log.info(f"discovery: run={run.id} produced {len(candidates)} candidates")
    return candidates

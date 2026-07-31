"""Story grouping: cluster sources that report the same event.

Publisher-based grouping was adequate for mock data but wrong on real results —
one outlet publishes many unrelated stories. These tests pin the title-similarity
behaviour that replaced it.
"""

from __future__ import annotations

from dataclasses import dataclass

from vvf_discovery_worker.grouping import group_by_story, similarity, title_tokens


@dataclass
class _Doc:
    """Stand-in for a SourceDocument (only the fields grouping touches)."""

    title: str | None
    canonical_url: str
    source_quality_score: float | None = 0.5


def _titles(groups: list[list[_Doc]]) -> list[set[str]]:
    return [{d.title or "" for d in g} for g in groups]


# --- tokenisation ----------------------------------------------------------


def test_title_tokens_drops_stopwords_and_short_words():
    tokens = title_tokens("Gempa yang di Bali dan itu")
    assert "gempa" in tokens
    assert "bali" in tokens
    assert "yang" not in tokens  # Indonesian stopword
    assert "di" not in tokens  # too short + stopword


def test_title_tokens_keeps_multi_character_numbers():
    """Years and magnitudes are distinguishing signal; single digits are noise."""
    tokens = title_tokens("Gempa M5.2 tahun 2026")
    assert "2026" in tokens
    assert "m5" in tokens
    # The lone "2" split out of "M5.2" carries no signal and is dropped.
    assert "2" not in tokens


def test_title_tokens_handles_none_and_empty():
    assert title_tokens(None) == frozenset()
    assert title_tokens("") == frozenset()
    assert title_tokens("di dan yang") == frozenset()  # all stopwords


def test_similarity_is_zero_for_empty_sets():
    assert similarity(frozenset(), frozenset({"a"})) == 0.0
    assert similarity(frozenset({"a"}), frozenset()) == 0.0


def test_similarity_is_one_for_identical_sets():
    tokens = frozenset({"gempa", "bali"})
    assert similarity(tokens, tokens) == 1.0


# --- grouping --------------------------------------------------------------


def test_same_story_across_publishers_groups_together():
    docs = [
        _Doc("Gempa M5.2 guncang Bali", "https://a.id/1", 0.9),
        _Doc("Gempa Bali magnitudo 5,2 kedalaman 10 km", "https://b.id/2", 0.8),
    ]
    groups = group_by_story(docs)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_unrelated_stories_stay_separate():
    docs = [
        _Doc("Gempa M5.2 guncang Bali", "https://a.id/1", 0.9),
        _Doc("Promo tiket pesawat murah ke Bali", "https://a.id/2", 0.8),
    ]
    groups = group_by_story(docs)
    assert len(groups) == 2


def test_same_publisher_different_stories_are_not_merged():
    """The regression that publisher-grouping caused on real data."""
    docs = [
        _Doc("Gempa M5.2 guncang Bali", "https://detik.com/1", 0.9),
        _Doc("Timnas menang lawan Vietnam", "https://detik.com/2", 0.85),
        _Doc("Harga cabai naik di pasar Jakarta", "https://detik.com/3", 0.8),
    ]
    groups = group_by_story(docs)
    assert len(groups) == 3


def test_third_article_joins_via_widened_group_vocabulary():
    """A group's tokens union as coverage widens, so partial matches still join."""
    docs = [
        _Doc("Gempa Bali magnitudo 5,2", "https://a.id/1", 0.9),
        _Doc("Gempa Bali tidak berpotensi tsunami", "https://b.id/2", 0.85),
        _Doc("BMKG: tsunami tidak berpotensi usai gempa", "https://c.id/3", 0.8),
    ]
    groups = group_by_story(docs)
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_untitled_documents_each_form_their_own_group():
    """Empty token sets must never collapse into one bucket."""
    docs = [
        _Doc(None, "https://a.id/1", 0.9),
        _Doc("", "https://b.id/2", 0.8),
    ]
    groups = group_by_story(docs)
    assert len(groups) == 2


def test_groups_are_ordered_by_quality_and_deterministic():
    docs = [
        _Doc("Berita kecil tentang pasar", "https://c.id/3", 0.2),
        _Doc("Gempa besar mengguncang Bali", "https://a.id/1", 0.95),
        _Doc("Cuaca cerah di Jakarta", "https://b.id/2", 0.5),
    ]
    first = group_by_story(docs)
    second = group_by_story(list(reversed(docs)))
    # Highest-quality story leads, and input order does not change the outcome.
    assert first[0][0].source_quality_score == 0.95
    assert _titles(first) == _titles(second)


def test_empty_input_yields_no_groups():
    assert group_by_story([]) == []


def test_missing_quality_scores_do_not_crash():
    docs = [
        _Doc("Gempa Bali", "https://a.id/1", None),
        _Doc("Banjir Jakarta", "https://b.id/2", None),
    ]
    assert len(group_by_story(docs)) == 2

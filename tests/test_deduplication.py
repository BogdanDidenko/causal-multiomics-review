from causal_multiomics_review.deduplication import (
    deduplicate,
    normalize_arxiv,
    normalize_doi,
    normalize_title,
)


def test_identifier_normalization() -> None:
    assert normalize_doi("https://doi.org/10.1000/ABC.1 ") == "10.1000/abc.1"
    assert normalize_arxiv("arXiv:2401.01234v2") == "2401.01234"
    assert normalize_title("Multi-omics: A causal study") == "multi omics a causal study"


def test_deduplicate_prefers_longest_abstract_and_keeps_sources() -> None:
    records = [
        {
            "record_id": "a",
            "doi": "10.1000/example",
            "title": "A study",
            "abstract": "short",
            "year": "2024",
            "source": "PubMed",
        },
        {
            "record_id": "b",
            "doi": "https://doi.org/10.1000/EXAMPLE",
            "title": "A study",
            "abstract": "a substantially longer abstract",
            "year": "2024",
            "source": "Scopus",
        },
    ]
    canonical, log = deduplicate(records)
    assert len(canonical) == 1
    assert canonical[0]["record_id"] == "b"
    assert canonical[0]["provenance_sources"] == "PubMed;Scopus"
    assert canonical[0]["duplicate_count"] == 1
    assert log[0]["match_reason"] == "doi"


def test_exact_title_year_deduplicates_without_identifiers() -> None:
    records = [
        {"title": "A causal multi-omics study", "year": "2023", "source": "A"},
        {"title": "A causal multi omics study!", "year": "2023", "source": "B"},
    ]
    canonical, log = deduplicate(records)
    assert len(canonical) == 1
    assert log[0]["match_reason"] == "title_year"

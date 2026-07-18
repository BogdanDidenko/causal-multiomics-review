from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
ARXIV = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_doi(value: str | None) -> str:
    return DOI_PREFIX.sub("", (value or "").strip()).lower().rstrip(" .")


def normalize_title(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return NON_ALNUM.sub(" ", text.lower()).strip()


def normalize_arxiv(value: str | None) -> str:
    match = ARXIV.search(value or "")
    return match.group(1).lower() if match else ""


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _keys(record: dict[str, Any]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for kind, value in (
        ("doi", normalize_doi(str(record.get("doi", "")))),
        ("pmid", str(record.get("pmid", "")).strip()),
        ("arxiv", normalize_arxiv(str(record.get("arxiv_id", "")))),
    ):
        if value:
            keys.append((kind, value))
    title = normalize_title(str(record.get("title", "")))
    year = str(record.get("year", "")).strip()
    if title and year:
        keys.append(("title_year", f"{title}|{year}"))
    return keys


def _representative_score(record: dict[str, Any]) -> tuple[int, int, int]:
    return (
        bool(normalize_doi(str(record.get("doi", "")))),
        len(str(record.get("abstract", ""))),
        len(str(record.get("title", ""))),
    )


def deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    union = _UnionFind(len(records))
    seen: dict[tuple[str, str], int] = {}
    reasons: dict[tuple[int, int], str] = {}

    for index, record in enumerate(records):
        for kind, value in _keys(record):
            if (kind, value) in seen:
                other = seen[(kind, value)]
                union.union(other, index)
                reasons.setdefault((min(other, index), max(other, index)), kind)
            else:
                seen[(kind, value)] = index

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        groups[union.find(index)].append(index)

    canonical: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []
    for group_number, indices in enumerate(groups.values(), start=1):
        representative_index = max(indices, key=lambda item: _representative_score(records[item]))
        representative = dict(records[representative_index])
        sources = sorted(
            {
                str(records[item].get("source", ""))
                for item in indices
                if records[item].get("source")
            }
        )
        representative["provenance_sources"] = ";".join(sources)
        representative["duplicate_count"] = len(indices) - 1
        canonical.append(representative)

        for index in indices:
            if index == representative_index:
                continue
            reason = next(
                (
                    kind
                    for pair, kind in reasons.items()
                    if index in pair and representative_index in pair
                ),
                "transitive_exact_match",
            )
            log.append(
                {
                    "group_id": group_number,
                    "representative_index": representative_index,
                    "duplicate_index": index,
                    "match_reason": reason,
                    "representative_title": representative.get("title", ""),
                    "duplicate_title": records[index].get("title", ""),
                }
            )
    return canonical, log

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import certifi

from causal_multiomics_review.audit import sha256_file, write_manifest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "protocol" / "search_config.json"


def request_json(
    base_url: str,
    params: dict[str, str | int],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    url = base_url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(
            request,
            timeout=180,
            context=ssl.create_default_context(cafile=certifi.where()),
        ) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {base_url}: {body[:500]}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {base_url}")
    return payload


def probe(name: str, query: str, api_key: str | None) -> tuple[int, dict[str, Any]]:
    if name == "pubmed":
        payload = request_json(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": 0,
                "api_key": api_key or "",
            },
        )
        return int(payload["esearchresult"]["count"]), payload
    if name == "europepmc":
        payload = request_json(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            {"query": query, "format": "json", "pageSize": 1},
        )
        return int(payload["hitCount"]), payload
    if name == "scopus":
        payload = request_json(
            "https://api.elsevier.com/content/search/scopus",
            {"query": query, "count": 1, "view": "STANDARD"},
            {"X-ELS-APIKey": api_key or "", "Accept": "application/json"},
        )
        return int(payload["search-results"]["opensearch:totalResults"]), payload
    if name == "semantic_scholar":
        payload = request_json(
            "https://api.semanticscholar.org/graph/v1/paper/search/bulk",
            {"query": query, "year": "2018-2026", "limit": 1, "fields": "title"},
            {"x-api-key": api_key or ""},
        )
        return int(payload["total"]), payload
    if name == "springernature":
        payload = request_json(
            "https://api.springernature.com/meta/v2/json",
            {"q": query, "p": 1, "api_key": api_key or ""},
        )
        return int(payload["result"][0]["total"]), payload
    if name == "openalex":
        payload = request_json(
            "https://api.openalex.org/works",
            {"filter": query, "per-page": 1, "api_key": api_key or ""},
        )
        return int(payload["meta"]["count"]), payload
    raise ValueError(f"Unsupported automated source: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe calibrated database query counts")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--database", action="append", dest="databases")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    selected = set(args.databases or config["databases"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    results: list[dict[str, Any]] = []

    for name, database in config["databases"].items():
        if name not in selected:
            continue
        query_path = ROOT / "protocol" / database["query_file"]
        query = query_path.read_text(encoding="utf-8").strip()
        if name == "google_scholar":
            results.append(
                {"database": name, "status": "manual_required", "count": None}
            )
            continue
        env_name = database["api_key_env"]
        api_key = os.environ.get(env_name) if env_name else None
        if env_name and not api_key:
            results.append(
                {
                    "database": name,
                    "status": "missing_api_key",
                    "api_key_env": env_name,
                    "count": None,
                }
            )
            continue
        try:
            count, payload = probe(name, query, api_key)
            (raw_dir / f"{name}.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            results.append({"database": name, "status": "ok", "count": count})
        except Exception as error:  # Continue so one source cannot erase the audit run.
            results.append(
                {"database": name, "status": "error", "count": None, "error": str(error)}
            )

    write_manifest(
        args.output_dir / "manifest.json",
        {
            "probe_time": datetime.now(timezone.utc).isoformat(),
            "search_config_sha256": sha256_file(CONFIG_PATH),
            "query_sha256": {
                name: sha256_file(ROOT / "protocol" / database["query_file"])
                for name, database in config["databases"].items()
                if name in selected
            },
            "results": results,
        },
    )
    for result in results:
        print(
            f"{result['database']}\t{result['status']}\t"
            f"{result.get('count') if result.get('count') is not None else ''}"
        )


if __name__ == "__main__":
    main()

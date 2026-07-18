from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    with Path(path).open("rb") as handle:
        return sha256_bytes(handle.read())


def git_revision(repo: str | Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def write_manifest(path: str | Path, payload: dict[str, Any]) -> None:
    document = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

"""Dataset validation and honest count reporting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _find_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if isinstance(value.get("id"), str):
            found.append(value["id"])
        for item in value.values():
            found.extend(_find_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_ids(item))
    return found


def validate_dataset(data_dir: Path) -> dict[str, Any]:
    data_dir = Path(data_dir)
    errors: list[str] = []
    warnings: list[str] = []
    files: list[dict[str, Any]] = []
    json_counts: dict[str, int] = {}
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file() or path.name.endswith(".bak") or path.name == "scrape_log.txt":
            continue
        relative = path.relative_to(data_dir).as_posix()
        content = path.read_bytes()
        files.append(
            {"path": relative, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        )
        if path.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: invalid JSON ({exc})")
            continue
        ids = _find_ids(payload)
        duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
        if duplicate_ids:
            errors.append(f"{relative}: duplicate ids {duplicate_ids[:5]}")
        for key in (
            "faq_entries",
            "drug_interactions",
            "test_entries",
            "synonym_groups",
            "lab_reference_values",
        ):
            if isinstance(payload.get(key), list):
                actual = len(payload[key])
                json_counts[f"{relative}:{key}"] = actual
                declared = payload.get("metadata", {}).get("total_count") or payload.get(
                    "metadata", {}
                ).get("total_groups")
                if declared is not None and int(declared) != actual:
                    warnings.append(f"{relative}:{key}: metadata={declared}, actual={actual}")
    return {
        "data_dir": str(data_dir),
        "file_count": len(files),
        "files": files,
        "json_counts": json_counts,
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
    }

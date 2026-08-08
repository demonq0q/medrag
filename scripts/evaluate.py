#!/usr/bin/env python3
"""Run a lightweight, reproducible evaluation against the bundled test set.

The default mode deliberately evaluates the deterministic template fallback. It
therefore remains useful in CI and on a fresh deployment without an LLM key.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from medrag.config import get_settings
from medrag.ingestion import KnowledgeBuilder
from medrag.normalization import MedicalTermNormalizer
from medrag.pipeline import MedicalRAGPipeline
from medrag.retrieval import HybridRetriever
from medrag.storage import SQLiteStore


def _load_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("test_entries", []))


def _source_hit(response: Any, expected: list[str]) -> bool:
    if not expected:
        return False
    expected_text = [str(value).lower() for value in expected]
    for citation in response.citations:
        haystack = f"{citation.source_id} {citation.source}".lower()
        if any(value in haystack or haystack in value for value in expected_text):
            return True
    return False


def _entity_hit(response: Any, entities: list[str]) -> bool:
    text = f"{response.answer} {response.normalized_query}".lower()
    return not entities or any(entity.lower() in text for entity in entities)


def _percent(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def run(limit: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    settings.ensure_directories()
    store = SQLiteStore(settings.db_path)
    if store.metrics()["chunks"] == 0:
        KnowledgeBuilder(settings.data_dir, store).build()
    pipeline = MedicalRAGPipeline(HybridRetriever(store, MedicalTermNormalizer(settings.data_dir)))
    entries = _load_entries(settings.data_dir / "evaluation" / "test_set.json")
    if limit:
        entries = entries[:limit]

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for entry in entries:
        started = time.perf_counter()
        response = pipeline.invoke(entry["question"])
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        latencies.append(latency_ms)
        rows.append(
            {
                "id": entry.get("id"),
                "category": entry.get("category"),
                "latency_ms": latency_ms,
                "has_answer": bool(response.answer.strip()),
                "has_citation": bool(response.citations),
                "source_hit": _source_hit(response, entry.get("ground_truth_docs", [])),
                "entity_hit": _entity_hit(response, entry.get("key_entities", [])),
                "risk_level": response.risk_level,
                "safety_status": response.safety_status,
                "citation_ids": [citation.citation_id for citation in response.citations],
            }
        )

    total = len(rows)
    ordered_latencies = sorted(latencies)
    summary = {
        "dataset": str(settings.data_dir / "evaluation" / "test_set.json"),
        "mode": settings.llm_provider,
        "total": total,
        "answer_rate": _percent(sum(row["has_answer"] for row in rows), total),
        "citation_coverage": _percent(sum(row["has_citation"] for row in rows), total),
        "source_hit_rate": _percent(sum(row["source_hit"] for row in rows), total),
        "entity_hit_rate": _percent(sum(row["entity_hit"] for row in rows), total),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "p50": ordered_latencies[(len(ordered_latencies) - 1) // 2] if latencies else 0.0,
            "p95": ordered_latencies[max(0, int(len(ordered_latencies) * 0.95) - 1)]
            if latencies
            else 0.0,
        },
        "knowledge_metrics": store.metrics(),
    }
    return {"summary": summary, "cases": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="only evaluate the first N cases")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/evaluation.json"),
        help="JSON report path",
    )
    args = parser.parse_args()
    report = run(args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

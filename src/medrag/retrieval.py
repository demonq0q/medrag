"""Hybrid medical retrieval: lexical, FAQ, graph and structured evidence routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ChunkRecord, RetrievalResult
from .normalization import MedicalTermNormalizer
from .storage import SQLiteStore


@dataclass(slots=True)
class RetrievalBundle:
    original_query: str
    normalized_query: str
    entities: dict[str, list[str]]
    results: list[RetrievalResult]
    interactions: list[dict[str, Any]] = field(default_factory=list)
    labs: list[dict[str, Any]] = field(default_factory=list)
    graph_relations: list[dict[str, Any]] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """Fuse four evidence paths while keeping route-level traceability."""

    ROUTE_WEIGHTS = {
        "bm25": 1.0,
        "faq": 1.25,
        "graph": 1.15,
        "interaction": 1.45,
        "lab": 1.30,
    }

    def __init__(self, store: SQLiteStore, normalizer: MedicalTermNormalizer):
        self.store = store
        self.normalizer = normalizer

    def retrieve(self, question: str, top_k: int = 6) -> RetrievalBundle:
        normalized = self.normalizer.normalize_text(question)
        entities = self.normalizer.extract_entities(question)
        terms = self.normalizer.tokenize(normalized)
        for values in entities.values():
            for value in values:
                if value not in terms:
                    terms.append(value)

        candidates: dict[str, RetrievalResult] = {}

        def add_candidate(chunk: ChunkRecord, score: float, route: str) -> None:
            if chunk.is_parent:
                return
            existing = candidates.get(chunk.chunk_id)
            if existing is None:
                candidates[chunk.chunk_id] = RetrievalResult(chunk=chunk, score=0.0, routes=[])
                existing = candidates[chunk.chunk_id]
            if route not in existing.routes:
                existing.routes.append(route)
            existing.score += score

        lexical = self.store.search_lexical(terms, limit=max(20, top_k * 4))
        for rank, (chunk, score) in enumerate(lexical, start=1):
            add_candidate(chunk, self._rrf("bm25", rank) + score * 0.05, "bm25")

        faq = self.store.search_lexical(terms, limit=max(8, top_k * 2), doc_type="FAQ")
        for rank, (chunk, score) in enumerate(faq, start=1):
            add_candidate(chunk, self._rrf("faq", rank) + score * 0.08, "faq")

        drug_names = entities.get("drugs", [])
        interactions = self.store.find_interactions(drug_names)
        for rank, item in enumerate(interactions, start=1):
            chunk = self.store.get_chunk(item["chunk_id"])
            if chunk:
                add_candidate(chunk, self._rrf("interaction", rank), "interaction")

        all_entities = [item for values in entities.values() for item in values]
        graph_relations = self.store.graph_context(all_entities, limit=top_k * 3)
        for rank, relation in enumerate(graph_relations, start=1):
            chunk_id = relation.get("chunk_id")
            chunk = self.store.get_chunk(chunk_id) if chunk_id else None
            if chunk:
                add_candidate(chunk, self._rrf("graph", rank), "graph")

        lab_terms = entities.get("examinations", []) or terms
        labs = self.store.lab_matches(lab_terms)
        for rank, item in enumerate(labs, start=1):
            chunk = self.store.get_chunk(item["chunk_id"])
            if chunk:
                add_candidate(chunk, self._rrf("lab", rank), "lab")

        ranked = sorted(
            candidates.values(),
            key=lambda result: result.score + result.chunk.credibility_score * 0.12,
            reverse=True,
        )
        ranked = self._deduplicate_sources(ranked)[:top_k]
        if interactions:
            interaction_ids = {item["chunk_id"] for item in interactions}
            ranked.sort(
                key=lambda result: (
                    0 if result.chunk.chunk_id in interaction_ids else 1,
                    -result.score,
                )
            )
        elif labs:
            lab_ids = {item["chunk_id"] for item in labs}
            ranked.sort(
                key=lambda result: (
                    0 if result.chunk.chunk_id in lab_ids else 1,
                    -result.score,
                )
            )
        trace = {
            "terms": terms[:32],
            "routes": {
                "bm25": len(lexical),
                "faq": len(faq),
                "interaction": len(interactions),
                "graph": len(graph_relations),
                "lab": len(labs),
            },
            "candidate_count": len(candidates),
            "returned_count": len(ranked),
        }
        return RetrievalBundle(
            original_query=question,
            normalized_query=normalized,
            entities=entities,
            results=ranked,
            interactions=interactions,
            labs=labs,
            graph_relations=graph_relations,
            trace=trace,
        )

    def _rrf(self, route: str, rank: int) -> float:
        return self.ROUTE_WEIGHTS[route] / (60.0 + rank)

    @staticmethod
    def _deduplicate_sources(results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Keep the strongest child from one source while preserving route evidence."""
        source_best: dict[str, RetrievalResult] = {}
        for result in results:
            key = result.chunk.source_id
            current = source_best.get(key)
            if current is None:
                source_best[key] = result
                continue
            current.routes = list(dict.fromkeys(current.routes + result.routes))
            current.score = max(current.score, result.score)
        return sorted(source_best.values(), key=lambda item: item.score, reverse=True)

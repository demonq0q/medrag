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

    DEFAULT_RELEVANCE_THRESHOLD = 0.40
    RELEVANCE_STOPWORDS = frozenset(
        {
            "怎么办",
            "怎么",
            "如何",
            "能否",
            "是否",
            "可以",
            "可否",
            "什么",
            "多少",
            "哪些",
            "哪个",
            "怎样",
            "应该",
            "需要",
            "问题",
            "治疗",
            "使用",
            "服用",
            "同时",
            "一起",
            "吃",
            "用药",
            "吗",
            "的",
            "和",
            "有",
            "请",
            "我",
            "想",
            "了解",
            "一下",
            "是什么",
            "是多少",
            "合并",
            "评估",
            "药物",
            "疾病",
            "症状",
            "资料",
        }
    )

    ROUTE_WEIGHTS = {
        "bm25": 1.0,
        "faq": 1.25,
        "graph": 1.15,
        "interaction": 1.45,
        "lab": 1.30,
    }

    def __init__(
        self,
        store: SQLiteStore,
        normalizer: MedicalTermNormalizer,
        relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    ):
        self.store = store
        self.normalizer = normalizer
        self.relevance_threshold = max(0.0, min(1.0, relevance_threshold))

    def retrieve(self, question: str, top_k: int = 6) -> RetrievalBundle:
        normalized = self.normalizer.normalize_text(question)
        entities = self.normalizer.extract_entities(question)
        terms = self.normalizer.tokenize(normalized)
        for term in self.normalizer.tokenize(question):
            if term not in terms:
                terms.append(term)
        for values in entities.values():
            for value in values:
                if value not in terms:
                    terms.append(value)
        relevance_terms = self._relevance_terms(terms)

        candidates: dict[str, RetrievalResult] = {}

        def add_candidate(
            chunk: ChunkRecord,
            score: float,
            route: str,
            relevance: float | None = None,
        ) -> None:
            if chunk.is_parent:
                return
            existing = candidates.get(chunk.chunk_id)
            if existing is None:
                candidates[chunk.chunk_id] = RetrievalResult(chunk=chunk, score=0.0, routes=[])
                existing = candidates[chunk.chunk_id]
            if route not in existing.routes:
                existing.routes.append(route)
            existing.score += score
            if relevance is not None:
                existing.relevance = max(existing.relevance, relevance)

        lexical = self.store.search_lexical(terms, limit=max(20, top_k * 4))
        for rank, (chunk, score) in enumerate(lexical, start=1):
            add_candidate(
                chunk,
                self._rrf("bm25", rank) + score * 0.05,
                "bm25",
                self._relevance_score(chunk, relevance_terms),
            )

        faq = self.store.search_lexical(terms, limit=max(8, top_k * 2), doc_type="FAQ")
        for rank, (chunk, score) in enumerate(faq, start=1):
            add_candidate(
                chunk,
                self._rrf("faq", rank) + score * 0.08,
                "faq",
                self._relevance_score(chunk, relevance_terms),
            )

        drug_names = entities.get("drugs", [])
        interactions = self.store.find_interactions(drug_names)
        for rank, item in enumerate(interactions, start=1):
            chunk = self.store.get_chunk(item["chunk_id"])
            if chunk:
                add_candidate(chunk, self._rrf("interaction", rank), "interaction", 1.0)

        all_entities = [item for values in entities.values() for item in values]
        graph_relations = self.store.graph_context(all_entities, limit=top_k * 3)
        for rank, relation in enumerate(graph_relations, start=1):
            chunk_id = relation.get("chunk_id")
            chunk = self.store.get_chunk(chunk_id) if chunk_id else None
            if chunk:
                add_candidate(
                    chunk,
                    self._rrf("graph", rank),
                    "graph",
                    self._relevance_score(chunk, relevance_terms),
                )

        lab_terms = entities.get("examinations", []) or terms
        labs = self.store.lab_matches(lab_terms)
        for rank, item in enumerate(labs, start=1):
            chunk = self.store.get_chunk(item["chunk_id"])
            if chunk:
                add_candidate(chunk, self._rrf("lab", rank), "lab", 1.0)

        filtered = [
            result
            for result in candidates.values()
            if result.relevance >= self.relevance_threshold
            and self._passes_entity_gate(result, drug_names, interactions)
        ]

        ranked = sorted(
            filtered,
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
            "filtered_candidate_count": len(filtered),
            "relevance_threshold": self.relevance_threshold,
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

    def _relevance_terms(self, terms: list[str]) -> list[str]:
        return list(
            dict.fromkeys(
                term
                for term in terms
                if len(term.strip()) > 1 and term not in self.RELEVANCE_STOPWORDS
            )
        )

    @staticmethod
    def _relevance_score(chunk: ChunkRecord, terms: list[str]) -> float:
        if not terms:
            return 0.0
        title_text = " ".join(
            value
            for value in (chunk.title, chunk.source, chunk.drug_name, chunk.disease_name)
            if value
        ).lower()
        content_text = chunk.content.lower()
        weighted_matches = 0.0
        for term in terms:
            normalized_term = term.lower()
            if normalized_term in title_text:
                weighted_matches += 1.0
            elif normalized_term in content_text:
                # A body mention is useful, but weaker than a title or metadata match.
                weighted_matches += 0.35
        return round(min(1.0, weighted_matches / len(terms)), 4)

    @staticmethod
    def _passes_entity_gate(
        result: RetrievalResult,
        drug_names: list[str],
        interactions: list[dict[str, Any]],
    ) -> bool:
        """Avoid citing a chunk that mentions only one drug in a pair question."""
        if len(drug_names) < 2 or not interactions or "interaction" in result.routes:
            return True
        haystack = f"{result.chunk.title} {result.chunk.content}".lower()
        return all(drug.lower() in haystack for drug in drug_names)

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
            current.relevance = max(current.relevance, result.relevance)
        return sorted(source_best.values(), key=lambda item: item.score, reverse=True)

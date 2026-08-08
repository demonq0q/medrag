"""SQLite persistence, FTS5 search and structured medical data access."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import ChunkRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    medical_field TEXT NOT NULL DEFAULT '',
    evidence_level TEXT NOT NULL DEFAULT '',
    drug_name TEXT NOT NULL DEFAULT '',
    disease_name TEXT NOT NULL DEFAULT '',
    page_number INTEGER,
    section TEXT NOT NULL DEFAULT '',
    publish_date TEXT NOT NULL DEFAULT '',
    credibility_score REAL NOT NULL DEFAULT 0.5,
    parent_chunk_id TEXT,
    is_parent INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_type ON chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    content,
    title,
    source,
    tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id TEXT PRIMARY KEY,
    drug_a TEXT NOT NULL,
    drug_b TEXT NOT NULL,
    interaction_level TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    clinical_effect TEXT NOT NULL,
    clinical_advice TEXT NOT NULL,
    monitoring TEXT NOT NULL,
    source TEXT NOT NULL,
    chunk_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_pair ON interactions(drug_a, drug_b);
CREATE TABLE IF NOT EXISTS graph_entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    attributes_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_graph_entities_name ON graph_entities(normalized_name);
CREATE TABLE IF NOT EXISTS graph_relations (
    relation_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    target_name TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_graph_relations_source ON graph_relations(source_name);
CREATE INDEX IF NOT EXISTS idx_graph_relations_target ON graph_relations(target_name);
CREATE TABLE IF NOT EXISTS lab_values (
    lab_id TEXT PRIMARY KEY,
    item TEXT NOT NULL,
    abbreviation TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    normal_range TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    critical_high TEXT,
    critical_low TEXT,
    sample_type TEXT NOT NULL DEFAULT '',
    clinical_significance TEXT NOT NULL DEFAULT '',
    affecting_factors_json TEXT NOT NULL DEFAULT '[]',
    chunk_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lab_item ON lab_values(item);
CREATE TABLE IF NOT EXISTS manifest (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    response_json TEXT,
    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, message_id);
"""


class SQLiteStore:
    """A small per-operation SQLite repository safe for FastAPI worker threads."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def reset_knowledge(self) -> None:
        with self.connect() as connection:
            for table in (
                "chunks",
                "interactions",
                "graph_entities",
                "graph_relations",
                "lab_values",
                "manifest",
            ):
                connection.execute(f"DELETE FROM {table}")
            connection.execute("DELETE FROM chunks_fts")

    def insert_chunks(self, chunks: Iterable[ChunkRecord]) -> int:
        records = list(chunks)
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO chunks
                (chunk_id, source_id, source, title, content, doc_type, medical_field,
                 evidence_level, drug_name, disease_name, page_number, section,
                 publish_date, credibility_score, parent_chunk_id, is_parent, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.source_id,
                        chunk.source,
                        chunk.title,
                        chunk.content,
                        chunk.doc_type,
                        chunk.medical_field,
                        chunk.evidence_level,
                        chunk.drug_name,
                        chunk.disease_name,
                        chunk.page_number,
                        chunk.section,
                        chunk.publish_date,
                        chunk.credibility_score,
                        chunk.parent_chunk_id,
                        int(chunk.is_parent),
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk in records
                ],
            )
            connection.executemany(
                """
                INSERT OR REPLACE INTO chunks_fts(chunk_id, content, title, source)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (chunk.chunk_id, chunk.content, chunk.title, chunk.source)
                    for chunk in records
                    if not chunk.is_parent
                ],
            )
        return len(records)

    def replace_interactions(self, items: Iterable[dict[str, Any]]) -> int:
        records = list(items)
        with self.connect() as connection:
            connection.execute("DELETE FROM interactions")
            connection.executemany(
                """
                INSERT INTO interactions
                (interaction_id, drug_a, drug_b, interaction_level, mechanism, clinical_effect,
                 clinical_advice, monitoring, source, chunk_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item["drug_a"],
                        item["drug_b"],
                        item.get("interaction_level", "未知"),
                        item.get("mechanism", ""),
                        item.get("clinical_effect", ""),
                        item.get("clinical_advice", ""),
                        item.get("monitoring", ""),
                        item.get("source", ""),
                        item["chunk_id"],
                    )
                    for item in records
                ],
            )
        return len(records)

    def replace_graph(
        self, entities: Iterable[dict[str, Any]], relations: Iterable[dict[str, Any]]
    ) -> tuple[int, int]:
        entity_records = list(entities)
        relation_records = list(relations)
        with self.connect() as connection:
            connection.execute("DELETE FROM graph_entities")
            connection.execute("DELETE FROM graph_relations")
            connection.executemany(
                """
                INSERT INTO graph_entities
                (entity_id, entity_type, name, normalized_name, attributes_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item["type"],
                        item["name"],
                        item.get("normalized_name", item["name"]),
                        json.dumps(item.get("attributes", {}), ensure_ascii=False),
                    )
                    for item in entity_records
                ],
            )
            connection.executemany(
                """
                INSERT INTO graph_relations
                (relation_id, source_name, target_name, relation_type, evidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item["source"],
                        item["target"],
                        item["type"],
                        item.get("evidence", ""),
                    )
                    for item in relation_records
                ],
            )
        return len(entity_records), len(relation_records)

    def replace_labs(self, items: Iterable[dict[str, Any]]) -> int:
        records = list(items)
        with self.connect() as connection:
            connection.execute("DELETE FROM lab_values")
            connection.executemany(
                """
                INSERT INTO lab_values
                (lab_id, item, abbreviation, category, normal_range, unit, critical_high,
                 critical_low, sample_type, clinical_significance, affecting_factors_json, chunk_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item.get("item", ""),
                        item.get("abbreviation", ""),
                        item.get("category", ""),
                        item.get("normal_range", ""),
                        item.get("unit", ""),
                        item.get("critical_high"),
                        item.get("critical_low"),
                        item.get("sample_type", ""),
                        item.get("clinical_significance", ""),
                        json.dumps(item.get("affecting_factors", []), ensure_ascii=False),
                        item["chunk_id"],
                    )
                    for item in records
                ],
            )
        return len(records)

    def set_manifest(self, values: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.executemany(
                "INSERT OR REPLACE INTO manifest(key, value_json) VALUES (?, ?)",
                [(key, json.dumps(value, ensure_ascii=False)) for key, value in values.items()],
            )

    def get_manifest(self) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute("SELECT key, value_json FROM manifest").fetchall()
        return {row["key"]: json.loads(row["value_json"]) for row in rows}

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> ChunkRecord:
        return ChunkRecord(
            chunk_id=row["chunk_id"],
            source_id=row["source_id"],
            source=row["source"],
            title=row["title"],
            content=row["content"],
            doc_type=row["doc_type"],
            medical_field=row["medical_field"],
            evidence_level=row["evidence_level"],
            drug_name=row["drug_name"],
            disease_name=row["disease_name"],
            page_number=row["page_number"],
            section=row["section"],
            publish_date=row["publish_date"],
            credibility_score=row["credibility_score"],
            parent_chunk_id=row["parent_chunk_id"],
            is_parent=bool(row["is_parent"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def get_chunk(self, chunk_id: str) -> ChunkRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
        return self._row_to_chunk(row) if row else None

    def search_lexical(
        self, terms: list[str], limit: int = 20, doc_type: str | None = None
    ) -> list[tuple[ChunkRecord, float]]:
        terms = [term.replace('"', " ").strip() for term in terms if term.strip()]
        if not terms:
            return []
        fts_query = " OR ".join(f'"{term}"' for term in terms)
        type_clause = " AND c.doc_type = ?" if doc_type else ""
        params: list[Any] = [fts_query]
        if doc_type:
            params.append(doc_type)
        params.append(limit)
        try:
            with self.connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT c.*, bm25(chunks_fts) AS rank_score
                    FROM chunks_fts
                    JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
                    WHERE chunks_fts MATCH ? AND c.is_parent = 0 {type_clause}
                    ORDER BY rank_score ASC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
            if rows:
                return [
                    (self._row_to_chunk(row), 1.0 / (1.0 + abs(float(row["rank_score"]))))
                    for row in rows
                ]
        except sqlite3.OperationalError:
            pass

        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM chunks WHERE is_parent = 0 {type_clause}",
                params[1:-1] if doc_type else [],
            ).fetchall()
        scored: list[tuple[ChunkRecord, float]] = []
        for row in rows:
            chunk = self._row_to_chunk(row)
            haystack = f"{chunk.title} {chunk.source} {chunk.content}".lower()
            score = sum(haystack.count(term.lower()) for term in terms)
            if score:
                scored.append((chunk, float(score)))
        return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]

    def find_interactions(self, drugs: list[str]) -> list[dict[str, Any]]:
        if not drugs:
            return []
        clauses: list[str] = []
        params: list[str] = []
        if len(drugs) >= 2:
            for index, first in enumerate(drugs):
                for second in drugs[index + 1 :]:
                    clauses.append("(drug_a = ? AND drug_b = ?) OR (drug_a = ? AND drug_b = ?)")
                    params.extend([first, second, first, second])
        else:
            clauses.append("drug_a = ? OR drug_b = ?")
            params.extend([drugs[0], drugs[0]])
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM interactions WHERE {' OR '.join(clauses)}", params
            ).fetchall()
        return [dict(row) for row in rows]

    def graph_context(self, entities: list[str], limit: int = 20) -> list[dict[str, Any]]:
        if not entities:
            return []
        placeholders = ",".join("?" for _ in entities)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM graph_relations
                WHERE source_name IN ({placeholders}) OR target_name IN ({placeholders})
                LIMIT ?
                """,
                [*entities, *entities, limit],
            ).fetchall()
        return [dict(row) for row in rows]

    def lab_matches(self, terms: list[str]) -> list[dict[str, Any]]:
        if not terms:
            return []
        clauses = " OR ".join("item LIKE ? OR abbreviation LIKE ?" for _ in terms)
        params = [value for term in terms for value in (f"%{term}%", f"%{term}%")]
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM lab_values WHERE {clauses}", params
            ).fetchall()
        return [dict(row) for row in rows]

    def metrics(self) -> dict[str, Any]:
        with self.connect() as connection:
            counts = {
                "documents": connection.execute(
                    "SELECT COUNT(DISTINCT source_id) FROM chunks"
                ).fetchone()[0],
                "chunks": connection.execute(
                    "SELECT COUNT(*) FROM chunks WHERE is_parent = 0"
                ).fetchone()[0],
                "faq_count": connection.execute(
                    "SELECT COUNT(*) FROM chunks WHERE doc_type = 'FAQ'"
                ).fetchone()[0],
                "interactions": connection.execute("SELECT COUNT(*) FROM interactions").fetchone()[
                    0
                ],
                "graph_entities": connection.execute(
                    "SELECT COUNT(*) FROM graph_entities"
                ).fetchone()[0],
                "graph_relations": connection.execute(
                    "SELECT COUNT(*) FROM graph_relations"
                ).fetchone()[0],
                "labs": connection.execute("SELECT COUNT(*) FROM lab_values").fetchone()[0],
            }
            departments = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT DISTINCT medical_field FROM chunks
                    WHERE medical_field != '' ORDER BY medical_field
                    """
                ).fetchall()
            ]
        return {**counts, "departments": departments}

    def upsert_conversation(self, conversation_id: str, title: str, timestamp: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations(conversation_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    title=excluded.title, updated_at=excluded.updated_at
                """,
                (conversation_id, title, timestamp, timestamp),
            )

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        timestamp: str,
        response_json: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(conversation_id, role, content, created_at, response_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, timestamp, response_json),
            )

    def list_conversations(self, limit: int = 30) -> list[dict[str, str]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT conversation_id, title, updated_at FROM conversations
                ORDER BY updated_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def conversation_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at, response_json FROM messages
                WHERE conversation_id = ? ORDER BY message_id
                """,
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

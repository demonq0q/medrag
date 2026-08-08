"""Shared domain and API models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field


@dataclass(slots=True)
class ChunkRecord:
    chunk_id: str
    source_id: str
    source: str
    title: str
    content: str
    doc_type: str
    medical_field: str = ""
    evidence_level: str = ""
    drug_name: str = ""
    disease_name: str = ""
    page_number: int | None = None
    section: str = ""
    publish_date: str = ""
    credibility_score: float = 0.5
    parent_chunk_id: str | None = None
    is_parent: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Document:
        metadata = {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source": self.source,
            "title": self.title,
            "doc_type": self.doc_type,
            "medical_field": self.medical_field,
            "evidence_level": self.evidence_level,
            "drug_name": self.drug_name,
            "disease_name": self.disease_name,
            "page_number": self.page_number,
            "section": self.section,
            "publish_date": self.publish_date,
            "credibility_score": self.credibility_score,
            "parent_chunk_id": self.parent_chunk_id,
            **self.metadata,
        }
        return Document(page_content=self.content, metadata=metadata)


@dataclass(slots=True)
class RetrievalResult:
    chunk: ChunkRecord
    score: float
    routes: list[str] = field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = None
    top_k: int = Field(default=6, ge=1, le=12)


class Citation(BaseModel):
    citation_id: str
    source_id: str
    source: str
    page_number: int | None = None
    section: str = ""
    evidence_level: str = ""
    doc_type: str
    credibility_score: float = 0.0
    snippet: str = ""


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    risk_level: str = "low"
    safety_status: str = "reviewed"
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    follow_up: list[str] = Field(default_factory=list)
    normalized_query: str = ""
    entities: dict[str, list[str]] = Field(default_factory=dict)
    retrieval_trace: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    chunks: int


class PreviewResponse(BaseModel):
    filename: str
    doc_type: str
    page_count: int | None = None
    extracted_text: str
    sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InteractionResponse(BaseModel):
    found: bool
    drug_a: str
    drug_b: str
    interaction_level: str | None = None
    mechanism: str | None = None
    clinical_effect: str | None = None
    clinical_advice: str | None = None
    monitoring: str | None = None
    source: str | None = None


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    updated_at: str


class MetricsResponse(BaseModel):
    documents: int
    chunks: int
    faq_count: int
    interactions: int
    graph_entities: int
    graph_relations: int
    labs: int
    departments: list[str]

"""FastAPI application for the 小荷 medical RAG assistant."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import Settings, get_settings
from .ingestion import KnowledgeBuilder
from .models import (
    ConversationSummary,
    HealthResponse,
    InteractionResponse,
    MetricsResponse,
    PreviewResponse,
    QueryRequest,
    QueryResponse,
)
from .normalization import MedicalTermNormalizer
from .pipeline import MedicalRAGPipeline
from .retrieval import HybridRetriever
from .storage import SQLiteStore


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    store = SQLiteStore(settings.db_path)
    if store.metrics()["chunks"] == 0:
        KnowledgeBuilder(settings.data_dir, store).build()
    normalizer = MedicalTermNormalizer(settings.data_dir)
    app.state.settings = settings
    app.state.store = store
    app.state.pipeline = MedicalRAGPipeline(HybridRetriever(store, normalizer))
    yield


app = FastAPI(
    title="小荷 MedRAG API",
    version=__version__,
    description="基于医学知识库和保守安全审核的循证问答接口",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]
    if "*" in get_settings().cors_origins
    else list(get_settings().cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _store() -> SQLiteStore:
    return app.state.store


def _pipeline() -> MedicalRAGPipeline:
    return app.state.pipeline


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"service": "小荷 MedRAG", "status": "ok", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    metrics = _store().metrics()
    return HealthResponse(
        status="ok",
        service="小荷 MedRAG",
        version=__version__,
        database="ready",
        chunks=metrics["chunks"],
    )


@app.get("/api/v1/metrics", response_model=MetricsResponse, tags=["knowledge"])
async def metrics(_: None = Depends(_require_api_key)) -> MetricsResponse:
    return MetricsResponse(**_store().metrics())


@app.post("/api/v1/query", response_model=QueryResponse, tags=["query"])
async def query(request: QueryRequest, _: None = Depends(_require_api_key)) -> QueryResponse:
    conversation_id = request.conversation_id or str(uuid.uuid4())
    response = _pipeline().invoke(request.question, request.top_k)
    response = response.model_copy(update={"conversation_id": conversation_id})
    timestamp = _now()
    store = _store()
    store.upsert_conversation(conversation_id, request.question[:40], timestamp)
    store.add_message(conversation_id, "user", request.question, timestamp)
    store.add_message(
        conversation_id,
        "assistant",
        response.answer,
        timestamp,
        json.dumps(response.model_dump(), ensure_ascii=False),
    )
    return response


@app.get("/api/v1/conversations", response_model=list[ConversationSummary], tags=["query"])
async def conversations(_: None = Depends(_require_api_key)) -> list[ConversationSummary]:
    return [ConversationSummary(**item) for item in _store().list_conversations()]


@app.get("/api/v1/conversations/{conversation_id}", tags=["query"])
async def conversation(conversation_id: str, _: None = Depends(_require_api_key)) -> dict:
    return {
        "conversation_id": conversation_id,
        "messages": _store().conversation_messages(conversation_id),
    }


@app.get("/api/v1/interactions", response_model=InteractionResponse, tags=["safety"])
async def interaction(
    drug_a: str,
    drug_b: str,
    _: None = Depends(_require_api_key),
) -> InteractionResponse:
    normalizer = MedicalTermNormalizer(app.state.settings.data_dir)
    names = [normalizer.normalize_term(drug_a), normalizer.normalize_term(drug_b)]
    records = _store().find_interactions(names)
    if not records:
        return InteractionResponse(found=False, drug_a=names[0], drug_b=names[1])
    item = records[0]
    return InteractionResponse(
        found=True,
        drug_a=item["drug_a"],
        drug_b=item["drug_b"],
        interaction_level=item["interaction_level"],
        mechanism=item["mechanism"],
        clinical_effect=item["clinical_effect"],
        clinical_advice=item["clinical_advice"],
        monitoring=item["monitoring"],
        source=item["source"],
    )


@app.post("/api/v1/documents/preview", response_model=PreviewResponse, tags=["documents"])
async def preview_document(
    file: UploadFile = File(...),  # noqa: B008
    _: None = Depends(_require_api_key),
) -> PreviewResponse:
    filename = file.filename or "uploaded-document"
    payload = await file.read()
    suffix = Path(filename).suffix.lower()
    warnings: list[str] = []
    page_count: int | None = None
    if suffix == ".pdf":
        try:
            import pymupdf

            document = pymupdf.open(stream=payload, filetype="pdf")
            page_count = document.page_count
            text = "\n\n".join(page.get_text("text").strip() for page in document)
            document.close()
            doc_type = "PDF医学文档"
        except Exception as exc:  # pragma: no cover - depends on malformed uploads
            raise HTTPException(status_code=400, detail=f"PDF解析失败: {exc}") from exc
    elif suffix in {".md", ".markdown", ".txt"}:
        text = payload.decode("utf-8", errors="replace")
        doc_type = "Markdown医学文档" if suffix != ".txt" else "文本医学文档"
    else:
        raise HTTPException(status_code=415, detail="仅支持 PDF、Markdown 和 TXT 预览")
    sections = [line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")]
    if not text.strip():
        warnings.append("文档没有提取到可检索文本，可能需要 OCR。")
    return PreviewResponse(
        filename=filename,
        doc_type=doc_type,
        page_count=page_count,
        extracted_text=text[:20000],
        sections=sections[:50],
        warnings=warnings,
    )

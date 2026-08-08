from pathlib import Path

from medrag.ingestion import KnowledgeBuilder
from medrag.models import ChunkRecord
from medrag.storage import SQLiteStore


def test_store_retrieves_interaction_and_lexical_chunk(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "medrag.sqlite3")
    KnowledgeBuilder(Path("med-rag-data"), store).build()
    interactions = store.find_interactions(["华法林", "阿司匹林"])
    assert interactions
    assert interactions[0]["interaction_level"] == "严重"
    results = store.search_lexical(["二甲双胍", "肾功能"], limit=5)
    assert results


def test_lexical_search_fallback_supports_doc_type_filter(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "test.sqlite3")
    store.insert_chunks(
        [
            ChunkRecord(
                chunk_id="chunk-1",
                source_id="source-1",
                source="指南",
                title="指南标题",
                content="仅有普通文档内容",
                doc_type="指南",
            )
        ]
    )

    assert store.search_lexical(["FAQ完全不会命中"], doc_type="FAQ") == []

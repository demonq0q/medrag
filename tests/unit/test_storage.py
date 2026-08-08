from pathlib import Path

from medrag.ingestion import KnowledgeBuilder
from medrag.storage import SQLiteStore


def test_store_retrieves_interaction_and_lexical_chunk(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "medrag.sqlite3")
    KnowledgeBuilder(Path("med-rag-data"), store).build()
    interactions = store.find_interactions(["华法林", "阿司匹林"])
    assert interactions
    assert interactions[0]["interaction_level"] == "严重"
    results = store.search_lexical(["二甲双胍", "肾功能"], limit=5)
    assert results

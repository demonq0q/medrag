from pathlib import Path

from medrag.ingestion import KnowledgeBuilder
from medrag.storage import SQLiteStore


def test_builder_creates_chunks_and_manifest(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "medrag.sqlite3")
    stats = KnowledgeBuilder(Path("med-rag-data"), store).build()
    assert stats.chunks > 100
    assert stats.faq_count == 30
    assert stats.interaction_count == 55
    assert stats.lab_count == 45
    assert stats.graph_entities > 0
    assert store.get_manifest()["input"]["file_count"] >= 78

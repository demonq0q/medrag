from pathlib import Path

from fastapi.testclient import TestClient

from medrag.config import get_settings
from medrag.ingestion import KnowledgeBuilder
from medrag.storage import SQLiteStore


def test_api_query_and_health(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("MEDRAG_DB_PATH", str(db_path))
    monkeypatch.setenv("MEDRAG_ARTIFACT_DIR", str(tmp_path))
    settings = get_settings()
    store = SQLiteStore(settings.db_path)
    KnowledgeBuilder(settings.data_dir, store).build()
    from medrag.app import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["chunks"] > 100
        response = client.post(
            "/api/v1/query",
            json={"question": "华法林和阿司匹林能否同时服用"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["risk_level"] == "high"
        assert body["citations"]

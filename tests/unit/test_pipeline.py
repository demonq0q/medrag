from pathlib import Path

from medrag.ingestion import KnowledgeBuilder
from medrag.normalization import MedicalTermNormalizer
from medrag.pipeline import MedicalRAGPipeline
from medrag.retrieval import HybridRetriever
from medrag.storage import SQLiteStore


def make_pipeline(tmp_path: Path) -> MedicalRAGPipeline:
    store = SQLiteStore(tmp_path / "medrag.sqlite3")
    KnowledgeBuilder(Path("med-rag-data"), store).build()
    return MedicalRAGPipeline(HybridRetriever(store, MedicalTermNormalizer(Path("med-rag-data"))))


def test_interaction_query_is_high_risk_and_cited(tmp_path: Path) -> None:
    response = make_pipeline(tmp_path).invoke("华法林和阿司匹林能否同时服用")
    assert response.risk_level == "high"
    assert "严重" in response.answer
    assert response.citations
    assert response.citations[0].citation_id == "C1"


def test_lab_query_returns_reference_context(tmp_path: Path) -> None:
    response = make_pipeline(tmp_path).invoke("糖化血红蛋白的参考范围和影响因素是什么")
    assert "参考范围" in response.answer
    assert "影响因素" in response.answer
    assert response.citations


def test_unknown_query_fails_closed(tmp_path: Path) -> None:
    response = make_pipeline(tmp_path).invoke("某个不存在的药物应该服用多少毫克")
    assert response.safety_status in {"blocked_no_evidence", "blocked_unsupported_dose"}
    assert "不会据此猜测" in response.answer

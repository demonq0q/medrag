from medrag.generation import TemplateGenerator
from medrag.models import ChunkRecord, Citation, RetrievalResult


def test_evidence_answer_preserves_markdown_table_structure() -> None:
    chunk = ChunkRecord(
        chunk_id="faq_test",
        source_id="faq_test",
        source="test.md",
        title="检验参考值",
        content=(
            "问题：参考范围是多少？\n\n"
            "回答：\n\n"
            "| 项目 | 范围 |\n"
            "| --- | --- |\n"
            "| 空腹血糖 | 3.9-6.1 mmol/L |"
        ),
        doc_type="FAQ",
    )
    result = RetrievalResult(chunk=chunk, score=0.8, routes=["faq"])
    citation = Citation(
        citation_id="C1",
        source_id=chunk.source_id,
        source=chunk.source,
        doc_type=chunk.doc_type,
    )

    answer = TemplateGenerator._evidence_answer("参考范围是多少？", [result], [citation])

    assert "### 证据摘录 [C1]" in answer
    assert "| 项目 | 范围 |\n| --- | --- |" in answer
    assert "\n| 空腹血糖 | 3.9-6.1 mmol/L |" in answer

    citation_snippet = TemplateGenerator._citation(result, 1).snippet
    assert "\n| 项目 | 范围 |" in citation_snippet

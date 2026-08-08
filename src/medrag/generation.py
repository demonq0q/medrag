"""Evidence-grounded answer generation with a deterministic no-key fallback."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Citation, RetrievalResult
from .retrieval import RetrievalBundle

DISCLAIMER = "\n\n> 以上内容仅基于当前知识库资料整理，不能替代医生诊断、处方或急诊服务。"


@dataclass(slots=True)
class GeneratedAnswer:
    answer: str
    citations: list[Citation]
    confidence: float


class TemplateGenerator:
    """A transparent generator used when no trusted LLM provider is configured."""

    def generate(self, question: str, bundle: RetrievalBundle) -> GeneratedAnswer:
        citations = [
            self._citation(result, index) for index, result in enumerate(bundle.results, start=1)
        ]
        if bundle.interactions:
            answer = self._interaction_answer(bundle.interactions[0], citations)
        elif bundle.labs:
            answer = self._lab_answer(bundle.labs[0], citations)
        elif bundle.results:
            answer = self._evidence_answer(question, bundle.results, citations)
        else:
            answer = "当前知识库中没有足够的循证资料支持这个问题，我不会据此猜测诊断、药物或剂量。"
        return GeneratedAnswer(
            answer=answer + DISCLAIMER,
            citations=citations,
            confidence=self._confidence(bundle),
        )

    @staticmethod
    def _citation(result: RetrievalResult, index: int) -> Citation:
        chunk = result.chunk
        snippet = " ".join(chunk.content.replace("\n", " ").split())[:180]
        return Citation(
            citation_id=f"C{index}",
            source_id=chunk.source_id,
            source=chunk.source,
            page_number=chunk.page_number,
            section=chunk.section,
            evidence_level=chunk.evidence_level,
            doc_type=chunk.doc_type,
            credibility_score=chunk.credibility_score,
            snippet=snippet,
        )

    @staticmethod
    def _interaction_answer(item: dict, citations: list[Citation]) -> str:
        source_refs = " ".join(f"[{citation.citation_id}]" for citation in citations[:2])
        return (
            f"## 重要药物相互作用\n\n"
            f"**{item['drug_a']} × {item['drug_b']}：{item['interaction_level']}** "
            f"{source_refs}\n\n"
            f"**作用机制**\n{item['mechanism']}\n\n"
            f"**可能风险**\n{item['clinical_effect']}\n\n"
            f"**处理建议**\n{item['clinical_advice']}\n\n"
            f"**需要监测**\n{item['monitoring']}\n\n"
            "请不要自行停药或调整剂量；是否联用必须由开方医生或药师结合适应证、出血风险和检查结果判断。"
        )

    @staticmethod
    def _lab_answer(item: dict, citations: list[Citation]) -> str:
        source_ref = f"[{citations[0].citation_id}]" if citations else ""
        factors = item.get("affecting_factors_json", "[]")
        import json

        try:
            factors_text = "、".join(json.loads(factors))
        except (TypeError, json.JSONDecodeError):
            factors_text = ""
        return (
            f"## {item['item']}（{item.get('abbreviation', '')}）{source_ref}\n\n"
            f"- **参考范围**：{item.get('normal_range', '')} {item.get('unit', '')}\n"
            f"- **样本类型**：{item.get('sample_type', '')}\n"
            f"- **临床意义**：{item.get('clinical_significance', '')}\n"
            f"- **影响因素**：{factors_text or '需结合检测方法、实验室参考范围和临床状态判断'}\n\n"
            "参考范围不是个人诊断阈值；如结果接近危急值或伴有明显不适，应及时联系医生。"
        )

    @staticmethod
    def _evidence_answer(
        question: str, results: list[RetrievalResult], citations: list[Citation]
    ) -> str:
        lines = ["## 基于循证资料的回答", "", f"针对“{question}”，当前检索到以下相关资料：", ""]
        for result, citation in zip(results[:4], citations[:4], strict=False):
            content = " ".join(result.chunk.content.replace("\n", " ").split())[:420]
            lines.append(f"- {content} [{citation.citation_id}]")
        lines.extend(
            [
                "",
                "以上内容是知识库证据摘要，具体诊疗应结合患者情况、最新指南和临床医生判断。",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _confidence(bundle: RetrievalBundle) -> float:
        if not bundle.results:
            return 0.05
        top = bundle.results[0]
        route_bonus = 0.08 if len(top.routes) > 1 else 0.0
        return round(min(0.96, 0.55 + top.chunk.credibility_score * 0.3 + route_bonus), 2)

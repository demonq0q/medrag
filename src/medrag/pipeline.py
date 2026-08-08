"""LangGraph orchestration for the medical RAG query path."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .generation import GeneratedAnswer, TemplateGenerator
from .models import QueryResponse
from .retrieval import HybridRetriever, RetrievalBundle
from .safety import SafetyAuditor, SafetyResult


class PipelineState(TypedDict, total=False):
    question: str
    top_k: int
    retrieval: RetrievalBundle
    generated: GeneratedAnswer
    safety: SafetyResult
    response: QueryResponse


class MedicalRAGPipeline:
    """Retrieve → compose → audit → finalize graph."""

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.generator = TemplateGenerator()
        self.auditor = SafetyAuditor()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(PipelineState)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("compose", self._compose)
        graph.add_node("audit", self._audit)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "compose")
        graph.add_edge("compose", "audit")
        graph.add_edge("audit", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def invoke(self, question: str, top_k: int = 6) -> QueryResponse:
        state = self.graph.invoke({"question": question, "top_k": top_k})
        return state["response"]

    def _retrieve(self, state: PipelineState) -> dict[str, Any]:
        return {"retrieval": self.retriever.retrieve(state["question"], state.get("top_k", 6))}

    def _compose(self, state: PipelineState) -> dict[str, Any]:
        return {"generated": self.generator.generate(state["question"], state["retrieval"])}

    def _audit(self, state: PipelineState) -> dict[str, Any]:
        bundle = state["retrieval"]
        generated = state["generated"]
        return {"safety": self.auditor.audit(state["question"], generated.answer, bundle)}

    def _finalize(self, state: PipelineState) -> dict[str, Any]:
        bundle = state["retrieval"]
        generated = state["generated"]
        safety = state["safety"]
        answer = generated.answer
        citations = generated.citations
        confidence = generated.confidence
        if safety.safety_status.startswith("blocked"):
            answer = (
                "当前问题缺少可验证的医学实体或循证来源，我不会据此猜测诊断、药物或剂量。\n\n"
                "> 以上内容仅基于当前知识库资料整理，不能替代医生诊断、处方或急诊服务。"
            )
            citations = []
            confidence = 0.05
        return {
            "response": QueryResponse(
                answer=answer,
                citations=citations,
                risk_level=safety.risk_level,
                safety_status=safety.safety_status,
                warnings=safety.warnings,
                confidence=confidence,
                follow_up=safety.follow_up,
                normalized_query=bundle.normalized_query,
                entities=bundle.entities,
                retrieval_trace=bundle.trace,
            )
        }

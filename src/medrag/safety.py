"""Conservative safety controls for medical answers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .retrieval import RetrievalBundle

EMERGENCY_TERMS = (
    "胸痛",
    "呼吸困难",
    "意识不清",
    "口角歪斜",
    "言语不清",
    "大出血",
    "黑便",
    "呕血",
    "昏迷",
    "严重过敏",
    "自杀",
    "抽搐",
)
DOSAGE_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|g|ml|mL|μg|ug|单位|U|片|粒|次|/日|/天)", re.I)


@dataclass(slots=True)
class SafetyResult:
    risk_level: str = "low"
    safety_status: str = "reviewed"
    warnings: list[str] = field(default_factory=list)
    follow_up: list[str] = field(default_factory=list)


class SafetyAuditor:
    """Rule-based safety gate that fails closed when evidence is insufficient."""

    def audit(self, question: str, answer: str, bundle: RetrievalBundle) -> SafetyResult:
        result = SafetyResult()
        if any(term in question for term in EMERGENCY_TERMS):
            result.risk_level = "critical"
            result.safety_status = "urgent_referral"
            result.warnings.append("检测到可能的急症关键词，请立即联系急救服务或前往急诊。")
            result.follow_up.append("如有胸痛、呼吸困难、意识障碍或大出血，请不要等待线上问答。")

        severe = [
            item
            for item in bundle.interactions
            if item.get("interaction_level") in {"禁忌", "严重"}
        ]
        if severe:
            result.risk_level = "high" if result.risk_level != "critical" else result.risk_level
            result.safety_status = "high_risk_review"
            for item in severe[:2]:
                result.warnings.append(
                    f"{item['drug_a']}与{item['drug_b']}存在{item['interaction_level']}相互作用，需由医生或药师核对用药。"
                )
            result.follow_up.append("不要自行停药、加量或叠加其他抗凝/抗血小板药物。")

        has_medical_context = (
            any(bundle.entities.values()) or bool(bundle.interactions) or bool(bundle.labs)
        )
        if not bundle.results or not has_medical_context:
            result.risk_level = max(result.risk_level, "medium", key=self._risk_rank)
            result.safety_status = "blocked_no_evidence"
            result.warnings.append("当前知识库没有足够的可引用资料支持该问题，系统不会猜测答案。")

        if DOSAGE_PATTERN.search(answer) and not bundle.results:
            result.risk_level = "high"
            result.safety_status = "blocked_unsupported_dose"
            result.warnings.append("检测到剂量表达但缺少可验证来源，已阻止输出。")

        if not result.follow_up and bundle.results:
            result.follow_up.append(
                "如需个体化建议，请补充年龄、基础疾病、当前用药和相关检查结果，并咨询临床医生。"
            )
        return result

    @staticmethod
    def _risk_rank(value: str) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(value, 0)

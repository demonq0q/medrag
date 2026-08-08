"""Medical term normalization and lightweight entity extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BASE_ALIASES = {
    "扑热息痛": "对乙酰氨基酚",
    "paracetamol": "对乙酰氨基酚",
    "acetaminophen": "对乙酰氨基酚",
    "感冒": "上呼吸道感染",
    "血压高": "高血压",
    "心衰": "心力衰竭",
    "慢阻肺": "慢性阻塞性肺疾病",
}


class MedicalTermNormalizer:
    """Normalize aliases with longest-term-first matching."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.alias_to_standard: dict[str, str] = dict(BASE_ALIASES)
        self.standard_terms: set[str] = set(BASE_ALIASES.values())
        self.term_metadata: dict[str, dict[str, Any]] = {}
        self._load()
        self._aliases = sorted(self.alias_to_standard, key=len, reverse=True)
        self._standards = sorted(self.standard_terms, key=len, reverse=True)

    def _load(self) -> None:
        path = self.data_dir / "reference" / "medical_synonyms.json"
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for group in payload.get("synonym_groups", []):
            standard = str(group.get("standard_term", "")).strip()
            if not standard:
                continue
            self.standard_terms.add(standard)
            self.term_metadata[standard] = group
            self.alias_to_standard.setdefault(standard, standard)
            for alias in group.get("synonyms", []):
                alias = str(alias).strip()
                if alias:
                    self.alias_to_standard[alias] = standard

    def normalize_term(self, term: str) -> str:
        normalized = term.strip()
        if not normalized:
            return normalized
        return self.alias_to_standard.get(normalized, normalized)

    def normalize_text(self, text: str) -> str:
        """Protect canonical terms, then replace aliases longest-first."""
        normalized = text.strip()
        if not normalized:
            return normalized
        protected: dict[str, str] = {}
        for index, standard in enumerate(self._standards):
            if standard and standard in normalized:
                marker = f"\ue000{index}\ue001"
                normalized = normalized.replace(standard, marker)
                protected[marker] = standard
        for alias in self._aliases:
            standard = self.alias_to_standard[alias]
            if alias == standard or not alias:
                continue
            normalized = normalized.replace(alias, standard)
        for marker, standard in protected.items():
            normalized = normalized.replace(marker, standard)
        return normalized

    def tokenize(self, text: str) -> list[str]:
        normalized = self.normalize_text(text)
        try:
            import jieba

            for term in self.standard_terms:
                if len(term) > 1:
                    jieba.add_word(term)
            tokens = [token.strip().lower() for token in jieba.lcut(normalized) if token.strip()]
        except ImportError:
            tokens = re.findall(r"[A-Za-z0-9_.+-]+|[\u4e00-\u9fff]", normalized.lower())
        return [
            token
            for token in tokens
            if token not in {"的", "了", "和", "是", "有", "吗", "我", "请"}
        ]

    def extract_entities(self, text: str) -> dict[str, list[str]]:
        normalized = self.normalize_text(text)
        terms = [term for term in self._standards if term and term in normalized]
        drugs: list[str] = []
        diseases: list[str] = []
        examinations: list[str] = []
        symptoms: list[str] = []
        for term in terms:
            category = str(self.term_metadata.get(term, {}).get("category", ""))
            if "药" in category or term in {"华法林", "阿司匹林", "布洛芬", "对乙酰氨基酚"}:
                drugs.append(term)
            elif "检查" in category or term.upper() in {"FPG", "HBA1C", "EGFR", "INR"}:
                examinations.append(term)
            elif "症状" in category:
                symptoms.append(term)
            else:
                diseases.append(term)
        return {
            "drugs": list(dict.fromkeys(drugs)),
            "diseases": list(dict.fromkeys(diseases)),
            "examinations": list(dict.fromkeys(examinations)),
            "symptoms": list(dict.fromkeys(symptoms)),
        }

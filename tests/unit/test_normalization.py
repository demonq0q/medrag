from pathlib import Path

from medrag.normalization import MedicalTermNormalizer


def test_normalizes_alias_and_protects_canonical_term() -> None:
    normalizer = MedicalTermNormalizer(Path("med-rag-data"))
    assert normalizer.normalize_term("扑热息痛") == "对乙酰氨基酚"
    assert normalizer.normalize_text("扑热息痛和华法林") == "对乙酰氨基酚和华法林"
    assert "2型糖尿病" in normalizer.normalize_text("2型糖尿病患者")


def test_extracts_drug_entities() -> None:
    normalizer = MedicalTermNormalizer(Path("med-rag-data"))
    entities = normalizer.extract_entities("华法林和阿司匹林能一起吃吗")
    assert "华法林" in entities["drugs"]
    assert "阿司匹林" in entities["drugs"]

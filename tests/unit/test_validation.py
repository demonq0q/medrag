from pathlib import Path

from medrag.validation import validate_dataset


def test_dataset_is_valid_and_reports_actual_files() -> None:
    result = validate_dataset(Path("med-rag-data"))
    assert result["valid"] is True
    assert result["file_count"] >= 78
    assert result["json_counts"]["faq/faq_dataset.json:faq_entries"] == 30
    assert result["json_counts"]["reference/medical_synonyms.json:synonym_groups"] == 102

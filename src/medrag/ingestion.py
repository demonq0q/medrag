"""Data inventory, format parsing and medical chunk construction."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import ChunkRecord
from .normalization import MedicalTermNormalizer
from .storage import SQLiteStore

try:
    import pymupdf as fitz  # type: ignore
except ImportError:  # pragma: no cover - exercised only in minimal environments
    try:
        import fitz  # type: ignore
    except ImportError:
        fitz = None


DOC_TYPES = {
    "guidelines": "临床指南",
    "drug_labels": "药品说明书",
    "disease_entries": "疾病知识",
}


@dataclass(slots=True)
class BuildStats:
    source_files: int = 0
    markdown_files: int = 0
    pdf_files: int = 0
    json_files: int = 0
    chunks: int = 0
    parent_chunks: int = 0
    faq_count: int = 0
    interaction_count: int = 0
    lab_count: int = 0
    graph_entities: int = 0
    graph_relations: int = 0
    skipped_files: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_files": self.source_files,
            "markdown_files": self.markdown_files,
            "pdf_files": self.pdf_files,
            "json_files": self.json_files,
            "chunks": self.chunks,
            "parent_chunks": self.parent_chunks,
            "faq_count": self.faq_count,
            "interaction_count": self.interaction_count,
            "lab_count": self.lab_count,
            "graph_entities": self.graph_entities,
            "graph_relations": self.graph_relations,
            "skipped_files": self.skipped_files or [],
        }


class KnowledgeBuilder:
    """Build a deterministic local SQLite knowledge base from the supplied dataset."""

    def __init__(self, data_dir: Path, store: SQLiteStore):
        self.data_dir = Path(data_dir)
        self.store = store
        self.normalizer = MedicalTermNormalizer(self.data_dir)
        self.stats = BuildStats(skipped_files=[])
        self.chunks: list[ChunkRecord] = []
        self.interactions: list[dict[str, Any]] = []
        self.labs: list[dict[str, Any]] = []
        self.graph_entities: list[dict[str, Any]] = []
        self.graph_relations: list[dict[str, Any]] = []

    def build(self) -> BuildStats:
        self._reset_state()
        files = sorted(
            path
            for path in self.data_dir.rglob("*")
            if path.is_file()
            and path.name not in {"scrape_log.txt"}
            and not path.name.endswith(".bak")
        )
        self.stats.source_files = len(files)
        for path in files:
            relative = path.relative_to(self.data_dir).as_posix()
            try:
                if path.suffix.lower() == ".md":
                    self.stats.markdown_files += 1
                    self._parse_markdown(path, relative)
                elif path.suffix.lower() == ".pdf":
                    self.stats.pdf_files += 1
                    self._parse_pdf(path, relative)
                elif path.suffix.lower() == ".json":
                    self.stats.json_files += 1
                    self._parse_json(path, relative)
                else:
                    self.stats.skipped_files.append(relative)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                self.stats.skipped_files.append(f"{relative}: {exc}")

        self.store.reset_knowledge()
        self.store.insert_chunks(self.chunks)
        self.store.replace_interactions(self.interactions)
        entity_count, relation_count = self.store.replace_graph(
            self.graph_entities, self.graph_relations
        )
        self.store.replace_labs(self.labs)
        self.stats.chunks = sum(1 for chunk in self.chunks if not chunk.is_parent)
        self.stats.parent_chunks = sum(1 for chunk in self.chunks if chunk.is_parent)
        self.stats.graph_entities = entity_count
        self.stats.graph_relations = relation_count
        manifest = self._manifest(files)
        self.store.set_manifest({"build": self.stats.as_dict(), "input": manifest})
        return self.stats

    def _reset_state(self) -> None:
        self.stats = BuildStats(skipped_files=[])
        self.chunks = []
        self.interactions = []
        self.labs = []
        self.graph_entities = []
        self.graph_relations = []

    def _manifest(self, files: list[Path]) -> dict[str, Any]:
        digest = hashlib.sha256()
        entries: list[dict[str, Any]] = []
        for path in files:
            content = path.read_bytes()
            relative = path.relative_to(self.data_dir).as_posix()
            file_hash = hashlib.sha256(content).hexdigest()
            digest.update(relative.encode("utf-8"))
            digest.update(file_hash.encode("ascii"))
            entries.append({"path": relative, "bytes": len(content), "sha256": file_hash})
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "file_count": len(files),
            "content_hash": digest.hexdigest(),
            "files": entries,
        }

    @staticmethod
    def _source_id(relative: str) -> str:
        return f"doc_{hashlib.sha1(relative.encode('utf-8')).hexdigest()[:12]}"

    @staticmethod
    def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) != 3:
            return {}, text
        metadata: dict[str, str] = {}
        for line in parts[1].splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip("\"'")
        return metadata, parts[2].lstrip("\n")

    @staticmethod
    def _title_from_text(path: Path, text: str) -> str:
        for line in text.splitlines():
            match = re.match(r"^#{1,2}\s+(.+?)\s*$", line)
            if match:
                return match.group(1).strip().strip("#")
        return path.stem

    @staticmethod
    def _classify(relative: str) -> tuple[str, str, float]:
        parts = Path(relative).parts
        if "guidelines" in parts:
            field = "心内科" if "cardiology" in parts else "内分泌科"
            return "临床指南", field, 0.96
        if "drug_labels" in parts:
            return "药品说明书", "药学", 0.93
        if "disease_entries" in parts or "processed" in parts:
            field = ""
            for candidate in (
                "内分泌科",
                "心内科",
                "呼吸科",
                "消化科",
                "神经内科",
                "精神科",
                "骨科",
                "肾内科",
            ):
                if candidate in Path(relative).stem:
                    field = candidate
                    break
            return "疾病知识", field, 0.88
        return "医学资料", "", 0.70

    @staticmethod
    def _split_sections(text: str, max_chars: int = 1800) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_title = "正文"
        current: list[str] = []
        for line in text.splitlines():
            if re.match(r"^#{1,6}\s+", line):
                if current and "\n".join(current).strip():
                    sections.append((current_title, "\n".join(current).strip()))
                current_title = re.sub(r"^#{1,6}\s+", "", line).strip().strip("#")
                current = []
            else:
                current.append(line)
        if current and "\n".join(current).strip():
            sections.append((current_title, "\n".join(current).strip()))
        if not sections:
            sections = [("正文", text.strip())]
        result: list[tuple[str, str]] = []
        for title, content in sections:
            if len(content) <= max_chars:
                result.append((title, content))
                continue
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
            buffer = ""
            for paragraph in paragraphs:
                if buffer and len(buffer) + len(paragraph) + 2 > max_chars:
                    result.append((title, buffer.strip()))
                    buffer = ""
                buffer = f"{buffer}\n\n{paragraph}".strip()
            if buffer:
                result.append((title, buffer.strip()))
        return result

    def _append_text_chunks(
        self,
        *,
        source_id: str,
        source: str,
        title: str,
        text: str,
        doc_type: str,
        medical_field: str = "",
        evidence_level: str = "",
        drug_name: str = "",
        disease_name: str = "",
        page_number: int | None = None,
        publish_date: str = "",
        credibility_score: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        chunk_ids: list[str] = []
        for index, (section, content) in enumerate(self._split_sections(text)):
            if not content:
                continue
            base = f"{source_id}_{index + 1}"
            parent_id: str | None = None
            if len(content) > 1900:
                parent_id = f"{base}_parent"
                self.chunks.append(
                    ChunkRecord(
                        chunk_id=parent_id,
                        source_id=source_id,
                        source=source,
                        title=title,
                        content=content,
                        doc_type=doc_type,
                        medical_field=medical_field,
                        evidence_level=evidence_level,
                        drug_name=drug_name,
                        disease_name=disease_name,
                        page_number=page_number,
                        section=section,
                        publish_date=publish_date,
                        credibility_score=credibility_score,
                        is_parent=True,
                        metadata={**(metadata or {}), "chunk_role": "parent"},
                    )
                )
            chunk = ChunkRecord(
                chunk_id=base,
                source_id=source_id,
                source=source,
                title=title,
                content=content,
                doc_type=doc_type,
                medical_field=medical_field,
                evidence_level=evidence_level,
                drug_name=drug_name,
                disease_name=disease_name,
                page_number=page_number,
                section=section,
                publish_date=publish_date,
                credibility_score=credibility_score,
                parent_chunk_id=parent_id,
                metadata={**(metadata or {}), "chunk_role": "child" if parent_id else "single"},
            )
            self.chunks.append(chunk)
            chunk_ids.append(base)
        return chunk_ids

    def _parse_markdown(self, path: Path, relative: str) -> None:
        if relative == "README.md":
            return
        raw = path.read_text(encoding="utf-8", errors="ignore")
        front_matter, body = self._parse_front_matter(raw)
        doc_type, field, credibility = self._classify(relative)
        title = front_matter.get("title") or self._title_from_text(path, body)
        source_id = self._source_id(relative)
        drugs = [term for term in self.normalizer.standard_terms if term in path.stem]
        diseases = [term for term in self.normalizer.standard_terms if term in path.stem]
        self._append_text_chunks(
            source_id=source_id,
            source=relative,
            title=title,
            text=body,
            doc_type=doc_type,
            medical_field=front_matter.get("department", field),
            evidence_level="A" if doc_type == "临床指南" else "",
            drug_name="、".join(sorted(drugs, key=len, reverse=True)[:3]),
            disease_name="、".join(sorted(diseases, key=len, reverse=True)[:3]),
            publish_date=front_matter.get("scrape_date", ""),
            credibility_score=credibility,
            metadata={"path": relative, "front_matter": front_matter},
        )

    def _parse_pdf(self, path: Path, relative: str) -> None:
        source_id = self._source_id(relative)
        doc_type, field, credibility = self._classify(relative)
        if fitz is None:
            self.stats.skipped_files.append(f"{relative}: PyMuPDF unavailable")
            return
        document = fitz.open(path)
        try:
            for page_index, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if not text:
                    continue
                self._append_text_chunks(
                    source_id=f"{source_id}_p{page_index}",
                    source=relative,
                    title=path.stem,
                    text=text,
                    doc_type=doc_type,
                    medical_field=field,
                    evidence_level="A",
                    page_number=page_index,
                    credibility_score=credibility,
                    metadata={"path": relative, "parser": "pymupdf"},
                )
        finally:
            document.close()

    @staticmethod
    def _json_text(value: Any, prefix: str = "") -> str:
        if isinstance(value, dict):
            return "\n".join(
                f"{prefix}{key}: {KnowledgeBuilder._json_text(item, prefix + '  ')}"
                for key, item in value.items()
            )
        if isinstance(value, list):
            return "\n".join(f"- {KnowledgeBuilder._json_text(item, prefix)}" for item in value)
        return str(value) if value is not None else ""

    def _parse_json(self, path: Path, relative: str) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if relative.endswith("faq_dataset.json"):
            for item in payload.get("faq_entries", []):
                faq_id = item.get("id", self._source_id(relative))
                content = (
                    f"问题：{item.get('question', '')}\n\n回答：{item.get('answer', '')}\n\n"
                    f"关键词：{'、'.join(item.get('keywords', []))}\n"
                    f"相关疾病：{'、'.join(item.get('related_diseases', []))}\n"
                    f"相关药品：{'、'.join(item.get('related_drugs', []))}"
                )
                self._append_text_chunks(
                    source_id=faq_id,
                    source=item.get("source", faq_id),
                    title=item.get("question", faq_id),
                    text=content,
                    doc_type="FAQ",
                    medical_field=item.get("category", "").strip(),
                    evidence_level=item.get("evidence_level", ""),
                    drug_name="、".join(item.get("related_drugs", [])),
                    disease_name="、".join(item.get("related_diseases", [])),
                    credibility_score=0.86,
                    metadata={
                        "category": item.get("category", ""),
                        "question_synonyms": item.get("question_synonyms", []),
                    },
                )
                self.stats.faq_count += 1
            return
        if relative.endswith("drug_interactions.json"):
            for item in payload.get("drug_interactions", []):
                interaction_id = item.get("id", f"DDI_{len(self.interactions) + 1:03d}")
                text = (
                    f"药物相互作用：{item.get('drug_a', '')} × {item.get('drug_b', '')}\n"
                    f"风险等级：{item.get('interaction_level', '')}\n"
                    f"机制：{item.get('mechanism', '')}\n"
                    f"临床影响：{item.get('clinical_effect', '')}\n"
                    f"临床建议：{item.get('clinical_advice', '')}\n"
                    f"监测：{item.get('monitoring', '')}"
                )
                chunk_id = f"{interaction_id}_1"
                self._append_text_chunks(
                    source_id=interaction_id,
                    source=item.get("source", relative),
                    title=f"{item.get('drug_a', '')}与{item.get('drug_b', '')}相互作用",
                    text=text,
                    doc_type="药物相互作用",
                    medical_field="药学",
                    evidence_level="A",
                    drug_name=f"{item.get('drug_a', '')}、{item.get('drug_b', '')}",
                    credibility_score=0.94,
                    metadata={"interaction_id": interaction_id},
                )
                item = {**item, "id": interaction_id, "chunk_id": chunk_id}
                self.interactions.append(item)
                self.stats.interaction_count += 1
            return
        if relative.endswith("medical_entities_relations.json"):
            for entity_type, items in payload.get("entities", {}).items():
                for index, item in enumerate(items):
                    name = str(item.get("name", "")).strip()
                    if name:
                        entity_hash = hashlib.sha1(name.encode()).hexdigest()[:8]
                        self.graph_entities.append(
                            {
                                "id": f"{entity_type}_{index}_{entity_hash}",
                                "type": entity_type,
                                "name": name,
                                "normalized_name": self.normalizer.normalize_term(name),
                                "attributes": item,
                            }
                        )
            for index, relation in enumerate(payload.get("relations", [])):
                source = relation.get("source", "")
                target = relation.get("target", "")
                relation_hash = hashlib.sha1(f"{source}:{target}".encode()).hexdigest()[:8]
                self.graph_relations.append(
                    {
                        "id": f"relation_{index}_{relation_hash}",
                        "source": source,
                        "target": target,
                        "type": relation.get("type", "RELATED_TO"),
                        "evidence": relation.get("evidence", ""),
                    }
                )
            return
        if relative.endswith("lab_reference_values.json"):
            for item in payload.get("lab_reference_values", []):
                lab_id = item.get("id", f"LAB_{len(self.labs) + 1:03d}")
                text = (
                    f"检验项目：{item.get('item', '')}（{item.get('abbreviation', '')}）\n"
                    f"参考范围：{item.get('normal_range', '')} {item.get('unit', '')}\n"
                    f"危急高值：{item.get('critical_high', '无')}；"
                    f"危急低值：{item.get('critical_low', '无')}\n"
                    f"临床意义：{item.get('clinical_significance', '')}\n"
                    f"影响因素：{'、'.join(item.get('affecting_factors', []))}"
                )
                chunk_id = f"{lab_id}_1"
                self._append_text_chunks(
                    source_id=lab_id,
                    source=relative,
                    title=item.get("item", lab_id),
                    text=text,
                    doc_type="检验参考值",
                    medical_field=item.get("category", "检验科"),
                    evidence_level="B",
                    credibility_score=0.90,
                    metadata={"lab_id": lab_id},
                )
                self.labs.append({**item, "id": lab_id, "chunk_id": chunk_id})
                self.stats.lab_count += 1
            return
        if relative.endswith("disease_entries.json"):
            for index, item in enumerate(payload.get("disease_entries", [])):
                name = item.get("disease_name") or item.get("name") or f"疾病条目{index + 1}"
                source_id = f"disease_{hashlib.sha1(str(name).encode()).hexdigest()[:12]}"
                self._append_text_chunks(
                    source_id=source_id,
                    source=relative,
                    title=str(name),
                    text=self._json_text(item),
                    doc_type="疾病知识",
                    medical_field=item.get("department", ""),
                    disease_name=str(name),
                    credibility_score=0.90,
                    metadata={"structured": True},
                )
            return

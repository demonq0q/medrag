"""Runtime configuration for the MedRAG service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    artifact_dir: Path
    db_path: Path
    cors_origins: tuple[str, ...]
    environment: str
    llm_provider: str
    llm_api_key: str | None
    llm_base_url: str | None
    llm_model: str | None
    api_key: str | None
    api_host: str
    api_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.getenv("MEDRAG_PROJECT_ROOT", PROJECT_ROOT)).resolve()
        data_dir = Path(os.getenv("MEDRAG_DATA_DIR", root / "med-rag-data"))
        artifact_dir = Path(os.getenv("MEDRAG_ARTIFACT_DIR", root / "artifacts"))
        db_path = Path(os.getenv("MEDRAG_DB_PATH", artifact_dir / "medrag.sqlite3"))
        if not data_dir.is_absolute():
            data_dir = (root / data_dir).resolve()
        if not artifact_dir.is_absolute():
            artifact_dir = (root / artifact_dir).resolve()
        if not db_path.is_absolute():
            db_path = (root / db_path).resolve()
        return cls(
            project_root=root,
            data_dir=data_dir,
            artifact_dir=artifact_dir,
            db_path=db_path,
            cors_origins=_csv(os.getenv("MEDRAG_CORS_ORIGINS"), ("*",)),
            environment=os.getenv("MEDRAG_ENV", "local"),
            llm_provider=os.getenv("MEDRAG_LLM_PROVIDER", "template"),
            llm_api_key=os.getenv("MEDRAG_LLM_API_KEY") or None,
            llm_base_url=os.getenv("MEDRAG_LLM_BASE_URL") or None,
            llm_model=os.getenv("MEDRAG_LLM_MODEL") or None,
            api_key=os.getenv("MEDRAG_API_KEY") or None,
            api_host=os.getenv("MEDRAG_API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("MEDRAG_API_PORT", "8000")),
        )

    def ensure_directories(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings.from_env()

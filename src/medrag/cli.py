"""Command line entry points for local data and service operations."""

from __future__ import annotations

import argparse
import json

from .config import get_settings
from .ingestion import KnowledgeBuilder
from .storage import SQLiteStore
from .validation import validate_dataset


def build_knowledge_base() -> dict:
    settings = get_settings()
    settings.ensure_directories()
    store = SQLiteStore(settings.db_path)
    stats = KnowledgeBuilder(settings.data_dir, store).build()
    result = {
        "stats": stats.as_dict(),
        "metrics": store.metrics(),
        "manifest": store.get_manifest(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="medrag")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="build the SQLite knowledge base")
    subparsers.add_parser("validate", help="validate source files and metadata")
    subparsers.add_parser("manifest", help="print the built knowledge manifest")
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "build":
        build_knowledge_base()
    elif args.command == "validate":
        print(json.dumps(validate_dataset(settings.data_dir), ensure_ascii=False, indent=2))
    elif args.command == "manifest":
        store = SQLiteStore(settings.db_path)
        print(json.dumps(store.get_manifest(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

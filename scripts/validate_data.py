#!/usr/bin/env python3
"""Validate all source data and report actual counts."""

import json

from medrag.config import get_settings
from medrag.validation import validate_dataset

if __name__ == "__main__":
    print(json.dumps(validate_dataset(get_settings().data_dir), ensure_ascii=False, indent=2))

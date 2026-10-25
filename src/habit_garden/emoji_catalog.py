"""Validate emoji labels against the bundled Unicode catalog."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = Path(__file__).parent / "static" / "emoji-catalog.json"
DEFAULT_EMOJI = "🌱"


@lru_cache(maxsize=1)
def allowed_emojis() -> frozenset[str]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return frozenset(item[0] for item in data["items"])

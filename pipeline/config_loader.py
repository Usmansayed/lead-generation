"""
Load Phase 1 config: keywords_master.json and phase1_sources.yaml.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import yaml

# Default: project root = parent of pipeline/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def load_keywords_master(path: Path | None = None) -> dict[str, Any]:
    p = path or (CONFIG_DIR / "keywords_master.json")
    if not p.exists():
        return {"intent_categories": {}}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_phase1_sources(path: Path | None = None) -> dict[str, Any]:
    p = path or (CONFIG_DIR / "phase1_sources.yaml")
    if not p.exists():
        return {"actors": {}, "platforms": []}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_platform_actor_config(sources: dict, platform: str) -> dict | None:
    """Return actor config for platform (folder + input)."""
    actors = sources.get("actors") or {}
    return actors.get(platform)


def get_all_intent_keywords(keywords_master: dict) -> list[str]:
    """Flatten all intent keywords for matching."""
    cats = keywords_master.get("intent_categories") or {}
    out: list[str] = []
    for kws in cats.values():
        if isinstance(kws, list):
            out.extend(kws)
    return list(dict.fromkeys(out))

"""
Search builder: build actor run_input (keywords, subreddits, etc.) from config/search_strategy.yaml
and optionally config/keywords_map.yaml (large, efficient keyword set for all 5 platforms).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

import yaml

from .config_loader import CONFIG_DIR

SEARCH_STRATEGY_PATH = CONFIG_DIR / "search_strategy.yaml"
KEYWORDS_MAP_FILENAME = "keywords_map.yaml"


def _load_search_strategy(path: Path | None = None) -> dict[str, Any]:
    p = path or SEARCH_STRATEGY_PATH
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_keywords_map(path: Path | None = None) -> dict[str, Any]:
    """Load keywords map YAML (themes + platform_keywords). Returns {} if missing."""
    p = path or (CONFIG_DIR / KEYWORDS_MAP_FILENAME)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _flatten_theme_phrases(cfg: dict) -> list[str]:
    """From a theme config, return ordered list: core then extended then long_tail, else seed_phrases."""
    if not isinstance(cfg, dict):
        return []
    out: list[str] = []
    for key in ("core", "extended", "long_tail"):
        part = cfg.get(key)
        if isinstance(part, list):
            out.extend(part)
    if out:
        return list(dict.fromkeys(out))
    return list(dict.fromkeys(cfg.get("seed_phrases") or []))


def _collect_theme_phrases_from_map(
    keywords_map: dict,
    announcement_ratio: float = 0.8,
    max_total: int = 50,
) -> list[str]:
    """Build phrase list from keywords_map: announcement (launch + international) then need_developer, by ratio."""
    themes = keywords_map.get("themes") or {}
    announcement: list[str] = []
    for name in ("announcement_launch", "international_launch"):
        cfg = themes.get(name)
        if isinstance(cfg, dict):
            announcement.extend(_flatten_theme_phrases(cfg))
    need_dev_cfg = themes.get("need_developer")
    need_dev = _flatten_theme_phrases(need_dev_cfg) if isinstance(need_dev_cfg, dict) else []
    announcement = list(dict.fromkeys(announcement))
    need_dev = list(dict.fromkeys(need_dev))
    n_ann = min(len(announcement), max(1, int(max_total * announcement_ratio)))
    n_dev = min(len(need_dev), max(0, max_total - n_ann))
    out: list[str] = []
    out.extend(announcement[:n_ann])
    out.extend(need_dev[:n_dev])
    return list(dict.fromkeys(out))


def _collect_physical_opening_phrases(keywords_map: dict, max_total: int = 50) -> list[str]:
    """Phrases for physical/local opening only (no 'just launched' / product/website launches). Used for IG/FB."""
    themes = keywords_map.get("themes") or {}
    cfg = themes.get("physical_opening_first")
    if not isinstance(cfg, dict):
        return []
    phrases = _flatten_theme_phrases(cfg)
    return list(dict.fromkeys(phrases))[:max_total]


def _collect_theme_phrases(
    strategy: dict,
    announcement_ratio: float = 0.8,
    max_total: int = 50,
) -> list[str]:
    """Collect phrases from strategy themes (fallback when no keywords_map). announcement_ratio to launch, rest to need_developer."""
    themes = strategy.get("themes") or {}
    announcement: list[str] = []
    need_dev: list[str] = []
    for name, cfg in themes.items():
        if not isinstance(cfg, dict):
            continue
        phrases = cfg.get("seed_phrases") or _flatten_theme_phrases(cfg)
        if not phrases and (cfg.get("core") or cfg.get("extended")):
            phrases = _flatten_theme_phrases(cfg)
        if "announcement" in name.lower() or "launch" in name.lower():
            announcement.extend(phrases)
        else:
            need_dev.extend(phrases)
    announcement = list(dict.fromkeys(announcement))
    need_dev = list(dict.fromkeys(need_dev))
    n_ann = min(len(announcement), max(1, int(max_total * announcement_ratio)))
    n_dev = min(len(need_dev), max(0, max_total - n_ann))
    out: list[str] = []
    out.extend(announcement[:n_ann])
    out.extend(need_dev[:n_dev])
    return list(dict.fromkeys(out))


def _platform_terms_from_map(
    keywords_map: dict,
    strategy: dict,
    platform: str,
    base_phrases: list[str],
) -> list[str]:
    """Add platform-specific terms from keywords_map and cap using strategy limits."""
    limits = strategy.get("limits") or {}
    caps = limits.get("max_search_terms_per_platform") or {}
    max_terms = caps.get(platform.lower(), 30)
    pk = (keywords_map.get("platform_keywords") or {}).get(platform.lower()) or {}
    hashtags = pk.get("hashtags") or []
    phrase_additions = pk.get("phrase_additions") or []
    combined = list(dict.fromkeys(base_phrases + phrase_additions + hashtags))
    return combined[:max_terms]


def _platform_terms(strategy: dict, platform: str, base_phrases: list[str]) -> list[str]:
    """Add platform-specific expansions (hashtags, phrase_additions) and cap total."""
    limits = strategy.get("limits") or {}
    caps = limits.get("max_search_terms_per_platform") or {}
    max_terms = caps.get(platform.lower(), 30)
    expansions = (strategy.get("platform_expansions") or {}).get(platform.lower()) or {}
    hashtags = expansions.get("hashtags") or []
    phrase_additions = expansions.get("phrase_additions") or []
    combined = list(dict.fromkeys(base_phrases + phrase_additions + hashtags))
    return combined[:max_terms]


def _get_max_terms_for_platform(strategy: dict, platform: str) -> int:
    limits = strategy.get("limits") or {}
    caps = limits.get("max_search_terms_per_platform") or {}
    return caps.get(platform.lower(), 30)


def _reddit_subreddits(strategy: dict) -> list[str]:
    """Merge subreddits from active groups, dedupe, cap."""
    limits = strategy.get("limits") or {}
    max_subs = limits.get("max_subreddits", 12)
    groups = strategy.get("reddit_active_groups") or ["entrepreneurship", "indie"]
    sources = strategy.get("reddit_sources") or {}
    out: list[str] = []
    for g in groups:
        subs = sources.get(g)
        if isinstance(subs, list):
            out.extend(subs)
    seen: set[str] = set()
    deduped: list[str] = []
    for s in out:
        key = str(s).strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            deduped.append(key)
    return deduped[:max_subs]


# Chunk size for keyword rotation: each run uses a different slice so we get different posts across runs.
KEYWORD_ROTATION_CHUNK = 12


def build_search_inputs_for_platform(
    platform: str,
    strategy: dict | None = None,
    announcement_ratio: float | None = None,
    keyword_offset: int | None = None,
) -> dict[str, Any]:
    """
    Build the search part of run_input for one platform (keywords, subreddits for reddit).
    If strategy has keywords_source (e.g. keywords_map.yaml), use keywords_map for themes + platform_keywords.
    If keyword_offset is set, rotate the keyword list so this run uses a different slice (reduces duplicate posts across runs).
    Returns dict with keys: keywords (list), and for reddit: subreddits, sortBy, timeFilter. May include _total_keywords for rotation.
    """
    strategy = strategy or _load_search_strategy()
    if not strategy:
        return {}
    limits = strategy.get("limits") or {}
    ratio = announcement_ratio if announcement_ratio is not None else limits.get("announcement_term_ratio", 0.8)
    max_terms = _get_max_terms_for_platform(strategy, platform)

    keywords_source = strategy.get("keywords_source")
    physical_first = [p.lower().strip() for p in (strategy.get("physical_first_platforms") or []) if p]
    use_physical_first = platform.lower() in physical_first

    if keywords_source or (CONFIG_DIR / KEYWORDS_MAP_FILENAME).exists():
        keywords_map_path = CONFIG_DIR / keywords_source if isinstance(keywords_source, str) else CONFIG_DIR / KEYWORDS_MAP_FILENAME
        keywords_map = _load_keywords_map(keywords_map_path)
        if keywords_map:
            if use_physical_first:
                base_phrases = _collect_physical_opening_phrases(keywords_map, max_total=max_terms)
            else:
                base_phrases = _collect_theme_phrases_from_map(keywords_map, announcement_ratio=ratio, max_total=max_terms)
            keywords = _platform_terms_from_map(keywords_map, strategy, platform, base_phrases)
        else:
            base_phrases = _collect_theme_phrases(strategy, announcement_ratio=ratio, max_total=max_terms)
            keywords = _platform_terms(strategy, platform, base_phrases)
    else:
        base_phrases = _collect_theme_phrases(strategy, announcement_ratio=ratio, max_total=max_terms)
        keywords = _platform_terms(strategy, platform, base_phrases)

    # Rotate keywords by offset so each run uses a different subset (different posts per batch).
    total_keywords = len(keywords)
    if keyword_offset is not None and total_keywords > 0:
        offset = keyword_offset % total_keywords
        keywords = (keywords[offset:] + keywords[:offset])[:max_terms]
        result = {"keywords": keywords, "_total_keywords": total_keywords}
    else:
        result = {"keywords": keywords}
    if platform.lower() == "reddit":
        result["subreddits"] = _reddit_subreddits(strategy)
        result["sortBy"] = limits.get("reddit_sort", "new")
        result["timeFilter"] = limits.get("reddit_time_filter", "week")
    return result


def build_run_input(
    platform: str,
    base_input: dict[str, Any],
    strategy: dict | None = None,
    merge_keywords: bool = True,
    keyword_offset: int | None = None,
) -> dict[str, Any]:
    """
    Merge search strategy output into actor base_input (from phase1_sources).
    If merge_keywords=True, replace base_input keywords/subreddits with strategy-built ones.
    keyword_offset rotates which keywords are used this run (different posts per run).
    """
    strategy = strategy or _load_search_strategy()
    out = dict(base_input)
    if not strategy:
        return out
    search = build_search_inputs_for_platform(platform, strategy=strategy, keyword_offset=keyword_offset)
    if merge_keywords and search:
        if search.get("keywords"):
            out["keywords"] = search["keywords"]
        if search.get("_total_keywords") is not None:
            out["_total_keywords"] = search["_total_keywords"]
        if platform.lower() == "reddit":
            if search.get("subreddits"):
                out["subreddits"] = search["subreddits"]
            if search.get("sortBy") is not None:
                out["sortBy"] = search["sortBy"]
            if search.get("timeFilter") is not None:
                out["timeFilter"] = search["timeFilter"]
    return out

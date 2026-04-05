# Keywords map — where the search magic lives

The **keywords map** (`keywords_map.yaml`) is the single source of search phrases and hashtags we send to all 5 platforms. **v2.0 is ~10x expanded**: 700+ theme phrases (announcement + international + need_developer) plus platform-specific terms. It remains **efficient** (priority order: core → extended → long_tail; builder fills platform cap from this pool) and **quality-preserving** (every entry is a meaningful phrase that signals real intent; no single words or vague terms).

## Quality rule (do not break)

- **Phrases only** — no single words. e.g. use "new cafe", "opened our cafe", "cafe opening", not "cafe" alone. Use "new law firm", "law firm opening", not "law firm" alone.
- **Related and meaningful** — every phrase should be something people actually say when announcing a new business/opening or when looking for a developer. Adding keywords must not dilute post quality.
- **Intent-aligned** — announcement phrases → real openings/launches; need_developer phrases → real hire/build intent.

## How it’s used

1. **search_strategy.yaml** sets `keywords_source: keywords_map.yaml` (or the pipeline auto-uses the map if the file exists).
2. **search_builder** loads the map and:
   - Builds the **base phrase list** from **themes** in priority order: `announcement_launch` (core → extended → long_tail) + `international_launch`, then `need_developer` (core → extended).
   - Applies **announcement_ratio** (e.g. 0.8) so ~80% of slots are launch/opening phrases, ~20% “need developer”.
   - Adds **platform_keywords** for the current platform (hashtags only where they work: Twitter, Instagram; phrases for all five).
   - Caps the final list per platform using **limits.max_search_terms_per_platform** in search_strategy.yaml.

So the “magic” is: one map, one place to add or tune phrases; priority order (core first) so we don’t waste slots on weak terms; and platform-specific additions so each channel gets the right mix.

## Structure of keywords_map.yaml

- **themes**  
  - **announcement_launch**:  
    - **core**: universal opening/launch phrases (just launched, grand opening, now open, new business, we opened, etc.).  
    - **extended**: firms & practice (new law firm, opened our practice, law firm opening, …), retail/food/venue (new cafe, restaurant opening, opened our cafe, …), service & local (opened our doors, come see us, first week in business, …). All full phrases.  
    - **long_tail**: conversational and event-style (ribbon cutting, grand opening event, celebrating our opening, …).  
  - **international_launch**: `seed_phrases` — same intent in Spanish, Portuguese, French, German, Dutch, Italian, Turkish, Indonesian, etc.  
  - **need_developer**: `core` and `extended` — explicit “looking for developer”, “need website built”, “need agency”, etc. No single words like “developer” alone.

- **platform_keywords** (additions per platform; merged after themes, then capped)  
  - **linkedin**: phrase_additions (no hashtags).  
  - **twitter**: hashtags + phrase_additions.  
  - **instagram**: hashtags + phrase_additions.  
  - **facebook**: phrase_additions.  
  - **reddit**: phrase_additions.

Order of use: theme phrases (by ratio) first, then platform additions, then cap. Duplicates are removed.

## Editing the map

- **Add a phrase only if it’s meaningful**: Use full phrases that signal real announcement or hire intent (e.g. "opened our cafe", "new law firm", "need website built"). Do not add single words or vague terms that would pull low-quality or off-topic posts.
- **Where to put it**: Highest-signal in `core`; business-type and variants in `extended`; conversational in `long_tail`. Platform-only phrases in `platform_keywords.<platform>`.
- **Prioritize**: Core is used first when filling the platform cap; extended and long_tail fill the rest. Keep core tight and high-quality.
- **No single words**: e.g. not "cafe" or "law firm" alone — use "new cafe", "cafe opening", "new law firm", "law firm opening".
- **No duplicates**: One place per phrase; the builder dedupes when merging.

## Limits (search_strategy.yaml)

- **limits.max_search_terms_per_platform**: linkedin 35, twitter 40, instagram 40, facebook 35, reddit 40.  
- **limits.announcement_term_ratio**: 0.8 (80% launch/opening, 20% need-developer).  

Increasing max terms per platform sends more queries per run; decreasing keeps runs smaller. The map stays one place; limits control how much of it we use per platform.

## Summary

| File | Role |
|------|------|
| **keywords_map.yaml** | All search phrases and hashtags by theme and platform; priority order (core → extended → long_tail). |
| **search_strategy.yaml** | `keywords_source`, limits (caps, ratio), Reddit subreddits, sort/time. |
| **search_builder.py** | Loads map (when configured), builds keyword list per platform, applies ratio and cap. |

The keywords map is where you grow and refine the search set; the strategy file controls how much of it we use and where (which platforms and Reddit subs).

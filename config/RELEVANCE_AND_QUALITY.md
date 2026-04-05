# How We Ensure Every Post Is a Real Lead

We use **four layers** so that no off-topic or useless post becomes a lead. Only posts that pass all layers are qualified.

---

## Layer 1: Search (what we fetch)

- **config/search_strategy.yaml** — We search for specific phrases and hashtags: announcement-style (“just launched”, “grand opening”, “new business”, “we opened”) and explicit need (“looking for developer”).
- **config/phase1_sources.yaml** — Actor limits and fallback keywords. Reddit subreddits are curated (startups, Entrepreneur, smallbusiness, SideProject, etc.).
- Result: We don’t scrape random feeds; we only request content that matches lead-oriented queries.

---

## Layer 2: Relevance at ingest (first filter)

As soon as a post is fetched, we score it and can **reject before storing as lead**.

- **Negative gate (config/filters.yaml)**  
  If the post text contains any **negative pattern**, it is rejected and not treated as a lead:
  - **learning**: “learning to”, “beginner tutorial”, “bootcamp”, “certification”
  - **hobby**: “side project”, “for fun”, “personal portfolio”, “practicing”
  - **job_seeking**: “hire me”, “my resume”, “looking for work”
  - **open_source**: “open source”, “volunteer”, “no budget”, “free project”
  - **low_quality**: “[deleted]”, “[removed]”, “test post”
  - **off_topic**: “unpopular opinion”, “change my view”, “meme”, “viral”, “thoughts?”, “hot take”, “does anyone else”
  - **news_style**: “according to”, “study shows”, “breaking:”, “reuters”
  - **rant_vent**: “rant”, “venting”, “so frustrated”, “complaint”
  - **promo_spam**: “use my code”, “affiliate link”, “dm for price”
  - **not_business**: “my cat”, “video game”, “movie review”, “recipe”, “gaming”
  - **generic_job_listing**: “submit your resume”, “apply at careers@”

- **Minimum length**  
  Posts with fewer than **20 words** (configurable) are rejected so we don’t treat short, ambiguous posts as leads.

- **Intent gate (config/relevance_keywords.yaml)**  
  To pass, a post must:
  1. **Contain at least one announcement or high-intent phrase** (e.g. “just launched”, “grand opening”, “new business”, “looking for developer”, “need a developer”). No “medium only” or “soft only” passes.
  2. **Reach minimum intent points** (default 5), which effectively means at least one strong phrase or equivalent.
  - Soft-combo (e.g. only “startup” + “building”) is **disabled** so weak signals don’t pass.

- **Scoring**  
  Posts that pass get a **staticScore** (intent + quality signals + recency + platform). Only posts that pass the intent gate and negative gate get a score and are stored as candidates for the next layer.

---

## Layer 3: Static filter (before AI)

- **config/static_scoring_rules.yaml** — **minimum_threshold: 8**
- Only posts with **staticScore ≥ 8** go to the AI. Lower-scoring posts are marked static_rejected and never sent to the LLM.
- This keeps cost down and ensures only clearly relevant posts get AI classification.

---

## Layer 4: AI scoring (final gate)

- **config/prompts.yaml** — The LLM is instructed to be **strict**:
  - **is_commercial_opportunity = true** only for: (a) clear new business/opening/launch announcements, or (b) explicit need to build/hire for software.
  - **False** for: learning, hobby, job seeking, open source, off-topic, meme, news, rant, vague, “congratulations only”, or unclear. **When in doubt, false.**
- Only posts the AI marks as commercial opportunities are written to **qualified_leads** and become candidates for email.

---

## End-to-end result

| Stage              | What happens |
|--------------------|--------------|
| Fetch              | Only query for lead-oriented keywords/hashtags and curated sources. |
| Ingest + relevance | Reject negative patterns, short posts, and anything without a strong intent phrase + enough points. |
| Static filter      | Only staticScore ≥ 8 go to AI. |
| AI                 | Only posts explicitly classified as commercial opportunities become qualified leads. |

So: **every post we treat as a lead has (1) passed our search and relevance rules, (2) met the static score bar, and (3) been approved by the AI.** No post should be off-topic or useless if all four layers are enabled and configs are left at their current strict defaults.

---

## Tuning (if you need to relax or tighten)

- **Too many rejections at ingest**  
  - Loosen **config/relevance_keywords.yaml**: e.g. set `require_announcement_or_high: false` or lower `min_intent_points`.  
  - Or reduce **config/filters.yaml** `minimum_word_count` (e.g. 15).

- **Still seeing off-topic posts**  
  - Add more phrases to **config/filters.yaml** under the right negative category.  
  - Raise **config/static_scoring_rules.yaml** `minimum_threshold` (e.g. 10).  
  - Keep AI prompt as “when in doubt, false.”

- **Too few leads**  
  - Slightly lower `minimum_threshold` (e.g. 6) or `min_intent_points` (e.g. 4).  
  - Do **not** disable `require_announcement_or_high` or the negative patterns unless you are sure you want more risk of non-leads.

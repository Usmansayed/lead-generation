# Static Filter Assessment & Improvements

## Is the static filter "really good"?

**Short answer:** It is **strong on the 110-lead calibration set** (100% accuracy) and is **better than before** after the changes below. It can still be improved with more data and tuning.

### Strengths

- **Two-phase logic:** Negative gate first (reject job-seeking, hobby, news, etc.), then intent gate (announcement or high-intent phrase + enough points). Reduces noise before scoring.
- **Config-driven:** `config/filters.yaml`, `config/relevance_keywords.yaml`, and `config/static_scoring_rules.yaml` let you tune without code.
- **Context-aware exceptions:** Phrases like "our website" and "our platform" no longer reject client intent such as "create our website", "develop our platform", "our website redesign", "integrate with our API".
- **Calibration set:** 110 leads with known pass/fail; run `python scripts/calibrate_static_filter.py` to regress after changes.

### Limitations

- **Keyword-only:** No semantics. Ambiguous posts (e.g. "we need help" without "developer" or "build") may pass or fail only on phrase match.
- **Negative list is global:** One substring match anywhere rejects the post; exceptions are the only way to allow client-intent phrasing.
- **Medium-only posts:** Without a high/announcement phrase, posts need optional `allow_medium_with_min_points` (e.g. 6) in `minimum_gate` to pass; default is 0 (disabled).
- **Real-world drift:** Calibration is 110 hand-picked examples. New platforms or phrasing can create false positives/negatives until you add cases and re-run calibration.

---

## Improvements made

### 1. Negative phrase order (longest first)

- **Where:** `pipeline/relevance.py` — `_flatten_negative_patterns()`.
- **What:** Negatives are sorted by length (desc) so longer phrases are tried first (e.g. "launched our website" before "our website").
- **Why:** More specific reject reasons and consistent behavior when phrases overlap.

### 2. Negative exceptions (client intent)

- **Where:** `pipeline/relevance.py` — `NEGATIVE_EXCEPTIONS` and `match_negative()`.
- **What:** When a negative phrase matches, we skip rejection if the text contains any of its exception substrings:
  - **our website:** e.g. "create our website", "build our website", "our website redesign", "redesign our website"
  - **our platform:** e.g. "develop our platform", "build our platform"
  - **our api:** e.g. "integrate with our api", "need api integration"
- **Why:** Lets us keep "our website" and "our platform" (and "our api") in the negative list to catch "we already have a site/platform" while still allowing clear client-intent posts.

### 3. Broader negative filters with exceptions

- **Where:** `config/filters.yaml`.
- **What:** Restored "our website", "our new website", "our platform", and "our api" in the negative lists, relying on the exception logic above so client-intent examples still pass.
- **Why:** Fewer false negatives (e.g. "create our website") while still rejecting "we have our website" / "our platform is live" type posts.

### 4. Optional medium-only gate

- **Where:** `config/relevance_keywords.yaml` — `minimum_gate.allow_medium_with_min_points`; `pipeline/relevance.py` — `passes_intent_gate()`.
- **What:** If `allow_medium_with_min_points` is set (e.g. 6), posts with only medium_intent phrases can pass when `intent_points >= min_intent_points` and `>= allow_medium_with_min_points`. Default is 0 (off).
- **Why:** Reduces false negatives for strong medium-only posts (e.g. "we need", "budget", "recommendations", "deadline") when you’re willing to send more to AI.

---

## How to keep improving

1. **Add calibration leads:** Add real or synthetic examples to `tests/fixtures/calibration_leads.json` with `expected_should_pass` and run `python scripts/calibrate_static_filter.py`.
2. **Tune threshold:** In `config/static_scoring_rules.yaml`, `minimum_threshold: 4` balances volume vs cost; raise to 5–6 to send fewer leads to Bedrock.
3. **Enable medium-only pass:** In `config/relevance_keywords.yaml`, set `allow_medium_with_min_points: 6` (or 7) if you want strong medium-only posts to pass; watch for new false positives and add to calibration.
4. **Add exception phrases:** If a good lead is rejected by "our website" or "our platform", add a safe substring to `NEGATIVE_EXCEPTIONS` in `pipeline/relevance.py` (e.g. "rebuild our website").
5. **Add negative phrases:** When you see recurring noise (e.g. a new job-seeking or off-topic pattern), add it to the right category in `config/filters.yaml` and re-run calibration.

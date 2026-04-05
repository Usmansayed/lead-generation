# FB/IG Scrape Engine — 4 Test Runs Summary

Ran **4 autonomous test cycles**: ingest (Instagram + Facebook) → analyze → improvise filters/keywords → re-run.

---

## Run 1 (baseline)
- **Command:** `--ingest-only --platforms instagram facebook --export-json output/fb_ig_run1.json`
- **Inserted:** 18 leads
- **Findings:** Beta Squad (entertainment), NPK “brand-new website”, ECI Software Solutions, Crumb Studio “new website”, product launches, Cannon Coffee rejected for “weekend”, Mayor post rejected for “rant” (false positive: “restaurant” contains “rant”).

---

## Improvisations (Run 2)

**Filters (`config/filters.yaml`):**
1. **Hobby:** Replaced single word `weekend` with `weekend project`, `weekend warrior` so “grand opening this weekend” is not rejected.
2. **Relevance (`pipeline/relevance.py`):** Single-word negative patterns now use **word boundary** so `rant` no longer matches inside `restaurant`.
3. **already_has_website:** Added `brand new website`, `our new website`, `just launched our new website`, `website is now live`, `website is live`.
4. **Entertainment:** New category `entertainment_content`: `beta squad`, `betasquad`, ` out now!`, etc.
5. **Gaming:** New category `gaming_server`: `join the server`, `java ip:`, `bedrock ip:`, `log into the server`, `minecraft`.

**Run 2 result:** 10 inserted. Beta Squad posts now **rejected** (rejectReason: "beta squad"). Quality improved.

---

## Improvisations (Run 3)

**Filters:**
1. **product_launch:** New category for e-commerce/product launches: `just launched our new product`, `just launched our new collection`, `just launched our new line`, `our new product launch`, `just launched our new spray`, `just launched our new range`.
2. **promo_spam:** Added `use code `, `use code!`.

**Run 3 result:** 17 inserted. Same pipeline; filters applied to new items.

---

## Improvisations (Run 4)

**Filters:**
1. **already_has_website:** Added `launched the official`, `official website`, `official site` (to catch “We just launched the official Metro Scott's website” style posts).

**Run 4 result:** 0 inserted — DuckDuckGo returned 0 results for all IG/FB queries (likely rate limit or search variance), not a config regression.

---

## Summary of All Engine Changes

| Area | Change |
|------|--------|
| **Negative filters** | `already_has_website` (expanded), `is_software_or_product`, `entertainment_content` (Beta Squad, “out now”), `gaming_server`, `product_launch`, `promo_spam` (+ use code). |
| **Hobby** | “weekend” → “weekend project” / “weekend warrior” to avoid blocking “grand opening this weekend”. |
| **Relevance** | Single-word negatives use word-boundary so “rant” ≠ “restaurant”. |
| **Search (IG/FB)** | Already using `physical_opening_first` theme only (grand opening, now open, opened our doors, etc.) — no “just launched” in main mix. |

---

## Exports

- `output/fb_ig_run1.json` — Run 1
- `output/fb_ig_run2.json` — Run 2 (Beta Squad rejected)
- `output/fb_ig_run3.json` — Run 3
- `output/fb_ig_run4.json` — Run 4 (0 new results from scraper)

To re-test:  
`python -m pipeline.run_pipeline --ingest-only --platforms instagram facebook --export-json output/fb_ig_test.json`

---

## Quality run (expected results)

**Criteria for “expected results”:**
- **Raw leads** = real business openings (physical/local/firms): grand opening, we opened, just opened, opened our doors, new restaurant/cafe/shop, ribbon cutting, new practice, etc.
- **Rejected** = already have website, software/product company, entertainment (e.g. Beta Squad), gaming, product launches.

**Latest upgrades applied:**
- **Relevance** (`config/relevance_keywords.yaml`): Added announcement phrases so more real openings pass the intent gate: `officially open`, `open our doors`, `we will open our doors`, `newly opened`, `opening fall`, `opening spring`, `opening summer`, `opening winter`, `opening 2025`, `opening in northern`, `opening in virginia`.
- **Filters** (`config/filters.yaml`): `already_has_website` + `from their website`, `from our website` (reviewer posts quoting a business’s site = that business already has a site).

**Test run results:** Beta Squad consistently rejected (rejectReason: `beta squad`). Raw leads include Metro Auto Mart, Loudoun County rec center, Improve Life PLLC, ProMD Health, Costello Construction, Cannon Coffee, Northern VA Balloons, Marc Lore Wonder, Teddy Baldassarre retail, Ocean Lilly Otte, Udayanga coffee, new tea spot/cafe/restaurant openings (reviewer posts still in raw but point to real businesses).

---

## Iteration log (keep running tests & updating the engine)

| Iter | Inserted | Notes |
|------|----------|--------|
| 1 | 18 | Baseline; Beta Squad, “website”, “weekend”, “rant” issues found. |
| 2 | 10 | Filters/relevance fixes; Beta Squad rejected. |
| 3 | 0 | DuckDuckGo returned 0 for all queries (scraper variance). |
| 4 | 0 | Same — 0 scrape results; engine unchanged. |

**How to keep the loop going:**
1. **Run:**  
   `python -m pipeline.run_pipeline --ingest-only --platforms instagram facebook --export-json output/fb_ig_latest.json`
2. **Inspect:** Open `output/fb_ig_latest.json` — check `raw` (good openings) vs `rejected` (rejectReason: already_has_website, intent_gate_failed, etc.).
3. **Update engine:**  
   - New bad pattern in `rejected` but it’s a good lead → add phrase to `config/relevance_keywords.yaml` (announcement intent) or relax a negative in `config/filters.yaml`.  
   - New bad lead in `raw` → add negative pattern to `config/filters.yaml` or extend `relevance_keywords` negatives.
4. **Re-run** and repeat.

---

## Latest Improvements (Feb 2025)

| Change | Impact |
|--------|--------|
| **Bing fallback** | When DuckDuckGo returns 0, IG/FB actors try Bing. Reduces dependency on DDG. |
| **Retry + delay** | If DDG returns 0, retry once after 2s before Bing fallback. |
| **More announcement phrases** | `opened the doors to`, `opening soon`, `now open at`, `just opened in`, `celebrate the grand opening`. |
| **Stronger website filter** | `according to their website`, `per their website`. |

**When DuckDuckGo returns 0 for every query:** That’s scraper/search variance (or rate limiting), not an engine regression. **Fix (Feb 2025):** DuckDuckGo blocks datacenter IPs. IG/FB actors now use Apify residential proxy. Redeploy actors and ensure residential proxy credits.

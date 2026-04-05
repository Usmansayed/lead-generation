# After AI filter: lead research & email (all 5 platforms)

This runs for **every** qualified lead from **any** of the 5 platforms (LinkedIn, Twitter, Instagram, Facebook, Reddit). There is no platform-specific branch; the same pipeline runs for all.

---

## Flow (Step 4) — for each qualified lead

| Step | What runs | Platform-agnostic? |
|------|-----------|--------------------|
| 1. **Full post fetch** | Fetches `lead.post_url` with your **post-content-fetcher** actor. Returns full page/post text for better personalization. | Yes – any URL (IG, FB, Reddit, Twitter, LinkedIn, etc.). |
| 2. **Business research** | Classifies: business type (cafe, restaurant, law_firm, retail, shop, salon, gym, …), size (small / medium+), has_website, suggested_offers, should_skip_email. | Yes – uses post text + full fetch text. |
| 3. **Skip logic** | If small cafe/restaurant **and** has website → skip (don’t email). Else continue. | Yes. |
| 4. **Profile enrichment** | Gets author profile URL (Reddit/Twitter/Instagram/Facebook/LinkedIn when we have handle). Fetches profile page if `PROFILE_SCRAPER_ACTOR_ID` set. | Yes – profile URL built per platform; same fetcher for all. |
| 5. **Contact discovery** | Finds email from post text or profile text. | Yes. |
| 6. **Email generation** | Hyper-personalized email using: full post text, profile, business type, **suggested_offers** (what to pitch: website, POS, booking, CRM, etc.). | Yes – prompt uses business type and offers for any platform. |
| 7. **Queue** | Adds to `email_queue` for SES. | Yes. |

---

## Do I need 5 separate actors for full fetch and profile fetch?

**No.** You need **one** actor: **post-content-fetcher**.

- It takes **any URL** (post URL or profile URL) and returns the page text.
- The pipeline uses it for:
  - **Full post fetch** – fetches the lead’s post URL (Instagram, Facebook, Reddit, Twitter, LinkedIn, etc.).
  - **Profile fetch** – fetches the lead’s profile URL (same actor, different URL).
- So one deployment covers **all 5 platforms** for both post and profile. No separate actors per platform.

You can leave `PROFILE_SCRAPER_ACTOR_ID` unset; the pipeline will use **post-content-fetcher** by name for profile enrichment too.

---

## Is everything ready?

| Piece | Status | What you need to do |
|-------|--------|----------------------|
| **Full post fetch** | Code ready | Deploy **post-content-fetcher** once. Pipeline uses it by name. |
| **Profile fetch** | Code ready | Same actor. No extra deploy; pipeline uses **post-content-fetcher** for profiles when `PROFILE_SCRAPER_ACTOR_ID` is not set. |
| **Business research** | Code ready | Nothing. Uses `config/business_offers.yaml`. |
| **Skip logic** | Code ready | Nothing. |
| **Contact discovery** | Code ready | Nothing. |
| **Email (hyper-personalized)** | Code ready | Nothing. Needs LLM (AWS2_* or CLAUDE_* for Bedrock Nova Lite). |
| **All 5 platforms** | Same flow | One actor for post + profile for LinkedIn, Twitter, Instagram, Facebook, Reddit. |

---

## Summary

- **One actor**: **post-content-fetcher** – used for full post fetch and profile fetch for all 5 platforms.
- **Deploy once**: `python deploy_and_test.py post-content-fetcher` or `apify push` from `services/apify-actors/post-content-fetcher`.
- No need for 5 different actors or a separate profile fetcher.

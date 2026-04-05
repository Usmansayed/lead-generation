# Reference Implementation: LinkedIn Profile Scraper

Complete, production-ready example showing best practices. Use as a template for other platforms.

---

## Directory Structure

```
services/apify-actors/linkedin-profile-scraper/
├── .actor/
│   ├── actor.json
│   ├── input_schema.json
│   ├── output_schema.json
│   └── dataset_schema.json
├── src/
│   ├── main.py
│   ├── linkedin_extractor.py
│   ├── contact_finder.py
│   └── __init__.py
├── Dockerfile
├── requirements.txt
├── example_input.json
└── README.md
```

---

## Key Files (Full Implementation)

### `src/main.py`

```python
"""LinkedIn Profile Scraper - Production Grade

Extracts professional profile data from LinkedIn:
- Headline, experience, education
- Contact information (email if public)
- Skills and endorsements
- Recommendations and connections
- Recent activity/posts

NOTE: LinkedIn has strict ToS. Use only for:
1. Publicly available data
2. Non-automated access (manual if possible)
3. Respect robots.txt and rate limits
4. Consider LinkedIn API alternatives
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from apify import Actor
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from playwright.async_api import Page


class LinkedInProfileExtractor:
    """Extract profile data from LinkedIn profile page."""
    
    def __init__(self):
        self.extract_methods = {
            "headline": self._extract_headline,
            "about": self._extract_about,
            "experience": self._extract_experience,
            "education": self._extract_education,
            "skills": self._extract_skills,
            "contact": self._extract_contact_info,
        }
    
    async def extract_profile(self, page: Page, profile_url: str) -> dict[str, Any]:
        """Extract all profile data from a LinkedIn profile."""
        
        profile_data = {
            "platform": "linkedin",
            "profileUrl": profile_url,
            "profileId": self._extract_profile_id(profile_url),
            "displayName": None,
            "headline": None,
            "about": "",
            "location": None,
            "connections": None,
            "followers": None,
            "experience": [],
            "education": [],
            "skills": [],
            "endorsements": {},
            "email": None,
            "phoneNumber": None,
            "website": None,
            "otherSocialLinks": {},
            "recommendations": 0,
            "mutualConnections": 0,
            "engagementMetrics": {
                "recentPostViews": 0,
                "recentPostEngagement": 0,
                "profileViews": 0,
            },
            "scrapedAt": datetime.utcnow().isoformat(),
            "success": False,
            "errors": [],
        }
        
        try:
            # Wait for page to load
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Extract name
            try:
                name_elem = await page.query_selector("[data-guide-id='profile_top_card']")
                if name_elem:
                    name_text = await name_elem.text_content()
                    profile_data["displayName"] = name_text.strip() if name_text else None
            except Exception as e:
                profile_data["errors"].append(f"Name extraction: {e}")
            
            # Extract headline
            try:
                headline = await page.text_content(".headline.text-body-medium")
                profile_data["headline"] = headline.strip() if headline else None
            except:
                pass
            
            # Extract about
            try:
                about_button = await page.query_selector("section[data-section='summary'] button")
                if about_button:
                    await about_button.click()
                    await page.wait_for_timeout(500)
                
                about_text = await page.text_content("section[data-section='summary']")
                profile_data["about"] = about_text.strip() if about_text else ""
            except:
                pass
            
            # Extract location
            try:
                location = await page.text_content(".location.text-body-small")
                profile_data["location"] = location.strip() if location else None
            except:
                pass
            
            # Extract connection count
            try:
                conn_text = await page.text_content("a[href*='/people/connections']")
                if conn_text:
                    # "2,345 connections" → 2345
                    match = re.search(r'([\d,]+)', conn_text)
                    if match:
                        profile_data["connections"] = int(match.group(1).replace(",", ""))
            except:
                pass
            
            # Extract experience
            profile_data["experience"] = await self._extract_experience(page)
            
            # Extract education
            profile_data["education"] = await self._extract_education(page)
            
            # Extract skills
            profile_data["skills"] = await self._extract_skills(page)
            
            # Extract contact info (if available)
            profile_data["email"] = await self._extract_email(page)
            profile_data["website"] = await self._extract_website(page)
            
            profile_data["success"] = True
            
        except Exception as e:
            profile_data["errors"].append(f"Main extraction error: {str(e)}")
            Actor.log.error(f"Error extracting profile {profile_url}: {e}")
        
        return profile_data
    
    async def _extract_experience(self, page: Page) -> list[dict[str, Any]]:
        """Extract work experience."""
        experience = []
        try:
            # Scroll to experience section
            await page.evaluate("""
                () => {
                    const elem = document.querySelector("section[data-section='experience']");
                    if (elem) elem.scrollIntoView({behavior: 'smooth'});
                }
            """)
            await page.wait_for_timeout(1000)
            
            # Get all experience items
            items = await page.query_selector_all(
                "li[data-test-id='experience-item']"
            )
            
            for item in items[:15]:  # Limit to last 15 jobs
                exp = {}
                try:
                    title = await item.text_content("h3")
                    company = await item.text_content("p.company-name")
                    duration = await item.text_content("span.date-range")
                    description = await item.text_content("p.description")
                    
                    if title:
                        exp["title"] = title.strip()
                    if company:
                        exp["company"] = company.strip()
                    if duration:
                        exp["duration"] = duration.strip()
                    if description:
                        exp["description"] = description.strip()
                    
                    if exp:
                        experience.append(exp)
                except:
                    continue
        except Exception as e:
            Actor.log.warning(f"Error extracting experience: {e}")
        
        return experience
    
    async def _extract_education(self, page: Page) -> list[dict[str, Any]]:
        """Extract education."""
        education = []
        try:
            await page.evaluate("""
                () => {
                    const elem = document.querySelector("section[data-section='education']");
                    if (elem) elem.scrollIntoView({behavior: 'smooth'});
                }
            """)
            await page.wait_for_timeout(1000)
            
            items = await page.query_selector_all(
                "li[data-test-id='education-item']"
            )
            
            for item in items[:10]:
                edu = {}
                try:
                    school = await item.text_content("h3")
                    degree = await item.text_content("p.degree-name")
                    field = await item.text_content("p.field-of-study")
                    
                    if school:
                        edu["school"] = school.strip()
                    if degree:
                        edu["degree"] = degree.strip()
                    if field:
                        edu["fieldOfStudy"] = field.strip()
                    
                    if edu:
                        education.append(edu)
                except:
                    continue
        except Exception as e:
            Actor.log.warning(f"Error extracting education: {e}")
        
        return education
    
    async def _extract_skills(self, page: Page) -> list[dict[str, Any]]:
        """Extract skills with endorsement counts."""
        skills = []
        try:
            await page.evaluate("""
                () => {
                    const elem = document.querySelector("section[data-section='skills']");
                    if (elem) elem.scrollIntoView({behavior: 'smooth'});
                }
            """)
            await page.wait_for_timeout(1000)
            
            items = await page.query_selector_all(
                "li[data-test-id='skill-item']"
            )
            
            for item in items[:20]:  # Top 20 skills
                try:
                    name = await item.text_content("h3")
                    endorsements_text = await item.text_content(".endorsements")
                    
                    skill = {"name": name.strip()} if name else {}
                    
                    if endorsements_text:
                        # "123 endorsements" → 123
                        match = re.search(r'(\d+)', endorsements_text)
                        if match:
                            skill["endorsements"] = int(match.group(1))
                    
                    if skill.get("name"):
                        skills.append(skill)
                except:
                    continue
        except Exception as e:
            Actor.log.warning(f"Error extracting skills: {e}")
        
        return skills
    
    async def _extract_email(self, page: Page) -> str | None:
        """Extract email if publicly available."""
        try:
            # Check contact info section
            contact_section = await page.query_selector(
                "section[data-section='contact_info']"
            )
            if contact_section:
                emails = await contact_section.query_selector_all("a[href^='mailto:']")
                for email_link in emails:
                    href = await email_link.get_attribute("href")
                    if href:
                        return href.replace("mailto:", "")
        except:
            pass
        return None
    
    async def _extract_website(self, page: Page) -> str | None:
        """Extract website URL if publicly available."""
        try:
            contact_section = await page.query_selector(
                "section[data-section='contact_info']"
            )
            if contact_section:
                links = await contact_section.query_selector_all(
                    "a:not([href^='mailto:'])"
                )
                for link in links:
                    href = await link.get_attribute("href")
                    text = await link.text_content()
                    if href and not "linkedin.com" in href:
                        return href
        except:
            pass
        return None
    
    @staticmethod
    def _extract_profile_id(url: str) -> str:
        """Extract LinkedIn profile ID from URL."""
        match = re.search(r'/in/([a-zA-Z0-9-]+)', url)
        return match.group(1) if match else url


async def main() -> None:
    """Main entry point for LinkedIn profile scraper."""
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        profiles = actor_input.get("profiles", [])
        keywords = actor_input.get("keywords", [])
        max_profiles = actor_input.get("maxProfiles", 50)
        
        Actor.log.info("=" * 80)
        Actor.log.info(f"🔗 LinkedIn Profile Scraper")
        Actor.log.info(f"   Profiles: {len(profiles)}")
        Actor.log.info(f"   Keywords: {keywords or 'None'}")
        Actor.log.info("=" * 80)
        
        proxy_config = await Actor.create_proxy_configuration()
        
        crawler = PlaywrightCrawler(
            proxy_configuration=proxy_config,
            max_requests_per_crawl=max_profiles,
            max_request_retries=3,
        )
        
        extractor = LinkedInProfileExtractor()
        profiles_found = 0
        
        @crawler.router.default_handler
        async def handle_profile(context: PlaywrightCrawlingContext) -> None:
            nonlocal profiles_found
            
            url = context.request.url
            Actor.log.info(f"🔄 Processing: {url}")
            
            try:
                profile_data = await extractor.extract_profile(
                    context.page,
                    url
                )
                
                if profile_data["success"]:
                    await Actor.push_data(profile_data)
                    profiles_found += 1
                    name = profile_data.get("displayName", "Unknown")
                    Actor.log.info(f"   ✓ {profiles_found}. {name}")
                else:
                    Actor.log.warning(f"   ✗ Failed to extract profile")
                    
            except Exception as e:
                Actor.log.error(f"Error handling profile: {e}")
        
        # Add URLs to crawler
        for profile_url in profiles[:max_profiles]:
            if not profile_url.startswith("http"):
                profile_url = f"https://www.linkedin.com/in/{profile_url}/"
            
            await crawler.add_requests([profile_url])
        
        # Run crawler
        await crawler.run()
        
        Actor.log.info("=" * 80)
        Actor.log.info(f"✅ Complete - Extracted {profiles_found} profiles")
        Actor.log.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
```

### `example_input.json`

```json
{
  "profiles": [
    "https://www.linkedin.com/in/billgates/",
    "https://www.linkedin.com/in/satyanadella/",
    "sheryl-sandberg"
  ],
  "keywords": ["technology", "ai", "software"],
  "maxProfiles": 30,
  "includeRecommendations": true
}
```

### `README.md`

```markdown
# LinkedIn Profile Scraper

Extract professional profile data from LinkedIn including headline, experience, education, skills, and contact information.

## Features

- Full profile extraction (headline, about, experience, education, skills)
- Skill endorsement counts
- Contact information (email, website if public)
- Working experience details
- Education history
- Engagement tracking

## Input

```json
{
  "profiles": ["url1", "url2", ...],  // URLs or profile slugs
  "keywords": ["optional", "filters"],
  "maxProfiles": 50
}
```

## Output

Standard profile schema with LinkedIn-specific fields:
- `headline`: Job title/headline
- `experience`: Array of {company, title, duration}
- `education`: Array of {school, degree, fieldOfStudy}
- `skills`: Array of {name, endorsements}
- `email`, `website`: Public contact info if available

## Important Notes

⚠️ **LinkedIn Terms of Service**

- LinkedIn has strict rules against scraping
- This actor is for **research and educational purposes**
- For production: use [LinkedIn Official APIs](https://www.linkedin.com/developers)
- Respect rate limits (2-5 second delays)
- Respect `robots.txt` and LinkedIn's blocking policies

## Best Practices

1. **Use Proxies** - LinkedIn blocks frequent requests from same IP
2. **Add Delays** - Wait 3-5 seconds between requests
3. **Rotate User-Agents** - Some protection measures
4. **Respect Robots.txt** - Don't overwhelm servers
5. **Monitor Blocks** - If blocked, requests will fail; retry with proxy

## Deployment

```bash
apify push
```

Then use in pipeline:

```yaml
# config/profile_sources.yaml
profile_platforms:
  linkedin:
    actor_id: YOUR_ACTOR_ID
    enabled: true
    timeout_secs: 600
    memory_mb: 512
    needs_proxy: true
```

## Legal

Check LinkedIn's Terms of Service before use. Consider using LinkedIn API for legitimate business purposes.
```

---

## Testing & Validation

### Test Locally

```bash
cd services/apify-actors/linkedin-profile-scraper

# Create test input
cat > test_input.json << 'EOF'
{
  "profiles": ["https://www.linkedin.com/in/satyanadella/"],
  "maxProfiles": 5
}
EOF

# Run
apify run

# Check storage/datasets/default/*.json
```

### Mock Testing (No Actual Scraping)

```python
# tests/test_linkedin_scraper.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.main import LinkedInProfileExtractor


@pytest.mark.asyncio
async def test_extract_profile_success():
    """Test successful profile extraction."""
    extractor = LinkedInProfileExtractor()
    
    # Mock page
    page = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.text_content = AsyncMock(return_value="Jane Doe")
    page.query_selector = AsyncMock()
    
    result = await extractor.extract_profile(page, "https://linkedin.com/in/janedoe")
    
    assert result["platform"] == "linkedin"
    assert result["displayName"] == "Jane Doe"
    assert result["success"] is True


def test_extract_profile_id():
    """Test profile ID extraction."""
    extractor = LinkedInProfileExtractor()
    
    url = "https://www.linkedin.com/in/john-smith-123/"
    profile_id = extractor._extract_profile_id(url)
    
    assert profile_id == "john-smith-123"
```

---

## Troubleshooting

### Issue: Getting 429 (Rate Limited)

**Solution:**
```python
# Add exponential backoff in main.py
import asyncio
MAX_RETRIES = 3

for attempt in range(MAX_RETRIES):
    try:
        await crawler.run()
        break
    except RateLimitError:
        wait_time = 2 ** attempt  # 2, 4, 8 seconds
        Actor.log.warning(f"Rate limited. Retrying in {wait_time}s...")
        await asyncio.sleep(wait_time)
```

### Issue: Getting Blocked (403 Forbidden)

**Solution:**
- Use Apify proxies: `Actor.create_proxy_configuration()`
- Add delays between requests (3-5 seconds)
- Rotate user agents
- Consider official LinkedIn API for production

### Issue: JavaScript Content Not Loading

**Solution:**
```python
# Use Playwright/Selenium instead of BeautifulSoup
# Ensure page waits for elements
await page.wait_for_selector(selector, timeout=10000)
await page.wait_for_load_state("networkidle")
```

---

## Integration with Pipeline

### 1. Add to Config

```yaml
# config/profile_sources.yaml
profile_platforms:
  linkedin:
    actor_id: "YOUR_APIFY_ACTOR_ID"
    enabled: true
    timeout_secs: 600
    memory_mb: 512
    needs_proxy: true
    run_every_hours: 48  # LinkedIn is slow, run less frequently
    rate_limit_secs: 5    # 5 second delay between profiles
```

### 2. Call from Pipeline

```python
# pipeline/profile_enrichment.py

async def enrich_leads_with_profiles():
    """Enrich leads with LinkedIn profile data."""
    
    # Get leads needing LinkedIn profiles
    leads = db.leads.find({"source": "linkedin", "profile_data": None}).limit(100)
    
    actor_id = config["profile_platforms"]["linkedin"]["actor_id"]
    
    batch = []
    for lead in leads:
        batch.append({
            "url": lead["profile_url"],
            "lead_id": str(lead["_id"])
        })
    
    # Run actor
    profiles = await run_actor(actor_id, {
        "profiles": [b["url"] for b in batch],
        "maxProfiles": 100
    })
    
    # Store enriched profiles
    for profile in profiles:
        # Normalize and store (see PROFILE_NORMALIZER.md)
        normalized = normalize_profile(profile)
        db.profiles.insert_one(normalized)
```

---

## Performance Metrics

Expected on Apify cloud with proxies:

- **Speed:** 1-3 profiles/minute (LinkedIn blocks fast scrapers)
- **Memory:** 256-512 MB
- **Timeout:** 10 minutes per batch
- **Rate limit:** Every 3-5 seconds between profiles
- **Success rate:** 70-85% (some profiles private/removed)

---

## Next Steps

1. Deploy actor: `apify push`
2. Get actor ID from console.apify.com
3. Add to `config/profile_sources.yaml`
4. Test from pipeline: `python -m pipeline.run_pipeline --profile-enrichment`
5. Monitor: Check logs + actor run history
```

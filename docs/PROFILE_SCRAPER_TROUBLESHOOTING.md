# Common Issues & Troubleshooting Guide

Solve the most common problems when building profile scrapers with Apify.

---

## Problem 1: Actor Won't Run Locally

### Error: `apify run` hangs or crashes

**Symptoms:**
```
📡 Starting actor
[no output for 30+ seconds]
Error: ENOENT - Cannot find apify package
```

**Solutions:**

1. **Check Python installation:**
```bash
python --version  # Should be 3.9+
pip list | grep apify  # Should see apify 2.0+
```

2. **Reinstall dependencies:**
```bash
cd services/apify-actors/youtube-profile-scraper
rm -rf venv
python -m venv venv
source venv/Scripts/activate  # Windows
pip install -r requirements.txt
```

3. **Check storage directory:**
```bash
# Storage must exist
mkdir -p storage/datasets
mkdir -p storage/key_value_stores
apify run
```

4. **Check main.py syntax:**
```bash
python -m py_compile src/main.py
```

---

## Problem 2: Scraper Returns Empty Results

### Error: Found 0 profiles; all skipped

**Symptoms:**
```
🚀 Starting scraper
📡 Processing: https://www.youtube.com/@TechCrunch
✓ 0 profiles found
```

**Root Causes & Solutions:**

#### Issue A: Page didn't load (JavaScript)
```python
# ❌ Wrong - BeautifulSoup can't handle JS
from bs4 import BeautifulSoup
html = requests.get(url).text
soup = BeautifulSoup(html)  # Won't work for YouTube/Instagram

# ✅ Correct - Use Playwright/Selenium
from playwright.async_api import async_playwright
async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    await page.goto(url, wait_until="networkidle")
    content = await page.content()
```

#### Issue B: Wrong selectors
```python
# Debug: Print page HTML
async def debug_page(page):
    content = await page.content()
    with open(f"debug_{platform}.html", "w") as f:
        f.write(content)
    actor.log.info(f"Dumped HTML to debug_{platform}.html")

# Then inspect the file in browser
# Platforms change DOM structure - selectors may be outdated
```

#### Issue C: Keyword filter too strict
```python
# ❌ Wrong
if not all(kw.lower() in bio for kw in keywords):
    skip()  # Skips if ANY keyword missing

# ✅ Correct
if not any(kw.lower() in bio for kw in keywords):
    skip()  # Skips only if NO keywords found
```

#### Issue D: Rate limiting kicked in
```python
# Add randomized delays
import time
import random

for profile in profiles:
    fetch_profile(profile)
    delay = random.uniform(2, 5)  # 2-5 seconds
    time.sleep(delay)
```

---

## Problem 3: Authentication / Login Required

### Error: Page redirects to login; data not accessible

**Typical Platforms:** LinkedIn, Facebook, TikTok, some private YouTube features

**Solutions:**

#### Option 1: Use cookies (LinkedIn, Facebook)
```python
from playwright.async_api import async_playwright

async def login_with_cookies():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        # Load saved cookies
        cookies = [
            {"name": "li_at", "value": "YOUR_COOKIE_VALUE", "domain": ".linkedin.com", "path": "/"},
        ]
        await context.add_cookies(cookies)
        
        # Now access protected pages
        await page.goto("https://www.linkedin.com/in/profile/")
```

#### Option 2: Use official API
```python
# For LinkedIn - use official API instead
import requests

headers = {
    "Authorization": f"Bearer {LINKEDIN_API_TOKEN}"
}

response = requests.get(
    "https://api.linkedin.com/v2/me",
    headers=headers
)
```

#### Option 3: Skip private platforms initially
```yaml
# config/profile_sources.yaml
profile_platforms:
  linkedin:
    enabled: false  # Disable for now
  facebook:
    enabled: false  # Come back later
  youtube:
    enabled: true   # Start with public platforms
```

---

## Problem 4: Getting Blocked / Rate Limited

### Error: 403 Forbidden, 429 Too Many Requests

**Solutions:**

#### Add Apify Proxies
```python
from apify import Actor

proxy_config = await Actor.create_proxy_configuration()

crawler = BeautifulSoupCrawler(
    proxy_configuration=proxy_config,
    max_session_rotations=15,  # Rotate IPs frequently
)
```

#### Add Delays & Backoff
```python
import asyncio
import random

async def scrape_with_backoff(profiles: list[str]):
    for i, profile in enumerate(profiles):
        try:
            await scrape(profile)
            
            # Random delay (3-8 seconds)
            delay = random.uniform(3, 8)
            print(f"Waiting {delay:.1f}s before next profile...")
            await asyncio.sleep(delay)
            
        except RateLimitError as e:
            # Exponential backoff on 429
            wait = 2 ** min(5, i // 10)  # 2s, 4s, 8s, 16s, 32s max
            print(f"Rate limited! Waiting {wait}s...")
            await asyncio.sleep(wait)
```

#### Check robots.txt
```python
import requests
from urllib.robotparser import RobotFileParser

def check_allowed(url: str) -> bool:
    rp = RobotFileParser()
    rp.set_url(f"{url}/robots.txt")
    rp.read()
    return rp.can_fetch("*", url)
```

#### Use Different Proxies
```python
# .env
APIFY_PROXY_URLS=["http://proxy1:8080", "http://proxy2:8080"]

# main.py
proxy_urls = os.getenv("APIFY_PROXY_URLS", "").split(",")
proxy_config = await Actor.create_proxy_configuration(
    proxy_urls=proxy_urls if proxy_urls else None
)
```

---

## Problem 5: Data Normalization Errors

### Error: Inconsistent data types across runs

**Problem:**
```python
# Run 1: followerCount = 1000  (int) ✓
# Run 2: followerCount = "1.2K"  (string) ✗
```

**Solutions:**

#### Always Parse Numbers
```python
def parse_count(text: str) -> int:
    """Convert '1.2K' or '1M' to integer."""
    if isinstance(text, int):
        return text
    
    text = text.lower().strip()
    multipliers = {"k": 1000, "m": 1000000, "b": 1000000000}
    
    for suffix, mult in multipliers.items():
        if suffix in text:
            num = float(text.replace(suffix, "").strip())
            return int(num * mult)
    
    # Try direct conversion
    return int(float(text))


# In scraper
profile_data["followerCount"] = parse_count(follower_text)
```

#### Validate Schema
```python
from pydantic import BaseModel, ValidationError

class ProfileData(BaseModel):
    platform: str
    profileId: str
    followerCount: int  # Won't accept "1.2K"
    email: str = None
    
# Validation happens on init
try:
    profile = ProfileData(
        platform="youtube",
        profileId="123",
        followerCount="1.2K"  # ❌ Raises ValidationError
    )
except ValidationError as e:
    logger.error(f"Invalid profile data: {e}")
```

#### MongoDB Schema Validation
```python
db.command({
    "collMod": "profiles",
    "validator": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["platform", "profileId", "followerCount"],
            "properties": {
                "followerCount": {"bsonType": "int"},
                "email": {"bsonType": ["string", "null"]},
            }
        }
    }
})
```

---

## Problem 6: Actor Timeout (10 minute limit)

### Error: Actor ran for 602 seconds (exceeds 600s limit)

**Symptoms:**
```
Actor exceeded timeout (600 seconds)
Last output: Scraped 47/100 profiles
```

**Solutions:**

#### Reduce Profile Count per Run
```python
# Instead of 1000 profiles per run...
# Process in batches of 50-100

# config/profile_sources.yaml
youtube:
  batch_size: 50  # Process 50 profiles per run
  interval_minutes: 30  # Run every 30 minutes
```

#### Parallelize Requests
```python
import asyncio
from crawlee import BeautifulSoupCrawler

crawler = BeautifulSoupCrawler(
    max_requests_per_crawl=100,  # 100 concurrent
    max_request_retries=2,
)

# Process 100 in parallel instead of sequential
await crawler.run()
```

#### Optimize Selectors
```python
# ❌ Slow - Full page parse
def extract(page):
    all_text = page.text_content()  # Entire page
    for line in all_text.split("\n"):
        if "followers" in line:
            return parse(line)

# ✅ Fast - Targeted selector
def extract(page):
    elem = page.query_selector(".follower-count")
    return parse(elem.text_content())
```

#### Skip Timeouts
```python
# Don't fail on timeout; just return partial data

try:
    full_data = await fetch_profile(url, timeout=5)
except asyncio.TimeoutError:
    # Return what we have
    return partial_profile
```

---

## Problem 7: Memory Issues

### Error: Actor killed for using too much memory

**Symptoms:**
```
Actor terminated: Out of memory
Current memory: 612 MB (limit 512 MB)
```

**Solutions:**

#### Increase Actor Memory
```json
{
  ".actor/actor.json": "defaultMemoryMbytes": 1024
}
```

#### Stream Data Instead of Storing
```python
# ❌ Wrong - Hold all data in memory
profiles = []
for url in urls:
    profile = scrape(url)
    profiles.append(profile)  # Grows list to 1000s

await Actor.push_data(profiles)  # Push all at once

# ✅ Correct - Push as you go
for url in urls:
    profile = scrape(url)
    await Actor.push_data(profile)  # Push one at a time
```

#### Cleanup Resources
```python
import gc

for i, url in enumerate(urls):
    profile = await scrape(url)
    await Actor.push_data(profile)
    
    # Cleanup every 50 profiles
    if i % 50 == 0:
        gc.collect()
        del profile
```

---

## Problem 8: Inconsistent / Duplicate Data

### Error: Same profile appears twice in output

**Causes:**

1. **Running same actor twice**
```python
# ❌ Don't run twice
await run_actor(actor_id, input)
await run_actor(actor_id, input)  # Oops!

# ✅ Run once, check dataset
profiles = await get_actor_dataset(run_id)
```

2. **Same profile in input list**
```python
# Deduplicate before passing to actor
profiles = list(set(profile_urls))  # Remove duplicates
```

3. **MongoDB not using _id correctly**
```python
# ❌ Wrong - Creates new doc even if exists
collection.insert_one({
    "profileId": "123",
    ...
})
collection.insert_one({
    "profileId": "123",  # Duplicate!
    ...
})

# ✅ Correct - Upsert using _id
collection.update_one(
    {"_id": f"{platform}:{profileId}"},  # Unique composite key
    {"$set": {...}},
    upsert=True
)
```

---

## Problem 9: Apify API Token Errors

### Error: APIFY_TOKEN not found or invalid

**Solutions:**

#### Check Environment
```bash
# Linux/Mac
echo $APIFY_TOKEN

# Windows PowerShell
$env:APIFY_TOKEN

# If empty, set it
export APIFY_TOKEN="apk_xxx..."
```

#### Check .env File
```bash
# Create .env in project root
cat > .env << 'EOF'
APIFY_TOKEN=apk_xxx...
APIFY_PROXY_URLS=...
EOF

# Load in Python
from dotenv import load_dotenv
import os
load_dotenv()
apify_token = os.getenv("APIFY_TOKEN")
```

#### Check Token Permissions
- Go to https://console.apify.com/account/integrations
- Ensure token has "Actor" permission
- Check token isn't expired

---

## Problem 10: Schema Validation Failure

### Error: Input doesn't match schema; no console form

**Problem:**
```json
// input_schema.json is invalid JSON
{
  "properties": {
    "profiles": [  // ❌ Array syntax wrong
```

**Solution:**

Valid `input_schema.json` structure:
```json
{
  "title": "My Input",
  "type": "object",
  "schemaVersion": 1,
  "properties": {
    "profiles": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1
    }
  },
  "required": ["profiles"]
}
```

**Test schema validation:**
```bash
# Use JSONSchema validator
python -c "
import json
with open('.actor/input_schema.json') as f:
    schema = json.load(f)
    print('Valid schema:', schema.get('title'))
"
```

---

## Quick Diagnostic Checklist

When something breaks, systematically check:

```bash
# 1. Is Actor running?
apify run

# 2. Check logs
tail -f storage/logs/actor.log

# 3. Is input correct?
cat example_input.json | python -m json.tool

# 4. Can Python find modules?
python -c "from apify import Actor; print('OK')"

# 5. Is network accessible?
curl -I https://www.youtube.com

# 6. Are selectors still valid?
# (Open in browser, inspect main elements)

# 7. Try with simpler input
# (Single profile, no filters, basic output)

# 8. Check Apify console for cloud runs
# https://console.apify.com/actors
```

---

## Getting Help

1. **Check actor logs:**
```bash
# Local
cat storage/logs/actor.log

# Cloud
apify actor:log --actor-id=YOUR_ACTOR_ID -s SUCCESS
```

2. **Enable debug logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

3. **Ask in Apify Discord:**
- https://discord.com/invite/jyEM2PRvMU

4. **Open issue in your repo:**
- Include: input, error message, platform, actor code

---

## Performance Optimization Checklist

- [ ] Using proxies for blocked platforms (LinkedIn, Instagram)
- [ ] Adding random delays between requests
- [ ] Filtering with keywords to reduce output
- [ ] Parallelizing requests where possible
- [ ] Streaming data to dataset (not storing in memory)
- [ ] Increasing memory if needed
- [ ] Caching profile data to avoid re-scraping
- [ ] Making batch calls (100 profiles per run, run frequently)
- [ ] Monitoring actor health (logs, memory, time)
- [ ] Testing on sample data before full run

---

## See Also

- Main Guide: `SOCIAL_MEDIA_PROFILE_SCRAPER_GUIDE.md`
- LinkedIn Reference: `LINKEDIN_PROFILE_SCRAPER_REFERENCE.md`
- Apify Docs: https://docs.apify.com/
- Your Project: `WORKFLOW.md`, `README.md`

# Complete Guide: Building Social Media Profile Scrapers with Apify

**Date:** March 2026  
**Project:** Lead Generation Pipeline - Social Media Profile Layer  
**Platforms:** YouTube, Instagram, Twitter, Facebook, LinkedIn, Reddit (+ others)

---

## Table of Contents

1. [Overview & Architecture](#overview--architecture)
2. [Prerequisites & Setup](#prerequisites--setup)
3. [Apify Concepts & Workflow](#apify-concepts--workflow)
4. [Directory Structure](#directory-structure)
5. [Building Your First Profile Scraper](#building-your-first-profile-scraper)
6. [Platform-Specific Implementation](#platform-specific-implementation)
7. [Data Normalization & Schema](#data-normalization--schema)
8. [Integration with Lead Generation Pipeline](#integration-with-lead-generation-pipeline)
9. [Testing & Validation](#testing--validation)
10. [Deployment & Monitoring](#deployment--monitoring)
11. [Best Practices & Performance](#best-practices--performance)

---

## Overview & Architecture

### What We're Building

A **profile scraping layer** that extracts detailed profile information from social media platforms. Unlike post-level scrapers (which find leads through content), profile scrapers dive deeper to extract:

- **Profile metadata:** bio, description, follower count, verified status
- **Contact info:** email (if public), website, location
- **Engagement metrics:** followers, following, total posts, interaction rates
- **Content summary:** recent posts, hashtags used, posting frequency
- **Profile links:** external URLs, social handles across platforms

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  PROFILE DISCOVERY PHASE                                             │
│  (from existing post-level scrapers)                                  │
│  → Reddit threads → YouTube channels → Instagram profiles            │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PROFILE EXTRACTION LAYER (NEW)                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Apify Actors (Platform-Specific):                             │  │
│  │ • youtube-profile-scraper      → channel metadata             │  │
│  │ • instagram-profile-scraper    → account info + recent posts  │  │
│  │ • twitter-profile-scraper      → tweets + followers           │  │
│  │ • facebook-profile-scraper     → public info + posts          │  │
│  │ • linkedin-profile-scraper     → headline + experience        │  │
│  │ • reddit-profile-scraper       → user info + karma + posts    │  │
│  │ • tiktok-profile-scraper       → account stats + videos       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Input: Profile URLs / Handles / IDs from previous stage             │
│  Output: Normalized profile JSON documents                           │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  NORMALIZATION & ENRICHMENT                                          │
│  → profile_normalizer.py   (standardize across platforms)            │
│  → profile_enrichment.py   (dedupe, validate, enrich)                │
│  MongoDB: profiles collection                                        │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  EXISTING AI + EMAIL PIPELINE                                        │
│  → static_filter + ai_scoring.py                                     │
│  → email generation & queue                                          │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Differences from Post Scrapers

| Aspect | Post Scraper | Profile Scraper |
|--------|--------------|-----------------|
| **Input** | Keywords, subreddits, search terms | Profile URLs, usernames, IDs |
| **Output** | Posts, comments, discussions | Account metadata, bio, followers, website |
| **Complexity** | Straightforward keyword matching | Browser automation often needed (JS rendering) |
| **Speed** | Fast (10-50 URLs/min) | Slower (1-5 profiles/min) |
| **Rate Limiting** | Platform API / robots.txt | Heavy (must respect delays) |
| **Authentication** | Usually public | Sometimes requires login (LinkedIn, private accounts) |
| **Data Freshness** | Content focus (newest posts) | Profile focus (overall stats) |

---

## Prerequisites & Setup

### What You Need

#### 1. **Apify Account & CLI**
```bash
# Install Apify CLI
npm install -g apify-cli

# Or via Python (for this project)
pip install apify-client

# Log in
apify login
```

#### 2. **Python & Dependencies**
```bash
# Install Crawlee (web scraping client)
pip install crawlee-python

# Install other essentials
pip install beautifulsoup4 lxml selenium requests playwrite
```

#### 3. **Apify API Token**
- Go to `https://console.apify.com/account/integrations`
- Copy your API token
- Add to `.env`:
  ```
  APIFY_TOKEN=apk_xxx...
  ```

#### 4. **Project Structure Already Set**
Your project already has:
- `services/apify-actors/` → actor code
- `config/` → actor configs
- `pipeline/` → ingestion & scoring
- `services/shared/` → shared utilities (keyword matcher)

---

## Apify Concepts & Workflow

### What is an Apify Actor?

An **Apify Actor** is a containerized web scraper that:
1. Reads **input** (URLs, keywords, credentials)
2. Performs scraping (HTTP requests, browser automation, parsing)
3. Outputs **structured data** (JSON items in dataset)
4. Can be run **locally** (testing) or **on Apify cloud** (production)

### Actor Lifecycle

```
┌─────────────────┐
│  Write Code     │  Create main.py + .actor/actor.json + input_schema.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Test Locally   │  apify run (uses local storage/)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Push to Cloud  │  apify push
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Run on Cloud (Manual or Scheduled)         │
│  → Can access proxies, bigger resources     │
│  → Output to dataset + trigger webhook      │
└─────────────────────────────────────────────┘
```

### Key Apify Files

Each actor needs:

1. **`main.py`** — Python entry point using Apify SDK
2. **`.actor/actor.json`** — Metadata (name, version, env variables)
3. **`.actor/input_schema.json`** — Input validation & UI form
4. **`Dockerfile`** — Container definition
5. **`requirements.txt`** — Python dependencies

---

## Directory Structure

### Current Project Layout

```
services/apify-actors/
├── shared/                              # Shared utilities across all actors
│   ├── keyword_matcher.py               # Smart keyword matching
│   └── __init__.py
├── reddit-lead-scraper/                 # Example post scraper
│   ├── .actor/
│   │   ├── actor.json
│   │   ├── input_schema.json
│   │   └── output_schema.json
│   ├── src/
│   │   ├── main.py
│   │   └── __init__.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── [NEW] youtube-profile-scraper/       # New profile scrapers
├── [NEW] instagram-profile-scraper/
├── [NEW] twitter-profile-scraper/
├── [NEW] linkedin-profile-scraper/
├── [NEW] facebook-profile-scraper/
├── [NEW] reddit-profile-scraper/
└── [NEW] profile-shared-utils/          # Shared profile scraper logic
    ├── profile_normalizer.py            # Standardize across platforms
    ├── contact_extractor.py             # Extract emails, websites
    ├── metrics_calculator.py            # Engagement rates, etc.
    └── __init__.py
```

---

## Building Your First Profile Scraper

### Step 1: Create Actor Scaffolding

```bash
cd services/apify-actors
mkdir youtube-profile-scraper
cd youtube-profile-scraper

# Create directories
mkdir .actor
mkdir src
mkdir storage
```

### Step 2: Create `actor.json`

**File:** `.actor/actor.json`

```json
{
  "actorSpecVersion": 1,
  "name": "youtube-profile-scraper",
  "title": "YouTube Channel Profile Scraper",
  "description": "Extracts detailed profile information from YouTube channels: subscribers, videos count, bio, verified status, recent videos",
  "version": "1.0.0",
  "buildTag": "latest",
  "dockerImage": "apify/python-3.11-latest",
  "dockerfile": "./Dockerfile",
  "gitRepo": "https://github.com/yourusername/lead-generation.git#services/apify-actors/youtube-profile-scraper",
  "example": "example_input.json",
  "readme": "./README.md",
  "input": "schema",
  "output": "schema",
  "deploymentSources": [],
  "categories": [
    "MOVIES_AND_TV",
    "SOCIAL_NETWORKS"
  ],
  "defaultMemoryMbytes": 256,
  "defaultTimeout": 600,
  "environmentVariables": [
    {
      "name": "APIFY_HEADLESS_BROWSER_POOL_SIZE",
      "description": "Size of headless browser pool",
      "default": "1"
    }
  ]
}
```

### Step 3: Create `input_schema.json`

**File:** `.actor/input_schema.json`

```json
{
  "title": "YouTube Channel Profile Scraper Input",
  "description": "Input settings for scraping YouTube channel profiles",
  "type": "object",
  "schemaVersion": 1,
  "properties": {
    "channels": {
      "title": "Channels to Scrape",
      "description": "List of YouTube channel URLs or @handles",
      "type": "array",
      "editor": "textarea",
      "items": {
        "type": "string",
        "pattern": "^(https://www.youtube.com/(@[a-zA-Z0-9_-]+|c/[a-zA-Z0-9_-]+|channel/[a-zA-Z0-9_-]+)|@[a-zA-Z0-9_-]+)$"
      },
      "minItems": 1,
      "example": [
        "https://www.youtube.com/@TechCrunch",
        "@MrBeast",
        "https://www.youtube.com/channel/UCkQX1tChV7i2b3YyZ1XBvkA"
      ]
    },
    "includeRecentVideos": {
      "title": "Include Recent Videos",
      "description": "Fetch metadata for last N recent videos",
      "type": "boolean",
      "default": true
    },
    "recentVideoCount": {
      "title": "Number of Recent Videos",
      "description": "How many recent videos to include",
      "type": "integer",
      "default": 10,
      "minimum": 1,
      "maximum": 50
    },
    "keywords": {
      "title": "Filter Keywords (Optional)",
      "description": "Only keep profiles matching these keywords (bio/description)",
      "type": "array",
      "editor": "textarea",
      "items": {
        "type": "string"
      },
      "example": [
        "AI",
        "technology",
        "startup"
      ]
    },
    "maxChannels": {
      "title": "Max Channels",
      "description": "Limit total channels processed",
      "type": "integer",
      "default": 100,
      "minimum": 1,
      "maximum": 1000
    },
    "proxyUrls": {
      "title": "Proxy URLs (Optional)",
      "description": "Custom proxy URLs if needed",
      "type": "array",
      "editor": "textarea",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "channels"
  ]
}
```

### Step 4: Create `output_schema.json`

**File:** `.actor/output_schema.json`

```json
{
  "title": "YouTube Profile Output",
  "description": "Extracted profile information",
  "type": "object",
  "properties": {
    "platform": {
      "type": "string",
      "description": "Always 'youtube'"
    },
    "profileId": {
      "type": "string",
      "description": "YouTube channel ID"
    },
    "profileUrl": {
      "type": "string",
      "description": "Full channel URL"
    },
    "displayName": {
      "type": "string"
    },
    "bio": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "subscriberCount": {
      "type": "integer"
    },
    "videoCount": {
      "type": "integer"
    },
    "isVerified": {
      "type": "boolean"
    },
    "joinedDate": {
      "type": "string"
    },
    "website": {
      "type": "string"
    },
    "email": {
      "type": "string"
    },
    "location": {
      "type": "string"
    },
    "socialLinks": {
      "type": "object"
    },
    "recentVideos": {
      "type": "array",
      "items": {
        "type": "object"
      }
    },
    "engagementMetrics": {
      "type": "object"
    },
    "scrapedAt": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

### Step 5: Create `requirements.txt`

**File:** `requirements.txt`

```txt
apify~=2.0.0
crawlee~=0.5.0
beautifulsoup4~=4.12.0
lxml~=4.9.0
selenium~=4.15.0
playwright~=1.40.0
requests~=2.31.0
```

### Step 6: Create `Dockerfile`

**File:** `Dockerfile`

```dockerfile
FROM apify/python-3.11-latest

# Install system dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    firefox \
    firefox-geckodriver \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy actor code
COPY src/ /app/src/
COPY .actor/ /app/.actor/

WORKDIR /app
```

### Step 7: Create Main Actor Code

**File:** `src/main.py`

```python
"""YouTube Channel Profile Scraper - Apify Actor

Extracts detailed profile information from YouTube channels:
- Channel metadata (name, bio, subscriber count, etc.)
- Verification status and joined date
- Contact information (website, email if available)
- Recent videos metadata
- Social media links
"""

import asyncio
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from apify import Actor
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from bs4 import BeautifulSoup
import json


def extract_youtube_channel_id(url_or_handle: str) -> str | None:
    """Extract channel ID from various YouTube URL formats."""
    # @handle format
    if url_or_handle.startswith("@"):
        return url_or_handle[1:]
    
    # Full URL
    try:
        parsed = urlparse(url_or_handle)
        if "youtube.com" in parsed.netloc:
            if "/channel/" in parsed.path:
                return parsed.path.split("/channel/")[1].split("/")[0]
            elif "/c/" in parsed.path:
                return parsed.path.split("/c/")[1].split("/")[0]
            elif "/@" in parsed.path:
                return parsed.path.split("/@")[1].split("/")[0]
        return None
    except Exception as e:
        Actor.log.warning(f"Failed to parse URL: {url_or_handle} - {e}")
        return None


def matches_keywords(bio: str, description: str, keywords: list[str]) -> bool:
    """Check if profile matches keyword filters."""
    if not keywords:
        return True  # No filter = match all
    
    combined_text = f"{bio} {description}".lower()
    return any(kw.lower() in combined_text for kw in keywords)


class YouTubeProfileScraper:
    """Handles YouTube profile scraping logic."""
    
    def __init__(self, keywords: list[str] = None):
        self.keywords = keywords or []
    
    async def fetch_profile(self, channel_handle: str) -> dict[str, Any] | None:
        """Fetch profile data for a YouTube channel."""
        try:
            # Construct channel URL
            if channel_handle.startswith("@"):
                url = f"https://www.youtube.com/{channel_handle}"
            elif channel_handle.startswith("http"):
                url = channel_handle
            else:
                url = f"https://www.youtube.com/@{channel_handle}"
            
            Actor.log.info(f"Fetching profile: {url}")
            
            profile_data = {
                "platform": "youtube",
                "profileUrl": url,
                "displayName": None,
                "bio": "",
                "subscriberCount": None,
                "videoCount": None,
                "isVerified": False,
                "joinedDate": None,
                "website": None,
                "email": None,
                "socialLinks": {},
                "recentVideos": [],
                "engagementMetrics": {},
                "scrapedAt": datetime.utcnow().isoformat(),
                "scrapeStrategy": "beautifulsoup",
                "success": False,
            }
            
            # NOTE: In production, use Selenium/Playwright for JS rendering
            # BeautifulSoup won't work for YouTube (requires JS)
            # This is a placeholder - see "Platform-Specific Implementation" below
            
            return profile_data
            
        except Exception as e:
            Actor.log.error(f"Error fetching profile {channel_handle}: {e}")
            return None


async def main() -> None:
    """Main entry point for YouTube Profile Scraper."""
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        channels = actor_input.get("channels", [])
        keywords = actor_input.get("keywords", [])
        include_recent_videos = actor_input.get("includeRecentVideos", True)
        recent_video_count = actor_input.get("recentVideoCount", 10)
        max_channels = actor_input.get("maxChannels", 100)
        
        Actor.log.info("=" * 80)
        Actor.log.info(f"🎥 YouTube Profile Scraper Starting")
        Actor.log.info(f"   Channels: {len(channels)}")
        Actor.log.info(f"   Keywords filter: {keywords or 'None'}")
        Actor.log.info(f"   Include recent videos: {include_recent_videos}")
        Actor.log.info("=" * 80)
        
        scraper = YouTubeProfileScraper(keywords=keywords)
        profiles_found = 0
        profiles_skipped = 0
        
        for i, channel in enumerate(channels[:max_channels]):
            try:
                profile = await scraper.fetch_profile(channel)
                
                if profile is None:
                    profiles_skipped += 1
                    continue
                
                # Check keyword filter
                if not matches_keywords(
                    profile.get("bio", ""),
                    profile.get("description", ""),
                    keywords
                ):
                    Actor.log.info(f"   Skipped (no keyword match): {channel}")
                    profiles_skipped += 1
                    continue
                
                # Push to dataset
                await Actor.push_data(profile)
                profiles_found += 1
                Actor.log.info(f"   ✓ {profiles_found}. {profile['displayName']}")
                
            except Exception as e:
                Actor.log.error(f"Error processing {channel}: {e}")
                profiles_skipped += 1
        
        # Final stats
        Actor.log.info("=" * 80)
        Actor.log.info(f"✅ COMPLETE")
        Actor.log.info(f"   Profiles found: {profiles_found}")
        Actor.log.info(f"   Profiles skipped: {profiles_skipped}")
        Actor.log.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 8: Test Locally

```bash
cd services/apify-actors/youtube-profile-scraper

# Create test input
cat > example_input.json << 'EOF'
{
  "channels": [
    "@TechCrunch",
    "@MrBeast"
  ],
  "includeRecentVideos": true,
  "recentVideoCount": 5
}
EOF

# Run locally
apify run

# Check output in storage/datasets/default/
```

---

## Platform-Specific Implementation

### YouTube Profile Scraper (Browser Automation Required)

YouTube heavily relies on JavaScript, so you need **Playwright** or **Selenium**.

**File:** `src/youtube_scraper.py`

```python
"""YouTube profile scraping with Playwright for JS rendering."""

import re
import json
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
import asyncio

from playwright.async_api import async_playwright
from apify import Actor


class YouTubeProfileExtractor:
    """Extract profile data from YouTube channel page."""
    
    # CSS selectors (may need updates if YouTube changes DOM)
    SELECTORS = {
        "title": "h1.title yt-formatted-string",
        "subscriber_count": "yt-formatted-string.content#subscriber-count",
        "video_count": "yt-formatted-string.content",
        "description": "#description yt-formatted-string",
        "about_section": "#collapsible-section-body",
    }
    
    async def extract_with_playwright(self, channel_url: str) -> dict[str, Any]:
        """Use Playwright to render and extract YouTube profile."""
        profile_data = {
            "platform": "youtube",
            "profileUrl": channel_url,
            "displayName": None,
            "bio": "",
            "subscriberCount": None,
            "videoCount": None,
            "isVerified": False,
            "joinedDate": None,
            "website": None,
            "email": None,
            "location": None,
            "socialLinks": {},
            "recentVideos": [],
            "engagementMetrics": {},
            "scrapedAt": datetime.utcnow().isoformat(),
            "success": False,
        }
        
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                proxy={"server": "socks5://proxy.apify.com:7080"}  # Apify proxy
            )
            
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                await page.goto(channel_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("networkidle")
                
                # Extract channel name
                title_text = await page.text_content("h1.style-scope.ytd-channel-tagline-renderer")
                profile_data["displayName"] = title_text.strip() if title_text else None
                
                # Extract subscriber count
                sub_text = await page.text_content("yt-formatted-string#subscriber-count")
                if sub_text:
                    # "2.3M subscribers" → 2300000
                    profile_data["subscriberCount"] = parse_count_string(sub_text)
                
                # Extract channel description (about section)
                about_content = await page.text_content("#content #description")
                if about_content:
                    profile_data["bio"] = about_content.strip()
                
                # Extract social media links
                links = await page.locator("a[href*='://']").all()
                for link in links:
                    href = await link.get_attribute("href")
                    if href and not href.startswith("/"):
                        text = await link.text_content()
                        if text:
                            profile_data["socialLinks"][text.strip()] = href
                
                # Extract recent videos
                video_elements = await page.locator("ytd-grid-video-renderer").all()
                for video in video_elements[:10]:
                    video_title = await video.text_content("a#video-title")
                    video_url = await video.get_attribute("href")
                    if video_title:
                        profile_data["recentVideos"].append({
                            "title": video_title.strip(),
                            "url": video_url if video_url.startswith("http") else f"https://youtube.com{video_url}"
                        })
                
                profile_data["success"] = True
                
            except Exception as e:
                Actor.log.error(f"Error scraping {channel_url}: {e}")
                profile_data["error"] = str(e)
            
            finally:
                await context.close()
                await browser.close()
        
        return profile_data


def parse_count_string(text: str) -> int | None:
    """Parse subscriber/view count from string like '2.3M' or '1.5K'."""
    try:
        text = text.lower().strip()
        # Remove non-numeric except . and letters (M, K, B, T)
        match = re.search(r'([\d.]+)\s*([mkbt])?', text)
        if not match:
            return None
        
        number = float(match.group(1))
        multiplier = match.group(2)
        
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
        if multiplier:
            number *= multipliers.get(multiplier, 1)
        
        return int(number)
    except Exception:
        return None
```

### Instagram Profile Scraper

```python
"""Instagram profile scraper using API + web scraping."""

import json
from typing import Any
from datetime import datetime
from apify import Actor
import httpx


class InstagramProfileScraper:
    """Scrape Instagram profiles."""
    
    async def fetch_instagram_profile(self, username: str) -> dict[str, Any]:
        """Fetch Instagram profile data."""
        profile_data = {
            "platform": "instagram",
            "username": username,
            "profileUrl": f"https://www.instagram.com/{username}/",
            "displayName": None,
            "bio": "",
            "followerCount": None,
            "followingCount": None,
            "postCount": None,
            "profileImage": None,
            "isVerified": False,
            "isBusinessAccount": False,
            "email": None,
            "website": None,
            "recentPosts": [],
            "engagementMetrics": {},
            "scrapedAt": datetime.utcnow().isoformat(),
            "success": False,
        }
        
        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
                }
            ) as client:
                # Attempt GraphQL fetch (Instagram)
                response = await client.get(
                    f"https://www.instagram.com/api/v1/users/web_profile_info/",
                    params={"username": username},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    user = data.get("data", {}).get("user", {})
                    
                    profile_data["displayName"] = user.get("full_name")
                    profile_data["bio"] = user.get("biography", "")
                    profile_data["followerCount"] = user.get("follower_count", 0)
                    profile_data["followingCount"] = user.get("following_count", 0)
                    profile_data["postCount"] = user.get("media_count", 0)
                    profile_data["isVerified"] = user.get("is_verified", False)
                    profile_data["isBusinessAccount"] = user.get("is_business", False)
                    profile_data["profileImage"] = user.get("profile_pic_url")
                    profile_data["website"] = user.get("external_url", "")
                    
                    profile_data["success"] = True
                
        except Exception as e:
            Actor.log.warning(f"Failed to fetch Instagram profile {username}: {e}")
        
        return profile_data
```

### Twitter Profile Scraper

```python
"""Twitter profile scraper."""

import re
from datetime import datetime
from typing import Any
from apify import Actor


class TwitterProfileScraper:
    """Extract Twitter/X profile data."""
    
    async def fetch_twitter_profile(self, username: str) -> dict[str, Any]:
        """Fetch Twitter profile using API or web scraping."""
        profile_data = {
            "platform": "twitter",
            "username": username,
            "profileUrl": f"https://twitter.com/{username}",
            "displayName": None,
            "bio": "",
            "followerCount": None,
            "followingCount": None,
            "tweetCount": None,
            "isVerified": False,
            "location": None,
            "website": None,
            "email": None,
            "joinedDate": None,
            "recentTweets": [],
            "engagementMetrics": {},
            "scrapedAt": datetime.utcnow().isoformat(),
            "success": False,
        }
        
        # For Twitter: Use Twitter API v2 (requires Bearer token)
        # Or use Apify's Twitter Actor as base
        # Note: Twitter requires authentication for most endpoints
        
        return profile_data
```

---

## Data Normalization & Schema

Once scrapers run, normalize profiles into a consistent schema for the pipeline.

**File:** `pipeline/profile_normalizer.py`

```python
"""Normalize social media profiles to consistent schema."""

from typing import Any
from datetime import datetime
from pymongo import MongoClient
from pipeline.db import DATABASE_CLIENT


class ProfileNormalizer:
    """Standardize profiles from different platforms."""
    
    SCHEMA_VERSION = "1.0.0"
    
    # Map platform-specific fields to standard schema
    PLATFORM_FIELD_MAPPING = {
        "youtube": {
            "displayName": "name",
            "subscriberCount": "follower_count",
            "videoCount": "content_count",
            "bio": "bio",
        },
        "instagram": {
            "displayName": "name",
            "followerCount": "follower_count",
            "postCount": "content_count",
            "bio": "bio",
        },
        "twitter": {
            "displayName": "name",
            "followerCount": "follower_count",
            "tweetCount": "content_count",
            "bio": "bio",
        },
        "linkedin": {
            "displayName": "name",
            "headline": "bio",
        },
        "reddit": {
            "displayName": "name",
            "postKarma": "follower_count",  # Reddit uses karma instead
        },
    }
    
    @staticmethod
    def normalize_profile(raw_profile: dict[str, Any]) -> dict[str, Any]:
        """Convert raw platform-specific profile to standard schema."""
        
        platform = raw_profile.get("platform")
        
        normalized = {
            "_schemaVersion": ProfileNormalizer.SCHEMA_VERSION,
            "platform": platform,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
            
            # Standard fields (platform-agnostic)
            "profileId": raw_profile.get("profileId") or raw_profile.get("username") or raw_profile.get("handle"),
            "profileUrl": raw_profile.get("profileUrl"),
            "name": raw_profile.get("displayName"),
            "bio": raw_profile.get("bio") or "",
            
            # Metrics
            "followerCount": raw_profile.get("subscriberCount") or raw_profile.get("followerCount") or 0,
            "followingCount": raw_profile.get("followingCount") or 0,
            "contentCount": raw_profile.get("videoCount") or raw_profile.get("postCount") or raw_profile.get("tweetCount") or 0,
            
            # Contact
            "email": raw_profile.get("email"),
            "website": raw_profile.get("website"),
            "location": raw_profile.get("location"),
            
            # Rich data
            "verified": raw_profile.get("isVerified", False),
            "recentContent": raw_profile.get("recentVideos") or raw_profile.get("recentPosts") or raw_profile.get("recentTweets") or [],
            "socialLinks": raw_profile.get("socialLinks", {}),
            
            # Metadata
            "rawProfile": raw_profile,  # Keep original for reference
        }
        
        return normalized
    
    @staticmethod
    async def store_normalized_profile(normalized: dict[str, Any]) -> bool:
        """Store normalized profile to MongoDB."""
        try:
            db = DATABASE_CLIENT["lead_discovery"]
            collection = db["profiles"]
            
            # Upsert: update if exists, create if not
            result = collection.update_one(
                {"platform": normalized["platform"], "profileId": normalized["profileId"]},
                {"$set": normalized},
                upsert=True
            )
            
            return result.acknowledged
        except Exception as e:
            print(f"Error storing profile: {e}")
            return False


# Usage in pipeline
async def normalize_and_store_actor_output(actor_dataset: list[dict]) -> int:
    """Take raw actor output and normalize to profiles collection."""
    stored = 0
    for raw_profile in actor_dataset:
        normalized = ProfileNormalizer.normalize_profile(raw_profile)
        if await ProfileNormalizer.store_normalized_profile(normalized):
            stored += 1
    return stored
```

---

## Integration with Lead Generation Pipeline

### Add Profile Scraping to Pipeline

**File:** `pipeline/run_pipeline.py` (modifications)

```python
# In run_pipeline.py, add profile scraper support:

async def run_profile_ingest(platforms: list[str]) -> int:
    """Run profile scrapers for specified platforms."""
    Actor.log.info(f"🔍 Starting profile ingest for platforms: {platforms}")
    
    profiles_found = 0
    
    for platform in platforms:
        actor_name = f"{platform}-profile-scraper"
        actor_id = await get_actor_id(actor_name)  # Look up in config
        
        if not actor_id:
            Actor.log.warning(f"Actor not found: {actor_name}")
            continue
        
        # Run actor with profile URLs from previous posts
        leads = await get_leads_needing_profiles(platform)
        
        if leads:
            input_data = {
                "profiles": [lead["profileUrl"] for lead in leads],
                "maxProfiles": 100,
            }
            
            profiles = await run_actor(actor_id, input_data)
            profiles_found += len(profiles)
    
    return profiles_found
```

### Add Profile Schema to MongoDB

**File:** `pipeline/schema.py` (additions)

```python
PROFILE_SCHEMA = {
    "_schemaVersion": "1.0.0",
    "platform": str,  # youtube, instagram, twitter, etc.
    "profileId": str,  # Unique identifier on platform
    "profileUrl": str,
    "name": str,
    "bio": str,
    "followerCount": int,
    "followingCount": int,
    "contentCount": int,
    "email": str,
    "website": str,
    "location": str,
    "verified": bool,
    "recentContent": list,
    "socialLinks": dict,
    "createdAt": datetime,
    "updatedAt": datetime,
}

# Create index for fast lookups
PROFILE_INDEXES = [
    ("platform", "profileId"),  # Compound unique index
    ("followerCount", -1),       # High-value profiles
    ("email", 1),                # Find profiles with emails
]
```

---

## Testing & Validation

### Local Testing

```bash
# Test YouTube scraper
cd services/apify-actors/youtube-profile-scraper
apify run

# Check output
cat storage/datasets/default/000000001.json
```

### Validation Checklist

- [ ] All required fields present in output
- [ ] Data types match schema (numbers are ints, not strings)
- [ ] URLs are valid and complete
- [ ] No duplicate profiles in single run
- [ ] Keyword filtering works (if enabled)
- [ ] Rate limiting respected (no IP bans)
- [ ] Error handling doesn't crash actor
- [ ] Logs show proper progress

### Unit Tests

**File:** `tests/test_profile_normalizer.py`

```python
"""Tests for profile normalization."""

import pytest
from pipeline.profile_normalizer import ProfileNormalizer


def test_normalize_youtube_profile():
    """Test YouTube profile normalization."""
    raw = {
        "platform": "youtube",
        "displayName": "TechCrunch",
        "subscriberCount": 2300000,
        "videoCount": 5234,
        "bio": "Technology news",
    }
    
    normalized = ProfileNormalizer.normalize_profile(raw)
    
    assert normalized["platform"] == "youtube"
    assert normalized["name"] == "TechCrunch"
    assert normalized["followerCount"] == 2300000
    assert normalized["contentCount"] == 5234


def test_normalize_instagram_profile():
    """Test Instagram profile normalization."""
    raw = {
        "platform": "instagram",
        "username": "techcrunch",
        "followerCount": 1500000,
        "bio": "Technology stories",
    }
    
    normalized = ProfileNormalizer.normalize_profile(raw)
    assert normalized["followerCount"] == 1500000


def test_normalize_handles_missing_fields():
    """Test normalization with incomplete data."""
    raw = {
        "platform": "twitter",
        "displayName": "TechCrunch",
    }
    
    normalized = ProfileNormalizer.normalize_profile(raw)
    assert normalized["followerCount"] == 0  # Default
    assert normalized["bio"] == ""  # Default
```

---

## Deployment & Monitoring

### Deploy to Apify

```bash
# Log in
apify login

# Deploy each actor
cd services/apify-actors/youtube-profile-scraper
apify push

# Creates: https://console.apify.com/actors/{actorId}
```

### Create Deployment Config

**File:** `config/profile_sources.yaml`

```yaml
profile_platforms:
  # YouTube
  youtube:
    actor_id: "YOUR_ACTOR_ID"  # From apify push
    enabled: true
    timeout_secs: 600
    memory_mb: 512
    input:
      includeRecentVideos: true
      recentVideoCount: 10
    run_every_hours: 24
    max_runs_per_day: 1
  
  # Instagram
  instagram:
    actor_id: "YOUR_ACTOR_ID"
    enabled: true
    timeout_secs: 300
    memory_mb: 256
    run_every_hours: 24
  
  # Twitter
  twitter:
    actor_id: "YOUR_ACTOR_ID"
    enabled: true
    timeout_secs: 600
    memory_mb: 512
  
  # LinkedIn (requires special handling)
  linkedin:
    actor_id: "YOUR_ACTOR_ID"
    enabled: false  # Requires authentication
    needs_proxy: true
  
  # Reddit
  reddit:
    actor_id: "YOUR_ACTOR_ID"
    enabled: true
    timeout_secs: 300
  
  # Facebook
  facebook:
    actor_id: "YOUR_ACTOR_ID"
    enabled: false  # Very rate-limited
```

### Monitoring Script

**File:** `scripts/monitor_profile_scrapers.py`

```python
"""Monitor profile scraper execution and health."""

import json
from datetime import datetime, timedelta
from apify_client import ApifyClient


def check_actor_run(actor_id: str, max_age_hours: int = 24) -> dict:
    """Check actor's recent run status."""
    client = ApifyClient(apify_token)
    
    runs = client.actor(actor_id).runs().list(limit=10)
    
    if not runs["data"]:
        return {"status": "never_run", "actor_id": actor_id}
    
    latest_run = runs["data"][0]
    run_time = datetime.fromisoformat(latest_run["createdAt"])
    age = datetime.utcnow() - run_time
    
    return {
        "actor_id": actor_id,
        "status": latest_run["status"],
        "age_hours": age.total_seconds() / 3600,
        "items_output": latest_run["stats"]["itemsCount"],
        "memory_mb": latest_run["stats"]["memoryHeapUsed"] // (1024 * 1024),
        "duration_secs": latest_run["stats"]["runTime"] // 1000,
    }


def monitor_all_profile_scrapers():
    """Run health check on all profile scrapers."""
    config = yaml.safe_load(open("config/profile_sources.yaml"))
    
    results = {}
    for platform, config_data in config["profile_platforms"].items():
        if not config_data.get("enabled"):
            continue
        
        health = check_actor_run(config_data["actor_id"])
        results[platform] = health
        
        print(f"{platform:12} | Status: {health['status']:10} | Items: {health.get('items_output', 0):5} | Age: {health.get('age_hours', 0):.1f}h")
    
    return results
```

---

## Best Practices & Performance

### 1. **Rate Limiting & Delays**

```python
import asyncio
import random

async def scrape_with_delay(profile_list: list[str]):
    """Scrape profiles with random delays to avoid blocking."""
    for profile in profile_list:
        await scrape_profile(profile)
        delay = random.uniform(2, 5)  # 2-5 second delay
        await asyncio.sleep(delay)
```

### 2. **Error Handling**

```python
async def robust_scrape(profile: str, max_retries: int = 3) -> dict | None:
    """Scrape with retry logic."""
    for attempt in range(max_retries):
        try:
            return await scrape_profile(profile)
        except RateLimitError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
        except Exception as e:
            Actor.log.error(f"Error scraping {profile}: {e}")
            return None
```

### 3. **Proxy Rotation**

```python
# Use Apify's proxy service
proxy_config = await Actor.create_proxy_configuration()

crawler = BeautifulSoupCrawler(
    proxy_configuration=proxy_config,
    max_session_rotations=10,  # Rotate IPs frequently
)
```

### 4. **Data Deduplication**

```python
async def deduplicate_profiles(profiles: list[dict]) -> list[dict]:
    """Remove duplicate profiles by ID."""
    seen = set()
    unique = []
    
    for profile in profiles:
        profile_key = (profile["platform"], profile["profileId"])
        if profile_key not in seen:
            seen.add(profile_key)
            unique.append(profile)
    
    return unique
```

### 5. **Logging & Metrics**

```python
# Always log key metrics
Actor.log.info(f"✅ Scraped {profiles_found} profiles")
Actor.log.info(f"⏭️  Skipped {profiles_skipped} (errors/filters)")
Actor.log.info(f"📊 Success rate: {profiles_found / (profiles_found + profiles_skipped) * 100:.1f}%")
Actor.log.info(f"⏱️  Avg time per profile: {total_time / profiles_found:.2f}s")
```

---

## Checklist: From Idea to Production

- [ ] **Actor Created:** Scaffolding + code structure
- [ ] **Local Testing:** `apify run` works without errors
- [ ] **Input Schema:** Validates correctly, has good defaults
- [ ] **Normalization:** Profiles convert to standard schema
- [ ] **Rate Limiting:** Respects platform limits
- [ ] **Error Handling:** Doesn't crash on bad input
- [ ] **Logging:** Shows clear progress + stats
- [ ] **Deploy:** `apify push` succeeds
- [ ] **Config Added:** `config/profile_sources.yaml` updated
- [ ] **Pipeline Integration:** Runs from `run_pipeline.py`
- [ ] **Monitoring:** Script tracks actor health
- [ ] **Documentation:** README explains usage

---

## Quick Reference: Multi-Platform Example

**Scrape profiles from different platforms in one pipeline run:**

```python
# In run_pipeline.py

async def run_profile_enrichment():
    """After post ingest, enrich top leads with profile data."""
    
    # 1. Get top leads that need profiles
    leads = db.leads.find({"profileData": None}).limit(100)
    
    # 2. Group by platform
    by_platform = {}
    for lead in leads:
        platform = lead["source_platform"]
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(lead)
    
    # 3. Run profile scraper for each platform
    for platform, platform_leads in by_platform.items():
        actor_id = config["profile_platforms"][platform]["actor_id"]
        
        profiles = await run_actor(actor_id, {
            "profiles": [lead["profile_url"] for lead in platform_leads]
        })
        
        # Normalize & store
        for raw_profile in profiles:
            normalized = ProfileNormalizer.normalize_profile(raw_profile)
            await ProfileNormalizer.store_normalized_profile(normalized)
    
    # 4. Link profiles back to leads
    for lead in leads:
        profile = db.profiles.find_one({
            "platform": lead["source_platform"],
            "profileId": lead["profile_id"]
        })
        db.leads.update_one(
            {"_id": lead["_id"]},
            {"$set": {"profileData": profile}}
        )
```

---

## Additional Resources

- **Apify Docs:** https://docs.apify.com/
- **Crawlee Python:** https://crawlee.dev/python/
- **Playwright:** https://playwright.dev/python/
- **Selenium:** https://www.selenium.dev/
- **Your Project:** See `pipeline/README.md`, `WORKFLOW.md`

---

**Last Updated:** March 2026  
**GitHub:** [Your Repo Link]

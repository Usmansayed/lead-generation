# Quick-Start: Create a New Profile Scraper in 5 Steps

Use this to rapidly scaffold a new actor for any social media platform.

---

## Step 1: Run the Generator Script

**File:** `scripts/create_profile_actor.sh`

```bash
#!/bin/bash

# Usage: ./create_profile_actor.sh <platform> <description>
# Example: ./create_profile_actor.sh tiktok "TikTok profile scraper"

PLATFORM=$1
DESCRIPTION=$2

if [ -z "$PLATFORM" ] || [ -z "$DESCRIPTION" ]; then
    echo "Usage: $0 <platform> <description>"
    echo "Example: $0 tiktok 'TikTok profile and video scraper'"
    exit 1
fi

ACTOR_DIR="services/apify-actors/${PLATFORM}-profile-scraper"

# Create directory structure
mkdir -p "$ACTOR_DIR/.actor"
mkdir -p "$ACTOR_DIR/src"
mkdir -p "$ACTOR_DIR/storage/datasets"
mkdir -p "$ACTOR_DIR/storage/key_value_stores"

echo "✓ Created directories"

# Create actor.json
cat > "$ACTOR_DIR/.actor/actor.json" << EOF
{
  "actorSpecVersion": 1,
  "name": "${PLATFORM}-profile-scraper",
  "title": "$(echo $PLATFORM | sed 's/.*/\U&/') Profile Scraper",
  "description": "$DESCRIPTION",
  "version": "1.0.0",
  "buildTag": "latest",
  "dockerImage": "apify/python-3.11-latest",
  "dockerfile": "./Dockerfile",
  "defaultMemoryMbytes": 256,
  "defaultTimeout": 600
}
EOF

echo "✓ Created .actor/actor.json"

# Create input_schema.json
cat > "$ACTOR_DIR/.actor/input_schema.json" << 'EOF'
{
  "title": "Profile Scraper Input",
  "type": "object",
  "schemaVersion": 1,
  "properties": {
    "profiles": {
      "title": "Profiles to Scrape",
      "description": "URLs or usernames",
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1
    },
    "maxProfiles": {
      "title": "Max Profiles",
      "type": "integer",
      "default": 100
    },
    "keywords": {
      "title": "Filter Keywords",
      "description": "Optional keyword filter",
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": ["profiles"]
}
EOF

echo "✓ Created .actor/input_schema.json"

# Create output_schema.json
cat > "$ACTOR_DIR/.actor/output_schema.json" << 'EOF'
{
  "title": "Profile Output",
  "type": "object",
  "properties": {
    "platform": {"type": "string"},
    "profileId": {"type": "string"},
    "profileUrl": {"type": "string"},
    "displayName": {"type": "string"},
    "bio": {"type": "string"},
    "followerCount": {"type": "integer"},
    "contentCount": {"type": "integer"},
    "email": {"type": "string"},
    "website": {"type": "string"},
    "verified": {"type": "boolean"},
    "recentContent": {"type": "array"},
    "scrapedAt": {"type": "string", "format": "date-time"}
  }
}
EOF

echo "✓ Created .actor/output_schema.json"

# Create requirements.txt
cat > "$ACTOR_DIR/requirements.txt" << 'EOF'
apify~=2.0.0
crawlee~=0.5.0
beautifulsoup4~=4.12.0
playwright~=1.40.0
requests~=2.31.0
EOF

echo "✓ Created requirements.txt"

# Create Dockerfile
cat > "$ACTOR_DIR/Dockerfile" << 'EOF'
FROM apify/python-3.11-latest

RUN apt-get update && apt-get install -y chromium firefox && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY .actor/ /app/.actor/

WORKDIR /app
EOF

echo "✓ Created Dockerfile"

# Create main.py template
cat > "$ACTOR_DIR/src/main.py" << 'EOF'
"""Profile Scraper Template - Customize for your platform."""

import asyncio
from datetime import datetime
from typing import Any
from apify import Actor


async def scrape_profile(profile_id: str) -> dict[str, Any] | None:
    """Scrape a single profile. IMPLEMENT THIS."""
    # TODO: Implement platform-specific scraping
    return None


async def main() -> None:
    """Main entry point."""
    async with Actor:
        actor_input = await Actor.get_input() or {}
        profiles = actor_input.get("profiles", [])
        
        Actor.log.info(f"🚀 Starting profile scraper")
        Actor.log.info(f"   Profiles to scrape: {len(profiles)}")
        
        found = 0
        for profile_id in profiles:
            try:
                profile_data = await scrape_profile(profile_id)
                if profile_data:
                    await Actor.push_data(profile_data)
                    found += 1
            except Exception as e:
                Actor.log.error(f"Error scraping {profile_id}: {e}")
        
        Actor.log.info(f"✅ Complete - Found {found} profiles")


if __name__ == "__main__":
    asyncio.run(main())
EOF

echo "✓ Created src/main.py"

# Create README
cat > "$ACTOR_DIR/README.md" << EOF
# $(echo $PLATFORM | sed 's/.*/\U&/') Profile Scraper

$DESCRIPTION

## Quick Start

\`\`\`bash
apify run
\`\`\`

## Input Schema

- \`profiles\` (required): Array of profile URLs or usernames
- \`maxProfiles\`: Limit results (default: 100)
- \`keywords\`: Filter profiles by keywords in bio

## Output

Standard profile schema with fields:
- \`platform\`: Always '${PLATFORM}'
- \`profileId\`: Unique ID on platform
- \`displayName\`, \`bio\`, \`followerCount\`, etc.

## Implementation

TODO: Customize \`src/main.py\` for this platform:
1. Profile URL format
2. Data extraction (CSS/XPath selectors or API)
3. Contact info extraction
4. Engagement metrics

## Notes

- Respect rate limits (2-5 second delays between requests)
- Use proxies via \`Actor.create_proxy_configuration()\`
- Log progress every 10 profiles

## Deploy

\`\`\`bash
apify login
apify push
\`\`\`
EOF

echo "✓ Created README.md"

# Create example_input.json
cat > "$ACTOR_DIR/example_input.json" << 'EOF'
{
  "profiles": [
    "profile1",
    "profile2"
  ],
  "maxProfiles": 50,
  "keywords": ["tech", "startup"]
}
EOF

echo "✓ Created example_input.json"

echo ""
echo "✅ Actor scaffolded successfully!"
echo ""
echo "Next steps:"
echo "1. cd $ACTOR_DIR"
echo "2. Edit src/main.py to implement scraping logic"
echo "3. Run: apify run"
echo "4. When ready: apify push"

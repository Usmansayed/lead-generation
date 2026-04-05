# Lead Discovery System - Project Explanation

## Overview

This project is a sophisticated **Lead Discovery System** designed to identify potential business leads from various online sources (Reddit, HackerNews, etc.). It has been modernized to use **MongoDB** as its primary database and **Crawlee** (Node.js) as the core crawling engine, replacing simpler Python scrapers.

## Core Architecture

The system follows a microservice-like architecture:

1.  **Crawlee Service** (`services/crawlee/`):
    *   **Runtime**: Node.js with TypeScript.
    *   **Purpose**: Handles all web scraping and crawling logic.
    *   **Engine**: Uses `Crawlee` framework to manage queues, storage, and anti-blocking.
    *   **Browsers**:
        *   **Playwright**: For dynamic, JavaScript-heavy sites (e.g., Reddit, Twitter).
        *   **Cheerio**: For fast, static HTML scraping (e.g., HackerNews, Forums).
    *   **Database**: Writes directly to MongoDB.

2.  **Configuration** (`config/`):
    *   The "Brain" of the operation. All targeting logic is stored in YAML files, not code.
    *   **`keywords_mega_expanded.yaml`**: Contains ~4,200 keywords grouped into clusters for identifying intent.
    *   **`sources_master_v2_mega.yaml`**: Defines 150+ target sources (URLs) with metadata like priority and category.
    *   **`scoring.yaml`**: Rules for scoring leads based on keyword matches and engagement.

3.  **Database** (MongoDB):
    *   **Database Name**: `lead_discovery`
    *   **Collection**: `raw_posts`
    *   Stores the raw data extracted from finding leads. Data includes title, body, author, engagement metrics, and discovery metadata.

4.  **Queue** (Redis):
    *   Used for job management and caching (optional but configured).

## File Structure

```
lead-generation/
├── config/                 # LOGIC & RULES
│   ├── keywords_mega_expanded.yaml  # Targeting keywords
│   ├── sources_master_v2_mega.yaml  # Target websites
│   ├── scoring.yaml                 # Lead scoring rules
│   └── prompts.yaml                 # LLM prompts (future use)
│
├── services/
│   └── crawlee/            # CRAWLER MICROSERVICE
│       ├── src/
│       │   ├── crawlers/   # Specific crawler implementations
│       │   │   ├── playwright.ts    # Dynamic site logic
│       │   │   └── cheerio.ts       # Static site logic
│       │   ├── config-loader.ts     # YAML parser & logic
│       │   ├── db.ts                # MongoDB connection & schema
│       │   └── index.ts             # CLI Entry point
│       ├── dist/           # Compiled JavaScript (after build)
│       └── package.json    # Dependencies
│
├── docker-compose.yml      # Container orchestration (Mongo, Redis)
└── .env.example            # Environment variables template
```

## Workflow

1.  **Initialization**:
    *   The system starts and connects to MongoDB.
    *   It loads the YAML configurations to understand *what* to look for (Keywords) and *where* to look (Sources).

2.  **Crawl Execution**:
    *   You trigger a crawl (e.g., "Crawl Reddit").
    *   The specific crawler (Playwright or Cheerio) is selected based on the source type.
    *   The crawler visits the URL, respecting rate limits.

3.  **Extraction**:
    *   The crawler extracts relevant data: Post Title, Body, Author, Upvotes/Comments.
    *   Specific selectors are used for each platform (defined in the code).

4.  **Data Persistence**:
    *   The raw data is validated and cleaned.
    *   It is checked against the database to prevent duplicates (using URL as a unique key).
    *   New leads are saved to the `raw_posts` collection in MongoDB.

## Key Features

*   **Hybrid Crawling**: Intelligent switching between fast HTML scraping and full browser automation.
*   **YAML-Driven**: Change what you scrape by editing a text file, no code changes needed.
*   **Duplicate Protection**: Ensures you don't process the same lead twice.
*   **Scalable**: Built on Docker and Node.js Event Loop for high concurrency.

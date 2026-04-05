# Lead Discovery System - Setup & Start Guide

This guide covers how to set up the project from scratch and run the crawler.

## Prerequisites

1.  **Node.js** (v18 or higher)
2.  **MongoDB** (Local installation or Docker)
3.  **Git** (Hash command line tools)

## 1. Environment Setup

### Database
You need a running MongoDB instance.

**Option A: Using Docker (Recommended)**
```bash
# In project root
docker-compose up -d mongo redis
```

**Option B: Local Install**
Ensure your local MongoDB service is running (`mongod`).

### Environment Variables
1.  Navigate to the service directory:
    ```bash
    cd services/crawlee
    ```
2.  Create a `.env` file:
    ```env
    # MongoDB Connection String
    MONGODB_URI=mongodb://localhost:27017/lead_discovery
    
    # Path to your config folder (Use forward slashes / even on Windows)
    CONFIG_DIR=C:/Users/usman/Music/lead-generation/config
    ```

## 2. Installation

Install the Node.js dependencies and browser binaries.

```bash
cd services/crawlee

# Install code dependencies
npm install

# Install Playwright browsers (Chrome/Firefox/Webkit)
npx playwright install
```

## 3. Build

The project uses TypeScript and needs to be compiled before running.

```bash
npm run build
```
*Note: If you make code changes, run this again.*

## 4. Running the Crawler

We use the compiled code in the `dist` folder. You must set the `CONFIG_DIR` variable to point to your config folder for the crawler to find your keywords and sources.

### Verify Everything Works (Stats)
This checks the database connection and configuration loading.

```bash
# PowerShell
$env:CONFIG_DIR='C:/Users/usman/Music/lead-generation/config'; node dist/index.js stats
```

### Run a Specific Crawl
**Syntax**: `node dist/index.js crawl <platform> <identifier> <limit>`

**Example: Crawl HackerNews**
```bash
$env:CONFIG_DIR='C:/Users/usman/Music/lead-generation/config'; node dist/index.js crawl hackernews newest 10
```

**Example: Crawl a Subreddit**
```bash
$env:CONFIG_DIR='C:/Users/usman/Music/lead-generation/config'; node dist/index.js crawl reddit startups 20
```

### Run All Sources
**Warning**: This will crawl all 150+ sources defined in your config file.

```bash
$env:CONFIG_DIR='C:/Users/usman/Music/lead-generation/config'; node dist/index.js all
```

## Troubleshooting

*   **Config Not Found**: If you see errors about loading YAML files, double-check your `$env:CONFIG_DIR` path. It must be an **absolute path** to the `config` folder.
*   **MongoDB Error**: Ensure MongoDB is running. `npm run crawl stats` will fail if it can't connect.
*   **Playwright Error**: If browsers fail to launch, try running `npx playwright install` again.

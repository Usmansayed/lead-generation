# Post Content Fetcher

Fetches a single URL and returns the main text content. Used by the lead-generation pipeline **after** a lead passes the AI filter: full fetch of the post URL so we can write hyper-personalized emails.

- **Input:** `url` (required), `useProxy` (optional, default true)
- **Output:** One item with `text`, `content`, and `url`

For Instagram/Facebook post URLs, residential proxy is recommended (set `useProxy: true`). Deploy this actor to your Apify account (creators account – your own actors). The pipeline will call it by name `post-content-fetcher` if `POST_SCRAPER_ACTOR_ID` is not set.

## Deploy

From this folder:

```bash
apify push
```

Or from project root:

```bash
python deploy_and_test.py post-content-fetcher
```

## Pipeline usage

Set in `.env` (optional):

- `POST_SCRAPER_ACTOR_ID=your_username/post-content-fetcher` – or leave unset and the pipeline will resolve by actor name `post-content-fetcher`.

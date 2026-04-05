# Lead Generation Pipeline

AI-powered lead discovery: scrape Reddit, Twitter, Instagram, Facebook, LinkedIn → score with keywords + LLM → queue personalized emails. Uses **Apify** actors, **MongoDB**, and **AWS Bedrock** (and optionally **SES** for sending).

## Quick Start

```bash
cp .env.example .env   # set APIFY_TOKEN, MONGODB_URI, AWS_BEDROCK_API or AWS2_* for Bedrock
pip install -r pipeline/requirements.txt
docker-compose up -d mongo   # optional: MongoDB
python -m pipeline.run_pipeline --ingest-only --platforms reddit   # or full pipeline
```

## Docs

- **Workflow and how it works:** [WORKFLOW.md](WORKFLOW.md) — pipeline stages, config, running daily, time limits, keyword rotation.
- **Pipeline detail and env:** [pipeline/README.md](pipeline/README.md)
- **AWS (SES, production):** [AWS_CHECKLIST.md](AWS_CHECKLIST.md)
- **Dashboard:** [services/dashboard/README.md](services/dashboard/README.md)

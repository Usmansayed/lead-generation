"""MongoDB connection for dashboard API. Uses MONGODB_URI from env (load .env from project root)."""
import os
from pathlib import Path

# Project root = lead-generation (parent of services)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)

def get_mongo_db():
    """Connect to MongoDB for main pipeline data (lead_discovery DB)."""
    from urllib.parse import urlparse
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/").strip()
    path = (urlparse(uri).path or "").strip("/").split("?")[0]
    db_name = path if path else "lead_discovery"
    try:
        from pymongo import MongoClient
        client = MongoClient(uri)
        return client.get_database(db_name)
    except Exception:
        return None

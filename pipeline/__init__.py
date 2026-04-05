# Lead Generation Pipeline - Phase 1 (5 platforms)
from .config_loader import load_keywords_master, load_phase1_sources
from .models import CanonicalLead, Author
from .normalizers import normalize_item, NORMALIZERS
from .ingestion import run_ingestion, ingest_platform, store_raw_posts
from .static_filter import apply_static_filter
from .relevance import RelevanceEngine, compute_relevance, get_engine
from .ai_scoring import apply_ai_scoring, score_lead
from .email_personalization import generate_email, enqueue_lead_for_email
from .email_queue import add_to_queue, get_pending, mark_sent, mark_failed

__all__ = [
    "load_keywords_master",
    "load_phase1_sources",
    "CanonicalLead",
    "Author",
    "normalize_item",
    "NORMALIZERS",
    "run_ingestion",
    "ingest_platform",
    "store_raw_posts",
    "apply_static_filter",
    "RelevanceEngine",
    "compute_relevance",
    "get_engine",
    "apply_ai_scoring",
    "score_lead",
    "generate_email",
    "enqueue_lead_for_email",
    "add_to_queue",
    "get_pending",
    "mark_sent",
    "mark_failed",
]

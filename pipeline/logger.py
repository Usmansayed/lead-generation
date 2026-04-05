"""
Structured logging for the pipeline: key=value style, optional run_id for tracing.
Use Python logging so level and output can be configured (e.g. JSON for production).

Evolution: keep log format additive (new keys only). Do not remove or change meaning
of existing keys so parsers and tooling stay stable; see config/DATA_AND_EVOLUTION.md.
"""
from __future__ import annotations
import logging
import uuid

# Module-level run id for this process; set at pipeline start
_run_id: str | None = None


def set_run_id(run_id: str | None = None) -> str:
    """Set and return run_id for this pipeline run (for tracing)."""
    global _run_id
    _run_id = run_id or str(uuid.uuid4())[:8]
    return _run_id


def get_run_id() -> str | None:
    return _run_id


def get_logger(name: str = "pipeline") -> logging.Logger:
    """Return a logger for the pipeline. Configure once at startup if needed."""
    return logging.getLogger(name)


def _extra() -> dict:
    return {"run_id": _run_id or "-"}


def log_info(logger: logging.Logger, msg: str, **kwargs) -> None:
    """Log info with optional key=value. Avoid logging secrets."""
    if kwargs:
        safe = " ".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        logger.info("%s %s", msg, safe, extra=_extra())
    else:
        logger.info(msg, extra=_extra())


def log_warning(logger: logging.Logger, msg: str, **kwargs) -> None:
    if kwargs:
        safe = " ".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        logger.warning("%s %s", msg, safe, extra=_extra())
    else:
        logger.warning(msg, extra=_extra())


def log_error(logger: logging.Logger, msg: str, **kwargs) -> None:
    if kwargs:
        safe = " ".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        logger.error("%s %s", msg, safe, extra=_extra())
    else:
        logger.error(msg, extra=_extra())

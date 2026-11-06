"""Structlog-based structured logging configuration.

Provides a single configure_logging() function called once at app startup.
In production (APP_ENV=production) emits newline-delimited JSON.
In all other environments emits coloured console output for readability.

Usage:
    from app.core.logging import configure_logging, get_logger
    configure_logging()                       # call once in lifespan
    log = get_logger(__name__)
    log.info("segment_scored", segment_id="pune-demo-001", score=0.72)
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(app_env: str = "development") -> None:
    """Wire structlog and stdlib logging together.

    Processors applied in both modes:
      - add_log_level       — attaches level string
      - add_logger_name     — attaches module name from stdlib
      - TimeStamper(iso)    — ISO-8601 timestamp
      - CallsiteParameter   — filename + line number
      - EventRenamer        — event → message (consistent JSON key)

    Production:  JSONRenderer → stdout (newline-delimited JSON)
    Development: ConsoleRenderer (coloured, human-readable)
    """
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    is_production = app_env == "production"

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            # Prepare event_dict for stdlib logging bridge
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # Final processor: render into the chosen format
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Quiet noisy libraries
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given module name."""
    return structlog.get_logger(name)

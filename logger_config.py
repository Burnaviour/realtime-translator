"""
Centralized logging configuration for the Real-time Translator.

Usage:
    from logger_config import get_logger
    logger = get_logger("ModuleName")
    logger.info("message")
    logger.warning("something off")
    logger.error("something broke")

Logs go to:
  - Console (INFO+)
  - logs/translator.log (rotating, 5 MB per file, 3 backups, DEBUG+)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR = os.path.join(_BASE_DIR, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "translator.log")

_CONFIGURED = False


def _setup_root_logger():
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # Create logs/ directory
    os.makedirs(_LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # ── Console handler (INFO+) ─────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "[%(name)s] %(message)s"
    )
    console.setFormatter(console_fmt)
    root.addHandler(console)

    # ── File handler (DEBUG+, rotating) ─────────────────────────
    try:
        file_handler = RotatingFileHandler(
            _LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        root.addHandler(file_handler)
    except Exception as e:
        # Last resort — can't use logger here
        sys.stderr.write(f"[Logger] Could not create log file: {e}\n")


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Initialises root config on first call."""
    _setup_root_logger()
    return logging.getLogger(name)

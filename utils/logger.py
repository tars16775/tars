"""
╔══════════════════════════════════════════╗
║       TARS — Utilities: Logger           ║
╚══════════════════════════════════════════╝

Structured logging with console + file output.
"""

import logging
import os
from datetime import datetime


def setup_logger(config, base_dir):
    """Set up TARS logger with console and file handlers."""
    log_level = getattr(logging, config["agent"]["log_level"].upper(), logging.INFO)
    log_file = os.path.join(base_dir, config["agent"]["log_file"])
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger("TARS")
    if logger.handlers:
        return logger  # Already configured — avoid duplicate handlers
    logger.setLevel(log_level)

    # Console handler with colors
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console_fmt = logging.Formatter("  %(message)s")
    console.setFormatter(console_fmt)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger

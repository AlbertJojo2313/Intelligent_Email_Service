"""Centralized logging configuration for Intelligent Email Service."""

import logging
import sys

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(
    level: str | int = logging.INFO,
    format_str: str = DEFAULT_LOG_FORMAT,
    stream=sys.stdout,
) -> logging.Logger:
    """
    Configures and returns the root logger for the intelligent_email_service package.

    Args:
        level: Logging level (e.g. "INFO", "DEBUG", logging.INFO).
        format_str: Format string for log messages.
        stream: Target output stream for log messages (default: sys.stdout).

    Returns:
        The configured package logger.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    pkg_logger = logging.getLogger("intelligent_email_service")
    pkg_logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not pkg_logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setLevel(level)
        formatter = logging.Formatter(format_str)
        handler.setFormatter(formatter)
        pkg_logger.addHandler(handler)

    return pkg_logger

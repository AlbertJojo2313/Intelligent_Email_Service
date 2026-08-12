"""Unit tests for intelligent_email_service logging configuration."""

import logging

from intelligent_email_service import setup_logging


def test_setup_logging_initialization():
    logger = setup_logging(level="DEBUG")
    assert logger.name == "intelligent_email_service"
    assert logger.level == logging.DEBUG

import pytest
import logging
import io
from app.infrastructure.logging.filters import GDPRSanitizingFilter

def test_logger_with_sanitizing_filter_emits_no_sensitive_data():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(GDPRSanitizingFilter())

    logger = logging.getLogger("test_zero_leak")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("Transacción de 12345678Z con cuenta ES6621000418401234567891 finalizada.")
    output = stream.getvalue()

    assert "12345678Z" not in output
    assert "ES6621000418401234567891" not in output
    assert "12******Z" in output

import pytest
import logging
from app.infrastructure.logging.filters import GDPRSanitizingFilter

def test_gdpr_logging_filter_masks_nif_and_iban():
    filter_ = GDPRSanitizingFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Usuario 12345678Z con cuenta ES6621000418401234567891 y teléfono 600123456",
        args=(),
        exc_info=None
    )

    filter_.filter(record)

    # NIF debe estar ofuscado
    assert "12345678Z" not in record.msg
    assert "12******Z" in record.msg

    # IBAN debe estar ofuscado
    assert "ES6621000418401234567891" not in record.msg
    assert "ES66****************7891" in record.msg

def test_gdpr_logging_filter_handles_args_dict_and_tuple():
    filter_ = GDPRSanitizingFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Datos recibidos: %s y %s",
        args=("12345678Z", "ES6621000418401234567891"),
        exc_info=None
    )

    filter_.filter(record)
    for arg in record.args:
        assert "12345678Z" not in str(arg)
        assert "ES6621000418401234567891" not in str(arg)

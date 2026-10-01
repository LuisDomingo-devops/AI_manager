import logging
import re
from typing import Any

class GDPRSanitizingFilter(logging.Filter):
    """
    Filtro de logging que intercepta y censura datos personales antes de emitirlos a consola o disco.
    Garantiza la política de cero fugas (Zero-Leak) exigida por RGPD y LOPDGDD.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize_obj(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize_obj(a) for a in record.args)
            elif isinstance(record.args, list):
                record.args = [self._sanitize_obj(a) for a in record.args]

        return True

    def _sanitize_obj(self, val: Any) -> Any:
        if isinstance(val, str):
            return self._sanitize(val)
        return val

    def _sanitize(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return text

        # 1. Enmascarar IBANs (ej: ES6621000418401234567891 -> ES66****************7891)
        text = re.sub(
            r'\b([A-Z]{2}\d{2})[\s.-]?(?:\d{4}[\s.-]?){4}(\d{4})\b',
            r'\1****************\2',
            text,
            flags=re.IGNORECASE
        )

        # 2. Enmascarar NIFs / NIEs (ej: 12345678Z -> 12******Z, X1234567L -> X1******L)
        text = re.sub(
            r'\b([0-9XYZxyz]{2})\d{6}([A-Za-z])\b',
            r'\1******\2',
            text
        )

        # 3. Enmascarar Emails (ej: usuario@empresa.es -> us***@empresa.es)
        text = re.sub(
            r'\b([A-Za-z0-9._%+-]{1,2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b',
            r'\1***\2',
            text
        )

        # 4. Enmascarar Teléfonos (ej: 600123456 -> 600***456)
        text = re.sub(
            r'(?:\+\d{1,3}[\s.-]?)?\b([6789]\d{2})[\s.-]?\d{3}[\s.-]?(\d{3})\b',
            r'\1***\2',
            text
        )

        return text

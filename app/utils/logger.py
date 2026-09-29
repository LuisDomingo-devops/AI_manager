"""
LOGGER — Configuración del registro de logs y observabilidad estructurada JSON.

¿QUÉ HACE?
Define e inicializa la configuración de logs con rotación diaria para la app, el planificador y los errores,
además de emitir registros estructurados en JSON para auditoría empresarial y monitorización.

¿CUÁNDO LO HACE?
Al inicio de la aplicación y a lo largo de toda la ejecución de cualquier script del servidor.

¿CÓMO LO HACE?
Configurando handlers de la biblioteca estándar `logging`, formateador JSON canónico e inyectando request IDs y tenants.

¿CON QUÉ OTROS SCRIPTS ESTÁ RELACIONADO?
- app/main.py (middleware HTTP utiliza el logger para registrar peticiones entrantes)
"""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

FORMAT = "%(asctime)s | %(levelname)s | %(name)s | [%(request_id)s] %(message)s"
DEFAULT_REQUEST_ID = "----------"


class RequestIdFormatter(logging.Formatter):
    def format(self, record):
        if getattr(record, "request_id", None) is None:
            record.request_id = DEFAULT_REQUEST_ID
        return super().format(record)


class ColorFormatter(RequestIdFormatter):
    COLOR_MAP = {
        logging.DEBUG: "\033[94m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[95m",
    }
    RESET = "\033[0m"

    def format(self, record):
        message = super().format(record)
        color = self.COLOR_MAP.get(record.levelno, self.RESET)
        return f"{color}{message}{self.RESET}"


class JSONFormatter(logging.Formatter):
    """
    Formateador de logs estructurados en JSON canónico (RFC 8259).
    Alineado con plataformas de observabilidad empresarial (Datadog, Elastic, CloudWatch, OpenTelemetry).
    """
    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", DEFAULT_REQUEST_ID)
        
        # Obtener tenant activo si está en contexto
        tenant_id = "default"
        try:
            from app.adapters.memory.memory import tenant_context
            tenant_val = tenant_context.get()
            if tenant_val:
                tenant_id = tenant_val
        except (ImportError, AttributeError, LookupError):
            tenant_id = "default"

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id,
            "tenant_id": tenant_id,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    Handler de rotación de archivos seguro para Windows y entornos multiproceso/concurrente.
    Evita PermissionError [WinError 32] cerrando los streams antes de rotar y capturando
    bloqueos de archivo de forma tolerante a fallos para que la aplicación nunca falle.
    """
    def doRollover(self):
        if self.stream:
            try:
                self.stream.close()
            except OSError:
                pass
            self.stream = None
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # En Windows, si otro proceso o subproceso tiene el archivo abierto, continuar de forma segura
            pass
        finally:
            if not self.stream:
                try:
                    self.stream = self._open()
                except OSError:
                    pass


import re

class CredentialSanitizingFilter(logging.Filter):
    """
    Filtro de seguridad que intercepta y sanitiza credenciales, tokens y secretos
    en los mensajes de registro para evitar fugas inadvertidas en archivos de log y consola.
    """
    PATTERNS = [
        (re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'((?:password|passwd|pwd)\s*[:=]\s*[\'"]?)[^\'"\s,]+([\'"]?)', re.IGNORECASE), r'\1[REDACTED]\2'),
        (re.compile(r'((?:api[_-]?key|client[_-]?secret|auth[_-]?secret)\s*[:=]\s*[\'"]?)[^\'"\s,]+([\'"]?)', re.IGNORECASE), r'\1[REDACTED]\2'),
        (re.compile(r'((?:access[_-]?token|refresh[_-]?token)\s*[:=]\s*[\'"]?)[^\'"\s,]+([\'"]?)', re.IGNORECASE), r'\1[REDACTED]\2'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            sanitized = record.msg
            for pattern, repl in self.PATTERNS:
                sanitized = pattern.sub(repl, sanitized)
            record.msg = sanitized
        return True


formatter = RequestIdFormatter(FORMAT)
console_formatter = ColorFormatter(FORMAT)
json_formatter = JSONFormatter()

_shared_json_handler = None

def get_shared_json_handler():
    global _shared_json_handler
    if _shared_json_handler is None:
        _shared_json_handler = SafeRotatingFileHandler(
            LOG_DIR / "app.json.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            delay=True
        )
        _shared_json_handler.setFormatter(json_formatter)
        _shared_json_handler.addFilter(CredentialSanitizingFilter())
    return _shared_json_handler


def attach_request_id(logger: logging.Logger, request_id: str | None = None):
    if request_id is None:
        request_id = DEFAULT_REQUEST_ID
    return logging.LoggerAdapter(logger, {"request_id": request_id})


def build_logger(name: str, filename: str, log_to_console: bool = True):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    sanitizer = CredentialSanitizingFilter()
    logger.addFilter(sanitizer)

    # 1. Handler tradicional de texto seguro
    file_handler = SafeRotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
        delay=True
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sanitizer)
    logger.addHandler(file_handler)

    # 2. Handler estructurado JSON global compartido (singleton)
    logger.addHandler(get_shared_json_handler())

    # 3. Handler de consola
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(sanitizer)
        logger.addHandler(console_handler)

    return logger


app_logger = build_logger("app", "app.log")
tool_logger = build_logger("tools", "tools.log")
error_logger = build_logger("errors", "errors.log")
orchestrator_logger = build_logger("planner_orchestrator", "planner_orchestrator.log")
agent_logger = build_logger("agent", "agent.log")
llm_logger = build_logger("llm", "llm.log")
tool_registry_logger = build_logger("tool_registry", "tool_registry.log")
parser_logger = build_logger("parser", "parser.log")
http_logger = build_logger("http", "http.log")

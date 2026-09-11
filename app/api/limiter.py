from slowapi import Limiter
from starlette.requests import Request
import sys

def get_ip(request: Request) -> str:
    # Si estamos en testing, permitimos aislar tests con X-Forwarded-For o damos IPs únicas por defecto
    # para no saturar el límite global con los test funcionales.
    if "pytest" in sys.modules:
        if "X-Forwarded-For" in request.headers:
            return request.headers["X-Forwarded-For"]
        import uuid
        return str(uuid.uuid4())
    return request.client.host if request.client else "127.0.0.1"

limiter = Limiter(key_func=get_ip, default_limits=["100 per minute"])

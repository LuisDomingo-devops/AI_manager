# ==============================================================================
# ALFONSO AUTÓNOMO — Dockerfile de Producción Multi-Stage
# ==============================================================================

# --- Etapa 1: Builder ---
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Etapa 2: Runtime Seguro ---
FROM python:3.12-slim AS runner

WORKDIR /app

# Instalar librerías de sistema mínimas necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario sin privilegios para ejecución segura
RUN useradd -m -u 10001 appuser

# Copiar paquetes instalados desde la etapa builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copiar código de la aplicación
COPY --chown=appuser:appuser . /app

# Crear directorios de datos y logs con permisos correctos
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app/data /app/logs

USER appuser

# Exponer puerto de la API FastAPI
EXPOSE 8000

# Healthcheck de disponibilidad
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

# Comando de arranque del servidor ASGI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

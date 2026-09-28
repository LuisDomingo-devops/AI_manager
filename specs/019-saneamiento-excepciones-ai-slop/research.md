# Research & Architecture Decisions: Saneamiento de Excepciones "AI Slop" (Spec 019)

**Feature**: `019-saneamiento-excepciones-ai-slop`  
**Date**: 2026-09-28  
**Status**: Completed

---

## 1. Problema Central y Diagnóstico

El análisis forense reveló 44 bloques idénticos:
```python
except Exception:
    from app.utils.logger import error_logger
    error_logger.warning("Excepción interceptada:", exc_info=True)
```
y 51 imports tardíos de `error_logger` en 16 archivos de `app/`.

### Impacto Negativo Comprobado:
1. **Enmascaramiento de Fallos**: Errores sintácticos o de tipado (`TypeError`, `KeyError`) son interceptados como si fueran errores esperados.
2. **Violación de Integridad en Auditoría**: Mutaciones contables (como borrado suave de cliente en `billing_tools.py`) continúan aunque falle `AuditLedgerService.log_audit_event`.
3. **Inconsistencia de Identificadores**: En `create_quote`, si falla el descifrado de un ID existente, se omite el contador secuencial en vez de alertar o recuperarse controladamente.
4. **Antipatrón de Lazy Import**: Importar dentro del `except` añade sobrecarga de resolución de símbolos en tiempo de ejecución y oculta dependencias circulares no resueltas.

---

## 2. Decisiones de Diseño Técnico

### Decisión 1: Taxonomía de Excepciones Tipadas por Capa
- **Contexto**: No se puede sustituir `except Exception:` por otro bloque catch-all genérico.
- **Decisión**: Clasificar cada uno de los 44 puntos según la naturaleza real de la operación:
  - **Capa Base de Datos y Repositorios** (`billing_tools.py`, `invoice_repository.py`, `calendar_db.py`):
    - Capturar `sqlite3.Error`, `sqlite3.DatabaseError` o `KeyError` específico.
  - **Capa Criptográfica y Presupuestos** (`billing_tools.py`):
    - Capturar `(ValueError, TypeError, Exception as err)` asegurando que si falla el descifrado, se registre como `error_logger.error("Error al descifrar identificador de presupuesto: ...")` y se defina una política de fallback o propagación explícita.
  - **Capa de Auditoría y Veri*Factu** (`AuditLedgerService` en `billing_tools.py`):
    - Si falla el log de auditoría, debe emitirse un log de severidad `ERROR`/`CRITICAL`. Las operaciones no deben fingir un éxito total sin alertar de la pérdida de traza de auditoría.
  - **Capa de Validación de Hardware y Licencias** (`license_validator.py`):
    - Capturar explícitamente `(OSError, FileNotFoundError, PermissionError, AttributeError)`. En fallbacks de hardware es legítimo no tener acceso al registro de Windows o machine-id en ciertos entornos, pero debe ser tipado y limpio.
  - **Capa de Adaptadores de Red y Bancarios** (`bank_providers.py`, `gmail_sync.py`, `llm_client.py`):
    - Capturar `(httpx.HTTPError, httpx.TimeoutException, ConnectionError, KeyError)`.
  - **Capa Core / API / Utils** (`paths.py`, `logger.py`, `main.py`, `config.py`, `onboarding_router.py`):
    - Capturar `(IOError, OSError, ValueError, KeyError)`.

### Decisión 2: Centralización y Limpieza de Imports de Logger
- **Contexto**: 51 archivos contienen `from app.utils.logger import error_logger` dentro del cuerpo de la función o de la cláusula `except`.
- **Decisión**: Mover la importación a la cabecera de cada módulo (`from app.utils.logger import error_logger, app_logger`). En caso de existir import circular histórico entre `logger.py` y `paths.py`, aislar la resolución de rutas sin depender de logger en el nivel superior.

### Decisión 3: Estrategia TDD Estricta (Red-Green-Refactor)
- **Contexto**: Las reglas constitucionales exigen TDD estricto y tests unitarios, de integración y QA.
- **Decisión**: 
  - Para cada User Story (P1, P2, P3, P4):
    1. Diseñar tests específicos que simulen los errores reales (ej. desconexión de BD, error de clave criptográfica, fallo de lectura en disco).
    2. Comprobar que el test verifica el manejo tipado y rechaza el swallowing silencioso.
    3. Aplicar el saneamiento en el archivo de producción.
    4. Ejecutar la suite completa y registrar el log.

---

## 3. Alternativas Evaluadas y Descartadas

| Alternativa | Veredicto | Justificación del Rechazo |
|---|---|---|
| **Decorador global `@safe_catch`** | ❌ Descartada | Crearía una capa adicional de ofuscación que seguiría ocultando las causas raíz y manteniendo el comportamiento catch-all. |
| **Sustitución masiva con scripts regex sin tests** | ❌ Descartada | Viola la regla de TDD estricto y el saneamiento auditado. Cada bloque tiene una semántica diferente según su subsistema. |
| **Ignorar y mantener los warnings** | ❌ Descartada | Mantiene la deuda técnica de AI slop y expone el sistema a fallos regulatorios y de trazabilidad contable. |

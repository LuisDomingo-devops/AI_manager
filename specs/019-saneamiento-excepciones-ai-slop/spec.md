# Feature Specification: Saneamiento Global de Excepciones y Erradicación de "AI Slop" (Spec 019)

**Feature Branch**: `019-saneamiento-excepciones-ai-slop`  
**Created**: 2026-09-28  
**Status**: Ready for Planning  
**Input**: Saneamiento global de bloques de excepciones genéricas AI slop (`except Exception: ... error_logger.warning("Excepción interceptada:")`) en los 16 archivos del proyecto.

---

## 1. Contexto y Problema

Durante la fase de descubrimiento técnico y auditoría forense del proyecto Alfonso AI Konta, se identificó un patrón masivo y recurrente de código defensivo autogenerado ("AI Slop"):
```python
except Exception:
    from app.utils.logger import error_logger
    error_logger.warning("Excepción interceptada:", exc_info=True)
```

Este bloque se repite exactamente **44 veces** en **16 archivos** distintos de la aplicación, acompañado de **51 importaciones locales tardías** de `error_logger`. 

### Riesgos Técnicos y Regulatorios Auditados:
1. **Silenciamiento de Errores Críticos (Blind Swallowing)**: Captura indiscriminada de `Exception` que absorbe errores lógicos (`TypeError`, `KeyError`, `AttributeError`) y de infraestructura (`sqlite3.Error`, `IOError`), enmascarando bugs y generando falsos positivos en las pruebas.
2. **Infracción Regulatoria en Trazabilidad (Ley Antifraude 11/2021 y Veri*Factu)**: En `billing_tools.py`, fallos en el registro de auditoría (`AuditLedgerService.log_audit_event`) ante la eliminación de clientes son descartados con un simple warning sin abortar la transacción, violando la integridad de las trazas de auditoría.
3. **Corrupción de Secuencias de Facturación**: En la generación de IDs de presupuestos, excepciones en el descifrado (`encryptor.decrypt`) son silenciadas, saltándose el cómputo del correlativo y abriendo la puerta a colisiones de claves primarias.
4. **Degradación de Rendimiento e Higiene de Arquitectura**: Importación tardía inline repetida 51 veces en el cuerpo del bloque `except`, denotando parches improvisados para resolver dependencias circulares o imports ausentes.

---

## 2. Mapa de Archivos Afectados (16 Archivos / 44 Ocurrencias)

| # | Archivo | Ocurrencias | Capa Arquitectónica | Prioridad |
|---|---|:---:|---|---|
| 1 | `app/tools/server/billing_tools.py` | 16 | Facturación / Presupuestos / Auditoría | P1 |
| 2 | `app/infrastructure/database/repositories/invoice_repository.py` | 4 | Persistencia / Repositorios SQL | P1 |
| 3 | `app/utils/license_validator.py` | 5 | Seguridad / Validación Hardware | P2 |
| 4 | `app/infrastructure/adapters/bank_providers.py` | 4 | Integraciones / Pasarelas Bancarias | P2 |
| 5 | `app/infrastructure/adapters/llm_client.py` | 1 | Adaptadores / Cliente LLM Gemini | P2 |
| 6 | `app/domain/agents/security/security_agent.py` | 1 | Agentes Especializados / CyberAgent | P2 |
| 7 | `app/infrastructure/database/calendar_db.py` | 1 | Persistencia / Base de Datos Calendario | P3 |
| 8 | `app/infrastructure/database/memory/vector_memory.py` | 1 | Infraestructura / Memoria Vectorial | P3 |
| 9 | `app/infrastructure/adapters/gmail_sync.py` | 1 | Integraciones / Sincronización Gmail | P3 |
| 10 | `app/infrastructure/adapters/tool_registry.py` | 1 | Herramientas / Despachador de Tools | P3 |
| 11 | `app/utils/logger.py` | 3 | Utilidades / Sistema de Logs | P4 |
| 12 | `app/domain/prompt_generator.py` | 2 | Dominio / Generación de Prompts | P4 |
| 13 | `app/utils/paths.py` | 1 | Utilidades / Resolución de Rutas | P4 |
| 14 | `app/api/v1/onboarding_router.py` | 1 | API / Router Onboarding | P4 |
| 15 | `app/main.py` | 1 | Core / FastAPI Lifecycle | P4 |
| 16 | `app/config.py` | 1 | Configuración / Variables de Entorno | P4 |

---

## 3. User Scenarios y Prioridades

### User Story 1 (P1): Integridad en Facturación, Presupuestos y Repositorio de Facturas
Como sistema contable y fiscal autónomo,  
quiero que las operaciones de facturación, emisión de presupuestos correlativos y persistencia de facturas manejen excepciones tipadas y propaguen fallos de auditoría de manera estricta,  
para que ninguna transacción contable o registro de auditoría se pierda o corrompa silenciosamente.

**Criterios de Aceptación**:
1. En `app/tools/server/billing_tools.py`, todas las 16 ocurrencias de captura genérica deben sustituirse por excepciones específicas (`sqlite3.Error`, `CryptoError`, `AuditFailureError`, `ValueError`).
2. Si `AuditLedgerService.log_audit_event` falla durante una mutación crítica (ej. `DELETE_CLIENT`), la operación debe elevar una excepción controlada o registrar un error severo sin enmascarar el fallo al llamador.
3. En el descifrado de identificadores de presupuestos (`create_quote`), si un registro no se descifra, debe lanzarse una alerta estructurada en lugar de omitir ciegamente el contador correlativo.
4. En `app/infrastructure/database/repositories/invoice_repository.py`, las 4 capturas genéricas deben tiparse con errores de base de datos (`sqlite3.Error`) y evitar el swallow de errores sintácticos.
5. Los imports inline `from app.utils.logger import error_logger` deben moverse a nivel de módulo con control de importaciones circulares.

---

### User Story 2 (P2): Robustez y Tipado en Seguridad, Licencias y Conectores Bancarios
Como administrador de la plataforma,  
quiero que el validador de licencias por hardware y los conectores bancarios gestionen fallos de conectividad o I/O mediante excepciones tipadas,  
para garantizar un diagnóstico certero de integridad de máquina y pasarelas financieras.

**Criterios de Aceptación**:
1. En `app/utils/license_validator.py`, las 5 ocurrencias de excepciones en lectura de registro de Windows (`winreg`), machine-id de Linux o fallbacks MAC deben capturar específicamente `(OSError, FileNotFoundError, PermissionError, KeyError)`.
2. En `app/infrastructure/adapters/bank_providers.py`, las 4 ocurrencias deben capturar errores de red/API (`httpx.HTTPError`, `httpx.TimeoutException`, `KeyError`) registrando contexto detallado de la transacción bancaria.
3. En `app/infrastructure/adapters/llm_client.py` y `app/domain/agents/security/security_agent.py`, los bloques deben tiparse con excepciones de proveedor o validación de payload.

---

### User Story 3 (P3): Saneamiento en Infraestructura, DB Auxiliar y Herramientas
Como desarrollador de la infraestructura,  
quiero que la base de datos de calendario, memoria vectorial y sincronización de correo utilicen gestión de errores explícita,  
para evitar retornos de listas vacías o valores por defecto ante caídas reales del almacenamiento.

**Criterios de Aceptación**:
1. En `calendar_db.py`, `vector_memory.py`, `gmail_sync.py` y `tool_registry.py`, sustituir los bloques genéricos por excepciones tipadas de conexión y parsing.
2. Eliminar toda importación diferida en el bloque de captura.

---

### User Story 4 (P4): Limpieza de Logging, API, Configuración y Core
Como responsable de observabilidad,  
quiero que el sistema de logs, configuración inicial y routers API no contengan bloques catch-all redundantes,  
para que el logging sea limpio, trazable y sin imports circulares.

**Criterios de Aceptación**:
1. En `paths.py`, `logger.py`, `main.py`, `config.py`, `onboarding_router.py` y `prompt_generator.py`, reemplazar los bloques "AI slop" por captura explícita de `(IOError, ValueError, KeyError)`.
2. Garantizar que `logger.py` tenga su propia gestión sin recursión de imports.

---

## 4. Requisitos No Funcionales e Invariantes Constitucionales

- **NFR-001 (TDD Estricto)**: Cada una de las 4 User Stories debe contar con tests unitarios, de integración y QA que fuercen las condiciones de error antes del saneamiento y verifiquen el comportamiento tipado después.
- **NFR-002 (Preservación de la Suite)**: Los 512 tests existentes en la suite base deben seguir pasando al 100% sin degradación.
- **NFR-003 (0 Módulos AI Slop)**: Las 44 ocurrencias exactas y las 51 importaciones inline deben quedar reducidas a 0.
- **NFR-004 (Registro de Logs)**: Cada batería de tests ejecutada generará su archivo de log correspondiente.
- **NFR-005 (Desarrollo en Español)**: Todo el código de tests, excepciones de dominio, logs y documentación debe redactarse en castellano.

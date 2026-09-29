# Plan de Implementación: 006-stripe-idempotency

## 1. Arquitectura y Enfoque

El objetivo es solucionar la vulnerabilidad identificada en la sección 9 del Discovery Contract:
- `DATA_DIR` no existe en `paths.py`, provocando que la comprobación de idempotencia en `subscriptions_router.py` falle silenciosamente.
- Se implementará la constante canónica `DATA_DIR` en `app/utils/paths.py`.
- Se saneará el endpoint del webhook en `app/api/v1/subscriptions_router.py` para asegurar que:
  1. Si `event_id` ya está en `DATA_DIR / "stripe_events.json"`, no se produce re-aprovisionamiento y se responde `{"status": "ignored", "reason": "already_processed", "event": event_type}`.
  2. Si es la primera vez que se procesa, se registra el `event_id` y se devuelve `{"status": "processed", ...}`.
  3. No se silencian excepciones que simulen falso funcionamiento de la idempotencia.

## 2. Fases de Ejecución

- **Fase 1 (Setup)**:
  - Crear directorio de logs de ejecución: `tests/logs/spec006/`.

- **Fase 2 (TDD Red)**:
  - Crear test unitario `tests/backend/unit/test_paths_data_dir.py` verificando `DATA_DIR` en `app.utils.paths` (fallará antes de definirlo).
  - Crear test de integración `tests/backend/integration/test_stripe_webhook_idempotency_integration.py` demostrando que el segundo webhook idéntico se ignora y no re-aprovisiona el tenant.
  - Ejecutar tests y guardar logs en `tests/logs/spec006/red.log`.

- **Fase 3 (TDD Green)**:
  - Definir y exportar `DATA_DIR = Path(__file__).resolve().parents[2] / "data"` en `app/utils/paths.py`.
  - Refactorizar el bloque de idempotencia en `app/api/v1/subscriptions_router.py` para garantizar persistencia fiable y manejo adecuado de errores.
  - Ejecutar tests unitario e integración, verificando pase verde. Guardar log en `tests/logs/spec006/green.log`.

- **Fase 4 (QA y Resiliencia)**:
  - Crear test de QA `tests/backend/qa/test_stripe_idempotency_qa_suite.py` probando secuencias concurrentes y archivo de eventos corrupto o preexistente.
  - Ejecutar suite de QA y guardar log en `tests/logs/spec006/qa_green.log`.

- **Fase 5 (Validación Completa y Certificación)**:
  - Ejecutar suite completa del backend y certificar cero regresiones.
  - Consolidar commit formal en Git.

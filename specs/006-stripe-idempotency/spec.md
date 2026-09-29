# Especificación: 006-stripe-idempotency

## 1. Contexto y Hallazgo en Discovery (Sección 9 del Contrato)

En la sección 9 de `docs/audit/discovery-contract.md` se estipula la auditoría rigurosa de la idempotencia del Webhook de Stripe:
> Audita completamente la idempotencia.
> Especialmente `DATA_DIR` en `paths.py`. Comprueba si realmente existe.
> La idempotencia debe verificarse mediante un test que:
> 1. recibe webhook A;
> 2. procesa A;
> 3. recibe webhook A de nuevo;
> 4. comprueba que NO duplica efectos;
> 5. devuelve el resultado correcto.
> No aceptes un `except Exception: ...` que haga parecer que la idempotencia funciona.

### Evidencia Técnica en el Código Fuente:
1. `app/api/v1/subscriptions_router.py` (Línea 138) realiza `from app.utils.paths import DATA_DIR`.
2. `app/utils/paths.py` **no define ni exporta** `DATA_DIR`.
3. Al recibir un evento en `/api/v1/subscriptions/webhook`, Python lanza un `ImportError` al llegar a la línea 138.
4. El bloque `try/except Exception as e:` captura silenciosamente este fallo, emite un warning y continúa la ejecución sin registrar el `event_id` en el almacén de eventos.
5. Consecuencia: el control de idempotencia nunca funciona; peticiones repetidas del webhook de Stripe con el mismo `event_id` vuelven a reprocesar el aprovisionamiento de tenant de forma no idempotente.

---

## 2. Requisitos Funcionales

1. **Definición Canónica de `DATA_DIR` en `app/utils/paths.py`**:
   - `DATA_DIR` debe ser una constante `Path` exportada a nivel de módulo, apuntando al directorio `data/` en la raíz del repositorio.
   - Debe asegurar la existencia del directorio si no existe (`DATA_DIR.mkdir(parents=True, exist_ok=True)`).

2. **Idempotencia Garantizada en `/api/v1/subscriptions/webhook`**:
   - Para eventos de tipo `checkout.session.completed` o `invoice.payment_succeeded` con `event_id`:
     - Consultar el registro de eventos procesados en `DATA_DIR / "stripe_events.json"`.
     - Si `event_id` ya existe en el registro:
       - Registrar en log que el evento ya fue procesado.
       - Retornar inmediatamente `{"status": "ignored", "reason": "already_processed", "event": event_type}` con código HTTP 200.
       - **Bajo ninguna circunstancia** volver a ejecutar `TenantProvisioningService.provision_new_tenant` ni alterar la base de datos del tenant.
     - Si `event_id` es nuevo:
       - Registrar el `event_id` de forma segura y persistente en `DATA_DIR / "stripe_events.json"`.
       - Proceder al aprovisionamiento llamando a `TenantProvisioningService.provision_new_tenant`.
       - Retornar `{"status": "processed", "event": event_type, "provision": provision_result}`.
   - Eliminar el enmascaramiento permisivo de errores: los fallos reales de I/O o deserialización deben ser tratados explícitamente y con fallback seguro.

---

## 3. Plan de Pruebas (TDD)

1. **Unitario**:
   - `tests/backend/unit/test_paths_data_dir.py`:
     - Verificar que `DATA_DIR` se importa exitosamente desde `app.utils.paths`.
     - Verificar que `DATA_DIR` es una instancia de `pathlib.Path`.
     - Verificar que `DATA_DIR.exists()` es verdadero y es un directorio.

2. **Integración**:
   - `tests/backend/integration/test_stripe_webhook_idempotency_integration.py`:
     - Webhook A recibido por primera vez -> procesado (200 OK, `status: "processed"`).
     - Webhook A recibido por segunda vez -> ignorado (200 OK, `status: "ignored"`, `reason: "already_processed"`).
     - Demostrar que el aprovisionamiento (`provision_new_tenant`) no se llama en la segunda invocación.

3. **QA y Concurrencia/Persistencia**:
   - `tests/backend/qa/test_stripe_idempotency_qa_suite.py`:
     - Verificar que múltiples eventos distintos (`evt_1`, `evt_2`, `evt_3`) se procesan correctamente y sus IDs se acumulan sin borrarse.
     - Verificar resiliencia ante archivos JSON preexistentes o corruptos.

---

## 4. Archivos Afectados

- `app/utils/paths.py` (Definir y exportar `DATA_DIR`)
- `app/api/v1/subscriptions_router.py` (Saneamiento del manejo de idempotencia y eliminación de swallowing de errores)
- `tests/backend/unit/test_paths_data_dir.py` (Nuevo test unitario)
- `tests/backend/integration/test_stripe_webhook_idempotency_integration.py` (Nuevo test de integración)
- `tests/backend/qa/test_stripe_idempotency_qa_suite.py` (Nuevo test de QA)

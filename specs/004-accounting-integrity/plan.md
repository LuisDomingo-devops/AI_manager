# Plan de Implementación: 004-accounting-integrity (Integridad Contable y Libro Mayor)

## 1. Arquitectura y Enfoque de Remediación

Siguiendo la **Sección 6 del Contrato de Discovery**, se ejecutará una remediación estricta dividida en tres niveles:

### Nivel 1: Servicio de Cobros (`app/domain/services/collection_service.py`)
1. **Importación de `LedgerService`**:
   - Importar formalmente `from app.domain.services.ledger_service import LedgerService`.
2. **Atomicidad y Consistencia de Cobro + Asiento**:
   - Reestructurar el método `register_payment()` para que la inserción del pago (`payments`), la actualización de estado de la factura (`invoices`) y el registro del apunte contable (`LedgerService.record_journal_entry`) se ejecuten de forma atómica y consistente.
   - Si la generación del apunte contable falla, la transacción debe ser revertida (`conn.rollback()`) y el error debe propagarse en el retorno (`{"status": "error", "message": f"Error registrando asiento contable: {e}"}`).

### Nivel 2: Servicio Contable (`app/domain/services/ledger_service.py`)
1. **Validación de Partida Doble**:
   - Asegurar que `validate_double_entry()` verifique con precisión decimal que `round(total_debe, 2) == round(total_haber, 2)`.
2. **Bloqueo de Ejercicios Cerrados**:
   - Mantener y verificar la protección de `fiscal_year_status`, impidiendo modificaciones en ejercicios cerrados.

### Nivel 3: Aislamiento por Tenant (`app/infrastructure/database/connection_manager.py`)
1. **Verificación de Inquilinos**:
   - Garantizar que los asientos contables y cobros ejecutados bajo `tenant_context.set("tenant_a")` no sean visibles ni alteren los libros mayores de `tenant_context.set("tenant_b")`.

### Nivel 4: Metodología TDD
1. **Fase Red**:
   - Crear `tests/backend/integration/test_payment_ledger_integration.py` para demostrar el fallo del asiento inexistente tras el cobro.
2. **Fase Green**:
   - Corregir `collection_service.py`.
3. **Fase Refactor y QA**:
   - Validar contratos unitarios de partida doble y construir la suite de QA para la cadena completa.

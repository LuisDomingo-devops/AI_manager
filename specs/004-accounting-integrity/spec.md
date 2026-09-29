# Especificación: 004-accounting-integrity (Integridad Contable, Asientos y Partida Doble)

## 1. Contexto y Justificación
En la auditoría técnica del sistema (Sección 6 del Contrato de Discovery, *"LEDGER"*), se constató que `CollectionService.register_payment()` invoca `LedgerService.record_journal_entry()` sin haber importado `LedgerService`, y silencia el `NameError` resultante mediante un bloque `try/except Exception: pass`. En consecuencia, se reporta que el cobro ha sido registrado con éxito (`status: "ok"`), pero el asiento contable en el Libro Diario (`journal_entries`) y en el Libro Mayor (`ledger_entries`) nunca llega a generarse.

## 2. Definición del Problema
1. **Falta de Importación y Silenciado de Excepciones**: En `app/domain/services/collection_service.py`, la invocación a `LedgerService` produce un `NameError` que es capturado y silenciado como advertencia de log, generando falsos éxitos sin apunte contable.
2. **Violación de la Integridad Transaccional**: El registro del cobro en la tabla `payments` y la emisión del asiento en `journal_entries`/`ledger_entries` deben formar una unidad atómica o consistente: si el asiento contable falla (por ejemplo, por ejercicio cerrado o descuadre), el cobro no debe consolidarse silenciosamente como un éxito desincronizado.
3. **Validación de Partida Doble**: Todo asiento contable generado en el sistema debe satisfacer estrictamente el principio de partida doble (`total_debe == total_haber`), impidiendo que descuadres numéricos corrompan el balance.
4. **Aislamiento por Tenant (`tenant isolation`)**: Los apuntes contables y cobros de un tenant deben registrarse y consultarse exclusivamente dentro del contexto de base de datos del tenant activo (`tenant_context`), sin filtraciones entre entidades.

## 3. Comportamiento Esperado
- `LedgerService` debe estar correctamente importado y disponible en `CollectionService`.
- Cada llamada a `CollectionService.register_payment()` que culmine con éxito debe crear un asiento en `journal_entries` y sus correspondientes apuntes en `ledger_entries` (cuenta de caja/banco al Debe y cuenta 430 de clientes al Haber).
- Si la generación del apunte contable falla (ejercicio cerrado o error de validación), la operación de cobro debe revertirse y propagar un error explícito, evitando estados contables inconsistentes.
- El flujo integral `payment -> ledger entry -> double-entry -> tenant isolation` debe ser completamente auditable y verificable mediante tests automatizados sin mocks globales que oculten la persistencia real.

## 4. Criterios de Aceptación (User Stories)
- **US1 (Integración)**: `test_payment_ledger_integration.py` certifica que `CollectionService.register_payment()` genera de manera verificable el asiento en `journal_entries` y los apuntes en `ledger_entries` con sus cuentas correspondientes (570/572 al Debe, 430 al Haber).
- **US2 (Unit)**: `test_double_entry_and_fiscal_year_contracts.py` valida que `LedgerService` rechace de forma atómica asientos descuadrados (`ValueError`) o sobre ejercicios cerrados (`ValueError`), sin degradarse a excepciones genéricas.
- **US3 (QA)**: `test_accounting_integrity_governance_suite.py` valida la cadena completa: `payment -> ledger entry -> double-entry integrity -> tenant isolation`.

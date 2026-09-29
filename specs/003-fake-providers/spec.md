# Especificación: 003-fake-providers (Aislamiento y Erradicación de Proveedores Falsos)

## 1. Contexto y Justificación
En la auditoría técnica del sistema (Sección 12 del Contrato de Discovery, *"PROVEEDORES FALSOS"*), se constató que varios adaptadores bancarios en `app/infrastructure/adapters/bank_providers.py` devuelven transacciones estáticas inventadas cuando se invocan en runtime. Este comportamiento oculta la ausencia de integraciones reales y permite que datos ficticios contaminen la base de datos contable (`bank_movements`, libro mayor, balances e impuestos) a través de `BankService.sync_connection`.

## 2. Definición del Problema
1. **`GenericApiProvider`**: No implementa conexión con ninguna API bancaria real. Su método `fetch_transactions()` devuelve un movimiento estático de 100.00 €.
2. **`PlaidProvider`**: No implementa el protocolo de Plaid. Su método `get_auth_link()` apunta a `localhost` y `fetch_transactions()` devuelve un movimiento estático de 540.00 €.
3. **`QontoProvider`**: No implementa la descarga de transacciones de la API de Qonto. Su método `fetch_transactions()` devuelve un movimiento estático de -145.20 € o una lista vacía.
4. **`TinkProvider`**: Cuando no recibe credenciales válidas, recurre a transacciones estáticas hardcodeadas (1250.00 € y -85.20 €), y silencia excepciones con `except Exception: pass`.
5. **Aislamiento de Mocks**: Los datos de prueba solo deben existir dentro de `tests/fixtures` o bajo el proveedor `MockBankProvider` debidamente aislado del flujo de sincronización contable de producción.

## 3. Comportamiento Esperado
- Cualquier invocación a `fetch_transactions()` en un proveedor no implementado (`GenericApiProvider`, `PlaidProvider`, `QontoProvider`) debe lanzar explícitamente `NotImplementedError` con un mensaje descriptivo en castellano.
- Los proveedores con integración real (`GoCardlessProvider`, `TinkProvider`, `WiseProvider`, `RevolutProvider`, `StripeProvider`) deben exigir credenciales válidas. Si no se suministran credenciales, deben lanzar `ValueError` y nunca devolver transacciones ficticias de relleno.
- `MockBankProvider` queda restringido exclusivamente a entornos de test/desarrollo y su uso a través de la factoría debe estar explícitamente acotado.
- `BankService.sync_connection()` debe propagar los errores de los adaptadores y garantizar que transacciones no verificadas no se inserten en el libro de movimientos bancarios.

## 4. Criterios de Aceptación (User Stories)
- **US1 (Unit)**: `test_bank_providers_fake_rejection.py` certifica que `GenericApiProvider.fetch_transactions`, `PlaidProvider.fetch_transactions` y `QontoProvider.fetch_transactions` lanzan `NotImplementedError`, y que `TinkProvider.fetch_transactions` sin credenciales lanza `ValueError` sin inventar movimientos.
- **US2 (Integration)**: `test_bank_sync_integrity.py` certifica que `BankService.sync_connection` rechaza sincronizar proveedores no implementados sin insertar registros falsos en `bank_movements`.
- **US3 (QA)**: `test_fake_providers_governance_suite.py` valida la integridad global del catálogo bancario, asegurando que ningún proveedor registrado en producción inyecte transacciones ficticias o genere asientos contables fantasma.

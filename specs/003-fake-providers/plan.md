# Plan de Implementación: 003-fake-providers (Aislamiento y Erradicación de Proveedores Falsos)

## 1. Arquitectura y Enfoque de Remediación

Siguiendo la **Sección 12 del Contrato de Discovery**, se ejecutará una remediación estricta dividida en tres niveles:

### Nivel 1: Adaptadores Bancarios (`app/infrastructure/adapters/bank_providers.py`)
1. **Proveedores sin API real (`GenericApiProvider`, `PlaidProvider`)**:
   - `fetch_transactions`: Lanzará `NotImplementedError("El proveedor {nombre} no tiene integración de descarga de transacciones implementada.")`.
   - `get_auth_link` y `confirm_auth`: Lanzarán `NotImplementedError`.
2. **`QontoProvider`**:
   - `fetch_transactions`: Lanzará `NotImplementedError("La descarga de transacciones vía API de Qonto no está implementada.")`.
3. **`TinkProvider`**:
   - Erradicar la generación de movimientos estáticos cuando `client_id` es vacío o mock.
   - Si no hay credenciales, lanzar `ValueError("Credenciales de Tink no configuradas.")`.
   - Reemplazar `except Exception: pass` por captura y registro de errores de red transparentes.
4. **`WiseProvider`, `RevolutProvider`, `StripeProvider`**:
   - Asegurar que la ausencia de credenciales lance `ValueError` en lugar de devolver datos simulados en producción.
5. **`MockBankProvider`**:
   - Mantenerlo exclusivamente como proveedor de test con prefijo/identificador claro.

### Nivel 2: Servicio Bancario (`app/domain/services/bank_service.py`)
- Asegurar que `BankService.sync_connection` capture ordenadamente `NotImplementedError` o `ValueError` emitidos por adaptadores incompletos y los registre en el log sin corromper la tabla `bank_movements`.

### Nivel 3: Tests (TDD Estricto)
- **Unitario**: `tests/backend/unit/test_bank_providers_fake_rejection.py` (Red -> Green).
- **Integración**: `tests/backend/integration/test_bank_sync_integrity.py` (Red -> Green).
- **QA**: `tests/backend/qa/test_fake_providers_governance_suite.py` (Red -> Green).
- **Ajuste de tests unitarios existentes**: Actualizar `tests/backend/unit/test_bank_providers_unit.py` para que verifique `NotImplementedError` en lugar de esperar datos estáticos inventados.

## 2. Metodología TDD
1. **Fase Red**: Escribir los tests específicos y verificar que fallan porque el código actual todavía devuelve datos ficticios.
2. **Fase Green**: Modificar `bank_providers.py` para erradicar las transacciones ficticias y lanzar las excepciones pertinentes.
3. **Fase Refactor**: Limpiar tests preexistentes y ejecutar suite completa con volcado de logs.

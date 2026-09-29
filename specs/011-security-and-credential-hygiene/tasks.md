# Tareas de Implementación: 011-security-and-credential-hygiene

## Phase 1: Setup

- [x] T001 Crear entorno y directorio para logs de ejecución de pruebas en `tests/logs/spec011/`.

---

## Phase 2: User Story 1 (P1) — TDD RED

**Meta**: Demostrar con evidencia que `Settings` expone `ALFONSO_CLIENT_TOKENS` en su `repr`, y que el logging carece de filtro sanitizador de credenciales.

### Tests TDD (Fase RED)
- [x] T002 [P] [US1] Crear test unitario en `tests/backend/unit/test_credential_and_secret_hygiene.py` verificando `repr=False` en `ALFONSO_CLIENT_TOKENS`, existencia y funcionamiento de `CredentialSanitizingFilter`, y uso de UTC en `AuthService`.
- [x] T003 [P] [US1] Crear test de integración en `tests/backend/integration/test_auth_credential_leak_prevention_integration.py` simulando peticiones con tokens y claves y verificando que los registros de log nunca almacenen el secreto en claro.
- [x] T004 [US1] Ejecutar los tests en fase RED y guardar log en `tests/logs/spec011/us1_red.log`.

---

## Phase 3: User Story 2 (P1) — Implementación TDD GREEN

**Meta**: Saneamiento de `app/config.py`, `app/utils/logger.py` y `app/domain/services/auth_service.py`.

### Implementación (Fase GREEN)
- [x] T005 [US2] En `app/config.py`, marcar `ALFONSO_CLIENT_TOKENS: str = Field(default="", repr=False)`.
- [x] T006 [US2] En `app/utils/logger.py`, implementar `CredentialSanitizingFilter` y registrarlo en `file_handler`, `console_handler` y `_shared_json_handler`.
- [x] T007 [US2] En `app/domain/services/auth_service.py`, reemplazar `datetime.utcnow()` por `datetime.now(timezone.utc)`.
- [x] T008 [US2] Ejecutar `test_credential_and_secret_hygiene.py` y `test_auth_credential_leak_prevention_integration.py` y guardar log en `tests/logs/spec011/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — Suite de QA

**Meta**: Certificar que ningún endpoint ni handler de auditoría exponga credenciales.

### Tests QA
- [x] T009 [P] [US3] Crear suite de QA en `tests/backend/qa/test_credential_sanitization_qa_suite.py` auditando payloads confidenciales en endpoints y formateadores JSON.
- [x] T010 [US3] Ejecutar `test_credential_sanitization_qa_suite.py` y guardar log en `tests/logs/spec011/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T011 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar 0 regresiones.
- [x] T012 Consolidar commit formal de entrega de la Spec 011.

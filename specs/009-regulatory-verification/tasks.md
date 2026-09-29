# Tareas de Implementación: 009-regulatory-verification

## Phase 1: Setup y Preparación de Entorno

- [x] T001 Crear directorio para logs de ejecución de pruebas en `tests/logs/spec009/`.

---

## Phase 2: User Story 1 (P1) — TDD RED (Fallo Verificado por Claims Absolutos no Homologados)

**Meta**: Demostrar con evidencia reproducible que la Declaración Responsable y los servicios emiten claims categóricos ("cumple íntegramente") y no catalogan capacidades no certificadas como UNVERIFIED.

### Tests TDD (Fase RED)
- [x] T002 [P] [US1] Crear test unitario en `tests/backend/unit/test_regulatory_claims_classification.py` que compruebe que `get_compliance_declaration_dossier()` debe devolver `status == "draft"`, `regulatory_status == "UNVERIFIED"`, no contener "cumple íntegramente", y que `generate_alta_afi()` debe incluir `regulatory_status == "UNVERIFIED"`.
- [x] T003 [P] [US1] Crear test de integración en `tests/backend/integration/test_compliance_router_regulatory_integrity.py` que invoque el endpoint `GET /compliance/declaration` y espere la clasificación `draft` y `UNVERIFIED`.
- [x] T004 [US1] Ejecutar los tests en fase RED y guardar log de evidencia en `tests/logs/spec009/us1_red.log`.

---

## Phase 3: User Story 2 (P1) — Implementación TDD GREEN

**Meta**: Clasificar formalmente como UNVERIFIED los componentes regulatorios y marcar la Declaración Responsable como borrador técnico.

### Implementación (Fase GREEN)
- [x] T005 [US2] En `app/domain/services/verifactu_service.py`, modificar `get_compliance_declaration_dossier` para emitir `status: "ok"`, `declaration_state: "draft"`, `regulatory_status: "UNVERIFIED"` y reformular el texto de la declaración eliminando afirmaciones absolutas.
- [x] T006 [US2] En `app/tools/server/advisor_tools.py`, actualizar `get_compliance_declaration_dossier` para incluir el aviso explícito de borrador técnico no homologado.
- [x] T007 [US2] En `app/domain/services/tgss_affiliation_service.py`, incluir `regulatory_status: "UNVERIFIED"` en los diccionarios de respuesta y persistencia de registros AFI.
- [x] T008 [US2] Ejecutar `test_regulatory_claims_classification.py` y `test_compliance_router_regulatory_integrity.py`, registrando pase a verde en `tests/logs/spec009/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — QA y Auditoría de Claims Regulatorios

**Meta**: Certificar que ningún módulo del sistema realice claims categóricos sobre Veri*Factu, SILTRA o AEAT sin contrastación oficial.

### Tests QA
- [x] T009 [P] [US3] Crear suite de QA en `tests/backend/qa/test_regulatory_audit_claims_qa_suite.py` auditando exhaustivamente los payloads y textos emitidos por compliance y nóminas.
- [x] T010 [US3] Ejecutar `test_regulatory_audit_claims_qa_suite.py` y guardar log en `tests/logs/spec009/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T011 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar 0 regresiones.
- [x] T012 Consolidar commit formal de entrega de la Spec 009.

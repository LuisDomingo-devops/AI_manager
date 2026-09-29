# Plan de Implementación: 009-regulatory-verification

## 1. Arquitectura y Enfoque

El objetivo es alinear el sistema con las directrices regulatorias de Discovery (Secciones 14 y 15):
- No se pueden afirmar cumplimientos normativos categóricos ("cumple íntegramente") sin verificación oficial.
- La Declaración Responsable debe marcarse como `draft` (borrador) con `regulatory_status: "UNVERIFIED"`.
- Los ficheros AFI de TGSS deben catalogarse formalmente como `regulatory_status: "UNVERIFIED"`.
- Se eliminará cualquier lenguaje absoluto que no esté verificado por fuentes oficiales o certificación AEAT.

## 2. Fases de Ejecución

- **Fase 1 (Setup)**:
  - Crear directorio para logs en `tests/logs/spec009/`.

- **Fase 2 (TDD Red)**:
  - Crear test unitario `tests/backend/unit/test_regulatory_claims_classification.py` que compruebe la ausencia de claims absolutos y la presencia de `status == "draft"` y `regulatory_status == "UNVERIFIED"`.
  - Crear test de integración `tests/backend/integration/test_compliance_router_regulatory_integrity.py` validando la API de compliance.
  - Ejecutar tests en fase RED y guardar log de evidencia en `tests/logs/spec009/us1_red.log`.

- **Fase 3 (TDD Green)**:
  - En `app/domain/services/verifactu_service.py`: actualizar `get_compliance_declaration_dossier` para retornar `status: "draft"`, `regulatory_status: "UNVERIFIED"` y reformular la declaración como borrador técnico.
  - En `app/tools/server/advisor_tools.py`: etiquetar la declaración con `[BORRADOR TÉCNICO]`.
  - En `app/domain/services/tgss_affiliation_service.py`: agregar metadatos `regulatory_status: "UNVERIFIED"` en los métodos de generación de ficheros AFI.
  - Ejecutar tests unitario e integración para verificar pase a verde y registrar en `tests/logs/spec009/us2_green.log`.

- **Fase 4 (QA y Resiliencia)**:
  - Crear `tests/backend/qa/test_regulatory_audit_claims_qa_suite.py` auditando exhaustivamente que no haya claims falsos en toda la capa de compliance.
  - Ejecutar suite de QA y guardar log en `tests/logs/spec009/us3_green.log`.

- **Fase 5 (Validación Completa y Certificación)**:
  - Ejecutar suite completa de backend y certificar cero regresiones.
  - Consolidar commit formal en Git.

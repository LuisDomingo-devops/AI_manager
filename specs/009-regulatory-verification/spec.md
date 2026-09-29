# Especificación: 009-regulatory-verification

## 1. Contexto y Hallazgo en Discovery (Secciones 14 y 15 del Contrato)

En las secciones 14 y 15 de `docs/audit/discovery-contract.md` y en las reglas de saneamiento se establece:
> - Los claims regulatorios deben clasificarse como VERIFIED, UNVERIFIED, CONFLICTING, INCORRECT o NOT_IMPLEMENTED.
> - AFI TGSS: El formato `EMP*0111*...*MA*...` no debe considerarse válido sin fuente oficial. Clasificar como UNVERIFIED.
> - Declaración Responsable: Busca cualquier funcionalidad que afirme `"cumple íntegramente con la normativa"`. No permitas esa afirmación mientras la implementación no haya sido formalmente verificada. La declaración debe marcarse como borrador (`draft`) y no afirmar cumplimiento no demostrado.

### Evidencia Técnica en el Código Fuente:
1. En `app/domain/services/verifactu_service.py` (Línea 998), `get_compliance_declaration_dossier()` afirma categóricamente que el SIF *"cumple íntegramente con todos los requisitos establecidos en el artículo 29.2.j) de la Ley 58/2003 (LGT)..."*, y devuelve `"status": "ok"` como si estuviese formalmente homologado.
2. En `app/tools/server/advisor_tools.py` (Línea 104), `get_compliance_declaration_dossier()` emite una declaración sin advertir su condición de borrador técnico no homologado.
3. En `app/domain/services/tgss_affiliation_service.py`, se genera un formato inventado `EMP*0111*...*MA*...` para el Sistema RED sin metadatos de clasificación que aclaren que su validez ante SILTRA es `UNVERIFIED`.

---

## 2. Requisitos Funcionales

1. **Declaración Responsable y Expediente Técnico**:
   - En `VerifactuService.get_compliance_declaration_dossier()`:
     - El estado devuelto debe ser `status: "draft"` con `regulatory_status: "UNVERIFIED"`.
     - El texto de la declaración debe modificarse para reflejar con honestidad técnica que es un *diseño técnico preliminar en fase de certificación/evaluación técnica (borrador)*, eliminando la aserción no demostrada de *"cumple íntegramente"*.
     - En el expediente de evidencias técnicas, marcar las capacidades no contrastadas en entorno real con la AEAT como `UNVERIFIED_PENDING_AEAT_VALIDATION`.
2. **Herramienta del Asesor (`advisor_tools.py`)**:
   - Marcar el resultado de la Declaración Responsable explícitamente con `status: "draft"` y encabezado `[BORRADOR TÉCNICO - PENDIENTE DE HOMOLOGACIÓN OFICIAL]`.
3. **Ficheros AFI de TGSS (`tgss_affiliation_service.py`)**:
   - Los registros y resultados de generación de ficheros AFI deben incluir el atributo `regulatory_status: "UNVERIFIED"` y advertir en el log y respuesta que el formato plano es experimental y requiere validación formal en SILTRA.

---

## 3. Plan de Pruebas (TDD)

1. **Unitario**:
   - `tests/backend/unit/test_regulatory_claims_classification.py`:
     - Verificar que `VerifactuService.get_compliance_declaration_dossier()` devuelve `status == "draft"` y `regulatory_status == "UNVERIFIED"`.
     - Verificar que el texto de la declaración no contiene la frase prohibida *"cumple íntegramente"*.
     - Verificar que `TgssAffiliationService.generate_alta_afi()` incluye `regulatory_status == "UNVERIFIED"`.

2. **Integración**:
   - `tests/backend/integration/test_compliance_router_regulatory_integrity.py`:
     - Invocar `GET /compliance/declaration` y validar que el payload retornado por la API expone `status == "draft"` y `regulatory_status == "UNVERIFIED"`.

3. **QA**:
   - `tests/backend/qa/test_regulatory_audit_claims_qa_suite.py`:
     - Auditoría exhaustiva sobre los endpoints de compliance y tools de advisor para certificar que ningún componente emite claims absolutos o no demostrados.

---

## 4. Archivos Afectados

- `app/domain/services/verifactu_service.py`
- `app/tools/server/advisor_tools.py`
- `app/domain/services/tgss_affiliation_service.py`
- `tests/backend/unit/test_regulatory_claims_classification.py`
- `tests/backend/integration/test_compliance_router_regulatory_integrity.py`
- `tests/backend/qa/test_regulatory_audit_claims_qa_suite.py`

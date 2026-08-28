# Pruebas de Control de Calidad y Resiliencia (QA & Resilience Tests)

Este directorio contiene las pruebas de control de calidad (QA), suites de resiliencia y simulaciones de negocio de Alfonso Autónomo. Su objetivo es validar el sistema a **nivel de negocio**, garantizando que el comportamiento de Alfonso cumple con las directivas comerciales, las reglas fiscales de la AEAT, las cuotas de licencias mensuales y que se comporta de forma estable ante caídas de red y escenarios extremos de carga.

## ¿Qué se testea en esta carpeta?

Las pruebas de QA y control de calidad cubren los siguientes aspectos críticos:

1. **Planes de Suscripción y Licenciamiento**:
   - [`test_tier_feature_gating_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_tier_feature_gating_suite.py): Restricción y desbloqueo selectivo de herramientas (Basic, Pro, Advisor) de acuerdo a la licencia instalada.
   - [`test_license_validator.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_license_validator.py) y [`test_license_grace_period.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_license_grace_period.py): Verificación del periodo de cortesía de 5 días tras el impago mensual y bloqueo automático una vez expirado.
   - [`test_onboarding_and_licensing_issuer_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_onboarding_and_licensing_issuer_suite.py): Flujo del asistente de bienvenida y emisión segura de licencias mediante firma de clave asimétrica.

2. **Suites de Negocio por Fases**:
   - [`test_phase1_compliance_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_phase1_compliance_suite.py): Requisitos Veri*Factu (encadenamiento local inviolable, almacenamiento en archivo fiscal del PDF, etc.).
   - [`test_phase2_accounting_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_phase2_accounting_suite.py): Contabilidad de partida doble bajo el Plan General de Contabilidad (PGC), generación automática de asientos en el Libro Diario y Mayor a partir de facturas emitidas y recibidas.
   - [`test_phase3_b2b_advisor_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_phase3_b2b_advisor_suite.py): Intercambio de facturas y comunicación con la asesoría externa a través del portal B2B.
   - [`test_phase4_infra_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_phase4_infra_suite.py): Integridad del almacenamiento, backups y tolerancia a fallos del hardware.
   - [`test_phase5_audit_remediation_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_phase5_audit_remediation_suite.py): Proceso de auto-corrección automática del registro en caso de inconsistencias de base de datos.

3. **Pruebas de Resiliencia y QA de Veri*Factu**:
   - [`test_verifactu_qa_resilience_suite.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_verifactu_qa_resilience_suite.py): Simulación de caídas temporales de los servidores de la AEAT, reintentos exponenciales automáticos sin bucles infinitos y persistencia en local para envío posterior.
   - [`test_verifactu_qa_stress.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_verifactu_qa_stress.py): Resiliencia del encadenamiento criptográfico con caracteres no ASCII, caracteres especiales y colisiones en la cola de envío.

4. **Pruebas de Estrés y Rotura de QA**:
   - [`test_qa_stress.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/qa/test_qa_stress.py): Simulación de campañas de control de calidad intensivas alternando chats y facturación concurrente, y el test de ruptura de generación/OCR para encontrar el punto exacto de crash del sistema.

---

## Cómo ejecutar las pruebas de QA

Para ejecutar únicamente los tests de este directorio:
```powershell
pytest tests/qa/
```

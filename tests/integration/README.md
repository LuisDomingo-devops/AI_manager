# Pruebas de Integración e Integridad (Integration & Integrity Tests)

Este directorio contiene las pruebas de integración e integridad de Alfonso Autónomo. A diferencia de las pruebas unitarias, el propósito de las pruebas de integración es verificar la correcta comunicación, interacción y flujo de datos entre **múltiples componentes y capas** del sistema (como los controladores de API, la base de datos SQLite física, el sistema de archivos, el bus de eventos y el motor de contabilidad).

## ¿Qué se testea en esta carpeta?

Las pruebas de integración de este directorio cubren los siguientes flujos de negocio e integridad:

1. **Gestión de Facturación y Cumplimiento (Veri*Factu)**:
   - [`test_verifactu.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_verifactu.py) y [`test_verifactu_anulacion.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_verifactu_anulacion.py): Registro y anulación de facturas con firmas encadenadas.
   - [`test_verifactu_integrity.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_verifactu_integrity.py): Validación criptográfica de hashes acumulados y encadenamiento inalterable del registro de auditoría local.
   - [`test_verifactu_real_soap.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_verifactu_real_soap.py): Serialización de mensajes XML SOAP y manejo de respuestas simuladas del webservice de la AEAT.
   - [`test_verifactu_sif_migration_integration.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_verifactu_sif_migration_integration.py): Migración de registros de facturas legados y ciclo de vida de los logs SIF.

2. **Open Banking y Conciliación Bancaria**:
   - [`test_banking_callback_integration.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_banking_callback_integration.py): Integración del webhook de callback bancario (conciliación automática y actualización de cobros).
   - [`test_bank_multibank.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_bank_multibank.py): Cuentas bancarias unificadas.
   - [`test_gocardless_provider.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_gocardless_provider.py): Integración con la API GoCardless (Nordigen) para importar extractos bancarios reales.

3. **Capa Web, Rutas y Controladores**:
   - [`test_routes.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_routes.py): Comprobación de que todos los endpoints HTTP principales devuelven respuestas válidas.
   - [`test_rbac_and_auth.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_rbac_and_auth.py): Validación de restricciones de seguridad (RBAC), tokens de sesión y llamadas no autorizadas.
   - [`test_multi_tenant_isolation.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_multi_tenant_isolation.py): Aislamiento estricto de base de datos y archivos entre diferentes clientes (Multi-tenant).

4. **Operaciones del Asistente (Herramientas / Tools)**:
   - [`test_mail_operations.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_mail_operations.py) y [`test_mail.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_mail.py): Procesamiento e indexación de correos.
   - [`test_calendar.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_calendar.py): Creación y sincronización de eventos de agenda.
   - [`test_dehu_processing.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_dehu_processing.py): Descarga, descifrado y lectura automática de notificaciones de la Dirección Electrónica Habilitada Única (DEHú).

5. **Pruebas de Estrés de Integración**:
   - [`test_integration_stress.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/integration/test_integration_stress.py): Concurrencia de base de datos SQLite física y llamadas al endpoint de creación de facturas.

---

## Cómo ejecutar las pruebas de integración

Para ejecutar únicamente los tests de este directorio:
```powershell
pytest tests/integration/
```

# Alfonso — Plan de Finalización (finish.md)

Este documento detalla el orden de ejecución de las tareas pendientes para convertir a Alfonso en un producto comercializable y seguro, basado en la priorización de la auditoría de `docs/CHECKLIST_ANOTADO_ALFONSO.md`.

---

## 📋 Lista de Tareas Priorizadas

### Fase 0: P0 Crítico — Seguridad y Estabilidad de Entorno
- [ ] **Tarea 0.1: Asegurar Endpoints de Memoria**  
  * **Problema:** Los endpoints `/memory`, `/memory/{session_id}` y `DELETE /memory/{session_id}` en `app/api/routes.py` no están protegidos con la API Key (`Depends(verify_api_key)`). Cualquiera puede acceder, leer o borrar el historial.
  * **Solución:** Añadir la dependencia de verificación de API Key a estos routers/endpoints.
  * **Validación:** Test unitario en `tests/test_routes.py` y `tests/test_rbac_and_auth.py` verificando que devuelven `401 Unauthorized` si no se envía la clave correcta.

- [ ] **Tarea 0.2: Evitar Fallo de Inicio por Carpeta "landing_page" Inexistente**  
  * **Problema:** En `app/main.py`, la línea `app.mount("/", StaticFiles(directory=str(Path(__file__).parent.parent / "landing_page"), html=True), name="landing")` produce un error crítico si la carpeta no existe, deteniendo toda la ejecución de tests.
  * **Solución:** Comprobar si existe el directorio antes de montarlo. Si no existe, crear un endpoint de fallback o crear la carpeta vacía.
  * **Validación:** Ejecución de la suite completa de tests de forma local sin errores de inicialización de la app.

- [ ] **Tarea 0.3: Mínimo Privilegio de Roles (Eliminar admin por defecto)**  
  * **Problema:** Si no hay `client_id` o no tiene un rol configurado en `ALFONSO_CLIENT_ROLES`, el fallback por defecto es `admin`.
  * **Solución:** Cambiar el comportamiento de fallback a `guest` o `limitado` para asegurar que el sistema esté cerrado por defecto.
  * **Validación:** Test unitario que simule un cliente sin rol asignado y verifique que no puede ejecutar herramientas administrativas.

---

### Fase 1: P1 MVP Comercial
- [ ] **Tarea 1.1: CRUD Completo de Clientes y Validación de NIF/CIF**  
  * **Descripción:** Implementar la actualización (update) y eliminación (delete) de la tabla `clients`. Añadir validación formal de NIF/CIF en la creación de clientes.
  * **Validación:** Tests de integración del CRUD y de formato correcto de NIF/CIF.

- [ ] **Tarea 1.2: Reemplazo de Mocks de Transacciones en Open Banking**  
  * **Descripción:** Conectar `fetch_transactions` de GoCardless con datos reales en lugar de los mocks hardcodeados actuales.
  * **Validación:** Simulación o tests de integración usando las credenciales/entorno sandbox de GoCardless.

- [ ] **Tarea 1.3: Módulo de Presupuestos (Quotes)**  
  * **Descripción:** Diseñar la entidad `Quote` en DB, generar PDFs con ReportLab y permitir la conversión directa de presupuesto a factura.
  * **Validación:** Test de flujo completo: Crear presupuesto -> Generar PDF -> Convertir a Factura.

- [ ] **Tarea 1.4: Módulo de Productos y Servicios**  
  * **Descripción:** Añadir catálogo de productos y servicios con sus respectivos precios e IVAs por defecto.
  * **Validación:** CRUD de productos.

- [ ] **Tarea 1.5: Entidad Cobros/Pagos (Payments)**  
  * **Descripción:** Crear entidad `Payment` para registrar cobros parciales, saldos pendientes y control de recordatorios de cobro.
  * **Validación:** Pruebas unitarias de flujo de pagos parciales contra facturas.

---

### Fase 2: P2 Diferenciación (Motor Fiscal y Human-in-the-Loop)
- [ ] **Tarea 2.1: Motor Fiscal Determinista e Inmutable**  
  * **Descripción:** Extraer las reglas fiscales de `TaxParserService` (regex e inline calculations) hacia un módulo independiente y versionado de reglas deterministas.
  * **Validación:** Comparativa de cálculo automático vs módulo versionado.

- [ ] **Tarea 2.2: Flujos de Confirmación Explícita (Human-in-the-loop)**  
  * **Descripción:** Implementar confirmación para conciliar movimientos, presentar impuestos y operaciones bancarias, y eliminación de datos contables.
  * **Validación:** Intentar operaciones críticas sin token de confirmación y verificar el bloqueo.

- [ ] **Tarea 2.3: Previsión de Cash-Flow (Tesorería)**  
  * **Descripción:** Módulo de previsión a 7/30/90 días y alertas de liquidez automatizadas.
  * **Validación:** Test del algoritmo de predicción con datos históricos.

---

### Fase 3: P3 Escalado e Infraestructura
- [ ] **Tarea 3.1: Multi-tenant Aislado por Empresa**  
  * **Descripción:** Separación física o lógica real de bases de datos por tenant (`client_id`), no dependiente de licencias premium para el aislamiento de datos.
  * **Validación:** Intentos de acceso cruzado entre tenants.

- [ ] **Tarea 3.2: Registro Estructurado de Logs y Auditoría Inmutable**  
  * **Descripción:** Implementar JSON logging y correlation ID para auditorías inmutables de tool-calls.
  * **Validación:** Verificación de formato JSON estructurado en consola y archivos de log.

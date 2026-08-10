# Roadmap — AI Manager / Alfonso

## Objetivo

Convertir Alfonso desde un agente IA generalista en un agente fiscal, contable y financiero para autónomos y pequeñas empresas.

El objetivo no es construir un clon de Sage o Anfix, sino que Alfonso pueda utilizar servicios de facturación, contabilidad, gestión bancaria y fiscalidad mediante una interfaz conversacional y un sistema de agentes capaz de ejecutar tareas.

---

# 1. Arquitectura base

## 1.1 Revisar arquitectura hexagonal

- [ ] Revisar estructura actual del proyecto.
- [ ] Separar claramente `domain`, `application`, `infrastructure` y `adapters`.
- [ ] Eliminar dependencias del dominio respecto a FastAPI.
- [ ] Eliminar dependencias del dominio respecto al LLM.
- [ ] Eliminar dependencias del dominio respecto a Ollama.
- [ ] Eliminar dependencias del dominio respecto a PostgreSQL/SQLite/etc.
- [ ] Definir interfaces/puertos para servicios externos.
- [ ] Definir adaptadores para cada infraestructura.
- [ ] Revisar dependencias entre módulos.
- [ ] Aplicar Dependency Inversion.
- [ ] Aplicar Single Responsibility.
- [ ] Aplicar Open/Closed.
- [ ] Aplicar Interface Segregation.
- [ ] Revisar cumplimiento general de SOLID.

# 2. Bounded Contexts

Crear una separación clara entre los principales dominios.

```text
domain/
├── billing/
├── accounting/
├── banking/
├── taxation/
├── customers/
└── advisor/
```

## 2.1 Facturación

- [ ] Crear bounded context `billing`.
- [ ] Definir entidades.
- [ ] Definir value objects.
- [ ] Definir reglas de negocio.
- [ ] Definir casos de uso.
- [ ] Definir puertos.
- [ ] Crear repositorios.
- [ ] Crear tests unitarios.

## 2.2 Contabilidad

- [ ] Crear bounded context `accounting`.
- [ ] Definir entidades contables.
- [ ] Definir reglas contables.
- [ ] Definir casos de uso.
- [ ] Definir puertos.
- [ ] Crear repositorios.
- [ ] Crear tests unitarios.

## 2.3 Bancos

- [ ] Crear bounded context `banking`.
- [ ] Definir cuentas bancarias.
- [ ] Definir movimientos.
- [ ] Definir conciliación.
- [ ] Definir reglas bancarias.
- [ ] Crear puertos para Open Banking.
- [ ] Crear adaptadores.
- [ ] Crear tests.

## 2.4 Fiscalidad

- [ ] Crear bounded context `taxation`.
- [ ] Definir impuestos.
- [ ] Definir tipos de IVA.
- [ ] Definir IRPF.
- [ ] Definir períodos fiscales.
- [ ] Definir obligaciones fiscales.
- [ ] Definir modelos fiscales.
- [ ] Crear motor de cálculo.
- [ ] Crear tests fiscales.

# 3. Facturación

## 3.1 Clientes

- [ ] Crear entidad `Customer`.
- [ ] Añadir NIF/CIF.
- [ ] Añadir nombre/razón social.
- [ ] Añadir dirección.
- [ ] Añadir email.
- [ ] Añadir teléfono.
- [ ] Añadir condiciones de pago.
- [ ] Añadir estado del cliente.
- [ ] Crear historial del cliente.
- [ ] Crear CRUD.
- [ ] Crear API.
- [ ] Crear tests.

# 4. Productos y servicios

- [ ] Crear entidad `Product`.
- [ ] Crear entidad `Service`.
- [ ] Añadir descripción.
- [ ] Añadir referencia.
- [ ] Añadir precio.
- [ ] Añadir unidad.
- [ ] Añadir tipo de IVA.
- [ ] Añadir retención IRPF cuando corresponda.
- [ ] Crear CRUD.
- [ ] Crear tests.

# 5. Presupuestos

- [ ] Crear entidad `Quote`.
- [ ] Crear líneas de presupuesto.
- [ ] Implementar cálculo de subtotal.
- [ ] Implementar IVA.
- [ ] Implementar descuentos.
- [ ] Implementar total.
- [ ] Implementar estados.
- [ ] Crear conversión presupuesto → factura.
- [ ] Crear PDF.
- [ ] Crear envío por email.
- [ ] Crear tests.

Estados:

```text
DRAFT
SENT
ACCEPTED
REJECTED
EXPIRED
CONVERTED
```

# 6. Facturas

- [ ] Crear entidad `Invoice`.
- [ ] Crear `InvoiceLine`.
- [ ] Implementar numeración.
- [ ] Implementar series.
- [ ] Implementar fecha.
- [ ] Implementar vencimiento.
- [ ] Implementar IVA.
- [ ] Implementar IRPF.
- [ ] Implementar descuentos.
- [ ] Implementar suplidos.
- [ ] Implementar cálculo automático de totales.
- [ ] Implementar estados.
- [ ] Implementar factura rectificativa.
- [ ] Implementar facturas recurrentes.
- [ ] Implementar duplicación.
- [ ] Implementar PDF.
- [ ] Implementar envío por email.
- [ ] Crear tests.

Estados:

```text
DRAFT
ISSUED
SENT
PARTIALLY_PAID
PAID
OVERDUE
CANCELLED
RECTIFIED
```

# 7. Cobros

- [ ] Crear entidad `Payment`.
- [ ] Relacionar pagos con facturas.
- [ ] Implementar pagos parciales.
- [ ] Implementar pagos completos.
- [ ] Detectar facturas vencidas.
- [ ] Calcular saldo pendiente.
- [ ] Crear listado de cobros pendientes.
- [ ] Crear recordatorios.
- [ ] Crear tests.

# 8. Contabilidad

## 8.1 Plan contable

- [ ] Crear entidad `Account`.
- [ ] Crear jerarquía de cuentas.
- [ ] Implementar códigos contables.
- [ ] Implementar cuentas de activo.
- [ ] Implementar cuentas de pasivo.
- [ ] Implementar patrimonio neto.
- [ ] Implementar ingresos.
- [ ] Implementar gastos.
- [ ] Crear plan contable configurable.

Ejemplo:

```text
430 Clientes
400 Proveedores
472 IVA soportado
477 IVA repercutido
570 Caja
572 Bancos
600 Compras
700 Ventas
```

# 9. Asientos contables

- [ ] Crear entidad `JournalEntry`.
- [ ] Crear `JournalEntryLine`.
- [ ] Implementar debe.
- [ ] Implementar haber.
- [ ] Validar que debe = haber.
- [ ] Asociar documentos.
- [ ] Asociar facturas.
- [ ] Asociar movimientos bancarios.
- [ ] Generar asientos automáticamente.
- [ ] Implementar asientos manuales.
- [ ] Implementar asientos periódicos.
- [ ] Crear tests.

# 10. Libros contables

- [ ] Implementar libro diario.
- [ ] Implementar libro mayor.
- [ ] Implementar balance de comprobación.
- [ ] Implementar sumas y saldos.
- [ ] Implementar exportación.
- [ ] Implementar filtros por período.
- [ ] Implementar filtros por cuenta.
- [ ] Crear tests.

# 11. Estados financieros

- [ ] Implementar cuenta de pérdidas y ganancias.
- [ ] Implementar balance de situación.
- [ ] Implementar patrimonio neto.
- [ ] Implementar resultados acumulados.
- [ ] Implementar informes financieros.
- [ ] Implementar comparación entre períodos.
- [ ] Crear tests.

# 12. Cierre contable

- [ ] Implementar cierre de ejercicio.
- [ ] Implementar regularización.
- [ ] Implementar asiento de cierre.
- [ ] Implementar apertura del ejercicio siguiente.
- [ ] Impedir modificaciones indebidas en ejercicios cerrados.
- [ ] Crear auditoría.
- [ ] Crear tests.

# 13. Gestión bancaria

## 13.1 Cuentas bancarias

- [ ] Crear entidad `BankAccount`.
- [ ] Añadir IBAN.
- [ ] Añadir entidad bancaria.
- [ ] Añadir moneda.
- [ ] Añadir saldo.
- [ ] Añadir estado.
- [ ] Crear CRUD.
- [ ] Crear tests.

# 14. Open Banking

- [ ] Investigar proveedores de Open Banking disponibles en España.
- [ ] Comparar proveedores.
- [ ] Seleccionar proveedor.
- [ ] Crear interfaz `BankingProvider`.
- [ ] Implementar autenticación segura.
- [ ] Implementar conexión bancaria.
- [ ] Implementar sincronización.
- [ ] Implementar renovación de autorización.
- [ ] Implementar desconexión.
- [ ] No almacenar credenciales bancarias.
- [ ] Cifrar información sensible.
- [ ] Registrar auditoría.
- [ ] Crear tests.

# 15. Movimientos bancarios

- [ ] Crear entidad `BankTransaction`.
- [ ] Importar movimientos.
- [ ] Guardar fecha.
- [ ] Guardar concepto.
- [ ] Guardar importe.
- [ ] Guardar saldo.
- [ ] Guardar referencia.
- [ ] Detectar duplicados.
- [ ] Clasificar movimientos.
- [ ] Crear historial.
- [ ] Crear tests.

# 16. Conciliación bancaria

- [ ] Crear entidad `Reconciliation`.
- [ ] Relacionar movimiento con factura.
- [ ] Detectar coincidencias automáticas.
- [ ] Detectar coincidencias por importe.
- [ ] Detectar coincidencias por fecha.
- [ ] Detectar coincidencias por cliente.
- [ ] Crear puntuación de confianza.
- [ ] Proponer conciliaciones al usuario.
- [ ] Permitir aceptación manual.
- [ ] Permitir rechazo.
- [ ] Registrar decisiones.
- [ ] Crear tests.

# 17. Reglas bancarias

- [ ] Crear sistema de reglas.
- [ ] Permitir reglas por proveedor.
- [ ] Permitir reglas por concepto.
- [ ] Permitir reglas por importe.
- [ ] Permitir reglas por categoría.
- [ ] Aplicar reglas automáticamente.
- [ ] Permitir modificar reglas.
- [ ] Registrar cambios.

# 18. Gestión de pagos

- [ ] Detectar pagos pendientes.
- [ ] Detectar facturas vencidas.
- [ ] Crear calendario de pagos.
- [ ] Calcular pagos previstos.
- [ ] Clasificar pagos.
- [ ] Crear alertas.
- [ ] Crear informes.

# 19. Cash-flow

- [ ] Calcular liquidez actual.
- [ ] Calcular cobros previstos.
- [ ] Calcular pagos previstos.
- [ ] Calcular impuestos previstos.
- [ ] Crear previsión a 7 días.
- [ ] Crear previsión a 30 días.
- [ ] Crear previsión a 90 días.
- [ ] Detectar problemas de liquidez.
- [ ] Generar recomendaciones.
- [ ] Crear tests.

# 20. OCR y documentos

- [ ] Crear servicio OCR.
- [ ] Procesar facturas.
- [ ] Procesar tickets.
- [ ] Extraer NIF.
- [ ] Extraer proveedor.
- [ ] Extraer fecha.
- [ ] Extraer número de factura.
- [ ] Extraer base imponible.
- [ ] Extraer IVA.
- [ ] Extraer total.
- [ ] Extraer IRPF.
- [ ] Detectar documentos duplicados.
- [ ] Asociar documento con factura.
- [ ] Asociar documento con asiento.
- [ ] Crear sistema de confianza OCR.
- [ ] Solicitar confirmación cuando la confianza sea baja.

# 21. Fiscalidad

## IVA

- [ ] Implementar IVA soportado.
- [ ] Implementar IVA repercutido.
- [ ] Calcular IVA trimestral.
- [ ] Implementar modelo 303.
- [ ] Implementar modelo 390.
- [ ] Validar operaciones.
- [ ] Crear tests fiscales.

## IRPF

- [ ] Implementar IRPF.
- [ ] Implementar modelo 130.
- [ ] Implementar modelo 131.
- [ ] Implementar retenciones.
- [ ] Crear tests.

## Otros modelos

- [ ] Modelo 111.
- [ ] Modelo 115.
- [ ] Modelo 180.
- [ ] Modelo 190.
- [ ] Modelo 347.
- [ ] Modelo 349.
- [ ] Modelo 200.
- [ ] Modelo 202.

# 22. Veri*Factu

- [ ] Estudiar especificaciones técnicas oficiales.
- [ ] Crear motor determinista de generación de registros.
- [ ] Implementar hash.
- [ ] Implementar encadenamiento.
- [ ] Implementar integridad.
- [ ] Implementar trazabilidad.
- [ ] Implementar registro de eventos.
- [ ] Implementar conservación.
- [ ] Implementar generación de registros.
- [ ] Implementar mecanismos de comunicación con AEAT cuando corresponda.
- [ ] Crear tests de conformidad.
- [ ] Crear auditoría.

> IMPORTANTE: La lógica fiscal y Veri*Factu no debe depender del LLM.

# 23. Factura electrónica

- [ ] Investigar requisitos de factura electrónica en España.
- [ ] Definir formato soportado.
- [ ] Generar factura electrónica.
- [ ] Validar factura electrónica.
- [ ] Recibir factura electrónica.
- [ ] Almacenar factura electrónica.
- [ ] Gestionar estados.
- [ ] Preparar integración con sistemas externos.

# 24. Relación empresa ↔ asesor

## Empresa

- [ ] Crear cuenta de empresa.
- [ ] Crear usuarios.
- [ ] Crear roles.
- [ ] Permitir invitar asesor.
- [ ] Compartir documentación.
- [ ] Compartir información fiscal.
- [ ] Compartir información contable.
- [ ] Compartir información bancaria.

## Asesor

- [ ] Crear perfil de asesor.
- [ ] Crear cartera de clientes.
- [ ] Acceder a empresas autorizadas.
- [ ] Revisar documentos.
- [ ] Revisar contabilidad.
- [ ] Revisar impuestos.
- [ ] Solicitar documentación.
- [ ] Crear comentarios.
- [ ] Resolver incidencias.

## Comunicación

- [ ] Crear sistema de mensajes.
- [ ] Crear notificaciones.
- [ ] Crear solicitudes de documentación.
- [ ] Crear tareas.
- [ ] Crear historial de comunicación.

# 25. Agente IA

Esta es la principal ventaja competitiva de Alfonso.

## Comprensión

- [ ] Interpretar preguntas fiscales.
- [ ] Interpretar preguntas contables.
- [ ] Interpretar preguntas financieras.
- [ ] Detectar intención.
- [ ] Identificar entidades.
- [ ] Mantener contexto.

# 26. Ejecución mediante herramientas

Crear tools específicas:

```text
create_customer
create_invoice
create_quote
send_invoice
register_payment
get_pending_invoices
get_bank_transactions
reconcile_transaction
get_accounting_balance
get_profit_loss
get_cash_flow
calculate_vat
calculate_irpf
prepare_tax_return
request_document
send_to_advisor
```

- [ ] Definir cada tool.
- [ ] Definir contratos.
- [ ] Validar inputs.
- [ ] Validar permisos.
- [ ] Registrar ejecución.
- [ ] Crear tests.

# 27. Human-in-the-loop

Alfonso no debe ejecutar determinadas operaciones automáticamente.

Crear niveles de autorización:

```text
LOW_RISK
MEDIUM_RISK
HIGH_RISK
```

### Automático

- [ ] Leer facturas.
- [ ] Clasificar documentos.
- [ ] Analizar movimientos.

### Requiere confirmación

- [ ] Crear factura.
- [ ] Enviar factura.
- [ ] Conciliar movimiento.
- [ ] Modificar datos contables.

### Requiere autorización explícita

- [ ] Presentar impuestos.
- [ ] Modificar declaraciones.
- [ ] Realizar operaciones bancarias.
- [ ] Eliminar información contable.

# 28. Auditoría

- [ ] Registrar todas las acciones del agente.
- [ ] Registrar usuario.
- [ ] Registrar fecha.
- [ ] Registrar tool utilizada.
- [ ] Registrar parámetros.
- [ ] Registrar resultado.
- [ ] Registrar autorización.
- [ ] Registrar errores.
- [ ] Crear historial inmutable.
- [ ] Permitir auditoría.

# 29. Seguridad

- [ ] Implementar autenticación.
- [ ] Implementar autorización.
- [ ] RBAC.
- [ ] Separación de tenants.
- [ ] Cifrado de datos sensibles.
- [ ] Gestión segura de secretos.
- [ ] Protección de credenciales bancarias.
- [ ] Rate limiting.
- [ ] Auditoría.
- [ ] Gestión de sesiones.
- [ ] Protección contra prompt injection.
- [ ] Validación de outputs del LLM.
- [ ] Nunca confiar directamente en decisiones fiscales generadas por el LLM.

# 30. Base de datos

Diseñar modelo multi-tenant.

```text
Tenant
 ├── Users
 ├── Customers
 ├── Products
 ├── Invoices
 ├── Payments
 ├── BankAccounts
 ├── BankTransactions
 ├── Accounts
 ├── JournalEntries
 ├── TaxPeriods
 └── Documents
```

- [ ] Diseñar esquema.
- [ ] Crear migraciones.
- [ ] Crear índices.
- [ ] Definir constraints.
- [ ] Definir relaciones.
- [ ] Implementar soft delete cuando corresponda.
- [ ] Implementar auditoría.

# 31. API

- [ ] Diseñar API REST.
- [ ] Documentar OpenAPI.
- [ ] Implementar endpoints de clientes.
- [ ] Implementar endpoints de facturación.
- [ ] Implementar endpoints contables.
- [ ] Implementar endpoints bancarios.
- [ ] Implementar endpoints fiscales.
- [ ] Implementar endpoints de asesor.
- [ ] Implementar autenticación.
- [ ] Implementar autorización.
- [ ] Crear tests de integración.

# 32. Tests

## Unitarios

- [ ] Dominio.
- [ ] Facturación.
- [ ] Contabilidad.
- [ ] Bancos.
- [ ] Fiscalidad.

## Integración

- [ ] Base de datos.
- [ ] API.
- [ ] Open Banking.
- [ ] OCR.
- [ ] LLM.
- [ ] Sistema de herramientas.

## End-to-end

- [ ] Crear cliente.
- [ ] Crear factura.
- [ ] Registrar pago.
- [ ] Conciliar banco.
- [ ] Generar asiento.
- [ ] Calcular IVA.
- [ ] Preparar declaración.

# 33. Observabilidad

- [ ] Logging estructurado.
- [ ] Correlation ID.
- [ ] Métricas.
- [ ] Tracing.
- [ ] Monitorización de agentes.
- [ ] Monitorización de tools.
- [ ] Monitorización de errores.
- [ ] Monitorización de costes LLM.
- [ ] Alertas.

# 34. MVP recomendado

No implementar inicialmente todo Sage/Anfix.

## Facturación

- [ ] Clientes.
- [ ] Productos/servicios.
- [ ] Facturas.
- [ ] Presupuestos.
- [ ] IVA.
- [ ] IRPF.
- [ ] PDF.
- [ ] Estados.
- [ ] Cobros.

## Bancos

- [ ] Importación de movimientos.
- [ ] Cuentas bancarias.
- [ ] Conciliación.
- [ ] Clasificación.
- [ ] Cobros/pagos.

## Contabilidad

- [ ] Plan contable.
- [ ] Asientos.
- [ ] Libro diario.
- [ ] Libro mayor.
- [ ] Balance.
- [ ] Pérdidas y ganancias.

## Fiscalidad

- [ ] IVA.
- [ ] IRPF.
- [ ] Modelo 303.
- [ ] Modelo 130.
- [ ] Calendario fiscal.

## IA

- [ ] Consultas en lenguaje natural.
- [ ] Creación de facturas mediante conversación.
- [ ] Análisis de gastos.
- [ ] Análisis bancario.
- [ ] Conciliación asistida.
- [ ] Cálculo de impuestos.
- [ ] Detección de anomalías.
- [ ] Generación de informes.
- [ ] Human-in-the-loop.

# 35. Primera versión comercial

## "¿Cuánto IVA tengo que pagar?"

- [ ] Analizar facturas emitidas.
- [ ] Analizar facturas recibidas.
- [ ] Calcular IVA.
- [ ] Explicar cálculo.
- [ ] Mostrar operaciones utilizadas.

## "Crea una factura"

- [ ] Identificar cliente.
- [ ] Identificar importe.
- [ ] Calcular impuestos.
- [ ] Crear factura.
- [ ] Solicitar confirmación.
- [ ] Emitir/enviar.

## "¿Quién me debe dinero?"

- [ ] Analizar facturas.
- [ ] Analizar pagos.
- [ ] Calcular pendientes.
- [ ] Mostrar vencidas.

## "¿Cuánto dinero tengo?"

- [ ] Consultar bancos.
- [ ] Consultar pagos.
- [ ] Consultar cobros.
- [ ] Consultar impuestos.
- [ ] Calcular liquidez.

## "¿Hay algo raro?"

- [ ] Analizar movimientos.
- [ ] Detectar duplicados.
- [ ] Detectar facturas anómalas.
- [ ] Detectar gastos inusuales.
- [ ] Detectar descuadres contables.
- [ ] Informar al usuario.

# 36. Prioridad general

## P0 — Crítico

- [ ] Arquitectura hexagonal.
- [ ] Dominio de facturación.
- [ ] Clientes.
- [ ] Facturas.
- [ ] IVA.
- [ ] Contabilidad básica.
- [ ] Asientos.
- [ ] Bancos.
- [ ] Movimientos bancarios.
- [ ] Conciliación.
- [ ] Sistema de tools del agente.
- [ ] Seguridad.
- [ ] Auditoría.

## P1 — MVP comercial

- [ ] Presupuestos.
- [ ] Cobros.
- [ ] Pagos.
- [ ] Pérdidas y ganancias.
- [ ] Balance.
- [ ] Modelo 303.
- [ ] Modelo 130.
- [ ] OCR.
- [ ] Cash-flow.
- [ ] Relación con asesor.
- [ ] Human-in-the-loop.

## P2 — Diferenciación

- [ ] Veri*Factu.
- [ ] Factura electrónica.
- [ ] Predicción de cash-flow.
- [ ] Detección avanzada de anomalías.
- [ ] Automatización fiscal.
- [ ] Reglas inteligentes.
- [ ] Agente proactivo.
- [ ] Integraciones bancarias avanzadas.

## P3 — Escalado

- [ ] Multiempresa.
- [ ] Multiusuario.
- [ ] Marketplace.
- [ ] API pública.
- [ ] Integraciones con Sage.
- [ ] Integraciones con Anfix.
- [ ] Integraciones con otras plataformas.
- [ ] Aplicación móvil.
- [ ] Ecosistema para asesorías.

# 37. Arquitectura objetivo

```text
Usuario
    ↓
Alfonso
    ↓
Agente IA
    ↓
Planner / Orchestrator
    ↓
Application Layer
    ↓
┌───────────────┬──────────────┬──────────────┐
│ Facturación   │ Contabilidad │ Bancos       │
└───────────────┴──────────────┴──────────────┘
                    ↓
               Fiscalidad
                    ↓
          Infraestructura / APIs
                    ↓
        AEAT / Bancos / Asesoría
```

## Principio estratégico

El objetivo no es:

> "Construir otro Anfix."

El objetivo es:

> **Construir un agente capaz de utilizar las capacidades de un sistema contable y fiscal por el usuario.**

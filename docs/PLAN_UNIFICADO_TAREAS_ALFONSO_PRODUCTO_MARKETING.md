# Alfonso --- Plan Unificado de Tareas

## Producto, Ingeniería, Cumplimiento y Marketing

**Objetivo:** convertir Alfonso en un producto profesional de gestión
fiscal, contable y financiera para autónomos y pequeñas empresas,
manteniendo la propuesta: **"Tú llevas el negocio. Alfonso lleva la
gestión."**

------------------------------------------------------------------------

# 0. Priorización

-   [ ] **P0 --- Crítico:** seguridad, cumplimiento, integridad,
    arquitectura y datos fiscales.
-   [ ] **P1 --- MVP comercial:** funcionalidades necesarias para
    generar valor real y cobrar.
-   [ ] **P2 --- Diferenciación:** capacidades competitivas.
-   [ ] **P3 --- Escalado:** integraciones, multiempresa, API, móvil y
    ecosistema.

El objetivo no es construir un clon de Sage o Anfix, sino permitir que
Alfonso utilice capacidades de facturación, contabilidad, banca y
fiscalidad mediante conversación y herramientas.

------------------------------------------------------------------------

# 1. PRODUCTO --- Arquitectura y calidad

## 1.1 Arquitectura hexagonal

-   [ ] Revisar estructura actual.
-   [ ] Separar `domain`, `application`, `infrastructure` y `adapters`.
-   [ ] Eliminar dependencias del dominio respecto a FastAPI.
-   [ ] Eliminar dependencias del dominio respecto al LLM.
-   [ ] Eliminar dependencias del dominio respecto a Ollama.
-   [ ] Eliminar dependencias del dominio respecto a bases de datos
    concretas.
-   [ ] Definir interfaces/puertos.
-   [ ] Crear adaptadores.
-   [ ] Revisar dependencias entre módulos.
-   [ ] Aplicar Dependency Inversion.
-   [ ] Aplicar Single Responsibility.
-   [ ] Aplicar Open/Closed.
-   [ ] Aplicar Interface Segregation.
-   [ ] Revisar SOLID.
-   [ ] Simplificar módulos excesivamente grandes.
-   [ ] Actualizar documentación para reflejar la arquitectura real.

## 1.2 Bounded Contexts

-   [ ] `billing`.
-   [ ] `accounting`.
-   [ ] `banking`.
-   [ ] `taxation`.
-   [ ] `customers`.
-   [ ] `advisor`.
-   [ ] Definir entidades, value objects, reglas, casos de uso, puertos
    y repositorios.
-   [ ] Crear tests unitarios por contexto.

## 1.3 Orquestación y tools

-   [ ] Revisar y simplificar Planner/Orchestrator.
-   [ ] Crear entidad `Task`.
-   [ ] Separar planificación y ejecución.
-   [ ] Crear Tool Executor.
-   [ ] Normalizar resultados de tools.
-   [ ] Definir contratos de entrada/salida.
-   [ ] Validar inputs.
-   [ ] Validar permisos.
-   [ ] Registrar ejecuciones.
-   [ ] Crear tests.
-   [ ] Impedir ejecución directa de operaciones críticas por el LLM.
-   [ ] Mantener las reglas fiscales fuera del LLM.

------------------------------------------------------------------------

# 2. PRODUCTO --- Seguridad, autorización y auditoría

## 2.1 Seguridad P0

-   [ ] Revisar todos los endpoints.
-   [ ] Proteger lectura y borrado de memoria/historial.
-   [ ] Implementar autorización por recurso.
-   [ ] Implementar RBAC (control de acceso basado en roles).
-   [ ] Aplicar mínimo privilegio.
-   [ ] Eliminar cualquier rol administrativo por defecto.
-   [ ] Gestionar sesiones.
-   [ ] Rate limiting.
-   [ ] Gestión segura de secretos.

## 2.2 Multi-tenant

-   [ ] Diseñar aislamiento por empresa.
-   [ ] Asociar todos los recursos al tenant correcto.
-   [ ] Impedir acceso cruzado.
-   [ ] Crear tests de aislamiento.
-   [ ] Auditar endpoints por fugas de datos.

## 2.3 Datos sensibles

-   [ ] Cifrar datos sensibles.
-   [ ] Proteger credenciales bancarias.
-   [ ] Eliminar NIF, emails y datos fiscales ficticios por defecto.
-   [ ] Bloquear producción si faltan datos fiscales obligatorios.
-   [ ] Evitar información sensible en logs.

## 2.4 Human-in-the-loop

### Automático

-   [ ] Leer facturas.
-   [ ] Clasificar documentos.
-   [ ] Analizar movimientos.

### Requiere confirmación

-   [ ] Crear factura.
-   [ ] Enviar factura.
-   [ ] Conciliar movimiento.
-   [ ] Modificar datos contables.

### Requiere autorización explícita

-   [ ] Presentar impuestos.
-   [ ] Modificar declaraciones.
-   [ ] Realizar operaciones bancarias.
-   [ ] Eliminar información contable.

## 2.5 Auditoría

-   [ ] Registrar usuario.
-   [ ] Registrar tenant.
-   [ ] Registrar fecha/hora.
-   [ ] Registrar tool.
-   [ ] Registrar parámetros.
-   [ ] Registrar resultado.
-   [ ] Registrar autorización.
-   [ ] Registrar errores.
-   [ ] Crear historial inmutable.
-   [ ] Permitir auditoría.

------------------------------------------------------------------------

# 3. PRODUCTO --- Base de datos y API

## 3.1 Modelo

-   [ ] `Tenant`.
-   [ ] `Users`.
-   [ ] `Customers`.
-   [ ] `Products`.
-   [ ] `Invoices`.
-   [ ] `Payments`.
-   [ ] `BankAccounts`.
-   [ ] `BankTransactions`.
-   [ ] `Accounts`.
-   [ ] `JournalEntries`.
-   [ ] `TaxPeriods`.
-   [ ] `Documents`.
-   [ ] Diseñar esquema.
-   [ ] Crear migraciones.
-   [ ] Crear índices.
-   [ ] Definir constraints.
-   [ ] Definir relaciones.
-   [ ] Soft delete cuando corresponda.
-   [ ] Auditoría.

## 3.2 API

-   [ ] Diseñar API REST.
-   [ ] Documentar OpenAPI.
-   [ ] Endpoints de clientes.
-   [ ] Endpoints de facturación.
-   [ ] Endpoints contables.
-   [ ] Endpoints bancarios.
-   [ ] Endpoints fiscales.
-   [ ] Endpoints de asesor.
-   [ ] Autenticación.
-   [ ] Autorización.
-   [ ] Tests de integración.

------------------------------------------------------------------------

# 4. PRODUCTO --- Facturación

## 4.1 Clientes

-   [ ] Entidad `Customer`.
-   [ ] NIF/CIF.
-   [ ] Nombre/razón social.
-   [ ] Dirección.
-   [ ] Email.
-   [ ] Teléfono.
-   [ ] Condiciones de pago.
-   [ ] Estado.
-   [ ] Historial.
-   [ ] CRUD.
-   [ ] API.
-   [ ] Tests.
-   [ ] Validación de NIF/CIF.

## 4.2 Productos y servicios

-   [ ] Entidad `Product`.
-   [ ] Entidad `Service`.
-   [ ] Descripción.
-   [ ] Referencia.
-   [ ] Precio.
-   [ ] Unidad.
-   [ ] Tipo de IVA.
-   [ ] Retención IRPF cuando corresponda.
-   [ ] CRUD.
-   [ ] Tests.

## 4.3 Presupuestos

-   [ ] Entidad `Quote`.
-   [ ] Líneas.
-   [ ] Subtotal.
-   [ ] IVA.
-   [ ] Descuentos.
-   [ ] Total.
-   [ ] Estados.
-   [ ] Conversión presupuesto → factura.
-   [ ] PDF.
-   [ ] Email.
-   [ ] Tests.

Estados: `DRAFT`, `SENT`, `ACCEPTED`, `REJECTED`, `EXPIRED`,
`CONVERTED`.

## 4.4 Facturas

-   [ ] Entidad `Invoice`.
-   [ ] `InvoiceLine`.
-   [ ] Numeración fiscal robusta.
-   [ ] Series.
-   [ ] Ejercicio.
-   [ ] Fecha.
-   [ ] Vencimiento.
-   [ ] IVA.
-   [ ] IRPF.
-   [ ] Descuentos.
-   [ ] Suplidos.
-   [ ] Cálculo automático de totales.
-   [ ] Validaciones matemáticas.
-   [ ] Facturas rectificativas.
-   [ ] Facturas recurrentes.
-   [ ] Duplicación controlada.
-   [ ] PDF.
-   [ ] Email.
-   [ ] Tests unitarios e integración.
-   [ ] Pruebas de concurrencia y ausencia de duplicidades.

Estados: `DRAFT`, `ISSUED`, `SENT`, `PARTIALLY_PAID`, `PAID`, `OVERDUE`,
`CANCELLED`, `RECTIFIED`.

## 4.5 Cobros

-   [ ] Entidad `Payment`.
-   [ ] Relacionar pagos con facturas.
-   [ ] Pagos parciales.
-   [ ] Pagos completos.
-   [ ] Facturas vencidas.
-   [ ] Saldo pendiente.
-   [ ] Cobros pendientes.
-   [ ] Recordatorios.
-   [ ] Tests.

------------------------------------------------------------------------

# 5. PRODUCTO --- OCR y documentos

-   [ ] Servicio OCR.
-   [ ] Facturas.
-   [ ] Tickets.
-   [ ] PDF.
-   [ ] NIF.
-   [ ] Proveedor.
-   [ ] Fecha.
-   [ ] Número de factura.
-   [ ] Base imponible.
-   [ ] IVA.
-   [ ] Total.
-   [ ] IRPF.
-   [ ] Datos obligatorios ausentes.
-   [ ] Coherencia base/IVA/IRPF/total.
-   [ ] Tipos de IVA.
-   [ ] Documentos duplicados.
-   [ ] Asociación documento ↔ factura.
-   [ ] Asociación documento ↔ asiento.
-   [ ] Puntuación de confianza.
-   [ ] Confirmación cuando la confianza sea baja.
-   [ ] No inventar valores fiscales cuando falten.
-   [ ] Registrar correcciones.
-   [ ] Dataset de pruebas anonimizado.
-   [ ] Medir precisión por campo.

------------------------------------------------------------------------

# 6. PRODUCTO --- Contabilidad

## 6.1 Plan contable

-   [ ] Entidad `Account`.
-   [ ] Jerarquía.
-   [ ] Códigos.
-   [ ] Activo.
-   [ ] Pasivo.
-   [ ] Patrimonio neto.
-   [ ] Ingresos.
-   [ ] Gastos.
-   [ ] Plan configurable.

## 6.2 Asientos

-   [ ] `JournalEntry`.
-   [ ] `JournalEntryLine`.
-   [ ] Debe.
-   [ ] Haber.
-   [ ] Validar debe = haber.
-   [ ] Asociar documentos.
-   [ ] Asociar facturas.
-   [ ] Asociar bancos.
-   [ ] Asientos automáticos.
-   [ ] Asientos manuales.
-   [ ] Asientos periódicos.
-   [ ] Tests.

## 6.3 Libros y estados

-   [ ] Libro diario.
-   [ ] Libro mayor.
-   [ ] Balance de comprobación.
-   [ ] Sumas y saldos.
-   [ ] Exportación.
-   [ ] Filtros por período/cuenta.
-   [ ] Pérdidas y ganancias.
-   [ ] Balance de situación.
-   [ ] Patrimonio neto.
-   [ ] Resultados acumulados.
-   [ ] Informes financieros.
-   [ ] Comparación entre períodos.
-   [ ] Tests.

## 6.4 Cierre

-   [ ] Cierre de ejercicio.
-   [ ] Regularización.
-   [ ] Asiento de cierre.
-   [ ] Apertura siguiente.
-   [ ] Bloqueo de modificaciones indebidas.
-   [ ] Auditoría.
-   [ ] Tests.

------------------------------------------------------------------------

# 7. PRODUCTO --- Bancos y tesorería

## 7.1 Cuentas

-   [ ] `BankAccount`.
-   [ ] IBAN.
-   [ ] Entidad bancaria.
-   [ ] Moneda.
-   [ ] Saldo.
-   [ ] Estado.
-   [ ] CRUD.
-   [ ] Tests.

## 7.2 Open Banking

-   [ ] Definir puerto.
-   [ ] Implementar agregador real.
-   [ ] Sustituir mocks.
-   [ ] Consentimiento.
-   [ ] Renovación.
-   [ ] Sincronización.
-   [ ] Errores.
-   [ ] Reintentos.
-   [ ] Tests de integración.
-   [ ] Documentar permisos de lectura.

## 7.3 Movimientos

-   [ ] `BankTransaction`.
-   [ ] Importación.
-   [ ] Fecha.
-   [ ] Concepto.
-   [ ] Importe.
-   [ ] Saldo.
-   [ ] Referencia.
-   [ ] Duplicados.
-   [ ] Clasificación.
-   [ ] Historial.
-   [ ] Tests.

## 7.4 Conciliación

-   [ ] `Reconciliation`.
-   [ ] Movimiento ↔ factura.
-   [ ] Coincidencia automática.
-   [ ] Coincidencia por importe.
-   [ ] Coincidencia por fecha.
-   [ ] Coincidencia por cliente/proveedor.
-   [ ] Confianza.
-   [ ] Propuesta.
-   [ ] Aceptación manual.
-   [ ] Rechazo.
-   [ ] Registro de decisiones.
-   [ ] Tests.

## 7.5 Cash-flow

-   [ ] Pagos pendientes.
-   [ ] Facturas vencidas.
-   [ ] Calendario de pagos.
-   [ ] Pagos previstos.
-   [ ] Alertas.
-   [ ] Liquidez actual.
-   [ ] Cobros previstos.
-   [ ] Pagos previstos.
-   [ ] Impuestos previstos.
-   [ ] Previsión 7 días.
-   [ ] Previsión 30 días.
-   [ ] Previsión 90 días.
-   [ ] Problemas de liquidez.
-   [ ] Recomendaciones.
-   [ ] Tests.

------------------------------------------------------------------------

# 8. PRODUCTO --- Fiscalidad

## 8.1 Motor fiscal

-   [ ] Bounded context `taxation`.
-   [ ] Impuestos.
-   [ ] Tipos IVA.
-   [ ] IRPF.
-   [ ] Períodos.
-   [ ] Obligaciones.
-   [ ] Modelos.
-   [ ] Motor determinista.
-   [ ] Separar cálculo fiscal de IA.
-   [ ] Versionar reglas.
-   [ ] Registrar fuente/versión de cada regla.
-   [ ] Tests.
-   [ ] Impedir decisiones fiscales vinculantes tomadas únicamente por
    el LLM.

## 8.2 IVA

-   [ ] IVA soportado.
-   [ ] IVA repercutido.
-   [ ] IVA trimestral.
-   [ ] Modelo 303.
-   [ ] Modelo 390.
-   [ ] Validación.
-   [ ] Tests.
-   [ ] Mostrar operaciones usadas.
-   [ ] Explicar cálculo.

## 8.3 IRPF

-   [ ] IRPF.
-   [ ] Modelo 130.
-   [ ] Modelo 131 cuando corresponda.
-   [ ] Retenciones.
-   [ ] Tests.
-   [ ] No presentar fórmulas simplificadas como liquidaciones
    definitivas.

## 8.4 Otros modelos

-   [ ] 111.
-   [ ] 115.
-   [ ] 180.
-   [ ] 190.
-   [ ] 347.
-   [ ] 349.
-   [ ] 200.
-   [ ] 202.
-   [ ] Determinar para cada modelo si se ofrece cálculo, preparación o
    presentación.

## 8.5 Calendario fiscal

-   [ ] Calendario.
-   [ ] Obligaciones según perfil.
-   [ ] Avisos.
-   [ ] Registro de obligaciones cumplidas.
-   [ ] Documentación necesaria.

------------------------------------------------------------------------

# 9. PRODUCTO --- VERI\*FACTU y AEAT

## 9.1 Especificaciones

-   [ ] Estudiar especificaciones oficiales vigentes.
-   [ ] Versionar implementación normativa.
-   [ ] Definir modelo oficial.
-   [ ] Definir campos obligatorios.
-   [ ] Definir tipos/restricciones.
-   [ ] Validaciones oficiales.

## 9.2 Registros

-   [ ] Motor determinista.
-   [ ] Registro de alta.
-   [ ] Registro de anulación.
-   [ ] Encadenamiento.
-   [ ] Integridad.
-   [ ] Trazabilidad.
-   [ ] Conservación.
-   [ ] Inalterabilidad.
-   [ ] Marca temporal.
-   [ ] Identificación correcta del sistema informático.
-   [ ] Identificación del productor cuando corresponda.
-   [ ] QR/representación exigida.
-   [ ] Casos fiscales reales.

## 9.3 AEAT

-   [ ] Comunicación oficial cuando corresponda.
-   [ ] Certificados/autenticación seguros.
-   [ ] Respuestas.
-   [ ] Errores.
-   [ ] Reintentos.
-   [ ] Idempotencia.
-   [ ] Evidencias de envío.
-   [ ] Respuestas persistidas.
-   [ ] Modo offline conforme a reglas aplicables.
-   [ ] Pruebas de entorno de pruebas.
-   [ ] No afirmar integración productiva hasta superar pruebas.

## 9.4 Declaración responsable

-   [ ] Proceso de control de versiones.
-   [ ] Preparar declaración responsable exigible.
-   [ ] Hacer visible la información requerida.
-   [ ] Asociar declaración a cada versión.
-   [ ] Crear expediente de evidencias.
-   [ ] Regresión normativa antes de cada release.

------------------------------------------------------------------------

# 10. PRODUCTO --- Factura electrónica

-   [ ] Requisitos aplicables en España.
-   [ ] Formato soportado.
-   [ ] Generación.
-   [ ] Validación.
-   [ ] Recepción.
-   [ ] Almacenamiento.
-   [ ] Estados.
-   [ ] Integraciones externas.
-   [ ] Tests.

------------------------------------------------------------------------

# 11. PRODUCTO --- Relación empresa ↔ asesor

## Empresa

-   [ ] Relación con asesor.
-   [ ] Autorizar acceso.
-   [ ] Revocar acceso.
-   [ ] Compartir documentos.
-   [ ] Compartir contabilidad.
-   [ ] Compartir información fiscal.
-   [ ] Consultar solicitudes.

## Asesor

-   [ ] Perfil.
-   [ ] Cartera.
-   [ ] Acceso sólo a empresas autorizadas.
-   [ ] Revisar documentos.
-   [ ] Revisar contabilidad.
-   [ ] Revisar impuestos.
-   [ ] Solicitar documentación.
-   [ ] Comentarios.
-   [ ] Resolver incidencias.

## Comunicación

-   [ ] Mensajes.
-   [ ] Notificaciones.
-   [ ] Solicitudes de documentación.
-   [ ] Tareas.
-   [ ] Historial.

------------------------------------------------------------------------

# 12. PRODUCTO --- Agente IA

## Comprensión

-   [ ] Preguntas fiscales.
-   [ ] Preguntas contables.
-   [ ] Preguntas financieras.
-   [ ] Intención.
-   [ ] Entidades.
-   [ ] Contexto.

## Tools

-   [ ] `create_customer`
-   [ ] `create_invoice`
-   [ ] `create_quote`
-   [ ] `send_invoice`
-   [ ] `register_payment`
-   [ ] `get_pending_invoices`
-   [ ] `get_bank_transactions`
-   [ ] `reconcile_transaction`
-   [ ] `get_accounting_balance`
-   [ ] `get_profit_loss`
-   [ ] `get_cash_flow`
-   [ ] `calculate_vat`
-   [ ] `calculate_irpf`
-   [ ] `prepare_tax_return`
-   [ ] `request_document`
-   [ ] `send_to_advisor`

Para cada tool:

-   [ ] Contrato.
-   [ ] Validación.
-   [ ] Permisos.
-   [ ] Nivel de riesgo.
-   [ ] Auditoría.
-   [ ] Tests.
-   [ ] Gestión de errores.

## Casos de uso

### "¿Cuánto IVA tengo que pagar?"

-   [ ] Analizar emitidas.
-   [ ] Analizar recibidas.
-   [ ] Calcular.
-   [ ] Explicar.
-   [ ] Mostrar operaciones.

### "Crea una factura"

-   [ ] Identificar cliente.
-   [ ] Identificar importe.
-   [ ] Calcular impuestos.
-   [ ] Crear.
-   [ ] Confirmación.
-   [ ] Emitir/enviar.

### "¿Quién me debe dinero?"

-   [ ] Analizar facturas.
-   [ ] Analizar pagos.
-   [ ] Calcular pendientes.
-   [ ] Mostrar vencidas.

### "¿Cuánto dinero tengo?"

-   [ ] Bancos.
-   [ ] Pagos.
-   [ ] Cobros.
-   [ ] Impuestos.
-   [ ] Liquidez.

### "¿Hay algo raro?"

-   [ ] Movimientos.
-   [ ] Duplicados.
-   [ ] Facturas anómalas.
-   [ ] Gastos inusuales.
-   [ ] Descuadres.
-   [ ] Informar.

------------------------------------------------------------------------

# 13. PRODUCTO --- Tests, calidad y producción

## Tests

-   [ ] Unitarios de dominio.
-   [ ] Facturación.
-   [ ] Contabilidad.
-   [ ] Bancos.
-   [ ] Fiscalidad.
-   [ ] Seguridad.
-   [ ] Tools.
-   [ ] Orquestación.
-   [ ] Integración de base de datos.
-   [ ] API.
-   [ ] Open Banking.
-   [ ] OCR.
-   [ ] LLM.
-   [ ] Sistema de tools.
-   [ ] AEAT.
-   [ ] VERI\*FACTU.

## End-to-end

-   [ ] Cliente.
-   [ ] Factura.
-   [ ] Pago.
-   [ ] Conciliación.
-   [ ] Asiento.
-   [ ] IVA.
-   [ ] Declaración.
-   [ ] Registro VERI\*FACTU.
-   [ ] Comunicación AEAT cuando corresponda.
-   [ ] Respuesta.
-   [ ] Auditoría.

## CI y observabilidad

-   [ ] Resolver bloqueos de SQLite en tests.
-   [ ] Corregir entornos virtuales rotos.
-   [ ] Corregir configuración de pytest.
-   [ ] Entorno reproducible.
-   [ ] CI limpia.
-   [ ] Cobertura mínima.
-   [ ] Regresiones.
-   [ ] Logging estructurado.
-   [ ] Correlation ID.
-   [ ] Métricas.
-   [ ] Tracing.
-   [ ] Monitorización de agentes/tools/errores.
-   [ ] Costes LLM.
-   [ ] Alertas.

## Producción

-   [ ] Configuración dev/staging/producción.
-   [ ] Docker.
-   [ ] Secretos.
-   [ ] Migraciones.
-   [ ] Backups.
-   [ ] Restauración.
-   [ ] Retención.
-   [ ] Health checks.
-   [ ] Readiness checks.
-   [ ] Rollback.
-   [ ] Versionado API.
-   [ ] Documentación de despliegue.
-   [ ] Recuperación ante incidentes.
-   [ ] Checklist de release.

------------------------------------------------------------------------

# 14. MARKETING --- Marca

## Posicionamiento

-   [ ] Concepto: **RECUPERA EL CONTROL**.
-   [ ] Claim: **"Tú llevas el negocio. Alfonso lleva la gestión."**
-   [ ] Promesa: **"Tú decides qué hacer. Alfonso hace el trabajo
    administrativo."**
-   [ ] Firma: **"Tú decides. Alfonso lo hace."**
-   [ ] Presentar Alfonso como herramienta de control y automatización.
-   [ ] Separar claramente funciones disponibles, beta y roadmap.
-   [ ] No afirmar funcionalidades no demostradas.
-   [ ] No afirmar cumplimiento VERI\*FACTU hasta superar el gate de
    conformidad.

## Propuesta de valor

-   [ ] Página de funcionalidades.
-   [ ] Página de seguridad.
-   [ ] Página fiscal.
-   [ ] Página VERI\*FACTU cuando exista implementación demostrable.
-   [ ] Página de relación con asesor.
-   [ ] Casos de uso.

------------------------------------------------------------------------

# 15. MARKETING --- Web y conversión

## Landing

-   [ ] Dominio.
-   [ ] Hosting cloud.
-   [ ] SSL.
-   [ ] Landing.
-   [ ] Hero problema/solución.
-   [ ] CTA "Prueba Gratis".
-   [ ] CTA "Ver Demo".
-   [ ] Fricciones administrativas eliminadas.
-   [ ] Casos reales.
-   [ ] Funcionalidades actuales.
-   [ ] Límites de automatización cuando proceda.
-   [ ] Analítica visitante → lead.
-   [ ] Analítica lead → registro.
-   [ ] Analítica registro → activación.

## Activación

-   [ ] Onboarding.
-   [ ] Primera acción de valor \<5 minutos.
-   [ ] Objetivo ideal \<2 minutos.
-   [ ] Subir factura / registrar gasto / conectar banco cuando esté
    disponible.
-   [ ] Resultado útil inmediato.
-   [ ] Medir activación por cohorte y canal.

------------------------------------------------------------------------

# 16. MARKETING --- SEO y contenido

## Calculadoras

-   [ ] IVA.
-   [ ] IRPF.
-   [ ] Cuota de autónomos.
-   [ ] Gastos deducibles.
-   [ ] "¿Estoy preparado para VERI\*FACTU?".
-   [ ] Captación de email cuando aporte valor.

## SEO

-   [ ] Primer lote de 20-30 contenidos de alta calidad.
-   [ ] Fiscalidad.
-   [ ] Facturación.
-   [ ] VERI\*FACTU.
-   [ ] Gastos deducibles.
-   [ ] Conciliación bancaria.
-   [ ] Modelos 303/130.
-   [ ] Medir tráfico cualificado.
-   [ ] Medir leads.
-   [ ] Medir clientes.
-   [ ] Ampliar contenido sólo según datos.

------------------------------------------------------------------------

# 17. MARKETING --- LinkedIn

## Preparación --- Días 1-14

-   [ ] Optimizar perfil del fundador.
-   [ ] Crear página de Alfonso.
-   [ ] Identidad visual.
-   [ ] Landing.
-   [ ] Enlaces de seguimiento.
-   [ ] Banco de 8-10 publicaciones.
-   [ ] Demos.

## "Recupera el control" --- Días 15-30

-   [ ] Dependencia de la gestoría.
-   [ ] Falta de visibilidad.
-   [ ] "Tú llevas el negocio. Alfonso lleva la gestión."
-   [ ] "Tú decides. Alfonso lo hace."
-   [ ] Demos.
-   [ ] Lista de espera.

## Beta --- Días 31-45

-   [ ] Demos.
-   [ ] Aprendizajes.
-   [ ] Casos de uso.
-   [ ] Contacto con autónomos.
-   [ ] Contacto con asesorías.
-   [ ] Testimonios.

## Autoridad --- Días 46-60

-   [ ] Fiscalidad.
-   [ ] Facturación.
-   [ ] VERI\*FACTU.
-   [ ] Gastos.
-   [ ] Demos.
-   [ ] Newsletter.

## Lanzamiento --- Días 61-75

-   [ ] Lanzamiento público.
-   [ ] 4-5 publicaciones durante la semana.
-   [ ] Vídeo demo.
-   [ ] Prueba gratuita.

## Conversión --- Días 76-90

-   [ ] Casos reales.
-   [ ] Objeciones.
-   [ ] Preguntas de usuarios.
-   [ ] Referidos.
-   [ ] Optimización por conversión.

## Cadencia

-   [ ] Lunes: problema.
-   [ ] Martes: demo.
-   [ ] Jueves: educación.
-   [ ] Viernes: opinión/caso.
-   [ ] 12-16 publicaciones/mes.
-   [ ] 4 demostraciones/mes.
-   [ ] Newsletter semanal "El negocio bajo control".

## KPIs

-   [ ] Visitas web cualificadas: 500-1.000 / 90 días.
-   [ ] Registros atribuidos: 50-100.
-   [ ] Activación atribuida: \>40 %.
-   [ ] Clientes de pago atribuibles: 10-20.
-   [ ] Optimizar por clientes, no por impresiones.

Embudo:

`Publicación → Perfil → Landing → Registro → Activación → Prueba → Pago → Referido`

------------------------------------------------------------------------

# 18. MARKETING --- Beta, referidos y Partners

## Beta

-   [ ] Seleccionar 50-100 usuarios.
-   [ ] Entrevistas.
-   [ ] Bugs OCR.
-   [ ] Clasificación fiscal.
-   [ ] Incidencias.
-   [ ] Cero fallos críticos antes del lanzamiento.
-   [ ] Medir NPS.

## Testimonios

-   [ ] Casos reales.
-   [ ] Autorización.
-   [ ] Casos de uso.
-   [ ] Prueba social en landing.

## Referidos

-   [ ] Programa.
-   [ ] Atribución.
-   [ ] Recompensa.
-   [ ] "Invita 3 negocios y consigue 3 meses gratis".
-   [ ] Medir clientes procedentes de referidos.

## Afiliados

-   [ ] Programa.
-   [ ] Contactar microinfluencers.
-   [ ] Priorizar acuerdos a éxito.
-   [ ] Medir CAC.
-   [ ] Medir clientes activos.
-   [ ] Escalar sólo si funciona.

## Asesorías Partners

-   [ ] Validar con 5-10 asesorías.
-   [ ] Dashboard multicliente.
-   [ ] Accesos independientes.
-   [ ] Autorizaciones.
-   [ ] Validar clientes activos aportados.
-   [ ] Escalar sólo tras validación.
-   [ ] Evaluar marca blanca cuando el volumen lo justifique.

------------------------------------------------------------------------

# 19. MARKETING --- Otros canales

## Vídeo

-   [ ] TikTok/Instagram Reels.
-   [ ] Vídeos de 30-45 segundos.
-   [ ] Comparativas de procesos tradicionales frente a Alfonso.
-   [ ] Demos.
-   [ ] YouTube 8-15 minutos.
-   [ ] Build in Public.

## Lanzamiento

-   [ ] Product Hunt.
-   [ ] Comunidades de autónomos.
-   [ ] Comunidades profesionales.
-   [ ] Reddit cuando las normas lo permitan.
-   [ ] Blogs especializados.

------------------------------------------------------------------------

# 20. MARKETING --- Presupuesto

## Máximo inicial: 1.500 €

-   [ ] Web/landing: 100-150 €.
-   [ ] Herramientas de adquisición: 350-400 €.
-   [ ] Contenido SEO: 400-450 €.
-   [ ] Afiliación/referidos: 200-250 €.
-   [ ] Reserva/experimentos: 250-300 €.
-   [ ] Publicidad LinkedIn: **0 €**.
-   [ ] Meta/Google Ads: **0 €**.

## Control

-   [ ] Separar CAC monetario y CAC total/imputado.
-   [ ] CAC por canal.
-   [ ] Conversión prueba → pago.
-   [ ] Objetivo inicial: \>8-12 %, revisado por cohorte.
-   [ ] Churn.
-   [ ] LTV como proyección hasta disponer de histórico.
-   [ ] LTV/CAC cuando exista evidencia suficiente.

------------------------------------------------------------------------

# 21. MARKETING --- Objetivos 90 días

  Escenario        Leads   Pruebas   Clientes de pago
  ------------- -------- --------- ------------------
  Mínimo             300       100                 10
  Objetivo         1.000   300-500              30-50
  Excepcional     1.500+   500-800                100

Los 100 clientes son un objetivo excepcional, no una condición de éxito.

------------------------------------------------------------------------

# 22. CALENDARIO MAESTRO --- 90 DÍAS

## Semanas 1-2

-   [ ] Seguridad P0.
-   [ ] Arquitectura crítica.
-   [ ] Landing.
-   [ ] LinkedIn.
-   [ ] Página Alfonso.
-   [ ] Analítica.
-   [ ] Contenido.
-   [ ] Preparación beta.

## Semanas 3-4

-   [ ] Calculadoras.
-   [ ] SEO inicial.
-   [ ] "Recupera el control".
-   [ ] Demos.
-   [ ] Correcciones OCR.
-   [ ] Onboarding.

## Semanas 5-6

-   [ ] 50-100 usuarios beta.
-   [ ] Entrevistas.
-   [ ] Tests.
-   [ ] Bugs.
-   [ ] Testimonios.
-   [ ] Outreach asesorías.

## Semanas 7-8

-   [ ] Activación.
-   [ ] Conversión.
-   [ ] OCR.
-   [ ] Fiscalidad.
-   [ ] Seguridad.
-   [ ] Lanzamiento.
-   [ ] Newsletter.

## Semana 9

-   [ ] Lanzamiento público.
-   [ ] Contenido coordinado.
-   [ ] Email.
-   [ ] Demo.
-   [ ] Prueba gratuita.
-   [ ] Medición.

## Semanas 10-12

-   [ ] Casos reales.
-   [ ] Objeciones.
-   [ ] Referidos.
-   [ ] Optimización onboarding.
-   [ ] Optimización LinkedIn.
-   [ ] Optimización landing.
-   [ ] CAC.
-   [ ] Conversión.
-   [ ] Retención.

------------------------------------------------------------------------

# 23. GATES DE SALIDA

## Gate 1 --- Seguridad

-   [ ] Autenticación.
-   [ ] Autorización.
-   [ ] Multi-tenant.
-   [ ] Protección de memoria.
-   [ ] Secretos.
-   [ ] Auditoría.

## Gate 2 --- Producto

-   [ ] Facturación fiable.
-   [ ] OCR con confianza/revisión.
-   [ ] Contabilidad coherente.
-   [ ] Bancos reales o limitación comunicada.
-   [ ] Motor fiscal determinista.
-   [ ] Human-in-the-loop.

## Gate 3 --- Fiscal

-   [ ] Motor fiscal validado.
-   [ ] Modelos validados.
-   [ ] Casos fiscales cubiertos.
-   [ ] Evidencias.

## Gate 4 --- VERI\*FACTU

-   [ ] Especificaciones oficiales.
-   [ ] Registro correcto.
-   [ ] Encadenamiento.
-   [ ] Integridad.
-   [ ] Comunicación AEAT cuando corresponda.
-   [ ] Errores/reintentos/idempotencia.
-   [ ] Evidencias.
-   [ ] Declaración responsable.
-   [ ] Control de versiones.

## Gate 5 --- Lanzamiento

-   [ ] Landing.
-   [ ] Onboarding.
-   [ ] Activación medida.
-   [ ] Usuarios beta.
-   [ ] Sin fallos críticos conocidos.
-   [ ] Soporte.
-   [ ] Analítica.
-   [ ] LinkedIn.
-   [ ] Mensaje comercial alineado con capacidades reales.

------------------------------------------------------------------------

# 24. Mensaje comercial

## Concepto

**RECUPERA EL CONTROL**

## Claim

**Tú llevas el negocio. Alfonso lleva la gestión.**

## Promesa

**Tú decides qué hacer. Alfonso hace el trabajo administrativo.**

## Firma

**Tú decides. Alfonso lo hace.**

### Regla de comunicación

-   [ ] No afirmar que Alfonso es VERI\*FACTU hasta superar el Gate 4.
-   [ ] No afirmar presentación automática de impuestos hasta disponer
    de la integración correspondiente.
-   [ ] No afirmar Open Banking productivo mientras existan proveedores
    mock.
-   [ ] No presentar cálculos fiscales simplificados como liquidaciones
    definitivas.
-   [ ] No presentar OCR heurístico como extracción totalmente fiable.

------------------------------------------------------------------------

# 25. Objetivo final

``` text
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
┌──────────────┬──────────────┬──────────────┐
│ Facturación  │ Contabilidad │ Bancos       │
└──────────────┴──────────────┴──────────────┘
                 ↓
             Fiscalidad
                 ↓
       Infraestructura / APIs
                 ↓
       AEAT / Bancos / Asesoría
```

**Resultado:** un agente fiscal, contable y financiero para autónomos y
pequeñas empresas cuya ventaja competitiva sea permitir al usuario
utilizar estas capacidades mediante conversación, automatización
controlada, trazabilidad y seguridad.

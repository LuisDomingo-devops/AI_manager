# Plan de Implementación: 005-billing-integrity

## 1. Arquitectura y Diseño Técnico

### 1.1 InvoiceRepository.find_all_invoices(year=None)
En `app/infrastructure/database/repositories/invoice_repository.py`:
- Añadir el método estático `find_all_invoices(year: Optional[int] = None) -> List[Dict[str, Any]]`.
- Consulta a la base de datos `invoices`. Si `year` se especifica, filtra `WHERE year = ?`.
- Itera sobre los registros y descifra los campos protegidos con Fernet:
  `invoice_id`, `date`, `issuer_name`, `issuer_nif`, `receiver_name`, `receiver_nif`, `base_imponible`, `iva_rate`, `iva_amount`, `irpf_rate`, `irpf_amount`, `total_amount`, `concept`, `file_path`.
- Preserva los campos en claro: `id`, `category`, `quarter`, `year`, `status`, `tax_engine_version`.

### 1.2 billing_router.py
En `app/api/v1/billing_router.py`:
- Actualizar el endpoint `GET /api/v1/billing/invoices`:
  ```python
  @router.get("/invoices")
  async def list_invoices(year: Optional[int] = None):
      invoices = InvoiceRepository.find_all_invoices(year=year)
      return {"status": "ok", "total": len(invoices), "invoices": invoices}
  ```

### 1.3 Saneamiento de Tests Inválidos
En `tests/backend/integration/test_billing_products.py` y `test_billing_services.py`:
- Sustituir `assert response.status_code in (200, 400)` por `assert response.status_code == 200`.
- Asegurar que los headers y la autenticación se resuelvan deterministamente para que el test nunca caiga en el falso branch de error.
- Eliminar condicionales que perdonan fallos en `update` o `delete`.

---

## 2. Fases de Ejecución TDD

- **Fase 1 (Setup & Logs)**:
  - Crear directorio de logs `tests/logs/spec005/`.
- **Fase 2 (US1 - Endpoint GET /invoices y método en Repositorio)**:
  - RED: Crear `tests/backend/integration/test_billing_invoices_api_integration.py` llamando al endpoint; registrar fallo `AttributeError`.
  - GREEN: Implementar `find_all_invoices` en `InvoiceRepository` y conectarlo en `billing_router.py`.
  - Verificar GREEN y registrar log.
- **Fase 3 (US2 - Saneamiento de Tests de Billing Products y Services)**:
  - Refactorizar `test_billing_products.py` y `test_billing_services.py` con aserciones deterministas.
  - Ejecutar y registrar log.
- **Fase 4 (US3 - Suite de QA de Gobernanza de Facturación)**:
  - Crear `tests/backend/qa/test_billing_governance_suite.py` auditando ciclo completo, filtros y descifrado.
  - Ejecutar y registrar log.
- **Fase 5 (Validación Completa del Repositorio)**:
  - Ejecutar suite completa y consolidar commit formal en Git.

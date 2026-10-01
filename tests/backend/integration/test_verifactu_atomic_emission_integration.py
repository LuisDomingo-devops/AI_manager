"""
Test de Integración: Validación contra verifactu.xsd y Transaccionalidad Atómica ACID sin huecos.
Task: T010 [P] [US1]
"""

import pytest
import sqlite3
from pathlib import Path
from app.domain.services.verifactu_validator import VerifactuValidator
from app.domain.exceptions import XSDValidationError, InvoiceNumberGapError
from app.infrastructure.database.connection_manager import _get_connection, write_transaction


def test_verifactu_xsd_validator_valid_xml():
    """Valida un documento XML correcto contra app/schemas/verifactu.xsd."""
    valid_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<RegFactuSistemaFacturacion xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Cabecera>
    <ObligadoEmision>
      <NombreRazon>EMPRESA TEST SL</NombreRazon>
      <NIF>B12345674</NIF>
    </ObligadoEmision>
  </Cabecera>
  <RegistroFacturacionAlta>
    <IDFactura>
      <NumSerieFacturaEmisor>F2026-0001</NumSerieFacturaEmisor>
      <FechaExpedicionFacturaEmisor>01-10-2026</FechaExpedicionFacturaEmisor>
    </IDFactura>
    <NombreRazonEmisor>EMPRESA TEST SL</NombreRazonEmisor>
    <Receptor>
      <NombreRazonReceptor>CLIENTE EJEMPLO SA</NombreRazonReceptor>
      <NIFReceptor>A98765432</NIFReceptor>
    </Receptor>
    <DetalleFactura>
      <TipoFactura>F1</TipoFactura>
      <ClaveRegimenEspecialOTrascendencia>01</ClaveRegimenEspecialOTrascendencia>
      <ImporteTotal>1210.00</ImporteTotal>
      <Desglose>
        <DetalleIVA>
          <BaseImponible>1000.00</BaseImponible>
          <CuotaIVA>210.00</CuotaIVA>
        </DetalleIVA>
      </Desglose>
    </DetalleFactura>
    <SistemaInformatico>
      <Nombre>Alfonso AI Konta</Nombre>
      <NIFProductor>B12345674</NIFProductor>
      <NumInstalacion>001</NumInstalacion>
      <Version>1.0.0</Version>
    </SistemaInformatico>
  </RegistroFacturacionAlta>
</RegFactuSistemaFacturacion>"""

    validator = VerifactuValidator()
    is_valid, errors = validator.validate_xml(valid_xml)
    assert is_valid is True
    assert len(errors) == 0


def test_verifactu_xsd_validator_invalid_xml_rejected():
    """Valida que un XML al que le falta un elemento obligatorio sea rechazado con errores descriptivos."""
    # XML sin Cabecera ni ObligadoEmision
    invalid_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<RegFactuSistemaFacturacion>
  <RegistroFacturacionAlta>
    <NombreRazonEmisor>EMPRESA TEST SL</NombreRazonEmisor>
  </RegistroFacturacionAlta>
</RegFactuSistemaFacturacion>"""

    validator = VerifactuValidator()
    is_valid, errors = validator.validate_xml(invalid_xml)
    assert is_valid is False
    assert len(errors) > 0


def test_atomic_emission_rollback_prevents_number_gaps():
    """
    Verifica que si la validación XSD falla o ocurre una excepción,
    la transacción ACID revierte la asignación de número y no se genera un hueco.
    """
    from app.domain.services.billing_service import BillingService
    from app.domain.models.billing import InvoiceCreateDTO, InvoiceType

    service = BillingService()
    series = "F2026_ATOMIC_TEST"

    # 1. Emitir la factura 1 con éxito
    inv1_in = InvoiceCreateDTO(
        series=series,
        invoice_type=InvoiceType.F1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="EMPRESA TEST SL",
        recipient_nif="A98765432",
        recipient_name="CLIENTE EJEMPLO SA",
        base_amount=100.0,
        tax_amount=21.0,
        total_amount=121.0
    )
    inv1 = service.emit_invoice_atomic(inv1_in, force_valid_xml=True)
    assert inv1.number == 1

    # 2. Intentar emitir una factura 2 con XML inválido que falla XSD
    inv2_in = InvoiceCreateDTO(
        series=series,
        invoice_type=InvoiceType.F1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="EMPRESA TEST SL",
        recipient_nif="A98765432",
        recipient_name="CLIENTE EJEMPLO SA",
        base_amount=200.0,
        tax_amount=42.0,
        total_amount=242.0
    )

    with pytest.raises(XSDValidationError):
        service.emit_invoice_atomic(inv2_in, force_invalid_xml=True)

    # 3. La siguiente emisión válida DEBE recibir el número 2 (¡sin huecos!)
    inv3_in = InvoiceCreateDTO(
        series=series,
        invoice_type=InvoiceType.F1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="EMPRESA TEST SL",
        recipient_nif="A98765432",
        recipient_name="CLIENTE EJEMPLO SA",
        base_amount=300.0,
        tax_amount=63.0,
        total_amount=363.0
    )
    inv3 = service.emit_invoice_atomic(inv3_in, force_valid_xml=True)
    assert inv3.number == 2, f"Se esperaba el correlativo 2, pero se obtuvo {inv3.number} (posible hueco en la serie)"

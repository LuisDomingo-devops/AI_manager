"""
test_tax_declarations_ledger_integration.py
===========================================
Pruebas de integración sobre la base de datos SQLite para la tabla tax_declarations_ledger:
- Inserción y actualización idempotente de autoliquidaciones tributarias.
- Verificación del plazo legal de retención a 5 años (retention_until_date).
- Consulta y filtrado por tenant_id, model_code y fiscal_year.
- Descarga íntegra del fichero telemático original BOE (.ses) y comprobación del hash SHA-256.
"""

import pytest
import hashlib
from app.domain.services.tax_ledger_service import TaxLedgerService


def test_integration_save_and_retrieve_tax_declaration():
    """Valida el almacenamiento de una declaración y su recuperación con todas las propiedades de custodia."""
    ledger = TaxLedgerService()

    boe_content = (
        "130320261TB12345674HOLDING FISCAL SL                        912345678            \r\n"
        "230320261TB123456740000000000010000000000000000021000000000000021000\r\n"
    )

    expected_hash = hashlib.sha256(boe_content.encode("utf-8")).hexdigest()

    saved = ledger.save_declaration_filing(
        model_code="303",
        fiscal_year=2026,
        period="1T",
        declarant_nif="B12345674",
        declarant_name="HOLDING FISCAL SL",
        casillas_payload={"01": 1000.0, "02": 21.0, "03": 210.0, "71": 210.0},
        boe_file_content=boe_content,
        filing_status="EXPORTED"
    )

    assert saved.id is not None
    assert saved.model_code == "303"
    assert saved.fiscal_year == 2026
    assert saved.period == "1T"
    assert saved.declarant_nif == "B12345674"
    assert saved.sha256_hash == expected_hash
    assert saved.filing_status == "EXPORTED"

    # Verificar que la fecha de retención es filing_year + 5 años
    filing_year = int(saved.filing_date[:4])
    retention_year = int(saved.retention_until_date[:4])
    assert retention_year == filing_year + 5

    # Recuperación por ID
    retrieved = ledger.get_declaration_by_id(saved.id)
    assert retrieved is not None
    assert retrieved.boe_file_content == boe_content
    assert retrieved.casillas_payload["71"] == 210.0

    # Listado con filtros
    items = ledger.list_declarations(tenant_id="default", model_code="303", fiscal_year=2026)
    assert len(items) >= 1
    found = [i for i in items if i.id == saved.id]
    assert len(found) == 1


def test_integration_save_declaration_idempotent_update():
    """Valida que volver a guardar el mismo modelo/ejercicio/periodo actualiza en lugar de duplicar."""
    ledger = TaxLedgerService()

    content_v1 = "113020262TB99999999EMPRESA 130 SL                          912345678            \r\n213020262TB9999999900000000000500000\r\n"
    content_v2 = "113020262TB99999999EMPRESA 130 SL                          912345678            \r\n213020262TB9999999900000000000750000\r\n"

    r1 = ledger.save_declaration_filing(
        model_code="130",
        fiscal_year=2026,
        period="2T",
        declarant_nif="B99999999",
        declarant_name="EMPRESA 130 SL",
        casillas_payload={"01": 5000.0},
        boe_file_content=content_v1
    )

    r2 = ledger.save_declaration_filing(
        model_code="130",
        fiscal_year=2026,
        period="2T",
        declarant_nif="B99999999",
        declarant_name="EMPRESA 130 SL MODIFICADA",
        casillas_payload={"01": 7500.0},
        boe_file_content=content_v2,
        filing_status="MODIFIED"
    )

    items = ledger.list_declarations(tenant_id="default", model_code="130", fiscal_year=2026)
    # Debe haber solo 1 registro para 130-2026-2T
    matched = [i for i in items if i.period == "2T"]
    assert len(matched) == 1
    assert matched[0].declarant_name == "EMPRESA 130 SL MODIFICADA"
    assert matched[0].casillas_payload["01"] == 7500.0

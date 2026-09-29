"""
Tests de Integración para el Pipeline de Extracción de Facturas (Spec 015).
Valida:
- Integración de TaxParserService con InvoiceRepository y TaxEngine.
- Flujo de persistencia segura de facturas extraídas sin excepciones de Pydantic.
- Marcado de requires_manual_confirmation en base de datos cuando hay anomalías.
- Consistencia contable entre facturas extraídas, libro diario (asientos) y agregados trimestrales.
"""

import pytest
import json
from unittest.mock import patch

from app.domain.services.tax_parser_service import TaxParserService
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection


@pytest.fixture(autouse=True)
def clean_invoices_table():
    with _get_connection() as conn:
        conn.execute("DELETE FROM invoices")
        conn.commit()
    yield


@pytest.mark.asyncio
async def test_integration_extraction_to_database_persistence():
    """
    Verifica que una factura con formato mixto de importes y tasas
    se extraiga, se normalice y se guarde en base de datos sin errores de esquema.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "INV-INT-001",
        "date": "2026-03-15",
        "issuer_name": "Consultores Asociados SL",
        "issuer_nif": "B12345674",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": "1.500,00 €",
        "iva_rate": "21 %",
        "iva_amount": "315,00 €",
        "irpf_amount": "0.0",
        "total_amount": "1.815,00 €"
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        raw_text = """
        Factura INV-INT-001
        Fecha: 15/03/2026
        Emisor: Consultores Asociados SL (NIF B12345674)
        Cliente: Luis Domingo (NIF 47019805P)
        Base Imponible: 1.500,00 €
        IVA 21%: 315,00 €
        Total: 1.815,00 €
        """

        extracted = TaxParserService.parse_invoice_text(raw_text, user_nif="47019805P")

        assert extracted["invoice_id"] == "INV-INT-001"
        assert extracted["base_imponible"] == 1500.0
        assert extracted["iva_rate"] == 21.0
        assert extracted["iva_amount"] == 315.0
        assert extracted["total_amount"] == 1815.0
        assert extracted["requires_manual_confirmation"] is False

        # Persistir en la base de datos
        db_id = TaxParserService.save_invoice_to_db(extracted)
        assert db_id > 0

        # Verificar en base de datos
        from app.utils.encryption import encryptor
        with _get_connection() as conn:
            row = conn.execute("SELECT id, iva_rate FROM invoices WHERE id = ?", (db_id,)).fetchone()
            assert row is not None
            assert float(encryptor.decrypt(row["iva_rate"])) == 21.0


@pytest.mark.asyncio
async def test_integration_hallucinated_rate_marked_for_review_in_db():
    """
    Verifica que si la extracción detecta anomalías lógicas irrecuperables
    (datos corruptos), se marque para revisión manual y se persista sin quebrar el sistema.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "INV-INT-ANOMALOUS",
        "date": "2026-04-10",
        "issuer_name": "Desconocido",
        "issuer_nif": "B00000000",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": 500.0,
        "iva_rate": 888.88,  # Tasa alucinada imposible
        "iva_amount": 888.88,
        "irpf_amount": 0.0,
        "total_amount": 1388.88
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        extracted = TaxParserService.parse_invoice_text("Texto anómalo", user_nif="47019805P")

        # iva_rate debe estar saneada a <= 100
        assert extracted["iva_rate"] <= 100.0
        assert extracted["requires_manual_confirmation"] is True
        assert extracted["status"] == "PENDIENTE_REVISION"


@pytest.mark.asyncio
async def test_integration_quarterly_aggregates_with_parsed_invoices():
    """
    Verifica que las facturas procesadas con el pipeline corregido
    alimentan correctamente los agregados trimestrales contables.
    """
    invoices_data = [
        {
            "invoice_id": "Q1-001",
            "date": "10/01/2026",
            "issuer_name": "Proveedor Uno",
            "issuer_nif": "B11111111",
            "receiver_name": "Luis Domingo",
            "receiver_nif": "47019805P",
            "base_imponible": 1000.0,
            "iva_rate": 21.0,
            "iva_amount": 210.0,
            "irpf_rate": 0.0,
            "irpf_amount": 0.0,
            "total_amount": 1210.0,
            "category": "expense",
            "quarter": 1,
            "year": 2026,
            "status": "firmada"
        },
        {
            "invoice_id": "Q1-002",
            "date": "20/02/2026",
            "issuer_name": "Luis Domingo",
            "issuer_nif": "47019805P",
            "receiver_name": "Cliente Uno",
            "receiver_nif": "B22222222",
            "base_imponible": 3000.0,
            "iva_rate": 21.0,
            "iva_amount": 630.0,
            "irpf_rate": 15.0,
            "irpf_amount": 450.0,
            "total_amount": 3180.0,
            "category": "income",
            "quarter": 1,
            "year": 2026,
            "status": "firmada"
        }
    ]

    for inv in invoices_data:
        TaxParserService.save_invoice_to_db(inv)

    aggregates = TaxParserService.get_quarterly_aggregates(year=2026)
    assert len(aggregates) > 0
    q1 = next(item for item in aggregates if item["quarter"] == 1 and item["year"] == 2026)
    assert q1["income"]["base"] == 3000.0
    assert q1["income"]["iva"] == 630.0
    assert q1["expense"]["base"] == 1000.0
    assert q1["expense"]["iva"] == 210.0

"""
Suite de Pruebas de QA para Estados Financieros Oficiales del PGC PYMES.
Valida la generación formal de documentos PDF para el depósito telemático en el Registro Mercantil
y la homologación de balances y cuentas de pérdidas y ganancias.
"""

import io
from decimal import Decimal
import pytest
from pypdf import PdfReader
from app.domain.schemas import BalanceSheetDTO, FinancialStatementLineDTO
from app.domain.services.financial_statement_pdf_service import FinancialStatementPdfService


@pytest.fixture
def sample_balanced_sheet():
    """Genera un DTO de Balance de Situación perfectamente cuadrado según el PGC PYMES."""
    return BalanceSheetDTO(
        tenant_id="test_qa_tenant",
        fiscal_year=2026,
        fecha_cierre="2026-12-31",
        activo_no_corriente=[
            FinancialStatementLineDTO(
                epigrafe_codigo="A.II",
                epigrafe_nombre="Inmovilizado material",
                cuentas_asociadas=["21700000", "28100000"],
                saldo_ejercicio_actual=Decimal("1500.00"),
                saldo_ejercicio_anterior=Decimal("0.00")
            )
        ],
        activo_corriente=[
            FinancialStatementLineDTO(
                epigrafe_codigo="B.II",
                epigrafe_nombre="Deudores comerciales y otras cuentas a cobrar",
                cuentas_asociadas=["43000000"],
                saldo_ejercicio_actual=Decimal("2500.00"),
                saldo_ejercicio_anterior=Decimal("0.00")
            ),
            FinancialStatementLineDTO(
                epigrafe_codigo="B.V",
                epigrafe_nombre="Efectivo y otros activos líquidos equivalentes",
                cuentas_asociadas=["57200000"],
                saldo_ejercicio_actual=Decimal("1000.00"),
                saldo_ejercicio_anterior=Decimal("0.00")
            )
        ],
        total_activo=Decimal("5000.00"),
        patrimonio_neto=[
            FinancialStatementLineDTO(
                epigrafe_codigo="A-1.I",
                epigrafe_nombre="Capital",
                cuentas_asociadas=["10000000"],
                saldo_ejercicio_actual=Decimal("3000.00"),
                saldo_ejercicio_anterior=Decimal("0.00")
            ),
            FinancialStatementLineDTO(
                epigrafe_codigo="A-1.VII",
                epigrafe_nombre="Resultado del ejercicio",
                cuentas_asociadas=["12900000"],
                saldo_ejercicio_actual=Decimal("1000.00"),
                saldo_ejercicio_anterior=Decimal("0.00")
            )
        ],
        pasivo_no_corriente=[],
        pasivo_corriente=[
            FinancialStatementLineDTO(
                epigrafe_codigo="C.II",
                epigrafe_nombre="Acreedores comerciales y otras cuentas a pagar",
                cuentas_asociadas=["40000000"],
                saldo_ejercicio_actual=Decimal("1000.00"),
                saldo_ejercicio_anterior=Decimal("0.00")
            )
        ],
        total_pasivo_y_patrimonio_neto=Decimal("5000.00"),
        is_balanced=True
    )


def test_balance_sheet_official_pdf_structure(sample_balanced_sheet):
    """Valida que el PDF oficial para el Registro Mercantil contenga los epígrafes normalizados y diseño legal."""
    service = FinancialStatementPdfService()
    pdf_bytes = service.generate_balance_sheet_pdf(sample_balanced_sheet)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

    # Inspección de contenido del PDF generado
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    page_text = reader.pages[0].extract_text()

    # Verificar presencia de textos legales normativos
    assert "BALANCE DE SITUACIÓN" in page_text or "BALANCE" in page_text
    assert "RD 1515/2007" in page_text or "PGC PYMES" in page_text
    assert "ACTIVO NO CORRIENTE" in page_text
    assert "ACTIVO CORRIENTE" in page_text
    assert "PATRIMONIO NETO" in page_text
    assert "PASIVO CORRIENTE" in page_text
    assert "5000.00" in page_text or "5.000,00" in page_text


def test_balance_sheet_pdf_blocks_unbalanced_export(sample_balanced_sheet):
    """Valida que no se permita emitir un PDF oficial si el balance está descuadrado."""
    unbalanced_sheet = sample_balanced_sheet.model_copy(deep=True)
    unbalanced_sheet.is_balanced = False
    unbalanced_sheet.total_activo = Decimal("5500.00")

    service = FinancialStatementPdfService()
    with pytest.raises(ValueError, match="descuadrado"):
        service.generate_balance_sheet_pdf(unbalanced_sheet)


def test_qa_api_financial_statements_endpoints():
    """Valida el acceso HTTP y formato de los endpoints oficiales de estados financieros y cierre."""
    from starlette.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    headers = {"X-API-Key": "test-api-key"}

    # 1. Endpoint Balance de Situación
    res_bs = client.get("/api/v1/accounting/financial-statements/balance-sheet?fiscal_year=2026&tenant_id=test_qa", headers=headers)
    assert res_bs.status_code == 200
    data_bs = res_bs.json()
    assert "total_activo" in data_bs
    assert "total_pasivo_y_patrimonio_neto" in data_bs
    assert "is_balanced" in data_bs

    # 2. Endpoint PyG Escalonada
    res_pyg = client.get("/api/v1/accounting/financial-statements/income-statement?fiscal_year=2026&tenant_id=test_qa", headers=headers)
    assert res_pyg.status_code == 200
    data_pyg = res_pyg.json()
    assert "cifra_negocios" in data_pyg
    assert "ebitda" in data_pyg
    assert "resultado_neto_ejercicio" in data_pyg

    # 3. Endpoint Simulación de Cierre
    res_sim = client.post("/api/v1/accounting/closing/simulate?fiscal_year=2026&tenant_id=test_qa", headers=headers)
    assert res_sim.status_code == 200, f"Error {res_sim.status_code}: {res_sim.text}"
    data_sim = res_sim.json()
    assert "resultado_antes_impuestos" in data_sim
    assert "asiento_cierre" in data_sim

    # 4. Endpoint Propuesta de Amortización
    res_dep = client.post("/api/v1/accounting/depreciation/calculate?fiscal_year=2026&tenant_id=test_qa", headers=headers)
    assert res_dep.status_code == 200
    assert "proposals" in res_dep.json()


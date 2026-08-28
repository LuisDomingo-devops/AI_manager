import pytest
from datetime import datetime
from app.domain.services.ledger_service import LedgerService
from app.domain.services.invoice_repository import InvoiceRepository
from app.tools.server.billing_tools import (
    generate_invoice_pdf,
    get_profit_and_loss_report,
    close_fiscal_year_tool
)
from app.adapters.memory.memory import _get_connection, tenant_context, _init_db_schema
from app.utils.encryption import encryptor

@pytest.fixture(autouse=True)
def setup_test_env():
    token = tenant_context.set("accounting_phase2_tenant")
    with _get_connection() as conn:
        _init_db_schema(conn)
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.execute("DELETE FROM user_profile")
        
        conn.execute("""
            INSERT INTO user_profile (user_type, nif, razon_social, direccion)
            VALUES (?, ?, ?, ?)
        """, (
            "autonomo",
            encryptor.encrypt("12345678Z"),
            encryptor.encrypt("LUIS DOMINGO AUTONOMO"),
            encryptor.encrypt("Calle Gran Vía 28, Madrid")
        ))
        conn.commit()
    yield
    tenant_context.reset(token)


def test_strict_double_entry_validation():
    """
    Verifica que el sistema valide estrictamente el principio de Partida Doble (Debe == Haber)
    y rechace con excepción cualquier apunte descuadrado.
    """
    # 1. Asiento cuadrado válido
    apuntes_validos = [
        {"account_code": "57200001", "debe": 100.0, "haber": 0.0},
        {"account_code": "70500000", "debe": 0.0, "haber": 100.0}
    ]
    journal_id = LedgerService.record_manual_entry("15/05/2026", "Cobro de servicio", apuntes_validos)
    assert journal_id > 0

    # 2. Asiento descuadrado (Debe: 100€ != Haber: 80€) -> Debe lanzar ValueError
    apuntes_descuadrados = [
        {"account_code": "57200001", "debe": 100.0, "haber": 0.0},
        {"account_code": "70500000", "debe": 0.0, "haber": 80.0}
    ]
    with pytest.raises(ValueError) as excinfo:
        LedgerService.record_manual_entry("16/05/2026", "Asiento erróneo", apuntes_descuadrados)
    assert "Asiento contable descuadrado" in str(excinfo.value)


def test_profit_and_loss_statement():
    """
    Verifica la generación de la Cuenta de Pérdidas y Ganancias (PyG) agregando ingresos (7) y gastos (6).
    """
    # 1. Registrar ingresos (3000 € base)
    LedgerService.record_invoice_asiento({
        "category": "ingreso",
        "invoice_id": "F-2026-001",
        "date": "10/02/2026",
        "base_imponible": 3000.0,
        "iva_amount": 630.0,
        "total_amount": 3630.0
    })

    # 2. Registrar gastos (1000 € base)
    LedgerService.record_invoice_asiento({
        "category": "gasto",
        "invoice_id": "EXP-2026-001",
        "date": "20/02/2026",
        "base_imponible": 1000.0,
        "iva_amount": 210.0,
        "total_amount": 1210.0
    })

    # 3. Consultar PyG anual 2026
    pnl = LedgerService.get_profit_and_loss_statement(2026)
    assert pnl["total_ingresos"] == 3000.0
    assert pnl["total_gastos"] == 1000.0
    assert pnl["resultado_explotacion"] == 2000.0
    assert pnl["impuesto_estimado"] == 400.0 # 20% de 2000€
    assert pnl["resultado_neto"] == 1600.0

    # 4. Consultar PyG trimestral T1 (Febrero -> T1)
    pnl_t1 = LedgerService.get_profit_and_loss_statement(2026, quarter=1)
    assert pnl_t1["resultado_explotacion"] == 2000.0

    # 5. Consultar PyG trimestral T2 (sin movimientos -> 0)
    pnl_t2 = LedgerService.get_profit_and_loss_statement(2026, quarter=2)
    assert pnl_t2["resultado_explotacion"] == 0.0


def test_close_fiscal_year_full_flow():
    """
    Verifica el flujo completo de cierre de ejercicio contable (PGC):
    1. Regularización de ingresos/gastos a cuenta 12900000.
    2. Asiento de Cierre de balance.
    3. Bloqueo de facturas y asientos en año cerrado.
    4. Asiento de Apertura en el ejercicio siguiente.
    """
    year = 2025
    # Registrar operaciones en 2025
    LedgerService.record_invoice_asiento({
        "category": "ingreso",
        "invoice_id": "F-2025-001",
        "date": f"15/06/{year}",
        "base_imponible": 5000.0,
        "iva_amount": 1050.0,
        "total_amount": 6050.0
    })
    LedgerService.record_invoice_asiento({
        "category": "gasto",
        "invoice_id": "EXP-2025-001",
        "date": f"20/06/{year}",
        "base_imponible": 2000.0,
        "iva_amount": 420.0,
        "total_amount": 2420.0
    })

    # Ejecutar cierre de 2025
    close_res = LedgerService.close_fiscal_year(year)
    assert close_res["status"] == "ok"
    assert close_res["resultado_ejercicio"] == 3000.0
    assert close_res["regularizacion_asiento_id"] is not None
    assert close_res["cierre_asiento_id"] is not None
    assert close_res["apertura_asiento_id"] is not None

    # Verificar que el año queda marcado como cerrado
    assert LedgerService.is_fiscal_year_closed(year) is True

    # Verificar bloqueo de nuevos asientos en 2025
    with pytest.raises(ValueError) as exc_entry:
        LedgerService.record_invoice_asiento({
            "category": "ingreso",
            "invoice_id": "F-2025-002",
            "date": f"10/07/{year}",
            "base_imponible": 1000.0,
            "iva_amount": 210.0,
            "total_amount": 1210.0
        })
    assert "está cerrado" in str(exc_entry.value)

    # Verificar bloqueo de inserción de facturas en repositorio en 2025
    with pytest.raises(ValueError) as exc_inv:
        InvoiceRepository.save({
            "invoice_id": "F-2025-999",
            "date": f"10/07/{year}",
            "issuer_name": "Luis",
            "issuer_nif": "12345678Z",
            "receiver_name": "Cliente",
            "receiver_nif": "B12345678",
            "base_imponible": 1000.0,
            "iva_rate": 21.0,
            "iva_amount": 210.0,
            "irpf_rate": 0.0,
            "irpf_amount": 0.0,
            "total_amount": 1210.0,
            "category": "ingreso",
            "quarter": 3,
            "year": year
        })
    assert "cerrado" in str(exc_inv.value)

    # Verificar que en 2026 existe el asiento de apertura
    diario_2026 = LedgerService.get_libro_diario(year + 1)
    apertura_entries = [e for e in diario_2026 if "Asiento de Apertura" in e["concepto"]]
    assert len(apertura_entries) == 1
    assert apertura_entries[0]["fecha"] == f"01/01/{year + 1}"


@pytest.mark.asyncio
async def test_tools_pnl_and_year_close():
    """
    Verifica las herramientas de usuario para consulta de PyG y cierre de ejercicio.
    """
    # 1. Herramienta PyG
    res_pnl = await get_profit_and_loss_report(2026)
    assert res_pnl["status"] == "ok"
    assert "report" in res_pnl

    # 2. Herramienta Cierre sin confirmación -> pending_confirmation
    res_close_pending = await close_fiscal_year_tool(2024, confirmed_by_user=False)
    assert res_close_pending["status"] == "pending_confirmation"

    # 3. Herramienta Cierre con confirmación -> ok
    res_close_ok = await close_fiscal_year_tool(2024, confirmed_by_user=True)
    assert res_close_ok["status"] == "ok"
    assert LedgerService.is_fiscal_year_closed(2024) is True

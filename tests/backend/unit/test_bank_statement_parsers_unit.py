"""
Test Unitarios para los Parsers de Extractos Bancarios (CSV Wise, CSV Genérico y Norma 43).
"""
import os
import tempfile
import pytest
from app.domain.services.bank_service import BankService

@pytest.fixture
def temp_wise_csv():
    content = """TransferWise ID,Date,Amount,Currency,Description,Payment Reference
WISE-001,2026-08-10,1250.00,EUR,Pago Factura Cliente Internacional,FAC-2026-101
WISE-002,2026-08-11,-45.50,EUR,Suscripcion Software Servidor,SRV-99
WISE-003,2026-08-12,300.00,EUR,Cobro Consultoria Alfonso,CONS-01
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
        f.write(content)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_spanish_csv():
    content = """Fecha;Concepto;Importe;Referencia
15/08/2026;Pago Alquiler Oficina;-650,00;ALQ-AGO
16/08/2026;Ingreso Transferencia Nomina;2400,00;NOM-2026
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
        f.write(content)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_norma43_file():
    # Registros tipo 22 alineados al estándar Norma 43 (90 caracteres por línea)
    line1 = "220049150005082605082601001100000000005000REF0000001PAGO SUMINISTRO ELECTRICIDAD          "
    line2 = "220049150006082606082601001200000000010000REF0000002COBRO CLIENTE SERVICIOS               "
    content = f"""110049150012345678900108260508262000000000000EUR3CUENTA PRINCIPAL
{line1}
{line2}
3300491500000002000000005000000000000100000200000000500000EUR
88999999000001000000000004
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".n43", encoding="utf-8") as f:
        f.write(content)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_parse_wise_csv(temp_wise_csv):
    conn_id = BankService.add_connection("Wise Test Parser", "wise", "Wise", "", "{}")
    count = BankService.parse_csv_statement(temp_wise_csv, conn_id)
    assert count == 3

    # Comprobar no duplicidad al re-importar el mismo archivo
    re_count = BankService.parse_csv_statement(temp_wise_csv, conn_id)
    assert re_count == 0


def test_parse_spanish_csv(temp_spanish_csv):
    conn_id = BankService.add_connection("Banco Santander CSV", "santander", "Santander", "ES91...", "{}")
    count = BankService.parse_csv_statement(temp_spanish_csv, conn_id)
    assert count == 2


def test_parse_norma43(temp_norma43_file):
    conn_id = BankService.add_connection("BBVA Norma 43", "bbva", "BBVA", "ES12...", "{}")
    count = BankService.parse_norma43_file(temp_norma43_file, conn_id)
    assert count == 2


def test_import_statement_auto_detection(temp_wise_csv, temp_norma43_file):
    conn_id = BankService.add_connection("Cuenta Auto Detec", "mock", "Multi", "", "{}")
    
    # Debe detectar CSV
    count_csv = BankService.import_statement(temp_wise_csv, conn_id)
    assert count_csv == 3
    
    # Debe detectar Norma 43
    count_n43 = BankService.import_statement(temp_norma43_file, conn_id)
    assert count_n43 == 2

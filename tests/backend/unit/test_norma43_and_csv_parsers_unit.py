"""
Test Unitario para Parsers de Extractos Bancarios (User Story 5: Conciliación Bancaria Real).
Valida el procesamiento estricto de ficheros Norma 43 (CSB 43) y CSV bancarios españoles sin datos simulados.
"""

import pytest
from app.domain.services.norma43_parser import Norma43Parser
from app.domain.services.bank_csv_parser import BankCsvParser
from app.domain.models.billing import BankStatementDTO


def test_norma43_parser_valid_file():
    """Valida el parseo de un extracto bancario estándar en formato Norma 43."""
    parser = Norma43Parser()
    
    # Simulación de un fichero Norma 43 de 1 cuenta con 2 movimientos
    # 11: Cabecera de cuenta (banco 0182, sucursal 1234, cta 0012345678, saldo inicial 5000.00 EUR)
    # 22: Movimiento 1 (Abono +1210.00 EUR, fecha 260115)
    # 23: Concepto complementario movimiento 1
    # 22: Movimiento 2 (Cargo -50.00 EUR, fecha 260120)
    # 33: Fin de cuenta (saldo final 6160.00 EUR)
    n43_content = (
        "11018212340012345678260101260131200000000500000EUR3CUENTA PRINCIPAL ALFONSO   \r\n"
        "2201821234260115260115010002000000001210000000000000000000000000TRANSFERENCIA EMITIDA \r\n"
        "2301PAGO FACTURA F2026-0001 ACME SL                                              \r\n"
        "2201821234260120260120010001000000000050000000000000000000000000COMISION MANTENIMIENTO \r\n"
        "2301GASTOS BANCARIOS MENSUALES                                                   \r\n"
        "33018212340012345678000001000000000050000000000100000000121000200000000616000EUR \r\n"
    ).encode("latin-1")
    
    statement: BankStatementDTO = parser.parse(n43_content)
    
    assert statement.source_type == "NORMA43"
    assert len(statement.entries) == 2
    
    # Movimiento 1: Abono de 1210.00
    m1 = statement.entries[0]
    assert m1.operation_date == "2026-01-15"
    assert m1.amount == 1210.00
    assert "ACME" in m1.concept or "FACTURA" in m1.concept
    
    # Movimiento 2: Cargo de -50.00
    m2 = statement.entries[1]
    assert m2.operation_date == "2026-01-20"
    assert m2.amount == -50.00
    assert "COMISION" in m2.concept or "GASTOS" in m2.concept


def test_bank_csv_parser_spanish_format():
    """Valida el parseo de CSV bancario español con separador de punto y coma y formato europeo de moneda."""
    parser = BankCsvParser()
    
    csv_text = (
        "Fecha;Fecha Valor;Concepto;Importe;Saldo\n"
        "15/01/2026;15/01/2026;TRANSFERENCIA CLIENTE ACME CORP;1.210,00;6.210,00\n"
        "20/01/2026;20/01/2026;SUMINISTRO INTERNET FIBRA;-45,50;6.164,50\n"
    )
    
    statement: BankStatementDTO = parser.parse(csv_text, account_iban="ES9121000418450200051332")
    assert statement.source_type == "CSV"
    assert len(statement.entries) == 2
    
    assert statement.entries[0].operation_date == "2026-01-15"
    assert statement.entries[0].amount == 1210.00
    assert "ACME" in statement.entries[0].concept
    
    assert statement.entries[1].operation_date == "2026-01-20"
    assert statement.entries[1].amount == -45.50
    assert "SUMINISTRO" in statement.entries[1].concept

"""
Tests unitarios para el parser oficial Norma 43 (Cuaderno CSB 43) de la AEB.
Valida el procesamiento posicional de registros 11, 22, 23, 33 con rigor Decimal y detección de descuadres.
"""
import pytest
from decimal import Decimal
from app.domain.services.norma43_parser import Norma43Parser
from app.domain.schemas import BankStatementDTO, BankMovementDTO
from app.domain.exceptions import BankStatementDiscrepancyError


def _generate_norma43_content(initial_cents: int, initial_sign: str,
                              movements: list[tuple[str, int, str, list[str]]],
                              final_cents: int, final_sign: str) -> bytes:
    """
    Genera un contenido sintético oficial Norma 43 conforme al cuaderno CSB 43.
    """
    lines = []
    # 11: Cabecera de cuenta
    # pos 0-2: 11
    # pos 2-6: banco (0182)
    # pos 6-10: sucursal (1234)
    # pos 10-20: num cuenta (1234567890)
    # pos 20-26: fecha inicio (260101)
    # pos 26-27: clave signo (1 debe, 2 haber)
    # pos 27-41: importe saldo (14 digitos)
    # pos 41-44: divisa (978 EUR)
    lines.append(f"11018212341234567890260101{initial_sign}{initial_cents:014d}9783TITULAR CUENTA ESPAÑA")

    for op_date, amt_cents, sign_code, concept_lines in movements:
        # 22: Movimiento principal
        # pos 0-2: 22
        # pos 2-6: libre/sucursal
        # pos 6-10: libre
        # pos 10-16: fecha operacion (YYMMDD)
        # pos 16-22: fecha valor (YYMMDD)
        # pos 22-24: concepto comun
        # pos 24-27: concepto propio
        # pos 27-28: clave debe/haber ('1' cargo, '2' abono)
        # pos 28-42: importe (14 digitos)
        # pos 42-52: num documento
        # pos 52-80: concepto principal
        main_concept = concept_lines[0] if concept_lines else "MOVIMIENTO BANCARIO"
        lines.append(f"2201821234{op_date}{op_date}01001{sign_code}{amt_cents:014d}DOC12345   {main_concept:<28}")

        # 23: Conceptos complementarios
        for extra in concept_lines[1:]:
            lines.append(f"2301{extra:<76}")

    # 33: Fin de cuenta y saldo final
    # pos 0-2: 33
    # pos 2-6: banco
    # pos 6-10: sucursal
    # pos 10-20: cuenta
    # pos 20-25: num apuntes debe
    # pos 25-39: total debe
    # pos 39-44: num apuntes haber
    # pos 44-58: total haber
    # pos 58-59: clave saldo ('1' debe, '2' haber)
    # pos 59-73: saldo final (14 digitos)
    # pos 73-76: divisa (978)
    lines.append(f"3301821234123456789000001000000000000000000100000000000000{final_sign}{final_cents:014d}978")

    text = "\r\n".join(lines) + "\r\n"
    return text.encode("latin-1")


def test_norma43_parser_valid_balanced_statement():
    """Valida la importación de extracto Norma 43 perfectamente cuadrado con Decimal."""
    parser = Norma43Parser()

    # Saldo inicial: 5.000,00 € (haber -> signo '2')
    # Movimiento 1: Abono de +1.210,00 € (haber -> signo '2') con concepto complementario
    # Movimiento 2: Cargo de -350,00 € (debe -> signo '1')
    # Saldo final: 5.000 + 1.210 - 350 = 5.860,00 € (haber -> signo '2')
    movements = [
        ("260115", 121000, "2", ["COBRO FACTURA F2026-001", "ORDENANTE: ACME CORP ESPAÑA"]),
        ("260116", 35000, "1", ["PAGO SUMINISTROS ENERGIA", "IBERDROLA CLIENTES"]),
    ]
    raw = _generate_norma43_content(500000, "2", movements, 586000, "2")

    statement = parser.parse(raw, account_iban="ES9101821234123456789012")

    assert isinstance(statement, BankStatementDTO)
    assert statement.initial_balance == Decimal("5000.00")
    assert statement.final_balance == Decimal("5860.00")
    assert len(statement.entries) == 2

    # Verificar apunte 1 (abono)
    e1 = statement.entries[0]
    assert e1.amount == Decimal("1210.00")
    assert e1.operation_date == "2026-01-15"
    assert "ACME CORP ESPAÑA" in e1.concept
    assert e1.reconciliation_status == "UNRECONCILED"

    # Verificar apunte 2 (cargo)
    e2 = statement.entries[1]
    assert e2.amount == Decimal("-350.00")
    assert e2.operation_date == "2026-01-16"
    assert "IBERDROLA" in e2.concept


def test_norma43_parser_raises_on_discrepancy():
    """Verifica que el parser detecta descuadres matemáticos y lanza BankStatementDiscrepancyError."""
    parser = Norma43Parser()

    # Saldo inicial 5.000,00 €, movimiento +1.210,00 €, pero saldo final falso de 6.500,00 € (descuadre de 290 €)
    movements = [
        ("260115", 121000, "2", ["COBRO CLIENTE", "REF SEPA 9988"]),
    ]
    raw = _generate_norma43_content(500000, "2", movements, 650000, "2")

    with pytest.raises(BankStatementDiscrepancyError) as exc_info:
        parser.parse(raw)

    err = exc_info.value
    assert err.initial_balance == Decimal("5000.00")
    assert err.final_balance == Decimal("6500.00")
    assert err.calculated_final == Decimal("6210.00")

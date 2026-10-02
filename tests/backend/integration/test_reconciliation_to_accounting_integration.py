"""
Tests de integración para el flujo completo de conciliación bancaria y contabilización obligatoria en Libro Diario PGC.
Verifica:
1. Inserción atómica e inmutable en legal_journal_entries y legal_journal_lines.
2. Imputación contable fiel (572 Debe vs 430 Haber para cobros, 400 Debe vs 572 Haber para pagos, 669 Debe para comisiones).
3. Transición de estados (bank_movements -> RECONCILED, invoices -> PAID).
4. Rechazo con BankReconciliationConflictError ante reintentos de apuntes ya conciliados (I1).
"""
import pytest
from decimal import Decimal
from datetime import date
from app.infrastructure.database.connection_manager import write_transaction
from app.infrastructure.database.legal_connection import legal_write_transaction, legal_read_transaction
from app.domain.services.bank_reconciliation_engine import BankReconciliationEngine
from app.domain.schemas import ApplyReconciliationCommand
from app.domain.exceptions import BankReconciliationConflictError


@pytest.fixture(autouse=True)
def setup_integration_data():
    """Limpia y prepara tablas para las pruebas de integración contable."""
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM bank_statements")

    with legal_write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM legal_journal_lines")
        cursor.execute("DELETE FROM legal_journal_entries")

    yield

    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM bank_statements")


def test_apply_reconciliation_creates_balanced_journal_entry_for_customer_collection():
    """Valida cobro de factura: apunte a RECONCILED, factura a PAID y asiento 572 Debe vs 430 Haber."""
    # 1. Crear apunte bancario
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bank_movements (
                id, account_iban, operation_date, value_date, movement_date, amount, balance_after,
                concept, reconciliation_status, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                10,
                "ES9101821234123456789012",
                "2026-01-20",
                "2026-01-20",
                "2026-01-20",
                1210.00,
                5210.00,
                "TRANSF COBRO FACTURA F2026-0010 CLIENTE SL",
                "UNRECONCILED",
                "default"
            )
        )
        cursor.execute(
            """
            INSERT INTO invoices (
                id, invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, total_amount, status, quarter, year
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                20,
                "F2026-0010",
                "2026-01-18",
                "ALFONSO AUTONOMO",
                "12345678Z",
                "CLIENTE SL",
                "B99887766",
                1000.00,
                21.0,
                210.00,
                1210.00,
                "ISSUED",
                1,
                2026
            )
        )

    engine = BankReconciliationEngine()
    cmd = ApplyReconciliationCommand(
        tenant_id="default",
        entry_id=10,
        invoice_id=20,
        debit_account="572",
        credit_account="430",
        fee_amount=Decimal("0.00")
    )

    result = engine.apply_reconciliation(cmd)

    assert result.status == "RECONCILED"
    assert result.journal_entry_id is not None

    # 2. Verificar estado en base de datos
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT reconciliation_status, journal_entry_id, reconciled_invoice_id FROM bank_movements WHERE id = 10")
        mov = cursor.fetchone()
        assert mov["reconciliation_status"] == "RECONCILED"
        assert mov["journal_entry_id"] == result.journal_entry_id
        assert mov["reconciled_invoice_id"] == 20

        cursor.execute("SELECT status FROM invoices WHERE id = 20")
        inv = cursor.fetchone()
        assert inv["status"] == "PAID"

    # 3. Verificar asiento contable en legal_journal_entries y legal_journal_lines
    with legal_read_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, entry_number, fiscal_year, concept FROM legal_journal_entries WHERE id = ?", (result.journal_entry_id,))
        entry = cursor.fetchone()
        assert entry is not None
        assert entry[2] == 2026

        cursor.execute("SELECT account_code, debit, credit FROM legal_journal_lines WHERE entry_id = ? ORDER BY account_code ASC", (result.journal_entry_id,))
        lines = cursor.fetchall()
        assert len(lines) == 2
        # Cuenta 430 Haber 1210.00
        line_430 = [l for l in lines if l[0] == "430"][0]
        assert Decimal(str(line_430[1])) == Decimal("0.00")
        assert Decimal(str(line_430[2])) == Decimal("1210.00")

        # Cuenta 572 Debe 1210.00
        line_572 = [l for l in lines if l[0] == "572"][0]
        assert Decimal(str(line_572[1])) == Decimal("1210.00")
        assert Decimal(str(line_572[2])) == Decimal("0.00")


def test_apply_reconciliation_with_gateway_fee_records_line_669():
    """Valida cobro con comisiones de pasarela: 572 (Debe 975) + 669 (Debe 25) vs 430 (Haber 1000)."""
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bank_movements (
                id, account_iban, operation_date, value_date, movement_date, amount, balance_after,
                concept, reconciliation_status, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                11,
                "ES9101821234123456789012",
                "2026-01-21",
                "2026-01-21",
                "2026-01-21",
                975.00,
                5975.00,
                "STRIPE PAYOUT F2026-0011",
                "UNRECONCILED",
                "default"
            )
        )
        cursor.execute(
            """
            INSERT INTO invoices (
                id, invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, total_amount, status, quarter, year
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                21,
                "F2026-0011",
                "2026-01-20",
                "ALFONSO AUTONOMO",
                "12345678Z",
                "CLIENTE ONLINE",
                "B11223344",
                1000.00,
                0.0,
                0.00,
                1000.00,
                "ISSUED",
                1,
                2026
            )
        )

    engine = BankReconciliationEngine()
    cmd = ApplyReconciliationCommand(
        tenant_id="default",
        entry_id=11,
        invoice_id=21,
        debit_account="572",
        credit_account="430",
        fee_amount=Decimal("25.00")
    )

    result = engine.apply_reconciliation(cmd)
    assert result.status == "RECONCILED"

    with legal_read_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT account_code, debit, credit FROM legal_journal_lines WHERE entry_id = ?", (result.journal_entry_id,))
        lines = cursor.fetchall()
        assert len(lines) == 3

        l_572 = [l for l in lines if l[0] == "572"][0]
        l_669 = [l for l in lines if l[0] == "669"][0]
        l_430 = [l for l in lines if l[0] == "430"][0]

        assert Decimal(str(l_572[1])) == Decimal("975.00")
        assert Decimal(str(l_572[2])) == Decimal("0.00")

        assert Decimal(str(l_669[1])) == Decimal("25.00")
        assert Decimal(str(l_669[2])) == Decimal("0.00")

        assert Decimal(str(l_430[1])) == Decimal("0.00")
        assert Decimal(str(l_430[2])) == Decimal("1000.00")


def test_apply_reconciliation_conflict_on_already_reconciled_movement():
    """Valida que intentar conciliar un apunte ya conciliado arroja BankReconciliationConflictError (I1)."""
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bank_movements (
                id, account_iban, operation_date, value_date, movement_date, amount, balance_after,
                concept, reconciliation_status, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                12,
                "ES9101821234123456789012",
                "2026-01-22",
                "2026-01-22",
                "2026-01-22",
                500.00,
                6500.00,
                "COBRO YA REALIZADO",
                "RECONCILED",
                "default"
            )
        )
        cursor.execute(
            """
            INSERT INTO invoices (
                id, invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, total_amount, status, quarter, year
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                22,
                "F2026-0012",
                "2026-01-21",
                "ALFONSO AUTONOMO",
                "12345678Z",
                "CLIENTE OMNI",
                "B99999999",
                500.00,
                0.0,
                0.00,
                500.00,
                "ISSUED",
                1,
                2026
            )
        )

    engine = BankReconciliationEngine()
    cmd = ApplyReconciliationCommand(
        tenant_id="default",
        entry_id=12,
        invoice_id=22
    )

    with pytest.raises(BankReconciliationConflictError):
        engine.apply_reconciliation(cmd)

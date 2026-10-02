"""
Suite QA de Integridad y Consistencia Banco vs Contabilidad PGC (T020).
Valida que:
1. El saldo neto de la cuenta 572 (Tesoreria/Bancos) en el Libro Mayor coincide exactamente al centimo
   con el flujo neto de movimientos bancarios conciliados.
2. Cada apunte conciliado tiene su correspondiente asiento inmutable en Libro Diario (legal_journal_entries).
3. No existen desfases ni perdida de precision de punto flotante en operaciones con comisiones (cuenta 669).
"""
import pytest
from decimal import Decimal
from app.infrastructure.database.connection_manager import write_transaction
from app.infrastructure.database.legal_connection import legal_write_transaction, legal_read_transaction
from app.domain.services.bank_reconciliation_engine import BankReconciliationEngine
from app.domain.schemas import ApplyReconciliationCommand


@pytest.fixture(autouse=True)
def clean_database():
    """Limpia la base de datos antes y después del test de QA."""
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


def test_qa_bank_ledger_572_integrity_and_balance_match():
    """
    Escenario QA integral:
    - 2 cobros de clientes (+1.210,00 €, +605,00 €)
    - 1 cobro con comisión TPV/Stripe (+975,00 € + 25,00 € comisión)
    - 1 pago a proveedor (-450,00 €)
    Flujo neto bancario real = 1210.00 + 605.00 + 975.00 - 450.00 = +2.340,00 €
    Verificar que el saldo del Libro Mayor de la cuenta 572 (Debe - Haber) es exactamente 2.340,00 €.
    """
    engine = BankReconciliationEngine()

    operations = [
        # (entry_id, invoice_id, amount, inv_total, fee, is_income)
        (101, 201, Decimal("1210.00"), 1210.00, Decimal("0.00"), True),
        (102, 202, Decimal("605.00"), 605.00, Decimal("0.00"), True),
        (103, 203, Decimal("975.00"), 1000.00, Decimal("25.00"), True),
        (104, 204, Decimal("-450.00"), 450.00, Decimal("0.00"), False),
    ]

    total_bank_net = Decimal("0.00")

    for entry_id, inv_id, amt, inv_total, fee, is_income in operations:
        total_bank_net += amt
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
                    entry_id,
                    "ES9101821234123456789012",
                    "2026-01-25",
                    "2026-01-25",
                    "2026-01-25",
                    float(amt),
                    10000.00,
                    f"OPERACION QA {entry_id}",
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
                    inv_id,
                    f"F2026-QA-{inv_id}",
                    "2026-01-24",
                    "ALFONSO AUTONOMO" if is_income else "PROVEEDOR QA",
                    "12345678Z" if is_income else "B12345678",
                    "CLIENTE QA" if is_income else "ALFONSO AUTONOMO",
                    "B99887766" if is_income else "12345678Z",
                    inv_total,
                    0.0,
                    0.0,
                    inv_total,
                    "ISSUED",
                    1,
                    2026
                )
            )

        cmd = ApplyReconciliationCommand(
            tenant_id="default",
            entry_id=entry_id,
            invoice_id=inv_id,
            debit_account="572" if is_income else "400",
            credit_account="430" if is_income else "572",
            fee_amount=fee
        )
        res = engine.apply_reconciliation(cmd)
        assert res.status == "RECONCILED"

    # Verificar cálculo del Libro Mayor para cuenta 572
    with legal_read_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT debit, credit FROM legal_journal_lines WHERE account_code = '572'
            """
        )
        lines_572 = cursor.fetchall()
        total_debit_572 = sum(Decimal(str(r[0])) for r in lines_572)
        total_credit_572 = sum(Decimal(str(r[1])) for r in lines_572)
        ledger_572_balance = total_debit_572 - total_credit_572

        # Comprobación de integridad estricta (tolerancia 0.00 €)
        assert total_bank_net == Decimal("2340.00")
        assert ledger_572_balance == Decimal("2340.00")

        # Verificar comisiones financieras en cuenta 669
        cursor.execute(
            """
            SELECT debit, credit FROM legal_journal_lines WHERE account_code = '669'
            """
        )
        lines_669 = cursor.fetchall()
        total_debit_669 = sum(Decimal(str(r[0])) for r in lines_669)
        assert total_debit_669 == Decimal("25.00")

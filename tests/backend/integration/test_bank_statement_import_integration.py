"""
Tests de integración para la importación de extractos y política "Cero Fakes".
Verifica la persistencia en base de datos de extractos y movimientos y el fallo en limpio ante falta de credenciales.
"""
import pytest
from decimal import Decimal
from app.infrastructure.database.connection_manager import write_transaction, tenant_context
from app.domain.services.norma43_parser import Norma43Parser
from app.domain.services.bank_service import BankService
from app.domain.exceptions import BankAuthenticationRequiredError
from tests.backend.unit.test_norma43_parser import _generate_norma43_content


@pytest.fixture(autouse=True)
def setup_bank_db():
    """Limpia las tablas bancarias antes de cada prueba de integración."""
    tenant_context.set("default")
    with write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM bank_statements")
    yield
    tenant_context.set("default")
    with write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM bank_statements")


def test_import_norma43_statement_persists_to_database():
    """Valida que un extracto Norma 43 se importa y persiste en bank_statements y bank_movements."""
    tenant_context.set("default")
    parser = Norma43Parser()
    movements = [
        ("260115", 121000, "2", ["COBRO FACTURA F2026-001", "ORDENANTE ACME CORP"]),
        ("260118", 45000, "1", ["PAGO ALQUILER OFICINA ENERO", "ARRENDAMIENTOS"]),
    ]
    raw = _generate_norma43_content(300000, "2", movements, 376000, "2")
    statement = parser.parse(raw, account_iban="ES9101821234123456789012")

    # Persistir mediante BankService
    statement_id = BankService.save_statement(statement, tenant_id="default")

    assert statement_id is not None

    with write_transaction("default") as conn:
        cursor = conn.cursor()
        # Verificar cabecera en bank_statements
        cursor.execute("SELECT initial_balance, final_balance, is_balanced FROM bank_statements WHERE id = ?", (statement_id,))
        st_row = cursor.fetchone()
        assert st_row is not None
        assert Decimal(str(st_row["initial_balance"])) == Decimal("3000.00")
        assert Decimal(str(st_row["final_balance"])) == Decimal("3760.00")
        assert st_row["is_balanced"] == 1

        # Verificar movimientos en bank_movements
        cursor.execute("SELECT amount, concept, reconciliation_status FROM bank_movements WHERE statement_id = ? ORDER BY id ASC", (statement_id,))
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert Decimal(str(rows[0]["amount"])) == Decimal("1210.00")
        assert rows[0]["reconciliation_status"] == "UNRECONCILED"
        assert Decimal(str(rows[1]["amount"])) == Decimal("-450.00")
        assert rows[1]["reconciliation_status"] == "UNRECONCILED"


def test_zero_fakes_policy_when_api_credentials_missing():
    """
    Verifica que ante la sincronización con un proveedor bancario sin credenciales válidas
    o con consentimiento expirado, el sistema lanza BankAuthenticationRequiredError y NO inserta ningún apunte falso.
    """
    tenant_context.set("default")
    before_count = 0
    with write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bank_movements")
        before_count = cursor.fetchone()[0]

    with pytest.raises(BankAuthenticationRequiredError) as exc_info:
        BankService.sync_connector_without_fakes(provider_name="Wise", connection_id=999, tenant_id="default")

    assert "Wise" in exc_info.value.provider_name or "Wise" in exc_info.value.message

    # Verificar que NINGÚN registro ficticio fue insertado en la base de datos
    after_count = 0
    with write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bank_movements")
        after_count = cursor.fetchone()[0]

    assert after_count == before_count

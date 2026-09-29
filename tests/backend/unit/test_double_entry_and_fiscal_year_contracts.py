"""
Tests Unitarios de Contratos Contables: Partida Doble y Ejercicios Cerrados (Spec 004).
Verifica que LedgerService impida rigurosamente apuntes descuadrados o en años cerrados.
Contrato de Discovery - Sección 6: LEDGER.
"""
import pytest
from app.domain.services.ledger_service import LedgerService
from app.domain.services.collection_service import CollectionService
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_fiscal_db():
    with _get_connection() as conn:
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.execute("DELETE FROM invoices")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.execute("DELETE FROM invoices")
        conn.commit()


def test_validate_double_entry_balanced():
    """Un asiento perfectamente balanceado debe ser validado con éxito."""
    apuntes = [
        {"account_code": "57200001", "debe": 150.25, "haber": 0.0},
        {"account_code": "43000000", "debe": 0.0, "haber": 150.25}
    ]
    assert LedgerService.validate_double_entry(apuntes) is True


def test_validate_double_entry_unbalanced_raises_value_error():
    """Un asiento descuadrado debe lanzar ValueError señalando la rotura de la partida doble."""
    apuntes = [
        {"account_code": "57200001", "debe": 150.25, "haber": 0.0},
        {"account_code": "43000000", "debe": 0.0, "haber": 140.00}
    ]
    with pytest.raises(ValueError) as exc_info:
        LedgerService.validate_double_entry(apuntes)
    assert "Partida Doble rota" in str(exc_info.value) or "descuadrado" in str(exc_info.value)


def test_record_journal_entry_in_closed_fiscal_year_raises_value_error():
    """Intentar registrar un asiento en un ejercicio cerrado debe ser rechazado."""
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO fiscal_year_status (year, is_closed, closed_at) VALUES (?, 1, datetime('now'))",
            (2024,)
        )
        conn.commit()

    entry = {
        "date": "10/05/2024",
        "concept": "Asiento extemporáneo en año cerrado",
        "entries": [
            {"account": "57200001", "debe": 200.0, "haber": 0.0},
            {"account": "43000000", "debe": 0.0, "haber": 200.0}
        ]
    }
    with pytest.raises(ValueError) as exc_info:
        LedgerService.record_journal_entry(entry)
    assert "está cerrado" in str(exc_info.value)


def test_register_payment_in_closed_fiscal_year_rejected():
    """CollectionService.register_payment no debe permitir cobros en un año cerrado."""
    # 1. Crear factura histórica cuando el año aún estaba abierto
    invoice_data = {
        "invoice_id": "FAC-2024-OLD",
        "date": "01/02/2024",
        "issuer_name": "Luis Domingo",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente Antiguo",
        "receiver_nif": "B99999999",
        "base_imponible": 100.0,
        "iva_rate": 21.0,
        "iva_amount": 21.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 121.0,
        "category": "income",
        "quarter": 1,
        "year": 2024,
        "concept": "Factura histórica de 2024",
        "status": "firmada"
    }
    InvoiceRepository.save(invoice_data)

    # 2. Posteriormente, el ejercicio 2024 se cierra formalmente
    with _get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO fiscal_year_status (year, is_closed, closed_at) VALUES (?, 1, datetime('now'))",
            (2024,)
        )
        conn.commit()

    # 3. Intentar cobrar la factura en fecha de año cerrado debe ser rechazado
    res = CollectionService.register_payment(
        invoice_id="FAC-2024-OLD",
        amount=121.0,
        payment_method="transferencia",
        date="15/02/2024",
        notes="Cobro que debe fallar por año cerrado"
    )
    assert res["status"] == "error"
    assert "ejercicio cerrado" in res["message"] or "está cerrado" in res["message"]

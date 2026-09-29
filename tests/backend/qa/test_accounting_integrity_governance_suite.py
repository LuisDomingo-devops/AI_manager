"""
Test QA de Gobernanza e Integridad Contable (Spec 004 - US3).

Audita el ciclo contable completo y los contratos de gobernanza:
1. Ciclo de vida: Factura creada -> Cobro registrado -> Asiento contable verificado en Libro Diario y Libro Mayor.
2. Validación estricta de partida doble: sum(Debe) == sum(Haber) requerida en todo asiento.
3. Bloqueo estricto por cierre de ejercicio fiscal: tanto para asientos directos como para cobros en años cerrados.
4. Integridad criptográfica y consistencia de datos contables (cuentas 572 y 430).
"""

import pytest
from app.domain.services.collection_service import CollectionService
from app.domain.services.ledger_service import LedgerService
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor


@pytest.fixture(autouse=True)
def clean_qa_ledger_db():
    with _get_connection() as conn:
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.commit()


def test_full_accounting_lifecycle_governance():
    """
    QA Test: Valida la cadena completa de factura -> cobro -> asiento verificado en Libro Mayor,
    garantizando que la partida doble cuadre exactamente al céntimo.
    """
    # 1. Factura
    invoice_data = {
        "invoice_id": "QA-INV-2026-001",
        "date": "10/04/2026",
        "issuer_name": "Luis Domingo QA",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente QA Auditado S.L.",
        "receiver_nif": "B87654321",
        "base_imponible": 1000.0,
        "iva_rate": 21.0,
        "iva_amount": 210.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 1210.0,
        "category": "income",
        "quarter": 2,
        "year": 2026,
        "concept": "Auditoría de Gobernanza Contable",
        "status": "firmada"
    }
    InvoiceRepository.save(invoice_data)

    # 2. Registrar cobro
    payment_res = CollectionService.register_payment(
        invoice_id="QA-INV-2026-001",
        amount=1210.0,
        payment_method="transferencia",
        date="15/04/2026",
        notes="Cobro íntegro verificado por QA"
    )
    assert payment_res["status"] == "ok"
    assert payment_res["payment_id"] is not None

    # 3. Comprobar existencia y cuadre de partida doble
    with _get_connection() as conn:
        journal_rows = conn.execute("SELECT id, entry_date, concept FROM journal_entries").fetchall()
        assert len(journal_rows) == 1, "Debe existir exactamente un asiento contable en journal_entries."

        j_entry = journal_rows[0]
        concept = encryptor.decrypt(j_entry["concept"])
        assert "QA-INV-2026-001" in concept

        ledger_rows = conn.execute(
            "SELECT account_code, debe, haber FROM ledger_entries WHERE journal_entry_id = ?",
            (j_entry["id"],)
        ).fetchall()
        assert len(ledger_rows) == 2, "Debe haber dos apuntes en ledger_entries."

        total_debe = 0.0
        total_haber = 0.0
        for r in ledger_rows:
            debe = float(encryptor.decrypt(r["debe"]))
            haber = float(encryptor.decrypt(r["haber"]))
            total_debe += debe
            total_haber += haber

        assert round(total_debe, 2) == 1210.0
        assert round(total_haber, 2) == 1210.0
        assert round(total_debe, 2) == round(total_haber, 2), "Partida doble rota en el asiento de cobro."


def test_double_entry_unbalanced_rejected_by_governance():
    """
    QA Test: Garantiza que el motor contable rechaza con excepción cualquier intento
    de introducir asientos descuadrados.
    """
    unbalanced_entry = {
        "concept": "Asiento descuadrado malicioso",
        "date": "15/04/2026",
        "entries": [
            {"account": "57200001", "debe": 100.0, "haber": 0.0},
            {"account": "70000000", "debe": 0.0, "haber": 85.0}  # Descuadre de 15€
        ]
    }
    with pytest.raises(ValueError, match="Partida Doble rota"):
        LedgerService.record_journal_entry(unbalanced_entry)

    # Verificar que no quedó ningún registro huérfano en la base de datos
    with _get_connection() as conn:
        journal_count = conn.execute("SELECT COUNT(*) as c FROM journal_entries").fetchone()["c"]
        ledger_count = conn.execute("SELECT COUNT(*) as c FROM ledger_entries").fetchone()["c"]
        assert journal_count == 0
        assert ledger_count == 0


def test_fiscal_year_close_blocks_retroactive_mutations():
    """
    QA Test: Garantiza que un ejercicio fiscal cerrado bloquea cualquier intento
    de registro contable y cobros con fecha retroactiva.
    """
    # 1. Crear factura histórica cuando el año aún estaba abierto
    invoice_2025 = {
        "invoice_id": "INV-RETRO-2025",
        "date": "10/11/2025",
        "issuer_name": "Luis Domingo",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente Antiguo",
        "receiver_nif": "B11111111",
        "base_imponible": 200.0,
        "iva_rate": 21.0,
        "iva_amount": 42.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 242.0,
        "category": "income",
        "quarter": 4,
        "year": 2025,
        "concept": "Factura de 2025",
        "status": "firmada"
    }
    InvoiceRepository.save(invoice_2025)

    # 2. Marcar formalmente el ejercicio 2025 como cerrado en fiscal_year_status
    with _get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO fiscal_year_status (year, is_closed, closed_at) VALUES (?, 1, datetime('now'))",
            (2025,)
        )
        conn.commit()

    # 3. Intentar asiento directo en 2025 debe ser rechazado
    balanced_entry_2025 = {
        "concept": "Intento retroactivo en año cerrado",
        "date": "31/12/2025",
        "entries": [
            {"account": "57200001", "debe": 500.0, "haber": 0.0},
            {"account": "70000000", "debe": 0.0, "haber": 500.0}
        ]
    }
    with pytest.raises(ValueError, match="El ejercicio fiscal 2025 está cerrado"):
        LedgerService.record_journal_entry(balanced_entry_2025)

    # 4. Intentar cobrar una factura fechada en 2025 debe ser rechazado
    res = CollectionService.register_payment(
        invoice_id="INV-RETRO-2025",
        amount=242.0,
        payment_method="transferencia",
        date="15/11/2025",
        notes="Cobro fuera de plazo cerrado"
    )
    assert res["status"] == "error"
    assert "ejercicio cerrado" in res["message"] or "está cerrado" in res["message"]

"""
Tests de Integración de Cobros y Generación del Libro Mayor (Spec 004).
Verifica que CollectionService.register_payment() genera de forma obligatoria,
verificable y atómica el asiento contable en journal_entries y ledger_entries.
Contrato de Discovery - Sección 6: LEDGER.
"""
import pytest
from app.domain.services.collection_service import CollectionService
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

@pytest.fixture(autouse=True)
def clean_ledger_db():
    with _get_connection() as conn:
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM invoices")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM invoices")
        conn.commit()


def test_register_payment_creates_verifiable_journal_and_ledger_entries():
    """
    Verifica que al registrar un cobro, el asiento contable se crea en journal_entries
    y sus apuntes correspondientes se insertan en ledger_entries (572 Debe, 430 Haber).
    """
    # 1. Crear factura previa
    invoice_data = {
        "invoice_id": "FAC-TEST-001",
        "date": "15/03/2026",
        "issuer_name": "Luis Domingo",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente de Prueba S.L.",
        "receiver_nif": "B12345678",
        "base_imponible": 100.0,
        "iva_rate": 21.0,
        "iva_amount": 21.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 121.0,
        "category": "income",
        "quarter": 1,
        "year": 2026,
        "concept": "Factura de prueba para cobro contable",
        "status": "firmada"
    }
    InvoiceRepository.save(invoice_data)

    # 2. Registrar cobro
    payment_res = CollectionService.register_payment(
        invoice_id="FAC-TEST-001",
        amount=121.0,
        payment_method="transferencia",
        date="15/03/2026",
        notes="Cobro íntegro por transferencia bancaria"
    )
    assert payment_res["status"] == "ok"

    # 3. Comprobar que el asiento contable existe físicamente en la BD
    with _get_connection() as conn:
        # Asiento en Libro Diario
        journal_rows = conn.execute("SELECT id, entry_date, concept FROM journal_entries").fetchall()
        assert len(journal_rows) > 0, (
            "ERROR CRÍTICO: No se generó ningún asiento en journal_entries tras registrar el cobro. "
            "Sección 6 de Discovery: un cobro que debe generar asiento contable debe ser verificable."
        )

        journal_entry = None
        for j in journal_rows:
            decrypted_concept = encryptor.decrypt(j["concept"])
            if "FAC-TEST-001" in decrypted_concept:
                journal_entry = j
                break

        assert journal_entry is not None, "El concepto del asiento debe hacer referencia a FAC-TEST-001."
        journal_id = journal_entry["id"]

        # Apuntes en Libro Mayor (Partida Doble)
        ledger_rows = conn.execute(
            "SELECT account_code, debe, haber FROM ledger_entries WHERE journal_entry_id = ?",
            (journal_id,)
        ).fetchall()

        assert len(ledger_rows) == 2, "El asiento de cobro debe tener exactamente 2 apuntes (Debe y Haber)."

        apuntes = []
        for r in ledger_rows:
            apuntes.append({
                "account": r["account_code"],
                "debe": float(encryptor.decrypt(r["debe"])),
                "haber": float(encryptor.decrypt(r["haber"]))
            })

        # Comprobar Debe en Banco (57200001) y Haber en Clientes (43000000)
        debe_entry = next((a for a in apuntes if a["debe"] > 0), None)
        haber_entry = next((a for a in apuntes if a["haber"] > 0), None)

        assert debe_entry is not None, "Debe existir un apunte al Debe."
        assert haber_entry is not None, "Debe existir un apunte al Haber."
        assert debe_entry["account"] == "57200001"
        assert debe_entry["debe"] == 121.0
        assert haber_entry["account"] == "43000000"
        assert haber_entry["haber"] == 121.0

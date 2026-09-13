import sys
import app.infrastructure.database.memory.memory as memory_module
from app.adapters.memory.memory import _get_connection
from app.domain.services.verifactu_service import VerifactuService

# Monkeypatch
memory_module.DB_PATH = 'data/memory_test.db'

with _get_connection() as conn:
    conn.execute("DELETE FROM verifactu_invoices")
    conn.commit()

invoice1 = {
    "invoice_number": "FAC-2026-0001",
    "date_of_issue": "2026-08-01",
    "issuer_nif": "12345678Z",
    "receiver_nif": "87654321A",
    "base_imponible": 100.0,
    "iva_amount": 21.0,
    "total_amount": 121.0
}
VerifactuService.register_invoice(invoice1)

invoice2 = {
    "invoice_number": "FAC-2026-0002",
    "date_of_issue": "2026-08-02",
    "issuer_nif": "12345678Z",
    "receiver_nif": "44555666B",
    "base_imponible": 200.0,
    "iva_amount": 42.0,
    "total_amount": 242.0
}
VerifactuService.register_invoice(invoice2)

with _get_connection() as conn:
    res = conn.execute("UPDATE verifactu_invoices SET total_amount = 999.0 WHERE invoice_number = 'FAC-2026-0001'")
    print("Rows updated:", res.rowcount)
    conn.commit()
    
    rows = conn.execute("SELECT * FROM verifactu_invoices").fetchall()
    print("Rows in DB:", len(rows))
    for r in rows:
        print(dict(r))

print("Integrity status:", VerifactuService.verify_chain_integrity())

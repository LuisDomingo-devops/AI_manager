import pytest
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

def test_verifactu_chain_corruption_debug():
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
    
    with _get_connection() as conn:
        rows = conn.execute("SELECT invoice_number, total_amount FROM verifactu_invoices").fetchall()
        print("\nBEFORE UPDATE:", [dict(r) for r in rows])
        
        res = conn.execute("UPDATE verifactu_invoices SET total_amount = 999.0 WHERE invoice_number = 'FAC-2026-0001'")
        print("UPDATE rowcount:", res.rowcount)
        conn.commit()
        
        rows = conn.execute("SELECT invoice_number, total_amount FROM verifactu_invoices").fetchall()
        print("AFTER UPDATE:", [dict(r) for r in rows])

    integrity = VerifactuService.verify_chain_integrity()
    print("INTEGRITY:", integrity)

if __name__ == '__main__':
    test_verifactu_chain_corruption_debug()

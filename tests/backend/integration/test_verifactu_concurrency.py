"""
Test de Integración: Estrés Transaccional Veri*Factu Concurrente (User Story 2)
Feature: specs/020-sqlite-connection-pool-concurrency
Metodología: TDD Estricto conforme a la Constitución del proyecto
"""

import concurrent.futures
import time
import pytest

from app.domain.services.verifactu_service import VerifactuService
from app.infrastructure.database.connection_manager import reset_thread_local_pool, write_transaction
from app.adapters.memory.memory import tenant_context


@pytest.fixture(autouse=True)
def setup_verifactu_test_env():
    reset_thread_local_pool()
    tenant_context.set("default")
    # Asegurar que user_profile tenga datos para emisor
    from app.utils.encryption import encryptor
    with write_transaction("default") as conn:
        conn.execute("DELETE FROM user_profile")
        conn.execute(
            "INSERT INTO user_profile (razon_social, nif, direccion, user_type) VALUES (?, ?, ?, ?)",
            (encryptor.encrypt("Autónomo Test SL"), encryptor.encrypt("B12345674"), encryptor.encrypt("Calle Mayor 1"), "autonomo"),
        )
    yield
    reset_thread_local_pool()


def test_concurrent_verifactu_invoice_registration_maintains_chain_integrity():
    """
    Verifica que bajo peticiones concurrentes de registro Veri*Factu,
    el encadenamiento criptográfico SHA-256 no se corrompe ni se producen bloqueos.
    """
    total_invoices = 20
    errors = []
    registered_numbers = []

    def register_worker(index: int):
        try:
            invoice_data = {
                "invoice_number": f"TEST-2026-{index:04d}",
                "date_of_issue": "29/09/2026",
                "issuer_nif": "B12345674",
                "receiver_nif": f"{20000000 + index}K",
                "receiver_name": f"Cliente Concurrente {index}",
                "base_imponible": float(100 + index),
                "iva_rate": 21.0,
                "iva_amount": round(float(100 + index) * 0.21, 2),
                "total_amount": round(float(100 + index) * 1.21, 2),
                "tipo_factura": "F1",
            }
            res = VerifactuService.register_invoice(invoice_data)
            if res.get("status") == "success":
                registered_numbers.append(res["invoice_number"])
            else:
                errors.append(f"Fallo en registro {index}: {res}")
        except Exception as e:
            errors.append(f"Excepción en registro {index}: {type(e).__name__}: {str(e)}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(register_worker, i) for i in range(1, total_invoices + 1)]
        concurrent.futures.wait(futures)

    if errors:
        pytest.fail(f"Errores en registro concurrente Veri*Factu: {errors[:5]}")

    assert len(registered_numbers) == total_invoices, f"Se esperaban {total_invoices} facturas registradas, se obtuvieron {len(registered_numbers)}"

    # Validar integridad criptográfica completa de la cadena Veri*Factu
    report = VerifactuService.verify_chain_integrity()
    assert report.get("status") == "valid", f"La cadena Veri*Factu se corrompió bajo concurrencia: {report}"

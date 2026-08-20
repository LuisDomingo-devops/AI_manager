import json
import uuid
from datetime import datetime
import pytest
from app.domain.services.bank_service import BankService
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

def test_multibank_qa_end_to_end_lifecycle():
    # 1. QA: Conexión por API Directa de Wise (Token API)
    unique_suffix = uuid.uuid4().hex[:6]
    wise_creds = json.dumps({"api_token": "mock_wise_token_live", "account_id": f"wise_eur_{unique_suffix}"})
    wise_id = BankService.add_connection(
        alias=f"Wise Multidivisa {unique_suffix}",
        provider="wise",
        bank_name="Wise",
        iban="BE1234567890",
        credentials_json=wise_creds
    )
    assert wise_id > 0

    # 2. QA: Sincronización en tiempo real de movimientos de Wise
    synced_count = BankService.sync_connection(wise_id)
    assert synced_count == 2

    # 3. QA: Conexión por Open Banking PSD2 (Santander) y verificación de consentimiento
    psd2_creds = json.dumps({"account_id": f"acc_gocardless_{unique_suffix}"})
    santander_id = BankService.add_connection(
        alias=f"Santander Empresa {unique_suffix}",
        provider="gocardless",
        bank_name="Santander",
        iban="ES9100491500001234567890",
        credentials_json=psd2_creds
    )
    assert santander_id > 0
    
    consent_info = BankService.check_consent_status(santander_id)
    assert consent_info["consent_status"] == "valid"
    assert consent_info["days_left"] > 100

    # 4. QA: Lista de conexiones
    connections = BankService.list_connections()
    assert len(connections) >= 2
    aliases = [c["alias"] for c in connections]
    assert f"Wise Multidivisa {unique_suffix}" in aliases
    assert f"Santander Empresa {unique_suffix}" in aliases

    # 5. QA: Crear una factura pendiente y conciliar con los movimientos sincronizados
    inv_id = f"FAC-WISE-{unique_suffix}"
    today_str = datetime.now().strftime("%d/%m/%Y")
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_id, date, issuer_name, receiver_name, total_amount, category, file_path)
            VALUES (?, ?, ?, ?, ?, 'ingreso', NULL)
        """, (
            encryptor.encrypt(inv_id),
            encryptor.encrypt(today_str),
            encryptor.encrypt("Mi Empresa SL"),
            encryptor.encrypt("Cliente Internacional"),
            encryptor.encrypt("2500.00")
        ))
        conn.commit()

    # Ejecutar conciliación automática
    reconciled_pairs = BankService.reconcile_matching_algorithm()
    assert len(reconciled_pairs) >= 1
    matched = [p for p in reconciled_pairs if p["invoice_id"] == inv_id]
    assert len(matched) == 1
    assert matched[0]["movement_amount"] == 2500.00

    # 6. QA: Comprobar reporte de no conciliados
    report = BankService.get_unreconciled_report()
    assert "movimientos_banco_pendientes" in report
    assert "facturas_pendientes" in report

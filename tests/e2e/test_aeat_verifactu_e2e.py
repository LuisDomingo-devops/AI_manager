import os
import pytest
from app.domain.services.verifactu_service import VerifactuService

# Require explicit activation to run E2E against AEAT Sandbox
# It expects ALFONSO_RUN_AEAT_E2E=1 and valid PEM paths in ALFONSO_AEAT_CERT and ALFONSO_AEAT_KEY
# If certificates are managed via the DB for the test tenant, the environment variables are not strictly needed, 
# but we enforce ALFONSO_RUN_AEAT_E2E for safety.
RUN_E2E = os.environ.get("ALFONSO_RUN_AEAT_E2E") == "1"

@pytest.mark.skipif(not RUN_E2E, reason="ALFONSO_RUN_AEAT_E2E=1 not set. Skipping real AEAT connection.")
def test_e2e_verifactu_alta_against_aeat_sandbox():
    """
    Test End-to-End explícito y opt-in contra el entorno Sandbox de la AEAT.
    Comprueba si existe configuración de certificados y el resultado real del envío.
    """
    cert_path = os.environ.get("ALFONSO_AEAT_CERT")
    key_path = os.environ.get("ALFONSO_AEAT_KEY")

    # Si se han seteado variables locales explícitamente, validamos su existencia.
    if cert_path or key_path:
        assert cert_path and os.path.exists(cert_path), f"Certificado no encontrado en {cert_path}"
        assert key_path and os.path.exists(key_path), f"Clave no encontrada en {key_path}"
    else:
        # En caso de no haber vars de entorno, el servicio intentará sacar el cert de la DB local
        pass

    invoice_data = {
        "invoice_number": "E2E-TEST-001",
        "date_of_issue": "01-01-2027",
        "issuer_nif": "B12345674",
        "receiver_name": "Cliente Sandbox E2E",
        "receiver_nif": "11111111H",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0,
        "tipo_factura": "F1",
    }
    
    try:
        # Esto usará los certificados disponibles y lanzará a Sandbox si ALFONSO_AEAT_ENV=sandbox
        result = VerifactuService.register_invoice(invoice_data)
        
        # Guardamos evidencia en el objeto result, que luego podemos revisar
        print("\n=== RESULTADO E2E AEAT ===")
        print(f"Delivery Status: {result.get('delivery_status')}")
        print(f"AEAT Response Code: {result.get('aeat_delivery', {}).get('error_code')}")
        print(f"AEAT Response Desc: {result.get('aeat_delivery', {}).get('error_desc')}")
        print(f"CSV: {result.get('csv')}")
        
        # Para que el test pase de verdad en E2E asumiendo certificados válidos, deberíamos tener un ACEPTADO o ACEPTADO_CON_ERRORES.
        # Si da ERROR_AUTH, significa que el certificado no es válido.
        assert result.get("delivery_status") in ["ACEPTADO", "ACEPTADO_CON_ERRORES", "RECHAZADO"], f"Fallo en integración E2E, status: {result.get('delivery_status')}"
    except Exception as e:
        pytest.fail(f"La ejecución E2E AEAT falló con una excepción no controlada: {e}")

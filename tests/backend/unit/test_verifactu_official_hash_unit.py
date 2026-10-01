"""
Test Unitario para el Cálculo Oficial de Huella SHA-256 según la Orden HAC/1177/2024.
Task: T009 [P] [US1]
"""

import hashlib
import pytest
from app.domain.services.verifactu_service import VerifactuService


def test_calculate_official_hash_format_hac_1177_2024():
    """Verifica que la cadena canónica utiliza pares clave=valor unidos por '&'."""
    invoice_data = {
        "issuer_nif": "B12345674",
        "invoice_number": "F2026-0001",
        "date_of_issue": "01-10-2026",
        "tipo_factura": "F1",
        "iva_amount": "210.00",
        "total_amount": "1210.00",
        "gen_timestamp": "2026-10-01T09:00:00+01:00",
    }
    prev_hash = "A" * 64

    # El formato oficial de la Orden HAC/1177/2024:
    expected_canonical = (
        f"IDEmisorFactura=B12345674&NumSerieFactura=F2026-0001&FechaExpedicionFactura=01-10-2026"
        f"&TipoRegistroDeclarado=F1&CuotaTotal=210.00&ImporteTotal=1210.00"
        f"&Huella={prev_hash}&FechaHoraHusoGenRegistro=2026-10-01T09:00:00+01:00"
    )
    expected_hash = hashlib.sha256(expected_canonical.encode("utf-8")).hexdigest().upper()

    actual_hash = VerifactuService.calculate_invoice_hash(invoice_data, prev_hash)
    assert actual_hash == expected_hash
    assert len(actual_hash) == 64
    assert actual_hash.isupper()


def test_calculate_official_hash_primer_registro_sin_ceros():
    """Verifica que el primer registro sin huella previa no usa cadenas de ceros arbitrarias."""
    invoice_data = {
        "issuer_nif": "B12345674",
        "invoice_number": "F2026-0001",
        "date_of_issue": "01-10-2026",
        "tipo_factura": "F1",
        "iva_amount": "21.00",
        "total_amount": "121.00",
        "gen_timestamp": "2026-10-01T09:00:00+01:00",
    }
    
    # En el primer registro, Huella va vacía
    expected_canonical = (
        f"IDEmisorFactura=B12345674&NumSerieFactura=F2026-0001&FechaExpedicionFactura=01-10-2026"
        f"&TipoRegistroDeclarado=F1&CuotaTotal=21.00&ImporteTotal=121.00"
        f"&Huella=&FechaHoraHusoGenRegistro=2026-10-01T09:00:00+01:00"
    )
    expected_hash = hashlib.sha256(expected_canonical.encode("utf-8")).hexdigest().upper()

    actual_hash_none = VerifactuService.calculate_invoice_hash(invoice_data, None)
    actual_hash_empty = VerifactuService.calculate_invoice_hash(invoice_data, "")

    assert actual_hash_none == expected_hash
    assert actual_hash_empty == expected_hash
    # Garantizar que no se usó "0"*64
    zeros_canonical = (
        f"IDEmisorFactura=B12345674&NumSerieFactura=F2026-0001&FechaExpedicionFactura=01-10-2026"
        f"&TipoRegistroDeclarado=F1&CuotaTotal=21.00&ImporteTotal=121.00"
        f"&Huella={'0'*64}&FechaHoraHusoGenRegistro=2026-10-01T09:00:00+01:00"
    )
    assert actual_hash_none != hashlib.sha256(zeros_canonical.encode("utf-8")).hexdigest().upper()

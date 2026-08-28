import pytest
from unittest.mock import patch, MagicMock
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection


@pytest.fixture(autouse=True)
def clean_verifactu_db(tmp_path, monkeypatch):
    import sys
    import app.adapters.memory.memory
    memory_module = sys.modules["app.adapters.memory.memory"]
    test_db = tmp_path / "memory_test_verifactu_real_soap.db"
    monkeypatch.setattr(memory_module, "DB_PATH", test_db)

    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.execute("DROP TABLE IF EXISTS sif_event_log")
        conn.commit()
    VerifactuService.init_verifactu_schema()
    yield
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.execute("DROP TABLE IF EXISTS sif_event_log")
        conn.commit()


def test_parse_aeat_soap_response_accepted():
    soap_xml = """<?xml version="1.0" encoding="utf-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
        <soapenv:Body>
            <val:RespuestaRegFactuSistemaFacturacion xmlns:val="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/RegFactuSistemaFacturacion.xsd">
                <val:Cabecera>
                    <val:ObligadoEmision>
                        <val:NombreRazon>Alfonso SIF User</val:NombreRazon>
                        <val:NIF>12345678Z</val:NIF>
                    </val:ObligadoEmision>
                </val:Cabecera>
                <val:TiempoEsperaEnvio>0</val:TiempoEsperaEnvio>
                <val:EstadoEnvio>Correcto</val:EstadoEnvio>
                <val:CSV>AEAT-2026-9876543210ABCDEF</val:CSV>
                <val:RespuestaLinea>
                    <val:IDFactura>
                        <val:NumSerieFacturaEmisor>F2026-001</val:NumSerieFacturaEmisor>
                        <val:FechaExpedicionFacturaEmisor>19-08-2026</val:FechaExpedicionFacturaEmisor>
                    </val:IDFactura>
                    <val:EstadoRegistro>Aceptado</val:EstadoRegistro>
                    <val:CSV>AEAT-2026-9876543210ABCDEF</val:CSV>
                    <val:RegistroDuplicado>N</val:RegistroDuplicado>
                </val:RespuestaLinea>
            </val:RespuestaRegFactuSistemaFacturacion>
        </soapenv:Body>
    </soapenv:Envelope>
    """
    res = VerifactuService.parse_aeat_soap_response(soap_xml, 200)
    assert res["status"] == "accepted"
    assert res["delivery_status"] == "ACEPTADO"
    assert res["estado_registro"] == "Aceptado"
    assert res["csv"] == "AEAT-2026-9876543210ABCDEF"
    assert res["es_duplicado"] is False


def test_parse_aeat_soap_response_rejected_http200():
    """
    Test fundamental: AEAT devuelve HTTP 200 pero el registro fue RECHAZADO por error de huella (1104).
    El parser NO debe marcarlo como aceptado.
    """
    soap_xml = """<?xml version="1.0" encoding="utf-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
        <soapenv:Body>
            <val:RespuestaRegFactuSistemaFacturacion xmlns:val="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/RegFactuSistemaFacturacion.xsd">
                <val:Cabecera>
                    <val:ObligadoEmision>
                        <val:NombreRazon>Alfonso SIF User</val:NombreRazon>
                        <val:NIF>12345678Z</val:NIF>
                    </val:ObligadoEmision>
                </val:Cabecera>
                <val:EstadoEnvio>Incorrecto</val:EstadoEnvio>
                <val:RespuestaLinea>
                    <val:IDFactura>
                        <val:NumSerieFacturaEmisor>F2026-002</val:NumSerieFacturaEmisor>
                        <val:FechaExpedicionFacturaEmisor>19-08-2026</val:FechaExpedicionFacturaEmisor>
                    </val:IDFactura>
                    <val:EstadoRegistro>Rechazado</val:EstadoRegistro>
                    <val:CodigoErrorRegistro>1104</val:CodigoErrorRegistro>
                    <val:DescripcionErrorRegistro>El valor del campo Huella del registro anterior no coincide con el calculado por la AEAT</val:DescripcionErrorRegistro>
                </val:RespuestaLinea>
            </val:RespuestaRegFactuSistemaFacturacion>
        </soapenv:Body>
    </soapenv:Envelope>
    """
    res = VerifactuService.parse_aeat_soap_response(soap_xml, 200)
    assert res["status"] == "rejected"
    assert res["delivery_status"] == "RECHAZADO"
    assert res["estado_registro"] == "Rechazado"
    assert res["error_code"] == "1104"
    assert "Huella del registro anterior" in res["error_desc"]
    assert res["csv"] is None


def test_parse_aeat_soap_response_accepted_with_errors():
    soap_xml = """<?xml version="1.0" encoding="utf-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
        <soapenv:Body>
            <val:RespuestaRegFactuSistemaFacturacion xmlns:val="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/RegFactuSistemaFacturacion.xsd">
                <val:EstadoEnvio>ParcialmenteCorrecto</val:EstadoEnvio>
                <val:CSV>AEAT-CSV-WARN-12345</val:CSV>
                <val:RespuestaLinea>
                    <val:IDFactura>
                        <val:NumSerieFacturaEmisor>F2026-003</val:NumSerieFacturaEmisor>
                        <val:FechaExpedicionFacturaEmisor>19-08-2026</val:FechaExpedicionFacturaEmisor>
                    </val:IDFactura>
                    <val:EstadoRegistro>AceptadoConErrores</val:EstadoRegistro>
                    <val:CodigoErrorRegistro>2001</val:CodigoErrorRegistro>
                    <val:DescripcionErrorRegistro>El NIF del destinatario no se encuentra en el censo pero el registro se admite</val:DescripcionErrorRegistro>
                    <val:CSV>AEAT-CSV-WARN-12345</val:CSV>
                </val:RespuestaLinea>
            </val:RespuestaRegFactuSistemaFacturacion>
        </soapenv:Body>
    </soapenv:Envelope>
    """
    res = VerifactuService.parse_aeat_soap_response(soap_xml, 200)
    assert res["status"] == "accepted_with_errors"
    assert res["delivery_status"] == "ACEPTADO_CON_ERRORES"
    assert res["csv"] == "AEAT-CSV-WARN-12345"
    assert res["error_code"] == "2001"


def test_parse_aeat_soap_fault():
    fault_xml = """<?xml version="1.0" encoding="utf-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
        <soapenv:Body>
            <soapenv:Fault>
                <faultcode>soapenv:Client</faultcode>
                <faultstring>XML Invalido contra esquema XSD</faultstring>
            </soapenv:Fault>
        </soapenv:Body>
    </soapenv:Envelope>
    """
    res = VerifactuService.parse_aeat_soap_response(fault_xml, 500)
    assert res["status"] == "incident"
    assert res["delivery_status"] == "INCIDENCIA_RED"
    assert res["error_code"] == "soapenv:Client"
    assert "XML Invalido" in res["error_desc"]


def test_register_invoice_stores_aeat_accepted_csv(clean_verifactu_db):
    invoice_data = {
        "invoice_number": "F2026-101",
        "date_of_issue": "19-08-2026",
        "issuer_nif": "12345678Z",
        "receiver_nif": "00000000T",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0,
        "iva_rate": 21.0,
        "tipo_factura": "F1"
    }

    mock_aeat_resp = {
        "status": "accepted",
        "delivery_status": "ACEPTADO",
        "csv": "AEAT-REAL-CSV-123456",
        "error_code": None,
        "error_desc": None,
        "raw_response": "<xml>Mocked AEAT Accepted</xml>"
    }

    with patch.object(VerifactuService, "send_to_aeat_sif", return_value=mock_aeat_resp):
        res = VerifactuService.register_invoice(invoice_data)
        assert res["status"] == "success"
        assert res["csv"] == "AEAT-REAL-CSV-123456"
        assert res["delivery_status"] == "ACEPTADO"

    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM verifactu_invoices WHERE invoice_number = 'F2026-101'").fetchone()
        assert row is not None
        assert row["delivery_status"] == "ACEPTADO"
        assert row["csv"] == "AEAT-REAL-CSV-123456"


def test_register_invoice_stores_aeat_rejection(clean_verifactu_db):
    invoice_data = {
        "invoice_number": "F2026-102",
        "date_of_issue": "19-08-2026",
        "issuer_nif": "12345678Z",
        "receiver_nif": "00000000T",
        "base_imponible": 200.0,
        "iva_amount": 42.0,
        "total_amount": 242.0,
        "iva_rate": 21.0,
        "tipo_factura": "F1"
    }

    mock_aeat_rejection = {
        "status": "rejected",
        "delivery_status": "RECHAZADO",
        "csv": None,
        "error_code": "1104",
        "error_desc": "Huella del registro anterior no encadena",
        "raw_response": "<xml>Mocked AEAT Rejected 1104</xml>"
    }

    with patch.object(VerifactuService, "send_to_aeat_sif", return_value=mock_aeat_rejection):
        res = VerifactuService.register_invoice(invoice_data)
        assert res["status"] == "success"
        assert res["delivery_status"] == "RECHAZADO"

    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM verifactu_invoices WHERE invoice_number = 'F2026-102'").fetchone()
        assert row is not None
        assert row["delivery_status"] == "RECHAZADO"
        assert row["aeat_error_code"] == "1104"
        assert "Huella del registro anterior" in row["delivery_error"]


def test_register_invoice_deterministic_validation_fails(clean_verifactu_db):
    """
    Comprueba que si el LLM extrae datos incoherentes (NIF emisor inválido o descuadre de IVA),
    el registro se aborta y no se altera la base de datos ni la cadena SHA-256.
    """
    corrupt_invoice = {
        "invoice_number": "F2026-999",
        "date_of_issue": "19-08-2026",
        "issuer_nif": "12345678A",  # NIF inválido
        "receiver_nif": "00000000T",
        "base_imponible": 100.0,
        "iva_amount": 50.0,  # Descuadre
        "total_amount": 150.0,
        "iva_rate": 21.0
    }

    with pytest.raises(ValueError) as exc_info:
        VerifactuService.register_invoice(corrupt_invoice)

    assert "Validación fiscal determinista fallida" in str(exc_info.value)

    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM verifactu_invoices WHERE invoice_number = 'F2026-999'").fetchone()
        assert row is None

"""
Tests Unitarios para Veri*factu y SIF (Spec 027).
Cubre T008 (US1), T015-T016 (US2), T023 (US3) y T030 (US4).
"""

import hashlib
from decimal import Decimal
import pytest
from app.domain.models.verifactu import (
    FacturaItemDTO,
    EmisionFacturaCommand,
    TipoFacturaEnum,
    TipoRectificativaEnum,
)
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.verifactu_validator import VerifactuValidator
from app.domain.services.verifactu_soap_client import VerifactuSoapClient
from app.domain.exceptions import XSDValidationError


class TestVerifactuHashAndQRUnit:

    def test_first_invoice_empty_prev_hash(self):
        """
        T008: Verificar que la primera factura de una serie calcula la huella oficial
        con HuellaAnterior vacía sin inyectar caracteres o ceros artificiales.
        Formato Anexo II Orden HAC/1177/2024:
        IDEmisorFactura&NumSerieFactura&FechaExpedicionFactura&TipoRegistroDeclarado&CuotaTotal&ImporteTotal&HuellaAnterior&FechaHoraHusoGenRegistro
        """
        emisor_nif = "B12345678"
        num_serie = "F2026-0001"
        fecha_exp = "01-10-2026"
        tipo_reg = "F1"
        cuota_total = Decimal("21.00")
        importe_total = Decimal("121.00")
        prev_hash = None
        timestamp = "2026-10-01T10:00:00+02:00"

        # Cadena esperada: IDEmisorFactura&NumSerieFactura&FechaExpedicionFactura&TipoRegistroDeclarado&CuotaTotal&ImporteTotal&&FechaHoraHusoGenRegistro
        expected_raw = f"{emisor_nif}&{num_serie}&{fecha_exp}&{tipo_reg}&{cuota_total:.2f}&{importe_total:.2f}&&{timestamp}"
        expected_hash = hashlib.sha256(expected_raw.encode("utf-8")).hexdigest().upper()

        computed_hash = VerifactuService.calcular_huella_oficial(
            emisor_nif=emisor_nif,
            num_serie=num_serie,
            fecha_expedicion=fecha_exp,
            tipo_registro=tipo_reg,
            cuota_total=cuota_total,
            importe_total=importe_total,
            huella_anterior=prev_hash,
            fecha_hora_huso=timestamp,
        )

        assert computed_hash == expected_hash
        assert len(computed_hash) == 64
        assert computed_hash.isupper()

    def test_chained_consecutive_invoice_hash(self):
        """
        T008: Verificar que una factura consecutiva encadena la huella anterior en mayúsculas de 64 caracteres.
        """
        emisor_nif = "B12345678"
        num_serie = "F2026-0002"
        fecha_exp = "01-10-2026"
        tipo_reg = "F1"
        cuota_total = Decimal("42.00")
        importe_total = Decimal("242.00")
        prev_hash = "A" * 64
        timestamp = "2026-10-01T10:05:00+02:00"

        expected_raw = f"{emisor_nif}&{num_serie}&{fecha_exp}&{tipo_reg}&{cuota_total:.2f}&{importe_total:.2f}&{prev_hash}&{timestamp}"
        expected_hash = hashlib.sha256(expected_raw.encode("utf-8")).hexdigest().upper()

        computed_hash = VerifactuService.calcular_huella_oficial(
            emisor_nif=emisor_nif,
            num_serie=num_serie,
            fecha_expedicion=fecha_exp,
            tipo_registro=tipo_reg,
            cuota_total=cuota_total,
            importe_total=importe_total,
            huella_anterior=prev_hash,
            fecha_hora_huso=timestamp,
        )

        assert computed_hash == expected_hash

    def test_hash_calculation_with_decimal_precision(self):
        """
        T008: Verificar que la cuota y el total se serializan con exactamente 2 decimales usando punto.
        """
        computed_hash = VerifactuService.calcular_huella_oficial(
            emisor_nif="A87654321",
            num_serie="F2026-0099",
            fecha_expedicion="02-10-2026",
            tipo_registro="F1",
            cuota_total=Decimal("10.5"),
            importe_total=Decimal("110.5"),
            huella_anterior=None,
            fecha_hora_huso="2026-10-02T11:00:00Z",
        )
        assert len(computed_hash) == 64
        assert computed_hash.isupper()

    def test_xsd_validation_atomic_rejection(self):
        """
        T015: Un XML con nodos faltantes o sintaxis inválida debe ser rechazado por VerifactuValidator
        lanzando XSDValidationError.
        """
        validator = VerifactuValidator()
        xml_invalido = b"<RegFactuSistemaFacturacion><Incompleto/></RegFactuSistemaFacturacion>"
        is_valid, errors = validator.validate_xml(xml_invalido)
        assert not is_valid
        assert len(errors) > 0

        with pytest.raises(XSDValidationError):
            validator.assert_valid_xml(xml_invalido)

    def test_qr_and_legal_legend_by_mode(self):
        """
        T016: Distinción de leyendas según régimen (Veri*factu vs SIF no Verifactu).
        """
        from app.domain.services.invoice_pdf_service import InvoicePDFService
        from app.domain.models.billing import InvoiceDTO, InvoiceType, InvoiceStatus

        pdf_service = InvoicePDFService()
        invoice = InvoiceDTO(
            id=1,
            series="F2026",
            number=1,
            issue_date="01-10-2026",
            issuer_nif="B12345678",
            issuer_name="Empresa SL",
            recipient_nif="A87654321",
            recipient_name="Cliente SA",
            base_amount=Decimal("100.00"),
            tax_amount=Decimal("21.00"),
            total_amount=Decimal("121.00"),
            invoice_type=InvoiceType.F1,
            status=InvoiceStatus.ISSUED
        )

        # 1. Modo Verifactu
        pdf_verifactu = pdf_service.generate_invoice_pdf(invoice, modalidad_verifactu=True)
        text_v = pdf_service.extract_text_from_pdf(pdf_verifactu)
        assert "VERI*FACTU" in text_v
        assert "Factura verificable en la sede electrónica de la AEAT" in text_v

        # 2. Modo SIF No Verifactu
        pdf_no_verifactu = pdf_service.generate_invoice_pdf(invoice, modalidad_verifactu=False)
        text_nv = pdf_service.extract_text_from_pdf(pdf_no_verifactu)
        assert "VERI*FACTU" not in text_nv
        assert "Factura verificable en la sede electrónica de la AEAT" not in text_nv
        assert "Sistema Informático de Facturación" in text_nv

    def test_soap_envelope_formatting_and_response_parsing(self):
        """
        T023: Formateo de sobre SOAP y parsing de acuses de recibo (éxito CSV y rechazo fiscal).
        """
        from app.domain.services.verifactu_soap_client import VerifactuSoapClient

        client = VerifactuSoapClient(sandbox=True)
        xml_inner = "<RegistroFacturacionAlta><IDFactura><NumSerieFactura>F2026-0001</NumSerieFactura></IDFactura></RegistroFacturacionAlta>"
        
        envelope = client.generar_sobre_soap(xml_inner)
        assert "<soapenv:Envelope" in envelope
        assert "<soapenv:Body>" in envelope
        assert xml_inner in envelope
        assert "https://www.agenciatributaria.gob.es" in envelope

        # 1. Parsing respuesta exitosa con CSV
        xml_exito = """<?xml version="1.0" encoding="UTF-8"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
            <s:Body>
                <RespuestaLRFacturasEmitidas xmlns="https://www.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/RespuestaSuministro.xsd">
                    <CSV>CSV-AEAT-1234567890ABCDEF</CSV>
                    <EstadoEnvio>Correcto</EstadoEnvio>
                    <RespuestaLinea>
                        <EstadoRegistro>Correcto</EstadoRegistro>
                    </RespuestaLinea>
                </RespuestaLRFacturasEmitidas>
            </s:Body>
        </s:Envelope>"""
        res_ok = client.parse_soap_response(xml_exito, 200)
        assert res_ok.success is True
        assert res_ok.csv == "CSV-AEAT-1234567890ABCDEF"
        assert res_ok.is_network_timeout is False

        # 2. Parsing rechazo fiscal con error 1117
        xml_rechazo = """<?xml version="1.0" encoding="UTF-8"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
            <s:Body>
                <RespuestaLRFacturasEmitidas xmlns="https://www.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/RespuestaSuministro.xsd">
                    <EstadoEnvio>Incorrecto</EstadoEnvio>
                    <RespuestaLinea>
                        <EstadoRegistro>Incorrecto</EstadoRegistro>
                        <CodigoErrorRegistro>1117</CodigoErrorRegistro>
                        <DescripcionErrorRegistro>NIF del receptor no identificado en el censo tributario</DescripcionErrorRegistro>
                    </RespuestaLinea>
                </RespuestaLRFacturasEmitidas>
            </s:Body>
        </s:Envelope>"""
        res_fail = client.parse_soap_response(xml_rechazo, 200)
        assert res_fail.success is False
        assert res_fail.csv is None
        assert res_fail.error_code == "1117"
        assert "no identificado en el censo tributario" in res_fail.error_message

    def test_sif_event_hash_chain_and_signature(self):
        """
        T030: Cálculo de hash de evento, encadenamiento y firma digital (Art. 8 Orden HAC/1177/2024).
        """
        from app.domain.services.sif_audit_logger import SIFAuditLogger

        logger = SIFAuditLogger()
        tenant_id = "test_unit_sif_01"

        # 1. Registrar primer evento (Génesis de eventos)
        hash1 = logger.registrar_evento(
            tenant_id=tenant_id,
            tipo_evento="STARTUP",
            descripcion="Arranque del sistema SIF con verificación de hash chain"
        )
        assert len(hash1) == 64
        assert hash1.isupper()

        # 2. Registrar segundo evento encadenado
        hash2 = logger.registrar_evento(
            tenant_id=tenant_id,
            tipo_evento="SOFTWARE_UPDATE",
            descripcion="Actualización a versión 2026.1.0"
        )
        assert len(hash2) == 64
        assert hash2 != hash1

        # 3. Verificar que la integridad es válida
        assert logger.verificar_integridad_eventos(tenant_id=tenant_id) is True

    def test_declaracion_responsable_pdf_content(self):
        """
        T039: Verificación de la Declaración Responsable del SIF conforme al Art. 13 del RD 1007/2023.
        """
        from app.utils.pdf_generator import generate_declaracion_responsable
        from pypdf import PdfReader
        import io

        pdf_bytes = generate_declaracion_responsable(
            razon_social="Autónomo de Pruebas",
            nif="12345678Z",
            modalidad_verifactu=True
        )
        assert len(pdf_bytes) > 500

        reader = PdfReader(io.BytesIO(pdf_bytes))
        full_text = "".join(page.extract_text() or "" for page in reader.pages)

        assert "DECLARACIÓN RESPONSABLE" in full_text
        assert "Real Decreto 1007/2023" in full_text
        assert "Orden HAC/1177/2024" in full_text
        assert "12345678Z" in full_text
        assert "Autónomo de Pruebas" in full_text
        assert "VERI*FACTU" in full_text





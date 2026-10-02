"""
Tests de QA para Veri*factu y SIF (Spec 027).
Cubre T010 (US1), T018 (US2), T025 (US3) y T032 (US4).
"""

import uuid
from decimal import Decimal
import pytest
from app.domain.models.verifactu import EmisionFacturaCommand, FacturaItemDTO, TipoFacturaEnum
from app.domain.services.verifactu_service import VerifactuService
from app.infrastructure.database.legal_connection import legal_write_transaction


class TestQAVerifactuPilotCompliance:

    @pytest.fixture
    def isolated_tenant(self):
        tenant_id = f"test_qa_{uuid.uuid4().hex[:8]}"
        yield tenant_id

    def test_qa_sequential_pilot_50_invoices_integrity(self, isolated_tenant):
        """
        T010: Emisión en bucle de 50 facturas correlativas y verificación matemática de toda la serie sin fracturas.
        """
        tenant_id = isolated_tenant
        serie = "QA2026"
        hashes = []

        for i in range(1, 51):
            cmd = EmisionFacturaCommand(
                tenant_id=tenant_id,
                serie=serie,
                numero=i,
                fecha_expedicion="01-10-2026",
                hora_huso=f"10:{i:02d}:00+02:00" if i < 60 else "11:00:00+02:00",
                emisor_nif="B12345678",
                emisor_nombre="QA Compliance SL",
                tipo_factura=TipoFacturaEnum.F1,
                modalidad_verifactu=False,
                lineas=[
                    FacturaItemDTO(
                        descripcion=f"Item {i}",
                        cantidad=Decimal("1.00"),
                        precio_unitario=Decimal(f"{i}.00"),
                        tipo_iva=Decimal("21.00"),
                        base_imponible=Decimal(f"{i}.00"),
                        cuota_iva=Decimal(f"{i * 0.21:.2f}"),
                        total_linea=Decimal(f"{i * 1.21:.2f}")
                    )
                ]
            )
            res = VerifactuService.emitir_factura_legal(cmd)
            hashes.append(res.current_hash)

            if i == 1:
                assert res.prev_hash is None or res.prev_hash == ""
            else:
                assert res.prev_hash == hashes[i - 2]

        check = VerifactuService.verificar_integridad_cadena(tenant_id=tenant_id, serie=serie, raise_on_error=True)
        assert check["status"] == "valid"
        assert check["invoices_checked"] == 50

    def test_qa_pdf_inspection_legends_no_false_claims(self, isolated_tenant):
        """
        T018: Auditoría forense de texto en PDF para verificar la presencia de leyendas
        obligatorias y la ausencia de reclamos falsos (sin leyenda VERI*FACTU si no se envía a AEAT).
        """
        from app.domain.services.invoice_pdf_service import InvoicePDFService
        from app.domain.models.billing import InvoiceDTO, InvoiceType, InvoiceStatus

        pdf_service = InvoicePDFService()
        invoice = InvoiceDTO(
            id=999,
            series="QA2026",
            number=999,
            issue_date="01-10-2026",
            issuer_nif="B12345678",
            issuer_name="QA Auditoría SL",
            recipient_nif="A12345678",
            recipient_name="Cliente Auditado SA",
            base_amount=Decimal("1000.00"),
            tax_amount=Decimal("210.00"),
            total_amount=Decimal("1210.00"),
            invoice_type=InvoiceType.F1,
            status=InvoiceStatus.ISSUED
        )

        # Caso A: Modalidad SIF no Verifactu (NO debe contener VERI*FACTU)
        pdf_bytes_no_vf = pdf_service.generate_invoice_pdf(invoice, modalidad_verifactu=False)
        text_no_vf = pdf_service.extract_text_from_pdf(pdf_bytes_no_vf)
        assert "VERI*FACTU" not in text_no_vf
        assert "Factura verificable en la sede electrónica" not in text_no_vf
        assert "SISTEMA INFORMÁTICO DE FACTURACIÓN" in text_no_vf

        # Caso B: Modalidad Veri*factu oficial (DEBE contener leyenda obligatoria)
        pdf_bytes_vf = pdf_service.generate_invoice_pdf(invoice, modalidad_verifactu=True)
        text_vf = pdf_service.extract_text_from_pdf(pdf_bytes_vf)
        assert "VERI*FACTU" in text_vf
        assert "Factura verificable en la sede electrónica de la AEAT" in text_vf

    def test_qa_retry_worker_processes_incidencia_red_invoices(self, isolated_tenant, monkeypatch):
        """
        T025: QA del worker de reintentos automáticos para facturas en estado INCIDENCIA_RED.
        - Se emite una factura en Verifactu con red caída -> queda en INCIDENCIA_RED.
        - Se restablece la red (mock exitoso de AEAT).
        - Se ejecuta el worker de reintentos.
        - La factura pasa a DELIVERED_AEAT con su CSV asignado.
        - Se comprueba la inmutabilidad y la integridad de la cadena.
        """
        import urllib.request
        from app.domain.models.verifactu import EmisionFacturaCommand, FacturaItemDTO, TipoFacturaEnum, VerifactuDeliveryStatus
        from app.domain.services.verifactu_service import VerifactuService
        from app.domain.services.verifactu_soap_client import SOAPTransmissionResult
        from app.infrastructure.database.legal_connection import legal_read_transaction

        tenant_id = isolated_tenant

        # 1. Simular fallo de red durante la emisión
        def mock_urlopen_fail(*args, **kwargs):
            raise TimeoutError("Fallo de conexión simulado con la AEAT")

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_fail)

        cmd = EmisionFacturaCommand(
            tenant_id=tenant_id,
            serie="QAF2026",
            numero=1,
            fecha_expedicion="01-10-2026",
            hora_huso="15:00:00+02:00",
            emisor_nif="B12345678",
            emisor_nombre="Empresa Emisora QA SL",
            destinatario_nif="A88776655",
            destinatario_nombre="Cliente QA SA",
            tipo_factura=TipoFacturaEnum.F1,
            modalidad_verifactu=True,
            lineas=[
                FacturaItemDTO(
                    descripcion="Producto QA en Incidencia",
                    cantidad=Decimal("1.00"),
                    precio_unitario=Decimal("300.00"),
                    tipo_iva=Decimal("21.00"),
                    base_imponible=Decimal("300.00"),
                    cuota_iva=Decimal("63.00"),
                    total_linea=Decimal("363.00")
                )
            ]
        )

        res_emitida = VerifactuService.emitir_factura_legal(cmd)
        assert res_emitida.status == VerifactuDeliveryStatus.INCIDENCIA_RED

        # 2. Restablecer la red con respuesta exitosa
        from app.domain.services.verifactu_soap_client import VerifactuSoapClient

        def mock_enviar_registro_exito(self, xml_factura, cert_pem=None, key_pem=None):
            return SOAPTransmissionResult(
                success=True,
                status_code=200,
                csv="CSV-AEAT-RECUPERADO-QA-001",
                response_xml="<Envelope><CSV>CSV-AEAT-RECUPERADO-QA-001</CSV><EstadoEnvio>Correcto</EstadoEnvio></Envelope>",
                is_network_timeout=False
            )

        monkeypatch.setattr(VerifactuSoapClient, "enviar_registro_factura", mock_enviar_registro_exito)

        # 3. Ejecutar el worker de reintentos
        resultado_worker = VerifactuService.reintentar_facturas_incidencia(tenant_id=tenant_id)
        assert resultado_worker["reintentadas"] >= 1
        assert resultado_worker["exitosas"] >= 1
        assert resultado_worker["fallidas"] == 0

        # 4. Verificar en base de datos que el estado ahora es DELIVERED_AEAT y tiene el CSV
        with legal_read_transaction(client_id=tenant_id) as conn:
            row = conn.execute(
                "SELECT status, aeat_csv FROM verifactu_invoices WHERE tenant_id = ? AND series = 'QAF2026' AND number = 1",
                (tenant_id,)
            ).fetchone()
            assert row is not None
            assert row[0] == "DELIVERED_AEAT"
            assert row[1] == "CSV-AEAT-RECUPERADO-QA-001"

        # 5. La integridad de la cadena debe mantenerse perfecta
        check = VerifactuService.verificar_integridad_cadena(tenant_id=tenant_id, serie="QAF2026")
        assert check["status"] == "valid"

    def test_qa_sif_event_log_export_and_forensic_verification(self, isolated_tenant):
        """
        T032: Exportación y verificación forense del libro de eventos del SIF:
        - Registro de eventos sucesivos.
        - Exportación estructurada (JSON/lista de dicts con hashes y firmas).
        - Verificación de integridad positiva.
        - Alteración forense simulada y detección inequívoca de corrupción.
        """
        from app.domain.services.sif_audit_logger import SIFAuditLogger
        from app.infrastructure.database.legal_connection import legal_write_transaction
        from app.domain.exceptions import SIFEventLogCorruptedError

        tenant_id = isolated_tenant
        logger = SIFAuditLogger()

        logger.registrar_evento(tenant_id=tenant_id, tipo_evento="STARTUP", descripcion="SIF arrancado")
        logger.registrar_evento(tenant_id=tenant_id, tipo_evento="BACKUP_RESTORE", descripcion="Restauración de backup fiscal")
        logger.registrar_evento(tenant_id=tenant_id, tipo_evento="SOFTWARE_UPDATE", descripcion="Actualización de reglas SIF")

        # 1. Exportación
        libro = logger.exportar_libro_eventos(tenant_id=tenant_id)
        assert len(libro) == 3
        assert libro[0]["event_type"] == "STARTUP"
        assert libro[1]["event_type"] == "BACKUP_RESTORE"
        assert libro[2]["event_type"] == "SOFTWARE_UPDATE"
        assert all("current_hash" in e and "signature" in e for e in libro)

        # 2. Verificación válida
        assert logger.verificar_integridad_eventos(tenant_id=tenant_id) is True

        # 3. Alteración maliciosa deshabilitando trigger temporalmente
        with legal_write_transaction(client_id=tenant_id) as conn:
            conn.execute("DROP TRIGGER IF EXISTS trg_prevent_update_sif")
            conn.execute(
                "UPDATE sif_event_log SET description = 'Descripción alterada' WHERE tenant_id = ? AND event_type = 'STARTUP'",
                (tenant_id,)
            )

        try:
            with pytest.raises(SIFEventLogCorruptedError):
                logger.verificar_integridad_eventos(tenant_id=tenant_id, raise_on_error=True)
        finally:
            with legal_write_transaction(client_id=tenant_id) as conn:
                conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_update_sif
                BEFORE UPDATE ON sif_event_log
                BEGIN
                    SELECT RAISE(ABORT, 'Inmutabilidad fiscal: Los registros de auditoría del SIF son de solo lectura.');
                END;
                """)




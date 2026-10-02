"""
Tests de Integración para Veri*factu y SIF (Spec 027).
Cubre T009 (US1), T017 (US2), T024 (US3) y T031 (US4).
"""

import uuid
from decimal import Decimal
import pytest
from app.domain.models.verifactu import EmisionFacturaCommand, FacturaItemDTO, TipoFacturaEnum
from app.domain.services.verifactu_service import VerifactuService
from app.domain.exceptions import InvoiceChainCorruptedError
from app.infrastructure.database.legal_connection import legal_write_transaction, get_legal_readonly_connection


class TestVerifactuIntegration:

    @pytest.fixture
    def isolated_tenant(self):
        tenant_id = f"test_it_{uuid.uuid4().hex[:8]}"
        yield tenant_id

    def test_sequential_invoice_chaining_and_integrity_check(self, isolated_tenant):
        """
        T009: Emisión secuencial de facturas encadenadas y verificación de integridad.
        """
        tenant_id = isolated_tenant

        cmd1 = EmisionFacturaCommand(
            tenant_id=tenant_id,
            serie="F2026",
            numero=1,
            fecha_expedicion="01-10-2026",
            hora_huso="10:00:00+02:00",
            emisor_nif="B12345678",
            emisor_nombre="Empresa Emisora S.L.",
            tipo_factura=TipoFacturaEnum.F1,
            modalidad_verifactu=False,
            lineas=[
                FacturaItemDTO(
                    descripcion="Producto A",
                    cantidad=Decimal("1.00"),
                    precio_unitario=Decimal("100.00"),
                    tipo_iva=Decimal("21.00"),
                    base_imponible=Decimal("100.00"),
                    cuota_iva=Decimal("21.00"),
                    total_linea=Decimal("121.00")
                )
            ]
        )

        res1 = VerifactuService.emitir_factura_legal(cmd1)
        assert res1.prev_hash is None or res1.prev_hash == ""
        assert len(res1.current_hash) == 64

        cmd2 = EmisionFacturaCommand(
            tenant_id=tenant_id,
            serie="F2026",
            numero=2,
            fecha_expedicion="01-10-2026",
            hora_huso="10:05:00+02:00",
            emisor_nif="B12345678",
            emisor_nombre="Empresa Emisora S.L.",
            tipo_factura=TipoFacturaEnum.F1,
            modalidad_verifactu=False,
            lineas=[
                FacturaItemDTO(
                    descripcion="Producto B",
                    cantidad=Decimal("2.00"),
                    precio_unitario=Decimal("50.00"),
                    tipo_iva=Decimal("21.00"),
                    base_imponible=Decimal("100.00"),
                    cuota_iva=Decimal("21.00"),
                    total_linea=Decimal("121.00")
                )
            ]
        )

        res2 = VerifactuService.emitir_factura_legal(cmd2)
        assert res2.prev_hash == res1.current_hash

        # Verificación de integridad intacta
        check = VerifactuService.verificar_integridad_cadena(tenant_id=tenant_id, serie="F2026")
        assert check["status"] == "valid"
        assert check["invoices_checked"] == 2

    def test_detection_of_corrupted_invoice_history(self, isolated_tenant):
        """
        T009: Detección forense de alteración maliciosa en base de datos.
        """
        tenant_id = isolated_tenant

        cmd = EmisionFacturaCommand(
            tenant_id=tenant_id,
            serie="F2026",
            numero=1,
            fecha_expedicion="01-10-2026",
            hora_huso="10:00:00+02:00",
            emisor_nif="B12345678",
            emisor_nombre="Empresa Emisora S.L.",
            tipo_factura=TipoFacturaEnum.F1,
            modalidad_verifactu=False,
            lineas=[
                FacturaItemDTO(
                    descripcion="Servicio",
                    cantidad=Decimal("1.00"),
                    precio_unitario=Decimal("50.00"),
                    tipo_iva=Decimal("21.00"),
                    base_imponible=Decimal("50.00"),
                    cuota_iva=Decimal("10.50"),
                    total_linea=Decimal("60.50")
                )
            ]
        )
        res = VerifactuService.emitir_factura_legal(cmd)

        # Alteración forzada deshabilitando temporalmente el trigger para simular corrupción a bajo nivel
        with legal_write_transaction(client_id=tenant_id) as conn:
            conn.execute("DROP TRIGGER IF EXISTS trg_prevent_update_verifactu")
            conn.execute(
                "UPDATE verifactu_invoices SET total_amount = '9999.00' WHERE tenant_id = ? AND series = 'F2026' AND number = 1",
                (tenant_id,)
            )

        try:
            with pytest.raises(InvoiceChainCorruptedError):
                VerifactuService.verificar_integridad_cadena(tenant_id=tenant_id, serie="F2026", raise_on_error=True)
        finally:
            # Recrear trigger de inmutabilidad
            with legal_write_transaction(client_id=tenant_id) as conn:
                conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_update_verifactu
                BEFORE UPDATE ON verifactu_invoices
                WHEN 
                    NEW.id != OLD.id OR 
                    NEW.invoice_number != OLD.invoice_number OR
                    NEW.base_imponible != OLD.base_imponible OR
                    NEW.iva_amount != OLD.iva_amount OR
                    NEW.total_amount != OLD.total_amount OR
                    NEW.date_of_issue != OLD.date_of_issue
                BEGIN
                    SELECT RAISE(ABORT, 'Inmutabilidad fiscal: No se permite alterar importes ni datos clave de facturas ya emitidas.');
                END;
                """)

    def test_billing_issue_endpoint_integration(self, isolated_tenant):
        """
        T017: Integración del endpoint REST POST /api/v1/billing/invoices/issue
        """
        from starlette.testclient import TestClient
        from app.main import app
        from app.config import settings

        client = TestClient(app)
        api_key = settings.ALFONSO_API_KEY
        payload = {
            "tenant_id": isolated_tenant,
            "serie": "F2026",
            "numero": 10,
            "fecha_expedicion": "01-10-2026",
            "hora_huso": "12:00:00+02:00",
            "emisor_nif": "B12345678",
            "emisor_nombre": "Empresa API Test SL",
            "destinatario_nif": "A99887766",
            "destinatario_nombre": "Cliente Final API",
            "tipo_factura": "F1",
            "modalidad_verifactu": False,
            "lineas": [
                {
                    "descripcion": "Consultoría",
                    "cantidad": 1.0,
                    "precio_unitario": 200.0,
                    "tipo_iva": 21.0,
                    "base_imponible": 200.0,
                    "cuota_iva": 42.0,
                    "total_linea": 242.0
                }
            ]
        }
        res = client.post("/api/v1/billing/invoices/issue", json=payload, headers={"X-API-Key": api_key})
        assert res.status_code == 201
        data = res.json()
        assert data["numero_factura"] == "F2026-0010"
        assert len(data["current_hash"]) == 64
        assert data["xml_valido"] is True

    def test_soap_transmission_timeout_leads_to_incidencia_red_and_preserves_invoice(self, isolated_tenant, monkeypatch):
        """
        T024: Manejo de corte de red o timeout en transmisión SOAP:
        - La factura se consolida inmutablemente.
        - Estado asignado es INCIDENCIA_RED.
        - Serie y huella quedan perfectamente aseguradas.
        """
        import urllib.request
        from app.domain.models.verifactu import VerifactuDeliveryStatus
        from app.infrastructure.database.legal_connection import legal_read_transaction

        tenant_id = isolated_tenant

        def mock_urlopen(*args, **kwargs):
            raise TimeoutError("Simulated AEAT connection timeout")

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        cmd = EmisionFacturaCommand(
            tenant_id=tenant_id,
            serie="F2026",
            numero=20,
            fecha_expedicion="01-10-2026",
            hora_huso="12:30:00+02:00",
            emisor_nif="B12345678",
            emisor_nombre="Empresa Emisora SL",
            destinatario_nif="A88776655",
            destinatario_nombre="Cliente Receptor SA",
            tipo_factura=TipoFacturaEnum.F1,
            modalidad_verifactu=True,
            lineas=[
                FacturaItemDTO(
                    descripcion="Servicio con corte de red",
                    cantidad=Decimal("1.00"),
                    precio_unitario=Decimal("100.00"),
                    tipo_iva=Decimal("21.00"),
                    base_imponible=Decimal("100.00"),
                    cuota_iva=Decimal("21.00"),
                    total_linea=Decimal("121.00")
                )
            ]
        )

        res = VerifactuService.emitir_factura_legal(cmd)
        assert res.status == VerifactuDeliveryStatus.INCIDENCIA_RED
        assert res.aeat_csv is None
        assert res.current_hash is not None

        # Verificar en base de datos
        with legal_read_transaction(client_id=tenant_id) as conn:
            row = conn.execute(
                "SELECT status, aeat_csv, current_hash FROM verifactu_invoices WHERE tenant_id = ? AND series = 'F2026' AND number = 20",
                (tenant_id,)
            ).fetchone()
            assert row is not None
            assert row[0] == "INCIDENCIA_RED"
            assert row[1] is None
            assert row[2] == res.current_hash

    def test_sif_lifecycle_events_integration(self, isolated_tenant):
        """
        T031: Registro de eventos de ciclo de vida (STARTUP, SHUTDOWN, NETWORK_OUTAGE)
        garantizando persistencia transaccional y encadenamiento en sif_event_log.
        """
        from app.domain.services.sif_audit_logger import SIFAuditLogger
        from app.infrastructure.database.legal_connection import legal_read_transaction

        tenant_id = isolated_tenant
        logger = SIFAuditLogger()

        h_start = logger.registrar_evento(tenant_id=tenant_id, tipo_evento="STARTUP", descripcion="Inicio del SIF")
        h_net = logger.registrar_evento(tenant_id=tenant_id, tipo_evento="NETWORK_OUTAGE", descripcion="Corte de red con la AEAT")
        h_shut = logger.registrar_evento(tenant_id=tenant_id, tipo_evento="SHUTDOWN", descripcion="Apagado controlado del servicio")

        assert len(h_start) == 64
        assert len(h_net) == 64
        assert len(h_shut) == 64

        with legal_read_transaction(client_id=tenant_id) as conn:
            rows = conn.execute(
                "SELECT event_type, prev_event_hash, current_hash FROM sif_event_log WHERE tenant_id = ? ORDER BY id ASC",
                (tenant_id,)
            ).fetchall()
            assert len(rows) == 3
            assert rows[0]["event_type"] == "STARTUP"
            assert rows[0]["prev_event_hash"] is None
            assert rows[0]["current_hash"] == h_start

            assert rows[1]["event_type"] == "NETWORK_OUTAGE"
            assert rows[1]["prev_event_hash"] == h_start
            assert rows[1]["current_hash"] == h_net

            assert rows[2]["event_type"] == "SHUTDOWN"
            assert rows[2]["prev_event_hash"] == h_net
            assert rows[2]["current_hash"] == h_shut




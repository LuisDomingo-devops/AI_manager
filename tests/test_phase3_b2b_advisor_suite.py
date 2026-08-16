import pytest
from datetime import datetime
from lxml import etree

from app.domain.services.b2b_einvoice_service import B2BEInvoiceService
from app.domain.services.ledger_service import LedgerService
from app.domain.services.invoice_repository import InvoiceRepository
from app.tools.server.billing_tools import (
    generate_invoice_pdf,
    export_einvoice_tool,
    update_b2b_invoice_status_tool,
    get_b2b_invoice_status_history_tool,
    export_advisor_pack_tool
)
from app.adapters.memory.memory import _get_connection, tenant_context, _init_db_schema
from app.utils.encryption import encryptor
from app.domain.planner_orchestrator import PlannerOrchestrator

@pytest.fixture(autouse=True)
def setup_test_env():
    token = tenant_context.set("b2b_phase3_tenant")
    with _get_connection() as conn:
        _init_db_schema(conn)
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.execute("DELETE FROM b2b_invoice_status_history")
        conn.execute("DELETE FROM verifactu_invoices")
        conn.execute("DELETE FROM sif_event_log")
        conn.execute("DELETE FROM user_profile")
        
        conn.execute("""
            INSERT INTO user_profile (user_type, nif, razon_social, direccion)
            VALUES (?, ?, ?, ?)
        """, (
            "autonomo",
            encryptor.encrypt("12345678Z"),
            encryptor.encrypt("LUIS DOMINGO AUTONOMO"),
            encryptor.encrypt("Calle Gran Vía 28, Madrid")
        ))
        conn.commit()
    yield
    tenant_context.reset(token)


def test_ubl_en16931_generation():
    """
    Verifica la generación de Factura Electrónica estándar UBL 2.1 conforme a la norma europea EN 16931.
    """
    invoice_data = {
        "invoice_number": "F-2026-042",
        "date_of_issue": "15/06/2026",
        "issuer_name": "LUIS DOMINGO",
        "issuer_nif": "12345678Z",
        "recipient_name": "TECNOLOGIAS AVANZADAS S.L.",
        "recipient_nif": "B88889999",
        "base_imponible": 1500.0,
        "iva_rate": 21.0,
        "iva_amount": 315.0,
        "total_amount": 1815.0,
        "concept": "Consultoría y Auditoría Técnica Software"
    }

    ubl_xml = B2BEInvoiceService.export_to_ubl_xml(invoice_data)
    assert ubl_xml.startswith("<?xml")
    
    # Parsear y verificar elementos y namespaces UBL 2.1
    root = etree.fromstring(ubl_xml.encode("utf-8"))
    
    assert "Invoice" in root.tag
    namespaces = {
        "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    }

    # CustomizationID & ProfileID (Peppol BIS 3.0 / EN 16931)
    customization_id = root.find("cbc:CustomizationID", namespaces)
    assert customization_id is not None
    assert "en16931" in customization_id.text

    # ID y Tipo de Factura
    id_elem = root.find("cbc:ID", namespaces)
    assert id_elem.text == "F-2026-042"
    type_code = root.find("cbc:InvoiceTypeCode", namespaces)
    assert type_code.text == "380" # Standard Invoice

    # Emisor y Receptor
    supplier_nif = root.find("cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID", namespaces)
    assert supplier_nif.text == "12345678Z"

    customer_nif = root.find("cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID", namespaces)
    assert customer_nif.text == "B88889999"

    # Desglose de Impuestos (TaxTotal)
    tax_amt = root.find("cac:TaxTotal/cbc:TaxAmount", namespaces)
    assert tax_amt.text == "315.00"

    # Totales Legales
    payable_amt = root.find("cac:LegalMonetaryTotal/cbc:PayableAmount", namespaces)
    assert payable_amt.text == "1815.00"

    # Línea de Factura
    line_desc = root.find("cac:InvoiceLine/cac:Item/cbc:Description", namespaces)
    assert line_desc.text == "Consultoría y Auditoría Técnica Software"


def test_b2b_status_lifecycle_workflow():
    """
    Verifica el ciclo de vida de estados de factura B2B exigido por la Ley Crea y Crece:
    1. RECEPCION_COMERCIAL
    2. ACEPTACION_CONFORME
    3. APROBACION_PAGO
    4. PAGO_EFECTIVO
    Y control de rechazos comerciales.
    """
    invoice_id = "F-2026-099"

    # 1. Acuse de recepción
    r1 = B2BEInvoiceService.update_b2b_invoice_status(invoice_id, "RECEPCION_COMERCIAL")
    assert r1["status"] == "ok"
    assert r1["current_status"] == "RECEPCION_COMERCIAL"

    # 2. Aceptación comercial
    r2 = B2BEInvoiceService.update_b2b_invoice_status(invoice_id, "ACEPTACION_CONFORME")
    assert r2["current_status"] == "ACEPTACION_CONFORME"

    # 3. Aprobación de pago (con fecha prevista)
    r3 = B2BEInvoiceService.update_b2b_invoice_status(
        invoice_id,
        "APROBACION_PAGO",
        payment_date="2026-07-31"
    )
    assert r3["current_status"] == "APROBACION_PAGO"

    # 4. Pago efectivo
    r4 = B2BEInvoiceService.update_b2b_invoice_status(
        invoice_id,
        "PAGO_EFECTIVO",
        payment_date="2026-07-30",
        payment_method="Transferencia SEPA"
    )
    assert r4["current_status"] == "PAGO_EFECTIVO"
    assert r4["payment_method"] == "Transferencia SEPA"

    # 5. Consultar trazabilidad completa
    history = B2BEInvoiceService.get_b2b_invoice_status_history(invoice_id)
    assert len(history) == 4
    assert history[0]["status"] == "RECEPCION_COMERCIAL"
    assert history[-1]["status"] == "PAGO_EFECTIVO"

    # 6. Test Rechazo Comercial y bloqueo de pago posterior
    inv_rejected = "F-2026-REJ"
    B2BEInvoiceService.update_b2b_invoice_status(inv_rejected, "RECEPCION_COMERCIAL")
    B2BEInvoiceService.update_b2b_invoice_status(inv_rejected, "RECHAZO_COMERCIAL", reason="Precio discrepante")

    with pytest.raises(ValueError) as exc:
        B2BEInvoiceService.update_b2b_invoice_status(inv_rejected, "PAGO_EFECTIVO")
    assert "RECHAZO_COMERCIAL" in str(exc.value)

    # 7. XML del mensaje de evento de estado
    status_xml = B2BEInvoiceService.generate_b2b_status_message_xml(
        invoice_id=invoice_id,
        status="PAGO_EFECTIVO",
        payment_date="2026-07-30"
    )
    assert "<B2BInvoiceStatusEvent" in status_xml
    assert "<Status>PAGO_EFECTIVO</Status>" in status_xml


def test_advisor_pack_export():
    """
    Verifica que el servicio y la herramienta del paquete de asesoría consoliden
    todos los libros contables, balances y registros fiscales del ejercicio.
    """
    # Registrar un ingreso y un gasto en 2026
    LedgerService.record_invoice_asiento({
        "category": "ingreso",
        "invoice_id": "F-2026-700",
        "date": "10/03/2026",
        "base_imponible": 2000.0,
        "iva_amount": 420.0,
        "total_amount": 2420.0
    })
    LedgerService.record_invoice_asiento({
        "category": "gasto",
        "invoice_id": "EXP-2026-700",
        "date": "15/03/2026",
        "base_imponible": 500.0,
        "iva_amount": 105.0,
        "total_amount": 605.0
    })

    pack = LedgerService.export_advisor_pack(2026)
    assert pack["year"] == 2026
    assert "libro_diario" in pack
    assert len(pack["libro_diario"]) >= 2
    assert "balance_situacion" in pack
    assert "cuenta_perdidas_y_ganancias" in pack
    assert pack["cuenta_perdidas_y_ganancias"]["resultado_explotacion"] == 1500.0
    assert "libros_registro_iva" in pack


@pytest.mark.asyncio
async def test_tools_b2b_and_advisor_endpoints():
    """
    Verifica la ejecución de las herramientas creadas a través de los entrypoints de billing_tools.
    """
    # 1. Crear una factura ordinaria firme
    res_inv = await generate_invoice_pdf(
        client_name="Cliente B2B S.A.",
        client_nif="A11223344",
        amount=1200.0,
        concept="Auditoría de Sistemas",
        confirmed_by_user=True
    )
    assert res_inv["status"] == "ok"
    inv_id = res_inv["invoice_id"]

    # 2. Herramienta de exportación UBL 2.1
    res_ubl = await export_einvoice_tool(inv_id, format_type="ubl")
    assert res_ubl["status"] == "ok"
    assert res_ubl["format"] == "ubl"
    assert "Invoice" in res_ubl["xml_preview"]

    # 3. Herramienta de exportación Facturae 3.2.2
    res_facturae = await export_einvoice_tool(inv_id, format_type="facturae")
    assert res_facturae["status"] == "ok"
    assert res_facturae["format"] == "facturae"

    # 4. Herramienta de actualización de estado B2B
    res_st = await update_b2b_invoice_status_tool(inv_id, "RECEPCION_COMERCIAL")
    assert res_st["status"] == "ok"

    # 5. Herramienta de consulta de historial de estados B2B
    res_hist = await get_b2b_invoice_status_history_tool(inv_id)
    assert res_hist["status"] == "ok"
    assert res_hist["total_events"] >= 1

    # 6. Herramienta de paquete de asesoría
    res_pack = await export_advisor_pack_tool(2026)
    assert res_pack["status"] == "ok"
    assert "pack" in res_pack


@pytest.mark.asyncio
async def test_advisor_role_rbac_isolation(monkeypatch):
    """
    Verifica que el rol 'advisor' tenga acceso a herramientas de consulta fiscal/contable
    pero tenga denegado el acceso a operaciones de modificación, borrado o transacciones bancarias.
    """
    from unittest.mock import AsyncMock, MagicMock
    orchestrator = PlannerOrchestrator()
    orchestrator.execution_engine.bridge._client_info_dict["advisor_client"] = {"role": "advisor"}

    mock_tool = AsyncMock()
    mock_tool.return_value = {"status": "ok"}
    monkeypatch.setattr("app.domain.planner_orchestrator.get_tool", lambda name, req_id: mock_tool)
    monkeypatch.setattr("app.domain.planner_orchestrator.prepare_tool_args", lambda name, args, req_id: MagicMock(ok=True, args=args))
    monkeypatch.setattr("app.domain.planner_orchestrator.vector_memory.query_facts", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.domain.planner_orchestrator._check_and_store_fact", lambda *args, **kwargs: False)

    mock_llm = AsyncMock()

    # 1. Herramienta permitida para advisor (export_advisor_pack_tool)
    mock_llm.generate.side_effect = [
        '{"tool": "export_advisor_pack_tool", "args": {"year": 2026}}',
        'Informe consolidado para el asesor.'
    ]
    res_allowed = await orchestrator.run("exportar pack", llm=mock_llm, client_id="advisor_client", session_id="test_sess_adv")
    assert res_allowed["type"] == "chat"
    mock_tool.assert_called_once()

    # 2. Herramienta denegada para advisor (cancel_invoice / delete_client / transfer)
    mock_tool.reset_mock()
    mock_llm.generate.side_effect = [
        '{"tool": "cancel_invoice", "args": {"invoice_id": "F-2026-001"}}',
        'Factura cancelada.'
    ]
    res_denied = await orchestrator.run("cancelar factura", llm=mock_llm, client_id="advisor_client", session_id="test_sess_adv")
    assert res_denied["type"] == "error"
    assert "Acceso denegado" in res_denied["message"]
    mock_tool.assert_not_called()


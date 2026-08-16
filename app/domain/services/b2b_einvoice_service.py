import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from lxml import etree

from app.adapters.memory.memory import _get_connection
from app.domain.services.verifactu_service import VerifactuService

class B2BEInvoiceService:
    """
    Servicio de Factura Electrónica B2B conforme a la Ley 18/2022 ('Crea y Crece')
    y al estándar europeo EN 16931 (UBL 2.1, Facturae 3.2.2 y Mensajería de Estados).
    """

    VALID_B2B_STATUSES = [
        "RECEPCION_COMERCIAL",
        "ACEPTACION_CONFORME",
        "RECHAZO_COMERCIAL",
        "APROBACION_PAGO",
        "PAGO_EFECTIVO"
    ]

    @classmethod
    def export_to_ubl_xml(cls, invoice_data: Dict[str, Any]) -> str:
        """
        Genera el documento XML de Factura Electrónica en estándar europeo UBL 2.1 (EN 16931 / Peppol BIS 3.0).
        """
        ns_map = {
            None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }

        invoice_elem = etree.Element("Invoice", nsmap=ns_map)

        # 1. Metadatos de Personalización y Perfil Europeo EN 16931
        etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CustomizationID").text = (
            "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
        )
        etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ProfileID").text = (
            "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
        )

        # 2. Identificación de la Factura
        invoice_id = str(invoice_data.get("invoice_number") or invoice_data.get("invoice_id") or "INV-001")
        etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = invoice_id

        # Fecha de emisión en formato YYYY-MM-DD
        date_raw = str(invoice_data.get("date_of_issue") or invoice_data.get("date") or datetime.now().strftime("%Y-%m-%d"))
        issue_date_iso = date_raw
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                issue_date_iso = datetime.strptime(date_raw, fmt).strftime("%Y-%m-%d")
                break
            except Exception:
                pass

        etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueDate").text = issue_date_iso
        
        # Tipo de Factura: 380 (Factura Comercial), 381 (Abono / Rectificativa)
        is_rect = invoice_id.startswith("R-") or "rectificativa" in str(invoice_data.get("category", "")).lower()
        invoice_type_code = "381" if is_rect else "380"
        etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoiceTypeCode").text = invoice_type_code
        etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}DocumentCurrencyCode").text = "EUR"

        # 3. Emisor (Supplier)
        supplier_party = etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingSupplierParty")
        s_party = etree.SubElement(supplier_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party")
        
        s_name = etree.SubElement(s_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyName")
        etree.SubElement(s_name, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name").text = str(invoice_data.get("issuer_name") or "LUIS DOMINGO")

        s_address = etree.SubElement(s_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PostalAddress")
        s_country = etree.SubElement(s_address, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Country")
        etree.SubElement(s_country, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IdentificationCode").text = "ES"

        s_tax = etree.SubElement(s_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyTaxScheme")
        etree.SubElement(s_tax, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CompanyID").text = str(invoice_data.get("issuer_nif") or "12345678Z")
        s_scheme = etree.SubElement(s_tax, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxScheme")
        etree.SubElement(s_scheme, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = "VAT"

        # 4. Receptor (Customer)
        customer_party = etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingCustomerParty")
        c_party = etree.SubElement(customer_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party")
        
        c_name = etree.SubElement(c_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyName")
        etree.SubElement(c_name, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name").text = str(invoice_data.get("recipient_name") or invoice_data.get("receiver_name") or "CLIENTE EMPRESA")

        c_address = etree.SubElement(c_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PostalAddress")
        c_country = etree.SubElement(c_address, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Country")
        etree.SubElement(c_country, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IdentificationCode").text = "ES"

        c_tax = etree.SubElement(c_party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyTaxScheme")
        etree.SubElement(c_tax, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CompanyID").text = str(invoice_data.get("recipient_nif") or invoice_data.get("receiver_nif") or "B87654321")
        c_scheme = etree.SubElement(c_tax, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxScheme")
        etree.SubElement(c_scheme, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = "VAT"

        # 5. Medio de pago
        payment_means = etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PaymentMeans")
        etree.SubElement(payment_means, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PaymentMeansCode").text = "30" # Credit Transfer

        # 6. Desglose de Impuestos (TaxTotal)
        base = float(invoice_data.get("base_imponible") or invoice_data.get("amount") or 0.0)
        iva_rate = float(invoice_data.get("iva_rate", 21.0))
        iva_amount = float(invoice_data.get("iva_amount") or round(base * (iva_rate / 100.0), 2))
        total_amount = float(invoice_data.get("total_amount") or round(base + iva_amount, 2))

        tax_total = etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxTotal")
        t_amt = etree.SubElement(tax_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount")
        t_amt.text = f"{iva_amount:.2f}"
        t_amt.set("currencyID", "EUR")

        tax_subtotal = etree.SubElement(tax_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxSubtotal")
        t_base = etree.SubElement(tax_subtotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxableAmount")
        t_base.text = f"{base:.2f}"
        t_base.set("currencyID", "EUR")

        t_sub_amt = etree.SubElement(tax_subtotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount")
        t_sub_amt.text = f"{iva_amount:.2f}"
        t_sub_amt.set("currencyID", "EUR")

        tax_cat = etree.SubElement(tax_subtotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxCategory")
        etree.SubElement(tax_cat, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = "S" # Standard
        etree.SubElement(tax_cat, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Percent").text = f"{iva_rate:.2f}"
        t_sch = etree.SubElement(tax_cat, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxScheme")
        etree.SubElement(t_sch, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = "VAT"

        # 7. Totales Monetarios Legales (LegalMonetaryTotal)
        legal_total = etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}LegalMonetaryTotal")
        
        l_ext = etree.SubElement(legal_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount")
        l_ext.text = f"{base:.2f}"
        l_ext.set("currencyID", "EUR")

        t_excl = etree.SubElement(legal_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxExclusiveAmount")
        t_excl.text = f"{base:.2f}"
        t_excl.set("currencyID", "EUR")

        t_incl = etree.SubElement(legal_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxInclusiveAmount")
        t_incl.text = f"{(base + iva_amount):.2f}"
        t_incl.set("currencyID", "EUR")

        payable = etree.SubElement(legal_total, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PayableAmount")
        payable.text = f"{total_amount:.2f}"
        payable.set("currencyID", "EUR")

        # 8. Línea de Factura (InvoiceLine)
        concept = str(invoice_data.get("concept") or "Servicios profesionales")
        invoice_line = etree.SubElement(invoice_elem, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}InvoiceLine")
        etree.SubElement(invoice_line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = "1"
        
        qty = etree.SubElement(invoice_line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoicedQuantity")
        qty.text = "1.00"
        qty.set("unitCode", "C62") # Unit (pieces/activities)

        line_ext = etree.SubElement(invoice_line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount")
        line_ext.text = f"{base:.2f}"
        line_ext.set("currencyID", "EUR")

        item = etree.SubElement(invoice_line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Item")
        etree.SubElement(item, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Description").text = concept
        etree.SubElement(item, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name").text = concept

        item_tax = etree.SubElement(item, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}ClassifiedTaxCategory")
        etree.SubElement(item_tax, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = "S"
        etree.SubElement(item_tax, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Percent").text = f"{iva_rate:.2f}"
        item_sch = etree.SubElement(item_tax, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxScheme")
        etree.SubElement(item_sch, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID").text = "VAT"

        price = etree.SubElement(invoice_line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Price")
        p_amt = etree.SubElement(price, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PriceAmount")
        p_amt.text = f"{base:.2f}"
        p_amt.set("currencyID", "EUR")

        # Serializar XML UBL 2.1
        xml_str = etree.tostring(invoice_elem, pretty_print=True, encoding="utf-8", xml_declaration=True).decode("utf-8")

        # Guardar en data/ubl_xml/
        xml_dir = Path(__file__).resolve().parents[3] / "data" / "ubl_xml"
        xml_dir.mkdir(parents=True, exist_ok=True)
        xml_file = xml_dir / f"{invoice_id}_ubl.xml"
        with open(xml_file, "w", encoding="utf-8") as f:
            f.write(xml_str)

        return xml_str

    @classmethod
    def export_to_facturae_xml(cls, invoice_data: Dict[str, Any]) -> str:
        """
        Exporta una factura emitida al formato oficial XML Facturae v3.2.2.
        """
        return VerifactuService.export_to_facturae_xml(invoice_data)

    @classmethod
    def update_b2b_invoice_status(
        cls,
        invoice_id: str,
        new_status: str,
        reason: Optional[str] = None,
        payment_date: Optional[str] = None,
        payment_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Registra una transición de estado obligatoria de la Ley Crea y Crece (18/2022).
        Estados: RECEPCION_COMERCIAL, ACEPTACION_CONFORME, RECHAZO_COMERCIAL, APROBACION_PAGO, PAGO_EFECTIVO.
        """
        new_status = new_status.upper().strip()
        if new_status not in cls.VALID_B2B_STATUSES:
            raise ValueError(f"Estado B2B inválido: '{new_status}'. Estados válidos: {cls.VALID_B2B_STATUSES}")

        # Comprobar historial previo
        history = cls.get_b2b_invoice_status_history(invoice_id)
        if history:
            last_status = history[-1]["status"]
            if last_status == "RECHAZO_COMERCIAL" and new_status in ("APROBACION_PAGO", "PAGO_EFECTIVO"):
                raise ValueError("No se puede aprobar el pago ni abonar una factura en estado 'RECHAZO_COMERCIAL'.")

        now_iso = datetime.now().isoformat()
        status_date = payment_date if payment_date and new_status == "PAGO_EFECTIVO" else now_iso

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO b2b_invoice_status_history (invoice_id, status, status_date, reason, payment_method, payment_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (invoice_id, new_status, status_date, reason, payment_method, payment_date))
            conn.commit()
            status_id = cursor.lastrowid

        return {
            "status": "ok",
            "history_id": status_id,
            "invoice_id": invoice_id,
            "current_status": new_status,
            "status_date": status_date,
            "reason": reason,
            "payment_method": payment_method,
            "message": f"Estado B2B de la factura {invoice_id} actualizado a '{new_status}' con éxito."
        }

    @classmethod
    def get_b2b_invoice_status_history(cls, invoice_id: str) -> List[Dict[str, Any]]:
        """
        Retorna la trazabilidad cronológica de estados comerciales de la factura.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, invoice_id, status, status_date, reason, payment_method, payment_date, created_at
                FROM b2b_invoice_status_history
                WHERE invoice_id = ?
                ORDER BY id ASC
            """, (invoice_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "invoice_id": r["invoice_id"],
                    "status": r["status"],
                    "status_date": r["status_date"],
                    "reason": r["reason"],
                    "payment_method": r["payment_method"],
                    "payment_date": r["payment_date"],
                    "created_at": r["created_at"]
                }
                for r in rows
            ]

    @classmethod
    def generate_b2b_status_message_xml(
        cls,
        invoice_id: str,
        status: str,
        status_date: Optional[str] = None,
        reason: Optional[str] = None,
        payment_date: Optional[str] = None
    ) -> str:
        """
        Genera el mensaje estructurado XML de evento de estado para el intercambio B2B.
        """
        root = etree.Element("B2BInvoiceStatusEvent", xmlns="http://www.mineco.gob.es/facturae/creaycrece/status/v1.0")
        etree.SubElement(root, "InvoiceID").text = invoice_id
        etree.SubElement(root, "Status").text = status
        etree.SubElement(root, "EventTimestamp").text = status_date or datetime.now().isoformat()
        if reason:
            etree.SubElement(root, "Reason").text = reason
        if payment_date:
            etree.SubElement(root, "PaymentDate").text = payment_date

        return etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True).decode("utf-8")

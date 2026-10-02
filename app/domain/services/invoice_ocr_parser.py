import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from app.domain.schemas import (
    InvoiceTaxBreakdownDTO,
    ExtractedInvoiceMetadataDTO,
)
from app.utils.logger import app_logger, error_logger


class InvoiceOCRParser:
    """
    Parser determinista de texto extraído por OCR para facturas emitidas conforme al RD 1619/2012.
    Extrae NIF/CIF emisor, número de factura, fecha ISO, desglose de bases y tipos de IVA,
    retenciones de IRPF y verifica el balance aritmético con Decimal.
    """

    NIF_REGEX = re.compile(r"\b([0-9A-Z][0-9]{7}[0-9A-Z])\b", re.IGNORECASE)
    
    # Patrones para identificar número de factura
    INVOICE_NUM_REGEX = re.compile(
        r"(?:Factura\s*(?:Nº|Número)?|Invoice\s*(?:#|No|Number)?|Fra\.?|Nº)\s*[:#º]?\s*([A-Za-z0-9\-_/]+)",
        re.IGNORECASE
    )

    # Patrones para fechas
    DATE_PATTERNS = [
        re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),  # YYYY-MM-DD
        re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"),  # DD/MM/YYYY
        re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b"),  # DD-MM-YYYY
    ]

    # Patrones para bases y cuotas
    TOTAL_REGEX = re.compile(
        r"(?:TOTAL\s*(?:A\s*PAGAR|FACTURA|LÍQUIDO\s*A\s*PERCIBIR|GENERAL)?|IMPORTE\s*TOTAL)\s*[:]?\s*([0-9]+(?:[\.,][0-9]{2})?)\s*€?",
        re.IGNORECASE
    )

    def _normalize_decimal(self, val_str: str) -> Decimal:
        """Convierte una cadena monetaria europea o estándar en Decimal quantizado a 2 decimales."""
        if not val_str:
            return Decimal("0.00")
        s = val_str.replace("€", "").strip()
        if "," in s and "." in s:
            # Ej: 1.250,50
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal("0.00")

    def _extract_nif(self, text: str) -> Optional[str]:
        # Buscar contexto de NIF / CIF
        for line in text.splitlines():
            if any(k in line.upper() for k in ("NIF", "CIF", "DNI", "IDENTIFICACIÓN")):
                match = self.NIF_REGEX.search(line)
                if match:
                    return match.group(1).upper()
        # Fallback a cualquier NIF válido en el documento
        match = self.NIF_REGEX.search(text)
        return match.group(1).upper() if match else None

    def _extract_sender_name(self, text: str, nif: Optional[str]) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:6]:
            if nif and nif in line:
                continue
            if not any(k in line.upper() for k in ("FACTURA", "INVOICE", "FECHA", "CLIENTE", "DIRECCIÓN")):
                if len(line) > 3:
                    return line
        return "Proveedor Comercial"

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        match = self.INVOICE_NUM_REGEX.search(text)
        if match:
            num = match.group(1).strip()
            if len(num) >= 2 and not num.isdigit() or len(num) >= 3:
                return num
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        for line in text.splitlines():
            if any(k in line.upper() for k in ("FECHA", "EMISIÓN", "EXPEDICIÓN", "DATE")):
                for pattern in self.DATE_PATTERNS:
                    m = pattern.search(line)
                    if m:
                        if len(m.group(1)) == 4:  # YYYY-MM-DD
                            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                        else:  # DD/MM/YYYY o DD-MM-YYYY
                            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        # Fallback a cualquier fecha en el texto
        for pattern in self.DATE_PATTERNS:
            m = pattern.search(text)
            if m:
                if len(m.group(1)) == 4:
                    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                else:
                    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return None

    def _extract_taxes(self, text: str) -> List[InvoiceTaxBreakdownDTO]:
        taxes = []
        
        # Buscar bloques de desglose explícitos (ej. IVA 21%, Base: 100, Cuota: 21)
        # 1. Búsqueda de líneas con porcentajes de IVA conocidos
        vat_matches = re.findall(
            r"(?:IVA\s*(?:\([^)]*\))?|TIPO\s*IVA)\s*[:]?\s*(21|10|4|0)\s*%",
            text,
            re.IGNORECASE
        )
        
        # Búsqueda específica con bases asociadas
        multi_vat_pattern = re.compile(
            r"(?:Base|Base\s*imponible)[:\s]+([0-9]+(?:[\.,][0-9]{2})?)[^0-9\n\r]*Cuota\s*IVA\s*(\d+)%?[:\s]+([0-9]+(?:[\.,][0-9]{2})?)",
            re.IGNORECASE
        )
        multi_matches = multi_vat_pattern.findall(text)
        if multi_matches:
            for b_str, r_str, a_str in multi_matches:
                taxes.append(InvoiceTaxBreakdownDTO(
                    tax_rate=Decimal(r_str),
                    tax_base=self._normalize_decimal(b_str),
                    tax_amount=self._normalize_decimal(a_str)
                ))
            return taxes

        # Si hay líneas separadas de Base Imponible e IVA
        base_match = re.search(r"Base\s*(?:Imponible)?\s*[:]?\s*([0-9]+(?:[\.,][0-9]{2})?)", text, re.IGNORECASE)
        iva_match = re.search(
            r"IVA\s*(?:Repercutido|Soportado|General|Reducido|Superreducido)?\s*(?:\((\d+)%\))?\s*[:]?\s*([0-9]+(?:[\.,][0-9]{2})?)",
            text,
            re.IGNORECASE
        )
        
        if base_match and iva_match:
            base_dec = self._normalize_decimal(base_match.group(1))
            iva_dec = self._normalize_decimal(iva_match.group(2))
            rate = Decimal("21.00")
            if iva_match.group(1):
                rate = Decimal(iva_match.group(1))
            elif vat_matches:
                rate = Decimal(vat_matches[0])
            taxes.append(InvoiceTaxBreakdownDTO(
                tax_rate=rate,
                tax_base=base_dec,
                tax_amount=iva_dec
            ))

        return taxes

    def _extract_irpf(self, text: str) -> Tuple[Decimal, Decimal]:
        irpf_rate = Decimal("0.00")
        irpf_amount = Decimal("0.00")
        
        match = re.search(
            r"Retención\s*(?:IRPF)?\s*(?:\((\d+)%\))?\s*[:]?\s*[-]?\s*([0-9]+(?:[\.,][0-9]{2})?)",
            text,
            re.IGNORECASE
        )
        if match:
            if match.group(1):
                irpf_rate = Decimal(match.group(1)).quantize(Decimal("0.01"))
            amount_str = match.group(2)
            irpf_amount = self._normalize_decimal(amount_str)
            if irpf_rate == Decimal("0.00") and irpf_amount > 0:
                irpf_rate = Decimal("15.00")

        return irpf_rate, irpf_amount

    def _extract_total(self, text: str) -> Decimal:
        matches = self.TOTAL_REGEX.findall(text)
        if matches:
            return self._normalize_decimal(matches[-1])
        return Decimal("0.00")

    def parse_invoice_text(
        self,
        text: str,
        source_email_id: str,
        pdf_path: str
    ) -> ExtractedInvoiceMetadataDTO:
        """Procesa el texto de la factura y retorna el DTO estructurado con índice de confianza."""
        nif = self._extract_nif(text) or "B00000000"
        sender_name = self._extract_sender_name(text, nif)
        invoice_num = self._extract_invoice_number(text) or f"INV-{datetime.now().strftime('%Y%m%d%H%M')}"
        issue_date = self._extract_date(text) or datetime.now().strftime("%Y-%m-%d")
        
        taxes = self._extract_taxes(text)
        irpf_rate, irpf_amount = self._extract_irpf(text)
        total_amount = self._extract_total(text)

        # Si no se detectó base pero sí total e IVA simple:
        if not taxes and total_amount > 0:
            taxes.append(InvoiceTaxBreakdownDTO(
                tax_rate=Decimal("21.00"),
                tax_base=(total_amount / Decimal("1.21")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                tax_amount=(total_amount - (total_amount / Decimal("1.21"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ))

        # Cálculo de confianza
        confidence = 0.50
        if nif and nif != "B00000000":
            confidence += 0.15
        if invoice_num and not invoice_num.startswith("INV-"):
            confidence += 0.10
        if issue_date:
            confidence += 0.10

        # Verificación de cuadre matemático: Base + IVA - IRPF == Total
        calc_total = sum(t.tax_base for t in taxes) + sum(t.tax_amount for t in taxes) - irpf_amount
        if total_amount > 0 and abs(calc_total - total_amount) == Decimal("0.00"):
            confidence += 0.15
        else:
            confidence -= 0.30

        confidence = max(0.0, min(1.0, confidence))

        # Determinar cuenta PGC sugerida según nombre o conceptos
        suggested_account = "6280001"
        suggested_name = "Suministros"
        text_upper = text.upper()
        if any(k in text_upper for k in ("TELEFÓNICA", "FIBRA", "INTERNET", "VODAFONE", "ORANGE")):
            suggested_account = "6280001"
            suggested_name = "Suministros - Comunicaciones"
        elif any(k in text_upper for k in ("LUZ", "ELECTRICIDAD", "IBERDROLA", "ENDESA", "NATURGY")):
            suggested_account = "6280002"
            suggested_name = "Suministros - Electricidad"
        elif any(k in text_upper for k in ("ASESOR", "ABOGADO", "HONORARIOS", "PROFESIONAL")):
            suggested_account = "6230000"
            suggested_name = "Servicios de profesionales independientes"
        elif any(k in text_upper for k in ("COMPRA", "MERCADERÍA", "PRODUCTOS")):
            suggested_account = "6000000"
            suggested_name = "Compras de mercaderías"

        return ExtractedInvoiceMetadataDTO(
            sender_nif=nif,
            sender_name=sender_name,
            invoice_number=invoice_num,
            issue_date=issue_date,
            taxes=taxes,
            irpf_retention_rate=irpf_rate,
            irpf_retention_amount=irpf_amount,
            total_amount=total_amount if total_amount > 0 else calc_total,
            suggested_pgc_account=suggested_account,
            suggested_pgc_account_name=suggested_name,
            source_email_id=source_email_id,
            attached_pdf_path=pdf_path,
            confidence_score=confidence
        )

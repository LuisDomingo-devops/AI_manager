"""Modelos de Dominio Inmutables para Facturación y Contabilidad.

Representan las entidades oficiales del PGC y VeriFactu (RD 1007/2023).
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"
    SUBMITTED = "SUBMITTED"


class InvoiceRecord(BaseModel):
    """Representación inmutable de una factura legal."""
    id: str
    tenant_id: str = "default"
    invoice_number: str
    issue_date: date
    recipient_tax_id: str
    recipient_name: str
    taxable_base: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: InvoiceStatus = InvoiceStatus.ISSUED
    verifactu_hash: str
    previous_hash: Optional[str] = None
    qr_payload: str
    is_rectified: bool = False
    rectified_invoice_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JournalEntryLine(BaseModel):
    """Línea de partida contable (Debe o Haber)."""
    account_code: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")


class JournalEntryRecord(BaseModel):
    """Representación inmutable de un asiento en el Libro Diario."""
    id: str
    tenant_id: str = "default"
    entry_number: int
    entry_date: date
    fiscal_year: int
    concept: str
    document_ref: Optional[str] = None
    lines: List[JournalEntryLine] = Field(default_factory=list)
    is_closed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

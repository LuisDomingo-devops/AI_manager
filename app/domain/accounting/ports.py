"""Puertos e Interfaces Formales para el Núcleo Legal y Contable.

Contrato tipado in-process para Facturación Oficial, PGC y VeriFactu.
"""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IssueInvoiceCommand(BaseModel):
    tenant_id: str = "default"
    series: str = "F2026"
    issue_date: date = Field(default_factory=date.today)
    recipient_tax_id: str
    recipient_name: str
    taxable_base: Decimal
    tax_rate: Decimal
    description: str
    is_rectified: bool = False
    rectified_invoice_number: Optional[str] = None


class InvoiceView(BaseModel):
    id: str
    invoice_number: str
    issue_date: date
    taxable_base: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    verifactu_hash: str
    qr_payload: str
    tenant_id: str = "default"


from pydantic import BaseModel, Field, field_validator, model_validator


class JournalLineDTO(BaseModel):
    """Línea individual de un asiento contable del PGC con exactitud Decimal."""
    account_code: str = Field(..., pattern=r"^\d{3,7}$", description="Código PGC de 3 a 7 dígitos numéricos")
    concept: str = Field(default="", min_length=0, max_length=255, description="Concepto del apunte")
    debit: Decimal = Field(default=Decimal("0.00"), ge=0, description="Importe al Debe")
    credit: Decimal = Field(default=Decimal("0.00"), ge=0, description="Importe al Haber")

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalizar "account" a "account_code" si es necesario
            if "account_code" not in data and "account" in data:
                data["account_code"] = str(data["account"])
        return data

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def parse_and_quantize_amount(cls, v) -> Decimal:
        if v is None:
            return Decimal("0.00")
        dec = Decimal(str(v))
        return dec.quantize(Decimal("0.01"))


class RecordJournalEntryCommand(BaseModel):
    tenant_id: str = "default"
    entry_date: date = Field(default_factory=date.today)
    fiscal_year: int
    concept: str
    document_ref: Optional[str] = None
    lines: List[JournalLineDTO] = Field(default_factory=list)

    @field_validator("lines", mode="before")
    @classmethod
    def convert_lines_to_dto(cls, v):
        if not isinstance(v, list):
            return v
        converted = []
        for item in v:
            if isinstance(item, JournalLineDTO):
                converted.append(item)
            elif isinstance(item, dict):
                converted.append(JournalLineDTO.model_validate(item))
            else:
                converted.append(item)
        return converted


class JournalEntryView(BaseModel):
    id: str
    entry_number: int
    entry_date: date
    fiscal_year: int
    concept: str
    is_balanced: bool
    tenant_id: str = "default"


class IAccountingService(ABC):
    """Interfaz exclusiva para operaciones del Plan General Contable (PGC)."""

    @abstractmethod
    def record_entry(self, command: RecordJournalEntryCommand) -> JournalEntryView:
        """Registra un asiento en el Libro Diario asegurando cuadre y correlatividad."""
        pass

    @abstractmethod
    def get_ledger(self, tenant_id: str, account_code: str, fiscal_year: int) -> List[Dict[str, Any]]:
        """Obtiene el extracto del Libro Mayor para una cuenta contable."""
        pass

    @abstractmethod
    def close_fiscal_year(self, tenant_id: str, fiscal_year: int) -> bool:
        """Ejecuta el asiento de regularización y cierre contable."""
        pass


class IVeriFactuService(ABC):
    """Interfaz exclusiva para emisión legal y encadenamiento criptográfico (RD 1007/2023)."""

    @abstractmethod
    def issue_legal_invoice(self, command: IssueInvoiceCommand) -> InvoiceView:
        """Emite una factura legal oficial con hash encadenado SHA-256 inmutable."""
        pass

    @abstractmethod
    def verify_chain_integrity(self, tenant_id: str, fiscal_year: int) -> bool:
        """Verifica criptográficamente que ningún registro histórico ha sido alterado."""
        pass

    @abstractmethod
    def get_invoice_by_number(self, tenant_id: str, invoice_number: str) -> Optional[InvoiceView]:
        """Recupera la vista pública inmutable de una factura emitida."""
        pass

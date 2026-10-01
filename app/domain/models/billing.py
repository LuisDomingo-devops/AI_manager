"""
Modelos de dominio canónicos y DTOs para Facturación, Veri*Factu, Modelos Fiscales y Bancos.
Conforme a la especificación técnica de Alfonso AI Konta y RD 1007/2023.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class InvoiceType(str, Enum):
    F1 = "F1"  # Factura ordinaria
    F2 = "F2"  # Factura simplificada (ticket)
    F3 = "F3"  # Factura emitida en sustitución de facturas simplificadas
    F4 = "F4"  # Asiento resumen de facturas
    R1 = "R1"  # Factura rectificativa: error fundado en derecho y Art. 80 Uno, Dos y Seis LIVA
    R2 = "R2"  # Factura rectificativa: Art. 80 Tres LIVA (concurso de acreedores)
    R3 = "R3"  # Factura rectificativa: Art. 80 Cuatro LIVA (créditos incobrables)
    R4 = "R4"  # Factura rectificativa: resto de causas
    R5 = "R5"  # Factura rectificativa en facturas simplificadas


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"


class RectificationMethod(str, Enum):
    SUSTITUTION = "S"
    DIFFERENCES = "I"


class InvoiceLineDTO(BaseModel):
    description: str = Field(..., min_length=1)
    quantity: float = Field(default=1.0)
    unit_price: float = Field(...)
    discount: float = Field(default=0.0, ge=0)
    vat_rate: float = Field(default=21.0, ge=0, le=100)
    subtotal: float = Field(...)


class InvoiceCreateDTO(BaseModel):
    series: str = Field(default="F2026", min_length=1)
    invoice_type: InvoiceType = Field(default=InvoiceType.F1)
    issue_date: str = Field(..., description="YYYY-MM-DD")
    operation_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    issuer_nif: str = Field(..., min_length=9)
    issuer_name: str = Field(..., min_length=2)
    recipient_nif: Optional[str] = None
    recipient_name: Optional[str] = None
    lines: List[InvoiceLineDTO] = Field(default_factory=list)
    base_amount: float = Field(...)
    tax_amount: float = Field(...)
    retention_amount: float = Field(default=0.0)
    surcharge_amount: float = Field(default=0.0)
    total_amount: float = Field(...)
    rectified_series: Optional[str] = None
    rectified_number: Optional[int] = None
    rectification_method: Optional[RectificationMethod] = None
    rectification_reason: Optional[str] = None


class InvoiceDTO(BaseModel):
    id: int
    series: str
    number: int
    invoice_type: InvoiceType
    issue_date: str
    operation_date: Optional[str] = None
    issuer_nif: str
    issuer_name: str
    recipient_nif: Optional[str] = None
    recipient_name: Optional[str] = None
    base_amount: float
    tax_amount: float
    retention_amount: float = 0.0
    surcharge_amount: float = 0.0
    total_amount: float
    rectified_series: Optional[str] = None
    rectified_number: Optional[int] = None
    rectification_method: Optional[RectificationMethod] = None
    rectification_reason: Optional[str] = None
    status: InvoiceStatus = InvoiceStatus.DRAFT
    hash_record: Optional[AuditHashDTO] = None
    created_at: Optional[str] = None


class AuditHashDTO(BaseModel):
    id: Optional[int] = None
    invoice_id: int
    previous_hash: Optional[str] = None
    canonical_payload: str
    current_hash: str
    generation_timestamp: str
    qr_url: str
    xml_content: Optional[str] = None
    aeat_submission_status: str = "LOCAL_ONLY"
    aeat_csv: Optional[str] = None


class Model303ResultDTO(BaseModel):
    fiscal_year: int
    quarter: int
    base_superreducido_4: float = 0.0
    cuota_superreducido_4: float = 0.0
    base_reducido_10: float = 0.0
    cuota_reducido_10: float = 0.0
    base_general_21: float = 0.0
    cuota_general_21: float = 0.0
    total_cuota_devengada: float = 0.0
    iva_deducible_corriente: float = 0.0
    iva_deducible_inversion: float = 0.0
    prorrata_pct: float = 100.0
    total_iva_deducible: float = 0.0
    resultado_autoliquidacion: float = 0.0
    casillas: Dict[str, float] = Field(default_factory=dict)


class Model130ResultDTO(BaseModel):
    fiscal_year: int
    quarter: int
    casilla_01_ingresos_acumulados: float = 0.0
    casilla_02_gastos_acumulados: float = 0.0
    casilla_03_rendimiento_neto: float = 0.0
    casilla_04_pago_fraccionado_previo: float = 0.0
    casilla_07_pagos_anteriores: float = 0.0
    casilla_13_deduccion: float = 0.0
    casilla_19_resultado_ingresar: float = 0.0
    casillas: Dict[str, float] = Field(default_factory=dict)


class FixedAssetDTO(BaseModel):
    id: Optional[int] = None
    code: str
    description: str
    acquisition_date: str
    start_date: str
    acquisition_value: float
    depreciation_rate: float
    accumulated_depreciation: float = 0.0
    net_book_value: float
    status: str = "ACTIVE"


class BankEntryDTO(BaseModel):
    id: Optional[int] = None
    statement_id: Optional[int] = None
    operation_date: str
    value_date: str
    concept: str
    amount: float
    balance_after: float
    reconciled_invoice_id: Optional[int] = None
    reconciliation_status: str = "UNRECONCILED"


class BankStatementDTO(BaseModel):
    id: Optional[int] = None
    source_type: str  # NORMA43, CSV, OPEN_BANKING
    account_iban: str
    initial_balance: float
    final_balance: float
    import_date: str
    entries: List[BankEntryDTO] = Field(default_factory=list)


class ReconciliationSuggestionDTO(BaseModel):
    entry_id: int
    invoice_id: int
    score: float
    matching_criteria: List[str]

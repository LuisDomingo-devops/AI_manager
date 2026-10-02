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
    RECEIVED = "RECEIVED"
    PAID = "PAID"
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


class DeclarantInfoDTO(BaseModel):
    nif: str = Field(..., min_length=9, max_length=9, description="NIF/NIE/CIF del declarante (9 caracteres)")
    name: str = Field(..., min_length=1, max_length=40, description="Apellidos y nombre o razón social")
    phone: Optional[str] = Field(None, max_length=9, description="Teléfono de contacto")
    contact_person: Optional[str] = Field(None, max_length=40, description="Persona de contacto")
    is_complementary: bool = Field(default=False, description="Indica si es declaración complementaria")
    previous_receipt_number: Optional[str] = Field(None, max_length=13, description="Nº justificante anterior si complementaria")


class Model303ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    quarter: int = Field(..., ge=1, le=4)
    base_superreducido_4: float = Field(default=0.0, description="Casilla 01: Base imponible al 4%")
    tipo_superreducido_4: float = Field(default=4.0, description="Casilla 02: Tipo 4%")
    cuota_superreducido_4: float = Field(default=0.0, description="Casilla 03: Cuota al 4%")
    base_reducido_10: float = Field(default=0.0, description="Casilla 04: Base imponible al 10%")
    tipo_reducido_10: float = Field(default=10.0, description="Casilla 05: Tipo 10%")
    cuota_reducido_10: float = Field(default=0.0, description="Casilla 06: Cuota al 10%")
    base_general_21: float = Field(default=0.0, description="Casilla 07: Base imponible al 21%")
    tipo_general_21: float = Field(default=21.0, description="Casilla 08: Tipo 21%")
    cuota_general_21: float = Field(default=0.0, description="Casilla 09: Cuota al 21%")
    total_cuota_devengada: float = Field(default=0.0, description="Casilla 27: Total cuota devengada")
    base_deducible_corriente: float = Field(default=0.0, description="Casilla 28: Base operaciones interiores corrientes")
    iva_deducible_corriente: float = Field(default=0.0, description="Casilla 29: Cuota operaciones interiores corrientes")
    base_deducible_inversion: float = Field(default=0.0, description="Casilla 30: Base bienes de inversión")
    iva_deducible_inversion: float = Field(default=0.0, description="Casilla 31: Cuota bienes de inversión")
    prorrata_pct: float = Field(default=100.0, ge=0.0, le=100.0, description="Porcentaje de prorrata aplicable")
    total_iva_deducible: float = Field(default=0.0, description="Casilla 37: Total a deducir")
    resultado_regimen_general: float = Field(default=0.0, description="Casilla 46: Diferencia (27 - 37)")
    casilla_110_compensacion_anterior: float = Field(default=0.0, ge=0.0, description="Casilla 110: Cuotas a compensar")
    resultado_autoliquidacion: float = Field(default=0.0, description="Casilla 71: Resultado final (46 - 110)")
    casillas: Dict[str, float] = Field(default_factory=dict)


class Model130ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    quarter: int = Field(..., ge=1, le=4)
    casilla_01_ingresos_acumulados: float = Field(default=0.0, description="Casilla 01: Ingresos computables acumulados")
    casilla_02_gastos_acumulados: float = Field(default=0.0, description="Casilla 02: Gastos deducibles acumulados")
    casilla_03_rendimiento_neto: float = Field(default=0.0, description="Casilla 03: Rendimiento neto (01 - 02)")
    casilla_04_pago_fraccionado_previo: float = Field(default=0.0, description="Casilla 04: 20% de casilla 03 (si > 0)")
    casilla_07_pagos_anteriores: float = Field(default=0.0, ge=0.0, description="Casilla 07: Pagos fraccionados anteriores")
    casilla_08_retenciones_soportadas: float = Field(default=0.0, ge=0.0, description="Casilla 08: Retenciones soportadas acumuladas")
    casilla_13_deduccion: float = Field(default=0.0, ge=0.0, description="Casilla 13: Deducción art. 80 bis LIRPF")
    casilla_19_resultado_ingresar: float = Field(default=0.0, description="Casilla 19: Resultado autoliquidación")
    casillas: Dict[str, float] = Field(default_factory=dict)


class Model111ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    quarter: int = Field(..., ge=1, le=4)
    perceptores_trabajo: int = Field(default=0, description="Casilla 01: Nº perceptores rendimientos trabajo")
    base_trabajo: float = Field(default=0.0, description="Casilla 02: Importe percepciones trabajo")
    retenciones_trabajo: float = Field(default=0.0, description="Casilla 03: Importe retenciones trabajo")
    perceptores_profesionales: int = Field(default=0, description="Casilla 07: Nº perceptores actividades económicas")
    base_profesionales: float = Field(default=0.0, description="Casilla 08: Importe percepciones actividades económicas")
    retenciones_profesionales: float = Field(default=0.0, description="Casilla 09: Importe retenciones actividades económicas")
    resultado_total: float = Field(default=0.0, description="Casilla 28: Total liquidación")
    casillas: Dict[str, float] = Field(default_factory=dict)


class Model115ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    quarter: int = Field(..., ge=1, le=4)
    numero_arrendadores: int = Field(default=0, description="Casilla 01: Nº perceptores arrendamientos")
    base_arrendamientos: float = Field(default=0.0, description="Casilla 02: Base de las retenciones")
    retenciones_arrendamientos: float = Field(default=0.0, description="Casilla 03: Retenciones practicadas (19%)")
    resultado_a_ingresar: float = Field(default=0.0, description="Casilla 05: Resultado a ingresar")
    casillas: Dict[str, float] = Field(default_factory=dict)


class Model390ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    total_base_devengada_21: float = 0.0
    total_cuota_devengada_21: float = 0.0
    total_base_devengada_10: float = 0.0
    total_cuota_devengada_10: float = 0.0
    total_base_devengada_4: float = 0.0
    total_cuota_devengada_4: float = 0.0
    total_base_deducible_corriente: float = 0.0
    total_cuota_deducible_corriente: float = 0.0
    total_base_deducible_inversion: float = 0.0
    total_cuota_deducible_inversion: float = 0.0
    volumen_total_operaciones: float = 0.0
    prorrata_anual_pct: float = 100.0
    regularizacion_anual: float = 0.0
    resultado_anual_declaracion: float = 0.0
    casillas: Dict[str, float] = Field(default_factory=dict)


class BoeExportResultDTO(BaseModel):
    model_code: str
    fiscal_year: int
    period: str
    filename: str
    content_raw: str
    total_bytes: int
    sha256_checksum: str
    declarant_nif: Optional[str] = None
    records_count: Optional[int] = None

    @property
    def sha256_hash(self) -> str:
        return self.sha256_checksum


class FilingSessionStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    BROWSER_LAUNCHED = "BROWSER_LAUNCHED"
    FORM_LOADED = "FORM_LOADED"
    DATA_IMPORTED = "DATA_IMPORTED"
    VALIDATED_OK = "VALIDATED_OK"
    VALIDATED_WARNINGS = "VALIDATED_WARNINGS"
    VALIDATED_ERRORS = "VALIDATED_ERRORS"
    AWAITING_USER_SIGNATURE = "AWAITING_USER_SIGNATURE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FirefoxFilingSessionDTO(BaseModel):
    session_id: str
    model_code: str
    fiscal_year: int
    quarter: int
    status: FilingSessionStatus
    browser_type: str = "firefox"
    validation_messages: List[str] = Field(default_factory=list)
    preview_url: Optional[str] = None
    created_at: str
    updated_at: str


class TaxDeclarationAuditDTO(BaseModel):
    id: Optional[int] = None
    tenant_id: str = Field(default="default", description="Identificador multi-tenant")
    model_code: str = Field(..., description="Código de modelo: 303, 130, 111, 115, 390")
    fiscal_year: int = Field(..., ge=2000, le=2100)
    period: str = Field(..., description="1T, 2T, 3T, 4T o 0A")
    declarant_nif: str = Field(..., min_length=9, max_length=9)
    declarant_name: str = Field(..., max_length=120)
    casillas_payload: Dict[str, float] = Field(default_factory=dict, description="Diccionario canónico de casillas")
    boe_file_content: str = Field(..., description="Contenido plano exacto del fichero telemático .ses")
    sha256_hash: str = Field(..., description="Hash criptográfico SHA-256 del fichero generado")
    filing_status: str = Field(default="CALCULATED", description="CALCULATED, EXPORTED, FILED_AEAT")
    aeat_csv: Optional[str] = Field(None, description="Código Seguro de Verificación emitido por la AEAT")
    filing_date: str = Field(..., description="Fecha de cálculo/presentación (YYYY-MM-DD HH:MM:SS)")
    retention_until_date: str = Field(..., description="Fecha límite obligatoria de retención legal (filing_date + 5 años)")
    created_at: str


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


from app.domain.schemas import (
    BankStatementSourceType,
    BankReconciliationStatus,
    BankMovementDTO,
    BankStatementDTO,
    ReconciliationSuggestionDTO,
    ApplyReconciliationCommand,
    ReconciliationResultDTO,
)

# Alias canónico compatible (I1):
BankEntryDTO = BankMovementDTO

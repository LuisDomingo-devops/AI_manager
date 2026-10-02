"""
Modelos de dominio y DTOs para el cumplimiento de Veri*factu y Sistemas Informáticos de Facturación (SIF).
Conforme a la Ley 11/2021, RD 1007/2023 y Orden HAC/1177/2024.
"""

from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class TipoFacturaEnum(str, Enum):
    F1 = "F1"  # Factura ordinaria
    F2 = "F2"  # Factura simplificada
    R1 = "R1"  # Rectificativa: error fundado en derecho y Art. 80 Uno, Dos y Seis LIVA
    R2 = "R2"  # Rectificativa: Art. 80 Tres LIVA (concurso acreedores)
    R3 = "R3"  # Rectificativa: Art. 80 Cuatro LIVA (créditos incobrables)
    R4 = "R4"  # Rectificativa: resto de supuestos
    R5 = "R5"  # Rectificativa en facturas simplificadas


class TipoRectificativaEnum(str, Enum):
    POR_DIFERENCIAS = "I"
    POR_SUSTITUCION = "S"


class VerifactuDeliveryStatus(str, Enum):
    LOCAL_RECORDED = "LOCAL_RECORDED"
    PENDING_DELIVERY = "PENDING_DELIVERY"
    DELIVERED_AEAT = "DELIVERED_AEAT"
    INCIDENCIA_RED = "INCIDENCIA_RED"
    REJECTED_AEAT = "REJECTED_AEAT"


class FacturaItemDTO(BaseModel):
    descripcion: str = Field(..., min_length=1, description="Concepto o descripción del ítem")
    cantidad: Decimal = Field(..., gt=0, description="Cantidad positiva")
    precio_unitario: Decimal = Field(..., ge=0, description="Precio unitario antes de impuestos")
    tipo_iva: Decimal = Field(..., description="Tipo impositivo IVA aplicable (ej. 0.00, 4.00, 5.00, 7.50, 10.00, 21.00)")
    base_imponible: Decimal = Field(..., description="Base imponible de la línea")
    cuota_iva: Decimal = Field(..., description="Cuota repercutida de la línea")
    total_linea: Decimal = Field(..., description="Total con impuestos")

    @field_validator("tipo_iva")
    @classmethod
    def validar_tipo_iva(cls, v: Decimal) -> Decimal:
        tipos_validos = {
            Decimal("0.00"), Decimal("4.00"), Decimal("5.00"),
            Decimal("7.50"), Decimal("10.00"), Decimal("21.00")
        }
        if v not in tipos_validos:
            raise ValueError(f"Tipo de IVA {v}% no reconocido por la normativa tributaria española vigente.")
        return v


class EmisionFacturaCommand(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    serie: str = Field(..., min_length=1, max_length=20, pattern=r"^[A-Z0-9_\-]+$")
    numero: int = Field(..., gt=0)
    fecha_expedicion: str = Field(..., pattern=r"^\d{2}-\d{2}-\d{4}$", description="Formato DD-MM-YYYY")
    hora_huso: str = Field(..., pattern=r"^\d{2}:\d{2}:\d{2}(\+\d{2}:\d{2}|Z)$", description="HH:MM:SS+01:00")
    emisor_nif: str = Field(..., min_length=9, max_length=9)
    emisor_nombre: str = Field(..., min_length=1)
    destinatario_nif: Optional[str] = None
    destinatario_nombre: Optional[str] = None
    tipo_factura: TipoFacturaEnum = TipoFacturaEnum.F1
    lineas: List[FacturaItemDTO] = Field(..., min_length=1)
    es_rectificativa: bool = False
    factura_rectificada_num: Optional[str] = None
    factura_rectificada_fecha: Optional[str] = None
    tipo_rectificativa: Optional[TipoRectificativaEnum] = None
    modalidad_verifactu: bool = Field(True, description="True para remisión telemática Veri*factu, False para SIF no Verifactu")


class RegistroFacturaResponseDTO(BaseModel):
    id: int
    tenant_id: str
    numero_factura: str
    fecha_expedicion: str
    cuota_total: Decimal
    importe_total: Decimal
    prev_hash: Optional[str]
    current_hash: str
    qr_url: str
    xml_valido: bool
    status: VerifactuDeliveryStatus
    aeat_csv: Optional[str] = None

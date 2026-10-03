"""
Modelos de dominio canónicos y DTOs para Facturación, Veri*Factu, Modelos Fiscales y Bancos.
Conforme a la especificación técnica de Alfonso AI Konta y RD 1007/2023.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


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

    @property
    def file_name(self) -> str:
        return self.filename

    @property
    def total_lines(self) -> int:
        return self.records_count or len(self.content_raw.splitlines())

    @property
    def record_type_1(self) -> str:
        lines = self.content_raw.splitlines()
        return lines[0] if lines else ""

    @property
    def records_type_2(self) -> List[str]:
        lines = self.content_raw.splitlines()
        return lines[1:] if len(lines) > 1 else []



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
    model_code: str = Field(..., description="Código de modelo: 303, 130, 111, 115, 390, 190, 180")
    fiscal_year: int = Field(..., ge=2000, le=2100)
    period: str = Field(..., description="1T, 2T, 3T, 4T o 0A")
    declarant_nif: str = Field(..., min_length=9, max_length=9)
    declarant_name: str = Field(..., max_length=120)
    casillas_payload: Dict[str, Any] = Field(default_factory=dict, description="Diccionario canónico de casillas o resumen")
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


class Model190PerceptorDTO(BaseModel):
    nif: str = Field(..., min_length=9, max_length=9, description="NIF/NIE del perceptor (9 caracteres)")
    name: str = Field(..., min_length=1, max_length=40, description="Apellidos y nombre o razón social")
    representative_nif: Optional[str] = Field(None, max_length=9, description="NIF representante legal")
    province_code: str = Field(default="28", min_length=2, max_length=2, description="Código provincia (01-52 o 99)")
    clave: str = Field(..., min_length=1, max_length=1, description="Clave de percepción regulatoria: A, B, C, E, F, G, H, I")
    subclave: str = Field(default="  ", min_length=2, max_length=2, description="Subclave de percepción (ej. '01', '02', '  ')")
    percepciones_dinerarias: float = Field(default=0.0, ge=0.0, description="Percepciones dinerarias íntegras")
    retenciones_practicadas: float = Field(default=0.0, ge=0.0, description="Retenciones dinerarias practicadas")
    percepciones_especie_valoracion: float = Field(default=0.0, ge=0.0, description="Valoración percepciones en especie")
    percepciones_especie_ingresos_a_cuenta: float = Field(default=0.0, ge=0.0, description="Ingresos a cuenta")
    percepciones_especie_repercutidos: float = Field(default=0.0, ge=0.0, description="Ingresos a cuenta repercutidos")
    ejercicio_devengo: int = Field(default=0, ge=0, le=2100, description="Año de devengo si son atrasos (0 si corriente)")
    discapacidad: int = Field(default=0, ge=0, le=3, description="0=Sin, 1=33%-65%, 2=65%+, 3=Movilidad reducida")
    tipo_contrato: int = Field(default=1, ge=1, le=4, description="1=General/Indefinido, 2=Temporal, 3=Sin relación laboral, 4=Relaciones esp.")
    reducciones_aplicables: int = Field(default=0, ge=0, le=2, description="Reducciones art. 18 LIRPF")
    ano_nacimiento: int = Field(default=0, ge=0, le=2100, description="Año nacimiento (0 si persona jurídica)")
    situacion_familiar: int = Field(default=3, ge=0, le=3, description="1=Soltero con hijos, 2=Casado, 3=Otras, 0=No residente/entidad")
    conyuge_nif: Optional[str] = Field(None, max_length=9, description="NIF cónyuge si situación_familiar = 2")
    conyuge_discapacidad: int = Field(default=0, ge=0, le=3, description="Discapacidad cónyuge")
    num_hijos: int = Field(default=0, ge=0, le=99, description="Hijos con derecho a mínimo por descendientes")
    num_hijos_discapacidad: int = Field(default=0, ge=0, le=99, description="Hijos con discapacidad")
    num_ascendientes: int = Field(default=0, ge=0, le=99, description="Ascendientes dependientes")

    @field_validator("clave")
    @classmethod
    def validate_clave_regulatoria(cls, v: str) -> str:
        valid_claves = {"A", "B", "C", "E", "F", "G", "H", "I"}
        v_upper = v.strip().upper()
        if v_upper not in valid_claves:
            raise ValueError(f"Clave de percepción inválida '{v}'. Debe ser una de: {', '.join(sorted(valid_claves))}")
        return v_upper


class Model190ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100, description="Ejercicio fiscal anual")
    total_perceptores: int = Field(..., ge=0, description="Número total de perceptores declarados")
    total_percepciones_dinerarias: float = Field(..., ge=0.0, description="Suma de percepciones dinerarias")
    total_retenciones_practicadas: float = Field(..., ge=0.0, description="Suma de retenciones practicadas")
    total_percepciones_especie: float = Field(default=0.0, ge=0.0, description="Suma valoración especie")
    total_ingresos_a_cuenta: float = Field(default=0.0, ge=0.0, description="Suma ingresos a cuenta")
    total_percepciones_global: float = Field(..., ge=0.0, description="Suma íntegra (dineraria + especie)")
    perceptores: List[Model190PerceptorDTO] = Field(default_factory=list, description="Lista detallada de perceptores")
    is_complementary: bool = Field(default=False)
    previous_receipt_number: Optional[str] = Field(None, max_length=13)


class Model190ReconciliationDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    total_retenciones_190: float = Field(..., ge=0.0)
    total_retenciones_111_1t: float = Field(default=0.0, ge=0.0)
    total_retenciones_111_2t: float = Field(default=0.0, ge=0.0)
    total_retenciones_111_3t: float = Field(default=0.0, ge=0.0)
    total_retenciones_111_4t: float = Field(default=0.0, ge=0.0)
    total_retenciones_111_anual: float = Field(..., ge=0.0)
    diferencia_total: float = Field(..., description="Diferencia absoluta entre 190 y sumatorio 111")
    is_cuadrado: bool = Field(..., description="True si diferencia <= 0.05 euros (tolerancia de redondeo)")
    is_tolerancia_redondeo: bool = Field(default=False, description="True si 0.00 < diferencia <= 0.05")
    desglose_por_claves: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    discrepancias_detectadas: List[str] = Field(default_factory=list)


class InmuebleArrendadoDTO(BaseModel):
    situacion_inmueble: int = Field(..., ge=1, le=4, description="1=Territorio común, 2=País Vasco/Navarra, 3=Sin referencia, 4=Extranjero")
    referencia_catastral: Optional[str] = Field(None, max_length=20, description="Referencia Catastral oficial de 20 caracteres")
    tipo_via: Optional[str] = Field(None, max_length=5, description="Tipo de vía (ej. CL, AV, PZ)")
    nombre_via: Optional[str] = Field(None, max_length=50, description="Nombre de la vía pública")
    numero: Optional[str] = Field(None, max_length=5, description="Número de finca / portal")
    municipio: Optional[str] = Field(None, max_length=30, description="Nombre del municipio")
    codigo_postal: Optional[str] = Field(None, max_length=5, description="Código postal de 5 dígitos")
    codigo_provincia: Optional[str] = Field(None, max_length=2, description="Código de provincia INE (01-52)")

    @model_validator(mode="after")
    def validate_datos_catastrales(self) -> InmuebleArrendadoDTO:
        sit = self.situacion_inmueble
        ref = (self.referencia_catastral or "").strip()
        if sit in (1, 2):
            if not ref or len(ref) != 20 or not ref.isalnum():
                raise ValueError(
                    f"Para situación catastral {sit}, la referencia catastral es obligatoria y debe tener exactamente 20 caracteres alfanuméricos."
                )
        elif sit == 3:
            if ref and len(ref) > 0:
                raise ValueError("Para situación catastral 3 (sin referencia catastral), el campo referencia_catastral debe estar vacío.")
            if not self.nombre_via or not self.nombre_via.strip():
                raise ValueError("Para situación catastral 3, es obligatorio especificar el nombre de la vía del inmueble.")
            if not self.municipio or not self.municipio.strip():
                raise ValueError("Para situación catastral 3, es obligatorio especificar el municipio del inmueble.")
            if not self.codigo_postal or len(self.codigo_postal.strip()) != 5 or not self.codigo_postal.strip().isdigit():
                raise ValueError("Para situación catastral 3, es obligatorio especificar un código postal válido de 5 dígitos.")
        elif sit == 4:
            if ref and len(ref) > 0:
                raise ValueError("Para situación catastral 4 (extranjero), la referencia catastral debe estar vacía.")
        return self


class Model180PerceptorDTO(BaseModel):
    nif: str = Field(..., min_length=9, max_length=9, description="NIF/NIE del arrendador (9 caracteres)")
    name: str = Field(..., min_length=1, max_length=40, description="Apellidos y nombre o razón social")
    province_code: str = Field(default="28", min_length=2, max_length=2, description="Código provincia (01-52 o 99)")
    base_retencion: float = Field(default=0.0, ge=0.0, description="Base de retención anual del arrendamiento")
    porcentaje_retencion: float = Field(default=19.0, ge=0.0, le=100.0, description="Porcentaje de retención aplicado")
    retencion_practicada: float = Field(default=0.0, ge=0.0, description="Retención practicada anual")
    inmueble: InmuebleArrendadoDTO = Field(..., description="Datos catastrales y domiciliarios del inmueble arrendado")


class Model180ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100, description="Ejercicio fiscal anual")
    total_perceptores: int = Field(..., ge=0, description="Número total de perceptores/inmuebles declarados")
    total_base_retenciones: float = Field(..., ge=0.0, description="Suma total de bases de retención")
    total_retenciones_practicadas: float = Field(..., ge=0.0, description="Suma total de retenciones practicadas")
    perceptores: List[Model180PerceptorDTO] = Field(default_factory=list, description="Lista detallada de perceptores e inmuebles")
    is_complementary: bool = Field(default=False)
    previous_receipt_number: Optional[str] = Field(None, max_length=13)


class Model180ReconciliationDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100)
    total_retenciones_180: float = Field(..., ge=0.0)
    total_retenciones_115_1t: float = Field(default=0.0, ge=0.0)
    total_retenciones_115_2t: float = Field(default=0.0, ge=0.0)
    total_retenciones_115_3t: float = Field(default=0.0, ge=0.0)
    total_retenciones_115_4t: float = Field(default=0.0, ge=0.0)
    total_retenciones_115_anual: float = Field(..., ge=0.0)
    diferencia_total: float = Field(..., description="Diferencia absoluta entre 180 y sumatorio 115")
    is_cuadrado: bool = Field(..., description="True si diferencia <= 0.05 euros (tolerancia de redondeo)")
    is_tolerancia_redondeo: bool = Field(default=False, description="True si 0.00 < diferencia <= 0.05")
    discrepancias_detectadas: List[str] = Field(default_factory=list)


# ==============================================================================
# MODELO 347 (Declaración Informativa de Operaciones con Terceros > 3.005,06 €)
# ==============================================================================

class Model347DeclaredDTO(BaseModel):
    nif: str = Field(..., description="NIF o CIF de la tercera persona declarada (9 posiciones)")
    name: str = Field(..., max_length=40, description="Razón social o apellidos y nombre (hasta 40 caracteres)")
    province_code: str = Field(default="99", max_length=2, description="Código de provincia de 2 dígitos o 99 si no aplica")
    operation_key: str = Field(..., description="Clave de operación: 'A' para adquisiciones/compras, 'B' para entregas/ventas")
    total_annual_amount: float = Field(..., description="Importe total anual de las operaciones con IVA/IGIC incluido")
    quarter_1_amount: float = Field(default=0.0, description="Importe de operaciones imputables al 1T")
    quarter_2_amount: float = Field(default=0.0, description="Importe de operaciones imputables al 2T")
    quarter_3_amount: float = Field(default=0.0, description="Importe de operaciones imputables al 3T")
    quarter_4_amount: float = Field(default=0.0, description="Importe de operaciones imputables al 4T")
    cash_amount: float = Field(default=0.0, description="Importe total percibido en metálico si supera 6.000,00 € en el año")
    is_cash_basis_recc: bool = Field(default=False, description="Operación acogida al Régimen Especial del Criterio de Caja")
    is_reverse_charge: bool = Field(default=False, description="Operación sujeta a Inversión del Sujeto Pasivo")

    @field_validator("operation_key")
    @classmethod
    def validate_operation_key(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if v_upper not in ("A", "B"):
            raise ValueError(f"Clave de operación inválida: '{v}'. Debe ser 'A' (compras) o 'B' (ventas).")
        return v_upper

    @field_validator("nif")
    @classmethod
    def validate_nif(cls, v: str) -> str:
        clean_nif = v.strip().upper()
        if not clean_nif:
            raise ValueError("El NIF del declarado no puede estar vacío.")
        return clean_nif

    @model_validator(mode="after")
    def validate_quarterly_sum(self) -> "Model347DeclaredDTO":
        quarter_sum = round(self.quarter_1_amount + self.quarter_2_amount + self.quarter_3_amount + self.quarter_4_amount, 2)
        annual = round(self.total_annual_amount, 2)
        if abs(quarter_sum - annual) > 0.05:
            raise ValueError(
                f"Discrepancia trimestral para NIF {self.nif}: suma de trimestres ({quarter_sum} €) "
                f"difiere del total anual ({annual} €)."
            )
        return self


class Model347ResultDTO(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2100, description="Ejercicio fiscal anual de la declaración")
    declarant_nif: str = Field(..., description="NIF o CIF del obligado tributario declarante")
    declarant_name: str = Field(..., description="Razón social o nombre completo del declarante")
    total_declared_records: int = Field(..., ge=0, description="Número total de registros declarados Tipo 2")
    total_operations_amount: float = Field(..., description="Importe total consolidado de todas las operaciones")
    total_cash_amount: float = Field(default=0.0, description="Suma total de cobros en metálico superiores a 6.000 € declarados")
    declared_records: List[Model347DeclaredDTO] = Field(default_factory=list, description="Lista de declarados Tipo 2")
    is_complementary: bool = Field(default=False, description="Indica si es declaración complementaria")
    previous_receipt_number: Optional[str] = Field(default=None, description="Número de justificante previo si es complementaria")

    @model_validator(mode="after")
    def validate_totals(self) -> "Model347ResultDTO":
        computed_count = len(self.declared_records)
        if self.total_declared_records != computed_count:
            self.total_declared_records = computed_count

        computed_ops = round(sum(d.total_annual_amount for d in self.declared_records), 2)
        if abs(self.total_operations_amount - computed_ops) > 0.05:
            self.total_operations_amount = computed_ops

        computed_cash = round(sum(d.cash_amount for d in self.declared_records), 2)
        if abs(self.total_cash_amount - computed_cash) > 0.05:
            self.total_cash_amount = computed_cash

        return self


class Model347ReconciliationDTO(BaseModel):
    fiscal_year: int
    total_annual_model_347: float
    total_quarterly_sum: float
    quarterly_difference: float
    is_mathematically_reconciled: bool
    has_rounding_tolerance: bool
    discrepancies: List[str] = Field(default_factory=list)




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

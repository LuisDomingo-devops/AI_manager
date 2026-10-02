import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

class UserProfileSchema(BaseModel):
    user_type: Literal["autónomo", "pyme"] = Field(..., description="Tipo de contribuyente")
    nif: str = Field(..., description="NIF o CIF del contribuyente")
    razon_social: str = Field(..., min_length=2, description="Nombre completo o Razón Social")
    direccion: str = Field(..., min_length=5, description="Dirección fiscal")
    cert_password: Optional[str] = Field(None, description="Contraseña del certificado digital")

    @field_validator("nif")
    @classmethod
    def validate_nif(cls, v: str) -> str:
        v = v.strip().upper()
        # Regex básico para NIF (personas físicas) y CIF (personas jurídicas) de España:
        # NIF: 8 números + 1 letra control, o letra (K, L, M, X, Y, Z) + 7 números + letra control
        # CIF: letra (A, B, C, D, E, F, G, H, J, N, P, Q, R, S, U, V, W) + 8 caracteres alfanuméricos/numéricos
        pattern = r"^[A-Z0-9][0-9]{7,8}[A-Z0-9]$"
        if not re.match(pattern, v):
            raise ValueError("El formato del NIF/CIF no es válido para España.")
        return v

class InvoiceSchema(BaseModel):
    invoice_id: str = Field(..., min_length=1, description="Identificador único de la factura")
    date: str = Field(..., description="Fecha en formato YYYY-MM-DD")
    issuer_name: str = Field(..., min_length=1, description="Nombre del emisor de la factura")
    issuer_nif: str = Field(..., description="NIF del emisor")
    receiver_name: str = Field(..., min_length=1, description="Nombre del receptor de la factura")
    receiver_nif: str = Field(..., description="NIF del receptor")
    base_imponible: float = Field(..., gt=0, description="Base imponible, debe ser mayor que 0")
    iva_rate: float = Field(default=21.0, ge=0, le=100, description="Tasa de IVA en porcentaje")
    iva_amount: float = Field(..., ge=0, description="Importe de IVA cobrado/soportado")
    irpf_rate: float = Field(default=0.0, ge=0, le=100, description="Tasa de IRPF en porcentaje")
    irpf_amount: float = Field(default=0.0, ge=0, description="Importe de retención IRPF")
    total_amount: float = Field(..., gt=0, description="Importe total de la factura")
    category: Literal["ingreso", "gasto", "income", "expense"] = Field(..., description="Categoría contable")
    quarter: int = Field(..., ge=1, le=4, description="Trimestre contable (1-4)")
    year: int = Field(..., ge=2000, le=2100, description="Año contable")
    status: Optional[str] = Field(default="pending", description="Estado de la factura")
    tax_engine_version: Optional[str] = Field(default=None, description="Versión del motor fiscal")
    requires_manual_confirmation: Optional[bool] = Field(default=False, description="Requiere revisión manual")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        v = v.strip()
        # Convertir formato DD/MM/YYYY o DD-MM-YYYY a YYYY-MM-DD
        if re.match(r"^\d{2}/\d{2}/\d{4}$", v):
            parts = v.split("/")
            v = f"{parts[2]}-{parts[1]}-{parts[0]}"
        elif re.match(r"^\d{2}-\d{2}-\d{4}$", v):
            parts = v.split("-")
            v = f"{parts[2]}-{parts[1]}-{parts[0]}"
            
        # Validar formato de fecha YYYY-MM-DD
        pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(pattern, v):
            raise ValueError(f"La fecha '{v}' debe tener el formato YYYY-MM-DD")
        return v

    @field_validator("issuer_nif", "receiver_nif")
    @classmethod
    def validate_nifs(cls, v: str) -> str:
        v = v.strip().upper().replace(" ", "").replace("-", "")
        # NIF, CIF, o VAT internacional (ej. EU372009659)
        pattern = r"^[A-Z]{0,2}[A-Z0-9]{7,15}$"
        if not re.match(pattern, v):
            raise ValueError(f"El NIF '{v}' no tiene un formato válido.")
        return v


class EmployeeCreateSchema(BaseModel):
    nif: str = Field(..., description="DNI o NIE del trabajador")
    nss: str = Field(..., min_length=10, max_length=15, description="Número de Afiliación a la Seguridad Social (NAF)")
    full_name: str = Field(..., min_length=3, description="Nombre y apellidos completos")
    email: Optional[str] = Field(None, description="Correo electrónico del empleado")
    iban: Optional[str] = Field(None, description="Cuenta bancaria IBAN para abono de nómina")
    contract_type: str = Field(default="100", description="Código de contrato (100: Indefinido T.C., 200: Indefinido T.P., etc.)")
    contribution_group: int = Field(default=1, ge=1, le=11, description="Grupo de cotización (1 al 11)")
    start_date: str = Field(..., description="Fecha de inicio del contrato (YYYY-MM-DD)")
    gross_annual_salary: float = Field(..., gt=0, description="Salario bruto anual")
    num_paychecks: int = Field(default=12, description="Número de pagas al año (12 o 14)")
    irpf_rate: float = Field(default=10.0, ge=0, le=50, description="Porcentaje de retención de IRPF")
    vacation_days_per_year: int = Field(default=30, ge=30, description="Días naturales de vacaciones al año (mínimo legal 30)")

    @field_validator("nif")
    @classmethod
    def validate_emp_nif(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) < 8:
            raise ValueError("El NIF/NIE no es válido.")
        return v

    @field_validator("start_date")
    @classmethod
    def validate_emp_date(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("La fecha debe tener formato YYYY-MM-DD.")
        return v.strip()


class EmployeeSchema(EmployeeCreateSchema):
    id: int
    monthly_base_salary: float
    vacation_days_taken: float = 0.0
    status: Literal["ACTIVE", "DISMISSED", "RESIGNED"] = "ACTIVE"
    end_date: Optional[str] = None
    created_at: str
    updated_at: str


class PayrollResultSchema(BaseModel):
    employee_id: int
    employee_name: str
    employee_nif: str
    month: int
    year: int
    salary_base: float
    extra_pay_prorata: float
    gross_total: float
    bccc: float
    bccp: float
    ss_worker_cc: float
    ss_worker_unemployment: float
    ss_worker_fp: float
    ss_worker_mei: float
    ss_worker_total: float
    ss_employer_cc: float
    ss_employer_unemployment: float
    ss_employer_fogasa: float
    ss_employer_fp: float
    ss_employer_mei: float
    ss_employer_atep: float
    ss_employer_total: float
    irpf_rate: float
    irpf_amount: float
    net_salary: float
    total_cost_company: float


class SettlementResultSchema(BaseModel):
    employee_id: int
    employee_name: str
    employee_nif: str
    termination_type: Literal["VOLUNTARY_RESIGNATION", "OBJECTIVE_DISMISSAL", "DISCIPLINARY_DISMISSAL"]
    termination_date: str
    worked_days_month: int
    worked_days_amount: float
    extra_pays_pending: float
    vacation_pending_days: float
    vacation_pending_amount: float
    seniority_years: float
    seniority_months: int
    daily_regulatory_salary: float
    indemnity_days_total: float
    indemnity_amount: float
    total_settlement: float
    is_exempt_irpf: bool


# ==============================================================================
# SPEC-030: GESTIÓN DE RRHH, NÓMINAS IRPF OFICIAL, SILTRA TGSS Y PGC
# ==============================================================================
from enum import Enum

class EmployeeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    LEAVE = "LEAVE"
    DISMISSED = "DISMISSED"

class IrpfFamilySituation(int, Enum):
    SITUATION_1 = 1  # Soltero, viudo, divorciado con hijos a cargo exclusivo (monoparental)
    SITUATION_2 = 2  # Casado cuyo cónyuge no percibe rentas anuales superiores a 1.500 €
    SITUATION_3 = 3  # Situación general / resto de supuestos

class EmployeeContractDTO(BaseModel):
    id: Optional[int] = None
    nif: str = Field(..., description="NIF o NIE español con letra de control válida")
    naf: str = Field(..., description="Número de Afiliación a la Seguridad Social (12 dígitos numéricos)")
    full_name: str = Field(..., min_length=3, max_length=150)
    email: Optional[str] = None
    iban: str = Field(..., pattern=r"^ES\d{22}$", description="Código de cuenta bancaria IBAN español")
    annual_gross_salary: Decimal = Field(..., gt=Decimal("0.00"), description="Salario bruto anual en euros")
    num_paychecks: int = Field(default=12, ge=12, le=14, description="Número de pagas (12 o 14)")
    contract_code: str = Field(default="100", pattern=r"^\d{3}$", description="Código de contrato SEPE (ej. 100 Indefinido TC, 200 Indefinido TP, 401)")
    contribution_group: int = Field(..., ge=1, le=11, description="Grupo de cotización a la TGSS (01 al 11)")
    cnae_code: str = Field(default="6201", pattern=r"^\d{4}$", description="Código CNAE 2009 de la actividad")
    irpf_situation: IrpfFamilySituation = Field(default=IrpfFamilySituation.SITUATION_3, description="Situación familiar Modelo 145")
    num_descendants: int = Field(default=0, ge=0, description="Hijos o descendientes a cargo")
    num_descendants_under_3: int = Field(default=0, ge=0, description="Descendientes a cargo menores de 3 años")
    disability_grade: int = Field(default=0, ge=0, le=100, description="Grado de discapacidad reconocido (%)")
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha de alta del contrato (AAAA-MM-DD)")
    end_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha de baja laboral si aplica")
    status: EmployeeStatus = Field(default=EmployeeStatus.ACTIVE)

    @field_validator("nif")
    @classmethod
    def validate_nif_nie(cls, v: str) -> str:
        clean = v.strip().upper()
        nif_pattern = r"^[0-9XYZ][0-9]{7}[TRWAGMYFPDXBNJZSQVHLCKE]$"
        if not re.match(nif_pattern, clean):
            raise ValueError(f"NIF/NIE con formato o letra de control inválida: {v}")
        return clean

    @field_validator("naf", mode="before")
    @classmethod
    def resolve_and_clean_naf(cls, v: Any) -> str:
        clean = re.sub(r"[\s\/\-\.]", "", str(v))
        if not re.match(r"^\d{12}$", clean):
            raise ValueError(f"El NAF/NSS debe contener exactamente 12 dígitos numéricos: {v}")
        return clean

    @property
    def nss(self) -> str:
        """Alias de compatibilidad hacia atrás para código legacy que accede a employee.nss"""
        return self.naf

class IrpfCalculationDTO(BaseModel):
    annual_gross: Decimal
    deductible_ss_worker_annual: Decimal
    general_deductible_expenses: Decimal = Decimal("2000.00")
    article_20_reduction: Decimal = Decimal("0.00")
    tax_base_irpf: Decimal
    personal_family_minimum: Decimal
    quota_tax_base: Decimal
    quota_minimum: Decimal
    prior_quota: Decimal
    is_exempt_art_81: bool
    final_irpf_rate: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("47.00"))
    monthly_retention_amount: Decimal

class PayrollDeductionsWorkerDTO(BaseModel):
    common_contingencies: Decimal
    unemployment: Decimal
    professional_training: Decimal
    mei: Decimal
    total_ss_worker: Decimal

class PayrollEmployerCostsDTO(BaseModel):
    common_contingencies: Decimal
    unemployment: Decimal
    fogasa: Decimal
    professional_training: Decimal
    mei: Decimal
    atep: Decimal
    total_ss_employer: Decimal

class MonthlyPayrollCalculationDTO(BaseModel):
    employee_id: int
    employee_name: str
    employee_nif: str
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)
    salary_base: Decimal
    extra_pay_prorata: Decimal = Decimal("0.00")
    gross_total: Decimal
    bccc: Decimal
    bccp: Decimal
    worker_deductions: PayrollDeductionsWorkerDTO
    employer_costs: PayrollEmployerCostsDTO
    irpf_rate: Decimal
    irpf_retention: Decimal
    net_salary: Decimal
    total_cost_to_company: Decimal

class TgssAfiAction(str, Enum):
    MA = "MA"  # Alta de trabajador
    MB = "MB"  # Baja de trabajador
    MC = "MC"  # Modificación de contrato/jornada

class TgssTerminationCause(str, Enum):
    OBJECTIVE = "51"      # Despido por causas objetivas / procedente
    VOLUNTARY = "53"      # Dimisión / baja voluntaria
    DISCIPLINARY = "54"   # Despido disciplinario procedente
    END_CONTRACT = "93"   # Fin de contrato temporal

class TgssAfiRecordDTO(BaseModel):
    action: TgssAfiAction
    regimen: str = "0111"
    ccc: str = Field(..., pattern=r"^\d{11}$")
    naf: str = Field(..., pattern=r"^\d{12}$")
    nif: str
    real_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    contract_code: Optional[str] = "100"
    contribution_group: Optional[int] = Field(default=1, ge=1, le=11)
    coefficient: Optional[str] = "1000"
    cause_code: Optional[TgssTerminationCause] = None
    vacation_days_l13: Optional[int] = 0
    formatted_payload: str

class CraConceptType(str, Enum):
    COMPUTABLE = "C"  # Concepto computable en base de cotización
    EXCLUDED = "E"    # Concepto excluido de cotización

class TgssCraConceptDTO(BaseModel):
    code: str = Field(..., pattern=r"^\d{4}$", description="Código concepto TGSS (ej. 0001 Salario Base, 0005 Extra)")
    description: str
    amount: Decimal
    concept_type: CraConceptType

class TgssCraWorkerDTO(BaseModel):
    naf: str = Field(..., pattern=r"^\d{12}$")
    nif: str
    concepts: List[TgssCraConceptDTO]

class TgssCraMessageDTO(BaseModel):
    regimen: str = "0111"
    province: str = Field(..., pattern=r"^\d{2}$")
    number: str = Field(..., pattern=r"^\d{7}$")
    control_digit: str = Field(..., pattern=r"^\d{2}$")
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)
    workers: List[TgssCraWorkerDTO]

class JournalEntryLineDTO(BaseModel):
    account_code: str
    concept: str
    debe: Decimal = Decimal("0.00")
    haber: Decimal = Decimal("0.00")

class PayrollJournalEntryDTO(BaseModel):
    date: str
    concept: str
    lines: List[JournalEntryLineDTO]

    def validate_double_entry(self) -> bool:
        total_debe = sum(line.debe for line in self.lines).quantize(Decimal("0.01"))
        total_haber = sum(line.haber for line in self.lines).quantize(Decimal("0.01"))
        if total_debe != total_haber:
            raise ValueError(f"Asiento de nómina descuadrado: Debe ({total_debe}) != Haber ({total_haber})")
        return True

class SettlementJournalEntryDTO(BaseModel):
    date: str
    concept: str
    lines: List[JournalEntryLineDTO]

    def validate_double_entry(self) -> bool:
        total_debe = sum(line.debe for line in self.lines).quantize(Decimal("0.01"))
        total_haber = sum(line.haber for line in self.lines).quantize(Decimal("0.01"))
        if total_debe != total_haber:
            raise ValueError(f"Asiento de finiquito descuadrado (Partida Doble rota): Debe ({total_debe}) != Haber ({total_haber})")
        return True


class IntentType(str, Enum):
    message = 'message'
    tool_call = 'tool_call'
    clarification = 'clarification'
    confirmation_required = 'confirmation_required'
    error = 'error'

class LLMDecisionEnvelope(BaseModel):
    type: IntentType
    message: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    domain: Optional[str] = Field("general", description="Dominio inferido (accounting, legal, general)")

class ToolExecutionResult(BaseModel):
    status: Literal["ok", "error", "cancelled", "rbac_error", "tier_upgrade_required", "missing_error", "validation_error", "execution_error"] = Field(
        ..., description="Estado de finalización de la ejecución"
    )
    execution: Literal["server", "client"] = Field(..., description="Entorno de ejecución (servidor FastAPI o agente de escritorio)")
    result: Optional[Any] = Field(None, description="Carga útil resultante de la ejecución exitosa")
    message: Optional[str] = Field(None, description="Mensaje explicativo para el usuario o logs")
    tool_name: Optional[str] = Field(None, description="Nombre de la herramienta ejecutada")

class ProtocolError(Exception):
    def __init__(self, message: str, raw_output: str):
        self.message = message
        self.raw_output = raw_output
        super().__init__(self.message)

class DomainErrorContract(BaseModel):
    status: Literal["needs_user_validation", "fatal_error", "system_error"] = Field(..., description="Estado del error")
    affected_fields: list[str] = Field(default_factory=list, description="Lista de campos que fallaron validación")
    extracted_values: Dict[str, Any] = Field(default_factory=dict, description="Valores extraídos exitosamente")
    missing_values: Dict[str, Any] = Field(default_factory=dict, description="Valores faltantes o inválidos")
    reason_code: str = Field(..., description="Código de error estandarizado")
    technical_details: Optional[str] = Field(None, description="Stack trace interno. NO ENVIAR AL LLM.")

# =====================================================================
# ESQUEMAS DE PRIVACIDAD Y ANONIMIZACIÓN PRE-GEMINI (GDPR / LOPDGDD)
# =====================================================================
from datetime import datetime, timezone
import uuid

EntityType = Literal[
    "NIF",
    "NIE",
    "CIF",
    "IBAN",
    "IMPORTE",
    "NOMBRE",
    "EMAIL",
    "TELEFONO",
    "DIRECCION",
    "CODIGO_POSTAL"
]

ENTITY_TOKEN_PREFIX: Dict[str, str] = {
    "NIF": "NIF",
    "NIE": "NIF",
    "CIF": "NIF",
    "IBAN": "IBAN",
    "IMPORTE": "IMPORTE",
    "NOMBRE": "NOMBRE",
    "EMAIL": "EMAIL",
    "TELEFONO": "TELEFONO",
    "DIRECCION": "DIRECCION",
    "CODIGO_POSTAL": "CP"
}

class AnonymizedEntity(BaseModel):
    token: str = Field(..., description="Token sintético generado determinista, ej: [NIF_1], [IMPORTE_1]")
    original_value: str = Field(..., description="Valor original sensible disociado")
    normalized_value: str = Field(..., description="Valor normalizado para deduplicación y mapeo")
    entity_type: EntityType = Field(..., description="Tipo legal de entidad sensible detectada")
    start_pos: int = Field(..., description="Índice de posición inicial en el texto original")
    end_pos: int = Field(..., description="Índice de posición final en el texto original")

class AnonymizationSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único de la sesión de inferencia")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de inicio de la sesión")
    entities: list[AnonymizedEntity] = Field(default_factory=list, description="Lista de entidades identificadas")
    token_to_value_map: Dict[str, str] = Field(default_factory=dict, description="Diccionario para desanonimización inversa")
    value_to_token_map: Dict[str, str] = Field(default_factory=dict, description="Diccionario para reutilización de tokens idénticos")
    entity_counters: Dict[str, int] = Field(default_factory=dict, description="Contadores secuenciales por tipo de entidad")

    def register_entity(
        self,
        original_value: str,
        entity_type: EntityType,
        start_pos: int,
        end_pos: int
    ) -> str:
        normalized = original_value.strip().lower()
        if normalized in self.value_to_token_map:
            token = self.value_to_token_map[normalized]
        else:
            prefix = ENTITY_TOKEN_PREFIX.get(entity_type, entity_type)
            current_count = self.entity_counters.get(prefix, 0) + 1
            self.entity_counters[prefix] = current_count
            token = f"[{prefix}_{current_count}]"
            self.value_to_token_map[normalized] = token
            self.token_to_value_map[token] = original_value.strip()

        entity = AnonymizedEntity(
            token=token,
            original_value=original_value,
            normalized_value=normalized,
            entity_type=entity_type,
            start_pos=start_pos,
            end_pos=end_pos
        )
        self.entities.append(entity)
        return token

    def purge(self) -> None:
        self.token_to_value_map.clear()
        self.value_to_token_map.clear()
        self.entities.clear()
        self.entity_counters.clear()

class StreamingTokenBuffer(BaseModel):
    max_token_len: int = Field(default=30, description="Longitud máxima esperada para un token sintético")
    buffer: str = Field(default="", description="Fragmentos acumulados pendientes de evaluación")
    in_token: bool = Field(default=False, description="Indica si se ha detectado '[' sin haber llegado a ']'")

    def feed(self, chunk: str, token_map: Dict[str, str]) -> str:
        self.buffer += chunk
        output = []

        while self.buffer:
            if not self.in_token:
                bracket_pos = self.buffer.find("[")
                if bracket_pos == -1:
                    output.append(self.buffer)
                    self.buffer = ""
                    break
                else:
                    output.append(self.buffer[:bracket_pos])
                    self.buffer = self.buffer[bracket_pos:]
                    self.in_token = True

            close_pos = self.buffer.find("]")
            if close_pos != -1:
                candidate_token = self.buffer[:close_pos + 1]
                resolved = token_map.get(candidate_token, candidate_token)
                output.append(resolved)
                self.buffer = self.buffer[close_pos + 1:]
                self.in_token = False
            else:
                if len(self.buffer) > self.max_token_len:
                    output.append(self.buffer[0])
                    self.buffer = self.buffer[1:]
                    self.in_token = False
                else:
                    break

        return "".join(output)

    def flush(self, token_map: Dict[str, str]) -> str:
        if not self.buffer:
            return ""
        candidate = self.buffer
        resolved = token_map.get(candidate, candidate)
        self.buffer = ""
        self.in_token = False
        return resolved

class AnonymizationResult(BaseModel):
    anonymized_text: str = Field(..., description="Texto seguro con tokens sintéticos para enviar al LLM")
    session: AnonymizationSession = Field(..., description="Sesión activa con el mapa de correspondencia")
    entities_count: int = Field(..., description="Número total de entidades anonimizadas")

class DetokenizationResult(BaseModel):
    restored_text: str = Field(..., description="Texto reconstruido con los datos reales para el usuario")
    unresolved_tokens: list[str] = Field(default_factory=list, description="Tokens no resueltos por el mapa")


# ==============================================================================
# ESTADOS FINANCIEROS OFICIALES, AMORTIZACIONES Y CIERRE CONTABLE (PGC PYMES)
# ==============================================================================

class FinancialStatementType(str, Enum):
    BALANCE_SHEET = "BALANCE_SHEET"
    INCOME_STATEMENT = "INCOME_STATEMENT"
    MEMORIA = "MEMORIA"


class DepreciationMethod(str, Enum):
    LINEAR = "LINEAR"
    DEGRESSIVE_DIGITS = "DEGRESSIVE_DIGITS"
    PERCENT_ON_DECLINING = "DECLINING_BALANCE"


class AssetStatus(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    FULLY_DEPRECIATED = "FULLY_DEPRECIATED"
    RETIRED = "RETIRED"


class FiscalYearStatusEnum(str, Enum):
    OPEN = "OPEN"
    PRE_CLOSING = "PRE_CLOSING"
    CLOSED = "CLOSED"


class FinancialStatementLineDTO(BaseModel):
    """Línea o epígrafe individual en el modelo normalizado del PGC PYMES."""
    epigrafe_codigo: str = Field(..., description="Código oficial del epígrafe (ej. 'A.II.1', 'B.II', '1.a')")
    epigrafe_nombre: str = Field(..., description="Denominación reglamentaria según el RD 1515/2007")
    cuentas_asociadas: List[str] = Field(default_factory=list, description="Códigos de cuentas PGC agregadas")
    saldo_ejercicio_actual: Decimal = Field(..., description="Saldo del ejercicio evaluado expresado en Decimal")
    saldo_ejercicio_anterior: Decimal = Field(default=Decimal("0.00"), description="Saldo comparativo del ejercicio N-1")

    @field_validator("saldo_ejercicio_actual", "saldo_ejercicio_anterior", mode="before")
    @classmethod
    def ensure_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class BalanceSheetDTO(BaseModel):
    """Balance de Situación normalizado para el depósito de cuentas en el Registro Mercantil."""
    tenant_id: str
    fiscal_year: int
    fecha_cierre: str = Field(..., description="Fecha de emisión o cierre contable (YYYY-MM-DD)")
    activo_no_corriente: List[FinancialStatementLineDTO] = Field(default_factory=list)
    activo_corriente: List[FinancialStatementLineDTO] = Field(default_factory=list)
    total_activo: Decimal = Field(..., description="Suma total de Activo No Corriente + Activo Corriente")
    patrimonio_neto: List[FinancialStatementLineDTO] = Field(default_factory=list)
    pasivo_no_corriente: List[FinancialStatementLineDTO] = Field(default_factory=list)
    pasivo_corriente: List[FinancialStatementLineDTO] = Field(default_factory=list)
    total_pasivo_y_patrimonio_neto: Decimal = Field(..., description="Suma total de PN + Pasivo NC + Pasivo C")
    is_balanced: bool = Field(..., description="Garantiza que abs(Total Activo - Total Pasivo y PN) == Decimal(\"0.00\")")
    descuadre_forense: Optional[Dict[str, Decimal]] = Field(
        default=None, 
        description="Si is_balanced es False, detalle de cuentas causantes de la discordancia"
    )

    @field_validator("total_activo", "total_pasivo_y_patrimonio_neto", mode="before")
    @classmethod
    def ensure_totals_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class IncomeStatementDTO(BaseModel):
    """Cuenta de Pérdidas y Ganancias (PyG) escalonada según el PGC PYMES."""
    tenant_id: str
    fiscal_year: int
    fecha_desde: str
    fecha_hasta: str
    cifra_negocios: Decimal = Decimal("0.00")
    variacion_existencias: Decimal = Decimal("0.00")
    aprovisionamientos: Decimal = Decimal("0.00")
    gastos_personal: Decimal = Decimal("0.00")
    otros_gastos_explotacion: Decimal = Decimal("0.00")
    amortizaciones_dotacion: Decimal = Decimal("0.00")
    otros_ingresos_explotacion: Decimal = Decimal("0.00")
    margen_bruto: Decimal = Decimal("0.00")
    ebitda: Decimal = Decimal("0.00")
    resultado_explotacion: Decimal = Field(..., description="EBIT / Resultado Operativo")
    ingresos_financieros: Decimal = Decimal("0.00")
    gastos_financieros: Decimal = Decimal("0.00")
    resultado_financiero: Decimal = Field(..., description="Diferencia de ingresos y gastos financieros")
    resultado_antes_impuestos: Decimal = Field(..., description="Resultado de explotación + financiero")
    impuesto_sociedades: Decimal = Field(..., description="Gasto por Impuesto sobre Sociedades (Cuenta 630)")
    resultado_neto_ejercicio: Decimal = Field(..., description="Beneficio o Pérdida final (Cuenta 129)")
    lineas_epigrafes: List[FinancialStatementLineDTO] = Field(default_factory=list)

    @field_validator(
        "cifra_negocios", "variacion_existencias", "aprovisionamientos", "gastos_personal",
        "otros_gastos_explotacion", "amortizaciones_dotacion", "otros_ingresos_explotacion",
        "margen_bruto", "ebitda", "resultado_explotacion", "ingresos_financieros",
        "gastos_financieros", "resultado_financiero", "resultado_antes_impuestos",
        "impuesto_sociedades", "resultado_neto_ejercicio", mode="before"
    )
    @classmethod
    def ensure_decimal_fields(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class AssetRecordDTO(BaseModel):
    """Ficha contable y técnica de un bien de inmovilizado afecto a la actividad."""
    id: str
    tenant_id: str
    code: str
    name: str
    account_asset: str = Field(default="21700000", description="Cuenta de inmovilizado")
    account_amort_accum: str = Field(default="28100000", description="Cuenta de amortización acumulada")
    account_amort_expense: str = Field(default="68100000", description="Cuenta de gasto por dotación a la amortización")
    acquisition_date: date
    acquisition_cost: Decimal
    salvage_value: Decimal = Field(default=Decimal("0.00"), description="Valor residual")
    useful_life_years: int = Field(..., ge=1)
    depreciation_rate: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"))
    method: DepreciationMethod = DepreciationMethod.LINEAR
    accumulated_depreciation: Decimal = Decimal("0.00")
    net_book_value: Decimal
    status: AssetStatus = AssetStatus.ACTIVE

    @field_validator("acquisition_cost", "salvage_value", "depreciation_rate", "accumulated_depreciation", "net_book_value", mode="before")
    @classmethod
    def ensure_asset_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class SimulatedJournalLineDTO(BaseModel):
    account_code: str
    concept: Optional[str] = None
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def ensure_decimal(cls, v):
        return Decimal(str(v or "0.00")).quantize(Decimal("0.01"))


class SimulatedJournalEntryDTO(BaseModel):
    entry_number: Optional[int] = None
    entry_date: str
    concept: str
    lines: List[SimulatedJournalLineDTO] = Field(default_factory=list)


class DepreciationQuotaDTO(BaseModel):
    """Cálculo individual de amortización para un período concreto."""
    asset_id: str
    asset_name: str
    account_debe: str = "68100000"
    account_haber: str = "28100000"
    quota_amount: Decimal
    period: str = Field(..., description="'YYYY-MM' para mensual o 'YYYY' para anual")
    is_prorated: bool = False
    concept: str

    @property
    def depreciation_quota(self) -> Decimal:
        return self.quota_amount

    @property
    def account_debit(self) -> str:
        return self.account_debe

    @property
    def account_credit(self) -> str:
        return self.account_haber

    @field_validator("quota_amount", mode="before")
    @classmethod
    def ensure_quota_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class DepreciationRunResultDTO(BaseModel):
    """Resultado del proceso por lotes de contabilización de amortizaciones."""
    status: str
    tenant_id: str
    fiscal_year: int
    period: str
    total_assets_processed: int
    total_amount_amortized: Decimal
    journal_entry_id: Optional[str] = None
    quotas: List[DepreciationQuotaDTO] = Field(default_factory=list)
    message: Optional[str] = None
    is_posted: bool = True

    @property
    def total_depreciation_amount(self) -> Decimal:
        return self.total_amount_amortized

    @field_validator("total_amount_amortized", mode="before")
    @classmethod
    def ensure_total_amort_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class YearEndClosingSimulationDTO(BaseModel):
    """Propuesta de cierre contable y saldado de cuentas antes de su ejecución definitiva."""
    tenant_id: str
    fiscal_year: int
    resultado_antes_impuestos: Decimal
    tipo_is_aplicado: Decimal
    cuota_is_estimada: Decimal
    resultado_neto: Decimal
    apuntes_regularizacion_cuentas_6_y_7: List[Dict[str, Any]] = Field(default_factory=list)
    apuntes_cierre_cuentas_balance: List[Dict[str, Any]] = Field(default_factory=list)
    apuntes_apertura_ejercicio_siguiente: List[Dict[str, Any]] = Field(default_factory=list)
    asiento_regularizacion: Optional[SimulatedJournalEntryDTO] = None
    asiento_cierre: Optional[SimulatedJournalEntryDTO] = None
    asiento_apertura_siguiente: Optional[SimulatedJournalEntryDTO] = None
    warnings: List[str] = Field(default_factory=list)

    @property
    def impuesto_sociedades_estimado(self) -> Decimal:
        return self.cuota_is_estimada

    @property
    def resultado_neto_ejercicio(self) -> Decimal:
        return self.resultado_neto


class CloseFiscalYearExecutionCommand(BaseModel):
    tenant_id: str
    fiscal_year: int
    confirmed_by_user: bool = Field(..., description="Requisito HITL explícito para autorizar el cierre")
    closed_by: str = "user"
    corporate_tax_rate: float = 0.25


class CloseFiscalYearExecutionResultDTO(BaseModel):
    status: str
    tenant_id: str
    fiscal_year: int
    next_fiscal_year: int
    resultado_ejercicio: Decimal
    asiento_regularizacion_id: str
    asiento_cierre_id: str
    asiento_apertura_id: str
    closed_at: datetime
    is_locked: bool
    message: str
    is_success: bool = True
    is_closed: bool = True
    entries_created: int = 3

    @field_validator("resultado_ejercicio", mode="before")
    @classmethod
    def ensure_result_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


# ============================================================================
# MÓDULO 8: INTELIGENCIA DE MERCADO, ANÁLISIS COMPETITIVO Y DAFO (SPEC 032)
# ============================================================================

class SectorBenchmarkDTO(BaseModel):
    """Comparativa cuantitativa de precios y posicionamiento de mercado."""
    cnae_code: str = Field(..., min_length=2, max_length=5, description="Código de actividad CNAE-2009 (ej. '6201')")
    sector_name: str = Field(..., min_length=1, description="Denominación oficial del sector de actividad")
    region: str = Field(..., min_length=1, description="Comunidad Autónoma o provincia de referencia")
    average_market_price: Decimal = Field(..., ge=Decimal("0.00"), description="Precio medio de mercado sectorial en euros")
    user_average_price: Decimal = Field(..., ge=Decimal("0.00"), description="Precio medio facturado por el usuario en euros")
    price_position_percentile: int = Field(..., ge=0, le=100, description="Posición relativa en percentil (0 a 100)")
    positioning_segment: str = Field(..., description="Segmento de mercado: 'Económico', 'Medio', 'Premium'")
    potential_revenue_upside: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), description="Incremento potencial de facturación al equiparar precios a la media")
    recommendation: str = Field(..., description="Recomendación táctica de fijación de precios y márgenes")

    @field_validator("average_market_price", "user_average_price", "potential_revenue_upside", mode="before")
    @classmethod
    def quantize_benchmark_decimals(cls, v):
        return Decimal(str(v or "0.00")).quantize(Decimal("0.01"))


class TopClientConcentrationItemDTO(BaseModel):
    """Desglose de concentración de facturación por cliente anonimizado."""
    client_label: str = Field(..., description="Etiqueta anónima del cliente (ej. 'Cliente Principal 1')")
    annual_turnover: Decimal = Field(..., ge=Decimal("0.00"), description="Importe neto facturado en el ejercicio")
    concentration_percentage: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"), description="Porcentaje sobre la facturación neta total")

    @field_validator("annual_turnover", "concentration_percentage", mode="before")
    @classmethod
    def quantize_client_decimals(cls, v):
        return Decimal(str(v or "0.00")).quantize(Decimal("0.01"))


class TopSupplierRiskItemDTO(BaseModel):
    """Desglose de riesgo y variación de costes en proveedores clave."""
    supplier_label: str = Field(..., description="Etiqueta anónima del proveedor (ej. 'Proveedor Clave A')")
    current_year_cost: Decimal = Field(..., ge=Decimal("0.00"), description="Gasto acumulado en el año N")
    previous_year_cost: Decimal = Field(..., ge=Decimal("0.00"), description="Gasto acumulado en el año N-1")
    cost_increase_rate: Decimal = Field(..., description="Porcentaje de variación del coste")
    exceeds_sector_inflation: bool = Field(..., description="Indica si el incremento supera la inflación sectorial")

    @field_validator("current_year_cost", "previous_year_cost", "cost_increase_rate", mode="before")
    @classmethod
    def quantize_supplier_decimals(cls, v):
        return Decimal(str(v or "0.00")).quantize(Decimal("0.01"))


class BusinessRiskAuditDTO(BaseModel):
    """Auditoría de riesgos de concentración, costes y solvencia de tesorería."""
    client_concentration_ratio: Decimal = Field(..., description="Porcentaje de facturación concentrado en el top 3 de clientes")
    top_single_client_ratio: Decimal = Field(..., description="Porcentaje de facturación del cliente mayoritario")
    high_concentration_alert: bool = Field(..., description="True si un único cliente supera el 40% o top 3 supera el 70%")
    top_clients: List[TopClientConcentrationItemDTO] = Field(default_factory=list, description="Desglose del top de clientes")
    supplier_cost_increase_rate: Decimal = Field(..., description="Tasa media de incremento de costes en proveedores clave")
    top_risk_suppliers: List[TopSupplierRiskItemDTO] = Field(default_factory=list, description="Proveedores con incrementos de costes anómalos")
    runway_months: Decimal = Field(..., description="Meses de supervivencia con la tesorería actual redondeado a 1 decimal")
    monthly_burn_rate: Decimal = Field(..., ge=Decimal("0.00"), description="Gasto operativo fijo mensual medio")
    available_liquidity: Decimal = Field(..., ge=Decimal("0.00"), description="Tesorería líquida total disponible")

    @field_validator("client_concentration_ratio", "top_single_client_ratio", "supplier_cost_increase_rate", "monthly_burn_rate", "available_liquidity", mode="before")
    @classmethod
    def quantize_risk_decimals(cls, v):
        return Decimal(str(v or "0.00")).quantize(Decimal("0.01"))

    @field_validator("runway_months", mode="before")
    @classmethod
    def quantize_runway_decimal(cls, v):
        return Decimal(str(v or "0.0")).quantize(Decimal("0.1"))


class DAFOAnalysisReportDTO(BaseModel):
    """Informe de diagnóstico estratégico DAFO estructurado validado con LLM."""
    cnae_code: str = Field(..., description="Código CNAE de la actividad evaluada")
    evaluation_date: str = Field(..., description="Fecha de emisión del informe (ISO 8601 YYYY-MM-DD)")
    fortalezas: List[str] = Field(..., min_length=2, description="Puntos fuertes internos cuantitativos y operativos")
    debilidades: List[str] = Field(..., min_length=2, description="Vulnerabilidades internas (liquidez, concentración, márgenes)")
    oportunidades: List[str] = Field(..., min_length=2, description="Oportunidades de mercado detectadas en la prospección externa")
    amenazas: List[str] = Field(..., min_length=2, description="Riesgos externos de mercado, inflación de proveedores o sector")
    acciones_recomendadas: List[str] = Field(..., min_length=3, description="Propuestas tácticas concretas con metas numéricas")
    synthetic_prompt_tokens: Optional[int] = Field(default=None, description="Métricas de ejecución pre-LLM anonimizado")


class StrategicAnalysisContextDTO(BaseModel):
    """Payload de contexto anonimizado para alimentar el asistente LLM (cumplimiento RGPD)."""
    cnae: str
    sector: str
    region: str
    gross_margin_pct: Decimal
    ebitda_margin_pct: Decimal
    debt_ratio_pct: Optional[Decimal] = Field(default=None, description="Ratio de endeudamiento patrimonial (Pasivo Total / Activo Total)")
    seasonality_pattern: Optional[str] = Field(default=None, description="Patrón de estacionalidad detectado en la facturación trimestral")
    average_collection_days: int
    user_price_percentile: int
    potential_upside_eur: Decimal
    client_concentration_c3_pct: Decimal
    max_client_c1_pct: Decimal
    high_concentration_alert: bool
    supplier_increase_pct: Decimal
    sector_inflation_pct: Decimal
    runway_months: Decimal = Field(..., description="Meses de supervivencia con la tesorería actual redondeado a 1 decimal")
    available_liquidity_eur: Decimal

    @field_validator("gross_margin_pct", "ebitda_margin_pct", "potential_upside_eur", "client_concentration_c3_pct", "max_client_c1_pct", "supplier_increase_pct", "sector_inflation_pct", "available_liquidity_eur", mode="before")
    @classmethod
    def quantize_context_decimals(cls, v):
        return Decimal(str(v or "0.00")).quantize(Decimal("0.01"))

    @field_validator("debt_ratio_pct", mode="before")
    @classmethod
    def quantize_debt_ratio(cls, v):
        if v is None:
            return None
        return Decimal(str(v)).quantize(Decimal("0.01"))

    @field_validator("runway_months", mode="before")
    @classmethod
    def quantize_context_runway(cls, v):
        return Decimal(str(v or "0.0")).quantize(Decimal("0.1"))


# ==============================================================================
# INGESTA AUTOMÁTICA DE FACTURAS DESDE EMAIL, OCR Y CONTABILIZACIÓN PGC (033)
# ==============================================================================

class InvoiceProcessingStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    PARSE_ERROR = "PARSE_ERROR"


class InvoiceTaxBreakdownDTO(BaseModel):
    """Desglose de impuestos por tipo impositivo según RD 1619/2012."""
    tax_rate: Decimal = Field(..., description="Tipo impositivo (ej. 4.00, 10.00, 21.00)")
    tax_base: Decimal = Field(..., description="Base imponible sujeta")
    tax_amount: Decimal = Field(..., description="Cuota tributaria de IVA")

    @field_validator("tax_rate", "tax_base", "tax_amount", mode="before")
    @classmethod
    def coerce_tax_decimals(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class ExtractedInvoiceMetadataDTO(BaseModel):
    """Metadatos de factura extraídos deterministamente del documento adjunto."""
    sender_nif: str = Field(..., pattern=r"^[0-9A-Z][0-9]{7}[0-9A-Z]$", description="NIF/CIF del emisor")
    sender_name: str = Field(..., min_length=1, description="Razón social o nombre comercial del emisor")
    invoice_number: str = Field(..., min_length=1, description="Serie y número de factura")
    issue_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha de emisión ISO")
    taxes: List[InvoiceTaxBreakdownDTO] = Field(default_factory=list, description="Desglose de bases y cuotas de IVA")
    irpf_retention_rate: Decimal = Field(default=Decimal("0.00"), description="Tipo de retención de IRPF (ej. 15.00)")
    irpf_retention_amount: Decimal = Field(default=Decimal("0.00"), description="Importe retenido de IRPF")
    total_amount: Decimal = Field(..., description="Importe total neto a pagar de la factura")
    suggested_pgc_account: str = Field(default="6280001", description="Cuenta PGC de gasto sugerida")
    suggested_pgc_account_name: str = Field(default="Suministros", description="Nombre descriptivo de la cuenta PGC")
    source_email_id: str = Field(..., description="Identificador único del correo de origen")
    attached_pdf_path: str = Field(..., description="Ruta local del documento archivado")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Índice de confianza de la extracción")

    @field_validator("irpf_retention_rate", "irpf_retention_amount", "total_amount", mode="before")
    @classmethod
    def coerce_amounts_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class ProposedJournalLineDTO(BaseModel):
    """Línea propuesta de asiento contable para revisión humana."""
    account_code: str = Field(..., description="Código de cuenta contable PGC")
    account_name: str = Field(..., description="Descripción de la cuenta PGC")
    debit: Decimal = Field(default=Decimal("0.00"), description="Importe al Debe")
    credit: Decimal = Field(default=Decimal("0.00"), description="Importe al Haber")

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def coerce_line_decimals(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))


class InvoiceApprovalProposalDTO(BaseModel):
    """Propuesta de factura y asiento contable presentada en la interfaz para validación humana."""
    proposal_id: str = Field(..., description="Identificador único UUID de la propuesta")
    status: InvoiceProcessingStatus = Field(default=InvoiceProcessingStatus.PENDING_APPROVAL)
    metadata: ExtractedInvoiceMetadataDTO
    proposed_entry_lines: List[ProposedJournalLineDTO] = Field(default_factory=list)
    created_at: str
    duplicate_warning: Optional[str] = None
    journal_entry_id: Optional[str] = None


class ApproveInvoiceProposalCommand(BaseModel):
    """Comando emitido por la interfaz al pulsar [Aprobar y Contabilizar]."""
    proposal_id: str
    tenant_id: str = "default_tenant"
    confirmed_pgc_account: Optional[str] = None
    custom_concept: Optional[str] = None
    target_partner_account: Optional[str] = None


class EmailAccountConfigDTO(BaseModel):
    """
    Parámetros de configuración del servidor de correo entrante (IMAP/TLS).
    Soporta contraseñas directas o contraseñas de aplicación (App Passwords) de Google y Microsoft.
    """
    imap_host: str = Field(..., description="Servidor IMAP (ej. imap.gmail.com, outlook.office365.com)")
    imap_port: int = Field(default=993, description="Puerto IMAP SSL/TLS (por defecto 993)")
    imap_user: str = Field(..., description="Dirección de correo electrónico / usuario")
    imap_password: str = Field(..., description="Contraseña o contraseña de aplicación (App Password)")
    use_ssl: bool = Field(default=True)
    mailbox_folder: str = Field(default="INBOX")


class InboxStatusDTO(BaseModel):
    """Estado del buzón de correo para la interfaz gráfica."""
    is_connected: bool
    status_label: str  # "Conectado" o "Desconectado: configure su cuenta de correo"
    account_email: Optional[str] = None
    unread_emails_count: int = 0
    pending_proposals_count: int = 0
    last_sync_at: Optional[str] = None


class EmailSyncResultDTO(BaseModel):
    """Resultado del proceso de sincronización desatendida."""
    status: str  # "ok" o "error"
    emails_processed: int
    attachments_downloaded: int
    invoices_extracted: int
    proposals_created: int
    duplicates_detected: int
    error_message: Optional[str] = None


class InvoiceApprovalResultDTO(BaseModel):
    """Resultado de la aprobación o rechazo de una propuesta de factura recibida."""
    proposal_id: str
    invoice_id: Optional[str] = None
    journal_entry_id: Optional[str] = None
    status: InvoiceProcessingStatus
    invoice_status: Optional[str] = None
    message: str
    is_success: bool = True




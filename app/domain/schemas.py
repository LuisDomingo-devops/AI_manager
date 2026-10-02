import re
from typing import Optional, Literal, Dict, Any
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
from enum import Enum
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


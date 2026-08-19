import re
from typing import Optional, Literal
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

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        # Validar formato de fecha YYYY-MM-DD
        pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(pattern, v):
            raise ValueError("La fecha debe tener el formato YYYY-MM-DD")
        return v

    @field_validator("issuer_nif", "receiver_nif")
    @classmethod
    def validate_nifs(cls, v: str) -> str:
        v = v.strip().upper()
        pattern = r"^[A-Z0-9][0-9]{7,8}[A-Z0-9]$"
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

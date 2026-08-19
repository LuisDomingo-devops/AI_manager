"""
PAYROLL SCHEMAS — Modelos de datos Pydantic para el módulo laboral de Alfonso.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


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
    def validate_nif(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) < 8:
            raise ValueError("El NIF/NIE no es válido.")
        return v

    @field_validator("start_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
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

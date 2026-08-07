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

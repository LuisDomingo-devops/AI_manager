"""
Motor de Validación Fiscal Determinista para Alfonso Autónomo.
Garantiza el cumplimiento estricto de la normativa fiscal española (RD 1619/2012, LGT y Veri*Factu RD 1007/2023)
antes de que los datos interpretados por la IA puedan ser firmados o registrados en la cadena criptográfica.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from pydantic import BaseModel, Field

# Tipos impositivos de IVA legalmente vigentes en España (Régimen General y Reducidos)
VALID_IVA_RATES = {0.0, 2.0, 4.0, 5.0, 7.5, 10.0, 21.0}

# Tipos de Retención de IRPF habituales para profesionales autónomos
VALID_IRPF_RATES = {0.0, 1.0, 2.0, 7.0, 15.0, 19.0}

# Tipos de Factura según Veri*Factu / Reglamento de Facturación
VALID_INVOICE_TYPES = {
    "F1",  # Factura ordinaria
    "F2",  # Factura simplificada
    "F3",  # Factura emitida en sustitución de facturas simplificadas
    "R1",  # Rectificativa por error fundado en derecho y art. 80 Uno, Dos y Seis LIVA
    "R2",  # Rectificativa por concurso de acreedores
    "R3",  # Rectificativa por crédito incobrable
    "R4",  # Rectificativa resto de causas
    "R5"   # Rectificativa en facturas simplificadas
}


class FiscalValidationResult(BaseModel):
    is_valid: bool
    requires_human_review: bool = False
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    sanitized_data: Optional[Dict[str, Any]] = None


def validate_spanish_id(nif_nie_cif: str) -> Tuple[bool, str]:
    """
    Valida un NIF, NIE o CIF español mediante sus algoritmos de dígito de control oficiales.
    Retorna (es_valido, tipo_documento_o_error).
    """
    if not nif_nie_cif or not isinstance(nif_nie_cif, str):
        return False, "Identificador vacío o inválido"
    
    val = nif_nie_cif.strip().upper().replace("-", "").replace(" ", "")
    if len(val) != 9:
        return False, f"Longitud incorrecta ({len(val)} caracteres, deben ser 9)"

    letras_nif = "TRWAGMYFPDXBNJZSQVHLCKE"

    # 1. Validación de DNI / NIF estándar (8 números + 1 letra)
    if re.match(r"^\d{8}[A-Z]$", val):
        numero = int(val[:8])
        letra_esperada = letras_nif[numero % 23]
        if val[8] == letra_esperada:
            return True, "NIF_PERSONA_FISICA"
        return False, f"Letra de NIF incorrecta (esperada {letra_esperada}, recibida {val[8]})"

    # 2. Validación de NIE (X, Y, Z + 7 números + 1 letra)
    if re.match(r"^[XYZ]\d{7}[A-Z]$", val):
        letra_inicial = val[0]
        prefijo = {"X": "0", "Y": "1", "Z": "2"}[letra_inicial]
        numero = int(prefijo + val[1:8])
        letra_esperada = letras_nif[numero % 23]
        if val[8] == letra_esperada:
            return True, "NIE"
        return False, f"Letra de NIE incorrecta (esperada {letra_esperada}, recibida {val[8]})"

    # 3. Validación de CIF (Entidades jurídicas)
    # Formato: 1 letra + 7 números + 1 carácter de control (número o letra)
    if re.match(r"^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$", val):
        tipo_cif = val[0]
        cuerpo = val[1:8]
        control = val[8]

        suma_pares = sum(int(cuerpo[i]) for i in (1, 3, 5))
        suma_impares = 0
        for i in (0, 2, 4, 6):
            doble = int(cuerpo[i]) * 2
            suma_impares += (doble // 10) + (doble % 10)

        suma_total = suma_pares + suma_impares
        digito_control = (10 - (suma_total % 10)) % 10
        letra_control = "JABCDEFGHI"[digito_control]

        # Tipos que solo admiten letra de control
        if tipo_cif in "PQSKW":
            if control == letra_control:
                return True, "CIF_LETRA"
            return False, f"Carácter de control CIF incorrecto (esperado {letra_control})"
        # Tipos que solo admiten número de control
        elif tipo_cif in "ABEH":
            if control == str(digito_control):
                return True, "CIF_NUMERICO"
            return False, f"Dígito de control CIF incorrecto (esperado {digito_control})"
        # Tipos que admiten tanto letra como número
        else:
            if control == str(digito_control) or control == letra_control:
                return True, "CIF_MIXTO"
            return False, f"Control CIF incorrecto (esperado {digito_control} o {letra_control})"

    return False, "Formato no reconocido para NIF, NIE o CIF español"


def validate_arithmetic_consistency(
    base_imponible: float,
    iva_amount: float,
    total_amount: float,
    iva_rate: Optional[float] = None,
    irpf_amount: float = 0.0,
    irpf_rate: Optional[float] = None,
    tolerance: float = 0.02
) -> Tuple[bool, List[str]]:
    """
    Comprueba estrictamente la consistencia aritmética de una factura:
    - Base + IVA - IRPF == Total (con tolerancia para redondeos por línea)
    - Base * (Tipo IVA / 100) == Cuota IVA
    """
    errors = []
    
    # 1. Verificación del cálculo de IVA
    if iva_rate is not None and iva_rate > 0:
        expected_iva = round(base_imponible * (iva_rate / 100.0), 2)
        if abs(expected_iva - iva_amount) > tolerance:
            errors.append(
                f"Descuadre en cuota de IVA: Base ({base_imponible:.2f} €) al {iva_rate}% "
                f"debería ser {expected_iva:.2f} €, pero se indicó {iva_amount:.2f} €."
            )

    # 2. Verificación del cálculo de IRPF (si aplica)
    if irpf_rate is not None and irpf_rate > 0:
        expected_irpf = round(base_imponible * (irpf_rate / 100.0), 2)
        if abs(expected_irpf - irpf_amount) > tolerance:
            errors.append(
                f"Descuadre en retención IRPF: Base ({base_imponible:.2f} €) al {irpf_rate}% "
                f"debería ser {expected_irpf:.2f} €, pero se indicó {irpf_amount:.2f} €."
            )

    # 3. Verificación de suma total
    expected_total = round(base_imponible + iva_amount - irpf_amount, 2)
    if abs(expected_total - total_amount) > tolerance:
        errors.append(
            f"Descuadre en importe total: Base ({base_imponible:.2f} €) + IVA ({iva_amount:.2f} €) - "
            f"IRPF ({irpf_amount:.2f} €) = {expected_total:.2f} €, pero se indicó {total_amount:.2f} €."
        )

    return (len(errors) == 0, errors)


def validate_invoice_for_sif(invoice_data: Dict[str, Any]) -> FiscalValidationResult:
    """
    Validador determinista integral antes del registro Veri*Factu.
    Garantiza que ningún dato erróneo o inventado por un LLM entre al SIF sin revisión.
    """
    errors = []
    warnings = []

    # 1. Campos obligatorios
    issuer_nif = str(invoice_data.get("issuer_nif", "")).strip().upper()
    receiver_nif = str(invoice_data.get("receiver_nif", "")).strip().upper()
    invoice_number = str(invoice_data.get("invoice_number", "")).strip()
    date_of_issue = str(invoice_data.get("date_of_issue", "")).strip()

    if not invoice_number:
        errors.append("El número de factura es obligatorio.")
    if not date_of_issue:
        errors.append("La fecha de expedición es obligatoria.")

    # 2. Validación de NIF Emisor
    valid_issuer, issuer_msg = validate_spanish_id(issuer_nif)
    if not valid_issuer:
        errors.append(f"NIF/CIF del emisor ({issuer_nif}) no válido: {issuer_msg}")

    # 3. Validación de NIF Receptor (si no es factura simplificada sin receptor)
    tipo_factura = str(invoice_data.get("tipo_factura", "F1")).strip().upper()
    if tipo_factura not in VALID_INVOICE_TYPES:
        warnings.append(f"Tipo de factura '{tipo_factura}' no estándar; se asumirá F1/R1.")

    if receiver_nif and receiver_nif not in ("VARIOUS", "GENERIC", "SIMPLIFICADA"):
        valid_recv, recv_msg = validate_spanish_id(receiver_nif)
        if not valid_recv:
            # En operaciones intracomunitarias o internacionales puede no ser NIF español
            warnings.append(f"NIF del receptor ({receiver_nif}) no es un NIF/CIF español estándar ({recv_msg}).")

    # 4. Validación numérica y de cuadre
    try:
        base_imponible = float(invoice_data.get("base_imponible", 0.0))
        iva_amount = float(invoice_data.get("iva_amount", 0.0))
        total_amount = float(invoice_data.get("total_amount", 0.0))
        irpf_amount = float(invoice_data.get("irpf_amount", 0.0))
        iva_rate = float(invoice_data["iva_rate"]) if "iva_rate" in invoice_data and invoice_data["iva_rate"] is not None else None
        irpf_rate = float(invoice_data["irpf_rate"]) if "irpf_rate" in invoice_data and invoice_data["irpf_rate"] is not None else None
    except (ValueError, TypeError) as e:
        return FiscalValidationResult(
            is_valid=False,
            requires_human_review=True,
            errors=[f"Error en formato numérico de importes: {str(e)}"]
        )

    # Validar tipos impositivos contra listas autorizadas
    if iva_rate is not None and iva_rate not in VALID_IVA_RATES:
        errors.append(f"Tipo de IVA '{iva_rate}%' no es un tipo impositivo legal en España ({sorted(VALID_IVA_RATES)}).")

    if irpf_rate is not None and irpf_rate not in VALID_IRPF_RATES:
        warnings.append(f"Tipo de IRPF '{irpf_rate}%' poco habitual. Verifique retención aplicable.")

    # Validar coherencia aritmética
    is_arithmetic_valid, arithmetic_errors = validate_arithmetic_consistency(
        base_imponible=base_imponible,
        iva_amount=iva_amount,
        total_amount=total_amount,
        iva_rate=iva_rate,
        irpf_amount=irpf_amount,
        irpf_rate=irpf_rate
    )
    if not is_arithmetic_valid:
        errors.extend(arithmetic_errors)

    is_valid = len(errors) == 0
    requires_human_review = not is_valid or len(warnings) > 0

    sanitized = {
        **invoice_data,
        "issuer_nif": issuer_nif,
        "receiver_nif": receiver_nif,
        "base_imponible": round(base_imponible, 2),
        "iva_amount": round(iva_amount, 2),
        "total_amount": round(total_amount, 2),
        "irpf_amount": round(irpf_amount, 2),
        "tipo_factura": tipo_factura
    }

    return FiscalValidationResult(
        is_valid=is_valid,
        requires_human_review=requires_human_review,
        errors=errors,
        warnings=warnings,
        sanitized_data=sanitized
    )

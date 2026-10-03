"""
Fixtures y generadores de datos sintéticos para las pruebas del Modelo 190.
"""

from typing import Dict, Any, List
from app.utils.encryption import encryptor


def create_mock_fiscal_190_dataset(year: int = 2026) -> Dict[str, Any]:
    """
    Genera un conjunto de datos coherente para pruebas del Modelo 190 y su conciliación con el Modelo 111.
    """
    employees = [
        {
            "id": 101,
            "nif": "12345678Z",
            "name": "GARCIA LOPEZ JUAN",
            "birth_year": 1985,
            "family_situation": 2,
            "spouse_nif": "87654321X",
            "num_descendants": 2,
            "disability": 0
        },
        {
            "id": 102,
            "nif": "23456789C",
            "name": "MARTINEZ RUIZ ANA",
            "birth_year": 1990,
            "family_situation": 1,
            "spouse_nif": None,
            "num_descendants": 1,
            "disability": 0
        }
    ]

    # Nóminas: Juan (12 meses a 2.500 bruto, 375 IRPF = 30.000 bruto, 4.500 IRPF)
    # Ana: (12 meses a 1.800 bruto, 180 IRPF = 21.600 bruto, 2.160 IRPF)
    # Total nóminas: 51.600 bruto, 6.660 IRPF
    payrolls = []
    for m in range(1, 13):
        payrolls.append({
            "employee_id": 101,
            "year": year,
            "month": m,
            "gross_total": 2500.0,
            "irpf_amount": 375.0,
            "in_kind_valuation": 50.0,
            "in_kind_on_account": 7.5
        })
        payrolls.append({
            "employee_id": 102,
            "year": year,
            "month": m,
            "gross_total": 1800.0,
            "irpf_amount": 180.0,
            "in_kind_valuation": 0.0,
            "in_kind_on_account": 0.0
        })

    # Facturas profesionales (Clave G):
    # Prof 1 (Tipo general 15%, Subclave 01): 4 facturas trimestrales de 1.000 € base, 150 € IRPF = 4.000 base, 600 IRPF
    # Prof 2 (Tipo reducido 7%, Subclave 02): 2 facturas de 2.000 € base, 140 € IRPF = 4.000 base, 280 IRPF
    # Total profesionales: 8.000 base, 880 IRPF
    invoices = [
        {
            "year": year,
            "quarter": 1,
            "category": "gasto",
            "issuer_nif": "34567890D",
            "issuer_name": "CONSULTORIA FISCAL EXPERTA SL",
            "base_imponible": 1000.0,
            "irpf_amount": 150.0,
            "irpf_rate": 15.0,
            "retention_subclave": "01",
            "retention_clave": "G"
        },
        {
            "year": year,
            "quarter": 2,
            "category": "gasto",
            "issuer_nif": "34567890D",
            "issuer_name": "CONSULTORIA FISCAL EXPERTA SL",
            "base_imponible": 1000.0,
            "irpf_amount": 150.0,
            "irpf_rate": 15.0,
            "retention_subclave": "01",
            "retention_clave": "G"
        },
        {
            "year": year,
            "quarter": 3,
            "category": "gasto",
            "issuer_nif": "34567890D",
            "issuer_name": "CONSULTORIA FISCAL EXPERTA SL",
            "base_imponible": 1000.0,
            "irpf_amount": 150.0,
            "irpf_rate": 15.0,
            "retention_subclave": "01",
            "retention_clave": "G"
        },
        {
            "year": year,
            "quarter": 4,
            "category": "gasto",
            "issuer_nif": "34567890D",
            "issuer_name": "CONSULTORIA FISCAL EXPERTA SL",
            "base_imponible": 1000.0,
            "irpf_amount": 150.0,
            "irpf_rate": 15.0,
            "retention_subclave": "01",
            "retention_clave": "G"
        },
        {
            "year": year,
            "quarter": 2,
            "category": "gasto",
            "issuer_nif": "45678901E",
            "issuer_name": "NUEVO ARQUITECTO AUTONOMO",
            "base_imponible": 2000.0,
            "irpf_amount": 140.0,
            "irpf_rate": 7.0,
            "retention_subclave": "02",
            "retention_clave": "G"
        },
        {
            "year": year,
            "quarter": 4,
            "category": "gasto",
            "issuer_nif": "45678901E",
            "issuer_name": "NUEVO ARQUITECTO AUTONOMO",
            "base_imponible": 2000.0,
            "irpf_amount": 140.0,
            "irpf_rate": 7.0,
            "retention_subclave": "02",
            "retention_clave": "G"
        }
    ]

    return {
        "year": year,
        "employees": employees,
        "payrolls": payrolls,
        "invoices": invoices,
        "expected_totales": {
            "total_perceptores": 4,
            "total_retenciones_trabajo": 6660.0,
            "total_retenciones_profesionales": 880.0,
            "total_retenciones_global": 7540.0
        }
    }

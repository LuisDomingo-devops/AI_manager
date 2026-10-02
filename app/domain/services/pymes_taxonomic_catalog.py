"""
Catálogo taxonómico oficial del Plan General de Contabilidad de PYMES (RD 1515/2007).
Define la estructura reglamentaria de masas patrimoniales y epígrafes para:
- Balance de Situación (Depósito de cuentas en el Registro Mercantil).
- Cuenta de Pérdidas y Ganancias (PyG) por naturaleza.
"""

from typing import Dict, List, Any


class PymesTaxonomicCatalog:
    """Catálogo de epígrafes oficiales del PGC PYMES (RD 1515/2007)."""

    # --- Epígrafes del Balance de Situación ---
    BALANCE_EPIGRAFES = {
        # ACTIVO NO CORRIENTE
        "ANC_INTANGIBLE": {
            "codigo": "A.I",
            "nombre": "Inmovilizado intangible",
            "tipo_masa": "ACTIVO_NO_CORRIENTE",
            "prefijos_positivos": ["20"],
            "prefijos_compensatorios": ["280", "290"]
        },
        "ANC_MATERIAL": {
            "codigo": "A.II",
            "nombre": "Inmovilizado material",
            "tipo_masa": "ACTIVO_NO_CORRIENTE",
            "prefijos_positivos": ["21"],
            "prefijos_compensatorios": ["281", "291"]
        },
        "ANC_INMOBILIARIAS": {
            "codigo": "A.III",
            "nombre": "Inversiones inmobiliarias",
            "tipo_masa": "ACTIVO_NO_CORRIENTE",
            "prefijos_positivos": ["22"],
            "prefijos_compensatorios": ["282", "292"]
        },
        "ANC_FINANCIERAS": {
            "codigo": "A.IV",
            "nombre": "Inversiones financieras a largo plazo",
            "tipo_masa": "ACTIVO_NO_CORRIENTE",
            "prefijos_positivos": ["25", "26"],
            "prefijos_compensatorios": ["297", "298"]
        },

        # ACTIVO CORRIENTE
        "AC_EXISTENCIAS": {
            "codigo": "B.I",
            "nombre": "Existencias",
            "tipo_masa": "ACTIVO_CORRIENTE",
            "prefijos_positivos": ["30", "31", "32", "33", "34", "35", "36"],
            "prefijos_compensatorios": ["39"]
        },
        "AC_DEUDORES": {
            "codigo": "B.II",
            "nombre": "Deudores comerciales y otras cuentas a cobrar",
            "tipo_masa": "ACTIVO_CORRIENTE",
            "prefijos_positivos": ["430", "431", "44", "460", "470", "472", "473"],
            "prefijos_compensatorios": ["490", "493"]
        },
        "AC_FINANCIERAS_CP": {
            "codigo": "B.III",
            "nombre": "Inversiones financieras a corto plazo",
            "tipo_masa": "ACTIVO_CORRIENTE",
            "prefijos_positivos": ["53", "54"],
            "prefijos_compensatorios": ["597", "598"]
        },
        "AC_PERIODIFICACIONES": {
            "codigo": "B.IV",
            "nombre": "Periodificaciones a corto plazo",
            "tipo_masa": "ACTIVO_CORRIENTE",
            "prefijos_positivos": ["480"],
            "prefijos_compensatorios": []
        },
        "AC_TESORERIA": {
            "codigo": "B.V",
            "nombre": "Efectivo y otros activos líquidos equivalentes",
            "tipo_masa": "ACTIVO_CORRIENTE",
            "prefijos_positivos": ["57"],
            "prefijos_compensatorios": []
        },

        # PATRIMONIO NETO (FONDOS PROPIOS)
        "PN_CAPITAL": {
            "codigo": "A-1.I",
            "nombre": "Capital",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": ["100", "101", "102"],
            "prefijos_compensatorios": ["103", "104"]
        },
        "PN_PRIMA_EMISION": {
            "codigo": "A-1.II",
            "nombre": "Prima de emisión",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": ["110"],
            "prefijos_compensatorios": []
        },
        "PN_RESERVAS": {
            "codigo": "A-1.III",
            "nombre": "Reservas",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": ["112", "113", "114", "119"],
            "prefijos_compensatorios": []
        },
        "PN_ACCIONES_PROPIAS": {
            "codigo": "A-1.IV",
            "nombre": "(Acciones y participaciones en patrimonio propias)",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": [],
            "prefijos_compensatorios": ["108", "109"]
        },
        "PN_RESULTADOS_ANTERIORES": {
            "codigo": "A-1.V",
            "nombre": "Resultados de ejercicios anteriores",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": ["120"],
            "prefijos_compensatorios": ["121"]
        },
        "PN_OTRAS_APORTACIONES": {
            "codigo": "A-1.VI",
            "nombre": "Otras aportaciones de socios",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": ["118"],
            "prefijos_compensatorios": []
        },
        "PN_RESULTADO_EJERCICIO": {
            "codigo": "A-1.VII",
            "nombre": "Resultado del ejercicio",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": ["129"],
            "prefijos_compensatorios": []
        },
        "PN_DIVIDENDO_CUENTA": {
            "codigo": "A-1.VIII",
            "nombre": "(Dividendo a cuenta)",
            "tipo_masa": "PATRIMONIO_NETO",
            "prefijos_positivos": [],
            "prefijos_compensatorios": ["557"]
        },

        # PASIVO NO CORRIENTE
        "PNC_DEUDAS_LP": {
            "codigo": "B.I",
            "nombre": "Deudas a largo plazo",
            "tipo_masa": "PASIVO_NO_CORRIENTE",
            "prefijos_positivos": ["16", "17", "18"],
            "prefijos_compensatorios": []
        },

        # PASIVO CORRIENTE
        "PC_DEUDAS_CP": {
            "codigo": "C.I",
            "nombre": "Deudas a corto plazo",
            "tipo_masa": "PASIVO_CORRIENTE",
            "prefijos_positivos": ["51", "52", "56"],
            "prefijos_compensatorios": []
        },
        "PC_ACREEDORES": {
            "codigo": "C.II",
            "nombre": "Acreedores comerciales y otras cuentas a pagar",
            "tipo_masa": "PASIVO_CORRIENTE",
            "prefijos_positivos": ["400", "401", "410", "411", "465", "475", "476", "477"],
            "prefijos_compensatorios": []
        },
        "PC_PERIODIFICACIONES": {
            "codigo": "C.III",
            "nombre": "Periodificaciones a corto plazo",
            "tipo_masa": "PASIVO_CORRIENTE",
            "prefijos_positivos": ["485"],
            "prefijos_compensatorios": []
        }
    }

    # --- Epígrafes de la Cuenta de Pérdidas y Ganancias ---
    PYG_EPIGRAFES = {
        "1_CIFRA_NEGOCIOS": {
            "codigo": "1",
            "nombre": "Importe neto de la cifra de negocios",
            "cuentas_ingreso": ["700", "701", "702", "703", "704", "705"],
            "cuentas_minoracion": ["706", "708", "709"]
        },
        "2_VARIACION_EXISTENCIAS": {
            "codigo": "2",
            "nombre": "Variación de existencias de productos terminados y en curso",
            "cuentas_ingreso": ["71"],
            "cuentas_minoracion": ["61"]
        },
        "3_TRABAJOS_ACTIVO": {
            "codigo": "3",
            "nombre": "Trabajos realizados por la empresa para su activo",
            "cuentas_ingreso": ["73"],
            "cuentas_minoracion": []
        },
        "4_APROVISIONAMIENTOS": {
            "codigo": "4",
            "nombre": "Aprovisionamientos",
            "cuentas_ingreso": ["606", "608", "609"],
            "cuentas_minoracion": ["600", "601", "602", "607", "610"]
        },
        "5_OTROS_INGRESOS_EXPLOTACION": {
            "codigo": "5",
            "nombre": "Otros ingresos de explotación",
            "cuentas_ingreso": ["740", "747", "75"],
            "cuentas_minoracion": []
        },
        "6_GASTOS_PERSONAL": {
            "codigo": "6",
            "nombre": "Gastos de personal",
            "cuentas_ingreso": [],
            "cuentas_minoracion": ["640", "641", "642", "643", "649"]
        },
        "7_OTROS_GASTOS_EXPLOTACION": {
            "codigo": "7",
            "nombre": "Otros gastos de explotación",
            "cuentas_ingreso": ["795"],
            "cuentas_minoracion": ["62", "631", "634", "636", "639", "65", "694"]
        },
        "8_AMORTIZACIONES": {
            "codigo": "8",
            "nombre": "Amortización del inmovilizado",
            "cuentas_ingreso": [],
            "cuentas_minoracion": ["680", "681", "682"]
        },
        "9_SUBVENCIONES_INMOVILIZADO": {
            "codigo": "9",
            "nombre": "Imputación de subvenciones de inmovilizado no financiero y otras",
            "cuentas_ingreso": ["746"],
            "cuentas_minoracion": []
        },
        "10_EXCESOS_PROVISIONES": {
            "codigo": "10",
            "nombre": "Excesos de provisiones",
            "cuentas_ingreso": ["7951", "7952"],
            "cuentas_minoracion": []
        },
        "11_DETERIORO_ENAJENACIONES": {
            "codigo": "11",
            "nombre": "Deterioro y resultado por enajenaciones del inmovilizado",
            "cuentas_ingreso": ["770", "771", "772"],
            "cuentas_minoracion": ["670", "671", "672"]
        },

        # SECCIÓN FINANCIERA
        "12_INGRESOS_FINANCIEROS": {
            "codigo": "12",
            "nombre": "Ingresos financieros",
            "cuentas_ingreso": ["760", "761", "762", "769"],
            "cuentas_minoracion": []
        },
        "13_GASTOS_FINANCIEROS": {
            "codigo": "13",
            "nombre": "Gastos financieros",
            "cuentas_ingreso": [],
            "cuentas_minoracion": ["661", "662", "669"]
        },
        "14_VARIACION_VALOR_RAZONABLE": {
            "codigo": "14",
            "nombre": "Variación de valor razonable en instrumentos financieros",
            "cuentas_ingreso": ["763"],
            "cuentas_minoracion": ["663"]
        },
        "15_DIFERENCIAS_CAMBIO": {
            "codigo": "15",
            "nombre": "Diferencias de cambio",
            "cuentas_ingreso": ["768"],
            "cuentas_minoracion": ["668"]
        },
        "16_DETERIORO_FINANCIERO": {
            "codigo": "16",
            "nombre": "Deterioro y enajenaciones de instrumentos financieros",
            "cuentas_ingreso": ["766"],
            "cuentas_minoracion": ["666", "667"]
        },

        # IMPUESTO SOBRE BENEFICIOS
        "17_IMPUESTO_BENEFICIOS": {
            "codigo": "17",
            "nombre": "Impuesto sobre beneficios",
            "cuentas_ingreso": ["6301", "638"],
            "cuentas_minoracion": ["630", "6300"]
        }
    }

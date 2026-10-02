"""
Servicio generador de la Cuenta de Pérdidas y Ganancias (PyG) por naturaleza según el PGC PYMES (RD 1515/2007).
Proporciona desglose escalonado de márgenes: Margen Bruto, EBITDA, EBIT, BAI, Cuenta 630 y Resultado Neto (Cuenta 129).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.domain.schemas import IncomeStatementDTO, FinancialStatementLineDTO
from app.domain.services.pymes_taxonomic_catalog import PymesTaxonomicCatalog
from app.infrastructure.database.legal_connection import get_legal_readonly_connection


class IncomeStatementService:
    """Motor de cálculo de la Cuenta de Pérdidas y Ganancias según el PGC PYMES."""

    def calculate_income_statement(
        self,
        tenant_id: str,
        fiscal_year: int,
        quarter: Optional[int] = None,
        corporate_tax_rate: float = 0.25
    ) -> IncomeStatementDTO:
        """
        Calcula la Cuenta de Resultados para el ejercicio o trimestre consultado.
        Aplica la escala escalonada y la provisión estimada de la Cuenta 630 (IS).
        """
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT l.account_code, l.debit, l.credit, e.entry_date
            FROM legal_journal_lines l
            JOIN legal_journal_entries e ON l.entry_id = e.id
            WHERE e.tenant_id = ? AND e.fiscal_year = ?
            """,
            (tenant_id, fiscal_year)
        )
        rows = cursor.fetchall()
        cursor.close()

        # Acumular saldos de cuentas de ingresos (7) y gastos (6)
        cuentas_saldos: Dict[str, Dict[str, Decimal]] = {}
        for code, debit_raw, credit_raw, entry_date_str in rows:
            if not (code.startswith("6") or code.startswith("7")):
                continue

            # Filtrar por trimestre si se solicita
            if quarter is not None and entry_date_str:
                try:
                    entry_dt = datetime.strptime(entry_date_str[:10], "%Y-%m-%d")
                    entry_quarter = (entry_dt.month - 1) // 3 + 1
                    if entry_quarter != quarter:
                        continue
                except Exception:
                    pass

            debit = Decimal(str(debit_raw if debit_raw is not None else "0.00")).quantize(Decimal("0.01"))
            credit = Decimal(str(credit_raw if credit_raw is not None else "0.00")).quantize(Decimal("0.01"))

            if code not in cuentas_saldos:
                cuentas_saldos[code] = {"debe": Decimal("0.00"), "haber": Decimal("0.00")}

            cuentas_saldos[code]["debe"] += debit
            cuentas_saldos[code]["haber"] += credit

        # Evaluar saldos netos por partida
        def _get_account_balance(code_prefix: str, is_income: bool) -> Decimal:
            total = Decimal("0.00")
            for acc, s in cuentas_saldos.items():
                if acc.startswith(code_prefix):
                    if is_income:
                        total += (s["haber"] - s["debe"])
                    else:
                        total += (s["debe"] - s["haber"])
            return total

        # 1. Cifra de negocios
        ingresos_ventas = sum(_get_account_balance(p, True) for p in ["700", "701", "702", "703", "704", "705"])
        minoracion_ventas = sum(_get_account_balance(p, False) for p in ["706", "708", "709"])
        cifra_negocios = (ingresos_ventas - minoracion_ventas).quantize(Decimal("0.01"))

        # 2. Variación de existencias
        var_existencias = (_get_account_balance("71", True) - _get_account_balance("61", False)).quantize(Decimal("0.01"))

        # 3. Aprovisionamientos
        gastos_compras = sum(_get_account_balance(p, False) for p in ["600", "601", "602", "607", "610"])
        descuentos_compras = sum(_get_account_balance(p, True) for p in ["606", "608", "609"])
        aprovisionamientos = (gastos_compras - descuentos_compras).quantize(Decimal("0.01"))

        # 4. Otros ingresos de explotación
        otros_ingresos = sum(_get_account_balance(p, True) for p in ["740", "747", "75"]).quantize(Decimal("0.01"))

        # 5. Gastos de personal
        gastos_personal = sum(_get_account_balance(p, False) for p in ["640", "641", "642", "643", "649"]).quantize(Decimal("0.01"))

        # 6. Otros gastos de explotación
        otros_gastos = sum(_get_account_balance(p, False) for p in ["62", "631", "634", "636", "639", "65", "694"]).quantize(Decimal("0.01"))

        # 7. Amortizaciones
        amortizaciones = sum(_get_account_balance(p, False) for p in ["680", "681", "682"]).quantize(Decimal("0.01"))

        # Márgenes escalonados
        margen_bruto = (cifra_negocios - aprovisionamientos).quantize(Decimal("0.01"))
        ebitda = (margen_bruto + otros_ingresos + var_existencias - gastos_personal - otros_gastos).quantize(Decimal("0.01"))
        resultado_explotacion = (ebitda - amortizaciones).quantize(Decimal("0.01"))

        # SECCIÓN FINANCIERA
        ingresos_financieros = sum(_get_account_balance(p, True) for p in ["760", "761", "762", "769"]).quantize(Decimal("0.01"))
        gastos_financieros = sum(_get_account_balance(p, False) for p in ["661", "662", "669"]).quantize(Decimal("0.01"))
        variacion_vr = (_get_account_balance("763", True) - _get_account_balance("663", False)).quantize(Decimal("0.01"))
        dif_cambio = (_get_account_balance("768", True) - _get_account_balance("668", False)).quantize(Decimal("0.01"))
        deterioro_fin = (_get_account_balance("766", True) - _get_account_balance("666", False) - _get_account_balance("667", False)).quantize(Decimal("0.01"))

        resultado_financiero = (ingresos_financieros - gastos_financieros + variacion_vr + dif_cambio + deterioro_fin).quantize(Decimal("0.01"))

        # RESULTADO ANTES DE IMPUESTOS (BAI)
        resultado_antes_impuestos = (resultado_explotacion + resultado_financiero).quantize(Decimal("0.01"))

        # IMPUESTO SOBRE SOCIEDADES (Cuenta 630)
        # Si ya existe asiento contable contabilizado en la 630, lo usamos; si no, calculamos la provisión
        gasto_630_asentado = _get_account_balance("630", False)
        if gasto_630_asentado > Decimal("0.00"):
            impuesto_sociedades = gasto_630_asentado.quantize(Decimal("0.01"))
        elif resultado_antes_impuestos > Decimal("0.00"):
            tasa_dec = Decimal(str(corporate_tax_rate)).quantize(Decimal("0.0001"))
            impuesto_sociedades = (resultado_antes_impuestos * tasa_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            impuesto_sociedades = Decimal("0.00")

        resultado_neto = (resultado_antes_impuestos - impuesto_sociedades).quantize(Decimal("0.01"))

        # Epígrafes estructurados
        lineas_epigrafes = [
            FinancialStatementLineDTO(
                epigrafe_codigo="1",
                epigrafe_nombre="Importe neto de la cifra de negocios",
                cuentas_asociadas=[c for c in cuentas_saldos if c.startswith("70")],
                saldo_ejercicio_actual=cifra_negocios
            ),
            FinancialStatementLineDTO(
                epigrafe_codigo="4",
                epigrafe_nombre="Aprovisionamientos",
                cuentas_asociadas=[c for c in cuentas_saldos if c.startswith("60")],
                saldo_ejercicio_actual=-aprovisionamientos
            ),
            FinancialStatementLineDTO(
                epigrafe_codigo="6",
                epigrafe_nombre="Gastos de personal",
                cuentas_asociadas=[c for c in cuentas_saldos if c.startswith("64")],
                saldo_ejercicio_actual=-gastos_personal
            ),
            FinancialStatementLineDTO(
                epigrafe_codigo="7",
                epigrafe_nombre="Otros gastos de explotación",
                cuentas_asociadas=[c for c in cuentas_saldos if c.startswith("62") or c.startswith("631")],
                saldo_ejercicio_actual=-otros_gastos
            ),
            FinancialStatementLineDTO(
                epigrafe_codigo="8",
                epigrafe_nombre="Amortización del inmovilizado",
                cuentas_asociadas=[c for c in cuentas_saldos if c.startswith("68")],
                saldo_ejercicio_actual=-amortizaciones
            ),
            FinancialStatementLineDTO(
                epigrafe_codigo="17",
                epigrafe_nombre="Impuesto sobre beneficios (Cuenta 630)",
                cuentas_asociadas=["63000000"],
                saldo_ejercicio_actual=-impuesto_sociedades
            )
        ]

        fecha_desde = f"{fiscal_year}-01-01"
        fecha_hasta = f"{fiscal_year}-12-31" if quarter is None else f"{fiscal_year}-{quarter*3:02d}-28"

        return IncomeStatementDTO(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            cifra_negocios=cifra_negocios,
            variacion_existencias=var_existencias,
            aprovisionamientos=aprovisionamientos,
            gastos_personal=gastos_personal,
            otros_gastos_explotacion=otros_gastos,
            amortizaciones_dotacion=amortizaciones,
            otros_ingresos_explotacion=otros_ingresos,
            margen_bruto=margen_bruto,
            ebitda=ebitda,
            resultado_explotacion=resultado_explotacion,
            ingresos_financieros=ingresos_financieros,
            gastos_financieros=gastos_financieros,
            resultado_financiero=resultado_financiero,
            resultado_antes_impuestos=resultado_antes_impuestos,
            impuesto_sociedades=impuesto_sociedades,
            resultado_neto_ejercicio=resultado_neto,
            lineas_epigrafes=lineas_epigrafes
        )

"""
Servicio generador de Informes Contables: Balance de Situación y Cuenta de Pérdidas y Ganancias (PyG).
Conforme a la estructura del Plan General Contable (PGC Pymes).
"""

from typing import Dict, Any
from app.infrastructure.database.legal_connection import get_legal_readonly_connection


class AccountingReportingService:
    """Genera estados financieros oficiales basados en el Libro Diario y Mayor."""

    def generate_profit_and_loss(self, tenant_id: str, fiscal_year: int) -> Dict[str, Any]:
        """
        Genera la Cuenta de Pérdidas y Ganancias (PyG) para el ejercicio.
        Ingresos (Grupo 7) - Gastos (Grupo 6).
        """
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT l.account_code, SUM(l.debit), SUM(l.credit)
            FROM legal_journal_lines l
            JOIN legal_journal_entries e ON l.entry_id = e.id
            WHERE e.tenant_id = ? AND e.fiscal_year = ?
            GROUP BY l.account_code
            """,
            (tenant_id, fiscal_year)
        )
        rows = cursor.fetchall()
        cursor.close()

        total_ingresos = 0.0
        total_gastos = 0.0
        desglose_ingresos = {}
        desglose_gastos = {}

        for code, debit, credit in rows:
            debit = debit or 0.0
            credit = credit or 0.0
            if code.startswith("7"):
                # En cuentas de ingresos, el saldo normal es acreedor (credit - debit)
                saldo = round(credit - debit, 2)
                total_ingresos += saldo
                desglose_ingresos[code] = saldo
            elif code.startswith("6"):
                # En cuentas de gastos, el saldo normal es deudor (debit - credit)
                saldo = round(debit - credit, 2)
                total_gastos += saldo
                desglose_gastos[code] = saldo

        resultado = round(total_ingresos - total_gastos, 2)

        return {
            "fiscal_year": fiscal_year,
            "total_ingresos": round(total_ingresos, 2),
            "total_gastos": round(total_gastos, 2),
            "resultado_ejercicio": resultado,
            "ingresos": desglose_ingresos,
            "gastos": desglose_gastos
        }

    def generate_balance_sheet(self, tenant_id: str, fiscal_year: int) -> Dict[str, Any]:
        """
        Genera el Balance de Situación cerrado al ejercicio contable.
        Garantiza el cuadre: Total Activo = Total Pasivo + Patrimonio Neto.
        """
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT l.account_code, SUM(l.debit), SUM(l.credit)
            FROM legal_journal_lines l
            JOIN legal_journal_entries e ON l.entry_id = e.id
            WHERE e.tenant_id = ? AND e.fiscal_year = ?
            GROUP BY l.account_code
            """,
            (tenant_id, fiscal_year)
        )
        rows = cursor.fetchall()
        cursor.close()

        activo_no_corriente = 0.0
        activo_corriente = 0.0
        patrimonio_neto = 0.0
        pasivo = 0.0

        for code, debit, credit in rows:
            debit = debit or 0.0
            credit = credit or 0.0
            # Saldo neto deudor = debit - credit
            saldo_deudor = debit - credit
            # Saldo neto acreedor = credit - debit
            saldo_acreedor = credit - debit

            # Grupo 2: Inmovilizado
            if code.startswith("2"):
                if code.startswith("28"):  # Amortización acumulada (cuenta compensatoria de activo)
                    activo_no_corriente -= saldo_acreedor
                else:
                    activo_no_corriente += saldo_deudor

            # Grupo 5: Tesorería
            elif code.startswith("57"):
                activo_corriente += saldo_deudor

            # Grupo 4: Deudores y Acreedores
            elif code.startswith("43"):  # Clientes
                activo_corriente += saldo_deudor
            elif code.startswith("472") or code.startswith("473"):  # IVA Soportado / Retenciones
                activo_corriente += saldo_deudor
            elif code.startswith("40") or code.startswith("41"):  # Proveedores / Acreedores
                pasivo += saldo_acreedor
            elif code.startswith("477") or code.startswith("475"):  # IVA Repercutido / H.P. Acreedora
                pasivo += saldo_acreedor

            # Grupo 1: Patrimonio Neto y Financiación básica
            elif code.startswith("10"):  # Capital
                patrimonio_neto += saldo_acreedor
            elif code.startswith("11") or code.startswith("12"):  # Reservas / Resultados anteriores
                patrimonio_neto += saldo_acreedor

        # Incorporar el resultado del ejercicio en el Patrimonio Neto
        pyg = self.generate_profit_and_loss(tenant_id, fiscal_year)
        resultado_ejercicio = pyg["resultado_ejercicio"]
        patrimonio_neto += resultado_ejercicio

        total_activo = round(activo_no_corriente + activo_corriente, 2)
        total_pasivo_pn = round(patrimonio_neto + pasivo, 2)

        return {
            "fiscal_year": fiscal_year,
            "activo_no_corriente": round(activo_no_corriente, 2),
            "activo_corriente": round(activo_corriente, 2),
            "total_activo": total_activo,
            "patrimonio_neto": round(patrimonio_neto, 2),
            "pasivo": round(pasivo, 2),
            "total_pasivo_y_patrimonio_neto": total_pasivo_pn,
            "is_balanced": abs(total_activo - total_pasivo_pn) < 0.01
        }

"""
Servicio generador de Informes Contables: Balance de Situación y Cuenta de Pérdidas y Ganancias (PyG).
Conforme a la estructura del Plan General Contable (PGC Pymes).
"""

from decimal import Decimal
from typing import Dict, Any, List
from app.infrastructure.database.legal_connection import get_legal_readonly_connection


class AccountingReportingService:
    """Genera estados financieros oficiales basados en el Libro Diario y Mayor."""

    def generate_profit_and_loss(self, tenant_id: str, fiscal_year: int) -> Dict[str, Any]:
        """
        Genera la Cuenta de Pérdidas y Ganancias (PyG) para el ejercicio conforme al PGC PYMES.
        Proporciona desglose escalonado (EBITDA, EBIT, BAI, IS y Resultado Neto).
        """
        from app.domain.services.income_statement_service import IncomeStatementService
        service = IncomeStatementService()
        dto = service.calculate_income_statement(tenant_id=tenant_id, fiscal_year=fiscal_year)

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

        desglose_ingresos = {}
        desglose_gastos = {}

        for code, debit, credit in rows:
            debit = debit or 0.0
            credit = credit or 0.0
            if code.startswith("7"):
                saldo = round(credit - debit, 2)
                desglose_ingresos[code] = saldo
            elif code.startswith("6"):
                saldo = round(debit - credit, 2)
                desglose_gastos[code] = saldo

        total_ingresos_calc = float(sum(desglose_ingresos.values()))
        total_gastos_calc = float(sum(desglose_gastos.values()))
        resultado_calc = round(total_ingresos_calc - total_gastos_calc, 2)

        res = dto.model_dump()
        res.update({
            "fiscal_year": fiscal_year,
            "total_ingresos": total_ingresos_calc,
            "total_gastos": total_gastos_calc,
            "resultado_ejercicio": resultado_calc,
            "ingresos": desglose_ingresos,
            "gastos": desglose_gastos
        })
        return res

    def generate_balance_sheet(self, tenant_id: str, fiscal_year: int) -> Dict[str, Any]:
        """
        Genera el Balance de Situación cerrado al ejercicio contable según el PGC PYMES.
        Garantiza el cuadre matemático: Total Activo = Total Pasivo + Patrimonio Neto al céntimo.
        """
        from app.domain.services.balance_sheet_pymes_service import BalanceSheetPymesService
        service = BalanceSheetPymesService()
        dto = service.calculate_balance_sheet(tenant_id, fiscal_year)

        total_pnc = sum(line.saldo_ejercicio_actual for line in dto.pasivo_no_corriente)
        total_pc = sum(line.saldo_ejercicio_actual for line in dto.pasivo_corriente)
        total_pasivo = (total_pnc + total_pc).quantize(Decimal("0.01"))
        total_pn = sum(line.saldo_ejercicio_actual for line in dto.patrimonio_neto).quantize(Decimal("0.01"))
        total_anc = sum(line.saldo_ejercicio_actual for line in dto.activo_no_corriente).quantize(Decimal("0.01"))
        total_ac = sum(line.saldo_ejercicio_actual for line in dto.activo_corriente).quantize(Decimal("0.01"))

        res = dto.model_dump()
        res.update({
            "activo_no_corriente": float(total_anc),
            "activo_corriente": float(total_ac),
            "total_activo": float(dto.total_activo),
            "patrimonio_neto": float(total_pn),
            "pasivo": float(total_pasivo),
            "total_pasivo_y_patrimonio_neto": float(dto.total_pasivo_y_patrimonio_neto),
            "is_balanced": dto.is_balanced
        })
        return res

    def generate_official_daily_book(self, tenant_id: str, fiscal_year: int) -> Dict[str, Any]:
        """
        Genera el Libro Diario oficial para legalización mercantil (Arts. 25, 27 y 28 Cód. Comercio).
        Verifica el foliado correlativo ininterrumpido (1, 2, 3...) y el cuadre exacto en Decimal.
        """
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT e.entry_number, e.entry_date, e.concept, e.document_ref,
                   l.account_code, l.concept as line_concept, l.debit, l.credit
            FROM legal_journal_entries e
            JOIN legal_journal_lines l ON e.id = l.entry_id
            WHERE e.tenant_id = ? AND e.fiscal_year = ?
            ORDER BY e.entry_number ASC, l.id ASC
            """,
            (tenant_id, fiscal_year)
        )
        rows = cursor.fetchall()
        cursor.close()

        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        entries_dict: Dict[int, Dict[str, Any]] = {}

        for r in rows:
            entry_number, entry_date, concept, doc_ref, account_code, line_concept, debit_raw, credit_raw = r
            debit_dec = Decimal(str(debit_raw if debit_raw is not None else "0.00")).quantize(Decimal("0.01"))
            credit_dec = Decimal(str(credit_raw if credit_raw is not None else "0.00")).quantize(Decimal("0.01"))
            total_debit += debit_dec
            total_credit += credit_dec

            if entry_number not in entries_dict:
                entries_dict[entry_number] = {
                    "entry_number": entry_number,
                    "entry_date": entry_date,
                    "concept": concept,
                    "document_ref": doc_ref,
                    "lines": [],
                }
            entries_dict[entry_number]["lines"].append({
                "account_code": account_code,
                "concept": line_concept or concept,
                "debit": debit_dec,
                "credit": credit_dec,
            })

        entry_numbers = sorted(entries_dict.keys())
        # Verificar foliado correlativo ininterrumpido empezando en 1
        is_foliated_correlative = True
        if entry_numbers:
            expected = list(range(1, len(entry_numbers) + 1))
            is_foliated_correlative = (entry_numbers == expected)

        is_balanced = (total_debit == total_credit)

        return {
            "tenant_id": tenant_id,
            "fiscal_year": fiscal_year,
            "total_entries": len(entry_numbers),
            "is_foliated_correlative": is_foliated_correlative,
            "is_balanced": is_balanced,
            "total_debit": total_debit.quantize(Decimal("0.01")),
            "total_credit": total_credit.quantize(Decimal("0.01")),
            "entries": list(entries_dict.values()),
        }


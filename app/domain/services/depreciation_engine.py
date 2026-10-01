"""
Motor de amortizaciones automáticas de activos fijos según tablas oficiales de la AEAT.
Genera cálculos fiscales lineales y asientos contables en partida doble (cuentas 681 y 281).
"""

from datetime import datetime, date
from typing import Dict, Any, Optional
from decimal import Decimal
from app.domain.accounting.ports import RecordJournalEntryCommand, JournalEntryView
from app.domain.accounting.services import AccountingService


class DepreciationEngine:
    """Calcula y contabiliza la depreciación sistemática del inmovilizado material e intangible."""

    def calculate_annual_depreciation(
        self,
        acquisition_value: float,
        depreciation_rate: float,
        acquisition_date: str,
        fiscal_year: int,
        previous_accumulated: float = 0.0,
        residual_value: float = 0.0
    ) -> Dict[str, float]:
        """
        Calcula la cuota de amortización para el ejercicio fiscal indicado, prorrateando meses en el año de compra.
        """
        max_depreciable = max(0.0, acquisition_value - residual_value)
        remaining_depreciable = max(0.0, max_depreciable - previous_accumulated)

        if remaining_depreciable <= 0.0:
            return {
                "annual_amount": 0.0,
                "accumulated_depreciation": round(previous_accumulated, 2),
                "net_book_value": round(max(0.0, acquisition_value - previous_accumulated), 2)
            }

        # Analizar fecha de adquisición para prorrateo
        acq_dt = datetime.strptime(acquisition_date[:10], "%Y-%m-%d").date()
        annual_full_rate_amount = acquisition_value * (depreciation_rate / 100.0)

        if acq_dt.year == fiscal_year:
            # Prorrateo por meses de uso en el año de adquisición (mes completo desde inicio)
            months_active = 12 - acq_dt.month + 1
            calculated_amount = annual_full_rate_amount * (months_active / 12.0)
        elif acq_dt.year > fiscal_year:
            calculated_amount = 0.0
        else:
            calculated_amount = annual_full_rate_amount

        # Limitar al saldo pendiente amortizable
        final_amount = round(min(calculated_amount, remaining_depreciable), 2)
        new_accumulated = round(previous_accumulated + final_amount, 2)
        net_book_value = round(max(0.0, acquisition_value - new_accumulated), 2)

        return {
            "annual_amount": final_amount,
            "accumulated_depreciation": new_accumulated,
            "net_book_value": net_book_value
        }

    def post_depreciation_entry(
        self,
        tenant_id: str,
        asset: Dict[str, Any],
        fiscal_year: int,
        accounting_service: Optional[AccountingService] = None
    ) -> JournalEntryView:
        """
        Genera el asiento contable de dotación a la amortización en el Libro Diario.
        Debe: 68100000 | Haber: 28100000
        """
        service = accounting_service or AccountingService()

        calc = self.calculate_annual_depreciation(
            acquisition_value=float(asset.get("acquisition_value", 0.0)),
            depreciation_rate=float(asset.get("depreciation_rate", 20.0)),
            acquisition_date=str(asset.get("acquisition_date", f"{fiscal_year}-01-01")),
            fiscal_year=fiscal_year,
            previous_accumulated=float(asset.get("previous_accumulated", 0.0))
        )

        amount = calc["annual_amount"]
        if amount <= 0.0:
            raise ValueError(f"El activo {asset.get('code')} no tiene cuota amortizable para el ejercicio {fiscal_year}")

        entry_date = date(fiscal_year, 12, 31)
        concept = f"Dotación amortización ejercicio {fiscal_year}: {asset.get('description', asset.get('code'))}"

        command = RecordJournalEntryCommand(
            tenant_id=tenant_id,
            entry_date=entry_date,
            fiscal_year=fiscal_year,
            concept=concept,
            document_ref=asset.get("code"),
            lines=[
                {"account_code": "68100000", "debit": amount, "credit": 0.0},
                {"account_code": "28100000", "debit": 0.0, "credit": amount}
            ]
        )

        return service.record_entry(command)

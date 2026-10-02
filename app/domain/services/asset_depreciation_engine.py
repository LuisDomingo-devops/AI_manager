"""
Motor de Cálculo y Contabilización de Amortizaciones de Inmovilizado (PGC PYMES / Ley 27/2014 LIS).
Aplica amortización lineal, prorrata de adquisición mensual/anual, salvaguarda estricta
de valor residual y contabilización idempotente en el Libro Diario legal (cuentas 681/281).
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import uuid
from typing import List, Dict, Any, Optional

from app.domain.schemas import (
    DepreciationQuotaDTO,
    DepreciationRunResultDTO,
    AssetRecordDTO,
)
from app.infrastructure.database.asset_repository_db import SqliteAssetRepositoryAdapter
from app.infrastructure.database.legal_connection import (
    legal_write_transaction,
    get_legal_readonly_connection,
)


class AssetDepreciationEngine:
    """Motor contable de amortización técnica de activos fijos e inmovilizado."""

    def __init__(self, repository: Optional[SqliteAssetRepositoryAdapter] = None):
        self.repository = repository or SqliteAssetRepositoryAdapter()

    def calculate_depreciation_proposal(self, client_id: str, year: int) -> List[DepreciationQuotaDTO]:
        """
        Calcula la propuesta de cuotas de amortización para todos los activos de la empresa
        en el ejercicio fiscal indicado, aplicando prorrata mensual de alta y tope de valor residual.
        """
        assets = self.repository.list_assets(client_id)
        proposals: List[DepreciationQuotaDTO] = []

        for asset in assets:
            try:
                purchase_date_str = str(asset.get("purchase_date", ""))[:10]
                purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d")
            except Exception:
                try:
                    purchase_year = int(str(asset.get("purchase_date", "")).split("-")[0])
                    purchase_date = datetime(year=purchase_year, month=1, day=1)
                except Exception:
                    continue

            purchase_year = purchase_date.year
            if purchase_year > year:
                continue

            cost_dec = Decimal(str(asset.get("cost", "0.00"))).quantize(Decimal("0.01"))
            salvage_dec = Decimal(str(asset.get("salvage_value", "0.00"))).quantize(Decimal("0.01"))
            useful_life = int(asset.get("useful_life_years", 0))

            if useful_life <= 0:
                continue

            base_amortizable = (cost_dec - salvage_dec).quantize(Decimal("0.01"))
            if base_amortizable <= Decimal("0.00"):
                continue

            annual_quota = (base_amortizable / Decimal(str(useful_life))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            years_passed = year - purchase_year
            if years_passed > useful_life:
                continue

            is_prorated = False
            if years_passed == useful_life:
                # Último año: amortiza los meses residuales pendientes del primer año si se prorrateó
                if purchase_date.month > 1:
                    meses_restantes = purchase_date.month - 1
                    cuota = (annual_quota * Decimal(str(meses_restantes)) / Decimal("12")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    is_prorated = True
                else:
                    continue
            elif purchase_year == year:
                # Primer año de amortización: prorrata mensual desde el mes de compra
                meses_uso = 12 - purchase_date.month + 1
                cuota = (annual_quota * Decimal(str(meses_uso)) / Decimal("12")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                is_prorated = (meses_uso < 12)
            else:
                cuota = annual_quota

            # Salvaguarda de valor residual: la cuota no puede superar la base amortizable
            if cuota > base_amortizable:
                cuota = base_amortizable

            if cuota > Decimal("0.00"):
                category = str(asset.get("category", "")).upper()
                acc_debe = "68000000" if "INTANGIBLE" in category else "68100000"
                acc_haber = "28000000" if "INTANGIBLE" in category else "28100000"

                proposals.append(
                    DepreciationQuotaDTO(
                        asset_id=str(asset.get("id", "")),
                        asset_name=str(asset.get("name", "")),
                        account_debe=acc_debe,
                        account_haber=acc_haber,
                        quota_amount=cuota,
                        period=str(year),
                        is_prorated=is_prorated,
                        concept=f"Amortización ejercicio {year} - {asset.get('name', '')}"
                    )
                )

        return proposals

    def record_depreciation_entries(self, client_id: str, year: int) -> DepreciationRunResultDTO:
        """
        Contabiliza las dotaciones a la amortización en el Libro Diario legal (cuentas 681/281).
        Garantiza la idempotencia mediante verificación previa de asientos existentes.
        """
        proposals = self.calculate_depreciation_proposal(client_id, year)
        total_amount = sum((p.quota_amount for p in proposals), Decimal("0.00")).quantize(Decimal("0.01"))

        if not proposals or total_amount <= Decimal("0.00"):
            return DepreciationRunResultDTO(
                status="ok",
                tenant_id=client_id,
                fiscal_year=year,
                period=str(year),
                total_assets_processed=0,
                total_amount_amortized=Decimal("0.00"),
                is_posted=False,
                message="No hay activos pendientes de amortizar en este ejercicio.",
                quotas=[]
            )

        # 1. Comprobar si ya existe asiento de amortización para este ejercicio
        conn = get_legal_readonly_connection(client_id=client_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, entry_number FROM legal_journal_entries
            WHERE tenant_id = ? AND fiscal_year = ? AND concept LIKE '%Amortización%Inmovilizado%'
            LIMIT 1
            """,
            (client_id, year)
        )
        existing_entry = cursor.fetchone()
        cursor.close()

        if existing_entry:
            return DepreciationRunResultDTO(
                status="warning",
                tenant_id=client_id,
                fiscal_year=year,
                period=str(year),
                total_assets_processed=len(proposals),
                total_amount_amortized=total_amount,
                journal_entry_id=str(existing_entry[0]),
                is_posted=False,
                message=f"Las amortizaciones del ejercicio {year} ya estaban contabilizadas (Asiento #{existing_entry[1]}).",
                quotas=proposals
            )

        # 2. Contabilizar asiento en el Libro Diario legal
        with legal_write_transaction(client_id=client_id) as write_conn:
            w_cursor = write_conn.cursor()

            # Obtener correlativo de asiento
            w_cursor.execute(
                "SELECT COALESCE(MAX(entry_number), 0) + 1 FROM legal_journal_entries WHERE tenant_id = ? AND fiscal_year = ?",
                (client_id, year)
            )
            entry_number = w_cursor.fetchone()[0]

            entry_id = f"entry-deprec-{year}-{uuid.uuid4().hex[:8]}"
            entry_date = f"{year}-12-31"
            concept = f"Dotación Amortización Inmovilizado Ejercicio {year}"

            w_cursor.execute(
                """
                INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entry_id, client_id, entry_number, entry_date, year, concept)
            )

            # Insertar líneas agrupadas por cuenta
            line_idx = 1
            # Agrupar cuotas por cuenta de gasto y cuenta compensatoria
            debitos: Dict[str, Decimal] = {}
            creditos: Dict[str, Decimal] = {}

            for p in proposals:
                debitos[p.account_debe] = debitos.get(p.account_debe, Decimal("0.00")) + p.quota_amount
                creditos[p.account_haber] = creditos.get(p.account_haber, Decimal("0.00")) + p.quota_amount

            for acc, deb_amt in debitos.items():
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{entry_id}-l{line_idx}", entry_id, acc, str(deb_amt), "0.00")
                )
                line_idx += 1

            for acc, cred_amt in creditos.items():
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{entry_id}-l{line_idx}", entry_id, acc, "0.00", str(cred_amt))
                )
                line_idx += 1

        return DepreciationRunResultDTO(
            status="ok",
            tenant_id=client_id,
            fiscal_year=year,
            period=str(year),
            total_assets_processed=len(proposals),
            total_amount_amortized=total_amount,
            journal_entry_id=entry_id,
            is_posted=True,
            message=f"Amortización contabilizada correctamente. Total: {total_amount:.2f} €",
            quotas=proposals
        )

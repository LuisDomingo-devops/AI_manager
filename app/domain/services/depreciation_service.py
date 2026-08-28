from typing import List, Dict, Any
from datetime import datetime
from app.domain.ports.asset_repository_port import AssetRepositoryPort

class DepreciationService:
    def __init__(self, repository: AssetRepositoryPort):
        self.repository = repository

    def calculate_depreciation_proposal(self, client_id: str, year: int) -> List[Dict[str, Any]]:
        """
        Calcula la propuesta de cuotas de amortización del año natural para todos los activos del cliente.
        Aplica prorrata mensual si el activo se adquirió durante el año consultado.
        """
        assets = self.repository.list_assets(client_id)
        proposal = []

        for asset in assets:
            try:
                purchase_date_str = asset["purchase_date"]
                purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d")
            except ValueError:
                # Fallback al 1 de enero si el formato de fecha no es válido
                try:
                    purchase_date = datetime(year=int(asset["purchase_date"].split("-")[0]), month=1, day=1)
                except Exception:
                    continue

            purchase_year = purchase_date.year
            
            # Solo amortizamos si el activo se compró en o antes del año evaluado
            if purchase_year > year:
                continue

            cost = asset["cost"]
            salvage_value = asset.get("salvage_value", 0.0)
            useful_life = asset["useful_life_years"]
            
            if useful_life <= 0:
                continue

            annual_dep = (cost - salvage_value) / useful_life

            # Años transcurridos desde el año de compra (inclusive)
            years_passed = year - purchase_year

            # Vida útil transcurrida
            if years_passed > useful_life:
                continue
            elif years_passed == useful_life:
                # Último año de amortización: amortiza el residuo del primer año (los meses que no se amortizaron)
                if purchase_date.month > 1:
                    meses_restantes = purchase_date.month - 1
                    cuota = annual_dep * (meses_restantes / 12)
                else:
                    continue
            elif purchase_year == year:
                # Primer año de amortización: prorrata mensual
                meses_uso = 12 - purchase_date.month + 1
                cuota = annual_dep * (meses_uso / 12)
            else:
                # Año completo estándar
                cuota = annual_dep

            cuota = round(cuota, 2)
            if cuota > 0:
                proposal.append({
                    "asset_id": asset["id"],
                    "asset_name": asset["name"],
                    "account_debe": "68100000",  # Amortización Inmovilizado Material
                    "account_haber": "28100000", # Amortización Acumulada Inmovilizado Material
                    "amount": cuota,
                    "concept": f"Amortización anual {year} - {asset['name']}"
                })

        return proposal

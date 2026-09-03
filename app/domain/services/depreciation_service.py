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

    def record_depreciation_entries(self, client_id: str, year: int) -> Dict[str, Any]:
        """
        Calcula las cuotas de amortización para el año y las registra en el Libro Diario 
        usando LedgerService a fecha 31/12 del año indicado. 
        Evita duplicar si ya están contabilizadas.
        """
        proposal = self.calculate_depreciation_proposal(client_id, year)
        
        if not proposal:
            return {"status": "ok", "message": "No hay activos para amortizar este año o las cuotas son 0.", "total_amount": 0.0}

        # Comprobar si ya existe un asiento de amortización este año
        from app.domain.services.ledger_service import LedgerService
        from app.adapters.memory.memory import _get_connection
        from app.utils.encryption import encryptor
        
        # Buscar si hay un asiento con el concepto de amortización para este año
        already_recorded = False
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT concept, entry_date FROM journal_entries WHERE entry_date = ?", (f"31/12/{year}",))
            rows = cursor.fetchall()
            for r in rows:
                concept = encryptor.decrypt(r["concept"])
                if f"Amortización Inmovilizado - Ejercicio {year}" in concept:
                    already_recorded = True
                    break

        if already_recorded:
            return {"status": "warning", "message": f"Las amortizaciones del ejercicio {year} ya estaban contabilizadas.", "total_amount": 0.0}

        apuntes = []
        total_amortization = 0.0
        for p in proposal:
            amount = p["amount"]
            total_amortization += amount
            # Debe: 681 (Gasto)
            apuntes.append({
                "account_code": p["account_debe"],
                "debe": amount,
                "haber": 0.0
            })
            # Haber: 281 (Amortización acumulada)
            apuntes.append({
                "account_code": p["account_haber"],
                "debe": 0.0,
                "haber": amount
            })
            
        if not apuntes:
            return {"status": "ok", "message": "No hay cuotas válidas para amortizar.", "total_amount": 0.0}

        # Contabilizar el asiento agrupado
        concept = f"Amortización Inmovilizado - Ejercicio {year}"
        date_str = f"31/12/{year}"
        
        try:
            journal_id = LedgerService.record_manual_entry(date_str, concept, apuntes)
            return {
                "status": "ok", 
                "message": f"Amortización contabilizada correctamente. Total: {total_amortization:.2f} €",
                "journal_id": journal_id,
                "total_amount": total_amortization
            }
        except Exception as e:
            return {"status": "error", "message": f"Error al contabilizar: {str(e)}", "total_amount": 0.0}

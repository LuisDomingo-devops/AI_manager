from typing import List, Dict, Any, Optional
from app.domain.ports.asset_repository_port import AssetRepositoryPort
from app.domain.services.asset_depreciation_engine import AssetDepreciationEngine


class DepreciationService:
    """Adaptador de compatibilidad para el servicio de amortizaciones contables."""

    def __init__(self, repository: Optional[AssetRepositoryPort] = None):
        self.repository = repository
        self.engine = AssetDepreciationEngine()

    def calculate_depreciation_proposal(self, client_id: str, year: int) -> List[Dict[str, Any]]:
        """
        Calcula la propuesta de cuotas de amortización del año natural para todos los activos del cliente.
        Aplica prorrata mensual si el activo se adquirió durante el año consultado.
        """
        proposals = self.engine.calculate_depreciation_proposal(client_id, year)
        return [
            {
                "asset_id": p.asset_id,
                "asset_name": p.asset_name,
                "account_debe": p.account_debe,
                "account_haber": p.account_haber,
                "amount": float(p.quota_amount),
                "concept": p.concept
            }
            for p in proposals
        ]

    def record_depreciation_entries(self, client_id: str, year: int) -> Dict[str, Any]:
        """
        Calcula las cuotas de amortización para el año y las registra en el Libro Diario legal.
        Garantiza idempotencia y cálculo en Decimal estricto.
        """
        res = self.engine.record_depreciation_entries(client_id, year)
        return {
            "status": res.status,
            "message": res.message,
            "journal_id": res.journal_entry_id,
            "total_amount": float(res.total_amount_amortized)
        }

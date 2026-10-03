"""
Puerto formal de contrato para el servicio del Modelo 180.
Declaración Informativa Anual de Retenciones e Ingresos a Cuenta sobre Arrendamiento de Inmuebles Urbanos.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.domain.models.billing import (
    DeclarantInfoDTO,
    BoeExportResultDTO,
    Model180ResultDTO,
    Model180ReconciliationDTO,
    TaxDeclarationAuditDTO
)


class IModel180Service(ABC):
    """
    Contrato que debe satisfacer el servicio del Modelo 180 en Alfonso AI Konta.
    """

    @abstractmethod
    def calculate_model_180(
        self,
        fiscal_year: int,
        tenant_id: str = "default",
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Model180ResultDTO:
        """
        Calcula la declaración informativa anual del Modelo 180 consolidando las facturas
        recibidas de arrendamiento de inmuebles urbanos con retención del ejercicio.
        """
        pass

    @abstractmethod
    def reconcile_with_model_115(
        self,
        fiscal_year: int,
        model_180_result: Model180ResultDTO,
        quarterly_115_declarations: Optional[List[Any]] = None,
        tenant_id: str = "default"
    ) -> Model180ReconciliationDTO:
        """
        Cruza las retenciones declaradas en el Modelo 180 contra el sumatorio de los cuatro
        trimestres del Modelo 115 (1T + 2T + 3T + 4T).
        Valida que abs(sum_180 - sum_115) <= 0.05 euros para absorber redondeos de céntimos.
        """
        pass

    @abstractmethod
    def export_model_180_boe(
        self,
        model_data: Model180ResultDTO,
        declarant_info: DeclarantInfoDTO
    ) -> BoeExportResultDTO:
        """
        Genera el fichero posicional oficial BOE (.ses) de exactamente 500 caracteres por línea,
        con un Registro Tipo 1 (Declarante) y N Registros Tipo 2 (Perceptor e Inmueble con Ref. Catastral).
        """
        pass

    @abstractmethod
    def file_and_custody_model_180(
        self,
        model_data: Model180ResultDTO,
        declarant_info: DeclarantInfoDTO,
        tenant_id: str = "default",
        filing_status: str = "CALCULATED",
        aeat_csv: Optional[str] = None
    ) -> TaxDeclarationAuditDTO:
        """
        Exporta el fichero BOE oficial, calcula el hash SHA-256 y lo custodia de forma inmutable
        en tax_declarations_ledger durante el plazo legal obligatorio de 5 años (Art. 29.2 LGT).
        """
        pass

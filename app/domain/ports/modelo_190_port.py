"""
Puerto formal de contrato para el servicio del Modelo 190.
Declaración Informativa Anual de Retenciones e Ingresos a Cuenta del IRPF.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.domain.models.billing import (
    DeclarantInfoDTO,
    BoeExportResultDTO,
    Model190ResultDTO,
    Model190ReconciliationDTO,
    TaxDeclarationAuditDTO
)


class IModel190Service(ABC):
    """
    Contrato que debe satisfacer el servicio del Modelo 190.
    """

    @abstractmethod
    def calculate_model_190(
        self,
        fiscal_year: int,
        tenant_id: str = "default",
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Model190ResultDTO:
        """
        Calcula la declaración anual consolidando nóminas y facturas de profesionales del año natural.
        """
        pass

    @abstractmethod
    def reconcile_with_model_111(
        self,
        fiscal_year: int,
        model_190_result: Model190ResultDTO,
        quarterly_111_declarations: Optional[List[Any]] = None,
        tenant_id: str = "default"
    ) -> Model190ReconciliationDTO:
        """
        Cruza las retenciones declaradas en el Modelo 190 contra el sumatorio de los cuatro trimestres del Modelo 111.
        """
        pass

    @abstractmethod
    def export_model_190_boe(
        self,
        model_data: Model190ResultDTO,
        declarant_info: DeclarantInfoDTO
    ) -> BoeExportResultDTO:
        """
        Genera el fichero posicional oficial BOE (.ses) de exactamente 500 caracteres por línea (Tipo 1 y Tipo 2).
        """
        pass

    @abstractmethod
    def file_and_custody_model_190(
        self,
        model_data: Model190ResultDTO,
        declarant_info: DeclarantInfoDTO,
        tenant_id: str = "default"
    ) -> TaxDeclarationAuditDTO:
        """
        Exporta el fichero BOE, calcula su hash SHA-256 y lo custodia en tax_declarations_ledger con 5 años de retención mínima.
        """
        pass

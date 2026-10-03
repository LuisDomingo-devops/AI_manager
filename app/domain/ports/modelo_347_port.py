"""
Puerto formal de contrato para el servicio del Modelo 347.
Declaración Informativa Anual de Operaciones con Terceras Personas superiores a 3.005,06 €.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.domain.models.billing import (
    DeclarantInfoDTO,
    BoeExportResultDTO,
    TaxDeclarationAuditDTO,
    Model347ResultDTO,
    Model347ReconciliationDTO
)


class IModel347Service(ABC):
    """
    Contrato que debe satisfacer el servicio del Modelo 347 en Alfonso AI Konta.
    """

    @abstractmethod
    def calculate_model_347(
        self,
        fiscal_year: int,
        tenant_id: str = "default",
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Model347ResultDTO:
        """
        Calcula la declaración informativa anual del Modelo 347 auditando todas las facturas
        de ventas y compras del ejercicio, agrupando por NIF y clave A o B, descartando a quienes
        no superen los 3.005,06 €, desglosando el devengo en 1T, 2T, 3T, 4T e identificando cobros en metálico > 6.000 €.
        """
        pass

    @abstractmethod
    def audit_and_reconcile_model_347(
        self,
        fiscal_year: int,
        model_347_result: Model347ResultDTO,
        tenant_id: str = "default"
    ) -> Model347ReconciliationDTO:
        """
        Audita la concordancia matemática estricta de los registros declarados:
        Verifica que 1T + 2T + 3T + 4T coincida con el total anual con tolerancia máxima de 0.05 €,
        y comprueba que ningún declarado tenga un volumen anual inferior o igual al umbral legal.
        """
        pass

    @abstractmethod
    def export_model_347_boe(
        self,
        model_data: Model347ResultDTO,
        declarant_info: DeclarantInfoDTO
    ) -> BoeExportResultDTO:
        """
        Genera el fichero posicional plano oficial BOE (.ses) de exactamente 500 caracteres por línea,
        con un Registro Tipo 1 (Declarante) y N Registros Tipo 2 (Declarados).
        """
        pass

    @abstractmethod
    def file_and_custody_model_347(
        self,
        model_data: Model347ResultDTO,
        declarant_info: DeclarantInfoDTO,
        tenant_id: str = "default",
        filing_status: str = "CALCULATED",
        aeat_csv: Optional[str] = None
    ) -> TaxDeclarationAuditDTO:
        """
        Exporta el fichero BOE oficial, calcula el hash SHA-256 y lo custodia inalterablemente
        en tax_declarations_ledger durante el plazo legal obligatorio de 5 años (Art. 29.2 LGT).
        """
        pass

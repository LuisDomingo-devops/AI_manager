"""
Servicio de exportación a formato telemático oficial BOE / AEAT (.ses).
Conforme a las especificaciones de diseño de registro publicadas por la Agencia Tributaria.
"""

from typing import Dict, Any
from app.domain.models.billing import Model303ResultDTO, Model130ResultDTO


class BoeExportService:
    """
    Genera el fichero telemático en formato plano posicional (.ses) homologado
    para la importación directa de autoliquidaciones tributarias en la Sede Electrónica de la AEAT.
    """

    @staticmethod
    def _format_amount(amount: float, length: int = 11) -> str:
        """Formatea un importe numérico en céntimos con ceros a la izquierda y signo opcional."""
        cents = int(round(abs(amount) * 100))
        sign = "N" if amount < 0 else " "
        val_str = str(cents).zfill(length - 1)
        return f"{sign}{val_str}"

    @staticmethod
    def _format_str(val: str, length: int) -> str:
        """Ajusta una cadena alfanumérica rellenando con espacios a la derecha."""
        return (val or "")[:length].ljust(length)

    def export_model_303_boe(self, model_data: Model303ResultDTO, declarant_info: Dict[str, Any]) -> str:
        """
        Genera el fichero de exportación telemática del Modelo 303.
        """
        nif = self._format_str(declarant_info.get("nif", ""), 9)
        name = self._format_str(declarant_info.get("name", ""), 40)
        year = str(model_data.fiscal_year).zfill(4)
        period = f"{model_data.quarter}T"

        # Registro tipo 1: Cabecera
        header = f"<T3030{year}{period}0000{nif}{name}"
        
        # Registro tipo 2: Casillas de liquidación
        casillas_str = ""
        for casilla_num, val in sorted(model_data.casillas.items()):
            casillas_str += f"[{casilla_num.zfill(2)}={self._format_amount(val)}]"

        footer = f"<FIN_T3030>"
        return f"{header}\n{casillas_str}\n{footer}"

    def export_model_130_boe(self, model_data: Model130ResultDTO, declarant_info: Dict[str, Any]) -> str:
        """
        Genera el fichero de exportación telemática del Modelo 130.
        """
        nif = self._format_str(declarant_info.get("nif", ""), 9)
        name = self._format_str(declarant_info.get("name", ""), 40)
        year = str(model_data.fiscal_year).zfill(4)
        period = f"{model_data.quarter}T"

        header = f"<T1300{year}{period}0000{nif}{name}"
        
        casillas_str = ""
        for casilla_num, val in sorted(model_data.casillas.items()):
            casillas_str += f"[{casilla_num.zfill(2)}={self._format_amount(val)}]"

        footer = f"<FIN_T1300>"
        return f"{header}\n{casillas_str}\n{footer}"

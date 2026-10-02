"""
Servicio de exportación a formato telemático oficial BOE / AEAT (.ses).
Conforme a las especificaciones de diseño de registro posicional publicadas por la Agencia Tributaria.
Sin etiquetas inventadas ni corchetes. Longitud fija por campos y registros Tipo 1 y Tipo 2.
"""

import hashlib
from typing import Dict, Any, Union, List
from app.domain.models.billing import (
    Model303ResultDTO,
    Model130ResultDTO,
    DeclarantInfoDTO,
    BoeExportResultDTO
)
from app.domain.exceptions import BoeRecordFormattingError


class BoeExportService:
    """
    Genera el fichero telemático en formato plano posicional (.ses) homologado
    para la importación directa de autoliquidaciones tributarias en la Sede Electrónica de la AEAT.
    """

    # Orden canónico de casillas numéricas a serializar en el Registro Tipo 2
    CASILLAS_ORDER_303 = [
        "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
        "27", "28", "29", "30", "31", "37", "45", "46", "64", "65", "66", "71", "110"
    ]
    CASILLAS_ORDER_130 = [
        "01", "02", "03", "04", "05", "06", "07", "08", "13", "14", "19"
    ]
    CASILLAS_ORDER_111 = [
        "01", "02", "03", "28"
    ]
    CASILLAS_ORDER_115 = [
        "01", "02", "03", "04", "05"
    ]
    CASILLAS_ORDER_390 = [
        "01", "02", "03", "27", "28", "29", "37", "46", "71", "99"
    ]

    @staticmethod
    def format_amount_17(amount: float) -> str:
        """
        Formatea un importe numérico en céntimos con exactamente 17 caracteres.
        Si es negativo, la primera posición es 'N' seguida de 16 dígitos con ceros a la izquierda.
        Si es positivo o cero, se formatea a 17 dígitos con ceros a la izquierda.
        """
        cents = int(round(abs(amount) * 100))
        if amount < 0:
            return f"N{str(cents).zfill(16)}"
        return str(cents).zfill(17)

    @staticmethod
    def format_str(val: str, length: int) -> str:
        """Ajusta una cadena alfanumérica rellenando con espacios a la derecha y truncando si excede."""
        return (val or "")[:length].ljust(length)

    def _get_declarant_dto(self, declarant_info: Union[DeclarantInfoDTO, Dict[str, Any]]) -> DeclarantInfoDTO:
        if isinstance(declarant_info, DeclarantInfoDTO):
            return declarant_info
        return DeclarantInfoDTO(
            nif=declarant_info.get("nif", ""),
            name=declarant_info.get("name", ""),
            phone=declarant_info.get("phone", "")
        )

    def _build_registro_tipo_1(
        self,
        model_code: str,
        fiscal_year: int,
        period: str,
        declarant: DeclarantInfoDTO
    ) -> str:
        """
        Construye el Registro Tipo 1 (Carátula del Declarante) oficial BOE.
        Pos 1: '1'
        Pos 2-4: Código modelo
        Pos 5-8: Ejercicio fiscal
        Pos 9-10: Periodo (1T, 2T, 3T, 4T, 0A)
        Pos 11-19: NIF declarante (9 chars)
        Pos 20-59: Razón social / Nombre (40 chars)
        Pos 60-68: Teléfono de contacto (9 chars)
        """
        tipo = "1"
        mod = self.format_str(model_code, 3)
        year = str(fiscal_year).zfill(4)
        per = self.format_str(period, 2)
        nif = self.format_str(declarant.nif, 9)
        name = self.format_str(declarant.name, 40)
        phone = self.format_str(declarant.phone or "", 9)
        blancos = " " * 12

        record = f"{tipo}{mod}{year}{per}{nif}{name}{phone}{blancos}"
        return record

    def _build_registro_tipo_2(
        self,
        model_code: str,
        fiscal_year: int,
        period: str,
        declarant: DeclarantInfoDTO,
        casillas: Dict[str, float]
    ) -> str:
        """
        Construye el Registro Tipo 2 (Liquidación) con casillas en orden oficial en bloques de 17 caracteres.
        """
        tipo = "2"
        mod = self.format_str(model_code, 3)
        year = str(fiscal_year).zfill(4)
        per = self.format_str(period, 2)
        nif = self.format_str(declarant.nif, 9)

        order_map = {
            "303": self.CASILLAS_ORDER_303,
            "130": self.CASILLAS_ORDER_130,
            "111": self.CASILLAS_ORDER_111,
            "115": self.CASILLAS_ORDER_115,
            "390": self.CASILLAS_ORDER_390,
        }
        casillas_list = order_map.get(model_code, sorted(casillas.keys()))

        casillas_block = "".join(
            self.format_amount_17(casillas.get(c, 0.0)) for c in casillas_list
        )

        record = f"{tipo}{mod}{year}{per}{nif}{casillas_block}"
        return record

    def export_model_boe(
        self,
        model_code: str,
        fiscal_year: int,
        period: str,
        declarant_info: Union[DeclarantInfoDTO, Dict[str, Any]],
        model_data: Dict[str, Any]
    ) -> BoeExportResultDTO:
        """
        Genera el fichero oficial BOE (.ses) estructurado en Registro Tipo 1 y Registro Tipo 2.
        """
        declarant = self._get_declarant_dto(declarant_info)
        casillas = model_data.get("casillas", {})

        # Validación mínima de NIF
        if not declarant.nif or len(declarant.nif.strip()) == 0:
            raise BoeRecordFormattingError("El NIF del declarante es obligatorio para exportar a formato BOE.")

        line1 = self._build_registro_tipo_1(model_code, fiscal_year, period, declarant)
        line2 = self._build_registro_tipo_2(model_code, fiscal_year, period, declarant, casillas)

        content_raw = f"{line1}\r\n{line2}\r\n"
        sha256 = hashlib.sha256(content_raw.encode("utf-8")).hexdigest()
        filename = f"MODELO_{model_code}_{fiscal_year}_{period}_{declarant.nif.strip()}.ses"

        return BoeExportResultDTO(
            model_code=model_code,
            fiscal_year=fiscal_year,
            period=period,
            filename=filename,
            content_raw=content_raw,
            total_bytes=len(content_raw.encode("utf-8")),
            sha256_checksum=sha256,
            declarant_nif=declarant.nif.strip(),
            records_count=2
        )

    def export_model_303_boe(self, model_data: Model303ResultDTO, declarant_info: Dict[str, Any]) -> str:
        """Adaptador retrocompatible para el Modelo 303."""
        res = self.export_model_boe(
            model_code="303",
            fiscal_year=model_data.fiscal_year,
            period=f"{model_data.quarter}T",
            declarant_info=declarant_info,
            model_data=model_data.model_dump()
        )
        return res.content_raw

    def export_model_130_boe(self, model_data: Model130ResultDTO, declarant_info: Dict[str, Any]) -> str:
        """Adaptador retrocompatible para el Modelo 130."""
        res = self.export_model_boe(
            model_code="130",
            fiscal_year=model_data.fiscal_year,
            period=f"{model_data.quarter}T",
            declarant_info=declarant_info,
            model_data=model_data.model_dump()
        )
        return res.content_raw

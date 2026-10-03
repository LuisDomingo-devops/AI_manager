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
    Model190ResultDTO,
    Model190PerceptorDTO,
    Model180ResultDTO,
    Model180PerceptorDTO,
    Model347ResultDTO,
    Model347DeclaredDTO,
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
    def format_amount_13(amount: float) -> str:
        """
        Formatea un importe numérico en céntimos con exactamente 13 caracteres (11 enteros + 2 decimales).
        Relleno con ceros a la izquierda sin separador decimal ni signos.
        """
        cents = int(round(abs(amount or 0.0) * 100))
        return str(cents).zfill(13)[:13]

    @staticmethod
    def format_amount_15(amount: float) -> str:
        """
        Formatea un importe numérico en céntimos con exactamente 15 caracteres (13 enteros + 2 decimales).
        Relleno con ceros a la izquierda sin separador decimal ni signos.
        """
        cents = int(round(abs(amount or 0.0) * 100))
        return str(cents).zfill(15)[:15]

    @staticmethod
    def format_amount_16_signed(amount: float) -> str:
        """
        Formatea un importe numérico con signo reglamentario en exactamente 16 caracteres:
        Posición 1: ' ' si es positivo o cero, 'N' si es negativo.
        Posiciones 2 a 16: 15 dígitos con ceros a la izquierda (13 enteros + 2 decimales sin coma).
        """
        cents = int(round(abs(amount or 0.0) * 100))
        sign = "N" if (amount or 0.0) < 0 else " "
        return f"{sign}{str(cents).zfill(15)[:15]}"


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

        # Validación mínima de NIF
        if not declarant.nif or len(declarant.nif.strip()) == 0:
            raise BoeRecordFormattingError("El NIF del declarante es obligatorio para exportar a formato BOE.")

        if model_code == "180":
            return self.export_model_180_boe(model_data, declarant)

        if model_code == "347":
            return self.export_model_347_boe(model_data, declarant)

        casillas = model_data.get("casillas", {}) if isinstance(model_data, dict) else getattr(model_data, "casillas", {})



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

    def _build_registro_tipo_1_190(
        self,
        model_data: Model190ResultDTO,
        declarant: DeclarantInfoDTO
    ) -> str:
        """
        Construye el Registro Tipo 1 (Carátula del Declarante) oficial BOE para el Modelo 190.
        Exactamente 500 caracteres ASCII conforme a la Orden EHA/3127/2009.
        """
        tipo = "1"
        mod = "190"
        year = str(model_data.fiscal_year).zfill(4)
        nif = self.format_str(declarant.nif, 9)
        name = self.format_str(declarant.name, 40)
        soporte = "T"
        phone = self.format_str(declarant.phone or "", 9)
        contact = self.format_str(declarant.contact_person or declarant.name, 40)
        num_ident = f"190{year}000001"[:13].zfill(13)
        tipo_decl = "C" if getattr(declarant, "is_complementary", False) else " "
        num_anterior = self.format_str(getattr(declarant, "previous_receipt_number", None) or "0" * 13, 13)
        num_perceptores = str(model_data.total_perceptores).zfill(9)[:9]
        total_percepciones = self.format_amount_15(model_data.total_percepciones_global)
        total_retenciones = self.format_amount_15(model_data.total_retenciones_practicadas)
        blancos = " " * 327

        record = (
            f"{tipo}{mod}{year}{nif}{name}{soporte}{phone}{contact}"
            f"{num_ident}{tipo_decl}{num_anterior}{num_perceptores}"
            f"{total_percepciones}{total_retenciones}{blancos}"
        )
        if len(record) != 500:
            raise BoeRecordFormattingError(
                f"Longitud inválida para Registro Tipo 1 Modelo 190: se esperaban 500 chars, generado {len(record)}"
            )
        return record

    def _build_registro_tipo_2_190(
        self,
        perceptor: Model190PerceptorDTO,
        fiscal_year: int,
        declarant_nif: str
    ) -> str:
        """
        Construye el Registro Tipo 2 (Detalle del Perceptor) oficial BOE para el Modelo 190.
        Exactamente 500 caracteres ASCII conforme a la Orden EHA/3127/2009.
        """
        tipo = "2"
        mod = "190"
        year = str(fiscal_year).zfill(4)
        decl_nif = self.format_str(declarant_nif, 9)
        perc_nif = self.format_str(perceptor.nif, 9)
        rep_nif = self.format_str(perceptor.representative_nif or "", 9)
        name = self.format_str(perceptor.name, 40)
        prov = self.format_str(perceptor.province_code or "28", 2)
        clave = self.format_str(perceptor.clave, 1)
        subclave = self.format_str(perceptor.subclave or "  ", 2)
        din = self.format_amount_13(perceptor.percepciones_dinerarias)
        ret = self.format_amount_13(perceptor.retenciones_practicadas)
        esp_val = self.format_amount_13(perceptor.percepciones_especie_valoracion)
        esp_ing = self.format_amount_13(perceptor.percepciones_especie_ingresos_a_cuenta)
        esp_rep = self.format_amount_13(perceptor.percepciones_especie_repercutidos)
        devengo = str(perceptor.ejercicio_devengo or 0).zfill(4)[:4]
        disc = str(perceptor.discapacidad or 0)[:1]
        contrato = str(perceptor.tipo_contrato or 0)[:1]
        red = str(perceptor.reducciones_aplicables or 0)[:1]
        nac = str(perceptor.ano_nacimiento or 0).zfill(4)[:4]
        sit_fam = str(perceptor.situacion_familiar or 0)[:1]
        cony_nif = self.format_str(perceptor.conyuge_nif or "", 9)
        cony_disc = str(perceptor.conyuge_discapacidad or 0)[:1]
        hijos = str(perceptor.num_hijos or 0).zfill(2)[:2]
        hijos_disc = str(perceptor.num_hijos_discapacidad or 0).zfill(2)[:2]
        asc = str(perceptor.num_ascendientes or 0).zfill(2)[:2]
        blancos = " " * 327

        record = (
            f"{tipo}{mod}{year}{decl_nif}{perc_nif}{rep_nif}{name}{prov}"
            f"{clave}{subclave}{din}{ret}{esp_val}{esp_ing}{esp_rep}"
            f"{devengo}{disc}{contrato}{red}{nac}{sit_fam}{cony_nif}"
            f"{cony_disc}{hijos}{hijos_disc}{asc}{blancos}"
        )
        if len(record) != 500:
            raise BoeRecordFormattingError(
                f"Longitud inválida para Registro Tipo 2 Modelo 190: se esperaban 500 chars, generado {len(record)}"
            )
        return record

    def export_model_190_boe(
        self,
        model_data: Model190ResultDTO,
        declarant_info: Union[DeclarantInfoDTO, Dict[str, Any]]
    ) -> BoeExportResultDTO:
        """
        Genera el fichero oficial BOE (.ses) del Modelo 190 conforme a la Orden EHA/3127/2009.
        Estructurado en un Registro Tipo 1 y N Registros Tipo 2 (uno por cada perceptor).
        """
        declarant = self._get_declarant_dto(declarant_info)

        if not declarant.nif or len(declarant.nif.strip()) == 0:
            raise BoeRecordFormattingError("El NIF del declarante es obligatorio para exportar el Modelo 190 a BOE.")

        tipo_1 = self._build_registro_tipo_1_190(model_data, declarant)
        lines = [tipo_1]

        for perceptor in model_data.perceptores:
            lines.append(self._build_registro_tipo_2_190(perceptor, model_data.fiscal_year, declarant.nif))

        content_raw = "\r\n".join(lines) + "\r\n"
        encoded = content_raw.encode("utf-8")
        sha256 = hashlib.sha256(encoded).hexdigest()
        filename = f"MODELO_190_{model_data.fiscal_year}_0A_{declarant.nif.strip()}.ses"

        return BoeExportResultDTO(
            model_code="190",
            fiscal_year=model_data.fiscal_year,
            period="0A",
            filename=filename,
            content_raw=content_raw,
            total_bytes=len(encoded),
            sha256_checksum=sha256,
            declarant_nif=declarant.nif.strip(),
            records_count=len(lines)
        )

    def _build_registro_tipo_1_180(
        self,
        model_data: Model180ResultDTO,
        declarant: DeclarantInfoDTO
    ) -> str:
        """
        Construye el Registro Tipo 1 (Carátula del Declarante) oficial BOE para el Modelo 180.
        Exactamente 500 caracteres conforme a la Orden EHA/3895/2004 y HFP/1395/2021.
        """
        tipo = "1"
        mod = "180"
        year = str(model_data.fiscal_year).zfill(4)
        nif = self.format_str(declarant.nif, 9)
        name = self.format_str(declarant.name, 40)
        soporte = "T"
        phone = self.format_str(declarant.phone or "", 9)
        contact = self.format_str(declarant.contact_person or declarant.name, 40)
        num_ident = f"180{year}000001"[:13].zfill(13)
        tipo_decl = "C" if getattr(declarant, "is_complementary", False) else " "
        num_anterior = self.format_str(getattr(declarant, "previous_receipt_number", None) or "0" * 13, 13)
        num_perceptores = str(model_data.total_perceptores).zfill(9)[:9]
        total_base = self.format_amount_15(model_data.total_base_retenciones)
        total_retenciones = self.format_amount_15(model_data.total_retenciones_practicadas)
        blancos = " " * 327

        record = (
            f"{tipo}{mod}{year}{nif}{name}{soporte}{phone}{contact}"
            f"{num_ident}{tipo_decl}{num_anterior}{num_perceptores}"
            f"{total_base}{total_retenciones}{blancos}"
        )
        if len(record) != 500:
            raise BoeRecordFormattingError(
                f"Longitud inválida para Registro Tipo 1 Modelo 180: se esperaban 500 chars, generado {len(record)}"
            )
        return record

    def _build_registro_tipo_2_180(
        self,
        perceptor: Model180PerceptorDTO,
        fiscal_year: int,
        declarant_nif: str
    ) -> str:
        """
        Construye el Registro Tipo 2 (Detalle de Perceptor e Inmueble) oficial BOE para el Modelo 180.
        Exactamente 500 caracteres conforme a la Orden EHA/3895/2004 y HFP/1395/2021.
        """
        tipo = "2"
        mod = "180"
        year = str(fiscal_year).zfill(4)
        decl_nif = self.format_str(declarant_nif, 9)
        perc_nif = self.format_str(perceptor.nif, 9)
        name = self.format_str(perceptor.name, 40)

        inmueble = perceptor.inmueble
        prov = self.format_str(inmueble.codigo_provincia if inmueble else "28", 2)
        reservado_1 = " " * 13

        base = self.format_amount_13(perceptor.base_retencion)
        pct_val = int(round(abs(perceptor.porcentaje_retencion or 19.0) * 100))
        pct = str(pct_val).zfill(13)[:13]
        ret = self.format_amount_13(perceptor.retencion_practicada)

        reservado_2 = " " * 93

        sit = str(inmueble.situacion_inmueble if inmueble else 1)[:1]
        if inmueble and inmueble.situacion_inmueble in (1, 2) and inmueble.referencia_catastral:
            ref_cat = self.format_str(inmueble.referencia_catastral, 20)
        else:
            ref_cat = " " * 20

        tipo_via = self.format_str(inmueble.tipo_via if inmueble else "CL", 5)
        nombre_via = self.format_str(inmueble.nombre_via if inmueble else "", 50)
        numero = self.format_str(inmueble.numero if inmueble else "", 5)
        municipio = self.format_str(inmueble.municipio if inmueble else "", 30)
        cp = self.format_str(inmueble.codigo_postal if inmueble else "", 5)

        blancos_final = " " * 171

        record = (
            f"{tipo}{mod}{year}{decl_nif}{perc_nif}{name}{prov}"
            f"{reservado_1}{base}{pct}{ret}{reservado_2}{sit}{ref_cat}"
            f"{tipo_via}{nombre_via}{numero}{municipio}{cp}{blancos_final}"
        )
        if len(record) != 500:
            raise BoeRecordFormattingError(
                f"Longitud inválida para Registro Tipo 2 Modelo 180: se esperaban 500 chars, generado {len(record)}"
            )
        return record

    def export_model_180_boe(
        self,
        model_data: Union[Model180ResultDTO, Dict[str, Any]],
        declarant_info: Union[DeclarantInfoDTO, Dict[str, Any]]
    ) -> BoeExportResultDTO:
        """
        Genera el fichero oficial BOE (.ses) del Modelo 180 conforme a la Orden EHA/3895/2004.
        Estructurado en un Registro Tipo 1 y N Registros Tipo 2 (uno por cada perceptor/inmueble).
        """
        declarant = self._get_declarant_dto(declarant_info)
        if isinstance(model_data, dict):
            model_data = Model180ResultDTO(**model_data)

        if not declarant.nif or len(declarant.nif.strip()) == 0:
            raise BoeRecordFormattingError("El NIF del declarante es obligatorio para exportar el Modelo 180 a BOE.")

        tipo_1 = self._build_registro_tipo_1_180(model_data, declarant)
        lines = [tipo_1]

        for perceptor in model_data.perceptores:
            lines.append(self._build_registro_tipo_2_180(perceptor, model_data.fiscal_year, declarant.nif))

        content_raw = "\r\n".join(lines) + "\r\n"
        encoded = content_raw.encode("utf-8")
        sha256 = hashlib.sha256(encoded).hexdigest()
        filename = f"MODELO_180_{model_data.fiscal_year}_0A_{declarant.nif.strip()}.ses"

        return BoeExportResultDTO(
            model_code="180",
            fiscal_year=model_data.fiscal_year,
            period="0A",
            filename=filename,
            content_raw=content_raw,
            total_bytes=len(encoded),
            sha256_checksum=sha256,
            declarant_nif=declarant.nif.strip(),
            records_count=len(lines)
        )

    def format_model_347_type_1(
        self,
        model_data: Model347ResultDTO,
        declarant_info: DeclarantInfoDTO
    ) -> str:
        """
        Construye el Registro Tipo 1 (Declarante) oficial BOE para el Modelo 347.
        Exactamente 500 caracteres conforme a la Orden EHA/3012/2008 y Orden HAP/2194/2013.
        """
        tipo = "1"
        mod = "347"
        year = str(model_data.fiscal_year).zfill(4)
        nif = self.format_str(declarant_info.nif, 9)
        name = self.format_str(declarant_info.name, 40)
        soporte = "T"
        phone = self.format_str(declarant_info.phone or "", 9)
        contact = self.format_str(declarant_info.contact_person or declarant_info.name, 40)
        num_ident = f"347{year}000001"[:13].zfill(13)
        tipo_decl = "C" if getattr(declarant_info, "is_complementary", False) or model_data.is_complementary else " "
        num_anterior = self.format_str(
            getattr(declarant_info, "previous_receipt_number", None) or model_data.previous_receipt_number or "0" * 13, 13
        )
        num_declarados = str(model_data.total_declared_records).zfill(9)[:9]
        total_operaciones = self.format_amount_16_signed(model_data.total_operations_amount)
        total_inmuebles = "0" * 9
        total_arrendamientos = self.format_amount_16_signed(0.0)
        blancos = " " * 316

        record = (
            f"{tipo}{mod}{year}{nif}{name}{soporte}{phone}{contact}"
            f"{num_ident}{tipo_decl}{num_anterior}{num_declarados}"
            f"{total_operaciones}{total_inmuebles}{total_arrendamientos}{blancos}"
        )
        if len(record) != 500:
            raise BoeRecordFormattingError(
                f"Longitud inválida para Registro Tipo 1 Modelo 347: se esperaban 500 chars, generado {len(record)}"
            )
        return record

    def format_model_347_type_2(
        self,
        declared: Model347DeclaredDTO,
        fiscal_year: int,
        declarant_nif: str
    ) -> str:
        """
        Construye el Registro Tipo 2 (Declarado) oficial BOE para el Modelo 347.
        Exactamente 500 caracteres con importes trimestrales y cobros en metálico.
        """
        tipo = "2"
        mod = "347"
        year = str(fiscal_year).zfill(4)
        decl_nif = self.format_str(declarant_nif, 9)
        decl_pers_nif = self.format_str(declared.nif, 9)
        rep_legal = " " * 9
        name = self.format_str(declared.name, 40)
        tipo_hoja = "D"
        prov = self.format_str(declared.province_code or "99", 2)
        clave_op = self.format_str(declared.operation_key, 1)

        total_anual = self.format_amount_16_signed(declared.total_annual_amount)
        op_seguro = " "
        q1 = self.format_amount_16_signed(declared.quarter_1_amount)
        q2 = self.format_amount_16_signed(declared.quarter_2_amount)
        q3 = self.format_amount_16_signed(declared.quarter_3_amount)
        q4 = self.format_amount_16_signed(declared.quarter_4_amount)
        metalico = self.format_amount_16_signed(declared.cash_amount)
        transmisiones_inm = self.format_amount_16_signed(0.0)
        ejercicio_metalico = " " * 4
        criterio_caja_imp = self.format_amount_16_signed(0.0)
        marca_recc = "X" if declared.is_cash_basis_recc else " "
        marca_isp = "X" if declared.is_reverse_charge else " "
        blancos_final = " " * 286

        record = (
            f"{tipo}{mod}{year}{decl_nif}{decl_pers_nif}{rep_legal}{name}"
            f"{tipo_hoja}{prov}{clave_op}{total_anual}{op_seguro}"
            f"{q1}{q2}{q3}{q4}{metalico}{transmisiones_inm}"
            f"{ejercicio_metalico}{criterio_caja_imp}{marca_recc}{marca_isp}{blancos_final}"
        )
        if len(record) != 500:
            raise BoeRecordFormattingError(
                f"Longitud inválida para Registro Tipo 2 Modelo 347: se esperaban 500 chars, generado {len(record)}"
            )
        return record

    def export_model_347_boe(
        self,
        model_data: Union[Model347ResultDTO, Dict[str, Any]],
        declarant_info: Union[DeclarantInfoDTO, Dict[str, Any]]
    ) -> BoeExportResultDTO:
        """
        Genera el fichero oficial BOE (.ses) del Modelo 347 conforme a la Orden EHA/3012/2008.
        Estructurado en un Registro Tipo 1 (Declarante) y N Registros Tipo 2 (Declarados).
        """
        declarant = self._get_declarant_dto(declarant_info)
        if isinstance(model_data, dict):
            model_data = Model347ResultDTO(**model_data)

        if not declarant.nif or len(declarant.nif.strip()) == 0:
            raise BoeRecordFormattingError("El NIF del declarante es obligatorio para exportar el Modelo 347 a BOE.")

        tipo_1 = self.format_model_347_type_1(model_data, declarant)
        lines = [tipo_1]

        for declared in model_data.declared_records:
            lines.append(self.format_model_347_type_2(declared, model_data.fiscal_year, declarant.nif))

        content_raw = "\r\n".join(lines) + "\r\n"
        encoded = content_raw.encode("utf-8")
        sha256 = hashlib.sha256(encoded).hexdigest()
        filename = f"347_{model_data.fiscal_year}_{declarant.nif.strip()}.ses"

        return BoeExportResultDTO(
            model_code="347",
            fiscal_year=model_data.fiscal_year,
            period="0A",
            filename=filename,
            content_raw=content_raw,
            total_bytes=len(encoded),
            sha256_checksum=sha256,
            declarant_nif=declarant.nif.strip(),
            records_count=len(lines)
        )




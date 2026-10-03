from __future__ import annotations
import sqlite3
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

if TYPE_CHECKING:
    from app.domain.models.billing import (
        Model190ResultDTO,
        Model190ReconciliationDTO,
        Model190PerceptorDTO,
        Model390ResultDTO,
        Model180ResultDTO,
        Model180ReconciliationDTO,
        Model180PerceptorDTO,
        InmuebleArrendadoDTO,
        Model347ResultDTO,
        Model347DeclaredDTO,
        Model347ReconciliationDTO,
        TaxDeclarationAuditDTO
    )


class AnnualTaxAggregatorService:

    @classmethod
    def get_modelo_390_data(cls, year: int) -> Dict[str, Any]:
        """
        Consolida los datos de IVA devengado e IVA devengado deducible a nivel anual para el Modelo 390.
        """
        query = """
            SELECT category, base_imponible, iva_amount, iva_rate
            FROM invoices
            WHERE year = ?
        """
        with _get_connection() as conn:
            rows = conn.execute(query, (year,)).fetchall()

        devengado = {
            "21": {"base": 0.0, "cuota": 0.0},
            "10": {"base": 0.0, "cuota": 0.0},
            "4": {"base": 0.0, "cuota": 0.0},
            "exento": {"base": 0.0, "cuota": 0.0},
            "total_base": 0.0,
            "total_cuota": 0.0
        }
        deducible = {
            "total_base": 0.0,
            "total_cuota": 0.0
        }

        for r in rows:
            cat = r["category"]
            try:
                base = float(encryptor.decrypt(r["base_imponible"]) or 0.0)
                iva = float(encryptor.decrypt(r["iva_amount"]) or 0.0)
                rate_dec = encryptor.decrypt(r["iva_rate"])
                rate = float(rate_dec) if rate_dec else 0.0
            except Exception:
                base = iva = rate = 0.0

            if cat in ("ingreso", "income"):
                devengado["total_base"] += base
                devengado["total_cuota"] += iva
                
                # Agrupar por tipo impositivo
                rate_str = str(int(rate)) if rate > 0 else "exento"
                if rate_str in ("21", "10", "4"):
                    devengado[rate_str]["base"] += base
                    devengado[rate_str]["cuota"] += iva
                else:
                    devengado["exento"]["base"] += base
            elif cat in ("gasto", "expense"):
                deducible["total_base"] += base
                deducible["total_cuota"] += iva

        # Redondear resultados
        for key in ("21", "10", "4", "exento"):
            devengado[key]["base"] = round(devengado[key]["base"], 2)
            devengado[key]["cuota"] = round(devengado[key]["cuota"], 2)

        devengado["total_base"] = round(devengado["total_base"], 2)
        devengado["total_cuota"] = round(devengado["total_cuota"], 2)
        deducible["total_base"] = round(deducible["total_base"], 2)
        deducible["total_cuota"] = round(deducible["total_cuota"], 2)

        resultado = round(devengado["total_cuota"] - deducible["total_cuota"], 2)

        return {
            "year": year,
            "devengado": devengado,
            "deducible": deducible,
            "resultado": resultado,
            # Compatibilidad con los asserts del test del proyecto
            "operaciones_interiores_devengadas_base": devengado["total_base"],
            "operaciones_interiores_deducibles_base": deducible["total_base"]
        }

    @classmethod
    def get_modelo_190_data(cls, year: int) -> Dict[str, Any]:
        """
        Consolida las retenciones anuales de IRPF de trabajadores (Clave A), profesionales (Clave G)
        y demás percepciones regulatorias para el Modelo 190.
        """
        perceptores = {}

        # 1. Rendimientos del Trabajo (Clave A) desde las Nóminas
        query_payrolls = """
            SELECT employee_id, gross_total, irpf_amount,
                   coalesce(in_kind_valuation, 0.0) as in_kind_val,
                   coalesce(in_kind_on_account, 0.0) as in_kind_acc
            FROM payrolls
            WHERE year = ?
        """
        with _get_connection() as conn:
            conn.row_factory = sqlite3.Row if hasattr(sqlite3, "Row") else None
            try:
                payrolls = conn.execute(query_payrolls, (year,)).fetchall()
            except Exception:
                # Fallback por si columnas de especie no existen en versiones legacy
                payrolls = conn.execute(
                    "SELECT employee_id, gross_total, irpf_amount FROM payrolls WHERE year = ?",
                    (year,)
                ).fetchall()

            for p in payrolls:
                emp_id = p["employee_id"]
                gross = float(p["gross_total"] or 0.0)
                irpf = float(p["irpf_amount"] or 0.0)
                in_kind_val = float(p["in_kind_val"] if "in_kind_val" in p.keys() else 0.0)
                in_kind_acc = float(p["in_kind_acc"] if "in_kind_acc" in p.keys() else 0.0)

                # Buscar datos del empleado
                emp_row = conn.execute(
                    "SELECT * FROM employees WHERE id = ?",
                    (emp_id,)
                ).fetchone()

                if not emp_row:
                    continue

                try:
                    nif = encryptor.decrypt(emp_row["nif_encrypted"])
                    name = encryptor.decrypt(emp_row["full_name_encrypted"])
                except Exception:
                    continue

                spouse_nif = None
                if "spouse_nif_encrypted" in emp_row.keys() and emp_row["spouse_nif_encrypted"]:
                    try:
                        spouse_nif = encryptor.decrypt(emp_row["spouse_nif_encrypted"])
                    except Exception:
                        spouse_nif = None

                birth_year = emp_row["birth_year"] if "birth_year" in emp_row.keys() and emp_row["birth_year"] else 1985
                family_situation = emp_row["family_situation"] if "family_situation" in emp_row.keys() and emp_row["family_situation"] else 3
                num_descendants = emp_row["num_descendants"] if "num_descendants" in emp_row.keys() and emp_row["num_descendants"] else 0
                disability_grade = emp_row["disability_grade"] if "disability_grade" in emp_row.keys() and emp_row["disability_grade"] else 0

                if nif not in perceptores:
                    perceptores[nif] = {
                        "nif": nif,
                        "name": name,
                        "clave": "A",
                        "subclave": "  ",
                        "percepciones": 0.0,
                        "retenciones": 0.0,
                        "percepciones_especie_valoracion": 0.0,
                        "percepciones_especie_ingresos_a_cuenta": 0.0,
                        "percepciones_especie_repercutidos": 0.0,
                        "ano_nacimiento": birth_year,
                        "situacion_familiar": family_situation,
                        "conyuge_nif": spouse_nif,
                        "num_hijos": num_descendants,
                        "discapacidad": disability_grade
                    }

                perceptores[nif]["percepciones"] += gross
                perceptores[nif]["retenciones"] += irpf
                perceptores[nif]["percepciones_especie_valoracion"] += in_kind_val
                perceptores[nif]["percepciones_especie_ingresos_a_cuenta"] += in_kind_acc
                perceptores[nif]["percepciones_especie_repercutidos"] += in_kind_acc

        # 2. Rendimientos Profesionales (Clave G) y demás claves desde Facturas de Gasto
        query_expenses = """
            SELECT * FROM invoices
            WHERE year = ? AND category IN ('gasto', 'expense')
        """
        with _get_connection() as conn:
            conn.row_factory = sqlite3.Row if hasattr(sqlite3, "Row") else None
            expenses = conn.execute(query_expenses, (year,)).fetchall()

        for exp in expenses:
            try:
                irpf = float(encryptor.decrypt(exp["irpf_amount"]) or 0.0)
                base = float(encryptor.decrypt(exp["base_imponible"]) or 0.0)
            except Exception:
                irpf = base = 0.0

            # Solo facturas con retención
            if irpf > 0:
                try:
                    nif = encryptor.decrypt(exp["issuer_nif"])
                    name = encryptor.decrypt(exp["issuer_name"])
                except Exception:
                    continue

                # Determinar clave y subclave
                clave = "G"
                if "retention_clave" in exp.keys() and exp["retention_clave"]:
                    clave = exp["retention_clave"].strip().upper()

                subclave = "01"
                if "retention_subclave" in exp.keys() and exp["retention_subclave"]:
                    subclave = exp["retention_subclave"].strip().zfill(2)
                else:
                    # Determinar por tipo impositivo de retención
                    try:
                        rate_dec = encryptor.decrypt(exp["irpf_rate"])
                        rate_val = float(rate_dec) if rate_dec else 15.0
                    except Exception:
                        rate_val = 15.0
                    if rate_val <= 10.0:
                        subclave = "02"  # Reducido inicio actividad (7%)
                    else:
                        subclave = "01"  # General (15%)

                pk_perceptor = f"{nif}_{clave}_{subclave}"
                if pk_perceptor not in perceptores:
                    perceptores[pk_perceptor] = {
                        "nif": nif,
                        "name": name,
                        "clave": clave,
                        "subclave": subclave,
                        "percepciones": 0.0,
                        "retenciones": 0.0,
                        "percepciones_especie_valoracion": 0.0,
                        "percepciones_especie_ingresos_a_cuenta": 0.0,
                        "percepciones_especie_repercutidos": 0.0,
                        "ano_nacimiento": 0,
                        "situacion_familiar": 0,
                        "conyuge_nif": None,
                        "num_hijos": 0,
                        "discapacidad": 0
                    }
                perceptores[pk_perceptor]["percepciones"] += base
                perceptores[pk_perceptor]["retenciones"] += irpf

        # Redondear y calcular totales
        perceptores_list = []
        total_percepciones_dinerarias = 0.0
        total_retenciones = 0.0
        total_especie = 0.0
        total_ingresos_acc = 0.0

        for p in perceptores.values():
            p["percepciones"] = round(p["percepciones"], 2)
            p["retenciones"] = round(p["retenciones"], 2)
            p["percepciones_especie_valoracion"] = round(p.get("percepciones_especie_valoracion", 0.0), 2)
            p["percepciones_especie_ingresos_a_cuenta"] = round(p.get("percepciones_especie_ingresos_a_cuenta", 0.0), 2)
            p["percepciones_especie_repercutidos"] = round(p.get("percepciones_especie_repercutidos", 0.0), 2)

            perceptores_list.append(p)
            total_percepciones_dinerarias += p["percepciones"]
            total_retenciones += p["retenciones"]
            total_especie += p["percepciones_especie_valoracion"]
            total_ingresos_acc += p["percepciones_especie_ingresos_a_cuenta"]

        return {
            "year": year,
            "perceptores": perceptores_list,
            "total_perceptores": len(perceptores_list),
            "total_percepciones": round(total_percepciones_dinerarias, 2),
            "total_retenciones": round(total_retenciones, 2),
            "total_percepciones_especie": round(total_especie, 2),
            "total_ingresos_a_cuenta": round(total_ingresos_acc, 2),
            "total_percepciones_global": round(total_percepciones_dinerarias + total_especie, 2)
        }

    @classmethod
    def get_modelo_180_data(cls, year: int, tenant_id: str = "default") -> Dict[str, Any]:
        """
        Consolida las facturas de gasto por arrendamiento de inmuebles urbanos con retención del ejercicio fiscal.
        Agrupa las bases y retenciones por NIF de arrendador e inmueble.
        """
        query = "SELECT * FROM invoices WHERE year = ?"
        with _get_connection() as conn:
            conn.row_factory = sqlite3.Row if hasattr(sqlite3, "Row") else None
            rows = conn.execute(query, (year,)).fetchall()

        perceptores_map: Dict[str, Dict[str, Any]] = {}
        total_base = 0.0
        total_retenciones = 0.0
        palabras_alquiler = ("alquiler", "arrendamiento", "rent", "lease", "local", "oficina")

        for r in rows:
            r_keys = r.keys() if hasattr(r, "keys") else (r.keys() if isinstance(r, dict) else [])
            cat = str(r["category"] or "").lower() if "category" in r_keys else ""
            concept = ""
            if "concept" in r_keys and r["concept"]:
                try:
                    concept = (encryptor.decrypt(r["concept"]) or "").lower()
                except Exception:
                    concept = str(r["concept"] or "").lower()

            ret_clave = ""
            if "retention_clave" in r_keys and r["retention_clave"]:
                ret_clave = str(r["retention_clave"]).strip()

            is_alquiler = (
                cat in ("alquiler", "arrendamiento", "rent", "lease")
                or ret_clave == "180"
                or any(p in concept for p in palabras_alquiler)
            )
            if not is_alquiler:
                continue
            try:
                irpf = float(encryptor.decrypt(r["irpf_amount"]) or 0.0)
                base = float(encryptor.decrypt(r["base_imponible"]) or 0.0)
            except Exception:
                irpf = base = 0.0

            if irpf <= 0 and base <= 0:
                continue

            try:
                nif = encryptor.decrypt(r["issuer_nif"])
                name = encryptor.decrypt(r["issuer_name"])
            except Exception:
                continue

            sit = int(r["inmueble_situacion"]) if "inmueble_situacion" in r_keys and r["inmueble_situacion"] is not None else 1
            ref = str(r["inmueble_ref_catastral"]).strip() if "inmueble_ref_catastral" in r_keys and r["inmueble_ref_catastral"] else None
            via = str(r["inmueble_via"]).strip() if "inmueble_via" in r_keys and r["inmueble_via"] else "CL"
            nom_via = str(r["inmueble_nombre_via"]).strip() if "inmueble_nombre_via" in r_keys and r["inmueble_nombre_via"] else "CALLE MAYOR"
            num = str(r["inmueble_numero"]).strip() if "inmueble_numero" in r_keys and r["inmueble_numero"] else "1"
            mun = str(r["inmueble_municipio"]).strip() if "inmueble_municipio" in r_keys and r["inmueble_municipio"] else "MADRID"
            cp = str(r["inmueble_codigo_postal"]).strip() if "inmueble_codigo_postal" in r_keys and r["inmueble_codigo_postal"] else "28013"
            prov = str(r["inmueble_provincia"]).strip() if "inmueble_provincia" in r_keys and r["inmueble_provincia"] else (cp[:2] if len(cp) >= 2 else "28")

            agg_key = f"{nif}_{ref or mun}"
            if agg_key not in perceptores_map:
                perceptores_map[agg_key] = {
                    "nif": nif,
                    "name": name,
                    "province_code": prov,
                    "base_retencion": 0.0,
                    "porcentaje_retencion": 19.0,
                    "retencion_practicada": 0.0,
                    "inmueble": {
                        "situacion_inmueble": sit,
                        "referencia_catastral": ref,
                        "tipo_via": via,
                        "nombre_via": nom_via,
                        "numero": num,
                        "municipio": mun,
                        "codigo_postal": cp,
                        "codigo_provincia": prov
                    }
                }

            perceptores_map[agg_key]["base_retencion"] = round(perceptores_map[agg_key]["base_retencion"] + base, 2)
            perceptores_map[agg_key]["retencion_practicada"] = round(perceptores_map[agg_key]["retencion_practicada"] + irpf, 2)
            total_base = round(total_base + base, 2)
            total_retenciones = round(total_retenciones + irpf, 2)

        perceptores_list = list(perceptores_map.values())
        return {
            "year": year,
            "perceptores": perceptores_list,
            "arrendadores": perceptores_list,
            "total_perceptores": len(perceptores_map),
            "total_arrendadores": len(perceptores_map),
            "total_base_retenciones": total_base,
            "total_bases": total_base,
            "total_retenciones_practicadas": total_retenciones,
            "total_retenciones": total_retenciones
        }

    @classmethod
    def calculate_model_180_from_perceptors(
        cls,
        fiscal_year: int,
        perceptors: List[Any],
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Any:
        """Calcula el Modelo 180 a partir de una lista explícita de perceptores e inmuebles."""
        from app.domain.models.billing import Model180ResultDTO
        total_base = round(sum(p.base_retencion for p in perceptors), 2)
        total_ret = round(sum(p.retencion_practicada for p in perceptors), 2)
        return Model180ResultDTO(
            fiscal_year=fiscal_year,
            total_perceptores=len(perceptors),
            total_base_retenciones=total_base,
            total_retenciones_practicadas=total_ret,
            perceptores=perceptors,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    @classmethod
    def calculate_model_180(
        cls,
        fiscal_year: int,
        tenant_id: str = "default",
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Any:
        """Calcula la declaración anual consolidando facturas de gasto de arrendamiento del ejercicio fiscal."""
        from app.domain.models.billing import (
            Model180ResultDTO,
            Model180PerceptorDTO,
            InmuebleArrendadoDTO
        )
        data = cls.get_modelo_180_data(year=fiscal_year, tenant_id=tenant_id)
        perceptores_dto = []
        for p in data.get("perceptores", []):
            inm_data = p["inmueble"]
            inmueble = InmuebleArrendadoDTO(
                situacion_inmueble=inm_data["situacion_inmueble"],
                referencia_catastral=inm_data["referencia_catastral"],
                tipo_via=inm_data.get("tipo_via", "CL"),
                nombre_via=inm_data.get("nombre_via", "CALLE"),
                numero=inm_data.get("numero", "1"),
                municipio=inm_data.get("municipio", "MADRID"),
                codigo_postal=inm_data.get("codigo_postal", "28013"),
                codigo_provincia=inm_data.get("codigo_provincia", "28")
            )
            perceptores_dto.append(Model180PerceptorDTO(
                nif=p["nif"],
                name=p["name"],
                province_code=p.get("province_code", "28"),
                base_retencion=p.get("base_retencion", 0.0),
                porcentaje_retencion=p.get("porcentaje_retencion", 19.0),
                retencion_practicada=p.get("retencion_practicada", 0.0),
                inmueble=inmueble
            ))

        return Model180ResultDTO(
            fiscal_year=fiscal_year,
            total_perceptores=len(perceptores_dto),
            total_base_retenciones=float(data.get("total_base_retenciones", 0.0)),
            total_retenciones_practicadas=float(data.get("total_retenciones_practicadas", 0.0)),
            perceptores=perceptores_dto,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    @classmethod
    def reconcile_with_model_115(
        cls,
        fiscal_year: int,
        model_180_result: Any,
        quarterly_115_declarations: Optional[List[Any]] = None,
        tenant_id: str = "default"
    ) -> Any:
        """
        Cruza las retenciones declaradas en el Modelo 180 contra el sumatorio de los cuatro trimestres del Modelo 115.
        Aplica un umbral de tolerancia de redondeo de hasta 0.05 €.
        """
        from app.domain.models.billing import (
            Model180ReconciliationDTO,
            Model115ResultDTO
        )
        total_180 = round(model_180_result.total_retenciones_practicadas, 2)
        q_totals = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

        if quarterly_115_declarations:
            for decl in quarterly_115_declarations:
                if isinstance(decl, Model115ResultDTO):
                    q = decl.quarter
                    val = decl.resultado_a_ingresar
                elif isinstance(decl, dict):
                    q = decl.get("quarter", 1)
                    val = decl.get("resultado_total", decl.get("resultado_a_ingresar", decl.get("casilla_05", decl.get("05", 0.0))))
                else:
                    q = getattr(decl, "quarter", 1)
                    val = getattr(decl, "resultado_a_ingresar", getattr(decl, "resultado_total", 0.0))
                if q in q_totals:
                    q_totals[q] = round(float(val), 2)
        else:
            query = """
                SELECT period, casillas_json FROM tax_declarations_ledger
                WHERE tenant_id = ? AND model_code = '115' AND fiscal_year = ?
            """
            with _get_connection() as conn:
                conn.row_factory = sqlite3.Row if hasattr(sqlite3, "Row") else None
                rows = conn.execute(query, (tenant_id, fiscal_year)).fetchall()

            import json
            for r in rows:
                p_str = r["period"]
                try:
                    q_num = int(p_str[0]) if p_str and p_str[0].isdigit() else 1
                except Exception:
                    q_num = 1
                try:
                    c_dict = json.loads(r["casillas_json"] or "{}")
                    val = float(c_dict.get("05", c_dict.get("03", c_dict.get("resultado_a_ingresar", 0.0))))
                except Exception:
                    val = 0.0
                if q_num in q_totals:
                    q_totals[q_num] = round(val, 2)

        total_115_anual = round(sum(q_totals.values()), 2)
        diff = round(abs(total_180 - total_115_anual), 2)

        is_cuadrado = diff <= 0.05
        is_tolerancia = (0.0 < diff <= 0.05)

        discrepancias = []
        if not is_cuadrado:
            discrepancias.append(
                f"Descuadre estructural entre Modelo 180 ({total_180} €) y suma de 115 trimestrales ({total_115_anual} €). "
                f"Diferencia: {diff} € excede el umbral de tolerancia de 0.05 €."
            )

        return Model180ReconciliationDTO(
            fiscal_year=fiscal_year,
            total_retenciones_180=total_180,
            total_retenciones_115_1t=q_totals[1],
            total_retenciones_115_2t=q_totals[2],
            total_retenciones_115_3t=q_totals[3],
            total_retenciones_115_4t=q_totals[4],
            total_retenciones_115_anual=total_115_anual,
            diferencia_total=diff,
            is_cuadrado=is_cuadrado,
            is_tolerancia_redondeo=is_tolerancia,
            discrepancias_detectadas=discrepancias
        )

    @classmethod
    def aggregate_invoices_for_model_347(
        cls,
        invoices: List[Dict[str, Any]],
        fiscal_year: int,
        declarant_nif: str = "B87654321",
        declarant_name: str = "INNOVACIONES TECNOLOGICAS SL",
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Any:
        """
        Agrupa facturas por NIF y clave de operación ('A' o 'B'), calcula el volumen con IVA,
        aplica el umbral legal (> 3.005,06 €), desglosa en 1T, 2T, 3T, 4T y detecta cobros en metálico > 6.000 €.
        """
        from app.domain.models.billing import Model347DeclaredDTO, Model347ResultDTO

        third_parties: Dict[tuple, Dict[str, Any]] = {}
        cash_by_client: Dict[str, float] = {}

        for inv in invoices:
            cat = str(inv.get("category", "")).lower()
            is_sales = cat in ("ingreso", "income", "venta")
            op_key = "B" if is_sales else "A"

            nif = str(inv.get("nif") or inv.get("contraparte_nif") or "").strip().upper()
            if not nif:
                continue
            name = str(inv.get("name") or inv.get("contraparte_name") or "TERCERO S.L.").strip()[:40]
            prov_code = str(inv.get("province_code") or (nif[:2] if nif[:2].isdigit() else "99"))[:2]

            base = float(inv.get("base") or inv.get("base_imponible") or 0.0)
            iva = float(inv.get("iva") or inv.get("iva_amount") or 0.0)
            recargo = float(inv.get("recargo") or inv.get("recargo_amount") or 0.0)
            retencion = float(inv.get("irpf") or inv.get("irpf_amount") or 0.0)

            total_line = round(base + iva + recargo - retencion, 2)
            q = int(inv.get("quarter", 1))
            if q not in (1, 2, 3, 4):
                q = 1

            # Detección de cobro en metálico
            pay_method = str(inv.get("payment_method", "")).lower()
            direct_cash = float(inv.get("cash_amount", 0.0))
            is_cash = direct_cash > 0.0 or pay_method in ("cash", "metalico", "efectivo")
            cash_val = direct_cash if direct_cash > 0.0 else (total_line if is_cash else 0.0)

            if is_sales and cash_val > 0.0:
                cash_by_client[nif] = round(cash_by_client.get(nif, 0.0) + cash_val, 2)

            key = (nif, op_key)
            if key not in third_parties:
                third_parties[key] = {
                    "nif": nif,
                    "name": name,
                    "province_code": prov_code,
                    "operation_key": op_key,
                    "total_annual_amount": 0.0,
                    "quarter_1_amount": 0.0,
                    "quarter_2_amount": 0.0,
                    "quarter_3_amount": 0.0,
                    "quarter_4_amount": 0.0,
                    "is_cash_basis_recc": bool(inv.get("is_cash_basis_recc", False)),
                    "is_reverse_charge": bool(inv.get("is_reverse_charge", False))
                }

            third_parties[key]["total_annual_amount"] = round(third_parties[key]["total_annual_amount"] + total_line, 2)
            q_field = f"quarter_{q}_amount"
            third_parties[key][q_field] = round(third_parties[key][q_field] + total_line, 2)

        # Filtrar umbral legal de 3.005,06 €
        declared_list: List[Model347DeclaredDTO] = []
        for (nif, op_key), data in third_parties.items():
            tot = data["total_annual_amount"]
            if tot > 3005.06:
                tot_cash = cash_by_client.get(nif, 0.0)
                cash_declared = tot_cash if tot_cash > 6000.00 else 0.0

                # Ajustar posible redondeo de céntimos para que suma(1T..4T) == total
                q_sum = round(
                    data["quarter_1_amount"] + data["quarter_2_amount"] +
                    data["quarter_3_amount"] + data["quarter_4_amount"], 2
                )
                if abs(q_sum - tot) > 0.0 and abs(q_sum - tot) <= 0.05:
                    data["quarter_4_amount"] = round(data["quarter_4_amount"] + (tot - q_sum), 2)

                declared_list.append(Model347DeclaredDTO(
                    nif=data["nif"],
                    name=data["name"],
                    province_code=data["province_code"],
                    operation_key=data["operation_key"],
                    total_annual_amount=tot,
                    quarter_1_amount=data["quarter_1_amount"],
                    quarter_2_amount=data["quarter_2_amount"],
                    quarter_3_amount=data["quarter_3_amount"],
                    quarter_4_amount=data["quarter_4_amount"],
                    cash_amount=cash_declared,
                    is_cash_basis_recc=data["is_cash_basis_recc"],
                    is_reverse_charge=data["is_reverse_charge"]
                ))

        total_ops = round(sum(d.total_annual_amount for d in declared_list), 2)
        total_cash_global = round(sum(d.cash_amount for d in declared_list), 2)

        return Model347ResultDTO(
            fiscal_year=fiscal_year,
            declarant_nif=declarant_nif,
            declarant_name=declarant_name,
            total_declared_records=len(declared_list),
            total_operations_amount=total_ops,
            total_cash_amount=total_cash_global,
            declared_records=declared_list,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    @classmethod
    def calculate_model_347(
        cls,
        fiscal_year: int,
        tenant_id: str = "default",
        declarant_nif: Optional[str] = None,
        declarant_name: Optional[str] = None,
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Any:
        """
        Consolida las facturas de ventas y compras del año de la base de datos SQLite y calcula el Modelo 347.
        """
        with _get_connection() as conn:
            conn.row_factory = sqlite3.Row if hasattr(sqlite3, "Row") else None
            query = """
                SELECT * FROM invoices
                WHERE year = ?
            """
            rows = conn.execute(query, (fiscal_year,)).fetchall()

        invoices_parsed = []
        for r in rows:
            r_keys = r.keys() if hasattr(r, "keys") else []
            cat = r["category"] if "category" in r_keys else ""
            is_sales = cat in ("ingreso", "income", "venta")

            try:
                base = float(encryptor.decrypt(r["base_imponible"]) or 0.0)
                iva = float(encryptor.decrypt(r["iva_amount"]) or 0.0)
                irpf = float(encryptor.decrypt(r["irpf_amount"]) or 0.0) if "irpf_amount" in r_keys and r["irpf_amount"] else 0.0
            except Exception:
                base = iva = irpf = 0.0

            try:
                if is_sales:
                    nif = encryptor.decrypt(r["receiver_nif"])
                    name = encryptor.decrypt(r["receiver_name"])
                else:
                    nif = encryptor.decrypt(r["issuer_nif"])
                    name = encryptor.decrypt(r["issuer_name"])
            except Exception:
                continue

            q = r["quarter"] if "quarter" in r_keys and r["quarter"] else None
            if not q and "date" in r_keys and r["date"]:
                try:
                    month = int(r["date"][5:7])
                    q = (month - 1) // 3 + 1
                except Exception:
                    q = 1

            pay_method = r["payment_method"] if "payment_method" in r_keys and r["payment_method"] else "transfer"

            invoices_parsed.append({
                "nif": nif,
                "name": name,
                "category": cat,
                "base": base,
                "iva": iva,
                "irpf": irpf,
                "quarter": q,
                "payment_method": pay_method
            })

        dec_nif = declarant_nif or "B87654321"
        dec_name = declarant_name or "INNOVACIONES TECNOLOGICAS SL"

        return cls.aggregate_invoices_for_model_347(
            invoices=invoices_parsed,
            fiscal_year=fiscal_year,
            declarant_nif=dec_nif,
            declarant_name=dec_name,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    @classmethod
    def audit_and_reconcile_model_347(
        cls,
        fiscal_year: int,
        model_347_result: Any,
        tenant_id: str = "default"
    ) -> Any:
        """
        Audita la concordancia matemática estricta de todos los registros declarados en el Modelo 347.
        Valida que sum(1T..4T) == total anual y que todos superen el umbral legal de 3.005,06 €.
        """
        from app.domain.models.billing import Model347ReconciliationDTO

        total_annual = round(model_347_result.total_operations_amount, 2)
        total_q_sum = 0.0
        discrepancias: List[str] = []

        max_declared_diff = 0.0
        for d in model_347_result.declared_records:
            d_q_sum = round(d.quarter_1_amount + d.quarter_2_amount + d.quarter_3_amount + d.quarter_4_amount, 2)
            d_annual = round(d.total_annual_amount, 2)
            d_diff = round(abs(d_q_sum - d_annual), 2)
            if d_diff > max_declared_diff:
                max_declared_diff = d_diff

            if d_diff > 0.05:
                discrepancias.append(
                    f"Descuadre en declarado {d.nif}: suma trimestral ({d_q_sum} €) difiere del anual ({d_annual} €)."
                )
            if d_annual <= 3005.06:
                discrepancias.append(
                    f"Infracción de umbral en declarado {d.nif}: importe ({d_annual} €) no supera 3.005,06 €."
                )

            total_q_sum = round(total_q_sum + d_q_sum, 2)

        global_diff = round(abs(total_annual - total_q_sum), 2)
        is_reconciled = (len(discrepancias) == 0 and global_diff <= 0.05)
        has_tolerance = (0.0 < global_diff <= 0.05) or (0.0 < max_declared_diff <= 0.05)

        return Model347ReconciliationDTO(
            fiscal_year=fiscal_year,
            total_annual_model_347=total_annual,
            total_quarterly_sum=total_q_sum,
            quarterly_difference=global_diff,
            is_mathematically_reconciled=is_reconciled,
            has_rounding_tolerance=has_tolerance,
            discrepancies=discrepancias
        )


class AnnualTaxService:
    """
    Servicio de consolidación anual para autoliquidaciones y declaraciones informativas (Modelos 390, 190, 180).
    """

    def calculate_model_390(
        self,
        fiscal_year: int,
        quarterly_declarations: List[Any] = None,
        prorrata_anual_pct: float = 100.0
    ):
        """
        Calcula la declaración resumen anual del IVA (Modelo 390) consolidando los 4 trimestres del Modelo 303.
        """
        from app.domain.models.billing import Model390ResultDTO, Model303ResultDTO

        total_base_21 = 0.0
        total_cuota_21 = 0.0
        total_base_10 = 0.0
        total_cuota_10 = 0.0
        total_base_4 = 0.0
        total_cuota_4 = 0.0
        total_base_ded_corr = 0.0
        total_cuota_ded_corr = 0.0
        total_base_ded_inv = 0.0
        total_cuota_ded_inv = 0.0
        total_resultado = 0.0

        if quarterly_declarations:
            for q in quarterly_declarations:
                if isinstance(q, Model303ResultDTO):
                    total_base_21 += q.base_general_21
                    total_cuota_21 += q.cuota_general_21
                    total_base_10 += q.base_reducido_10
                    total_cuota_10 += q.cuota_reducido_10
                    total_base_4 += q.base_superreducido_4
                    total_cuota_4 += q.cuota_superreducido_4
                    total_base_ded_corr += q.base_deducible_corriente
                    total_cuota_ded_corr += q.iva_deducible_corriente
                    total_base_ded_inv += q.base_deducible_inversion
                    total_cuota_ded_inv += q.iva_deducible_inversion
                    total_resultado += q.resultado_autoliquidacion
                elif isinstance(q, dict):
                    total_base_21 += q.get("base_general_21", 0.0)
                    total_cuota_21 += q.get("cuota_general_21", 0.0)
                    total_base_10 += q.get("base_reducido_10", 0.0)
                    total_cuota_10 += q.get("cuota_reducido_10", 0.0)
                    total_base_4 += q.get("base_superreducido_4", 0.0)
                    total_cuota_4 += q.get("cuota_superreducido_4", 0.0)
                    total_base_ded_corr += q.get("base_deducible_corriente", 0.0)
                    total_cuota_ded_corr += q.get("iva_deducible_corriente", 0.0)
                    total_base_ded_inv += q.get("base_deducible_inversion", 0.0)
                    total_cuota_ded_inv += q.get("iva_deducible_inversion", 0.0)
                    total_resultado += q.get("resultado_autoliquidacion", 0.0)

        volumen_operaciones = round(total_base_21 + total_base_10 + total_base_4, 2)

        casillas = {
            "01": round(total_base_21, 2), "02": 21.0, "03": round(total_cuota_21, 2),
            "04": round(total_base_10, 2), "05": 10.0, "06": round(total_cuota_10, 2),
            "07": round(total_base_4, 2), "08": 4.0, "09": round(total_cuota_4, 2),
            "27": round(total_cuota_21 + total_cuota_10 + total_cuota_4, 2),
            "28": round(total_base_ded_corr, 2), "29": round(total_cuota_ded_corr, 2),
            "30": round(total_base_ded_inv, 2), "31": round(total_cuota_ded_inv, 2),
            "37": round(total_cuota_ded_corr + total_cuota_ded_inv, 2),
            "88": volumen_operaciones,
            "99": round(total_resultado, 2)
        }

        return Model390ResultDTO(
            fiscal_year=fiscal_year,
            total_base_devengada_21=round(total_base_21, 2),
            total_cuota_devengada_21=round(total_cuota_21, 2),
            total_base_devengada_10=round(total_base_10, 2),
            total_cuota_devengada_10=round(total_cuota_10, 2),
            total_base_devengada_4=round(total_base_4, 2),
            total_cuota_devengada_4=round(total_cuota_4, 2),
            total_base_deducible_corriente=round(total_base_ded_corr, 2),
            total_cuota_deducible_corriente=round(total_cuota_ded_corr, 2),
            total_base_deducible_inversion=round(total_base_ded_inv, 2),
            total_cuota_deducible_inversion=round(total_cuota_ded_inv, 2),
            volumen_total_operaciones=volumen_operaciones,
            prorrata_anual_pct=prorrata_anual_pct,
            regularizacion_anual=0.0,
            resultado_anual_declaracion=round(total_resultado, 2),
            casillas=casillas
        )

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
        from app.domain.models.billing import Model190ResultDTO, Model190PerceptorDTO

        data = AnnualTaxAggregatorService.get_modelo_190_data(year=fiscal_year)
        perceptores_dto = []

        for p in data.get("perceptores", []):
            perceptores_dto.append(Model190PerceptorDTO(
                nif=p["nif"],
                name=p["name"],
                clave=p.get("clave", "A"),
                subclave=p.get("subclave", "  "),
                percepciones_dinerarias=p.get("percepciones", 0.0),
                retenciones_practicadas=p.get("retenciones", 0.0),
                percepciones_especie_valoracion=p.get("percepciones_especie_valoracion", 0.0),
                percepciones_especie_ingresos_a_cuenta=p.get("percepciones_especie_ingresos_a_cuenta", 0.0),
                percepciones_especie_repercutidos=p.get("percepciones_especie_repercutidos", 0.0),
                ejercicio_devengo=p.get("ejercicio_devengo", 0),
                discapacidad=p.get("discapacidad", 0),
                tipo_contrato=p.get("tipo_contrato", 1),
                reducciones_aplicables=p.get("reducciones_aplicables", 0),
                ano_nacimiento=p.get("ano_nacimiento", 0),
                situacion_familiar=p.get("situacion_familiar", 3),
                conyuge_nif=p.get("conyuge_nif"),
                num_hijos=p.get("num_hijos", 0),
                num_hijos_discapacidad=p.get("num_hijos_discapacidad", 0),
                num_ascendientes=p.get("num_ascendientes", 0)
            ))

        tot_dinerarias = float(data.get("total_percepciones", 0.0))
        tot_especie = float(data.get("total_percepciones_especie", 0.0))
        tot_global = float(data.get("total_percepciones_global", 0.0)) or round(tot_dinerarias + tot_especie, 2)

        return Model190ResultDTO(
            fiscal_year=fiscal_year,
            total_perceptores=len(perceptores_dto),
            total_percepciones_dinerarias=tot_dinerarias,
            total_retenciones_practicadas=float(data.get("total_retenciones", 0.0)),
            total_percepciones_especie=tot_especie,
            total_ingresos_a_cuenta=float(data.get("total_ingresos_a_cuenta", 0.0)),
            total_percepciones_global=tot_global,
            perceptores=perceptores_dto,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    def reconcile_with_model_111(
        self,
        fiscal_year: int,
        model_190_result: Model190ResultDTO,
        quarterly_111_declarations: Optional[List[Any]] = None,
        tenant_id: str = "default"
    ) -> Model190ReconciliationDTO:
        """
        Cruza las retenciones declaradas en el Modelo 190 contra el sumatorio de los cuatro trimestres del Modelo 111.
        Diferencia entre tolerancia por redondeo acumulativo (<= +-0.05 €) y descuadres estructurales.
        """
        from app.domain.models.billing import Model190ReconciliationDTO, Model111ResultDTO

        total_190 = round(model_190_result.total_retenciones_practicadas, 2)
        q_totals = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

        if quarterly_111_declarations:
            for decl in quarterly_111_declarations:
                if isinstance(decl, Model111ResultDTO):
                    q = decl.quarter
                    val = decl.resultado_total
                elif isinstance(decl, dict):
                    q = decl.get("quarter", 1)
                    val = decl.get("resultado_total", decl.get("casilla_28", 0.0))
                else:
                    q = getattr(decl, "quarter", 1)
                    val = getattr(decl, "resultado_total", 0.0)
                if q in q_totals:
                    q_totals[q] = round(float(val), 2)

        total_111_anual = round(sum(q_totals.values()), 2)
        diff = round(abs(total_190 - total_111_anual), 2)

        is_cuadrado = diff <= 0.05
        is_tolerancia = (0.0 < diff <= 0.05)

        discrepancias = []
        if not is_cuadrado:
            discrepancias.append(
                f"Descuadre estructural entre Modelo 190 ({total_190} €) y suma de 111 trimestrales ({total_111_anual} €). "
                f"Diferencia: {diff} € excede el umbral de tolerancia de 0.05 €."
            )

        # Desglose por claves en 190
        desglose: Dict[str, Dict[str, float]] = {}
        for p in model_190_result.perceptores:
            c = p.clave
            if c not in desglose:
                desglose[c] = {"percepciones": 0.0, "retenciones": 0.0}
            desglose[c]["percepciones"] = round(desglose[c]["percepciones"] + p.percepciones_dinerarias, 2)
            desglose[c]["retenciones"] = round(desglose[c]["retenciones"] + p.retenciones_practicadas, 2)

        return Model190ReconciliationDTO(
            fiscal_year=fiscal_year,
            total_retenciones_190=total_190,
            total_retenciones_111_1t=q_totals[1],
            total_retenciones_111_2t=q_totals[2],
            total_retenciones_111_3t=q_totals[3],
            total_retenciones_111_4t=q_totals[4],
            total_retenciones_111_anual=total_111_anual,
            diferencia_total=diff,
            is_cuadrado=is_cuadrado,
            is_tolerancia_redondeo=is_tolerancia,
            desglose_por_claves=desglose,
            discrepancias_detectadas=discrepancias
        )

    def file_and_custody_model_190(
        self,
        model_190: Any,
        declarant_info: Any,
        tenant_id: str = "default",
        filing_status: str = "CALCULATED",
        aeat_csv: Optional[str] = None
    ) -> Any:
        """
        Exporta el Modelo 190 a formato telemático oficial BOE (.ses) y lo custodia
        inmutablemente en el libro de declaraciones tributarias durante el plazo legal de 5 años.
        """
        from app.domain.services.boe_export_service import BoeExportService
        from app.domain.services.tax_ledger_service import TaxLedgerService
        from app.domain.models.billing import DeclarantInfoDTO

        boe_service = BoeExportService()
        boe_result = boe_service.export_model_190_boe(model_190, declarant_info)

        ledger_service = TaxLedgerService()
        declarant_nif = boe_result.declarant_nif
        if isinstance(declarant_info, DeclarantInfoDTO):
            declarant_name = declarant_info.name
        elif isinstance(declarant_info, dict):
            declarant_name = declarant_info.get("name", "")
        else:
            declarant_name = getattr(declarant_info, "name", "")

        casillas_payload = {
            "total_perceptores": model_190.total_perceptores,
            "total_percepciones_dinerarias": model_190.total_percepciones_dinerarias,
            "total_retenciones_practicadas": model_190.total_retenciones_practicadas,
            "total_percepciones_especie": model_190.total_percepciones_especie,
            "total_ingresos_a_cuenta": model_190.total_ingresos_a_cuenta,
            "total_percepciones_global": model_190.total_percepciones_global
        }

        audit_record = ledger_service.save_declaration_filing(
            model_code="190",
            fiscal_year=model_190.fiscal_year,
            period="0A",
            declarant_nif=declarant_nif,
            declarant_name=declarant_name,
            casillas_payload=casillas_payload,
            boe_file_content=boe_result.content_raw,
            tenant_id=tenant_id,
            filing_status=filing_status,
            aeat_csv=aeat_csv
        )
        return audit_record

    @classmethod
    def calculate_model_180_from_perceptors(
        cls,
        fiscal_year: int,
        perceptors: List[Any],
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Any:
        return AnnualTaxAggregatorService.calculate_model_180_from_perceptors(
            fiscal_year=fiscal_year,
            perceptors=perceptors,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    def calculate_model_180(
        self,
        fiscal_year: int,
        tenant_id: str = "default",
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Any:
        return AnnualTaxAggregatorService.calculate_model_180(
            fiscal_year=fiscal_year,
            tenant_id=tenant_id,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    def reconcile_with_model_115(
        self,
        fiscal_year: int,
        model_180_result: Any,
        quarterly_115_declarations: Optional[List[Any]] = None,
        tenant_id: str = "default"
    ) -> Any:
        return AnnualTaxAggregatorService.reconcile_with_model_115(
            fiscal_year=fiscal_year,
            model_180_result=model_180_result,
            quarterly_115_declarations=quarterly_115_declarations,
            tenant_id=tenant_id
        )

    def file_and_custody_model_180(
        self,
        model_180: Any = None,
        declarant_info: Any = None,
        tenant_id: str = "default",
        filing_status: str = "CALCULATED",
        aeat_csv: Optional[str] = None,
        model_180_result: Any = None
    ) -> Any:
        target_model = model_180 if model_180 is not None else model_180_result
        from app.domain.services.boe_export_service import BoeExportService
        from app.domain.services.tax_ledger_service import TaxLedgerService
        from app.domain.models.billing import DeclarantInfoDTO

        boe_service = BoeExportService()
        boe_result = boe_service.export_model_180_boe(target_model, declarant_info)

        ledger_service = TaxLedgerService()
        declarant_nif = boe_result.declarant_nif
        if isinstance(declarant_info, DeclarantInfoDTO):
            declarant_name = declarant_info.name
        elif isinstance(declarant_info, dict):
            declarant_name = declarant_info.get("name", "")
        else:
            declarant_name = getattr(declarant_info, "name", "")

        casillas_payload = {
            "total_perceptores": target_model.total_perceptores,
            "total_base_retenciones": target_model.total_base_retenciones,
            "total_retenciones_practicadas": target_model.total_retenciones_practicadas
        }

        audit_record = ledger_service.save_declaration_filing(
            model_code="180",
            fiscal_year=target_model.fiscal_year,
            period="0A",
            declarant_nif=declarant_nif,
            declarant_name=declarant_name,
            casillas_payload=casillas_payload,
            boe_file_content=boe_result.content_raw,
            tenant_id=tenant_id,
            filing_status=filing_status,
            aeat_csv=aeat_csv
        )
        return audit_record

    def calculate_model_347(
        self,
        fiscal_year: int,
        tenant_id: str = "default",
        declarant_nif: Optional[str] = None,
        declarant_name: Optional[str] = None,
        is_complementary: bool = False,
        previous_receipt_number: Optional[str] = None
    ) -> Any:
        return AnnualTaxAggregatorService.calculate_model_347(
            fiscal_year=fiscal_year,
            tenant_id=tenant_id,
            declarant_nif=declarant_nif,
            declarant_name=declarant_name,
            is_complementary=is_complementary,
            previous_receipt_number=previous_receipt_number
        )

    def audit_and_reconcile_model_347(
        self,
        fiscal_year: int,
        model_347_result: Any,
        tenant_id: str = "default"
    ) -> Any:
        return AnnualTaxAggregatorService.audit_and_reconcile_model_347(
            fiscal_year=fiscal_year,
            model_347_result=model_347_result,
            tenant_id=tenant_id
        )

    def file_and_custody_model_347(
        self,
        model_347: Any = None,
        declarant_info: Any = None,
        tenant_id: str = "default",
        filing_status: str = "CALCULATED",
        aeat_csv: Optional[str] = None,
        model_347_result: Any = None
    ) -> Any:
        target_model = model_347 if model_347 is not None else model_347_result
        from app.domain.services.boe_export_service import BoeExportService
        from app.domain.services.tax_ledger_service import TaxLedgerService
        from app.domain.models.billing import DeclarantInfoDTO

        boe_service = BoeExportService()
        boe_result = boe_service.export_model_347_boe(target_model, declarant_info)

        ledger_service = TaxLedgerService()
        declarant_nif = boe_result.declarant_nif
        if isinstance(declarant_info, DeclarantInfoDTO):
            declarant_name = declarant_info.name
        elif isinstance(declarant_info, dict):
            declarant_name = declarant_info.get("name", "")
        else:
            declarant_name = getattr(declarant_info, "name", "")

        casillas_payload = {
            "total_declarados": target_model.total_declared_records,
            "total_operaciones": target_model.total_operations_amount,
            "total_metalico": target_model.total_cash_amount
        }

        audit_record = ledger_service.save_declaration_filing(
            model_code="347",
            fiscal_year=target_model.fiscal_year,
            period="0A",
            declarant_nif=declarant_nif,
            declarant_name=declarant_name,
            casillas_payload=casillas_payload,
            boe_file_content=boe_result.content_raw,
            tenant_id=tenant_id,
            filing_status=filing_status,
            aeat_csv=aeat_csv
        )
        return audit_record


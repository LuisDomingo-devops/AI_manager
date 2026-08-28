"""
ANNUAL TAX SERVICE — Servicio de dominio para la consolidación anual de IVA (390) y retenciones de IRPF (190, 180).
"""

from typing import Dict, Any, List
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor


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
        Consolida las retenciones anuales de IRPF de trabajadores (Clave A) y profesionales (Clave G) para el Modelo 190.
        """
        perceptores = {}

        # 1. Rendimientos del Trabajo (Clave A) desde las Nóminas
        query_payrolls = """
            SELECT employee_id, gross_total, irpf_amount
            FROM payrolls
            WHERE year = ?
        """
        with _get_connection() as conn:
            payrolls = conn.execute(query_payrolls, (year,)).fetchall()

            for p in payrolls:
                emp_id = p["employee_id"]
                gross = p["gross_total"]
                irpf = p["irpf_amount"]

                if emp_id not in perceptores:
                    # Buscar datos del empleado
                    emp_row = conn.execute(
                        "SELECT nif_encrypted, full_name_encrypted FROM employees WHERE id = ?",
                        (emp_id,)
                    ).fetchone()
                    
                    if emp_row:
                        nif = encryptor.decrypt(emp_row["nif_encrypted"])
                        name = encryptor.decrypt(emp_row["full_name_encrypted"])
                        perceptores[nif] = {
                            "nif": nif,
                            "name": name,
                            "clave": "A",
                            "percepciones": 0.0,
                            "retenciones": 0.0
                        }
                    else:
                        continue

                nif_key = encryptor.decrypt(
                    conn.execute("SELECT nif_encrypted FROM employees WHERE id = ?", (emp_id,)).fetchone()["nif_encrypted"]
                )
                if nif_key in perceptores:
                    perceptores[nif_key]["percepciones"] += gross
                    perceptores[nif_key]["retenciones"] += irpf

        # 2. Rendimientos Profesionales (Clave G) desde las Facturas de Gasto
        query_expenses = """
            SELECT issuer_nif, issuer_name, base_imponible, irpf_amount
            FROM invoices
            WHERE year = ? AND category IN ('gasto', 'expense')
        """
        with _get_connection() as conn:
            expenses = conn.execute(query_expenses, (year,)).fetchall()

        for exp in expenses:
            try:
                irpf = float(encryptor.decrypt(exp["irpf_amount"]) or 0.0)
                base = float(encryptor.decrypt(exp["base_imponible"]) or 0.0)
            except Exception:
                irpf = base = 0.0

            # Solo nos interesan las facturas de gasto donde practicamos retención de IRPF
            if irpf > 0:
                try:
                    nif = encryptor.decrypt(exp["issuer_nif"])
                    name = encryptor.decrypt(exp["issuer_name"])
                except Exception:
                    continue

                if nif not in perceptores:
                    perceptores[nif] = {
                        "nif": nif,
                        "name": name,
                        "clave": "G",
                        "percepciones": 0.0,
                        "retenciones": 0.0
                    }
                perceptores[nif]["percepciones"] += base
                perceptores[nif]["retenciones"] += irpf

        # Redondear y calcular totales
        perceptores_list = []
        total_percepciones = 0.0
        total_retenciones = 0.0

        for p in perceptores.values():
            p["percepciones"] = round(p["percepciones"], 2)
            p["retenciones"] = round(p["retenciones"], 2)
            perceptores_list.append(p)
            total_percepciones += p["percepciones"]
            total_retenciones += p["retenciones"]

        return {
            "year": year,
            "perceptores": perceptores_list,
            "total_perceptores": len(perceptores_list),
            "total_percepciones": round(total_percepciones, 2),
            "total_retenciones": round(total_retenciones, 2)
        }

    @classmethod
    def get_modelo_180_data(cls, year: int) -> Dict[str, Any]:
        """
        Consolida las retenciones anuales por arrendamiento de inmuebles urbanos para el Modelo 180.
        """
        query = """
            SELECT issuer_nif, issuer_name, base_imponible, irpf_amount, concept
            FROM invoices
            WHERE year = ? AND category IN ('gasto', 'expense')
        """
        with _get_connection() as conn:
            rows = conn.execute(query, (year,)).fetchall()

        arrendadores = {}
        palabras_alquiler = ("alquiler", "arrendamiento", "renta", "local", "oficina")

        for r in rows:
            try:
                concept = encryptor.decrypt(r["concept"]).lower()
                irpf = float(encryptor.decrypt(r["irpf_amount"]) or 0.0)
                base = float(encryptor.decrypt(r["base_imponible"]) or 0.0)
            except Exception:
                concept = ""
                irpf = base = 0.0

            # Es un alquiler si tiene retención y el concepto contiene palabras clave de alquileres
            if irpf > 0 and any(p in concept for p in palabras_alquiler):
                try:
                    nif = encryptor.decrypt(r["issuer_nif"])
                    name = encryptor.decrypt(r["issuer_name"])
                except Exception:
                    continue

                if nif not in arrendadores:
                    arrendadores[nif] = {
                        "nif": nif,
                        "name": name,
                        "base_alquiler": 0.0,
                        "retencion_practicada": 0.0
                    }
                arrendadores[nif]["base_alquiler"] += base
                arrendadores[nif]["retencion_practicada"] += irpf

        arrendadores_list = []
        total_bases = 0.0
        total_retenciones = 0.0

        for a in arrendadores.values():
            a["base_alquiler"] = round(a["base_alquiler"], 2)
            a["retencion_practicada"] = round(a["retencion_practicada"], 2)
            arrendadores_list.append(a)
            total_bases += a["base_alquiler"]
            total_retenciones += a["retencion_practicada"]

        return {
            "year": year,
            "arrendadores": arrendadores_list,
            "total_arrendadores": len(arrendadores_list),
            "total_bases": round(total_bases, 2),
            "total_retenciones": round(total_retenciones, 2)
        }

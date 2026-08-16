import json
from datetime import datetime
from typing import List, Dict, Any
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

class LedgerService:
    """
    Servicio de Contabilidad por Partida Doble (PGC) para Pymes.
    Gestiona la creación de Asientos contables (Libro Diario), balances, Cuenta de Pérdidas y Ganancias y Cierre de Ejercicio.
    """

    @classmethod
    def validate_double_entry(cls, apuntes: List[Dict[str, Any]]) -> bool:
        """
        Valida el principio contable fundamental de partida doble:
        La suma total de los importes al Debe debe ser exactamente igual a la del Haber.
        """
        total_debe = round(sum(float(ap.get("debe", 0.0)) for ap in apuntes), 2)
        total_haber = round(sum(float(ap.get("haber", 0.0)) for ap in apuntes), 2)
        if total_debe != total_haber:
            raise ValueError(
                f"Asiento contable descuadrado (Partida Doble rota): "
                f"Total Debe ({total_debe:.2f} €) != Total Haber ({total_haber:.2f} €)."
            )
        return True

    @classmethod
    def extract_year_from_date(cls, date_str: str) -> int:
        """Extrae el año entero a partir de cadenas de fecha comunes."""
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).year
            except Exception:
                pass
        return datetime.now().year

    @classmethod
    def is_fiscal_year_closed(cls, year: int) -> bool:
        """
        Comprueba si un ejercicio contable/fiscal está marcado como cerrado en la base de datos.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_closed FROM fiscal_year_status WHERE year = ?", (year,))
            row = cursor.fetchone()
            return bool(row["is_closed"]) if row else False

    @classmethod
    def _insert_journal_and_ledger(cls, date_str: str, concept: str, apuntes: List[Dict[str, Any]]) -> int:
        """Inserta de forma atómica y cifrada un asiento en el Libro Diario y sus apuntes en el Mayor."""
        cls.validate_double_entry(apuntes)
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO journal_entries (entry_date, concept) VALUES (?, ?)",
                (date_str, encryptor.encrypt(concept))
            )
            journal_id = cursor.lastrowid
            db_apuntes = []
            for ap in apuntes:
                db_apuntes.append((
                    journal_id,
                    ap["account_code"],
                    encryptor.encrypt(str(float(ap.get("debe", 0.0)))),
                    encryptor.encrypt(str(float(ap.get("haber", 0.0))))
                ))
            cursor.executemany(
                "INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (?, ?, ?, ?)",
                db_apuntes
            )
            conn.commit()
            return journal_id

    @classmethod
    def record_invoice_asiento(cls, invoice_data: Dict[str, Any]) -> int:
        """
        Registra el asiento contable (partida doble) para una factura de ingreso o gasto.
        - Ventas/Ingresos:
            Debe: 43000000 (Clientes) - Total Factura
            Haber: 70500000 (Prestación de Servicios) - Base Imponible
            Haber: 47700021 (IVA Repercutido 21%) - IVA
        - Compras/Gastos:
            Debe: 62900000 (Gastos Diversos) - Base Imponible
            Debe: 47200021 (IVA Soportado 21%) - IVA
            Haber: 40000000 (Proveedores) - Total Factura
        """
        category = invoice_data.get("category", "ingreso").lower()
        invoice_id = invoice_data.get("invoice_id", "FAC-MOCK")
        date_str = invoice_data.get("date", datetime.now().strftime("%d/%m/%Y"))
        year = cls.extract_year_from_date(date_str)
        if cls.is_fiscal_year_closed(year):
            raise ValueError(f"El ejercicio fiscal {year} está cerrado. No se permiten nuevos asientos ni modificaciones.")

        base = float(invoice_data.get("base_imponible", 0.0))
        iva = float(invoice_data.get("iva_amount", 0.0))
        irpf = float(invoice_data.get("irpf_amount", 0.0))
        total = float(invoice_data.get("total_amount", 0.0))

        concept = f"Factura {invoice_id}"
        apuntes = []
        
        if category in ("ingreso", "income"):
            apuntes.append({"account_code": "43000000", "debe": total, "haber": 0.0})
            if irpf > 0:
                apuntes.append({"account_code": "47300000", "debe": irpf, "haber": 0.0})
            apuntes.append({"account_code": "70500000", "debe": 0.0, "haber": base})
            if iva > 0:
                apuntes.append({"account_code": "47700021", "debe": 0.0, "haber": iva})
        else:
            apuntes.append({"account_code": "62900000", "debe": base, "haber": 0.0})
            if iva > 0:
                apuntes.append({"account_code": "47200021", "debe": iva, "haber": 0.0})
            if irpf > 0:
                apuntes.append({"account_code": "47510000", "debe": 0.0, "haber": irpf})
            apuntes.append({"account_code": "40000000", "debe": 0.0, "haber": total})

        return cls._insert_journal_and_ledger(date_str, concept, apuntes)

    @classmethod
    def get_libro_diario(cls, year: int) -> List[Dict[str, Any]]:
        """
        Retorna la lista de todos los asientos y apuntes contables para un año fiscal específico.
        """
        result = []
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, entry_date, concept FROM journal_entries ORDER BY id ASC
            """)
            raw_entries = cursor.fetchall()

            entries = []
            for entry in raw_entries:
                entry_date_raw = entry["entry_date"]
                entry_year = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        dt = datetime.strptime(entry_date_raw, fmt)
                        entry_year = dt.year
                        break
                    except Exception:
                        pass
                if entry_year is None:
                    if str(year) in entry_date_raw:
                        entry_year = year
                if entry_year == year:
                    entries.append(entry)

            for entry in entries:
                journal_id = entry["id"]
                concept = encryptor.decrypt(entry["concept"])
                
                # Obtener apuntes de este asiento
                cursor.execute("""
                    SELECT l.account_code, a.name as account_name, l.debe, l.haber 
                    FROM ledger_entries l
                    JOIN pgc_accounts a ON l.account_code = a.code
                    WHERE l.journal_entry_id = ?
                """, (journal_id,))
                apuntes = cursor.fetchall()
                
                apuntes_list = []
                for ap in apuntes:
                    apuntes_list.append({
                        "cuenta": ap["account_code"],
                        "nombre_cuenta": ap["account_name"],
                        "debe": float(encryptor.decrypt(ap["debe"])),
                        "haber": float(encryptor.decrypt(ap["haber"]))
                    })

                result.append({
                    "asiento_id": journal_id,
                    "fecha": entry["entry_date"],
                    "concepto": concept,
                    "apuntes": apuntes_list
                })
        return result

    @classmethod
    def get_balance_situacion(cls, year: int) -> Dict[str, Any]:
        """
        Genera el Balance de Situación simplificado bajo el PGC: Activos vs Pasivos + Patrimonio.
        """
        activo = 0.0
        pasivo_patrimonio = 0.0
        cuentas_balance = {}

        with _get_connection() as conn:
            cursor = conn.cursor()
            # Seleccionar todos los apuntes del año
            cursor.execute("""
                SELECT l.account_code, a.name as account_name, a.type as account_type, l.debe, l.haber, j.entry_date 
                FROM ledger_entries l
                JOIN pgc_accounts a ON l.account_code = a.code
                JOIN journal_entries j ON l.journal_entry_id = j.id
            """)
            raw_apuntes = cursor.fetchall()
            
            apuntes = []
            for ap in raw_apuntes:
                entry_date_raw = ap["entry_date"]
                entry_year = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        dt = datetime.strptime(entry_date_raw, fmt)
                        entry_year = dt.year
                        break
                    except Exception:
                        pass
                if entry_year is None:
                    if str(year) in entry_date_raw:
                        entry_year = year
                if entry_year == year:
                    apuntes.append(ap)

            for ap in apuntes:
                code = ap["account_code"]
                name = ap["account_name"]
                atype = ap["account_type"]
                debe = float(encryptor.decrypt(ap["debe"]))
                haber = float(encryptor.decrypt(ap["haber"]))

                if code not in cuentas_balance:
                    cuentas_balance[code] = {"name": name, "type": atype, "saldo": 0.0}

                # Ajustar saldo según naturaleza de la cuenta
                if atype == "activo" or atype == "gasto":
                    cuentas_balance[code]["saldo"] += (debe - haber)
                else:
                    cuentas_balance[code]["saldo"] += (haber - debe)

        # Separar en Activo y Pasivo/Patrimonio
        desglose_activo = {}
        desglose_pasivo = {}

        for code, info in cuentas_balance.items():
            if info["type"] == "activo":
                activo += info["saldo"]
                desglose_activo[code] = {"nombre": info["name"], "saldo": info["saldo"]}
            elif info["type"] in ("pasivo", "patrimonio"):
                pasivo_patrimonio += info["saldo"]
                desglose_pasivo[code] = {"nombre": info["name"], "saldo": info["saldo"]}

        return {
            "año": year,
            "total_activo": activo,
            "total_pasivo_patrimonio": pasivo_patrimonio,
            "activo": desglose_activo,
            "pasivo_patrimonio": desglose_pasivo
        }

    @classmethod
    def get_pgc_accounts(cls) -> List[Dict[str, Any]]:
        """
        Retorna la lista de todas las cuentas registradas en el PGC.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('57000000', 'Caja, euros (efectivo)', 'activo')")
            conn.commit()
            cursor.execute("SELECT code, name, type FROM pgc_accounts ORDER BY code ASC")
            rows = cursor.fetchall()
            return [{"code": r["code"], "name": r["name"], "type": r["type"]} for r in rows]

    @classmethod
    def record_manual_entry(cls, date_str: str, concept: str, apuntes: List[Dict[str, Any]]) -> int:
        """
        Registra un asiento contable manual con una lista de apuntes (partida doble).
        Cada apunte contiene:
        - account_code: código de subcuenta PGC (ej: '57000000')
        - debe: importe al debe
        - haber: importe al haber
        """
        year = cls.extract_year_from_date(date_str)
        if cls.is_fiscal_year_closed(year):
            raise ValueError(f"El ejercicio fiscal {year} está cerrado. No se permiten nuevos asientos ni modificaciones.")
        return cls._insert_journal_and_ledger(date_str, concept, apuntes)

    @classmethod
    def get_libro_mayor(cls, account_code: str, year: int) -> List[Dict[str, Any]]:
        """
        Retorna la lista de todos los apuntes contables asociados a una subcuenta específica.
        Incluye el cálculo del saldo acumulado histórico según la naturaleza de la cuenta.
        """
        result = []
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT j.id as journal_id, j.entry_date, j.concept, l.debe, l.haber
                FROM ledger_entries l
                JOIN journal_entries j ON l.journal_entry_id = j.id
                WHERE l.account_code = ?
                ORDER BY j.id ASC
            """, (account_code,))
            rows = cursor.fetchall()
            
            # Obtener tipo/naturaleza de la cuenta para el cálculo del saldo
            cursor.execute("SELECT type FROM pgc_accounts WHERE code = ?", (account_code,))
            ac_type_row = cursor.fetchone()
            ac_type = ac_type_row["type"] if ac_type_row else "activo"
            
            saldo = 0.0
            for r in rows:
                entry_date_raw = r["entry_date"]
                entry_year = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        dt = datetime.strptime(entry_date_raw, fmt)
                        entry_year = dt.year
                        break
                    except Exception:
                        pass
                if entry_year is None:
                    if str(year) in entry_date_raw:
                        entry_year = year
                
                if entry_year == year:
                    debe = float(encryptor.decrypt(r["debe"]))
                    haber = float(encryptor.decrypt(r["haber"]))
                    concept = encryptor.decrypt(r["concept"])
                    
                    if ac_type in ("activo", "gasto"):
                        saldo += (debe - haber)
                    else:
                        saldo += (haber - debe)
                        
                    result.append({
                        "asiento_id": r["journal_id"],
                        "fecha": r["entry_date"],
                        "concepto": concept,
                        "debe": debe,
                        "haber": haber,
                        "saldo": saldo
                    })
        return result

    @classmethod
    def get_modelo_130_estimate(cls, year: int, quarter: int) -> Dict[str, Any]:
        """
        Calcula el rendimiento neto y el pago fraccionado estimado del IRPF (Modelo 130).
        """
        total_ingresos = 0.0
        total_gastos = 0.0
        
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.account_code, a.type as account_type, l.debe, l.haber, j.entry_date 
                FROM ledger_entries l
                JOIN pgc_accounts a ON l.account_code = a.code
                JOIN journal_entries j ON l.journal_entry_id = j.id
            """)
            rows = cursor.fetchall()
            
            for r in rows:
                entry_date_raw = r["entry_date"]
                entry_year = None
                entry_month = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        dt = datetime.strptime(entry_date_raw, fmt)
                        entry_year = dt.year
                        entry_month = dt.month
                        break
                    except Exception:
                        pass
                if entry_year is None:
                    if str(year) in entry_date_raw:
                        entry_year = year
                
                # Mapear mes a trimestre
                entry_quarter = None
                if entry_month:
                    entry_quarter = (entry_month - 1) // 3 + 1
                
                if entry_year == year and (entry_quarter == quarter or entry_quarter is None):
                    atype = r["account_type"]
                    debe = float(encryptor.decrypt(r["debe"]))
                    haber = float(encryptor.decrypt(r["haber"]))
                    
                    if atype == "ingreso":
                        total_ingresos += (haber - debe)
                    elif atype == "gasto":
                        total_gastos += (debe - haber)
                        
        rendimiento = total_ingresos - total_gastos
        pago_estimado = rendimiento * 0.20 if rendimiento > 0 else 0.0
        
        return {
            "ingresos": total_ingresos,
            "gastos": total_gastos,
            "rendimiento": rendimiento,
            "pago_estimado": pago_estimado
        }

    @classmethod
    def get_iva_register_books(cls, year: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retorna las facturas emitidas (ingresos) y recibidas (gastos) para los libros oficiales.
        """
        emitidas = []
        recibidas = []
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif, 
                       base_imponible, iva_rate, iva_amount, irpf_amount, total_amount, category, quarter
                FROM invoices 
                WHERE year = ?
                ORDER BY date ASC
            """, (year,))
            rows = cursor.fetchall()
            
            for r in rows:
                def _dec(val, is_num=False, default=0.0):
                    if val is None:
                        return default if is_num else ""
                    try:
                        dec = encryptor.decrypt(val)
                        return float(dec) if is_num else str(dec)
                    except Exception:
                        return float(val) if is_num else str(val)

                cat = _dec(r["category"]).lower()
                data = {
                    "num_factura": _dec(r["invoice_id"]),
                    "fecha": _dec(r["date"]),
                    "proveedor": _dec(r["issuer_name"]),
                    "nif_proveedor": _dec(r["issuer_nif"]),
                    "cliente": _dec(r["receiver_name"]),
                    "nif_cliente": _dec(r["receiver_nif"]),
                    "base": _dec(r["base_imponible"], is_num=True),
                    "tipo_iva": _dec(r["iva_rate"], is_num=True),
                    "cuota_iva": _dec(r["iva_amount"], is_num=True),
                    "retencion": _dec(r["irpf_amount"], is_num=True),
                    "total": _dec(r["total_amount"], is_num=True),
                    "trimestre": r["quarter"]
                }
                if cat in ("ingreso", "income", "emitida"):
                    emitidas.append(data)
                else:
                    recibidas.append(data)
        return {"emitidas": emitidas, "recibidas": recibidas}

    get_libros_iva = get_iva_register_books

    @classmethod
    def record_rectificativa_invoice_asiento(cls, rectificativa_data: Dict[str, Any]) -> int:
        """
        Registra el asiento contable para una factura rectificativa / abono bajo el PGC.
        Minoración de ingresos e IVA devengado:
            Debe: 70500000 (Prestación de Servicios) - Base Rectificada
            Debe: 47700021 (Hacienda Pública, IVA Repercutido) - Cuota IVA Rectificada
            Haber: 43000000 (Clientes) - Total Rectificado
        """
        rect_id = rectificativa_data.get("invoice_id", "R-MOCK")
        orig_id = rectificativa_data.get("original_invoice_id", "")
        date_str = rectificativa_data.get("date", datetime.now().strftime("%d/%m/%Y"))
        year = cls.extract_year_from_date(date_str)
        if cls.is_fiscal_year_closed(year):
            raise ValueError(f"El ejercicio fiscal {year} está cerrado. No se permiten nuevos asientos ni modificaciones.")

        base = abs(float(rectificativa_data.get("base_imponible", 0.0)))
        iva = abs(float(rectificativa_data.get("iva_amount", 0.0)))
        irpf = abs(float(rectificativa_data.get("irpf_amount", 0.0)))
        total = abs(float(rectificativa_data.get("total_amount", 0.0)))

        concept = f"Factura Rectificativa {rect_id} (Ref: {orig_id})"
        apuntes = [
            {"account_code": "70500000", "debe": base, "haber": 0.0}
        ]
        if iva > 0:
            apuntes.append({"account_code": "47700021", "debe": iva, "haber": 0.0})
        apuntes.append({"account_code": "43000000", "debe": 0.0, "haber": total})
        if irpf > 0:
            apuntes.append({"account_code": "47300000", "debe": 0.0, "haber": irpf})

        return cls._insert_journal_and_ledger(date_str, concept, apuntes)

    @classmethod
    def get_profit_and_loss_statement(cls, year: int, quarter: int = None) -> Dict[str, Any]:
        """
        Genera la Cuenta de Pérdidas y Ganancias (PyG / P&L) según el PGC español:
        - Grupo 7: Ingresos de explotación (Ventas 700, Prestación servicios 705, etc.)
        - Grupo 6: Gastos de explotación (Compras 600, Suministros/Servicios 629, etc.)
        - Resultado de Explotación (EBITDA / Beneficio Bruto) = Ingresos Grupo 7 - Gastos Grupo 6
        - Impuesto estimado (20% en IRPF estimación directa o 25% IS)
        - Resultado Neto del Ejercicio
        """
        ingresos_cuentas = {}
        gastos_cuentas = {}
        total_ingresos = 0.0
        total_gastos = 0.0

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.account_code, a.name as account_name, a.type as account_type,
                       l.debe, l.haber, j.entry_date
                FROM ledger_entries l
                JOIN pgc_accounts a ON l.account_code = a.code
                JOIN journal_entries j ON l.journal_entry_id = j.id
            """)
            rows = cursor.fetchall()

            for r in rows:
                entry_date_raw = r["entry_date"]
                entry_year = None
                entry_quarter = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        dt = datetime.strptime(entry_date_raw, fmt)
                        entry_year = dt.year
                        entry_quarter = (dt.month - 1) // 3 + 1
                        break
                    except Exception:
                        pass
                if entry_year is None:
                    if str(year) in entry_date_raw:
                        entry_year = year
                
                if entry_year != year:
                    continue
                if quarter is not None and entry_quarter is not None and entry_quarter != quarter:
                    continue

                code = r["account_code"]
                name = r["account_name"]
                atype = r["account_type"]
                debe = float(encryptor.decrypt(r["debe"]))
                haber = float(encryptor.decrypt(r["haber"]))

                # Ingresos (Grupo 7 o tipo ingreso)
                if code.startswith("7") or atype == "ingreso":
                    saldo = haber - debe
                    if code not in ingresos_cuentas:
                        ingresos_cuentas[code] = {"name": name, "saldo": 0.0}
                    ingresos_cuentas[code]["saldo"] += saldo
                    total_ingresos += saldo
                # Gastos (Grupo 6 o tipo gasto)
                elif code.startswith("6") or atype == "gasto":
                    saldo = debe - haber
                    if code not in gastos_cuentas:
                        gastos_cuentas[code] = {"name": name, "saldo": 0.0}
                    gastos_cuentas[code]["saldo"] += saldo
                    total_gastos += saldo

        resultado_explotacion = round(total_ingresos - total_gastos, 2)
        impuesto_estimado = round(resultado_explotacion * 0.20, 2) if resultado_explotacion > 0 else 0.0
        resultado_neto = round(resultado_explotacion - impuesto_estimado, 2)

        return {
            "año": year,
            "trimestre": quarter,
            "total_ingresos": round(total_ingresos, 2),
            "total_gastos": round(total_gastos, 2),
            "resultado_explotacion": resultado_explotacion,
            "impuesto_estimado": impuesto_estimado,
            "resultado_neto": resultado_neto,
            "desglose_ingresos": ingresos_cuentas,
            "desglose_gastos": gastos_cuentas
        }

    @classmethod
    def close_fiscal_year(cls, year: int) -> Dict[str, Any]:
        """
        Ejecuta el cierre oficial de ejercicio fiscal conforme al PGC:
        1. Asiento de Regularización a 31/12/{year}:
           Traspasa los saldos de ingresos (Grupo 7) y gastos (Grupo 6) a la cuenta 12900000 (Resultado del ejercicio).
        2. Asiento de Cierre a 31/12/{year}:
           Salda todas las cuentas de balance (Grupos 1-5 y 12900000) dejando todos los saldos a cero.
        3. Bloqueo del ejercicio en fiscal_year_status.
        4. Asiento de Apertura a 01/01/{year + 1}:
           Abre el ejercicio siguiente reestableciendo los saldos de balance.
        """
        if cls.is_fiscal_year_closed(year):
            raise ValueError(f"El ejercicio fiscal {year} ya está cerrado. No se puede volver a cerrar.")

        date_close = f"31/12/{year}"
        date_open = f"01/01/{year + 1}"

        # 1. Calcular saldos acumulados de todas las cuentas del ejercicio
        cuentas_saldos = {}
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.account_code, a.name as account_name, a.type as account_type, l.debe, l.haber, j.entry_date
                FROM ledger_entries l
                JOIN pgc_accounts a ON l.account_code = a.code
                JOIN journal_entries j ON l.journal_entry_id = j.id
            """)
            rows = cursor.fetchall()
            for r in rows:
                entry_year = cls.extract_year_from_date(r["entry_date"])
                if entry_year == year:
                    code = r["account_code"]
                    atype = r["account_type"]
                    debe = float(encryptor.decrypt(r["debe"]))
                    haber = float(encryptor.decrypt(r["haber"]))
                    if code not in cuentas_saldos:
                        cuentas_saldos[code] = {"name": r["account_name"], "type": atype, "debe": 0.0, "haber": 0.0}
                    cuentas_saldos[code]["debe"] += debe
                    cuentas_saldos[code]["haber"] += haber

        # --- PASO 1: REGULARIZACIÓN (Grupos 6 y 7 -> 12900000) ---
        apuntes_reg = []
        total_ingresos = 0.0
        total_gastos = 0.0

        for code, data in cuentas_saldos.items():
            if code.startswith("7") or data["type"] == "ingreso":
                saldo_haber = data["haber"] - data["debe"]
                if saldo_haber != 0:
                    apuntes_reg.append({
                        "account_code": code,
                        "debe": round(abs(saldo_haber), 2),
                        "haber": 0.0
                    })
                    total_ingresos += saldo_haber
            elif code.startswith("6") or data["type"] == "gasto":
                saldo_debe = data["debe"] - data["haber"]
                if saldo_debe != 0:
                    apuntes_reg.append({
                        "account_code": code,
                        "debe": 0.0,
                        "haber": round(abs(saldo_debe), 2)
                    })
                    total_gastos += saldo_debe

        resultado_ejercicio = round(total_ingresos - total_gastos, 2)
        if resultado_ejercicio > 0:
            apuntes_reg.append({
                "account_code": "12900000",
                "debe": 0.0,
                "haber": abs(resultado_ejercicio)
            })
        elif resultado_ejercicio < 0:
            apuntes_reg.append({
                "account_code": "12900000",
                "debe": abs(resultado_ejercicio),
                "haber": 0.0
            })

        asiento_reg_id = None
        if apuntes_reg:
            asiento_reg_id = cls._insert_journal_and_ledger(
                date_str=date_close,
                concept=f"Asiento de Regularización de Ingresos y Gastos - Ejercicio {year}",
                apuntes=apuntes_reg
            )

        # --- PASO 2: ASIENTO DE CIERRE (Cuentas de Balance) ---
        balance_saldos = {}
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.account_code, a.name as account_name, a.type as account_type, l.debe, l.haber, j.entry_date
                FROM ledger_entries l
                JOIN pgc_accounts a ON l.account_code = a.code
                JOIN journal_entries j ON l.journal_entry_id = j.id
            """)
            rows = cursor.fetchall()
            for r in rows:
                entry_year = cls.extract_year_from_date(r["entry_date"])
                if entry_year == year:
                    code = r["account_code"]
                    if not code.startswith("6") and not code.startswith("7"):
                        debe = float(encryptor.decrypt(r["debe"]))
                        haber = float(encryptor.decrypt(r["haber"]))
                        if code not in balance_saldos:
                            balance_saldos[code] = {"debe": 0.0, "haber": 0.0}
                        balance_saldos[code]["debe"] += debe
                        balance_saldos[code]["haber"] += haber

        apuntes_cierre = []
        apuntes_apertura = []

        for code, bdata in balance_saldos.items():
            diff = round(bdata["debe"] - bdata["haber"], 2)
            if diff > 0:
                apuntes_cierre.append({"account_code": code, "debe": 0.0, "haber": diff})
                apuntes_apertura.append({"account_code": code, "debe": diff, "haber": 0.0})
            elif diff < 0:
                apuntes_cierre.append({"account_code": code, "debe": abs(diff), "haber": 0.0})
                apuntes_apertura.append({"account_code": code, "debe": 0.0, "haber": abs(diff)})

        asiento_cierre_id = None
        asiento_apertura_id = None

        if apuntes_cierre:
            asiento_cierre_id = cls._insert_journal_and_ledger(
                date_str=date_close,
                concept=f"Asiento de Cierre del Ejercicio {year}",
                apuntes=apuntes_cierre
            )

        # --- PASO 3: MARCAR EJERCICIO COMO CERRADO ---
        now_str = datetime.now().isoformat()
        with _get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO fiscal_year_status (year, is_closed, closed_at)
                VALUES (?, 1, ?)
            """, (year, now_str))
            conn.commit()

        # --- PASO 4: ASIENTO DE APERTURA N+1 ---
        if apuntes_apertura:
            asiento_apertura_id = cls._insert_journal_and_ledger(
                date_str=date_open,
                concept=f"Asiento de Apertura del Ejercicio {year + 1}",
                apuntes=apuntes_apertura
            )

        return {
            "status": "ok",
            "year": year,
            "next_year": year + 1,
            "resultado_ejercicio": resultado_ejercicio,
            "regularizacion_asiento_id": asiento_reg_id,
            "cierre_asiento_id": asiento_cierre_id,
            "apertura_asiento_id": asiento_apertura_id,
            "closed_at": now_str,
            "message": f"Ejercicio fiscal {year} cerrado con éxito. Asientos de regularización, cierre y apertura del {year + 1} generados."
        }

    @classmethod
    def reopen_fiscal_year(cls, year: int) -> Dict[str, Any]:
        """
        Reabre un ejercicio fiscal previamente cerrado permitiendo ajustes contables.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            conn.execute(
                "UPDATE fiscal_year_status SET is_closed = 0 WHERE year = ?",
                (year,)
            )
            conn.commit()
        return {
            "status": "ok",
            "year": year,
            "message": f"Ejercicio fiscal {year} reabierto correctamente."
        }

    @classmethod
    def export_advisor_pack(cls, year: int) -> Dict[str, Any]:
        """
        Consolida el paquete fiscal y contable completo del ejercicio para la gestoría/asesor externo:
        - Libro Diario oficial
        - Balance de Situación (Activos vs Pasivos/Patrimonio)
        - Cuenta de Pérdidas y Ganancias (PyG)
        - Libros Registro de IVA (Facturas Expedidas y Recibidas)
        - Estado del ejercicio (Cerrado/Abierto)
        """
        return {
            "year": year,
            "generated_at": datetime.now().isoformat(),
            "is_closed": cls.is_fiscal_year_closed(year),
            "libro_diario": cls.get_libro_diario(year),
            "balance_situacion": cls.get_balance_situacion(year),
            "cuenta_perdidas_y_ganancias": cls.get_profit_and_loss_statement(year),
            "libros_registro_iva": cls.get_libros_iva(year)
        }



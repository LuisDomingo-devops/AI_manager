import json
from datetime import datetime
from typing import List, Dict, Any
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

class LedgerService:
    """
    Servicio de Contabilidad por Partida Doble (PGC) para Pymes.
    Gestiona la creación de Asientos contables (Libro Diario) y balances en tiempo real.
    """

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
        base = float(invoice_data.get("base_imponible", 0.0))
        iva = float(invoice_data.get("iva_amount", 0.0))
        total = float(invoice_data.get("total_amount", 0.0))

        concept = f"Factura {invoice_id}"

        with _get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Crear Asiento General (journal_entry)
            cursor.execute(
                "INSERT INTO journal_entries (entry_date, concept) VALUES (?, ?)",
                (date_str, encryptor.encrypt(concept))
            )
            journal_id = cursor.lastrowid

            # 2. Crear Apuntes Contables (ledger_entries)
            apuntes = []
            
            if category in ("ingreso", "income"):
                # CLIENTES (430) al DEBE
                apuntes.append((journal_id, "43000000", encryptor.encrypt(str(total)), encryptor.encrypt("0.0")))
                # INGRESOS (705) al HABER
                apuntes.append((journal_id, "70500000", encryptor.encrypt("0.0"), encryptor.encrypt(str(base))))
                # IVA REPERCUTIDO (477) al HABER
                if iva > 0:
                    apuntes.append((journal_id, "47700021", encryptor.encrypt("0.0"), encryptor.encrypt(str(iva))))
            else:
                # GASTOS (629) al DEBE
                apuntes.append((journal_id, "62900000", encryptor.encrypt(str(base)), encryptor.encrypt("0.0")))
                # IVA SOPORTADO (472) al DEBE
                if iva > 0:
                    apuntes.append((journal_id, "47200021", encryptor.encrypt(str(iva)), encryptor.encrypt("0.0")))
                # PROVEEDORES (400) al HABER
                apuntes.append((journal_id, "40000000", encryptor.encrypt("0.0"), encryptor.encrypt(str(total))))

            # Insertar apuntes
            cursor.executemany(
                "INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (?, ?, ?, ?)",
                apuntes
            )
            conn.commit()
            return journal_id

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

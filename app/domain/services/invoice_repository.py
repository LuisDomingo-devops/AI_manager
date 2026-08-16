import sqlite3
import hashlib
from typing import Optional, Dict, Any, Tuple
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

class InvoiceRepository:
    @staticmethod
    def save(invoice_db_data: Dict[str, Any], existing_id_db: Optional[int] = None) -> int:
        """
        Saves or updates an invoice in the local SQLite database.
        Automatically calculates blind_index for duplicate checks.
        """
        # Calculate blind_index
        target_invoice_id = str(invoice_db_data.get("invoice_id", "")).strip().upper()
        target_issuer_nif = str(invoice_db_data.get("issuer_nif", "")).strip().upper()
        
        blind_index = None
        if target_invoice_id and target_issuer_nif:
            blind_raw = f"{target_invoice_id}:{target_issuer_nif}".encode("utf-8")
            blind_index = hashlib.sha256(blind_raw).hexdigest()

        conn = _get_connection()
        try:
            cursor = conn.cursor()

            # Verificar si el ejercicio fiscal está cerrado
            year = int(invoice_db_data.get("year", 2026))
            try:
                cursor.execute("SELECT is_closed FROM fiscal_year_status WHERE year = ?", (year,))
                fy_row = cursor.fetchone()
                if fy_row and fy_row["is_closed"]:
                    raise ValueError(f"No se pueden emitir ni modificar facturas en el ejercicio fiscal cerrado {year}.")
            except sqlite3.OperationalError:
                pass
            
            # If inserting and no existing_id_db is provided, check for duplicates
            if not existing_id_db and blind_index:
                cursor.execute("SELECT id FROM invoices WHERE blind_index = ? LIMIT 1", (blind_index,))
                row = cursor.fetchone()
                if row:
                    raise ValueError(f"Factura duplicada detectada: {target_invoice_id} del emisor {target_issuer_nif}")

            if existing_id_db:
                cursor.execute("""
                    UPDATE invoices SET
                        invoice_id = ?, date = ?, issuer_name = ?, issuer_nif = ?, receiver_name = ?, receiver_nif = ?,
                        base_imponible = ?, iva_rate = ?, iva_amount = ?, irpf_rate = ?, irpf_amount = ?, total_amount = ?,
                        category = ?, quarter = ?, year = ?, file_path = ?, status = ?, concept = ?, blind_index = ?
                    WHERE id = ?
                """, (
                    encryptor.encrypt(invoice_db_data["invoice_id"]),
                    encryptor.encrypt(invoice_db_data["date"]),
                    encryptor.encrypt(invoice_db_data["issuer_name"]),
                    encryptor.encrypt(invoice_db_data["issuer_nif"]),
                    encryptor.encrypt(invoice_db_data["receiver_name"]),
                    encryptor.encrypt(invoice_db_data["receiver_nif"]),
                    encryptor.encrypt(str(invoice_db_data["base_imponible"])),
                    encryptor.encrypt(str(invoice_db_data["iva_rate"])),
                    encryptor.encrypt(str(invoice_db_data["iva_amount"])),
                    encryptor.encrypt(str(invoice_db_data["irpf_rate"])),
                    encryptor.encrypt(str(invoice_db_data["irpf_amount"])),
                    encryptor.encrypt(str(invoice_db_data["total_amount"])),
                    invoice_db_data["category"],
                    invoice_db_data["quarter"],
                    invoice_db_data["year"],
                    encryptor.encrypt(invoice_db_data.get("file_path", "")),
                    invoice_db_data.get("status", "firmada"),
                    encryptor.encrypt(invoice_db_data.get("concept", "")),
                    blind_index,
                    existing_id_db
                ))
                invoice_db_id = existing_id_db
            else:
                cursor.execute("""
                    INSERT INTO invoices (
                        invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                        base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount,
                        category, quarter, year, file_path, status, concept, blind_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    encryptor.encrypt(invoice_db_data["invoice_id"]),
                    encryptor.encrypt(invoice_db_data["date"]),
                    encryptor.encrypt(invoice_db_data["issuer_name"]),
                    encryptor.encrypt(invoice_db_data["issuer_nif"]),
                    encryptor.encrypt(invoice_db_data["receiver_name"]),
                    encryptor.encrypt(invoice_db_data["receiver_nif"]),
                    encryptor.encrypt(str(invoice_db_data["base_imponible"])),
                    encryptor.encrypt(str(invoice_db_data["iva_rate"])),
                    encryptor.encrypt(str(invoice_db_data["iva_amount"])),
                    encryptor.encrypt(str(invoice_db_data["irpf_rate"])),
                    encryptor.encrypt(str(invoice_db_data["irpf_amount"])),
                    encryptor.encrypt(str(invoice_db_data["total_amount"])),
                    invoice_db_data["category"],
                    invoice_db_data["quarter"],
                    invoice_db_data["year"],
                    encryptor.encrypt(invoice_db_data.get("file_path", "")),
                    invoice_db_data.get("status", "firmada"),
                    encryptor.encrypt(invoice_db_data.get("concept", "")),
                    blind_index
                ))
                invoice_db_id = cursor.lastrowid
            conn.commit()
            return invoice_db_id
        finally:
            conn.close()

    @staticmethod
    def find_existing_invoice_data(invoice_id: str, client_name: str, client_nif: str, amount: float, concept: str) -> Tuple[Optional[int], Optional[str], str, str, float, str]:
        """
        Looks up an invoice by business fields, matching the logic inside billing_tools.py.
        """
        existing_id_db = None
        existing_file_path = None
        if invoice_id:
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, invoice_id, receiver_name, receiver_nif, base_imponible, concept, file_path FROM invoices")
                rows = cursor.fetchall()
                for r in rows:
                    try:
                        dec_id = encryptor.decrypt(r["invoice_id"])
                        if dec_id.upper() == invoice_id.upper():
                            existing_id_db = r["id"]
                            existing_file_path = encryptor.decrypt(r["file_path"])
                            
                            if not client_name or client_name.lower().strip() in ("desconocido", "pendiente", "cliente genérico", "cliente desconocido"):
                                dec_client_name = encryptor.decrypt(r["receiver_name"])
                                if dec_client_name and dec_client_name.lower().strip() not in ("desconocido", "pendiente", "cliente genérico", "cliente desconocido"):
                                    client_name = dec_client_name
                            
                            if not client_nif or client_nif.lower().strip() in ("desconocido", "pendiente", "sin nif", "nif_desconocido", "nif desconocido"):
                                dec_client_nif = encryptor.decrypt(r["receiver_nif"])
                                if dec_client_nif and dec_client_nif.lower().strip() not in ("desconocido", "pendiente", "sin nif", "nif_desconocido", "nif desconocido"):
                                    client_nif = dec_client_nif
                            
                            if not amount or float(amount) <= 0.0:
                                dec_amount = float(encryptor.decrypt(r["base_imponible"]))
                                if dec_amount > 0.0:
                                    amount = dec_amount
                                    
                            if not concept or concept.lower().strip() in ("desconocido", "pendiente", "concepto desconocido", "sin concepto"):
                                dec_concept = encryptor.decrypt(r["concept"])
                                if dec_concept and dec_concept.lower().strip() not in ("desconocido", "pendiente", "concepto desconocido", "sin concepto"):
                                    concept = dec_concept
                            break
                    except Exception:
                        pass
            finally:
                conn.close()
        return existing_id_db, existing_file_path, client_name, client_nif, amount, concept

    @staticmethod
    def find_invoice_by_id(invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Finds an invoice by its user-facing ID string.
        """
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                       base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount, status, concept, file_path
                FROM invoices
            """)
            rows = cursor.fetchall()
            for r in rows:
                try:
                    dec_id = encryptor.decrypt(r["invoice_id"])
                    if dec_id.upper() == invoice_id.upper():
                        return {
                            "db_id": r["id"],
                            "invoice_id": dec_id,
                            "date": encryptor.decrypt(r["date"]) if r["date"] else "",
                            "issuer_name": encryptor.decrypt(r["issuer_name"]) if r["issuer_name"] else "",
                            "issuer_nif": encryptor.decrypt(r["issuer_nif"]) if r["issuer_nif"] else "",
                            "receiver_name": encryptor.decrypt(r["receiver_name"]) if r["receiver_name"] else "",
                            "receiver_nif": encryptor.decrypt(r["receiver_nif"]) if r["receiver_nif"] else "",
                            "base_imponible": float(encryptor.decrypt(r["base_imponible"])) if r["base_imponible"] else 0.0,
                            "iva_rate": float(encryptor.decrypt(r["iva_rate"])) if r["iva_rate"] else 21.0,
                            "iva_amount": float(encryptor.decrypt(r["iva_amount"])) if r["iva_amount"] else 0.0,
                            "irpf_rate": float(encryptor.decrypt(r["irpf_rate"])) if r["irpf_rate"] else 0.0,
                            "irpf_amount": float(encryptor.decrypt(r["irpf_amount"])) if r["irpf_amount"] else 0.0,
                            "total_amount": float(encryptor.decrypt(r["total_amount"])) if r["total_amount"] else 0.0,
                            "status": r["status"],
                            "concept": encryptor.decrypt(r["concept"]) if r["concept"] else "",
                            "file_path": encryptor.decrypt(r["file_path"]) if r["file_path"] else ""
                        }
                except Exception:
                    pass
            return None
        finally:
            conn.close()

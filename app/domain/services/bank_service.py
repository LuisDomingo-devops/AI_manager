import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

class BankService:
    """
    Servicio de Conciliación Bancaria Automática y Manual para Alfonso.
    Soporta la lectura de ficheros Norma 43, registros manuales, integración multibanco y algoritmo de matching.
    """

    @classmethod
    def add_connection(cls, alias: str, provider: str, bank_name: str, iban: str, credentials_json: str = "") -> int:
        """
        Añade una nueva cuenta bancaria conectada a la base de datos.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bank_connections (alias, provider, bank_name, iban, credentials, status)
                VALUES (?, ?, ?, ?, ?, 'active')
            """, (
                alias,
                provider,
                bank_name,
                encryptor.encrypt(iban) if iban else None,
                encryptor.encrypt(credentials_json) if credentials_json else None
            ))
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def list_connections(cls) -> List[Dict[str, Any]]:
        """
        Retorna la lista de todas las cuentas bancarias conectadas.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, alias, provider, bank_name, iban, status, last_sync_at FROM bank_connections")
            rows = cursor.fetchall()
            connections = []
            for r in rows:
                connections.append({
                    "id": r["id"],
                    "alias": r["alias"],
                    "provider": r["provider"],
                    "bank_name": r["bank_name"],
                    "iban": encryptor.decrypt(r["iban"]) if r["iban"] else "",
                    "status": r["status"],
                    "last_sync_at": r["last_sync_at"]
                })
            return connections

    @classmethod
    def delete_connection(cls, connection_id: int) -> None:
        """
        Elimina una conexión bancaria y desasocia sus movimientos.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bank_connections WHERE id = ?", (connection_id,))
            cursor.execute("UPDATE bank_movements SET connection_id = NULL WHERE connection_id = ?", (connection_id,))
            conn.commit()

    @classmethod
    def sync_connection(cls, connection_id: int) -> int:
        """
        Descarga movimientos en tiempo real desde el proveedor de la cuenta.
        """
        from app.adapters.bank_providers import BankProviderFactory
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, provider, credentials, last_sync_at FROM bank_connections WHERE id = ?", (connection_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Conexión bancaria con ID {connection_id} no encontrada.")
            
            provider_name = row["provider"]
            creds_cipher = row["credentials"]
            creds_dict = {}
            if creds_cipher:
                try:
                    creds_dict = json.loads(encryptor.decrypt(creds_cipher))
                except Exception:
                    pass
            
            provider = BankProviderFactory.get_provider(provider_name)
            
            # Rango de fechas por defecto: últimos 30 días
            start_dt = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y") if "timedelta" in globals() else (datetime.now().replace(day=1)).strftime("%d/%m/%Y")
            # fallback robusto para timedelta
            try:
                from datetime import timedelta
                start_dt = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")
            except Exception:
                pass
            
            account_id = creds_dict.get("account_id", "default_account")
            movements = provider.fetch_transactions(creds_dict, account_id, start_dt)
            
            # Obtener movimientos existentes para esta conexión para evitar duplicados (con cifrado aleatorio)
            cursor.execute("SELECT movement_date, amount, concept, reference FROM bank_movements WHERE connection_id = ?", (connection_id,))
            existing_rows = cursor.fetchall()
            existing_movements = []
            for r in existing_rows:
                existing_movements.append({
                    "date": r["movement_date"],
                    "amount": r["amount"],
                    "concept": encryptor.decrypt(r["concept"]),
                    "reference": encryptor.decrypt(r["reference"]) if r["reference"] else ""
                })

            count = 0
            for mov in movements:
                is_duplicate = False
                for ext in existing_movements:
                    if (ext["date"] == mov["date"] and 
                        abs(ext["amount"] - mov["amount"]) < 0.01 and 
                        ext["concept"] == mov["concept"] and 
                        ext["reference"] == mov.get("reference", "")):
                        is_duplicate = True
                        break
                
                if is_duplicate:
                    continue
                
                cursor.execute("""
                    INSERT INTO bank_movements (movement_date, concept, amount, reference, reconciled, connection_id)
                    VALUES (?, ?, ?, ?, 0, ?)
                """, (
                    mov["date"],
                    encryptor.encrypt(mov["concept"]),
                    mov["amount"],
                    encryptor.encrypt(mov.get("reference", "")),
                    connection_id
                ))
                count += 1
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE bank_connections SET last_sync_at = ? WHERE id = ?", (now_str, connection_id))
            conn.commit()
            return count

    @classmethod
    def add_manual_movement(cls, date_str: str, concept: str, amount: float, reference: str = "", connection_id: int = None) -> int:
        """
        Inserta manualmente un movimiento bancario en la base de datos (cifrando sensibles).
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bank_movements (movement_date, concept, amount, reference, reconciled, connection_id)
                VALUES (?, ?, ?, ?, 0, ?)
            """, (
                date_str,
                encryptor.encrypt(concept),
                amount,
                encryptor.encrypt(reference),
                connection_id
            ))
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def parse_norma43_file(cls, filepath: str, connection_id: int = None) -> int:
        """
        Parser básico de archivos de extracto bancario Norma 43 (estándar español).
        Lee registros tipo 22 (movimiento principal) y extrae importe, signo, fecha y concepto.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Archivo Norma 43 no encontrado: {filepath}")

        count = 0
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        with _get_connection() as conn:
            cursor = conn.cursor()
            for line in lines:
                if line.startswith("22"):
                    try:
                        day = line[10:12]
                        month = line[12:14]
                        year = "20" + line[14:16]
                        date_str = f"{day}/{month}/{year}"

                        sign_code = line[27] # '1' es Debe (Gasto/Negativo), '2' es Haber (Cobro/Positivo)
                        raw_amount = float(line[28:42]) / 100.0
                        amount = -raw_amount if sign_code == "1" else raw_amount

                        concept = line[52:90].strip()
                        reference = line[42:52].strip()

                        cursor.execute("""
                            INSERT INTO bank_movements (movement_date, concept, amount, reference, reconciled, connection_id)
                            VALUES (?, ?, ?, ?, 0, ?)
                        """, (
                            date_str,
                            encryptor.encrypt(concept or "Movimiento extracto"),
                            amount,
                            encryptor.encrypt(reference),
                            connection_id
                        ))
                        count += 1
                    except Exception:
                        continue
            conn.commit()
        return count

    @classmethod
    def reconcile_matching_algorithm(cls) -> List[Dict[str, Any]]:
        """
        Algoritmo de Matching: Empareja movimientos de banco no conciliados con facturas no conciliadas.
        """
        reconciled_pairs = []

        with _get_connection() as conn:
            cursor = conn.cursor()

            # 1. Obtener movimientos bancarios no conciliados
            cursor.execute("SELECT id, movement_date, concept, amount, reference, connection_id FROM bank_movements WHERE reconciled = 0")
            movements = cursor.fetchall()

            # 2. Obtener IDs de facturas ya conciliadas para no duplicar
            cursor.execute("SELECT invoice_id FROM bank_movements WHERE reconciled = 1 AND invoice_id IS NOT NULL")
            reconciled_invoice_ids = {r["invoice_id"] for r in cursor.fetchall()}

            # 3. Obtener todas las facturas de la base de datos
            cursor.execute("SELECT id, invoice_id, date, issuer_name, receiver_name, total_amount, category, file_path FROM invoices")
            invoices_raw = cursor.fetchall()

            invoices = []
            for inv in invoices_raw:
                inv_id = encryptor.decrypt(inv["invoice_id"])
                if inv_id in reconciled_invoice_ids:
                    continue
                
                invoices.append({
                    "db_id": inv["id"],
                    "invoice_id": inv_id,
                    "date": encryptor.decrypt(inv["date"]),
                    "issuer_name": encryptor.decrypt(inv["issuer_name"]),
                    "receiver_name": encryptor.decrypt(inv["receiver_name"]),
                    "total_amount": float(encryptor.decrypt(inv["total_amount"])),
                    "category": inv["category"],
                    "file_path": encryptor.decrypt(inv["file_path"]) if inv["file_path"] else None
                })

            for mov in movements:
                mov_id = mov["id"]
                mov_date_str = mov["movement_date"]
                mov_amount = mov["amount"]
                mov_concept = encryptor.decrypt(mov["concept"]).lower()
                mov_ref = encryptor.decrypt(mov["reference"]).lower()

                try:
                    mov_date = datetime.strptime(mov_date_str, "%d/%m/%Y")
                except ValueError:
                    continue

                best_match = None
                
                for inv in invoices:
                    if mov_amount > 0 and inv["category"] not in ("ingreso", "income"):
                        continue
                    if mov_amount < 0 and inv["category"] not in ("gasto", "expense"):
                        continue

                    if abs(abs(mov_amount) - inv["total_amount"]) > 0.01:
                        continue

                    try:
                        inv_date = datetime.strptime(inv["date"], "%d/%m/%Y")
                    except ValueError:
                        continue

                    date_diff = abs((mov_date - inv_date).days)
                    if date_diff > 15:
                        continue

                    score = 0
                    inv_id_lower = inv["invoice_id"].lower()
                    
                    if inv_id_lower in mov_concept or inv_id_lower in mov_ref:
                        score += 10
                    
                    partner = inv["receiver_name"] if inv["category"] in ("ingreso", "income") else inv["issuer_name"]
                    partner_words = [w for w in partner.lower().split() if len(w) > 3]
                    for w in partner_words:
                        if w in mov_concept:
                            score += 5

                    if score >= 0:
                        if best_match is None or score > best_match["score"]:
                            best_match = {"invoice": inv, "score": score}

                if best_match:
                    matched_inv = best_match["invoice"]
                    
                    cursor.execute("""
                        UPDATE bank_movements 
                        SET reconciled = 1, invoice_id = ? 
                        WHERE id = ?
                    """, (matched_inv["invoice_id"], mov_id))
                    
                    reconciled_pairs.append({
                        "movement_id": mov_id,
                        "movement_concept": encryptor.decrypt(mov["concept"]),
                        "movement_amount": mov_amount,
                        "invoice_id": matched_inv["invoice_id"],
                        "invoice_total": matched_inv["total_amount"],
                        "score": best_match["score"]
                    })

                    if matched_inv["category"] in ("ingreso", "income") and matched_inv.get("file_path"):
                        try:
                            import shutil
                            src_path = Path(matched_inv["file_path"])
                            if src_path.exists() and ("Facturas_Pendientes_Cobro" in str(src_path) or "facturas pendientes" in str(src_path)):
                                now_dt = datetime.now()
                                year_str = str(now_dt.year)
                                quarter_str = f"T{(now_dt.month - 1) // 3 + 1}"
                                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                                    try:
                                        inv_dt = datetime.strptime(matched_inv["date"], fmt)
                                        year_str = str(inv_dt.year)
                                        quarter_str = f"T{(inv_dt.month - 1) // 3 + 1}"
                                        break
                                    except Exception:
                                        pass
                                
                                dest_dir = Path(__file__).resolve().parents[3] / "data" / "archivo fiscal" / year_str / quarter_str / "Ingresos"
                                dest_dir.mkdir(parents=True, exist_ok=True)
                                dest_file = dest_dir / src_path.name
                                
                                shutil.move(str(src_path), str(dest_file))
                                cursor.execute("UPDATE invoices SET file_path = ? WHERE id = ?", (encryptor.encrypt(str(dest_file)), matched_inv["db_id"]))
                        except Exception:
                            pass
                    
                    invoices.remove(matched_inv)

            conn.commit()
        return reconciled_pairs

    @classmethod
    def get_unreconciled_report(cls, connection_id: int = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retorna los movimientos bancarios y facturas pendientes de conciliar.
        """
        unreconciled_movements = []
        unreconciled_invoices = []

        with _get_connection() as conn:
            cursor = conn.cursor()

            # 1. Movimientos sin conciliar
            if connection_id is not None:
                cursor.execute("""
                    SELECT m.id, m.movement_date, m.concept, m.amount, c.alias 
                    FROM bank_movements m
                    LEFT JOIN bank_connections c ON m.connection_id = c.id
                    WHERE m.reconciled = 0 AND m.connection_id = ?
                """, (connection_id,))
            else:
                cursor.execute("""
                    SELECT m.id, m.movement_date, m.concept, m.amount, c.alias 
                    FROM bank_movements m
                    LEFT JOIN bank_connections c ON m.connection_id = c.id
                    WHERE m.reconciled = 0
                """)
            
            movs = cursor.fetchall()
            for m in movs:
                unreconciled_movements.append({
                    "id": m["id"],
                    "fecha": m["movement_date"],
                    "concepto": encryptor.decrypt(m["concept"]),
                    "importe": m["amount"],
                    "cuenta": m["alias"] or "Sin Vincular"
                })

            # 2. Facturas sin conciliar
            cursor.execute("SELECT invoice_id FROM bank_movements WHERE reconciled = 1 AND invoice_id IS NOT NULL")
            reconciled_invoice_ids = {r["invoice_id"] for r in cursor.fetchall()}

            cursor.execute("SELECT invoice_id, date, issuer_name, receiver_name, total_amount, category FROM invoices")
            invs = cursor.fetchall()
            for inv in invs:
                inv_id = encryptor.decrypt(inv["invoice_id"])
                if inv_id in reconciled_invoice_ids:
                    continue
                unreconciled_invoices.append({
                    "invoice_id": inv_id,
                    "fecha": encryptor.decrypt(inv["date"]),
                    "emisor": encryptor.decrypt(inv["issuer_name"]),
                    "receptor": encryptor.decrypt(inv["receiver_name"]),
                    "total": float(encryptor.decrypt(inv["total_amount"])),
                    "tipo": inv["category"]
                })

        return {
            "movimientos_banco_pendientes": unreconciled_movements,
            "facturas_pendientes": unreconciled_invoices
        }

    @classmethod
    def get_subscription_status(cls) -> Dict[str, Any]:
        """
        Retorna la información de suscripción y uso de transferencias del mes actual.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tier, billing_cycle_start, extra_transfer_fee FROM subscription_status LIMIT 1")
            row = cursor.fetchone()
            if not row:
                import datetime
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                cursor.execute("INSERT INTO subscription_status (tier, billing_cycle_start, extra_transfer_fee) VALUES ('free', ?, 0.50)", (today_str,))
                conn.commit()
                tier = "free"
                cycle_start = today_str
                extra_fee = 0.50
            else:
                tier = row["tier"]
                cycle_start = row["billing_cycle_start"]
                extra_fee = row["extra_transfer_fee"]

            limits = {
                "free": 0,
                "premium_10": 10,
                "premium_20": 20,
                "premium_50": 50
            }
            limit = limits.get(tier, 0)

            cursor.execute("SELECT COUNT(*), SUM(extra_charge) FROM bank_transfers WHERE transfer_date >= ?", (cycle_start,))
            count_row = cursor.fetchone()
            used = count_row[0] or 0
            extra_charges = count_row[1] or 0.0

            return {
                "tier": tier,
                "billing_cycle_start": cycle_start,
                "limit": limit,
                "used": used,
                "remaining": max(0, limit - used),
                "extra_charge_per_transfer": extra_fee,
                "accumulated_extra_charges": extra_charges
            }

    @classmethod
    def update_subscription_tier(cls, tier: str) -> None:
        """
        Actualiza el nivel de suscripción del usuario.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscription_status SET tier = ?", (tier,))
            conn.commit()

    @classmethod
    def list_transfers(cls) -> List[Dict[str, Any]]:
        """
        Retorna el historial de transferencias realizadas.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.transfer_date, t.recipient_name, t.recipient_iban, t.amount, t.concept, t.status, t.extra_charge, c.alias 
                FROM bank_transfers t
                LEFT JOIN bank_connections c ON t.connection_id = c.id
                ORDER BY t.id DESC
            """)
            rows = cursor.fetchall()
            transfers = []
            for r in rows:
                transfers.append({
                    "id": r["id"],
                    "fecha": r["transfer_date"],
                    "destinatario": r["recipient_name"],
                    "iban": r["recipient_iban"],
                    "importe": r["amount"],
                    "concepto": r["concept"],
                    "estado": r["status"],
                    "cargo_extra": r["extra_charge"],
                    "cuenta_origen": r["alias"] or "Sin Vincular"
                })
            return transfers

    @classmethod
    def initiate_transfer(cls, connection_id: int, recipient_name: str, recipient_iban: str, amount: float, concept: str) -> Dict[str, Any]:
        """
        Inicia y registra una transferencia bancaria simulando el proceso PIS de Open Banking.
        Aplica cobros adicionales si excede el cupo contratado.
        """
        status = cls.get_subscription_status()
        
        extra_charge = 0.0
        if status["tier"] == "free":
            extra_charge = status["extra_charge_per_transfer"]
        elif status["used"] >= status["limit"]:
            extra_charge = status["extra_charge_per_transfer"]

        import datetime
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bank_transfers (transfer_date, recipient_name, recipient_iban, amount, concept, status, extra_charge, connection_id)
                VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
            """, (
                today_str,
                recipient_name,
                recipient_iban,
                amount,
                concept,
                extra_charge,
                connection_id
            ))
            
            cursor.execute("""
                INSERT INTO bank_movements (movement_date, concept, amount, reference, reconciled, connection_id)
                VALUES (?, ?, ?, 'TRANSFERENCIA', 0, ?)
            """, (
                datetime.datetime.now().strftime("%d/%m/%Y"),
                encryptor.encrypt(f"Transferencia a {recipient_name}: {concept}"),
                -amount,
                connection_id
            ))
            conn.commit()

        return {
            "status": "success",
            "message": "Transferencia iniciada correctamente.",
            "extra_charge": extra_charge
        }

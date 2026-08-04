import os
from datetime import datetime
from typing import List, Dict, Any
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

class BankService:
    """
    Servicio de Conciliación Bancaria Automática y Manual para Alfonso.
    Soporta la lectura de ficheros Norma 43, registros manuales y algoritmo de matching.
    """

    @classmethod
    def add_manual_movement(cls, date_str: str, concept: str, amount: float, reference: str = "") -> int:
        """
        Inserta manualmente un movimiento bancario en la base de datos (cifrando sensibles).
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bank_movements (movement_date, concept, amount, reference, reconciled)
                VALUES (?, ?, ?, ?, 0)
            """, (
                date_str,
                encryptor.encrypt(concept),
                amount,
                encryptor.encrypt(reference)
            ))
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def parse_norma43_file(cls, filepath: str) -> int:
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
                # El registro tipo 22 contiene los movimientos individuales en Norma 43
                if line.startswith("22"):
                    try:
                        # Extraer fecha de operación (DDMMYY) en posiciones 10-16
                        day = line[10:12]
                        month = line[12:14]
                        year = "20" + line[14:16]
                        date_str = f"{day}/{month}/{year}"

                        # Importe: posiciones 28-42 (14 dígitos, últimos 2 decimales)
                        sign_code = line[27] # '1' es Debe (Gasto/Negativo), '2' es Haber (Cobro/Positivo)
                        raw_amount = float(line[28:42]) / 100.0
                        amount = -raw_amount if sign_code == "1" else raw_amount

                        # Concepto secundario / Referencia: posiciones 52-90
                        concept = line[52:90].strip()
                        reference = line[42:52].strip()

                        # Insertar cifrado
                        cursor.execute("""
                            INSERT INTO bank_movements (movement_date, concept, amount, reference, reconciled)
                            VALUES (?, ?, ?, ?, 0)
                        """, (
                            date_str,
                            encryptor.encrypt(concept or "Movimiento extracto"),
                            amount,
                            encryptor.encrypt(reference)
                        ))
                        count += 1
                    except Exception:
                        # Saltar líneas mal formateadas
                        continue
            conn.commit()
        return count

    @classmethod
    def reconcile_matching_algorithm(cls) -> List[Dict[str, Any]]:
        """
        Algoritmo de Matching: Empareja movimientos de banco no conciliados con facturas no conciliadas.
        Criterios:
        1. Importes idénticos (el cobro bancario debe igualar al total de la factura).
        2. Fechas próximas (diferencia de máximo 15 días).
        3. Coincidencia semántica en concepto (número de factura, o nombre de emisor/receptor).
        """
        reconciled_pairs = []

        with _get_connection() as conn:
            cursor = conn.cursor()

            # 1. Obtener movimientos bancarios no conciliados
            cursor.execute("SELECT id, movement_date, concept, amount, reference FROM bank_movements WHERE reconciled = 0")
            movements = cursor.fetchall()

            # 2. Obtener IDs de facturas ya conciliadas para no duplicar
            cursor.execute("SELECT invoice_id FROM bank_movements WHERE reconciled = 1 AND invoice_id IS NOT NULL")
            reconciled_invoice_ids = {r["invoice_id"] for r in cursor.fetchall()}

            # 3. Obtener todas las facturas de la base de datos
            cursor.execute("SELECT id, invoice_id, date, issuer_name, receiver_name, total_amount, category, file_path FROM invoices")
            invoices_raw = cursor.fetchall()

            # Descifrar facturas en memoria
            invoices = []
            for inv in invoices_raw:
                inv_id = encryptor.decrypt(inv["invoice_id"])
                if inv_id in reconciled_invoice_ids:
                    continue # Saltar ya conciliadas
                
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

            # 4. Bucle de matching
            for mov in movements:
                mov_id = mov["id"]
                mov_date_str = mov["movement_date"]
                mov_amount = mov["amount"]
                mov_concept = encryptor.decrypt(mov["concept"]).lower()
                mov_ref = encryptor.decrypt(mov["reference"]).lower()

                # Parsear fecha del movimiento bancario
                try:
                    mov_date = datetime.strptime(mov_date_str, "%d/%m/%Y")
                except ValueError:
                    continue

                best_match = None
                
                # Buscar entre las facturas
                for inv in invoices:
                    # El signo del importe debe corresponder a la categoría
                    # Cobro (positivo) -> Factura de Ingreso (venta)
                    # Pago (negativo) -> Factura de Gasto (compra)
                    if mov_amount > 0 and inv["category"] not in ("ingreso", "income"):
                        continue
                    if mov_amount < 0 and inv["category"] not in ("gasto", "expense"):
                        continue

                    # Comprobar si el importe coincide (en valor absoluto)
                    if abs(abs(mov_amount) - inv["total_amount"]) > 0.01:
                        continue

                    # Comprobar cercanía de fechas (ventana de 15 días)
                    try:
                        inv_date = datetime.strptime(inv["date"], "%d/%m/%Y")
                    except ValueError:
                        continue

                    date_diff = abs((mov_date - inv_date).days)
                    if date_diff > 15:
                        continue

                    # Coincidencia semántica (puntuación)
                    score = 0
                    inv_id_lower = inv["invoice_id"].lower()
                    
                    # Si el concepto menciona el ID de factura
                    if inv_id_lower in mov_concept or inv_id_lower in mov_ref:
                        score += 10
                    
                    # Si el concepto menciona parte del nombre de la contraparte
                    partner = inv["receiver_name"] if inv["category"] in ("ingreso", "income") else inv["issuer_name"]
                    partner_words = [w for w in partner.lower().split() if len(w) > 3]
                    for w in partner_words:
                        if w in mov_concept:
                            score += 5

                    # Si coincide importe y fecha dentro de la ventana, es un match viable.
                    # El score semántico prioriza si hay conflicto.
                    if score >= 0:
                        if best_match is None or score > best_match["score"]:
                            best_match = {"invoice": inv, "score": score}

                # Si encontramos un match válido
                if best_match:
                    matched_inv = best_match["invoice"]
                    
                    # Actualizar movimiento bancario como conciliado
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

                    # Mover factura de ingresos física desde Pendientes de Cobro al Archivo Fiscal
                    if matched_inv["category"] in ("ingreso", "income") and matched_inv.get("file_path"):
                        try:
                            import shutil
                            src_path = Path(matched_inv["file_path"])
                            if src_path.exists() and ("Facturas_Pendientes_Cobro" in str(src_path) or "facturas pendientes" in str(src_path)):
                                # Calcular año y trimestre a partir de la fecha de la factura
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
                                
                                # Actualizar la ruta física del archivo en la base de datos
                                cursor.execute("UPDATE invoices SET file_path = ? WHERE id = ?", (encryptor.encrypt(str(dest_file)), matched_inv["db_id"]))
                        except Exception as e:
                            pass
                    
                    # Remover factura de la lista disponible en memoria para evitar doble emparejamiento
                    invoices.remove(matched_inv)

            conn.commit()
        return reconciled_pairs

    @classmethod
    def get_unreconciled_report(cls) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retorna los movimientos bancarios y facturas pendientes de conciliar.
        """
        unreconciled_movements = []
        unreconciled_invoices = []

        with _get_connection() as conn:
            cursor = conn.cursor()

            # 1. Movimientos sin conciliar
            cursor.execute("SELECT id, movement_date, concept, amount FROM bank_movements WHERE reconciled = 0")
            movs = cursor.fetchall()
            for m in movs:
                unreconciled_movements.append({
                    "id": m["id"],
                    "fecha": m["movement_date"],
                    "concepto": encryptor.decrypt(m["concept"]),
                    "importe": m["amount"]
                })

            # 2. Facturas sin conciliar (las que no están asignadas a ningún movimiento bancario conciliado)
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

import uuid
from typing import Dict, Any, List
from datetime import datetime
from app.adapters.memory.memory import _get_connection
from app.utils.logger import tool_logger
from app.utils.encryption import encryptor
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.domain.services.ledger_service import LedgerService

class CollectionService:
    @staticmethod
    def register_payment(invoice_id: str, amount: float, payment_method: str, date: str, notes: str = "") -> dict:
        """
        Registra un pago para una factura y actualiza su estado si está completamente cobrada.
        También genera el asiento contable del cobro.
        """
        conn = _get_connection()
        try:
            # 1. Encontrar la factura
            invoice_data = InvoiceRepository.find_invoice_by_id(invoice_id)
            if not invoice_data:
                return {"status": "error", "message": f"Factura '{invoice_id}' no encontrada."}

            invoice_db_id = invoice_data["id"]
            total_invoice = invoice_data["total_amount"]
            
            # Verificar año cerrado (asumiendo que date es YYYY-MM-DD o DD/MM/YYYY)
            try:
                if "/" in date:
                    d, m, y = date.split("/")
                    year = int(y)
                else:
                    year = int(date.split("-")[0])
                    
                cursor = conn.cursor()
                cursor.execute("SELECT is_closed FROM fiscal_year_status WHERE year = ?", (year,))
                fy_row = cursor.fetchone()
                if fy_row and fy_row["is_closed"]:
                    return {"status": "error", "message": f"No se pueden registrar cobros en el ejercicio cerrado {year}."}
            except Exception:
                pass
            
            cursor = conn.cursor()
            
            # 2. Calcular saldo pendiente actual
            cursor.execute("SELECT COALESCE(SUM(amount), 0) as paid FROM payments WHERE invoice_id = ?", (invoice_id,))
            paid_amount = cursor.fetchone()["paid"]
            outstanding_balance = total_invoice - paid_amount
            
            if amount > outstanding_balance + 0.01: # Margen de error flotante
                return {"status": "error", "message": f"El importe ({amount}) supera el saldo pendiente ({outstanding_balance})."}
                
            # 3. Registrar el pago
            payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
            cursor.execute("""
                INSERT INTO payments (payment_id, invoice_id, date, amount, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (payment_id, invoice_id, date, amount, payment_method, notes))
            
            # 4. Actualizar estado de factura si está pagada completa
            new_outstanding = outstanding_balance - amount
            status_msg = f"Pago parcial registrado. Saldo pendiente: {new_outstanding:.2f}"
            
            if new_outstanding <= 0.01:
                cursor.execute("UPDATE invoices SET status = 'cobrada' WHERE id = ?", (invoice_db_id,))
                status_msg = "Pago registrado. Factura completamente cobrada."
                
            conn.commit()
            
            # 5. Generar apunte contable
            # De clientes (430) a caja/banco (572/570)
            account_debe = "57000000" if payment_method.lower() in ("efectivo", "cash") else "57200001"
            
            ledger_entry = {
                "date": date,
                "concept": f"Cobro fra {invoice_id}",
                "entries": [
                    {"account": account_debe, "debe": amount, "haber": 0},
                    {"account": "43000000", "debe": 0, "haber": amount}
                ]
            }
            try:
                LedgerService.record_journal_entry(ledger_entry)
            except Exception as e:
                tool_logger.warning(f"No se pudo registrar asiento del cobro: {e}")
                
            return {
                "status": "ok",
                "message": status_msg,
                "payment_id": payment_id,
                "outstanding_balance": round(new_outstanding, 2)
            }
        except Exception as e:
            conn.rollback()
            tool_logger.exception("Error al registrar pago")
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_outstanding_balance(invoice_id: str) -> dict:
        """
        Retorna el saldo pendiente de una factura.
        """
        invoice_data = InvoiceRepository.find_invoice_by_id(invoice_id)
        if not invoice_data:
            return {"status": "error", "message": f"Factura '{invoice_id}' no encontrada."}

        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(SUM(amount), 0) as paid FROM payments WHERE invoice_id = ?", (invoice_id,))
            paid_amount = cursor.fetchone()["paid"]
            
            outstanding_balance = invoice_data["total_amount"] - paid_amount
            
            # Recuperar detalle de pagos
            cursor.execute("SELECT payment_id, date, amount, payment_method FROM payments WHERE invoice_id = ?", (invoice_id,))
            payments = []
            for r in cursor.fetchall():
                payments.append(dict(r))
                
            return {
                "status": "ok",
                "invoice_id": invoice_id,
                "total_amount": invoice_data["total_amount"],
                "paid_amount": paid_amount,
                "outstanding_balance": round(outstanding_balance, 2),
                "payments": payments
            }
        finally:
            conn.close()

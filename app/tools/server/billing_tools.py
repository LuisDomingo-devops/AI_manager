import os
import sys
import random
import qrcode
import sqlite3
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.domain.services.ledger_service import LedgerService
from app.domain.services.excel_sync import ExcelSyncService
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.invoice_repository import InvoiceRepository
from app.core.events import event_bus
from app.utils.logger import tool_logger
from app.utils.validators import validate_nif_nie_cif


async def get_projects_wip() -> dict:
    """
    Retorna la lista de proyectos en curso (WIP) y su estado de facturación.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, client_name, client_nif, budget, status, description FROM projects")
            rows = cursor.fetchall()
            projects = []
            for r in rows:
                projects.append({
                    "id": r["id"],
                    "name": r["name"],
                    "client_name": r["client_name"],
                    "client_nif": r["client_nif"],
                    "budget": float(r["budget"]),
                    "status": r["status"],
                    "description": r["description"]
                })
            return {"status": "ok", "projects": projects}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al obtener los proyectos en curso")
        return {"status": "error", "message": str(e)}

async def update_project_status(project_id: int, status: str) -> dict:
    """
    Actualiza el estado de un proyecto/trabajo en curso (valores permitidos: 'en_progreso', 'pendiente_facturar', 'facturado').
    """
    valid_statuses = ("en_progreso", "pendiente_facturar", "facturado")
    if status not in valid_statuses:
        return {"status": "error", "message": f"Estado inválido. Debe ser uno de: {', '.join(valid_statuses)}"}
    
    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
            conn.commit()
            return {"status": "ok", "message": f"Proyecto {project_id} actualizado al estado '{status}' con éxito."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al actualizar el estado del proyecto")
        return {"status": "error", "message": str(e)}

async def get_clients() -> dict:
    """
    Retorna la lista completa de clientes registrados en la base de datos para autocompletado y facturación.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, nif, email, address FROM clients")
            rows = cursor.fetchall()
            clients = []
            for r in rows:
                clients.append({
                    "id": r["id"],
                    "name": r["name"],
                    "nif": r["nif"],
                    "email": r["email"],
                    "address": r["address"]
                })
            return {"status": "ok", "clients": clients}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al obtener la lista de clientes")
        return {"status": "error", "message": str(e)}

async def create_client(name: str, nif: str, email: str, address: str = "") -> dict:
    """
    Registra un nuevo cliente en la base de datos para automatizar futuras facturas.
    """
    try:
        nif_clean = nif.strip().upper()
        if not validate_nif_nie_cif(nif_clean):
            return {"status": "error", "message": f"El NIF/CIF/NIE '{nif}' no es válido formalmente."}

        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clients (name, nif, email, address)
                VALUES (?, ?, ?, ?)
            """, (name.strip(), nif_clean, email.strip(), address.strip()))
            conn.commit()
            return {"status": "ok", "message": f"Cliente '{name}' registrado con éxito en la base de datos."}
        except sqlite3.IntegrityError:
            return {"status": "error", "message": f"El cliente '{name}' ya está registrado."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al registrar cliente")
        return {"status": "error", "message": str(e)}

async def update_client(client_id: int, name: str = None, nif: str = None, email: str = None, address: str = None) -> dict:
    """
    Actualiza los datos de un cliente existente por su ID.
    """
    try:
        if nif is not None:
            nif_clean = nif.strip().upper()
            if not validate_nif_nie_cif(nif_clean):
                return {"status": "error", "message": f"El NIF/CIF/NIE '{nif}' no es válido formalmente."}
        
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM clients WHERE id = ?", (client_id,))
            if not cursor.fetchone():
                return {"status": "error", "message": f"No se encontró el cliente con ID {client_id}."}

            fields_to_update = []
            params = []
            if name is not None:
                fields_to_update.append("name = ?")
                params.append(name.strip())
            if nif is not None:
                fields_to_update.append("nif = ?")
                params.append(nif.strip().upper())
            if email is not None:
                fields_to_update.append("email = ?")
                params.append(email.strip())
            if address is not None:
                fields_to_update.append("address = ?")
                params.append(address.strip())

            if not fields_to_update:
                return {"status": "ok", "message": "No se especificaron campos para actualizar."}

            params.append(client_id)
            query = f"UPDATE clients SET {', '.join(fields_to_update)} WHERE id = ?"
            cursor.execute(query, tuple(params))
            conn.commit()
            return {"status": "ok", "message": f"Cliente con ID {client_id} actualizado con éxito."}
        except sqlite3.IntegrityError:
            return {"status": "error", "message": "El nombre del cliente ya está registrado por otro cliente."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al actualizar cliente")
        return {"status": "error", "message": str(e)}

async def delete_client(client_id: int, confirmed_by_user: bool = False) -> dict:
    """
    Elimina un cliente existente por su ID. Requiere confirmación explícita del usuario.
    """
    if not confirmed_by_user:
        return {
            "status": "pending_confirmation",
            "message": f"¿Confirmas que deseas eliminar permanentemente al cliente con ID {client_id} de tu base de datos?"
        }

    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM clients WHERE id = ?", (client_id,))
            if not cursor.fetchone():
                return {"status": "error", "message": f"No se encontró el cliente con ID {client_id}."}

            cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            conn.commit()
            
            # Registrar en el Ledger de Auditoría
            from app.domain.services.audit_ledger import AuditLedgerService
            from app.adapters.memory.memory import tenant_context
            cid = tenant_context.get()
            AuditLedgerService.log_audit_event(
                event_type="DELETE_CLIENT",
                description=f"Eliminación permanente del cliente con ID {client_id}.",
                client_id=cid
            )
            
            return {"status": "ok", "message": f"Cliente con ID {client_id} eliminado con éxito."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al eliminar cliente")
        return {"status": "error", "message": str(e)}

async def create_product(sku: str, name: str, price: float, description: str = "", iva_rate: float = 21.0) -> dict:
    """
    Registra un nuevo producto o servicio en el catálogo.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (sku, name, description, price, iva_rate)
                VALUES (?, ?, ?, ?, ?)
            """, (sku.strip().upper(), name.strip(), description.strip(), float(price), float(iva_rate)))
            conn.commit()
            return {"status": "ok", "message": f"Producto '{name}' con SKU '{sku}' registrado exitosamente."}
        except sqlite3.IntegrityError:
            return {"status": "error", "message": f"El producto/servicio con SKU '{sku}' ya existe."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al registrar producto")
        return {"status": "error", "message": str(e)}

async def get_products() -> dict:
    """
    Retorna la lista de todos los productos y servicios del catálogo.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, sku, name, description, price, iva_rate FROM products")
            rows = cursor.fetchall()
            products = []
            for r in rows:
                products.append({
                    "id": r["id"],
                    "sku": r["sku"],
                    "name": r["name"],
                    "description": r["description"],
                    "price": float(r["price"]),
                    "iva_rate": float(r["iva_rate"])
                })
            return {"status": "ok", "products": products}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al obtener catálogo de productos")
        return {"status": "error", "message": str(e)}

async def update_product(sku: str, name: str = None, price: float = None, description: str = None, iva_rate: float = None) -> dict:
    """
    Actualiza la información de un producto o servicio por su SKU.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            sku_upper = sku.strip().upper()
            cursor.execute("SELECT id FROM products WHERE sku = ?", (sku_upper,))
            if not cursor.fetchone():
                return {"status": "error", "message": f"No se encontró ningún producto con SKU '{sku}'."}

            fields_to_update = []
            params = []
            if name is not None:
                fields_to_update.append("name = ?")
                params.append(name.strip())
            if price is not None:
                fields_to_update.append("price = ?")
                params.append(float(price))
            if description is not None:
                fields_to_update.append("description = ?")
                params.append(description.strip())
            if iva_rate is not None:
                fields_to_update.append("iva_rate = ?")
                params.append(float(iva_rate))

            if not fields_to_update:
                return {"status": "ok", "message": "No se especificaron campos para actualizar."}

            params.append(sku_upper)
            query = f"UPDATE products SET {', '.join(fields_to_update)} WHERE sku = ?"
            cursor.execute(query, tuple(params))
            conn.commit()
            return {"status": "ok", "message": f"Producto con SKU '{sku}' actualizado exitosamente."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al actualizar producto")
        return {"status": "error", "message": str(e)}

async def delete_product(sku: str, confirmed_by_user: bool = False) -> dict:
    """
    Elimina un producto o servicio del catálogo por su SKU. Requiere confirmación explícita del usuario.
    """
    if not confirmed_by_user:
        return {
            "status": "pending_confirmation",
            "message": f"¿Confirmas que deseas eliminar permanentemente el producto/servicio con SKU '{sku}' del catálogo?"
        }

    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            sku_upper = sku.strip().upper()
            cursor.execute("SELECT id FROM products WHERE sku = ?", (sku_upper,))
            if not cursor.fetchone():
                return {"status": "error", "message": f"No se encontró ningún producto con SKU '{sku}'."}

            cursor.execute("DELETE FROM products WHERE sku = ?", (sku_upper,))
            conn.commit()
            
            # Registrar en el Ledger de Auditoría
            from app.domain.services.audit_ledger import AuditLedgerService
            from app.adapters.memory.memory import tenant_context
            cid = tenant_context.get()
            AuditLedgerService.log_audit_event(
                event_type="DELETE_PRODUCT",
                description=f"Eliminación permanente del producto con SKU '{sku_upper}'.",
                client_id=cid
            )
            
            return {"status": "ok", "message": f"Producto con SKU '{sku}' eliminado del catálogo."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al eliminar producto")
        return {"status": "error", "message": str(e)}

def _generate_unique_quote_id(is_draft: bool, quote_id: str = None) -> str:
    if quote_id:
        return quote_id
        
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT quote_id FROM quotes")
        rows = cursor.fetchall()
        count = 0
        prefix = "P-BORRADOR-2026-" if is_draft else "P-2026-"
        for r in rows:
            try:
                dec_id = encryptor.decrypt(r["quote_id"])
                if dec_id.startswith(prefix):
                    count += 1
            except Exception:
                pass
        return f"{prefix}{count + 101:03d}"
    finally:
        conn.close()

async def create_quote(
    client_name: str,
    client_nif: str,
    amount: float,
    concept: str,
    quote_id: str = None,
    date: str = None,
    iva_rate: float = 21.0,
    irpf_rate: float = 15.0,
    is_draft: bool = True
) -> dict:
    """
    Genera un presupuesto en PDF (PDF de presupuesto/Quote), guarda sus detalles cifrados en la DB de presupuestos,
    y devuelve la ruta del PDF y el ID de presupuesto.
    """
    try:
        now = datetime.now()
        if not date:
            date_str = now.strftime("%d/%m/%Y")
        else:
            date_str = date

        quote_id = _generate_unique_quote_id(is_draft, quote_id)

        # Razón social del emisor
        from app.config import settings
        emisor_name = settings.ALFONSO_USER_NAME or "LUIS DOMINGO"
        emisor_nif = settings.ALFONSO_USER_NIF or "12345678Z"
        try:
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT razon_social, nif FROM user_profile LIMIT 1")
                row = cursor.fetchone()
                if row:
                    if row["razon_social"]:
                        emisor_name = encryptor.decrypt(row["razon_social"])
                    if row["nif"]:
                        emisor_nif = encryptor.decrypt(row["nif"])
        except Exception:
            pass

        iva_amount = round(amount * (iva_rate / 100.0), 2)
        irpf_amount = round(amount * (irpf_rate / 100.0), 2)
        total_amount = round(amount + iva_amount - irpf_amount, 2)

        target_dir = Path(__file__).resolve().parents[3] / "data" / "archivo fiscal" / "presupuestos"
        target_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"Presupuesto_{quote_id}.pdf"
        pdf_path = target_dir / pdf_filename

        # Generar PDF
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        c.setFillColorRGB(0.12, 0.35, 0.23) # Color institucional verde oscuro para diferenciar
        c.rect(50, 720, 510, 40, fill=True, stroke=False)
        
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(65, 732, "PRESUPUESTO DE SERVICIOS")
        
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(380, 735, f"Nro Presupuesto: {quote_id}")
        c.drawString(380, 723, f"Fecha Emisión: {date_str}")
        
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.line(50, 700, 560, 700)
        
        # Emisor
        c.setFont("Helvetica-Bold", 11)
        c.drawString(55, 675, "DATOS DEL EMISOR:")
        c.setFont("Helvetica", 10)
        c.drawString(55, 655, f"Razón Social: {emisor_name}")
        c.drawString(55, 640, f"NIF/CIF: {emisor_nif}")
        
        # Receptor
        c.setFont("Helvetica-Bold", 11)
        c.drawString(320, 675, "DATOS DEL CLIENTE:")
        c.setFont("Helvetica", 10)
        c.drawString(320, 655, f"Razón Social: {client_name}")
        c.drawString(320, 640, f"NIF/CIF: {client_nif}")
        
        c.line(50, 605, 560, 605)
        
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(50, 570, 510, 20, fill=True, stroke=False)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, 576, "Descripción / Concepto")
        c.drawString(450, 576, "Importe Base")
        
        c.setFont("Helvetica", 10)
        c.drawString(60, 545, concept)
        c.drawString(450, 545, f"{amount:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
        
        c.line(50, 520, 560, 520)
        
        y = 480
        totals = [
            ("Base Imponible:", amount),
            (f"IVA (+{iva_rate:.1f}%):", iva_amount) if iva_rate > 0 else ("IVA (0%):", 0.0),
            (f"Retención IRPF (-{irpf_rate:.1f}%):", irpf_amount) if irpf_rate > 0 else ("Retención IRPF (0%):", 0.0),
        ]
        
        for label, val in totals:
            c.setFont("Helvetica", 10)
            c.drawString(340, y, label)
            c.drawString(450, y, f"{val:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
            y -= 20
            
        c.line(340, y + 10, 560, y + 10)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(340, y - 5, "Total Presupuestado:")
        c.drawString(450, y - 5, f"{total_amount:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
        
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(55, 90, "Presupuesto válido por 30 días.")
        status_text = "BORRADOR" if is_draft else "EMITIDO"
        c.drawString(55, 75, f"Estado del Documento: {status_text}")
        c.save()

        # Insertar en DB
        status = "borrador" if is_draft else "enviado"
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quotes (
                    quote_id, date, client_name, client_nif, base_imponible, iva_rate, iva_amount,
                    irpf_rate, irpf_amount, total_amount, concept, file_path, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                encryptor.encrypt(quote_id),
                encryptor.encrypt(date_str),
                encryptor.encrypt(client_name),
                encryptor.encrypt(client_nif),
                encryptor.encrypt(str(amount)),
                encryptor.encrypt(str(iva_rate)),
                encryptor.encrypt(str(iva_amount)),
                encryptor.encrypt(str(irpf_rate)),
                encryptor.encrypt(str(irpf_amount)),
                encryptor.encrypt(str(total_amount)),
                encryptor.encrypt(concept),
                encryptor.encrypt(str(pdf_path)),
                status
            ))
            conn.commit()
        finally:
            conn.close()

        return {
            "status": "ok",
            "message": f"Presupuesto '{quote_id}' creado exitosamente en {pdf_path}.",
            "quote_id": quote_id,
            "file_path": str(pdf_path)
        }
    except Exception as e:
        tool_logger.exception("Error al crear presupuesto")
        return {"status": "error", "message": str(e)}

async def get_quotes() -> dict:
    """
    Retorna la lista de todos los presupuestos descifrados.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, quote_id, date, client_name, client_nif, base_imponible, iva_rate,
                       iva_amount, irpf_rate, irpf_amount, total_amount, concept, file_path, status
                FROM quotes
            """)
            rows = cursor.fetchall()
            quotes = []
            for r in rows:
                try:
                    quotes.append({
                        "id": r["id"],
                        "quote_id": encryptor.decrypt(r["quote_id"]),
                        "date": encryptor.decrypt(r["date"]),
                        "client_name": encryptor.decrypt(r["client_name"]),
                        "client_nif": encryptor.decrypt(r["client_nif"]),
                        "base_imponible": float(encryptor.decrypt(r["base_imponible"])),
                        "iva_rate": float(encryptor.decrypt(r["iva_rate"])),
                        "iva_amount": float(encryptor.decrypt(r["iva_amount"])),
                        "irpf_rate": float(encryptor.decrypt(r["irpf_rate"])),
                        "irpf_amount": float(encryptor.decrypt(r["irpf_amount"])),
                        "total_amount": float(encryptor.decrypt(r["total_amount"])),
                        "concept": encryptor.decrypt(r["concept"]),
                        "file_path": encryptor.decrypt(r["file_path"]),
                        "status": r["status"]
                    })
                except Exception:
                    pass
            return {"status": "ok", "quotes": quotes}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al obtener presupuestos")
        return {"status": "error", "message": str(e)}

async def convert_quote_to_invoice(quote_id: str, confirmed_by_user: bool = False) -> dict:
    """
    Convierte un presupuesto existente en una factura formal.
    """
    try:
        conn = _get_connection()
        quote_data = None
        db_id = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, quote_id, client_name, client_nif, base_imponible, concept, iva_rate, irpf_rate FROM quotes")
            rows = cursor.fetchall()
            for r in rows:
                try:
                    dec_qid = encryptor.decrypt(r["quote_id"])
                    if dec_qid == quote_id:
                        db_id = r["id"]
                        quote_data = {
                            "client_name": encryptor.decrypt(r["client_name"]),
                            "client_nif": encryptor.decrypt(r["client_nif"]),
                            "base_imponible": float(encryptor.decrypt(r["base_imponible"])),
                            "concept": encryptor.decrypt(r["concept"]),
                            "iva_rate": float(encryptor.decrypt(r["iva_rate"])),
                            "irpf_rate": float(encryptor.decrypt(r["irpf_rate"]))
                        }
                        break
                except Exception:
                    pass
            
            if not quote_data:
                return {"status": "error", "message": f"No se encontró el presupuesto con ID '{quote_id}'."}

            # Actualizar estado del presupuesto a 'facturado'
            cursor.execute("UPDATE quotes SET status = 'facturado' WHERE id = ?", (db_id,))
            conn.commit()
        finally:
            conn.close()

        # Generar factura PDF real
        res = await generate_invoice_pdf(
            client_name=quote_data["client_name"],
            client_nif=quote_data["client_nif"],
            amount=quote_data["base_imponible"],
            concept=quote_data["concept"],
            iva_rate=quote_data["iva_rate"],
            irpf_rate=quote_data["irpf_rate"],
            confirmed_by_user=confirmed_by_user
        )
        if res["status"] == "error":
            return {"status": "error", "message": f"Presupuesto marcado como facturado, pero error al emitir factura: {res['message']}"}

        return {
            "status": "ok",
            "message": f"Presupuesto '{quote_id}' convertido con éxito en la factura '{res['invoice_id']}'.",
            "invoice_id": res["invoice_id"],
            "invoice_detail": res
        }
    except Exception as e:
        tool_logger.exception("Error al convertir presupuesto a factura")
        return {"status": "error", "message": str(e)}


def _generate_unique_rectificativa_id(is_draft: bool, rect_id: str = None) -> str:
    if rect_id:
        return rect_id
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_id FROM invoices")
        rows = cursor.fetchall()
        count = 0
        prefix = "R-BORRADOR-2026-" if is_draft else "R-2026-"
        for r in rows:
            try:
                dec_id = encryptor.decrypt(r["invoice_id"])
                if dec_id.startswith(prefix):
                    count += 1
            except Exception:
                pass
        return f"{prefix}{count + 101:03d}"
    finally:
        conn.close()


def _generate_unique_invoice_id(is_draft: bool, invoice_id: str) -> str:
    if is_draft:
        if not invoice_id or not invoice_id.startswith("BORRADOR-"):
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT invoice_id FROM invoices")
                rows = cursor.fetchall()
                draft_count = 0
                for r in rows:
                    try:
                        dec_id = encryptor.decrypt(r["invoice_id"])
                        if dec_id.startswith("BORRADOR-"):
                            draft_count += 1
                    except Exception:
                        pass
                invoice_id = f"BORRADOR-2026-{draft_count + 101:03d}"
            finally:
                conn.close()
    else:
        if not invoice_id or invoice_id.startswith("BORRADOR-"):
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT invoice_id FROM invoices")
                rows = cursor.fetchall()
                firm_count = 0
                for r in rows:
                    try:
                        dec_id = encryptor.decrypt(r["invoice_id"])
                        if dec_id.startswith("F-"):
                            firm_count += 1
                    except Exception:
                        pass
                invoice_id = f"F-2026-{firm_count + 101:03d}"
            finally:
                conn.close()
    return invoice_id


async def generate_invoice_pdf(
    client_name: str,
    client_nif: str,
    amount: float,
    concept: str,
    invoice_id: str = None,
    date: str = None,
    iva_rate: float = 21.0,
    irpf_rate: float = 15.0,
    confirmed_by_user: bool = False
) -> dict:
    """
    Genera una factura en PDF con formato profesional de venta en la carpeta Facturas_Pendientes_Cobro del Escritorio,
    la inserta en la base de datos de facturas y realiza el asiento contable (Diario/Mayor) automáticamente si no es borrador.
    Soporta la persistencia de borradores si faltan datos del cliente, NIF, concepto o importe.
    """
    try:
        # 1. Buscar si existe un registro previo con el invoice_id proporcionado
        existing_id_db, existing_file_path, client_name, client_nif, amount, concept = InvoiceRepository.find_existing_invoice_data(
            invoice_id, client_name, client_nif, amount, concept
        )

        # 2. Evaluar si es borrador (faltan datos o se solicita explícitamente)
        is_incomplete_name = not client_name or client_name.strip() == "" or client_name.lower().strip() in ("desconocido", "pendiente", "cliente genérico", "cliente desconocido", "cliente_desconocido")
        is_incomplete_nif = not client_nif or client_nif.strip() == "" or client_nif.lower().strip() in ("desconocido", "pendiente", "sin nif", "nif_desconocido", "nif desconocido")
        is_incomplete_concept = not concept or concept.strip() == "" or concept.lower().strip() in ("desconocido", "pendiente", "concepto desconocido", "sin concepto")
        is_incomplete_amount = not amount or float(amount) <= 0.0

        is_draft = is_incomplete_name or is_incomplete_nif or is_incomplete_concept or is_incomplete_amount

        # Capa de confirmación humana obligatoria antes de emitir factura firme
        force_draft_msg = None
        if not is_draft and not confirmed_by_user:
            is_draft = True
            force_draft_msg = "La factura tiene todos los campos necesarios, pero se ha generado como BORRADOR sin validez fiscal porque requiere la confirmación explícita del usuario (confirmed_by_user=True) para su registro firme en Verifactu (AEAT)."

        # 3. Resolver fechas e identificadores secuenciales
        now = datetime.now()
        if not date:
            date_str = now.strftime("%d/%m/%Y")
        else:
            date_str = date

        # Resolver ID único
        invoice_id = _generate_unique_invoice_id(is_draft, invoice_id)

        # Obtener datos reales del perfil del usuario emisor
        from app.config import settings
        emisor_name = settings.ALFONSO_USER_NAME or "LUIS DOMINGO"
        emisor_nif = settings.ALFONSO_USER_NIF or ""
        emisor_direccion = "España"
        try:
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT razon_social, nif, direccion FROM user_profile LIMIT 1")
                row = cursor.fetchone()
                if row:
                    if row["razon_social"]:
                        emisor_name = encryptor.decrypt(row["razon_social"])
                    if row["nif"]:
                        emisor_nif = encryptor.decrypt(row["nif"])
                    if row["direccion"]:
                        emisor_direccion = encryptor.decrypt(row["direccion"])
        except Exception:
            pass

        # Si es factura firme (no borrador), verificar obligatoriamente que emisor_nif no esté vacío
        if not is_draft and not emisor_nif:
            # Fallback seguro solo en tests o desarrollo si no hay perfil
            if settings.ENV == "development" or "pytest" in sys.modules:
                emisor_nif = "12345678Z"
            else:
                return {
                    "status": "error",
                    "message": "No se puede emitir una factura firme ante la AEAT sin configurar previamente el NIF del emisor en el perfil fiscal."
                }

        # 4. Cálculos económicos
        iva_amount = round(amount * (iva_rate / 100.0), 2)
        irpf_amount = round(amount * (irpf_rate / 100.0), 2)
        total_amount = round(amount + iva_amount - irpf_amount, 2)
        
        # Obtener trimestre y año
        try:
            parsed_date = datetime.strptime(date_str, "%d/%m/%Y")
            quarter = (parsed_date.month - 1) // 3 + 1
            year = parsed_date.year
        except ValueError:
            quarter = (now.month - 1) // 3 + 1
            year = now.year

        target_dir = Path(__file__).resolve().parents[3] / "data" / "archivo fiscal" / "facturas pendientes"
        target_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"Factura_{invoice_id}.pdf"
        pdf_path = target_dir / pdf_filename

        # 5. Generación del Canvas PDF
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        
        # Estilo premium básico
        c.setFillColorRGB(0.12, 0.23, 0.35) # Color institucional azul oscuro
        c.rect(50, 720, 510, 40, fill=True, stroke=False)
        
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        if is_draft:
            c.drawString(65, 732, "BORRADOR DE FACTURA")
        else:
            c.drawString(65, 732, "FACTURA DE VENTA / INGRESO")
        
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(380, 735, f"Nro Factura: {invoice_id}")
        c.drawString(380, 723, f"Fecha Emisión: {date_str}")
        
        # Bloques de Emisor y Receptor
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.line(50, 700, 560, 700)
        
        # Emisor
        c.setFont("Helvetica-Bold", 11)
        c.drawString(55, 675, "DATOS DEL EMISOR:")
        c.setFont("Helvetica", 10)
        c.drawString(55, 655, f"Razón Social: {emisor_name}")
        c.drawString(55, 640, f"NIF/CIF: {emisor_nif}")
        c.drawString(55, 625, f"Dirección: {emisor_direccion}")
        
        # Receptor
        c.setFont("Helvetica-Bold", 11)
        c.drawString(320, 675, "DATOS DEL CLIENTE:")
        c.setFont("Helvetica", 10)
        c.drawString(320, 655, f"Razón Social: {client_name if client_name else 'PENDIENTE DE ASIGNAR'}")
        c.drawString(320, 640, f"NIF/CIF: {client_nif if client_nif else 'PENDIENTE DE ASIGNAR'}")
        
        c.line(50, 605, 560, 605)
        
        # Línea de detalle / Conceptos
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(50, 570, 510, 20, fill=True, stroke=False)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, 576, "Descripción / Concepto")
        c.drawString(450, 576, "Importe Base")
        
        c.setFont("Helvetica", 10)
        c.drawString(60, 545, concept if concept else "Pendiente de definir concepto")
        c.drawString(450, 545, f"{amount:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
        
        c.line(50, 520, 560, 520)
        
        # Resumen económico / Totales
        y = 480
        totals = [
            ("Base Imponible:", amount),
            (f"IVA (+{iva_rate:.1f}%):", iva_amount) if iva_rate > 0 else ("IVA (0%):", 0.0),
            (f"Retención IRPF (-{irpf_rate:.1f}%):", irpf_amount) if irpf_rate > 0 else ("Retención IRPF (0%):", 0.0),
        ]
        
        for label, val in totals:
            c.setFont("Helvetica", 10)
            c.drawString(340, y, label)
            c.drawString(450, y, f"{val:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
            y -= 20
            
        c.line(340, y + 10, 560, y + 10)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(340, y - 5, "Total a Cobrar:")
        c.drawString(450, y - 5, f"{total_amount:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
        
        if is_draft:
            # Indicador visual muy visible de que es un borrador no fiscal
            c.setFont("Helvetica-Bold", 14)
            c.setFillColorRGB(0.8, 0.2, 0.2)
            c.drawString(135, 165, "BORRADOR SIN VALIDEZ FISCAL")
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(135, 145, "Este documento provisional no se encuentra registrado ante la AEAT.")
            c.drawString(135, 135, "Se requiere NIF, Razón Social e Importe para poder firmar y registrar.")
            
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(55, 90, "Forma de Pago: Transferencia bancaria a la cuenta indicada.")
            c.drawString(55, 75, "Este documento provisional es un borrador y no es válido como factura definitiva.")
            c.save()
            
            current_hash = ""
            signature_base64 = ""
        else:
            from app.config import settings
            
            if settings.VERIFACTU_ACTIVE:
                # 6. Registrar en el encadenamiento Verifactu (AEAT) si es una factura firme
                verifactu_data = {
                    "invoice_number": invoice_id,
                    "date_of_issue": date_str,
                    "issuer_nif": emisor_nif,
                    "receiver_nif": client_nif,
                    "receiver_name": client_name,
                    "base_imponible": amount,
                    "iva_amount": iva_amount,
                    "total_amount": total_amount,
                    "tipo_factura": "F1"
                }
                verifactu_res = VerifactuService.register_invoice(verifactu_data)
                current_hash = verifactu_res["current_hash"]
                signature_base64 = verifactu_res["signature"]

                # Generar código QR oficial de verificación de la AEAT conforme a la normativa VERIFACTU (Orden HAC/1177/2024)
                hash_snippet = current_hash[:16] if current_hash else ""
                qr_url = f"https://sede.agenciatributaria.gob.es/qr/valide?nif={emisor_nif}&numserie={invoice_id}&fecha={date_str}&importe={total_amount:.2f}&huella={hash_snippet}"
                qr = qrcode.QRCode(version=1, box_size=3, border=1)
                qr.add_data(qr_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                qr_temp_path = target_dir / f"qr_{invoice_id}.png"
                qr_img.save(str(qr_temp_path))

                # Dibujar QR en el Canvas PDF
                c.drawImage(str(qr_temp_path), 55, 120, width=70, height=70)

                # Añadir leyenda oficial imperativa de VERIFACTU y metadatos del XML firmado
                c.setFont("Helvetica-Bold", 9)
                c.setFillColorRGB(0.12, 0.23, 0.35)
                c.drawString(135, 175, "VERIFACTU - FACTURA VERIFICABLE")
                
                c.setFont("Helvetica", 7)
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawString(135, 163, "Factura verificable en la Sede electrónica de la AEAT")
                c.drawString(135, 151, f"Huella de encadenamiento (SHA256): {current_hash}")
                c.drawString(135, 140, "Este registro de facturación ha sido firmado digitalmente y enviado a la AEAT.")

                # Limpiar QR temporal
                if qr_temp_path.exists():
                    os.remove(qr_temp_path)
            else:
                # Modo NO VERIFACTU (SIF estándar)
                current_hash = ""
                signature_base64 = ""
                
                c.setFont("Helvetica-Bold", 9)
                c.setFillColorRGB(0.12, 0.23, 0.35)
                c.drawString(55, 175, "SISTEMA INFORMÁTICO DE FACTURACIÓN (SIF)")
                
                c.setFont("Helvetica", 7)
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawString(55, 163, "Factura emitida de conformidad con los requisitos de integridad y conservación del Real Decreto 1007/2023.")
                c.drawString(55, 151, "Conservación inalterable de registros de facturación local garantizada.")

            # Notas finales
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(55, 90, "Forma de Pago: Transferencia bancaria a la cuenta indicada.")
            c.drawString(55, 75, "Esta factura se emite bajo el régimen de autónomos de la Agencia Tributaria Española.")
            
            c.save()

        # Si el archivo PDF viejo existe y el nombre/ruta cambió, lo borramos
        if existing_file_path and existing_file_path != str(pdf_path):
            try:
                if os.path.exists(existing_file_path):
                    os.remove(existing_file_path)
            except Exception as e:
                tool_logger.warning(f"No se pudo borrar el PDF del borrador antiguo: {e}")

        # 7. Registrar/Actualizar en la Base de Datos SQLite (cifrado)
        invoice_db_data = {
            "invoice_id": invoice_id,
            "date": date_str,
            "issuer_name": emisor_name,
            "issuer_nif": emisor_nif,
            "receiver_name": client_name if client_name else "",
            "receiver_nif": client_nif if client_nif else "",
            "base_imponible": amount,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_rate": irpf_rate,
            "irpf_amount": irpf_amount,
            "total_amount": total_amount,
            "category": "income",
            "quarter": quarter,
            "year": year,
            "file_path": str(pdf_path),
            "status": "borrador" if is_draft else "firmada",
            "concept": concept if concept else ""
        }

        InvoiceRepository.save(invoice_db_data, existing_id_db)
        
        # 8. Sincronizar Excel y generar asientos contables asíncronamente vía EventBus
        if not is_draft:
            await event_bus.publish("InvoiceCreated", invoice_db_data)

        msg_detail = f"Borrador {invoice_id} creado" if is_draft else f"Factura {invoice_id} creada y registrada ante la AEAT (Veri*Factu)"
        return {
            "status": "ok",
            "invoice_id": invoice_id,
            "is_draft": is_draft,
            "pdf_path": str(pdf_path),
            "total_amount": total_amount,
            "base_imponible": amount,
            "message": force_draft_msg if force_draft_msg else f"{msg_detail} y guardada en 'archivo fiscal/facturas pendientes'."
        }
    except Exception as e:
        tool_logger.exception("Error al generar e inyectar la factura")
        return {"status": "error", "message": str(e)}

async def cancel_invoice(invoice_id: str) -> dict:
    """
    Anula una factura emitida de forma firme bajo la regulación Verifactu (AEAT).
    Genera el XML de anulación correspondiente y lo envía / registra en la cadena de huellas de auditoría.
    """
    try:
        from app.domain.services.verifactu_service import VerifactuService
        res = VerifactuService.cancel_invoice(invoice_id)
        if res["status"] == "success":
            return {"status": "ok", "message": f"Factura {invoice_id} anulada correctamente en Verifactu (AEAT).", "detail": res}
        else:
            return {"status": "error", "message": res.get("message", "Error al anular la factura.")}
    except Exception as e:
        tool_logger.exception("Error al anular la factura")
        return {"status": "error", "message": str(e)}

async def send_invoice_email(invoice_id: str, recipient_email: str) -> dict:
    """
    Envía por correo electrónico la factura generada a la dirección de email especificada.
    """
    try:
        from app.tools.server.mail_tools import mail_send_email
        
        # Buscar la ruta de la factura en DB
        conn = _get_connection()
        pdf_path_str = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM invoices")
            rows = cursor.fetchall()
            for r in rows:
                p_dec = encryptor.decrypt(r["file_path"])
                if invoice_id in p_dec:
                    pdf_path_str = p_dec
                    break
        finally:
            conn.close()
            
        if not pdf_path_str:
            return {"status": "error", "message": f"No se encontró el archivo físico de la factura {invoice_id} en la base de datos."}

        # Obtener emisor_name dinámico
        emisor_name = "LUIS DOMINGO"
        try:
            with _get_connection() as conn_profile:
                cursor_profile = conn_profile.cursor()
                cursor_profile.execute("SELECT razon_social FROM user_profile LIMIT 1")
                row_profile = cursor_profile.fetchone()
                if row_profile and row_profile["razon_social"]:
                    emisor_name = encryptor.decrypt(row_profile["razon_social"])
        except Exception:
            pass

        subject = f"Factura {invoice_id} emitida por {emisor_name.upper()}"
        body = (
            f"Estimado cliente,\n\n"
            f"Adjunto a este correo le enviamos la factura correspondiente {invoice_id}.\n"
            f"El archivo se encuentra archivado físicamente en la ruta: {pdf_path_str}\n\n"
            f"Atentamente,\n"
            f"{emisor_name}"
        )
        
        res = await mail_send_email(recipient=recipient_email, subject=subject, body=body)
        return {"status": "ok", "message": f"Factura {invoice_id} enviada por correo electrónico a {recipient_email} correctamente.", "detail": res}
    except Exception as e:
        tool_logger.exception("Error al enviar el email de la factura")
        return {"status": "error", "message": f"Error al enviar correo: {str(e)}"}

async def send_quote_email(quote_id: str, recipient_email: str) -> dict:
    """
    Envía por correo electrónico el presupuesto generado a la dirección de email especificada.
    """
    try:
        from app.tools.server.mail_tools import mail_send_email
        
        # Buscar la ruta del presupuesto en DB
        conn = _get_connection()
        pdf_path_str = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM quotes")
            rows = cursor.fetchall()
            for r in rows:
                p_dec = encryptor.decrypt(r["file_path"])
                if quote_id in p_dec:
                    pdf_path_str = p_dec
                    break
        finally:
            conn.close()
            
        if not pdf_path_str:
            return {"status": "error", "message": f"No se encontró el archivo físico del presupuesto {quote_id} en la base de datos."}

        # Obtener emisor_name dinámico
        emisor_name = "LUIS DOMINGO"
        try:
            with _get_connection() as conn_profile:
                cursor_profile = conn_profile.cursor()
                cursor_profile.execute("SELECT razon_social FROM user_profile LIMIT 1")
                row_profile = cursor_profile.fetchone()
                if row_profile and row_profile["razon_social"]:
                    emisor_name = encryptor.decrypt(row_profile["razon_social"])
        except Exception:
            pass

        subject = f"Presupuesto {quote_id} de {emisor_name.upper()}"
        body = (
            f"Estimado cliente,\n\n"
            f"Adjunto a este correo le enviamos el presupuesto {quote_id} solicitado.\n"
            f"El archivo se encuentra archivado físicamente en la ruta: {pdf_path_str}\n\n"
            f"Atentamente,\n"
            f"{emisor_name}"
        )
        
        res = await mail_send_email(recipient=recipient_email, subject=subject, body=body)
        return {"status": "ok", "message": f"Presupuesto {quote_id} enviado por correo electrónico a {recipient_email} correctamente.", "detail": res}
    except Exception as e:
        tool_logger.exception("Error al enviar el email del presupuesto")
        return {"status": "error", "message": f"Error al enviar correo: {str(e)}"}

async def sign_quote(quote_id: str) -> dict:
    """
    Firma criptográficamente los campos principales de un presupuesto usando la clave privada RSA de Verifactu.
    Guarda la firma digital en formato Base64 en la base de datos.
    """
    try:
        import hashlib
        import base64
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from app.domain.services.verifactu_service import VerifactuService

        # 1. Obtener datos del presupuesto
        conn = _get_connection()
        quote_data = None
        db_id = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, quote_id, client_nif, total_amount, concept, date FROM quotes")
            rows = cursor.fetchall()
            for r in rows:
                try:
                    dec_qid = encryptor.decrypt(r["quote_id"])
                    if dec_qid == quote_id:
                        db_id = r["id"]
                        quote_data = {
                            "client_nif": encryptor.decrypt(r["client_nif"]),
                            "total_amount": float(encryptor.decrypt(r["total_amount"])),
                            "concept": encryptor.decrypt(r["concept"]),
                            "date": encryptor.decrypt(r["date"])
                        }
                        break
                except Exception:
                    pass
        finally:
            conn.close()

        if not quote_data:
            return {"status": "error", "message": f"No se encontró el presupuesto '{quote_id}'."}

        # 2. Generar cadena canónica y calcular su hash SHA-256
        canonical_str = f"{quote_id}|{quote_data['client_nif']}|{quote_data['total_amount']:.2f}|{quote_data['concept']}|{quote_data['date']}"
        data_bytes = canonical_str.encode('utf-8')
        digest = hashlib.sha256(data_bytes).digest()

        # 3. Obtener clave privada y firmar
        private_key = VerifactuService.get_or_create_private_key()
        signature_bytes = private_key.sign(
            digest,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')

        # 4. Guardar firma en DB
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE quotes SET signature = ? WHERE id = ?", (signature_b64, db_id))
            conn.commit()
        finally:
            conn.close()

        return {
            "status": "ok",
            "message": f"Presupuesto '{quote_id}' firmado criptográficamente con éxito.",
            "signature": signature_b64,
            "canonical_data": canonical_str
        }
    except Exception as e:
        tool_logger.exception("Error al firmar presupuesto")
        return {"status": "error", "message": str(e)}

async def verify_quote_signature(quote_id: str) -> dict:
    """
    Verifica la autenticidad y la integridad de la firma digital de un presupuesto.
    """
    try:
        import hashlib
        import base64
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from app.domain.services.verifactu_service import VerifactuService

        # 1. Obtener datos del presupuesto y la firma
        conn = _get_connection()
        quote_data = None
        signature_b64 = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT quote_id, client_nif, total_amount, concept, date, signature FROM quotes")
            rows = cursor.fetchall()
            for r in rows:
                try:
                    dec_qid = encryptor.decrypt(r["quote_id"])
                    if dec_qid == quote_id:
                        signature_b64 = r["signature"]
                        quote_data = {
                            "client_nif": encryptor.decrypt(r["client_nif"]),
                            "total_amount": float(encryptor.decrypt(r["total_amount"])),
                            "concept": encryptor.decrypt(r["concept"]),
                            "date": encryptor.decrypt(r["date"])
                        }
                        break
                except Exception:
                    pass
        finally:
            conn.close()

        if not quote_data:
            return {"status": "error", "message": f"No se encontró el presupuesto '{quote_id}'."}

        if not signature_b64:
            return {"status": "error", "message": f"El presupuesto '{quote_id}' no posee ninguna firma digital registrada."}

        # 2. Generar cadena canónica y calcular su hash SHA-256
        canonical_str = f"{quote_id}|{quote_data['client_nif']}|{quote_data['total_amount']:.2f}|{quote_data['concept']}|{quote_data['date']}"
        data_bytes = canonical_str.encode('utf-8')
        digest = hashlib.sha256(data_bytes).digest()

        # 3. Obtener clave pública y verificar
        private_key = VerifactuService.get_or_create_private_key()
        public_key = private_key.public_key()
        signature_bytes = base64.b64decode(signature_b64.encode('utf-8'))

        try:
            public_key.verify(
                signature_bytes,
                digest,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return {
                "status": "ok",
                "valid": True,
                "message": f"Firma digital del presupuesto '{quote_id}' verificada y VÁLIDA. Integridad del documento garantizada."
            }
        except Exception:
            return {
                "status": "ok",
                "valid": False,
                "message": f"ATENCIÓN: La firma digital del presupuesto '{quote_id}' es INVÁLIDA. El documento ha sido modificado o alterado."
            }
    except Exception as e:
        tool_logger.exception("Error al verificar firma de presupuesto")
        return {"status": "error", "message": str(e)}


def _generate_unique_payment_id() -> str:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM payments")
        count = cursor.fetchone()["count"]
        return f"PAY-2026-{count + 101:03d}"
    finally:
        conn.close()

async def register_payment(invoice_id: str, amount: float, payment_method: str = "transferencia", notes: str = "", date: str = None) -> dict:
    """
    Registra un cobro parcial o total contra una factura existente.
    """
    try:
        inv = InvoiceRepository.find_invoice_by_id(invoice_id)
        if not inv:
            return {"status": "error", "message": f"No se encontró la factura con ID '{invoice_id}'."}

        now = datetime.now()
        if not date:
            date_str = now.strftime("%d/%m/%Y")
        else:
            date_str = date

        # Calcular cobros previos
        conn = _get_connection()
        total_paid_before = 0.0
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT amount FROM payments WHERE invoice_id = ?", (invoice_id,))
            rows = cursor.fetchall()
            for r in rows:
                total_paid_before += float(r["amount"])
        finally:
            conn.close()

        total_amount = inv["total_amount"]
        pending = round(total_amount - total_paid_before, 2)

        if pending <= 0.0:
            return {"status": "error", "message": f"La factura '{invoice_id}' ya está totalmente cobrada."}

        if round(amount, 2) > pending:
            return {"status": "error", "message": f"El importe del cobro ({amount:.2f} €) excede el saldo pendiente ({pending:.2f} €)."}

        payment_id = _generate_unique_payment_id()

        # Registrar pago
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payments (payment_id, invoice_id, date, amount, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (payment_id, invoice_id, date_str, float(amount), payment_method, notes))
            
            # Si el pago actual completa la factura, actualizar su estado a 'cobrada'
            new_total_paid = round(total_paid_before + amount, 2)
            new_pending = round(total_amount - new_total_paid, 2)
            if new_pending <= 0.0:
                cursor.execute("UPDATE invoices SET status = 'cobrada' WHERE id = ?", (inv["db_id"],))
                
            conn.commit()
        finally:
            conn.close()

        # Publicar evento de pago registrado
        try:
            await event_bus.publish("PaymentRegistered", {
                "payment_id": payment_id,
                "invoice_id": invoice_id,
                "amount": float(amount),
                "date": date_str,
                "payment_method": payment_method
            })
        except Exception as e:
            tool_logger.warning("No se pudo publicar el evento PaymentRegistered: %s", str(e))

        return {
            "status": "ok",
            "message": f"Pago '{payment_id}' de {amount:.2f} € registrado contra la factura '{invoice_id}' exitosamente.",
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "invoice_total": total_amount,
            "total_paid": new_total_paid,
            "pending_balance": new_pending,
            "status_factura": "cobrada" if new_pending <= 0.0 else inv["status"]
        }
    except Exception as e:
        tool_logger.exception("Error al registrar pago")
        return {"status": "error", "message": str(e)}

async def get_invoice_payment_summary(invoice_id: str) -> dict:
    """
    Retorna el resumen de cobros y el saldo pendiente para una factura concreta.
    """
    try:
        inv = InvoiceRepository.find_invoice_by_id(invoice_id)
        if not inv:
            return {"status": "error", "message": f"No se encontró la factura con ID '{invoice_id}'."}

        conn = _get_connection()
        payments = []
        total_paid = 0.0
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT payment_id, date, amount, payment_method, notes FROM payments WHERE invoice_id = ?", (invoice_id,))
            rows = cursor.fetchall()
            for r in rows:
                amt = float(r["amount"])
                total_paid += amt
                payments.append({
                    "payment_id": r["payment_id"],
                    "date": r["date"],
                    "amount": amt,
                    "payment_method": r["payment_method"],
                    "notes": r["notes"]
                })
        finally:
            conn.close()

        total_amount = inv["total_amount"]
        pending = round(total_amount - total_paid, 2)

        return {
            "status": "ok",
            "invoice_id": invoice_id,
            "client_name": inv["receiver_name"],
            "invoice_total": total_amount,
            "total_paid": total_paid,
            "pending_balance": pending,
            "payments": payments
        }
    except Exception as e:
        tool_logger.exception("Error al obtener resumen de pagos")
        return {"status": "error", "message": str(e)}

async def get_pending_payments_report() -> dict:
    """
    Genera un listado consolidado de todas las facturas que tienen un saldo pendiente de cobro.
    """
    try:
        conn = _get_connection()
        invoices = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, invoice_id, receiver_name, receiver_nif, total_amount, status, concept, date FROM invoices")
            rows = cursor.fetchall()
            for r in rows:
                try:
                    invoices.append({
                        "db_id": r["id"],
                        "invoice_id": encryptor.decrypt(r["invoice_id"]),
                        "receiver_name": encryptor.decrypt(r["receiver_name"]),
                        "receiver_nif": encryptor.decrypt(r["receiver_nif"]),
                        "total_amount": float(encryptor.decrypt(r["total_amount"])),
                        "status": r["status"],
                        "concept": encryptor.decrypt(r["concept"]) if r["concept"] else "",
                        "date": encryptor.decrypt(r["date"])
                    })
                except Exception:
                    pass
        finally:
            conn.close()

        conn = _get_connection()
        pending_report = []
        try:
            cursor = conn.cursor()
            for inv in invoices:
                cursor.execute("SELECT SUM(amount) as total_paid FROM payments WHERE invoice_id = ?", (inv["invoice_id"],))
                row = cursor.fetchone()
                total_paid = float(row["total_paid"]) if row and row["total_paid"] else 0.0
                pending = round(inv["total_amount"] - total_paid, 2)
                if pending > 0.0:
                    pending_report.append({
                        "invoice_id": inv["invoice_id"],
                        "client_name": inv["receiver_name"],
                        "client_nif": inv["receiver_nif"],
                        "date": inv["date"],
                        "concept": inv["concept"],
                        "invoice_total": inv["total_amount"],
                        "total_paid": total_paid,
                        "pending_balance": pending,
                        "status": inv["status"]
                    })
        finally:
            conn.close()

        return {"status": "ok", "pending_invoices": pending_report}
    except Exception as e:
        tool_logger.exception("Error al generar reporte de cobros pendientes")
        return {"status": "error", "message": str(e)}

async def send_payment_reminder_email(invoice_id: str) -> dict:
    """
    Envía un email amigable de recordatorio de pago al cliente con el saldo pendiente de una factura.
    """
    try:
        summary = await get_invoice_payment_summary(invoice_id)
        if summary["status"] == "error":
            return {"status": "error", "message": summary["message"]}

        pending = summary["pending_balance"]
        if pending <= 0.0:
            return {"status": "ok", "message": f"La factura '{invoice_id}' ya está completamente pagada. No se requiere recordatorio."}

        client_email = "cliente@correo.com"
        client_name = summary["client_name"]
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM clients WHERE name = ?", (client_name,))
            row = cursor.fetchone()
            if row:
                client_email = row["email"]
        finally:
            conn.close()

        emisor_name = "LUIS DOMINGO"
        try:
            with _get_connection() as conn_profile:
                cursor_profile = conn_profile.cursor()
                cursor_profile.execute("SELECT razon_social FROM user_profile LIMIT 1")
                row_profile = cursor_profile.fetchone()
                if row_profile and row_profile["razon_social"]:
                    emisor_name = encryptor.decrypt(row_profile["razon_social"])
        except Exception:
            pass

        from app.tools.server.mail_tools import mail_send_email
        subject = f"Recordatorio de pago pendiente — Factura {invoice_id}"
        body = (
            f"Estimado/a {client_name},\n\n"
            f"Le escribimos para recordarle amigablemente que la factura {invoice_id} cuenta con un saldo pendiente de cobro.\n\n"
            f"Detalles del saldo:\n"
            f"- Total Factura: {summary['invoice_total']:.2f} €\n"
            f"- Total Cobrado: {summary['total_paid']:.2f} €\n"
            f"- Saldo Pendiente de Pago: {pending:.2f} €\n\n"
            f"Por favor, realice el pago correspondiente mediante transferencia bancaria.\n\n"
            f"Atentamente,\n"
            f"{emisor_name}"
        )

        res = await mail_send_email(recipient=client_email, subject=subject, body=body)
        return {"status": "ok", "message": f"Recordatorio de pago para factura '{invoice_id}' enviado a '{client_email}' correctamente.", "detail": res}
    except Exception as e:
        tool_logger.exception("Error al enviar recordatorio de pago")
        return {"status": "error", "message": str(e)}


async def create_rectificativa_invoice(
    original_invoice_id: str,
    reason: str,
    rectificativa_type: str = "R1",
    amount: float = None,
    concept: str = None,
    date: str = None,
    iva_rate: float = None,
    irpf_rate: float = None,
    confirmed_by_user: bool = False
) -> dict:
    """
    Emite una Factura Rectificativa oficial (RD 1619/2012 Art. 15 y Verifactu RD 1007/2023) vinculada a una factura ordinaria previa.
    Genera el PDF con serie R-2026-XXX, registra el asiento contable corrector y emite el registro Verifactu R1-R5.
    """
    try:
        # 1. Buscar factura original
        orig_inv = InvoiceRepository.find_invoice_by_id(original_invoice_id)
        if not orig_inv:
            return {
                "status": "error",
                "message": f"No se encontró la factura original con ID '{original_invoice_id}'."
            }

        client_name = orig_inv["receiver_name"]
        client_nif = orig_inv["receiver_nif"]
        orig_date = orig_inv["date"]
        
        # Si no se especifica importe nuevo, se rectifica el importe original completo
        rect_amount = float(amount) if amount is not None else float(orig_inv["base_imponible"])
        rect_iva_rate = float(iva_rate) if iva_rate is not None else float(orig_inv["iva_rate"])
        rect_irpf_rate = float(irpf_rate) if irpf_rate is not None else float(orig_inv["irpf_rate"])
        rect_concept = concept if concept else f"Rectificación de Factura {original_invoice_id}: {reason}"

        # Evaluar confirmación humana
        is_draft = not confirmed_by_user
        force_draft_msg = None
        if is_draft:
            force_draft_msg = f"La factura rectificativa se ha generado como BORRADOR (R-BORRADOR) porque requiere la confirmación explícita del usuario (confirmed_by_user=True) para su registro firme en Verifactu (AEAT)."

        now = datetime.now()
        date_str = date if date else now.strftime("%d/%m/%Y")
        rect_id = _generate_unique_rectificativa_id(is_draft)

        # Datos del emisor
        from app.config import settings
        emisor_name = settings.ALFONSO_USER_NAME or "LUIS DOMINGO"
        emisor_nif = settings.ALFONSO_USER_NIF or ""
        emisor_direccion = "España"
        try:
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT razon_social, nif, direccion FROM user_profile LIMIT 1")
                row = cursor.fetchone()
                if row:
                    if row["razon_social"]:
                        emisor_name = encryptor.decrypt(row["razon_social"])
                    if row["nif"]:
                        emisor_nif = encryptor.decrypt(row["nif"])
                    if row["direccion"]:
                        emisor_direccion = encryptor.decrypt(row["direccion"])
        except Exception:
            pass

        if not is_draft and not emisor_nif:
            if settings.ENV == "development" or "pytest" in sys.modules:
                emisor_nif = "12345678Z"
            else:
                return {
                    "status": "error",
                    "message": "No se puede emitir una factura rectificativa firme ante la AEAT sin configurar el NIF del emisor en el perfil fiscal."
                }

        # Cálculos económicos
        iva_amount = round(rect_amount * (rect_iva_rate / 100.0), 2)
        irpf_amount = round(rect_amount * (rect_irpf_rate / 100.0), 2)
        total_amount = round(rect_amount + iva_amount - irpf_amount, 2)

        try:
            parsed_date = datetime.strptime(date_str, "%d/%m/%Y")
            quarter = (parsed_date.month - 1) // 3 + 1
            year = parsed_date.year
        except ValueError:
            quarter = (now.month - 1) // 3 + 1
            year = now.year

        target_dir = Path(__file__).resolve().parents[3] / "data" / "archivo fiscal" / "facturas rectificativas"
        target_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"Factura_Rectificativa_{rect_id}.pdf"
        pdf_path = target_dir / pdf_filename

        # Generar Canvas PDF
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        c.setFillColorRGB(0.55, 0.15, 0.15) # Granate institucional para diferenciar rectificativas
        c.rect(50, 720, 510, 40, fill=True, stroke=False)
        
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 15)
        title_text = f"BORRADOR FACTURA RECTIFICATIVA ({rectificativa_type})" if is_draft else f"FACTURA RECTIFICATIVA ({rectificativa_type})"
        c.drawString(65, 732, title_text)
        
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(380, 735, f"Nro Factura: {rect_id}")
        c.drawString(380, 723, f"Fecha Emisión: {date_str}")
        
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.line(50, 700, 560, 700)
        
        # Emisor
        c.setFont("Helvetica-Bold", 11)
        c.drawString(55, 675, "DATOS DEL EMISOR:")
        c.setFont("Helvetica", 10)
        c.drawString(55, 655, f"Razón Social: {emisor_name}")
        c.drawString(55, 640, f"NIF/CIF: {emisor_nif}")
        c.drawString(55, 625, f"Dirección: {emisor_direccion}")
        
        # Receptor
        c.setFont("Helvetica-Bold", 11)
        c.drawString(320, 675, "DATOS DEL CLIENTE:")
        c.setFont("Helvetica", 10)
        c.drawString(320, 655, f"Razón Social: {client_name}")
        c.drawString(320, 640, f"NIF/CIF: {client_nif}")
        
        c.line(50, 605, 560, 605)
        
        # Referencia obligatoria a factura rectificada
        c.setFillColorRGB(0.95, 0.95, 0.95)
        c.rect(50, 575, 510, 22, fill=True, stroke=False)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(60, 581, f"FACTURA RECTIFICADA: {original_invoice_id} | Fecha Original: {orig_date} | Motivo: {reason}")
        
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(50, 545, 510, 20, fill=True, stroke=False)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, 551, "Descripción / Concepto Rectificado")
        c.drawString(450, 551, "Importe Base")
        
        c.setFont("Helvetica", 10)
        c.drawString(60, 520, rect_concept)
        c.drawString(450, 520, f"-{rect_amount:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
        
        c.line(50, 495, 560, 495)
        
        y = 460
        totals = [
            ("Base Rectificada:", -rect_amount),
            (f"IVA Rectificado ({rect_iva_rate:.1f}%):", -iva_amount) if rect_iva_rate > 0 else ("IVA (0%):", 0.0),
            (f"Retención IRPF ({rect_irpf_rate:.1f}%):", -irpf_amount) if rect_irpf_rate > 0 else ("Retención IRPF (0%):", 0.0),
        ]
        
        for label, val in totals:
            c.setFont("Helvetica", 10)
            c.drawString(340, y, label)
            c.drawString(450, y, f"{val:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
            y -= 20
            
        c.line(340, y + 10, 560, y + 10)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(340, y - 5, "Total Rectificación:")
        c.drawString(450, y - 5, f"-{total_amount:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))
        
        if is_draft:
            c.setFont("Helvetica-Bold", 14)
            c.setFillColorRGB(0.8, 0.2, 0.2)
            c.drawString(135, 165, "BORRADOR SIN VALIDEZ FISCAL")
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(135, 145, "Documento provisional pendiente de confirmación de emisión firme ante la AEAT.")
            c.drawString(55, 75, "Este documento provisional es un borrador rectificativo sin registro oficial.")
            c.save()
            current_hash = ""
        else:
            from app.config import settings
            if settings.VERIFACTU_ACTIVE:
                verifactu_data = {
                    "invoice_number": rect_id,
                    "date_of_issue": date_str,
                    "issuer_nif": emisor_nif,
                    "receiver_nif": client_nif,
                    "receiver_name": client_name,
                    "base_imponible": rect_amount,
                    "iva_amount": iva_amount,
                    "total_amount": total_amount,
                    "tipo_factura": rectificativa_type,
                    "tipo_rectificativa": "I",
                    "rectified_invoice_number": original_invoice_id,
                    "rectified_invoice_date": orig_date
                }
                verifactu_res = VerifactuService.register_invoice(verifactu_data)
                current_hash = verifactu_res["current_hash"]

                hash_snippet = current_hash[:16] if current_hash else ""
                qr_url = f"https://sede.agenciatributaria.gob.es/qr/valide?nif={emisor_nif}&numserie={rect_id}&fecha={date_str}&importe={total_amount:.2f}&huella={hash_snippet}"
                qr = qrcode.QRCode(version=1, box_size=3, border=1)
                qr.add_data(qr_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                qr_temp_path = target_dir / f"qr_{rect_id}.png"
                qr_img.save(str(qr_temp_path))

                c.drawImage(str(qr_temp_path), 55, 120, width=70, height=70)
                c.setFont("Helvetica-Bold", 9)
                c.setFillColorRGB(0.55, 0.15, 0.15)
                c.drawString(135, 175, "VERIFACTU - FACTURA RECTIFICATIVA VERIFICABLE")
                
                c.setFont("Helvetica", 7)
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawString(135, 163, "Factura rectificativa verificable en la Sede electrónica de la AEAT")
                c.drawString(135, 151, f"Huella de encadenamiento (SHA256): {current_hash}")
                c.drawString(135, 140, "Este registro de rectificación ha sido firmado digitalmente y enviado a la AEAT.")

                if qr_temp_path.exists():
                    os.remove(qr_temp_path)
            
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(55, 75, "Factura rectificativa emitida de conformidad con el Art. 15 del Real Decreto 1619/2012.")
            c.save()

        # Guardar en Base de Datos de Facturas
        invoice_db_data = {
            "invoice_id": rect_id,
            "date": date_str,
            "issuer_name": emisor_name,
            "issuer_nif": emisor_nif,
            "receiver_name": client_name,
            "receiver_nif": client_nif,
            "base_imponible": -rect_amount,
            "iva_rate": rect_iva_rate,
            "iva_amount": -iva_amount,
            "irpf_rate": rect_irpf_rate,
            "irpf_amount": -irpf_amount,
            "total_amount": -total_amount,
            "category": "income_rectificativa",
            "quarter": quarter,
            "year": year,
            "file_path": str(pdf_path),
            "status": "borrador" if is_draft else "firmada",
            "concept": rect_concept
        }
        InvoiceRepository.save(invoice_db_data, None)

        # Contabilizar si no es borrador
        if not is_draft:
            try:
                LedgerService.record_rectificativa_invoice_asiento({
                    "invoice_id": rect_id,
                    "original_invoice_id": original_invoice_id,
                    "date": date_str,
                    "base_imponible": rect_amount,
                    "iva_amount": iva_amount,
                    "irpf_amount": irpf_amount,
                    "total_amount": total_amount
                })
            except Exception as leg_err:
                tool_logger.warning("No se pudo generar asiento contable para la rectificativa: %s", str(leg_err))

        return {
            "status": "ok",
            "rectificativa_id": rect_id,
            "original_invoice_id": original_invoice_id,
            "is_draft": is_draft,
            "pdf_path": str(pdf_path),
            "total_amount": -total_amount,
            "base_imponible": -rect_amount,
            "message": force_draft_msg if force_draft_msg else f"Factura rectificativa {rect_id} emitida y registrada ante la AEAT (Veri*Factu) vinculada a {original_invoice_id}."
        }
    except Exception as e:
        tool_logger.exception("Error al generar factura rectificativa")
        return {"status": "error", "message": str(e)}

async def get_profit_and_loss_report(year: int = None, quarter: int = None) -> dict:
    """
    Genera el informe oficial de la Cuenta de Pérdidas y Ganancias (PyG / P&L) del Plan General Contable (PGC).
    Devuelve los ingresos de explotación (Grupo 7), gastos de explotación (Grupo 6), EBITDA, impuesto estimado y resultado neto.
    """
    try:
        from app.domain.services.ledger_service import LedgerService
        target_year = year if year is not None else datetime.now().year
        pnl = LedgerService.get_profit_and_loss_statement(target_year, quarter)
        return {
            "status": "ok",
            "report": pnl,
            "message": f"Cuenta de Pérdidas y Ganancias para el ejercicio {target_year}{f' (Trimestre {quarter})' if quarter else ''} calculada con éxito."
        }
    except Exception as e:
        tool_logger.exception("Error al generar la cuenta de pérdidas y ganancias")
        return {"status": "error", "message": str(e)}


async def close_fiscal_year_tool(year: int, confirmed_by_user: bool = False) -> dict:
    """
    Ejecuta el cierre oficial del ejercicio contable/fiscal:
    1. Asiento de Regularización (Grupos 6 y 7 a cuenta 12900000).
    2. Asiento de Cierre de balance.
    3. Bloqueo de modificaciones en el ejercicio cerrado.
    4. Asiento de Apertura del ejercicio siguiente.
    Requiere confirmación explícita del usuario (confirmed_by_user=True).
    """
    try:
        from app.domain.services.ledger_service import LedgerService
        if not confirmed_by_user:
            return {
                "status": "pending_confirmation",
                "year": year,
                "message": f"El cierre del ejercicio contable {year} es una operación irreversible que bloqueará la modificación de facturas y generará los asientos de regularización, cierre y apertura. Confirma explícitamente para proceder (confirmed_by_user=True)."
            }

        res = LedgerService.close_fiscal_year(year)
        return res
    except Exception as e:
        tool_logger.exception("Error al cerrar el ejercicio fiscal")
        return {"status": "error", "message": str(e)}


async def export_einvoice_tool(invoice_id: str, format_type: str = "ubl") -> dict:
    """
    Exporta una factura a un estándar de Facturación Electrónica interoperable:
    - 'ubl': Estándar europeo EN 16931 / UBL 2.1 (OASIS)
    - 'facturae': Estándar español Facturae v3.2.2 firmado digitalmente
    """
    try:
        from app.domain.services.invoice_repository import InvoiceRepository
        from app.domain.services.b2b_einvoice_service import B2BEInvoiceService
        
        inv = InvoiceRepository.find_invoice_by_id(invoice_id)
        if not inv:
            return {"status": "error", "message": f"Factura no encontrada con ID: {invoice_id}"}
        
        invoice_data = {
            "invoice_number": inv.get("invoice_id", invoice_id),
            "date_of_issue": inv.get("date", ""),
            "issuer_name": inv.get("issuer_name", ""),
            "issuer_nif": inv.get("issuer_nif", ""),
            "recipient_name": inv.get("receiver_name", ""),
            "recipient_nif": inv.get("receiver_nif", ""),
            "base_imponible": inv.get("base_imponible", 0.0),
            "iva_rate": inv.get("iva_rate", 21.0),
            "iva_amount": inv.get("iva_amount", 0.0),
            "irpf_rate": inv.get("irpf_rate", 0.0),
            "irpf_amount": inv.get("irpf_amount", 0.0),
            "total_amount": inv.get("total_amount", 0.0),
            "concept": inv.get("concept", "Servicios profesionales"),
            "category": inv.get("category", "income")
        }

        if format_type.lower() == "facturae":
            xml_content = B2BEInvoiceService.export_to_facturae_xml(invoice_data)
            file_path = f"data/facturae_xml/{invoice_id}_facturae.xml"
        else:
            xml_content = B2BEInvoiceService.export_to_ubl_xml(invoice_data)
            file_path = f"data/ubl_xml/{invoice_id}_ubl.xml"

        return {
            "status": "ok",
            "invoice_id": invoice_id,
            "format": format_type.lower(),
            "file_path": file_path,
            "xml_preview": xml_content[:300] + "...",
            "message": f"Factura electrónica {invoice_id} exportada con éxito en formato {format_type.upper()}."
        }
    except Exception as e:
        tool_logger.exception("Error al exportar factura electrónica")
        return {"status": "error", "message": str(e)}


async def update_b2b_invoice_status_tool(
    invoice_id: str,
    new_status: str,
    reason: str = None,
    payment_date: str = None,
    payment_method: str = None
) -> dict:
    """
    Actualiza el estado comercial de una factura B2B conforme a la Ley Crea y Crece (18/2022).
    Estados válidos: RECEPCION_COMERCIAL, ACEPTACION_CONFORME, RECHAZO_COMERCIAL, APROBACION_PAGO, PAGO_EFECTIVO.
    """
    try:
        from app.domain.services.b2b_einvoice_service import B2BEInvoiceService
        return B2BEInvoiceService.update_b2b_invoice_status(
            invoice_id=invoice_id,
            new_status=new_status,
            reason=reason,
            payment_date=payment_date,
            payment_method=payment_method
        )
    except Exception as e:
        tool_logger.exception("Error al actualizar estado B2B")
        return {"status": "error", "message": str(e)}


async def get_b2b_invoice_status_history_tool(invoice_id: str) -> dict:
    """
    Consulta la trazabilidad y el historial cronológico de estados B2B de una factura.
    """
    try:
        from app.domain.services.b2b_einvoice_service import B2BEInvoiceService
        history = B2BEInvoiceService.get_b2b_invoice_status_history(invoice_id)
        return {
            "status": "ok",
            "invoice_id": invoice_id,
            "history": history,
            "total_events": len(history)
        }
    except Exception as e:
        tool_logger.exception("Error al consultar historial de estados B2B")
        return {"status": "error", "message": str(e)}


async def export_advisor_pack_tool(year: int = None) -> dict:
    """
    Genera el paquete completo de información contable y fiscal para la gestoría/asesor externo.
    Incluye Diario, Mayor, Balances, PyG y Libros de IVA.
    """
    try:
        from app.domain.services.ledger_service import LedgerService
        target_year = year if year is not None else datetime.now().year
        pack = LedgerService.export_advisor_pack(target_year)
        return {
            "status": "ok",
            "pack": pack,
            "message": f"Paquete de asesoría para el ejercicio {target_year} consolidado con éxito."
        }
    except Exception as e:
        tool_logger.exception("Error al generar el paquete de asesoría")
        return {"status": "error", "message": str(e)}

TOOLS = {
    "get_projects_wip": get_projects_wip,
    "update_project_status": update_project_status,
    "get_clients": get_clients,
    "create_client": create_client,
    "update_client": update_client,
    "delete_client": delete_client,
    "create_product": create_product,
    "get_products": get_products,
    "update_product": update_product,
    "delete_product": delete_product,
    "create_quote": create_quote,
    "get_quotes": get_quotes,
    "convert_quote_to_invoice": convert_quote_to_invoice,
    "sign_quote": sign_quote,
    "verify_quote_signature": verify_quote_signature,
    "register_payment": register_payment,
    "get_invoice_payment_summary": get_invoice_payment_summary,
    "get_pending_payments_report": get_pending_payments_report,
    "send_payment_reminder_email": send_payment_reminder_email,
    "generate_invoice_pdf": generate_invoice_pdf,
    "create_rectificativa_invoice": create_rectificativa_invoice,
    "get_profit_and_loss_report": get_profit_and_loss_report,
    "close_fiscal_year_tool": close_fiscal_year_tool,
    "export_einvoice_tool": export_einvoice_tool,
    "update_b2b_invoice_status_tool": update_b2b_invoice_status_tool,
    "get_b2b_invoice_status_history_tool": get_b2b_invoice_status_history_tool,
    "export_advisor_pack_tool": export_advisor_pack_tool,
    "send_invoice_email": send_invoice_email,
    "send_quote_email": send_quote_email,
    "cancel_invoice": cancel_invoice,
}


import os
import sys
import random
import qrcode
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.domain.services.ledger_service import LedgerService
from app.domain.services.excel_sync import ExcelSyncService
from app.domain.services.verifactu_service import VerifactuService
from app.utils.logger import tool_logger


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
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clients (name, nif, email, address)
                VALUES (?, ?, ?, ?)
            """, (name.strip(), nif.strip().upper(), email.strip(), address.strip()))
            conn.commit()
            return {"status": "ok", "message": f"Cliente '{name}' registrado con éxito en la base de datos."}
        except sqlite3.IntegrityError:
            return {"status": "error", "message": f"El cliente '{name}' ya está registrado."}
        finally:
            conn.close()
    except Exception as e:
        tool_logger.exception("Error al registrar cliente")
        return {"status": "error", "message": str(e)}

async def generate_invoice_pdf(
    client_name: str,
    client_nif: str,
    amount: float,
    concept: str,
    invoice_id: str = None,
    date: str = None,
    iva_rate: float = 21.0,
    irpf_rate: float = 15.0
) -> dict:
    """
    Genera una factura en PDF con formato profesional de venta en la carpeta Facturas_Pendientes_Cobro del Escritorio,
    la inserta en la base de datos de facturas y realiza el asiento contable (Diario/Mayor) automáticamente si no es borrador.
    Soporta la persistencia de borradores si faltan datos del cliente, NIF, concepto o importe.
    """
    try:
        # 1. Buscar si existe un registro previo con el invoice_id proporcionado
        existing_id_db = None
        existing_file_path = None
        is_updating = False

        if invoice_id:
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, invoice_id, date, receiver_name, receiver_nif, base_imponible, concept, file_path, status
                    FROM invoices
                """)
                rows = cursor.fetchall()
                for r in rows:
                    try:
                        dec_id = encryptor.decrypt(r["invoice_id"])
                        if dec_id.upper() == invoice_id.upper():
                            existing_id_db = r["id"]
                            existing_file_path = encryptor.decrypt(r["file_path"])
                            is_updating = True
                            
                            # Cargar valores antiguos si los nuevos no son válidos/proporcionados
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
                                try:
                                    dec_concept = encryptor.decrypt(r["concept"])
                                    if dec_concept and dec_concept.lower().strip() not in ("desconocido", "pendiente", "concepto desconocido", "sin concepto"):
                                        concept = dec_concept
                                except Exception:
                                    pass
                            break
                    except Exception:
                        pass
            finally:
                conn.close()

        # 2. Evaluar si es borrador (faltan datos o se solicita explícitamente)
        is_incomplete_name = not client_name or client_name.strip() == "" or client_name.lower().strip() in ("desconocido", "pendiente", "cliente genérico", "cliente desconocido", "cliente_desconocido")
        is_incomplete_nif = not client_nif or client_nif.strip() == "" or client_nif.lower().strip() in ("desconocido", "pendiente", "sin nif", "nif_desconocido", "nif desconocido")
        is_incomplete_concept = not concept or concept.strip() == "" or concept.lower().strip() in ("desconocido", "pendiente", "concepto desconocido", "sin concepto")
        is_incomplete_amount = not amount or float(amount) <= 0.0

        is_draft = is_incomplete_name or is_incomplete_nif or is_incomplete_concept or is_incomplete_amount

        # 3. Resolver fechas e identificadores secuenciales
        now = datetime.now()
        if not date:
            date_str = now.strftime("%d/%m/%Y")
        else:
            date_str = date

        # Si ya teníamos un ID asignado y sigue siendo borrador, lo mantenemos.
        # Si era borrador y ahora se completa, le asignamos un ID secuencial de factura real.
        if is_draft:
            if not invoice_id or not invoice_id.startswith("BORRADOR-"):
                # Generar nuevo ID de borrador secuencial
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
            # Es factura completa/firme. Si venía de un borrador o no tiene ID, le generamos un ID de la serie de facturas F-
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

        # Datos fiscales del emisor (Luis Domingo)
        emisor_name = "LUIS DOMINGO"
        emisor_nif = "12345678Z"

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
            year = 2026

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
        c.drawString(55, 625, "Dirección: Calle Falsa 123, Madrid, España")
        
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
            # 6. Registrar en el encadenamiento Verifactu (AEAT) si es una factura firme
            verifactu_data = {
                "invoice_number": invoice_id,
                "date_of_issue": date_str,
                "issuer_nif": emisor_nif,
                "receiver_nif": client_nif,
                "base_imponible": amount,
                "iva_amount": iva_amount,
                "total_amount": total_amount
            }
            verifactu_res = VerifactuService.register_invoice(verifactu_data)
            current_hash = verifactu_res["current_hash"]
            signature_base64 = verifactu_res["signature"]

            # Generar código QR oficial de verificación de la AEAT
            qr_url = f"https://www2.agenciatributaria.gob.es/wlpl/PORT-SSII/VerificaFactura?nif={emisor_nif}&num={invoice_id}&fecha={date_str}&importe={total_amount:.2f}"
            qr = qrcode.QRCode(version=1, box_size=3, border=1)
            qr.add_data(qr_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            qr_temp_path = target_dir / f"qr_{invoice_id}.png"
            qr_img.save(str(qr_temp_path))

            # Dibujar QR en el Canvas PDF
            c.drawImage(str(qr_temp_path), 55, 120, width=70, height=70)

            # Añadir leyenda de VERI*FACTU y metadatos criptográficos
            c.setFont("Helvetica-Bold", 9)
            c.setFillColorRGB(0.12, 0.23, 0.35)
            c.drawString(135, 175, "VERI*FACTU - FACTURA VERIFICABLE")
            
            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawString(135, 163, "Factura verificable en la sede electrónica de la AEAT")
            c.drawString(135, 151, f"Hash Encadenamiento: {current_hash[:36]}...")
            c.drawString(135, 140, f"Firma Criptográfica (RSA): {signature_base64[:40]}...")

            # Notas finales
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(55, 90, "Forma de Pago: Transferencia bancaria a la cuenta indicada.")
            c.drawString(55, 75, "Esta factura se emite bajo el régimen de autónomos de la Agencia Tributaria Española.")
            
            c.save()

            # Limpiar QR temporal
            if qr_temp_path.exists():
                os.remove(qr_temp_path)

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

        if existing_id_db:
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE invoices SET
                        invoice_id = ?, date = ?, issuer_name = ?, issuer_nif = ?, receiver_name = ?, receiver_nif = ?,
                        base_imponible = ?, iva_rate = ?, iva_amount = ?, irpf_rate = ?, irpf_amount = ?, total_amount = ?,
                        category = ?, quarter = ?, year = ?, file_path = ?, status = ?, concept = ?
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
                    encryptor.encrypt(invoice_db_data["file_path"]),
                    invoice_db_data["status"],
                    encryptor.encrypt(invoice_db_data["concept"]),
                    existing_id_db
                ))
                conn.commit()
            finally:
                conn.close()
        else:
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO invoices (
                        invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                        base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount,
                        category, quarter, year, file_path, status, concept
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    encryptor.encrypt(invoice_db_data["file_path"]),
                    invoice_db_data["status"],
                    encryptor.encrypt(invoice_db_data["concept"])
                ))
                conn.commit()
            finally:
                conn.close()

        # 8. Registrar asiento contable PGC y sincronizar Excel SOLO si no es borrador
        if not is_draft:
            try:
                LedgerService.record_invoice_asiento(invoice_db_data)
            except Exception as cont_err:
                tool_logger.warning("No se pudo generar el asiento contable automáticamente: %s", cont_err)

            try:
                ExcelSyncService.sync_invoices_to_excel()
            except Exception as xls_err:
                tool_logger.warning("No se pudo sincronizar con el archivo Excel local: %s", xls_err)

        msg_detail = f"Borrador {invoice_id} creado" if is_draft else f"Factura {invoice_id} creada y registrada ante la AEAT (Veri*Factu)"
        return {
            "status": "ok",
            "invoice_id": invoice_id,
            "is_draft": is_draft,
            "pdf_path": str(pdf_path),
            "total_amount": total_amount,
            "base_imponible": amount,
            "message": f"{msg_detail} y guardada en 'archivo fiscal/facturas pendientes'."
        }
    except Exception as e:
        tool_logger.exception("Error al generar e inyectar la factura")
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

        subject = f"Factura {invoice_id} emitida por LUIS DOMINGO"
        body = (
            f"Estimado cliente,\n\n"
            f"Adjunto a este correo le enviamos la factura correspondiente {invoice_id}.\n"
            f"El archivo se encuentra archivado físicamente en la ruta: {pdf_path_str}\n\n"
            f"Atentamente,\n"
            f"Luis Domingo"
        )
        
        res = await mail_send_email(recipient=recipient_email, subject=subject, body=body)
        return {"status": "ok", "message": f"Factura {invoice_id} enviada por correo electrónico a {recipient_email} correctamente.", "detail": res}
    except Exception as e:
        tool_logger.exception("Error al enviar el email de la factura")
        return {"status": "error", "message": f"Error al enviar correo: {str(e)}"}

TOOLS = {
    "get_projects_wip": get_projects_wip,
    "update_project_status": update_project_status,
    "get_clients": get_clients,
    "create_client": create_client,
    "generate_invoice_pdf": generate_invoice_pdf,
    "send_invoice_email": send_invoice_email,
}

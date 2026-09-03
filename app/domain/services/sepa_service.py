import datetime
import uuid
import xml.etree.ElementTree as ET
from app.adapters.memory.memory import _get_connection

class SepaService:
    @classmethod
    def generate_remittance_xml(cls) -> dict:
        """
        Genera el archivo XML SEPA (pain.001.001.03) para transferencias pendientes.
        Extrae la cuenta bancaria marcada como por defecto para remesas, o la primera activa si no hay.
        Lee los registros en bank_transfers con status = 'initiated'.
        Retorna un dict con el status, xml_content y transfer_ids incluidos.
        """
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # Obtener cuenta del emisor (prioridad a la de por defecto)
            cursor.execute("SELECT iban, bank_name FROM bank_connections WHERE is_default_remittance = 1 LIMIT 1")
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT iban, bank_name FROM bank_connections WHERE status = 'active' LIMIT 1")
                row = cursor.fetchone()
                if not row:
                    return {"status": "error", "message": "No hay cuentas bancarias activas para emitir la remesa. Añade una conexión bancaria primero."}
            
            issuer_iban = row["iban"]
            
            # Obtener datos del perfil del usuario (emisor)
            cursor.execute("SELECT razon_social FROM user_profile LIMIT 1")
            profile_row = cursor.fetchone()
            issuer_name = profile_row["razon_social"] if profile_row else "Usuario de Alfonso"
            
            # Leer transferencias pendientes
            cursor.execute("SELECT id, transfer_date, recipient_name, recipient_iban, amount, concept FROM bank_transfers WHERE status = 'initiated'")
            transfers = cursor.fetchall()
            
            if not transfers:
                return {"status": "error", "message": "No hay pagos pendientes ('initiated') para generar la remesa."}
            
            # Procesar datos
            total_sum = sum(t["amount"] for t in transfers)
            nb_of_txs = len(transfers)
            msg_id = f"MSG-{uuid.uuid4().hex[:12].upper()}"
            pmt_inf_id = f"PMT-{uuid.uuid4().hex[:12].upper()}"
            creation_dt = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            exec_dt = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # Construcción del XML XML SEPA (pain.001.001.03)
            ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
            ET.register_namespace("", ns)
            
            document = ET.Element(f"{{{ns}}}Document")
            cstmr_cdt_trf_initn = ET.SubElement(document, f"{{{ns}}}CstmrCdtTrfInitn")
            
            # GrpHdr
            grp_hdr = ET.SubElement(cstmr_cdt_trf_initn, f"{{{ns}}}GrpHdr")
            ET.SubElement(grp_hdr, f"{{{ns}}}MsgId").text = msg_id
            ET.SubElement(grp_hdr, f"{{{ns}}}CreDtTm").text = creation_dt
            ET.SubElement(grp_hdr, f"{{{ns}}}NbOfTxs").text = str(nb_of_txs)
            ET.SubElement(grp_hdr, f"{{{ns}}}CtrlSum").text = f"{total_sum:.2f}"
            initg_pty = ET.SubElement(grp_hdr, f"{{{ns}}}InitgPty")
            ET.SubElement(initg_pty, f"{{{ns}}}Nm").text = issuer_name
            
            # PmtInf
            pmt_inf = ET.SubElement(cstmr_cdt_trf_initn, f"{{{ns}}}PmtInf")
            ET.SubElement(pmt_inf, f"{{{ns}}}PmtInfId").text = pmt_inf_id
            ET.SubElement(pmt_inf, f"{{{ns}}}PmtMtd").text = "TRF"
            ET.SubElement(pmt_inf, f"{{{ns}}}NbOfTxs").text = str(nb_of_txs)
            ET.SubElement(pmt_inf, f"{{{ns}}}CtrlSum").text = f"{total_sum:.2f}"
            
            pmt_tp_inf = ET.SubElement(pmt_inf, f"{{{ns}}}PmtTpInf")
            svc_lvl = ET.SubElement(pmt_tp_inf, f"{{{ns}}}SvcLvl")
            ET.SubElement(svc_lvl, f"{{{ns}}}Cd").text = "SEPA"
            
            ET.SubElement(pmt_inf, f"{{{ns}}}ReqdExctnDt").text = exec_dt
            
            dbtr = ET.SubElement(pmt_inf, f"{{{ns}}}Dbtr")
            ET.SubElement(dbtr, f"{{{ns}}}Nm").text = issuer_name
            
            dbtr_acct = ET.SubElement(pmt_inf, f"{{{ns}}}DbtrAcct")
            dbtr_acct_id = ET.SubElement(dbtr_acct, f"{{{ns}}}Id")
            ET.SubElement(dbtr_acct_id, f"{{{ns}}}IBAN").text = issuer_iban
            
            dbtr_agt = ET.SubElement(pmt_inf, f"{{{ns}}}DbtrAgt")
            fin_instn_id = ET.SubElement(dbtr_agt, f"{{{ns}}}FinInstnId")
            othr = ET.SubElement(fin_instn_id, f"{{{ns}}}Othr")
            ET.SubElement(othr, f"{{{ns}}}Id").text = "NOTPROVIDED"
            
            # Transacciones individuales
            transfer_ids = []
            for t in transfers:
                transfer_ids.append(t["id"])
                cdt_trf_tx_inf = ET.SubElement(pmt_inf, f"{{{ns}}}CdtTrfTxInf")
                
                pmt_id = ET.SubElement(cdt_trf_tx_inf, f"{{{ns}}}PmtId")
                ET.SubElement(pmt_id, f"{{{ns}}}EndToEndId").text = f"E2E-{t['id']}-{uuid.uuid4().hex[:6]}"
                
                amt = ET.SubElement(cdt_trf_tx_inf, f"{{{ns}}}Amt")
                instd_amt = ET.SubElement(amt, f"{{{ns}}}InstdAmt")
                instd_amt.attrib["Ccy"] = "EUR"
                instd_amt.text = f"{t['amount']:.2f}"
                
                cdtr = ET.SubElement(cdt_trf_tx_inf, f"{{{ns}}}Cdtr")
                ET.SubElement(cdtr, f"{{{ns}}}Nm").text = t["recipient_name"]
                
                cdtr_acct = ET.SubElement(cdt_trf_tx_inf, f"{{{ns}}}CdtrAcct")
                cdtr_acct_id = ET.SubElement(cdtr_acct, f"{{{ns}}}Id")
                ET.SubElement(cdtr_acct_id, f"{{{ns}}}IBAN").text = t["recipient_iban"]
                
                if t["concept"]:
                    rmt_inf = ET.SubElement(cdt_trf_tx_inf, f"{{{ns}}}RmtInf")
                    ET.SubElement(rmt_inf, f"{{{ns}}}Ustrd").text = str(t["concept"])
            
            # Marcar transferencias como emitidas en remesa
            for t_id in transfer_ids:
                cursor.execute("UPDATE bank_transfers SET status = 'remitted' WHERE id = ?", (t_id,))
            conn.commit()
            
            xml_string = ET.tostring(document, encoding="utf-8", xml_declaration=True).decode("utf-8")
            
            return {
                "status": "ok",
                "message": f"Remesa SEPA generada correctamente para {nb_of_txs} pago(s).",
                "xml_content": xml_string,
                "transfer_ids": transfer_ids,
                "total_sum": total_sum
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Error generando la remesa SEPA: {str(e)}"}
        finally:
            conn.close()

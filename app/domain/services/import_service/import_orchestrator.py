import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

logger = logging.getLogger("import_orchestrator")

class ImportOrchestrator:
    """
    Orchestrates the import process. 
    Receives parsed invoices, encrypts them, and saves to the database.
    """
    
    @classmethod
    def save_invoices(cls, invoices: List[Dict[str, Any]]) -> int:
        """
        Saves a list of parsed invoices into the database, marking them as historical.
        Returns the number of invoices inserted.
        """
        if not invoices:
            return 0
            
        inserted_count = 0
        with _get_connection() as conn:
            for inv in invoices:
                try:
                    # Encrypt fields
                    enc_invoice_id = encryptor.encrypt(f"IMP-{int(datetime.now().timestamp())}-{inserted_count}")
                    enc_date = encryptor.encrypt(inv["date"])
                    enc_issuer_name = encryptor.encrypt(inv["issuer_name"])
                    enc_issuer_nif = encryptor.encrypt(inv["issuer_nif"])
                    enc_receiver_name = encryptor.encrypt(inv["receiver_name"])
                    enc_receiver_nif = encryptor.encrypt(inv["receiver_nif"])
                    enc_base = encryptor.encrypt(str(inv["base_imponible"]))
                    enc_iva_rate = encryptor.encrypt(str(inv["iva_rate"]))
                    enc_iva_amount = encryptor.encrypt(str(inv["iva_amount"]))
                    enc_irpf_rate = encryptor.encrypt(str(inv["irpf_rate"]))
                    enc_irpf_amount = encryptor.encrypt(str(inv["irpf_amount"]))
                    enc_total = encryptor.encrypt(str(inv["total_amount"]))
                    
                    category = inv["category"]
                    quarter = inv["quarter"]
                    year = inv["year"]
                    status = inv["status"]
                    source = inv["source"]
                    
                    # Ensure is_historical flag exists in the schema or we use a metadata approach
                    # If we don't have is_historical column, we can just use status or source.
                    # We will insert standard invoice structure.
                    
                    conn.execute("""
                        INSERT INTO invoices (
                            invoice_id, date, issuer_name, issuer_nif, 
                            receiver_name, receiver_nif, base_imponible, 
                            iva_rate, iva_amount, irpf_rate, irpf_amount, 
                            total_amount, category, quarter, year, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        enc_invoice_id, enc_date, enc_issuer_name, enc_issuer_nif,
                        enc_receiver_name, enc_receiver_nif, enc_base,
                        enc_iva_rate, enc_iva_amount, enc_irpf_rate, enc_irpf_amount,
                        enc_total, category, quarter, year, status
                    ))
                    inserted_count += 1
                except Exception as e:
                    logger.error(f"Error saving imported invoice: {str(e)}")
                    continue
                    
            conn.commit()
            
        logger.info(f"Imported {inserted_count} invoices successfully.")
        return inserted_count

import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger("a3_parser")

class A3Parser:
    """
    Parser for A3ECO/A3CON SUENLACE.DAT files.
    Extracts invoice data from fixed-width ASCII text.
    """
    
    @classmethod
    def parse(cls, content: str) -> List[Dict[str, Any]]:
        """
        Parses the fixed-width content and returns a list of invoice dictionaries.
        Basic implementation for extracting Date, Amounts, and NIF.
        """
        invoices = []
        lines = content.splitlines()
        
        for line in lines:
            if not line.strip():
                continue
                
            try:
                # Simplified fixed-width extraction (Example format)
                # In a real SUENLACE.DAT, layout is strictly defined by A3 documentation.
                # 0-2: Entry type
                # 2-10: Date (DDMMAAAA)
                # 10-20: Account
                # ...
                
                entry_type = line[0:2].strip()
                # Only process typical invoice entry types (mock logic)
                if entry_type not in ("01", "02", "11", "12"):
                    continue
                    
                date_str = line[2:10]
                if not date_str.strip() or len(date_str) < 8:
                    continue
                
                dt = datetime.strptime(date_str, "%d%m%Y")
                iso_date = dt.strftime("%Y-%m-%d")
                
                # Mock positions for extraction
                nif = line[20:30].strip() or "UNKNOWN"
                name = line[30:70].strip() or "Cliente/Proveedor A3"
                
                base_str = line[70:82].strip() or "0"
                base = float(base_str) / 100.0  # Usually implies 2 decimals
                
                iva_amount_str = line[82:94].strip() or "0"
                iva_amount = float(iva_amount_str) / 100.0
                
                total = base + iva_amount
                
                category = "expense" if entry_type in ("02", "12") else "income"
                
                invoices.append({
                    "date": iso_date,
                    "issuer_name": name if category == "expense" else "Autónomo",
                    "issuer_nif": nif if category == "expense" else "AUTONOMO-NIF",
                    "receiver_name": "Autónomo" if category == "expense" else name,
                    "receiver_nif": "AUTONOMO-NIF" if category == "expense" else nif,
                    "base_imponible": base,
                    "iva_amount": iva_amount,
                    "iva_rate": 21.0 if base > 0 and iva_amount > 0 else 0.0,
                    "irpf_amount": 0.0,
                    "irpf_rate": 0.0,
                    "total_amount": total,
                    "category": category,
                    "quarter": (dt.month - 1) // 3 + 1,
                    "year": dt.year,
                    "status": "firmada",
                    "source": "A3_SUENLACE"
                })
            except Exception as e:
                logger.warning(f"Failed to parse A3 line: {str(e)}")
                continue
                
        return invoices

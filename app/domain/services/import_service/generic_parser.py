import csv
import logging
from typing import List, Dict, Any
from datetime import datetime
import io

logger = logging.getLogger("generic_parser")

class GenericParser:
    """
    Parser for Generic CSV/Excel files using column mapping.
    """
    
    @classmethod
    def parse_csv(cls, content: str, mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Parses CSV content based on a column mapping.
        mapping example: {"date": "Fecha", "base": "Base Imponible", ...}
        """
        invoices = []
        try:
            f = io.StringIO(content)
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    date_val = row.get(mapping.get("date", ""))
                    if not date_val:
                        continue
                        
                    dt = datetime.strptime(date_val, "%Y-%m-%d")
                    
                    base = float(row.get(mapping.get("base", ""), 0))
                    iva_amount = float(row.get(mapping.get("iva_amount", ""), 0))
                    total = float(row.get(mapping.get("total", ""), base + iva_amount))
                    category = row.get(mapping.get("category", ""), "expense").lower()
                    
                    invoices.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "issuer_name": row.get(mapping.get("issuer_name", ""), "Unknown"),
                        "issuer_nif": row.get(mapping.get("issuer_nif", ""), "UNKNOWN"),
                        "receiver_name": row.get(mapping.get("receiver_name", ""), "Unknown"),
                        "receiver_nif": row.get(mapping.get("receiver_nif", ""), "UNKNOWN"),
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
                        "source": "GENERIC_CSV"
                    })
                except Exception as row_e:
                    logger.warning(f"Failed to parse row: {row_e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing generic CSV: {e}")
            
        return invoices

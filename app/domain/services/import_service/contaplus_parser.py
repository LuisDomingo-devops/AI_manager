import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger("contaplus_parser")

class ContaPlusParser:
    """
    Parser for ContaPlus export files (Diario.txt / Subcuen.txt).
    """
    
    @classmethod
    def parse(cls, content: str) -> List[Dict[str, Any]]:
        """
        Parses ContaPlus ASCII files.
        Typically comma or tab delimited, sometimes custom separated.
        """
        invoices = []
        lines = content.splitlines()
        
        for line in lines:
            if not line.strip():
                continue
                
            try:
                # Mock ContaPlus Diario parsing
                # Assume comma separated for demonstration: Date, Account, Name, Base, IVA, Total
                parts = line.split(',')
                if len(parts) < 6:
                    continue
                    
                date_str = parts[0].strip()
                if len(date_str) < 8:
                    continue
                    
                dt = datetime.strptime(date_str, "%Y%m%d")
                iso_date = dt.strftime("%Y-%m-%d")
                
                account = parts[1].strip()
                name = parts[2].strip()
                base = float(parts[3].strip())
                iva_amount = float(parts[4].strip())
                total = float(parts[5].strip())
                
                category = "income" if account.startswith("7") else "expense"
                
                invoices.append({
                    "date": iso_date,
                    "issuer_name": name if category == "expense" else "Autónomo",
                    "issuer_nif": "UNKNOWN",
                    "receiver_name": "Autónomo" if category == "expense" else name,
                    "receiver_nif": "UNKNOWN",
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
                    "source": "CONTAPLUS"
                })
            except Exception as e:
                logger.warning(f"Failed to parse ContaPlus line: {str(e)}")
                continue
                
        return invoices

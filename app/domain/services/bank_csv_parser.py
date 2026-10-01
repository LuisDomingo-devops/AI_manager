"""
Parser para extractos bancarios en formato CSV con autodetección de delimitador y columnas estándar españolas.
"""

import csv
import io
import re
from typing import Optional, Dict
from datetime import datetime
from app.domain.models.billing import BankStatementDTO, BankEntryDTO


class BankCsvParser:
    """Parsea CSVs bancarios con soporte para formatos numéricos españoles y europeos."""

    @staticmethod
    def _detect_delimiter(text: str) -> str:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if ";" in first_line:
            return ";"
        if "\t" in first_line:
            return "\t"
        return ","

    @staticmethod
    def _parse_amount(raw_val: str) -> float:
        if not raw_val:
            return 0.0
        cleaned = raw_val.replace("€", "").replace("EUR", "").strip()
        cleaned = cleaned.replace(" ", "")
        
        # Formato español: 1.234,56
        if "." in cleaned and "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
            
        try:
            return float(cleaned)
        except Exception:
            return 0.0

    @staticmethod
    def _parse_date(raw_date: str) -> str:
        raw_date = raw_date.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                dt = datetime.strptime(raw_date, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                continue
        return datetime.now().strftime("%Y-%m-%d")

    def parse(self, csv_content: str, account_iban: Optional[str] = None) -> BankStatementDTO:
        delimiter = self._detect_delimiter(csv_content)
        reader = csv.reader(io.StringIO(csv_content), delimiter=delimiter)

        headers = None
        col_map: Dict[str, int] = {}
        entries = []

        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue

            if headers is None:
                # Detectar fila de cabeceras
                row_upper = [c.strip().upper() for c in row]
                if any("FECHA" in c or "CONCEPTO" in c or "IMPORTE" in c for c in row_upper):
                    headers = row_upper
                    for idx, h in enumerate(headers):
                        if "FECHA VALOR" in h or "F. VALOR" in h:
                            col_map["val_date"] = idx
                        elif "FECHA" in h or "F. OPER" in h:
                            col_map["op_date"] = idx
                        elif "CONCEPTO" in h or "DETALLE" in h or "DESCRIP" in h:
                            col_map["concept"] = idx
                        elif "IMPORTE" in h or "CANTIDAD" in h:
                            col_map["amount"] = idx
                        elif "SALDO" in h:
                            col_map["balance"] = idx
                    continue

            # Fila de datos
            if "op_date" not in col_map or "amount" not in col_map:
                continue

            op_date_raw = row[col_map["op_date"]] if col_map["op_date"] < len(row) else ""
            val_date_raw = row[col_map["val_date"]] if "val_date" in col_map and col_map["val_date"] < len(row) else op_date_raw
            concept = row[col_map["concept"]] if "concept" in col_map and col_map["concept"] < len(row) else "Movimiento bancario"
            amount_raw = row[col_map["amount"]] if col_map["amount"] < len(row) else "0.0"
            balance_raw = row[col_map["balance"]] if "balance" in col_map and col_map["balance"] < len(row) else "0.0"

            parsed_amount = self._parse_amount(amount_raw)
            parsed_balance = self._parse_amount(balance_raw)

            entries.append(BankEntryDTO(
                id=len(entries) + 1,
                operation_date=self._parse_date(op_date_raw),
                value_date=self._parse_date(val_date_raw),
                concept=concept.strip(),
                amount=parsed_amount,
                balance_after=parsed_balance,
                reconciliation_status="UNRECONCILED"
            ))

        return BankStatementDTO(
            source_type="CSV",
            account_iban=account_iban or "ES0000000000000000000000",
            initial_balance=0.0,
            final_balance=entries[-1].balance_after if entries else 0.0,
            import_date=datetime.now().strftime("%Y-%m-%d"),
            entries=entries
        )

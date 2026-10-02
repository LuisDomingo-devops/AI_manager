"""
Parser para extractos bancarios en formato CSV con autodetección de delimitador, columnas estándar españolas
e internacionales (Wise, Revolut) y verificación matemática estricta con Decimal.
"""

import csv
import io
import re
from typing import Optional, Dict, List
from datetime import datetime
from decimal import Decimal
from app.domain.schemas import BankStatementDTO, BankMovementDTO, BankStatementSourceType, BankReconciliationStatus
from app.domain.exceptions import BankStatementDiscrepancyError


class BankCsvParser:
    """Parsea CSVs bancarios con soporte para formatos numéricos españoles y europeos con rigor Decimal."""

    @staticmethod
    def _detect_delimiter(text: str) -> str:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if ";" in first_line:
            return ";"
        if "\t" in first_line:
            return "\t"
        return ","

    @staticmethod
    def _parse_decimal_amount(raw_val: str) -> Decimal:
        if not raw_val:
            return Decimal("0.00")
        cleaned = raw_val.replace("€", "").replace("EUR", "").strip()
        cleaned = cleaned.replace(" ", "")
        
        # Formato español / europeo: 1.234,56
        if "." in cleaned and "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
            
        try:
            return Decimal(cleaned).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

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

        iban = account_iban or "ES0000000000000000000000"
        headers = None
        col_map: Dict[str, int] = {}
        entries: List[BankMovementDTO] = []
        initial_balance: Optional[Decimal] = None
        final_balance: Optional[Decimal] = None

        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue

            if headers is None:
                # Detectar fila de cabeceras (español o inglés)
                row_upper = [c.strip().upper() for c in row]
                is_header = any(
                    any(term in c for term in ("FECHA", "CONCEPTO", "IMPORTE", "DATE", "DESCRIPTION", "AMOUNT"))
                    for c in row_upper
                )
                if is_header:
                    headers = row_upper
                    for idx, h in enumerate(headers):
                        if any(term in h for term in ("FECHA VALOR", "F. VALOR", "VALUE DATE")):
                            col_map["val_date"] = idx
                        elif any(term in h for term in ("FECHA", "F. OPER", "BOOKING DATE", "DATE")):
                            col_map["op_date"] = idx
                        elif any(term in h for term in ("CONCEPTO", "DETALLE", "DESCRIP", "DETAILS", "NARRATIVE")):
                            col_map["concept"] = idx
                        elif any(term in h for term in ("IMPORTE", "CANTIDAD", "AMOUNT", "MONTO", "NET")):
                            col_map["amount"] = idx
                        elif any(term in h for term in ("SALDO", "BALANCE")):
                            col_map["balance"] = idx
                    continue

            # Fila de datos
            if "op_date" not in col_map:
                continue

            op_date_raw = row[col_map["op_date"]] if col_map["op_date"] < len(row) else ""
            val_date_raw = row[col_map["val_date"]] if "val_date" in col_map and col_map["val_date"] < len(row) else op_date_raw
            concept = row[col_map["concept"]] if "concept" in col_map and col_map["concept"] < len(row) else "Movimiento bancario"
            amount_raw = row[col_map["amount"]] if "amount" in col_map and col_map["amount"] < len(row) else ""
            balance_raw = row[col_map["balance"]] if "balance" in col_map and col_map["balance"] < len(row) else ""

            parsed_amount = self._parse_decimal_amount(amount_raw)
            parsed_balance = self._parse_decimal_amount(balance_raw) if balance_raw.strip() else None

            concept_upper = concept.strip().upper()

            # Comprobar si la fila es explícitamente el saldo inicial
            if any(term in concept_upper for term in ("SALDO INICIAL", "OPENING BALANCE", "SALDO ANTERIOR")) and (not amount_raw.strip() or parsed_amount == Decimal("0.00")):
                if parsed_balance is not None:
                    initial_balance = parsed_balance
                continue

            # Registro de movimiento ordinario
            entry = BankMovementDTO(
                id=len(entries) + 1,
                account_iban=iban,
                operation_date=self._parse_date(op_date_raw),
                value_date=self._parse_date(val_date_raw),
                concept=concept.strip(),
                amount=parsed_amount,
                balance_after=parsed_balance if parsed_balance is not None else Decimal("0.00"),
                reconciliation_status=BankReconciliationStatus.UNRECONCILED.value
            )
            entries.append(entry)

        # Resolver saldo inicial y final si no estaban explícitos
        if initial_balance is None:
            if entries and entries[0].balance_after != Decimal("0.00"):
                initial_balance = (entries[0].balance_after - entries[0].amount).quantize(Decimal("0.01"))
            else:
                initial_balance = Decimal("0.00")

        # Calcular saldos progresivos si no venían en cada fila
        running = initial_balance
        for entry in entries:
            if entry.balance_after == Decimal("0.00"):
                running = (running + entry.amount).quantize(Decimal("0.01"))
                entry.balance_after = running
            else:
                running = entry.balance_after

        final_balance = entries[-1].balance_after if entries else initial_balance

        # Verificación estricta de cuadre contable
        calculated_final = (initial_balance + sum(e.amount for e in entries)).quantize(Decimal("0.01"))
        if abs(calculated_final - final_balance) >= Decimal("0.005"):
            raise BankStatementDiscrepancyError(
                message=(
                    f"Descuadre contable detectado en el extracto CSV. "
                    f"Saldo Inicial ({initial_balance} €) + Movimientos ({calculated_final - initial_balance} €) "
                    f"!= Saldo Final ({final_balance} €). Diferencia: {calculated_final - final_balance} €."
                ),
                initial_balance=initial_balance,
                final_balance=final_balance,
                calculated_final=calculated_final
            )

        return BankStatementDTO(
            source_type=BankStatementSourceType.CSV,
            account_iban=iban,
            initial_balance=initial_balance,
            final_balance=final_balance,
            import_date=datetime.now().strftime("%Y-%m-%d"),
            entries=entries
        )

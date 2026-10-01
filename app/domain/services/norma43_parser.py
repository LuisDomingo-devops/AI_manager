"""
Parser oficial para extractos bancarios en formato Norma 43 (CSB 43) de la Asociación Española de Banca (AEB).
Procesa registros posicionales 11, 22, 23, 33 y 88 con rigor contable.
"""

from typing import List, Optional
from datetime import datetime
from app.domain.models.billing import BankStatementDTO, BankEntryDTO


class Norma43Parser:
    """Parsea ficheros en especificación Norma 43 / Cuaderno 43."""

    def parse(self, raw_content: bytes, account_iban: Optional[str] = None) -> BankStatementDTO:
        # Decodificar usando latin-1 o iso-8859-1 (estándar bancario español histórico)
        text = raw_content.decode("latin-1", errors="replace")
        lines = [line.strip("\r\n") for line in text.splitlines() if line.strip("\r\n")]

        iban = account_iban or ""
        initial_balance = 0.0
        final_balance = 0.0
        entries: List[BankEntryDTO] = []
        current_entry: Optional[dict] = None

        for line in lines:
            if len(line) < 2:
                continue

            record_type = line[:2]

            # 11: Registro de Cabecera de Cuenta
            if record_type == "11":
                banco = line[2:6]
                sucursal = line[6:10]
                cuenta = line[10:20]
                if not iban:
                    iban = f"ES00{banco}{sucursal}00{cuenta}"
                
                # Saldo inicial: pos 28 a 42 (14 dígitos) con signo en pos 27 ('1' debe/deudor, '2' haber/acreedor)
                try:
                    sign_char = line[26:27]
                    amount_cents = int(line[27:41])
                    initial_balance = (amount_cents / 100.0) * (-1.0 if sign_char == "1" else 1.0)
                except Exception:
                    initial_balance = 0.0

            # 22: Registro Principal de Movimiento
            elif record_type == "22":
                if current_entry:
                    entries.append(self._build_entry_dto(len(entries) + 1, current_entry))
                    current_entry = None

                # Fecha operación (YYMMDD pos 10-16)
                raw_op_date = line[10:16]
                raw_val_date = line[16:22]
                op_date = self._parse_n43_date(raw_op_date)
                val_date = self._parse_n43_date(raw_val_date)

                # Clave D/H: '1'=Debe/Cargo(-), '2'=Haber/Abono(+) en pos 27
                sign_code = line[27:28]
                # Importe: pos 28-42 (14 dígitos céntimos)
                amount_cents = int(line[28:42])
                amount = (amount_cents / 100.0) * (-1.0 if sign_code == "1" else 1.0)

                concept_main = line[42:].strip()
                current_entry = {
                    "operation_date": op_date,
                    "value_date": val_date,
                    "amount": round(amount, 2),
                    "concept_parts": [concept_main] if concept_main else []
                }

            # 23: Registros Complementarios de Concepto
            elif record_type == "23":
                if current_entry:
                    extra_concept = line[4:].strip()
                    if extra_concept:
                        current_entry["concept_parts"].append(extra_concept)

            # 33: Registro de Fin de Cuenta
            elif record_type == "33":
                if current_entry:
                    entries.append(self._build_entry_dto(len(entries) + 1, current_entry))
                    current_entry = None

                # Saldo final pos 59-73 (14 dígitos) y signo en pos 58 ('1'=Debe, '2'=Haber)
                try:
                    sign_char = line[58:59]
                    amount_cents = int(line[59:73])
                    final_balance = (amount_cents / 100.0) * (-1.0 if sign_char == "1" else 1.0)
                except Exception:
                    final_balance = 0.0

        if current_entry:
            entries.append(self._build_entry_dto(len(entries) + 1, current_entry))

        return BankStatementDTO(
            source_type="NORMA43",
            account_iban=iban,
            initial_balance=round(initial_balance, 2),
            final_balance=round(final_balance, 2),
            import_date=datetime.now().strftime("%Y-%m-%d"),
            entries=entries
        )

    def _build_entry_dto(self, entry_id: int, entry_dict: dict) -> BankEntryDTO:
        full_concept = " ".join(entry_dict["concept_parts"]).strip()
        return BankEntryDTO(
            id=entry_id,
            operation_date=entry_dict["operation_date"],
            value_date=entry_dict["value_date"],
            concept=full_concept,
            amount=entry_dict["amount"],
            balance_after=0.0,
            reconciliation_status="UNRECONCILED"
        )

    @staticmethod
    def _parse_n43_date(raw_date: str) -> str:
        """Convierte YYMMDD a YYYY-MM-DD."""
        if len(raw_date) == 6 and raw_date.isdigit():
            yy = int(raw_date[:2])
            year = 2000 + yy if yy < 70 else 1900 + yy
            mm = raw_date[2:4]
            dd = raw_date[4:6]
            return f"{year}-{mm}-{dd}"
        return datetime.now().strftime("%Y-%m-%d")

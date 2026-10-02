"""
Parser oficial para extractos bancarios en formato Norma 43 (CSB 43) de la Asociación Española de Banca (AEB).
Procesa registros posicionales 11, 22, 23, 33 y 88 con rigor contable Decimal y comprobación estricta de balance.
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.domain.schemas import BankStatementDTO, BankMovementDTO, BankStatementSourceType, BankReconciliationStatus
from app.domain.exceptions import BankStatementDiscrepancyError


class Norma43Parser:
    """Parsea ficheros en especificación Norma 43 / Cuaderno 43 con exactitud Decimal."""

    def parse(self, raw_content: bytes, account_iban: Optional[str] = None) -> BankStatementDTO:
        # Decodificar usando latin-1 o iso-8859-1 (estándar bancario español histórico)
        text = raw_content.decode("latin-1", errors="replace")
        lines = [line.strip("\r\n") for line in text.splitlines() if line.strip("\r\n")]

        iban = account_iban or ""
        initial_balance = Decimal("0.00")
        final_balance = Decimal("0.00")
        entries: List[BankMovementDTO] = []
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
                
                # Saldo inicial:
                # Estándar oficial CSB 43: fecha inicio (20:26), fecha fin (26:32), signo D/H (32:33), importe (33:47)
                # Variante compacta: fecha (20:26), signo D/H (26:27), importe (27:41)
                try:
                    if len(line) >= 47 and line[26:32].isdigit() and line[32:33] in ("1", "2") and line[33:47].isdigit():
                        sign_char = line[32:33]
                        amount_cents = int(line[33:47])
                    else:
                        sign_char = line[26:27]
                        amount_cents = int(line[27:41])
                    raw_dec = Decimal(amount_cents) / Decimal("100.00")
                    initial_balance = (-raw_dec if sign_char == "1" else raw_dec).quantize(Decimal("0.01"))
                except Exception:
                    initial_balance = Decimal("0.00")


            # 22: Registro Principal de Movimiento
            elif record_type == "22":
                if current_entry:
                    entries.append(self._build_entry_dto(len(entries) + 1, current_entry, iban))
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
                raw_amount = Decimal(amount_cents) / Decimal("100.00")
                amount = (-raw_amount if sign_code == "1" else raw_amount).quantize(Decimal("0.01"))

                concept_main = line[42:].strip()
                current_entry = {
                    "operation_date": op_date,
                    "value_date": val_date,
                    "amount": amount,
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
                    entries.append(self._build_entry_dto(len(entries) + 1, current_entry, iban))
                    current_entry = None

                # Saldo final: signo ('1'=Debe, '2'=Haber) e importe (14 dígitos)
                try:
                    import re
                    matches = re.findall(r'([12])(\d{14})', line)
                    if matches:
                        sign_char, amount_cents_str = matches[-1]
                        amount_cents = int(amount_cents_str)
                    else:
                        sign_char = line[58:59]
                        amount_cents = int(line[59:73])
                    raw_dec = Decimal(amount_cents) / Decimal("100.00")
                    final_balance = (-raw_dec if sign_char == "1" else raw_dec).quantize(Decimal("0.01"))
                except Exception:
                    final_balance = Decimal("0.00")



        if current_entry:
            entries.append(self._build_entry_dto(len(entries) + 1, current_entry, iban))

        # Calcular saldos progresivos (balance_after) para cada apunte
        running = initial_balance
        for entry in entries:
            running = (running + entry.amount).quantize(Decimal("0.01"))
            entry.balance_after = running

        # Validación estricta de cuadre contable
        calculated_final = (initial_balance + sum(e.amount for e in entries)).quantize(Decimal("0.01"))
        if abs(calculated_final - final_balance) >= Decimal("0.005"):
            raise BankStatementDiscrepancyError(
                message=(
                    f"Descuadre contable detectado en el extracto Norma 43. "
                    f"Saldo Inicial ({initial_balance} €) + Movimientos ({calculated_final - initial_balance} €) "
                    f"!= Saldo Final ({final_balance} €). Diferencia: {calculated_final - final_balance} €."
                ),
                initial_balance=initial_balance,
                final_balance=final_balance,
                calculated_final=calculated_final
            )

        return BankStatementDTO(
            source_type=BankStatementSourceType.NORMA43,
            account_iban=iban,
            initial_balance=initial_balance,
            final_balance=final_balance,
            import_date=datetime.now().strftime("%Y-%m-%d"),
            entries=entries
        )

    def _build_entry_dto(self, entry_id: int, entry_dict: dict, account_iban: str) -> BankMovementDTO:
        full_concept = " ".join(entry_dict["concept_parts"]).strip()
        return BankMovementDTO(
            id=entry_id,
            account_iban=account_iban,
            operation_date=entry_dict["operation_date"],
            value_date=entry_dict["value_date"],
            concept=full_concept,
            amount=entry_dict["amount"],
            balance_after=Decimal("0.00"),
            reconciliation_status=BankReconciliationStatus.UNRECONCILED.value
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

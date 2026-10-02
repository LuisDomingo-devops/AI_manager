"""
Motor de Conciliación Bancaria Inteligente con correspondencia probabilística ponderada.
Conforme al contrato de conciliación bancaria de Alfonso AI Konta y normativa PGC.
"""

from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.domain.models.billing import InvoiceDTO, InvoiceType, InvoiceStatus
from app.domain.schemas import (
    BankMovementDTO,
    ReconciliationSuggestionDTO,
    ApplyReconciliationCommand,
    ReconciliationResultDTO,
)
from app.domain.accounting.ports import RecordJournalEntryCommand, JournalLineDTO
from app.domain.accounting.services import AccountingService
from app.domain.exceptions import BankReconciliationConflictError
from app.infrastructure.database.connection_manager import write_transaction, get_readonly_connection


class BankReconciliationEngine:
    """Calcula sugerencias de casación entre extractos y facturas y aplica conciliaciones confirmadas con asiento PGC."""

    def __init__(self, accounting_service: Optional[AccountingService] = None):
        self.accounting_service = accounting_service or AccountingService()

    def suggest_matches(
        self,
        unlinked_entries: List[BankMovementDTO],
        open_invoices: List[InvoiceDTO],
        min_score: float = 0.70
    ) -> List[ReconciliationSuggestionDTO]:
        suggestions: List[ReconciliationSuggestionDTO] = []

        for entry in unlinked_entries:
            entry_amt = Decimal(str(entry.amount)).quantize(Decimal("0.01"))
            # Determinar cuentas por defecto según signo
            is_credit = entry_amt >= Decimal("0.00")
            debit_acc = "572" if is_credit else "400"
            credit_acc = "430" if is_credit else "572"

            for inv in open_invoices:
                score = 0.0
                criteria: List[str] = []
                fee_amt = Decimal("0.00")

                inv_amt = Decimal(str(inv.total_amount)).quantize(Decimal("0.01"))
                entry_abs = abs(entry_amt)
                inv_abs = abs(inv_amt)

                # 1. Coincidencia de importe o importe ajustado por comisión: peso 0.50
                diff = (inv_abs - entry_abs).quantize(Decimal("0.01"))
                if abs(entry_abs - inv_abs) < Decimal("0.01"):
                    score += 0.50
                    criteria.append("exact_amount")
                elif Decimal("0.00") < diff <= (inv_abs * Decimal("0.15")):
                    # Diferencia admisible como comisión de pasarela (ej. TPV / Stripe <= 15%)
                    score += 0.50
                    criteria.append("amount_with_fee_match")
                    fee_amt = diff
                elif Decimal("0.00") < diff <= Decimal("50.00") and any(
                    k in (entry.concept or "").upper() for k in ("STRIPE", "TPV", "COMISION", "FEE", "PAYPAL", "SUMUP")
                ):
                    score += 0.50
                    criteria.append("amount_with_fee_match")
                    fee_amt = diff

                # 2. Proximidad temporal (+/- 3 días peso 0.30, 4-7 días peso 0.15)
                try:
                    dt_entry_str = str(entry.operation_date)[:10]
                    dt_inv_str = str(inv.issue_date)[:10]
                    dt_entry = datetime.strptime(dt_entry_str, "%Y-%m-%d")
                    dt_inv = datetime.strptime(dt_inv_str, "%Y-%m-%d")
                    diff_days = abs((dt_entry - dt_inv).days)
                    if diff_days <= 3:
                        score += 0.30
                        criteria.append("date_proximity")
                    elif diff_days <= 7:
                        score += 0.15
                        criteria.append("date_proximity_week")
                except Exception:
                    pass

                # 3. Coincidencia textual (NIF o Nombre en concepto o número factura): peso 0.20
                import re
                concept_upper = (entry.concept or "").upper()

                def _matches_name(raw_name: Optional[str]) -> bool:
                    if not raw_name:
                        return False
                    raw_upper = raw_name.upper().strip()
                    if raw_upper and raw_upper in concept_upper:
                        return True
                    # Quitar sufijos societarios tipo SL, SA, SLU, etc.
                    clean_name = re.sub(r'\b(S\.?L\.?U?|S\.?A\.?)\b', '', raw_upper).strip()
                    if clean_name and len(clean_name) >= 3 and clean_name in concept_upper:
                        return True
                    # Si alguna palabra significativa (>= 5 letras) del nombre está en el concepto
                    words = [w for w in clean_name.split() if len(w) >= 5]
                    if len(words) >= 2 and all(w in concept_upper for w in words):
                        return True
                    return False

                name_match = _matches_name(inv.recipient_name)
                issuer_name_match = _matches_name(inv.issuer_name)
                nif_match = bool(inv.recipient_nif and inv.recipient_nif.upper() in concept_upper)
                issuer_nif_match = bool(inv.issuer_nif and inv.issuer_nif.upper() in concept_upper)

                number_match = False
                if inv.series and inv.number is not None:
                    series_num = f"{inv.series}-{inv.number}".upper()
                    series_num_padded = f"{inv.series}-{inv.number:04d}".upper()
                    series_num_simple = f"{inv.series}{inv.number}".upper()
                    if (
                        series_num in concept_upper
                        or series_num_padded in concept_upper
                        or series_num_simple in concept_upper
                    ):
                        number_match = True
                if not number_match and inv.number is not None:
                    num_str = str(inv.number)
                    if f" {num_str} " in f" {concept_upper} " or f"-{num_str}" in concept_upper or f"#{num_str}" in concept_upper:
                        number_match = True

                if name_match or nif_match or issuer_name_match or issuer_nif_match or number_match:
                    score += 0.20
                    criteria.append("concept_or_counterpart_match")

                final_score = round(min(score, 1.0), 2)
                if final_score >= min_score and entry.id is not None and inv.id is not None:
                    suggestions.append(ReconciliationSuggestionDTO(
                        entry_id=entry.id,
                        invoice_id=inv.id,
                        score=final_score,
                        matching_criteria=criteria,
                        suggested_entry_debit_account=debit_acc,
                        suggested_entry_credit_account=credit_acc,
                        fee_amount=fee_amt
                    ))

        # Ordenar por mayor score descendente
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions

    def get_suggestions(
        self,
        tenant_id: str = "default",
        min_score: float = 0.70
    ) -> List[ReconciliationSuggestionDTO]:
        """Obtiene apuntes sin conciliar y facturas abiertas del tenant y calcula las sugerencias."""
        unlinked_entries: List[BankMovementDTO] = []
        open_invoices: List[InvoiceDTO] = []

        def _safe_decrypt(val) -> str:
            if val is None:
                return ""
            val_str = str(val)
            try:
                from app.utils.encryption import encryptor
                dec = encryptor.decrypt(val_str)
                return dec if dec is not None else val_str
            except Exception:
                return val_str

        def _safe_float(val) -> float:
            if val is None:
                return 0.0
            dec = _safe_decrypt(val)
            try:
                return float(dec)
            except Exception:
                return 0.0

        with get_readonly_connection(tenant_id) as conn:
            cursor = conn.cursor()

            # 1. Movimientos bancarios no conciliados
            try:
                cursor.execute(
                    """
                    SELECT id, account_iban, operation_date, value_date, amount, balance_after, concept, reconciliation_status
                    FROM bank_movements
                    WHERE (tenant_id = ? OR tenant_id IS NULL)
                      AND (reconciliation_status = 'UNRECONCILED' OR reconciliation_status IS NULL)
                    ORDER BY operation_date DESC
                    """,
                    (tenant_id,)
                )
                rows = cursor.fetchall()
                for row in rows:
                    try:
                        amt_flt = _safe_float(row[4])
                        bal_flt = _safe_float(row[5])
                        unlinked_entries.append(BankMovementDTO(
                            id=row[0],
                            account_iban=_safe_decrypt(row[1]),
                            operation_date=_safe_decrypt(row[2]),
                            value_date=_safe_decrypt(row[3]),
                            amount=Decimal(str(amt_flt)).quantize(Decimal("0.01")),
                            balance_after=Decimal(str(bal_flt)).quantize(Decimal("0.01")),
                            concept=_safe_decrypt(row[6]),
                            reconciliation_status=row[7] or "UNRECONCILED"
                        ))
                    except Exception:
                        continue
            except Exception:
                pass

            # 2. Facturas pendientes de cobro o pago
            try:
                cursor.execute(
                    """
                    SELECT id, invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                           base_imponible, iva_amount, total_amount, status
                    FROM invoices
                    WHERE status NOT IN ('PAID', 'pagada', 'CANCELLED', 'anulada')
                    """
                )
                rows = cursor.fetchall()
                for row in rows:
                    try:
                        inv_id = row[0]
                        inv_code = _safe_decrypt(row[1])
                        # Descomponer series y number si es posible
                        series = "F"
                        number = inv_id
                        if "-" in inv_code:
                            parts = inv_code.split("-", 1)
                            series = parts[0]
                            try:
                                number = int(parts[1])
                            except ValueError:
                                pass

                        base_amt = _safe_float(row[7])
                        tax_amt = _safe_float(row[8])
                        tot_amt = _safe_float(row[9])

                        open_invoices.append(InvoiceDTO(
                            id=inv_id,
                            series=series,
                            number=number,
                            invoice_type=InvoiceType.F1,
                            issue_date=_safe_decrypt(row[2]) or datetime.now().strftime("%Y-%m-%d"),
                            issuer_name=_safe_decrypt(row[3]),
                            issuer_nif=_safe_decrypt(row[4]),
                            recipient_name=_safe_decrypt(row[5]),
                            recipient_nif=_safe_decrypt(row[6]),
                            base_amount=base_amt,
                            tax_amount=tax_amt,
                            total_amount=tot_amt,
                            status=InvoiceStatus.ISSUED
                        ))
                    except Exception:
                        continue
            except Exception:
                pass

        return self.suggest_matches(unlinked_entries, open_invoices, min_score=min_score)

    def apply_reconciliation(
        self,
        command: Optional[ApplyReconciliationCommand] = None,
        entry_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        tenant_id: str = "default"
    ) -> ReconciliationResultDTO:
        """
        Consolida la conciliación tras aprobación explícita humana en la interfaz.
        Genera el asiento contable obligatorio en el Libro Diario PGC y actualiza estados de forma atómica.
        Acepta tanto un ApplyReconciliationCommand como parámetros individuales (entry_id, invoice_id).
        """
        if command is None:
            if entry_id is None or invoice_id is None:
                raise ValueError("Se requiere ApplyReconciliationCommand o (entry_id, invoice_id)")
            command = ApplyReconciliationCommand(
                entry_id=entry_id,
                invoice_id=invoice_id,
                tenant_id=tenant_id
            )

        tenant_id = command.tenant_id
        entry_id = command.entry_id
        invoice_id = command.invoice_id

        # 1. Cargar apunte y factura dentro de transacción
        with write_transaction(tenant_id) as conn:
            cursor = conn.cursor()

            # Verificar si ya está conciliado
            cursor.execute(
                """
                SELECT id, operation_date, amount, concept, reconciliation_status
                FROM bank_movements
                WHERE id = ?
                """,
                (entry_id,)
            )
            entry_row = cursor.fetchone()
            if not entry_row:
                raise ValueError(f"Movimiento bancario con ID {entry_id} no encontrado")

            if entry_row[4] == "RECONCILED":
                raise BankReconciliationConflictError(
                    f"El movimiento bancario {entry_id} ya se encuentra conciliado previamente."
                )

            op_date_str = str(entry_row[1])[:10]
            entry_amt = Decimal(str(entry_row[2])).quantize(Decimal("0.01"))
            concept = entry_row[3] or "Conciliación bancaria"

            # Verificar factura
            cursor.execute(
                """
                SELECT id, invoice_id, date, total_amount, status
                FROM invoices
                WHERE id = ? OR invoice_id = ?
                """,
                (invoice_id, str(invoice_id))
            )
            inv_row = cursor.fetchone()
            if not inv_row:
                raise ValueError(f"Factura con ID {invoice_id} no encontrada")

            real_invoice_id = inv_row[0]
            invoice_code = inv_row[1] or str(real_invoice_id)
            inv_total = Decimal(str(inv_row[3])).quantize(Decimal("0.01"))

            # Determinar cuentas y comisiones
            fee = Decimal(str(command.fee_amount or "0.00")).quantize(Decimal("0.01"))
            debit_account = command.debit_account or ("572" if entry_amt >= 0 else "400")
            credit_account = command.credit_account or ("430" if entry_amt >= 0 else "572")

            # 2. Generar Asiento Contable PGC
            entry_date = datetime.strptime(op_date_str, "%Y-%m-%d").date()
            fiscal_year = entry_date.year

            lines: List[JournalLineDTO] = []
            if entry_amt >= Decimal("0.00"):
                # Cobro de cliente: Debe 572 (neto) + Debe 669 (comisión) vs Haber 430 (total factura)
                lines.append(JournalLineDTO(
                    account_code=debit_account,
                    concept=f"Cobro factura {invoice_code}",
                    debit=entry_amt,
                    credit=Decimal("0.00")
                ))
                if fee > Decimal("0.00"):
                    lines.append(JournalLineDTO(
                        account_code="669",
                        concept=f"Comisión bancaria factura {invoice_code}",
                        debit=fee,
                        credit=Decimal("0.00")
                    ))
                lines.append(JournalLineDTO(
                    account_code=credit_account,
                    concept=f"Cancelación crédito cliente {invoice_code}",
                    debit=Decimal("0.00"),
                    credit=(entry_amt + fee).quantize(Decimal("0.01"))
                ))
            else:
                # Pago a proveedor: Debe 400 (total factura) + Debe 669 (comisión) vs Haber 572 (total pagado)
                paid_total = abs(entry_amt)
                inv_paid = (paid_total - fee).quantize(Decimal("0.01"))
                lines.append(JournalLineDTO(
                    account_code=debit_account,
                    concept=f"Cancelación deuda proveedor {invoice_code}",
                    debit=inv_paid,
                    credit=Decimal("0.00")
                ))
                if fee > Decimal("0.00"):
                    lines.append(JournalLineDTO(
                        account_code="669",
                        concept=f"Comisión bancaria pago {invoice_code}",
                        debit=fee,
                        credit=Decimal("0.00")
                    ))
                lines.append(JournalLineDTO(
                    account_code=credit_account,
                    concept=f"Pago bancario factura {invoice_code}",
                    debit=Decimal("0.00"),
                    credit=paid_total
                ))

            journal_cmd = RecordJournalEntryCommand(
                tenant_id=tenant_id,
                entry_date=entry_date,
                fiscal_year=fiscal_year,
                concept=f"Conciliación bancaria {invoice_code} - {concept}",
                document_ref=invoice_code,
                lines=lines
            )
            journal_view = self.accounting_service.record_entry(journal_cmd)

            # 3. Actualizar apunte bancario
            cursor.execute(
                """
                UPDATE bank_movements 
                SET reconciled_invoice_id = ?,
                    reconciliation_status = 'RECONCILED',
                    journal_entry_id = ?
                WHERE id = ?
                """,
                (real_invoice_id, journal_view.id, entry_id)
            )

            # 4. Actualizar factura a PAID
            cursor.execute(
                """
                UPDATE invoices 
                SET status = 'PAID'
                WHERE id = ? OR invoice_id = ?
                """,
                (real_invoice_id, str(invoice_id))
            )

        return ReconciliationResultDTO(
            entry_id=entry_id,
            invoice_id=real_invoice_id,
            journal_entry_id=journal_view.id,
            status="RECONCILED",
            total_reconciled=entry_amt,
            fee_accounted=fee,
            message=f"Conciliación realizada y asentada con éxito en el Libro Diario (Asiento Nº {journal_view.entry_number})."
        )


    apply_reconciliation_command = apply_reconciliation


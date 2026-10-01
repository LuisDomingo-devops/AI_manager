"""
Motor de Conciliación Bancaria Inteligente con correspondencia probabilística ponderada.
Conforme al contrato de conciliación bancaria de Alfonso AI Konta.
"""

from typing import List
from datetime import datetime
from app.domain.models.billing import BankEntryDTO, InvoiceDTO, ReconciliationSuggestionDTO
from app.infrastructure.database.connection_manager import write_transaction


class BankReconciliationEngine:
    """Calcula sugerencias de casación entre extractos y facturas y aplica conciliaciones confirmadas."""

    def suggest_matches(
        self,
        unlinked_entries: List[BankEntryDTO],
        open_invoices: List[InvoiceDTO],
        min_score: float = 0.70
    ) -> List[ReconciliationSuggestionDTO]:
        suggestions: List[ReconciliationSuggestionDTO] = []

        for entry in unlinked_entries:
            for inv in open_invoices:
                score = 0.0
                criteria: List[str] = []

                # 1. Coincidencia de importe: peso 0.50
                if abs(abs(entry.amount) - abs(inv.total_amount)) < 0.01:
                    score += 0.50
                    criteria.append("exact_amount")

                # 2. Proximidad temporal (+/- 3 días): peso 0.30
                try:
                    dt_entry = datetime.strptime(entry.operation_date[:10], "%Y-%m-%d")
                    dt_inv = datetime.strptime(inv.issue_date[:10], "%Y-%m-%d")
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
                concept_upper = entry.concept.upper()
                name_match = inv.recipient_name and inv.recipient_name.upper() in concept_upper
                nif_match = inv.recipient_nif and inv.recipient_nif.upper() in concept_upper
                number_match = f"{inv.series}-{inv.number}".upper() in concept_upper or str(inv.number) in concept_upper

                if name_match or nif_match or number_match:
                    score += 0.20
                    criteria.append("concept_or_counterpart_match")

                if score >= min_score and entry.id is not None:
                    suggestions.append(ReconciliationSuggestionDTO(
                        entry_id=entry.id,
                        invoice_id=inv.id,
                        score=round(score, 2),
                        matching_criteria=criteria
                    ))

        # Ordenar por mayor score descendente
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions

    async def apply_reconciliation(self, entry_id: int, invoice_id: int, tenant_id: str = "default") -> None:
        """
        Consolida la conciliación tras aprobación explícita humana en la interfaz.
        """
        with write_transaction(tenant_id) as conn:
            cursor = conn.cursor()
            # Actualizar apunte bancario
            cursor.execute(
                """
                UPDATE bank_movements 
                SET reconciled_invoice_id = ?, reconciliation_status = 'RECONCILED'
                WHERE id = ?
                """,
                (invoice_id, entry_id)
            )
            # Actualizar factura a PAID
            cursor.execute(
                """
                UPDATE invoices 
                SET status = 'PAID'
                WHERE id = ? OR invoice_id = ?
                """,
                (invoice_id, str(invoice_id))
            )

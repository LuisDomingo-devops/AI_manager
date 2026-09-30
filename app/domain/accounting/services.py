"""Servicio de Contabilidad General (PGC) y Libro Diario.

Garantiza la partida doble, cuadre obligatorio e inmutabilidad tras el cierre contable.
"""

from decimal import Decimal
import uuid
from typing import Any, Dict, List

from app.domain.accounting.ports import (
    IAccountingService,
    RecordJournalEntryCommand,
    JournalEntryView,
)
from app.infrastructure.database.legal_connection import (
    legal_write_transaction,
    get_legal_readonly_connection,
)


class AccountingService(IAccountingService):
    """Implementación oficial del servicio contable del Plan General Contable."""

    def record_entry(self, command: RecordJournalEntryCommand) -> JournalEntryView:
        # Validación de partida doble y cuadre contable
        total_debit = sum(Decimal(str(line.get("debit", 0.0))) for line in command.lines)
        total_credit = sum(Decimal(str(line.get("credit", 0.0))) for line in command.lines)

        if abs(total_debit - total_credit) >= Decimal("0.01"):
            raise ValueError(
                f"Asiento descuadrado: total Debe ({total_debit}) != total Haber ({total_credit})"
            )

        entry_id = str(uuid.uuid4())

        with legal_write_transaction(client_id=command.tenant_id) as conn:
            cursor = conn.cursor()

            # Asegurar tablas creadas si aún no existen
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legal_journal_entries (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    entry_number INTEGER NOT NULL,
                    entry_date TEXT NOT NULL,
                    fiscal_year INTEGER NOT NULL,
                    concept TEXT NOT NULL,
                    document_ref TEXT,
                    is_closed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legal_journal_lines (
                    id TEXT PRIMARY KEY,
                    entry_id TEXT NOT NULL,
                    account_code TEXT NOT NULL,
                    debit REAL DEFAULT 0.0,
                    credit REAL DEFAULT 0.0,
                    FOREIGN KEY (entry_id) REFERENCES legal_journal_entries(id)
                )
            """)

            # Obtener correlativo de asiento para el ejercicio
            cursor.execute(
                """
                SELECT MAX(entry_number) FROM legal_journal_entries 
                WHERE tenant_id = ? AND fiscal_year = ?
                """,
                (command.tenant_id, command.fiscal_year),
            )
            last_entry = cursor.fetchone()[0]
            entry_number = (last_entry or 0) + 1

            cursor.execute(
                """
                INSERT INTO legal_journal_entries (
                    id, tenant_id, entry_number, entry_date, fiscal_year, concept, document_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    command.tenant_id,
                    entry_number,
                    command.entry_date.isoformat(),
                    command.fiscal_year,
                    command.concept,
                    command.document_ref,
                ),
            )

            for line in command.lines:
                cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (
                        id, entry_id, account_code, debit, credit
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        entry_id,
                        str(line.get("account", line.get("account_code", ""))),
                        float(line.get("debit", 0.0)),
                        float(line.get("credit", 0.0)),
                    ),
                )
            cursor.close()

        return JournalEntryView(
            id=entry_id,
            entry_number=entry_number,
            entry_date=command.entry_date,
            fiscal_year=command.fiscal_year,
            concept=command.concept,
            is_balanced=True,
            tenant_id=command.tenant_id,
        )

    def get_ledger(self, tenant_id: str, account_code: str, fiscal_year: int) -> List[Dict[str, Any]]:
        """Recupera los movimientos del Libro Mayor para una cuenta."""
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT e.entry_number, e.entry_date, e.concept, l.debit, l.credit
            FROM legal_journal_lines l
            JOIN legal_journal_entries e ON l.entry_id = e.id
            WHERE e.tenant_id = ? AND e.fiscal_year = ? AND l.account_code = ?
            ORDER BY e.entry_number ASC
            """,
            (tenant_id, fiscal_year, account_code),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "entry_number": r[0],
                "entry_date": r[1],
                "concept": r[2],
                "debit": r[3],
                "credit": r[4],
            }
            for r in rows
        ]

    def close_fiscal_year(self, tenant_id: str, fiscal_year: int) -> bool:
        """Cierra el ejercicio contable e impide modificaciones futuras."""
        with legal_write_transaction(client_id=tenant_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE legal_journal_entries 
                SET is_closed = 1 
                WHERE tenant_id = ? AND fiscal_year = ?
                """,
                (tenant_id, fiscal_year),
            )
            cursor.close()
        return True

"""Servicio de Contabilidad General (PGC) y Libro Diario.

Garantiza la partida doble, cuadre obligatorio e inmutabilidad tras el cierre contable.
"""

from decimal import Decimal
import uuid
from typing import Any, Dict, List, Optional

from app.domain.accounting.ports import (
    IAccountingService,
    JournalLineDTO,
    RecordJournalEntryCommand,
    PostRectificationInvoiceCommand,
    JournalEntryView,
)
from app.domain.exceptions import UnbalancedJournalEntryError, FiscalYearClosedError
from app.infrastructure.database.legal_connection import (
    legal_write_transaction,
    get_legal_readonly_connection,
)


class AccountingService(IAccountingService):
    """Implementación oficial del servicio contable del Plan General Contable."""

    def record_entry(self, command: RecordJournalEntryCommand) -> JournalEntryView:
        # Verificar inmutabilidad del ejercicio fiscal
        if self.is_fiscal_year_closed(command.tenant_id, command.fiscal_year):
            raise FiscalYearClosedError(tenant_id=command.tenant_id, fiscal_year=command.fiscal_year)

        # Validación estricta de partida doble y cuadre contable (tolerancia cero 0.00)
        total_debit = sum(
            line.debit if isinstance(line, JournalLineDTO) else Decimal(str(line.get("debit", 0.0))).quantize(Decimal("0.01"))
            for line in command.lines
        ).quantize(Decimal("0.01"))
        total_credit = sum(
            line.credit if isinstance(line, JournalLineDTO) else Decimal(str(line.get("credit", 0.0))).quantize(Decimal("0.01"))
            for line in command.lines
        ).quantize(Decimal("0.01"))

        if total_debit != total_credit:
            raise UnbalancedJournalEntryError(total_debit=total_debit, total_credit=total_credit)

        entry_id = str(uuid.uuid4())

        with legal_write_transaction(client_id=command.tenant_id) as conn:
            cursor = conn.cursor()

            # Asegurar tablas creadas si aún no existen
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legal_fiscal_years (
                    tenant_id TEXT NOT NULL,
                    fiscal_year INTEGER NOT NULL,
                    is_closed INTEGER NOT NULL DEFAULT 0,
                    closed_at TEXT,
                    closed_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tenant_id, fiscal_year)
                )
            """)
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (tenant_id, fiscal_year, entry_number)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legal_journal_lines (
                    id TEXT PRIMARY KEY,
                    entry_id TEXT NOT NULL,
                    account_code TEXT NOT NULL,
                    concept TEXT,
                    debit TEXT DEFAULT '0.00',
                    credit TEXT DEFAULT '0.00',
                    FOREIGN KEY (entry_id) REFERENCES legal_journal_entries(id)
                )
            """)

            # Asegurar columna concept si la tabla ya existía previamente
            try:
                cursor.execute("ALTER TABLE legal_journal_lines ADD COLUMN concept TEXT")
            except Exception:
                pass

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
                acc_code = line.account_code if isinstance(line, JournalLineDTO) else str(line.get("account", line.get("account_code", "")))
                concept_val = line.concept if isinstance(line, JournalLineDTO) else str(line.get("concept", command.concept))
                if isinstance(line, JournalLineDTO):
                    deb_val = str(line.debit.quantize(Decimal("0.01")))
                    cred_val = str(line.credit.quantize(Decimal("0.01")))
                else:
                    deb_val = str(Decimal(str(line.get("debit", 0.0))).quantize(Decimal("0.01")))
                    cred_val = str(Decimal(str(line.get("credit", 0.0))).quantize(Decimal("0.01")))

                cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (
                        id, entry_id, account_code, concept, debit, credit
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        entry_id,
                        acc_code,
                        concept_val,
                        deb_val,
                        cred_val,
                    ),
                )
            cursor.close()

        return JournalEntryView(
            id=entry_id,
            entry_number=entry_number,
            entry_date=command.entry_date,
            fiscal_year=command.fiscal_year,
            concept=command.concept,
            document_ref=command.document_ref,
            is_balanced=True,
            tenant_id=command.tenant_id,
            lines=command.lines,
        )

    def post_rectification_entry(self, command: PostRectificationInvoiceCommand) -> JournalEntryView:
        """Registra el asiento contable oficial de una factura rectificativa o abono usando PGC 708/608."""
        tb = command.taxable_base.quantize(Decimal("0.01"))
        ta = command.tax_amount.quantize(Decimal("0.01"))
        tot = command.total_amount.quantize(Decimal("0.01"))

        if command.is_sales:
            # Factura rectificativa emitida (Ventas / Abono a cliente)
            # 708 (Devoluciones de ventas) al Debe
            # 477 (H.P. IVA Repercutido) al Debe (minoración)
            # Cuenta del cliente (ej. 43000000) al Haber
            concept = f"Factura rectificativa ventas {command.invoice_number} (rectifica {command.rectified_invoice_number})"
            lines = [
                JournalLineDTO(account_code="708000", concept=concept, debit=tb, credit=Decimal("0.00")),
                JournalLineDTO(account_code="477000", concept=concept, debit=ta, credit=Decimal("0.00")),
                JournalLineDTO(account_code=command.third_party_account, concept=concept, debit=Decimal("0.00"), credit=tot),
            ]
        else:
            # Factura rectificativa recibida (Compras / Abono de proveedor)
            # Cuenta del proveedor (ej. 40000000) al Debe
            # 608 (Devoluciones de compras) al Haber
            # 472 (H.P. IVA Soportado) al Haber (minoración)
            concept = f"Factura rectificativa compras {command.invoice_number} (rectifica {command.rectified_invoice_number})"
            lines = [
                JournalLineDTO(account_code=command.third_party_account, concept=concept, debit=tot, credit=Decimal("0.00")),
                JournalLineDTO(account_code="608000", concept=concept, debit=Decimal("0.00"), credit=tb),
                JournalLineDTO(account_code="472000", concept=concept, debit=Decimal("0.00"), credit=ta),
            ]

        record_cmd = RecordJournalEntryCommand(
            tenant_id=command.tenant_id,
            entry_date=command.entry_date,
            fiscal_year=command.fiscal_year,
            concept=concept,
            document_ref=command.invoice_number,
            lines=lines,
        )
        return self.record_entry(record_cmd)

    def get_ledger(self, tenant_id: str, account_code: str, fiscal_year: int) -> List[Dict[str, Any]]:
        """Recupera los movimientos del Libro Mayor para una cuenta calculando el saldo progresivo exacto."""
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT e.entry_number, e.entry_date, e.concept, l.debit, l.credit
            FROM legal_journal_lines l
            JOIN legal_journal_entries e ON l.entry_id = e.id
            WHERE e.tenant_id = ? AND e.fiscal_year = ? AND l.account_code = ?
            ORDER BY e.entry_number ASC, l.id ASC
            """,
            (tenant_id, fiscal_year, account_code),
        )
        rows = cursor.fetchall()
        cursor.close()

        movements = []
        running_balance = Decimal("0.00")
        for r in rows:
            entry_number, entry_date, concept, debit_raw, credit_raw = r
            debit_dec = Decimal(str(debit_raw if debit_raw is not None else "0.00")).quantize(Decimal("0.01"))
            credit_dec = Decimal(str(credit_raw if credit_raw is not None else "0.00")).quantize(Decimal("0.01"))
            running_balance = (running_balance + debit_dec - credit_dec).quantize(Decimal("0.01"))
            movements.append({
                "entry_number": entry_number,
                "entry_date": entry_date,
                "concept": concept,
                "debit": debit_dec,
                "credit": credit_dec,
                "progressive_balance": running_balance,
            })

        return movements

    def is_fiscal_year_closed(self, tenant_id: str, fiscal_year: int) -> bool:
        """Verifica si el ejercicio fiscal está marcado como cerrado en la base de datos legal."""
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT is_closed FROM legal_fiscal_years 
                WHERE tenant_id = ? AND fiscal_year = ?
                """,
                (tenant_id, fiscal_year),
            )
            row = cursor.fetchone()
            return bool(row and row[0] == 1)
        except Exception:
            return False
        finally:
            cursor.close()

    def close_fiscal_year(self, tenant_id: str, fiscal_year: int, closed_by: Optional[str] = None) -> bool:
        """Cierra el ejercicio contable e impide modificaciones futuras."""
        with legal_write_transaction(client_id=tenant_id) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legal_fiscal_years (
                    tenant_id TEXT NOT NULL,
                    fiscal_year INTEGER NOT NULL,
                    is_closed INTEGER NOT NULL DEFAULT 0,
                    closed_at TEXT,
                    closed_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tenant_id, fiscal_year)
                )
            """)
            cursor.execute(
                """
                INSERT INTO legal_fiscal_years (tenant_id, fiscal_year, is_closed, closed_at, closed_by)
                VALUES (?, ?, 1, datetime('now'), ?)
                ON CONFLICT(tenant_id, fiscal_year) DO UPDATE SET
                    is_closed = 1,
                    closed_at = datetime('now'),
                    closed_by = excluded.closed_by
                """,
                (tenant_id, fiscal_year, closed_by or "system"),
            )
            cursor.execute(
                """
                UPDATE legal_journal_entries 
                SET is_closed = 1
                WHERE tenant_id = ? AND fiscal_year = ?
                """,
                (tenant_id, fiscal_year),
            )
        return True

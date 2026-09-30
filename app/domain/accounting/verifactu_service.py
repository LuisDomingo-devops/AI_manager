"""Servicio de Facturación Legal y Encadenamiento VeriFactu (RD 1007/2023).

Implementa la emisión atómica e inmutable de facturas con cálculo SHA-256 encadenado.
"""

from decimal import Decimal
import hashlib
import uuid
from typing import Optional

from app.domain.accounting.ports import IVeriFactuService, IssueInvoiceCommand, InvoiceView
from app.infrastructure.database.legal_connection import (
    legal_write_transaction,
    get_legal_readonly_connection,
)


class VeriFactuService(IVeriFactuService):
    """Servicio exclusivo para la emisión y verificación de facturas oficiales."""

    def issue_legal_invoice(self, command: IssueInvoiceCommand) -> InvoiceView:
        # Validación de dominio: base imponible positiva en facturas ordinarias
        if not command.is_rectified and command.taxable_base <= Decimal("0.00"):
            raise ValueError("Base imponible debe ser positiva para facturas ordinarias")

        tax_amount = round(command.taxable_base * (command.tax_rate / Decimal("100.0")), 2)
        total_amount = round(command.taxable_base + tax_amount, 2)
        invoice_id = str(uuid.uuid4())

        with legal_write_transaction(client_id=command.tenant_id) as conn:
            cursor = conn.cursor()

            # Asegurar tabla creada si aún no se inicializó
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legal_invoices (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    invoice_number TEXT NOT NULL UNIQUE,
                    issue_date TEXT NOT NULL,
                    recipient_tax_id TEXT NOT NULL,
                    recipient_name TEXT NOT NULL,
                    taxable_base REAL NOT NULL,
                    tax_rate REAL NOT NULL,
                    tax_amount REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    verifactu_hash TEXT NOT NULL,
                    previous_hash TEXT,
                    qr_payload TEXT NOT NULL,
                    is_rectified INTEGER DEFAULT 0,
                    rectified_invoice_number TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Obtener última factura de la serie para encadenamiento y correlatividad
            cursor.execute(
                """
                SELECT invoice_number, verifactu_hash 
                FROM legal_invoices 
                WHERE tenant_id = ? AND invoice_number LIKE ? 
                ORDER BY created_at DESC, invoice_number DESC 
                LIMIT 1
                """,
                (command.tenant_id, f"{command.series}-%"),
            )
            last_record = cursor.fetchone()

            if last_record:
                last_number_str = last_record[0].split("-")[1]
                next_seq = int(last_number_str) + 1
                previous_hash = last_record[1]
            else:
                next_seq = 1
                previous_hash = ""

            invoice_number = f"{command.series}-{next_seq:04d}"

            # Cálculo de la huella criptográfica encadenada (SHA-256)
            hash_input = (
                f"{command.tenant_id}|{invoice_number}|{command.issue_date.isoformat()}|"
                f"{float(command.taxable_base):.2f}|{float(tax_amount):.2f}|{float(total_amount):.2f}|{previous_hash}"
            )
            verifactu_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            # Código QR oficial tributario
            qr_payload = (
                f"https://sede.agenciatributaria.gob.es/qr?"
                f"nif={command.recipient_tax_id}&num={invoice_number}&total={float(total_amount):.2f}&hash={verifactu_hash[:16]}"
            )

            cursor.execute(
                """
                INSERT INTO legal_invoices (
                    id, tenant_id, invoice_number, issue_date, recipient_tax_id, recipient_name,
                    taxable_base, tax_rate, tax_amount, total_amount, status, verifactu_hash,
                    previous_hash, qr_payload, is_rectified, rectified_invoice_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    command.tenant_id,
                    invoice_number,
                    command.issue_date.isoformat(),
                    command.recipient_tax_id,
                    command.recipient_name,
                    float(command.taxable_base),
                    float(command.tax_rate),
                    float(tax_amount),
                    float(total_amount),
                    "ISSUED",
                    verifactu_hash,
                    previous_hash,
                    qr_payload,
                    1 if command.is_rectified else 0,
                    command.rectified_invoice_number,
                ),
            )
            cursor.close()

        return InvoiceView(
            id=invoice_id,
            invoice_number=invoice_number,
            issue_date=command.issue_date,
            taxable_base=command.taxable_base,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status="ISSUED",
            verifactu_hash=verifactu_hash,
            qr_payload=qr_payload,
            tenant_id=command.tenant_id,
        )

    def verify_chain_integrity(self, tenant_id: str, fiscal_year: int) -> bool:
        """Verifica la integridad criptográfica de la cadena de facturación."""
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT invoice_number, issue_date, taxable_base, tax_amount, total_amount, 
                   previous_hash, verifactu_hash 
            FROM legal_invoices 
            WHERE tenant_id = ? AND issue_date LIKE ? 
            ORDER BY invoice_number ASC
            """,
            (tenant_id, f"{fiscal_year}-%"),
        )
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return True

        expected_previous_hash = ""
        for row in rows:
            inv_num, issue_date, tax_base, tax_amt, total_amt, prev_h, stored_hash = row

            if prev_h != expected_previous_hash:
                return False

            hash_input = (
                f"{tenant_id}|{inv_num}|{issue_date}|"
                f"{float(tax_base):.2f}|{float(tax_amt):.2f}|{float(total_amt):.2f}|{prev_h}"
            )
            calculated_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            if calculated_hash != stored_hash:
                return False

            expected_previous_hash = stored_hash

        return True

    def get_invoice_by_number(self, tenant_id: str, invoice_number: str) -> Optional[InvoiceView]:
        """Obtiene una factura por su número correlativo."""
        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, invoice_number, issue_date, taxable_base, tax_amount, total_amount, 
                   status, verifactu_hash, qr_payload, tenant_id
            FROM legal_invoices 
            WHERE tenant_id = ? AND invoice_number = ?
            """,
            (tenant_id, invoice_number),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        from datetime import date
        return InvoiceView(
            id=row[0],
            invoice_number=row[1],
            issue_date=date.fromisoformat(row[2]),
            taxable_base=Decimal(str(row[3])),
            tax_amount=Decimal(str(row[4])),
            total_amount=Decimal(str(row[5])),
            status=row[6],
            verifactu_hash=row[7],
            qr_payload=row[8],
            tenant_id=row[9],
        )

"""
Servicio de Facturación Canónico de Alfonso AI Konta.
Garantiza transaccionalidad atómica ACID anti-huecos, validación XSD obligatoria y soporte de rectificativas.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from app.infrastructure.database.connection_manager import _get_connection, write_transaction
from app.domain.models.billing import (
    InvoiceCreateDTO,
    InvoiceDTO,
    InvoiceType,
    InvoiceStatus,
    AuditHashDTO,
    RectificationMethod,
)
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.verifactu_validator import VerifactuValidator
from app.domain.exceptions import XSDValidationError, InvoiceValidationError, InvoiceNumberGapError


class BillingService:
    """Servicio de emisión atómica y gestión de facturas bajo normativa Veri*Factu."""

    def __init__(self):
        self.validator = VerifactuValidator()

    def _ensure_tables(self, conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_sequences (
                year INTEGER NOT NULL,
                prefix TEXT NOT NULL,
                last_value INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (year, prefix)
            );
        """)

        cols = [r[1] for r in conn.execute("PRAGMA table_info(invoices)").fetchall()]
        if cols:
            new_cols = [
                ("series", "TEXT"),
                ("number", "INTEGER"),
                ("invoice_type", "TEXT"),
                ("issue_date", "TEXT"),
                ("operation_date", "TEXT"),
                ("base_amount", "REAL"),
                ("tax_amount", "REAL"),
                ("retention_amount", "REAL DEFAULT 0.0"),
                ("surcharge_amount", "REAL DEFAULT 0.0"),
                ("recipient_nif", "TEXT"),
                ("recipient_name", "TEXT"),
                ("rectified_series", "TEXT"),
                ("rectified_number", "INTEGER"),
                ("rectification_method", "TEXT"),
                ("rectification_reason", "TEXT")
            ]
            for col_name, col_type in new_cols:
                if col_name not in cols:
                    try:
                        conn.execute(f"ALTER TABLE invoices ADD COLUMN {col_name} {col_type};")
                    except Exception:
                        pass
        else:

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT NOT NULL,
                    series TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    invoice_type TEXT NOT NULL,
                    issue_date TEXT NOT NULL,
                    operation_date TEXT,
                    issuer_nif TEXT NOT NULL,
                    issuer_name TEXT NOT NULL,
                    receiver_nif TEXT,
                    receiver_name TEXT,
                    base_imponible REAL NOT NULL,
                    iva_amount REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    rectified_series TEXT,
                    rectified_number INTEGER,
                    rectification_method TEXT,
                    rectification_reason TEXT,
                    status TEXT NOT NULL,
                    quarter INTEGER DEFAULT 1,
                    year INTEGER DEFAULT 2026,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(series, number)
                );
            """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                previous_hash TEXT,
                canonical_payload TEXT NOT NULL,
                current_hash TEXT NOT NULL,
                generation_timestamp TEXT NOT NULL,
                qr_url TEXT NOT NULL,
                xml_content TEXT,
                aeat_submission_status TEXT DEFAULT 'LOCAL_ONLY',
                aeat_csv TEXT
            );
        """)


    def _generate_verifactu_xml(
        self,
        invoice_in: InvoiceCreateDTO,
        invoice_number: str,
        issue_date_fmt: str,
        prev_hash: Optional[str]
    ) -> bytes:
        prev_hash_tag = ""
        if prev_hash:
            prev_hash_tag = f"""
                <Encadenamiento>
                  <RegistroAnterior>
                    <Huella>{prev_hash}</Huella>
                  </RegistroAnterior>
                </Encadenamiento>
            """

        rectificadas_tag = ""
        tipo_rect_tag = ""
        if invoice_in.invoice_type.value.startswith("R"):
            tipo_rect_tag = f"<TipoRectificativa>{invoice_in.rectification_method.value if invoice_in.rectification_method else 'S'}</TipoRectificativa>"
            rect_series = invoice_in.rectified_series or invoice_in.series
            rect_num = invoice_in.rectified_number or 1
            rectificadas_tag = f"""
                <FacturasRectificadas>
                  <FacturaRectificada>
                    <NumSerieFacturaEmisor>{rect_series}-{rect_num:04d}</NumSerieFacturaEmisor>
                    <FechaExpedicionFacturaEmisor>{invoice_in.issue_date}</FechaExpedicionFacturaEmisor>
                  </FacturaRectificada>
                </FacturasRectificadas>
            """

        xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<RegFactuSistemaFacturacion xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Cabecera>
    <ObligadoEmision>
      <NombreRazon>{invoice_in.issuer_name}</NombreRazon>
      <NIF>{invoice_in.issuer_nif}</NIF>
    </ObligadoEmision>
  </Cabecera>
  <RegistroFacturacionAlta>
    <IDFactura>
      <NumSerieFacturaEmisor>{invoice_number}</NumSerieFacturaEmisor>
      <FechaExpedicionFacturaEmisor>{issue_date_fmt}</FechaExpedicionFacturaEmisor>
    </IDFactura>
    <NombreRazonEmisor>{invoice_in.issuer_name}</NombreRazonEmisor>
    <Receptor>
      <NombreRazonReceptor>{invoice_in.recipient_name or 'CONSUMIDOR FINAL'}</NombreRazonReceptor>
      <NIFReceptor>{invoice_in.recipient_nif or 'NIF_NO_APLICA'}</NIFReceptor>
    </Receptor>
    <DetalleFactura>
      <TipoFactura>{invoice_in.invoice_type.value}</TipoFactura>
      {tipo_rect_tag}
      {rectificadas_tag}
      <ClaveRegimenEspecialOTrascendencia>01</ClaveRegimenEspecialOTrascendencia>
      <ImporteTotal>{invoice_in.total_amount:.2f}</ImporteTotal>
      <Desglose>
        <DetalleIVA>
          <BaseImponible>{invoice_in.base_amount:.2f}</BaseImponible>
          <CuotaIVA>{invoice_in.tax_amount:.2f}</CuotaIVA>
        </DetalleIVA>
      </Desglose>
    </DetalleFactura>
    <SistemaInformatico>
      <Nombre>Alfonso AI Konta</Nombre>
      <NIFProductor>{invoice_in.issuer_nif}</NIFProductor>
      <NumInstalacion>001</NumInstalacion>
      <Version>1.0.0</Version>
    </SistemaInformatico>
    {prev_hash_tag}
  </RegistroFacturacionAlta>
</RegFactuSistemaFacturacion>"""
        return xml_str.strip().encode("utf-8")

    def emit_invoice_atomic(
        self,
        invoice_in: InvoiceCreateDTO,
        force_valid_xml: bool = False,
        force_invalid_xml: bool = False,
        client_id: Optional[str] = None
    ) -> InvoiceDTO:
        """
        Emite una factura en una transacción atómica única ACID.
        Si la validación XSD o la inserción falla, la transacción realiza rollback
        garantizando que no se generen huecos en la serie numérica.
        """
        # Validación de rectificativas
        if invoice_in.invoice_type.value.startswith("R"):
            if not invoice_in.rectified_series or invoice_in.rectified_number is None:
                raise InvoiceValidationError(
                    "Las facturas rectificativas requieren obligatoriamente serie y número de la factura original rectificada."
                )

        with write_transaction(client_id) as conn:
            self._ensure_tables(conn)

            # 1. Obtener y bloquear correlativo siguiente (MAX(number) + 1)
            row = conn.execute(
                "SELECT COALESCE(MAX(number), 0) AS max_num FROM invoices WHERE series = ?",
                (invoice_in.series,)
            ).fetchone()
            next_num = int(row["max_num"]) + 1
            invoice_num_str = f"{invoice_in.series}-{next_num:04d}"

            # 2. Obtener hash previo
            last_hash_row = conn.execute(
                """
                SELECT h.current_hash 
                FROM audit_hashes h
                JOIN invoices i ON h.invoice_id = i.id
                WHERE i.series = ?
                ORDER BY i.number DESC LIMIT 1
                """,
                (invoice_in.series,)
            ).fetchone()
            prev_hash = last_hash_row["current_hash"] if last_hash_row else None

            # 3. Formatear fechas y calcular huella oficial HAC/1177/2024
            gen_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+01:00")
            parts = invoice_in.issue_date.split("-")
            date_of_issue_ddmmyyyy = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else invoice_in.issue_date

            hash_payload_dict = {
                "issuer_nif": invoice_in.issuer_nif,
                "invoice_number": invoice_num_str,
                "date_of_issue": date_of_issue_ddmmyyyy,
                "tipo_factura": invoice_in.invoice_type.value,
                "iva_amount": f"{invoice_in.tax_amount:.2f}",
                "total_amount": f"{invoice_in.total_amount:.2f}",
                "gen_timestamp": gen_ts
            }
            current_hash = VerifactuService.calculate_invoice_hash(hash_payload_dict, prev_hash)

            # 4. Generar y Validar XML contra verifactu.xsd
            if force_invalid_xml:
                xml_bytes = b"<?xml version='1.0'?><Invalido/>"
            else:
                xml_bytes = self._generate_verifactu_xml(
                    invoice_in, invoice_num_str, date_of_issue_ddmmyyyy, prev_hash
                )

            self.validator.assert_valid_xml(xml_bytes)

            # 5. Generar URL de cotejo QR
            qr_url = f"https://www.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR?nif={invoice_in.issuer_nif}&numserie={invoice_num_str}&fecha={date_of_issue_ddmmyyyy}&importe={invoice_in.total_amount:.2f}"

            # 6. Inserción atómica en base de datos
            invoice_year = int(invoice_in.issue_date[:4]) if len(invoice_in.issue_date) >= 4 else 2026
            cursor = conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, series, number, invoice_type, date, issue_date, operation_date,
                    issuer_nif, issuer_name, receiver_nif, receiver_name,
                    base_imponible, base_amount, iva_rate, iva_amount, tax_amount,
                    retention_amount, surcharge_amount, total_amount, rectified_series,
                    rectified_number, rectification_method, rectification_reason, status,
                    quarter, year, category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_num_str,
                    invoice_in.series,
                    next_num,
                    invoice_in.invoice_type.value,
                    invoice_in.issue_date,
                    invoice_in.issue_date,
                    invoice_in.operation_date,
                    invoice_in.issuer_nif,
                    invoice_in.issuer_name,
                    invoice_in.recipient_nif or "NIF_NO_APLICA",
                    invoice_in.recipient_name or "CONSUMIDOR FINAL",
                    invoice_in.base_amount,
                    invoice_in.base_amount,
                    21.0,
                    invoice_in.tax_amount,
                    invoice_in.tax_amount,
                    invoice_in.retention_amount,
                    invoice_in.surcharge_amount,
                    invoice_in.total_amount,
                    invoice_in.rectified_series,
                    invoice_in.rectified_number,
                    invoice_in.rectification_method.value if invoice_in.rectification_method else None,
                    invoice_in.rectification_reason,
                    InvoiceStatus.ISSUED.value,
                    1,
                    invoice_year,
                    "ingreso"
                )
            )
            invoice_id = cursor.lastrowid


            canonical_payload = (
                f"IDEmisorFactura={invoice_in.issuer_nif}&NumSerieFactura={invoice_num_str}&FechaExpedicionFactura={date_of_issue_ddmmyyyy}"
                f"&TipoRegistroDeclarado={invoice_in.invoice_type.value}&CuotaTotal={invoice_in.tax_amount:.2f}&ImporteTotal={invoice_in.total_amount:.2f}"
                f"&Huella={prev_hash or ''}&FechaHoraHusoGenRegistro={gen_ts}"
            )

            conn.execute(
                """
                INSERT INTO audit_hashes (
                    invoice_id, previous_hash, canonical_payload, current_hash,
                    generation_timestamp, qr_url, xml_content
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    prev_hash,
                    canonical_payload,
                    current_hash,
                    gen_ts,
                    qr_url,
                    xml_bytes.decode("utf-8")
                )
            )

            audit_hash_dto = AuditHashDTO(
                invoice_id=invoice_id,
                previous_hash=prev_hash,
                canonical_payload=canonical_payload,
                current_hash=current_hash,
                generation_timestamp=gen_ts,
                qr_url=qr_url,
                xml_content=xml_bytes.decode("utf-8")
            )

            return InvoiceDTO(
                id=invoice_id,
                series=invoice_in.series,
                number=next_num,
                invoice_type=invoice_in.invoice_type,
                issue_date=invoice_in.issue_date,
                operation_date=invoice_in.operation_date,
                issuer_nif=invoice_in.issuer_nif,
                issuer_name=invoice_in.issuer_name,
                recipient_nif=invoice_in.recipient_nif,
                recipient_name=invoice_in.recipient_name,
                base_amount=invoice_in.base_amount,
                tax_amount=invoice_in.tax_amount,
                retention_amount=invoice_in.retention_amount,
                surcharge_amount=invoice_in.surcharge_amount,
                total_amount=invoice_in.total_amount,
                rectified_series=invoice_in.rectified_series,
                rectified_number=invoice_in.rectified_number,
                rectification_method=invoice_in.rectification_method,
                rectification_reason=invoice_in.rectification_reason,
                status=InvoiceStatus.ISSUED,
                hash_record=audit_hash_dto
            )

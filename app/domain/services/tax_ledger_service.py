"""
tax_ledger_service.py
=====================
Servicio de dominio para la custodia inmutable, auditoría y consulta de declaraciones tributarias.
Garantiza el cumplimiento del plazo legal obligatorio de conservación de 5 años (Ley 58/2003 LGT).
"""
import sqlite3
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.adapters.memory.memory import _get_connection
from app.domain.models.billing import TaxDeclarationAuditDTO
from app.domain.exceptions import TaxRetentionPolicyViolationError, DatabasePersistenceError


class TaxLedgerService:
    """
    Gestiona el archivo inmutable de declaraciones fiscales y su custodia legal por 5 años.
    """

    @staticmethod
    def compute_sha256(content: str) -> str:
        """Calcula el hash criptográfico SHA-256 de una cadena de texto."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def calculate_retention_date(base_date: datetime = None) -> str:
        """
        Calcula la fecha límite legal obligatoria de retención (5 años naturales desde la fecha base).
        Conforme a los arts. 66 a 70 de la Ley General Tributaria.
        """
        now = base_date or datetime.now()
        # Sumar 5 años exactos conservando mes y día (manejando bisiestos)
        try:
            retention_dt = now.replace(year=now.year + 5)
        except ValueError:
            # Caso 29 de febrero
            retention_dt = now.replace(year=now.year + 5, day=28)
        return retention_dt.strftime("%Y-%m-%d %H:%M:%S")

    def save_declaration_filing(
        self,
        model_code: str,
        fiscal_year: int,
        period: str,
        declarant_nif: str,
        declarant_name: str,
        casillas_payload: Dict[str, Any],
        boe_file_content: str,
        tenant_id: str = "default",
        filing_status: str = "CALCULATED",
        aeat_csv: Optional[str] = None
    ) -> TaxDeclarationAuditDTO:
        """
        Guarda o actualiza de forma auditada una declaración en el libro mayor de autoliquidaciones.
        """
        now_dt = datetime.now()
        filing_date = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        retention_until_date = self.calculate_retention_date(now_dt)
        sha256_hash = self.compute_sha256(boe_file_content)
        casillas_json = json.dumps(casillas_payload, ensure_ascii=False)

        query = """
            INSERT INTO tax_declarations_ledger (
                tenant_id, model_code, fiscal_year, period,
                declarant_nif, declarant_name, casillas_json,
                boe_file_content, sha256_hash, filing_status,
                aeat_csv, filing_date, retention_until_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, model_code, fiscal_year, period) DO UPDATE SET
                declarant_name = excluded.declarant_name,
                casillas_json = excluded.casillas_json,
                boe_file_content = excluded.boe_file_content,
                sha256_hash = excluded.sha256_hash,
                filing_status = excluded.filing_status,
                aeat_csv = coalesce(excluded.aeat_csv, tax_declarations_ledger.aeat_csv),
                filing_date = excluded.filing_date,
                retention_until_date = excluded.retention_until_date
        """
        try:
            with _get_connection() as conn:
                cursor = conn.execute(query, (
                    tenant_id, model_code, fiscal_year, period,
                    declarant_nif, declarant_name, casillas_json,
                    boe_file_content, sha256_hash, filing_status,
                    aeat_csv, filing_date, retention_until_date, filing_date
                ))
                record_id = cursor.lastrowid
                conn.commit()

            return TaxDeclarationAuditDTO(
                id=record_id,
                tenant_id=tenant_id,
                model_code=model_code,
                fiscal_year=fiscal_year,
                period=period,
                declarant_nif=declarant_nif,
                declarant_name=declarant_name,
                casillas_payload=casillas_payload,
                boe_file_content=boe_file_content,
                sha256_hash=sha256_hash,
                filing_status=filing_status,
                aeat_csv=aeat_csv,
                filing_date=filing_date,
                retention_until_date=retention_until_date,
                created_at=filing_date
            )
        except Exception as e:
            raise DatabasePersistenceError(
                message=f"Error al custodiar declaración en tax_declarations_ledger: {str(e)}",
                operation="INSERT",
                table="tax_declarations_ledger",
                details={"model": model_code, "year": fiscal_year, "period": period}
            )

    def list_declarations(
        self,
        tenant_id: str = "default",
        model_code: Optional[str] = None,
        fiscal_year: Optional[int] = None
    ) -> List[TaxDeclarationAuditDTO]:
        """Consulta el histórico de declaraciones custodiadas."""
        query = "SELECT * FROM tax_declarations_ledger WHERE tenant_id = ?"
        params: List[Any] = [tenant_id]

        if model_code:
            query += " AND model_code = ?"
            params.append(model_code)
        if fiscal_year:
            query += " AND fiscal_year = ?"
            params.append(fiscal_year)

        query += " ORDER BY fiscal_year DESC, period DESC"

        results = []
        with _get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                try:
                    casillas = json.loads(r["casillas_json"] or "{}")
                except Exception:
                    casillas = {}

                results.append(TaxDeclarationAuditDTO(
                    id=r["id"],
                    tenant_id=r["tenant_id"],
                    model_code=r["model_code"],
                    fiscal_year=r["fiscal_year"],
                    period=r["period"],
                    declarant_nif=r["declarant_nif"],
                    declarant_name=r["declarant_name"] or "",
                    casillas_payload=casillas,
                    boe_file_content=r["boe_file_content"] or "",
                    sha256_hash=r["sha256_hash"] or "",
                    filing_status=r["filing_status"] or "CALCULATED",
                    aeat_csv=r["aeat_csv"],
                    filing_date=r["filing_date"],
                    retention_until_date=r["retention_until_date"],
                    created_at=r["created_at"]
                ))
        return results

    def get_declaration_by_id(self, filing_id: int) -> Optional[TaxDeclarationAuditDTO]:
        """Recupera una declaración específica por su identificador primario."""
        query = "SELECT * FROM tax_declarations_ledger WHERE id = ?"
        with _get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(query, (filing_id,)).fetchone()
            if not row:
                return None

            try:
                casillas = json.loads(row["casillas_json"] or "{}")
            except Exception:
                casillas = {}

            return TaxDeclarationAuditDTO(
                id=row["id"],
                tenant_id=row["tenant_id"],
                model_code=row["model_code"],
                fiscal_year=row["fiscal_year"],
                period=row["period"],
                declarant_nif=row["declarant_nif"],
                declarant_name=row["declarant_name"] or "",
                casillas_payload=casillas,
                boe_file_content=row["boe_file_content"] or "",
                sha256_hash=row["sha256_hash"] or "",
                filing_status=row["filing_status"] or "CALCULATED",
                aeat_csv=row["aeat_csv"],
                filing_date=row["filing_date"],
                retention_until_date=row["retention_until_date"],
                created_at=row["created_at"]
            )

    def assert_can_delete(self, filing_id: int) -> None:
        """
        Verifica si una declaración puede ser purgada legalmente.
        Lanza TaxRetentionPolicyViolationError si está dentro del plazo obligatorio de 5 años.
        """
        decl = self.get_declaration_by_id(filing_id)
        if not decl:
            return

        now = datetime.now()
        try:
            retention_dt = datetime.strptime(decl.retention_until_date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            retention_dt = datetime.strptime(decl.retention_until_date[:10], "%Y-%m-%d")

        if now < retention_dt:
            raise TaxRetentionPolicyViolationError(
                message=(
                    f"No es posible eliminar la declaración {decl.model_code} {decl.fiscal_year}-{decl.period}. "
                    f"Está bajo custodia legal obligatoria de 5 años hasta {decl.retention_until_date} (Ley 58/2003 LGT)."
                ),
                filing_id=str(filing_id),
                details={
                    "model": decl.model_code,
                    "retention_until": decl.retention_until_date,
                    "now": now.strftime("%Y-%m-%d %H:%M:%S")
                }
            )

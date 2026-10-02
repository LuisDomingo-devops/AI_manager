"""
Router REST para Conciliación Bancaria y Asientos Contables PGC (Spec 034).
Conforme a la especificación OpenAPI 3.0 bank_reconciliation_contract.yaml.
"""
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, status
from app.domain.schemas import (
    BankStatementDTO,
    BankMovementDTO,
    BankStatementSourceType,
    ReconciliationSuggestionDTO,
    ApplyReconciliationCommand,
    ReconciliationResultDTO,
)
from app.domain.services.norma43_parser import Norma43Parser
from app.domain.services.bank_csv_parser import BankCsvParser
from app.domain.services.bank_service import BankService
from app.domain.services.bank_reconciliation_engine import BankReconciliationEngine
from app.domain.exceptions import BankStatementDiscrepancyError, BankReconciliationConflictError
from app.infrastructure.database.connection_manager import write_transaction

router = APIRouter(prefix="/bank", tags=["Bank Reconciliation"])


@router.post("/statements/import", response_model=BankStatementDTO)
async def import_bank_statement_endpoint(
    file: UploadFile = File(...),
    source_type: Optional[BankStatementSourceType] = Form(None),
    format: Optional[BankStatementSourceType] = Form(None),
    account_iban: Optional[str] = Form(None),
    tenant_id: str = Form("default")
):
    """
    Importa extractos bancarios en formato oficial Norma 43 o CSV con rigor Decimal y validación de balance.
    """
    chosen_source = source_type or format or BankStatementSourceType.NORMA43
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo subido está vacío.")

    try:
        if chosen_source == BankStatementSourceType.NORMA43:
            parser = Norma43Parser()
            statement = parser.parse(content_bytes, account_iban=account_iban)
        else:
            parser = BankCsvParser()
            # Probar decodificaciones seguras
            decoded_text = None
            for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
                try:
                    decoded_text = content_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if not decoded_text:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo decodificar el archivo CSV.")
            statement = parser.parse(decoded_text, account_iban=account_iban)

        # Persistir extracto y movimientos en base de datos
        statement_id = BankService.save_statement(statement, tenant_id=tenant_id)
        statement.id = statement_id
        return statement

    except BankStatementDiscrepancyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error procesando extracto bancario: {str(e)}")


@router.get("/movements/unreconciled", response_model=List[BankMovementDTO])
async def get_unreconciled_movements_endpoint(
    tenant_id: str = Query("default"),
    account_iban: Optional[str] = Query(None)
):
    """
    Retorna la lista de movimientos bancarios pendientes de conciliar (UNRECONCILED).
    """
    movements: List[BankMovementDTO] = []
    with write_transaction(tenant_id) as conn:
        cursor = conn.cursor()
        query = """
            SELECT id, statement_id, account_iban, operation_date, value_date,
                   amount, balance_after, concept, reference, reconciled_invoice_id,
                   reconciliation_status, journal_entry_id
            FROM bank_movements
            WHERE tenant_id = ? AND reconciliation_status = 'UNRECONCILED'
        """
        params = [tenant_id]
        if account_iban:
            query += " AND account_iban = ?"
            params.append(account_iban)
        query += " ORDER BY operation_date DESC, id DESC"

        cursor.execute(query, tuple(params))
        for row in cursor.fetchall():
            movements.append(BankMovementDTO(
                id=row["id"],
                statement_id=row["statement_id"],
                account_iban=row["account_iban"] or "",
                operation_date=row["operation_date"] if "operation_date" in row.keys() and row["operation_date"] else row["movement_date"],
                value_date=row["value_date"] if "value_date" in row.keys() and row["value_date"] else row["movement_date"],
                amount=Decimal(str(row["amount"])),
                balance_after=Decimal(str(row["balance_after"])) if "balance_after" in row.keys() and row["balance_after"] is not None else Decimal("0.00"),
                concept=row["concept"],
                reference=row["reference"],
                reconciled_invoice_id=row["reconciled_invoice_id"] if "reconciled_invoice_id" in row.keys() else None,
                reconciliation_status=row["reconciliation_status"] if "reconciliation_status" in row.keys() else "UNRECONCILED",
                journal_entry_id=row["journal_entry_id"] if "journal_entry_id" in row.keys() else None
            ))
    return movements


@router.get("/reconciliation/suggestions", response_model=List[ReconciliationSuggestionDTO])
async def get_reconciliation_suggestions_endpoint(
    tenant_id: str = Query("default"),
    min_score: float = Query(0.70, ge=0.0, le=1.0)
):
    """
    Calcula y devuelve sugerencias de casación probabilística ponderada con score >= min_score.
    """
    engine = BankReconciliationEngine()
    suggestions = engine.get_suggestions(tenant_id=tenant_id, min_score=min_score)
    return suggestions


@router.post("/reconciliation/apply", response_model=ReconciliationResultDTO)
async def apply_reconciliation_endpoint(
    command: ApplyReconciliationCommand
):
    """
    Consolida una conciliación confirmada y asienta atómicamente el cobro/pago en el Libro Diario PGC.
    """
    engine = BankReconciliationEngine()
    try:
        result = engine.apply_reconciliation_command(command)
        return result
    except BankReconciliationConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e.message))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error aplicando conciliación: {str(e)}")

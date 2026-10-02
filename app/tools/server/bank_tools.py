from typing import Dict, Any, List
from app.domain.services.bank_service import BankService
from app.utils.logger import tool_logger

async def add_manual_bank_movement(date_str: str, concept: str, amount: float, reference: str = "") -> dict:
    """
    Registra manualmente un movimiento bancario en el sistema para la conciliación.
    """
    try:
        mov_id = BankService.add_manual_movement(date_str, concept, amount, reference)
        return {
            "status": "ok",
            "message": "Movimiento bancario registrado correctamente en el sistema.",
            "movement_id": mov_id,
            "data": {
                "fecha": date_str,
                "concepto": concept,
                "importe": amount,
                "referencia": reference
            }
        }
    except Exception as e:
        tool_logger.exception("Error al añadir movimiento bancario manual")
        return {"status": "error", "message": str(e)}

async def import_bank_statement(filepath: str) -> dict:
    """
    Importa extractos bancarios desde ficheros CSV o estándar Norma 43 español.
    """
    try:
        count = BankService.import_statement(filepath)
        return {
            "status": "ok",
            "message": f"Se han importado con éxito {count} movimientos desde el extracto bancario.",
            "movements_imported": count
        }
    except Exception as e:
        tool_logger.exception("Error al importar extracto bancario")
        return {"status": "error", "message": str(e)}

async def run_bank_reconciliation() -> dict:
    """
    Ejecuta el algoritmo de conciliación contable automática cruzando movimientos y facturas.
    Requiere confirmación explícita del usuario vía OOB.
    """
    from app.domain.services.approval_service import approval_service
    from app.domain.services.bank_reconciliation_engine import BankReconciliationEngine

    approved = await approval_service.request_approval(
        "run_bank_reconciliation",
        details={"action": "reconcile_all_pending"},
        summary="Ejecución de conciliación bancaria automática"
    )
    if not approved:
        return {"status": "error", "message": "Operación cancelada o timeout en confirmación."}

    try:
        engine = BankReconciliationEngine()
        suggestions = engine.get_suggestions(min_score=0.70)
        pairs = BankService.reconcile_matching_algorithm()
        return {
            "status": "ok",
            "message": f"Conciliación finalizada. Se han emparejado con éxito {len(pairs)} movimientos y se han hallado {len(suggestions)} sugerencias de alta confianza.",
            "reconciled_count": len(pairs),
            "reconciled_pairs": pairs,
            "suggestions_count": len(suggestions),
            "suggestions": [s.model_dump() for s in suggestions]
        }
    except Exception as e:
        tool_logger.exception("Error al ejecutar conciliación bancaria")
        return {"status": "error", "message": str(e)}

async def get_unreconciled_report_tool() -> dict:
    """
    Retorna el reporte de movimientos bancarios y facturas pendientes de conciliar,
    enriquecido con propuestas de casación probabilística ponderada.
    """
    try:
        from app.domain.services.bank_reconciliation_engine import BankReconciliationEngine
        report = BankService.get_unreconciled_report()
        engine = BankReconciliationEngine()
        suggestions = engine.get_suggestions(min_score=0.70)
        return {
            "status": "ok",
            "report": report,
            "suggestions": [s.model_dump() for s in suggestions]
        }
    except Exception as e:
        tool_logger.exception("Error al recuperar reporte de conciliación")
        return {"status": "error", "message": str(e)}

async def get_bank_balance() -> dict:
    """
    Recupera el saldo total de la cuenta bancaria.
    """
    try:
        from app.adapters.memory.memory import _get_connection
        saldo = 0.0
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(amount) FROM bank_movements")
            row = cursor.fetchone()
            if row and row[0] is not None:
                saldo = float(row[0])
        return {
            "status": "ok",
            "balance": saldo,
            "message": f"El saldo total actual en la cuenta bancaria es de {saldo:.2f} €."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}



TOOLS = {
    "add_manual_bank_movement": add_manual_bank_movement,
    "import_bank_statement": import_bank_statement,
    "run_bank_reconciliation": run_bank_reconciliation,
    "get_unreconciled_report_tool": get_unreconciled_report_tool,
    "get_bank_balance": get_bank_balance,

}

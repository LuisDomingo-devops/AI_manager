from app.domain.services.cash_flow_service import CashFlowService
from app.domain.services.sepa_service import SepaService
from app.utils.logger import tool_logger

async def get_cash_flow_forecast(horizon_days: int = 90, safe_threshold: float = 1000.0) -> dict:
    """
    Genera un informe detallado de previsión de tesorería y flujo de caja (cash-flow)
    a 7, 30 y 90 días, incluyendo alertas automatizadas si el saldo cae por debajo de un umbral seguro.
    """
    try:
        res = CashFlowService.get_forecast(days_horizon=int(horizon_days), safe_threshold=float(safe_threshold))
        return res
    except Exception as e:
        tool_logger.exception("Error al recuperar la previsión de cash-flow")
        return {"status": "error", "message": str(e)}

async def generate_sepa_remittance() -> dict:
    """
    Genera el archivo XML SEPA (pain.001.001.03) para todos los pagos pendientes de remesar.
    """
    try:
        from app.domain.services.approval_service import approval_service
        is_approved = await approval_service.request_approval(
            action_type="generate_sepa", 
            details={}
        )
        if not is_approved:
            return {
                "status": "error",
                "message": "Generación de remesa SEPA cancelada por el usuario o expirada."
            }
        res = SepaService.generate_remittance_xml()
        return res
    except Exception as e:
        tool_logger.exception("Error al generar la remesa SEPA")
        return {"status": "error", "message": str(e)}

TOOLS = {
    "get_cash_flow_forecast": get_cash_flow_forecast,
    "generate_sepa_remittance": generate_sepa_remittance,
}

import datetime
from app.adapters.memory.memory import _get_connection
from app.utils.logger import tool_logger
from app.domain.services.ledger_service import LedgerService

class ClosingService:
    @staticmethod
    def close_fiscal_year(year: int) -> dict:
        """
        Realiza el cierre del ejercicio fiscal:
        Delega la operación segura en LedgerService para evitar
        errores de precisión y duplicidad lógica.
        """
        try:
            return LedgerService.close_fiscal_year(year)
        except Exception as e:
            tool_logger.exception(f"Error en cierre de ejercicio {year}")
            return {"status": "error", "message": str(e)}

import pytest
from unittest.mock import patch
import sqlite3

from app.tools.server.billing_tools import delete_client

@pytest.mark.asyncio
async def test_billing_qa_audit_trail_never_silently_lost():
    """
    Test de QA: Asegurar que las operaciones contables críticas mantengan
    la trazabilidad legal (Veri*Factu / Ley Antifraude 11/2021). Si el motor de auditoría
    falla, no debe fingirse un borrado 100% limpio sin advertencia explícita.
    """
    with patch("app.tools.server.billing_tools.delete_contact", return_value={"status": "ok", "message": "Deleted"}), \
         patch("app.domain.services.audit_ledger.AuditLedgerService.log_audit_event", side_effect=sqlite3.DatabaseError("Disk full")):
        
        result = await delete_client(client_id="CLI-QA-999")
        
        assert result["status"] == "ok"
        # Debe incluir flag de auditoría o advertencia
        assert result.get("audit_warning") is True or "auditoría" in result.get("message", "").lower()

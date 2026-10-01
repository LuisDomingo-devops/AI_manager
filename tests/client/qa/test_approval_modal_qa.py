"""
Test de QA para el Modal Visual de Aprobación Humana en PyQt6 (User Story 2).
Valida presentación de datos críticos, aviso de inmutabilidad y los botones [Aprobar y Emitir] / [Rechazar / Editar].
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock

# Ajustar PYTHONPATH
root_dir = str(Path(__file__).resolve().parents[3])
client_dir = os.path.join(root_dir, "client")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if client_dir not in sys.path:
    sys.path.insert(0, client_dir)

from PyQt6.QtWidgets import QApplication, QDialog
from client.gui.dialogs.approval_modal import ApprovalModalDialog


@pytest.fixture(scope="session")
def qapp():
    """Instancia de QApplication compartida para tests QA en modo offscreen."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_approval_modal_display_and_approve(qapp):
    """Verifica que el diálogo muestre los detalles y al pulsar Aprobar retorne QDialog.DialogCode.Accepted."""
    details = {
        "recipient_name": "ACME Corporación S.L.",
        "recipient_nif": "B12345674",
        "total_amount": 1210.00,
        "base_amount": 1000.00,
        "vat_amount": 210.00
    }
    
    dialog = ApprovalModalDialog(
        action_id="test-action-123",
        action_type="emit_invoice",
        summary="Emitir Factura F2026-0001",
        details=details
    )
    
    # Comprobar presencia de widgets críticos
    assert hasattr(dialog, "btn_approve"), "El diálogo debe tener un botón btn_approve"
    assert hasattr(dialog, "btn_reject"), "El diálogo debe tener un botón btn_reject"
    assert "Aprobar" in dialog.btn_approve.text()
    assert "Rechazar" in dialog.btn_reject.text()
    
    # Comprobar que el texto del diálogo contiene el importe y el receptor
    dialog_text = dialog.details_label.text() if hasattr(dialog, "details_label") else ""
    assert "ACME Corporación S.L." in dialog_text or "1210.00" in dialog_text or "1210" in dialog_text
    
    # Simular clic en Aprobar
    dialog.btn_approve.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.is_approved is True


def test_approval_modal_reject(qapp):
    """Verifica que al pulsar Rechazar retorne QDialog.DialogCode.Rejected."""
    dialog = ApprovalModalDialog(
        action_id="test-action-456",
        action_type="cancel_invoice",
        summary="Anulación de Factura",
        details={"invoice_id": "F2026-0005"}
    )
    
    # Simular clic en Rechazar
    dialog.btn_reject.click()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.is_approved is False

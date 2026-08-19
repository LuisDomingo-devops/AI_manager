"""
TESTS DE INTEGRACIÓN — Categorías GUI, QStackedWidget y Servicios del Backend
Verifica la vinculación entre todas las subcategorías del sidebar, el conmutador de vistas y los datos reales.
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Asegurar sys.path con root y client
root_dir = str(Path(__file__).resolve().parents[1])
client_dir = os.path.join(root_dir, "client")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if client_dir not in sys.path:
    sys.path.insert(0, client_dir)

from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import Qt

from client.gui.sidebar_widget import SIDEBAR_CATEGORIES
from client.gui.app import AlfonsoHUDDashboard
from client.gui.dialogs.specialized_views import (
    AlfonsoCashFlowWidget,
    AlfonsoInvoiceEmitterWidget,
    AlfonsoPayrollWidget,
    AlfonsoVerifactuAuditWidget,
    AlfonsoBoeWidget,
    AlfonsoOfficialBooksWidget,
    AlfonsoBackupWidget,
    AlfonsoTenantAdvisorWidget
)


@pytest.fixture(scope="session")
def qapp():
    """Instancia de QApplication compartida para tests de integración GUI."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(autouse=True)
def mock_api_calls():
    """Mockea las llamadas HTTP de requests para que los tests de GUI sean instantáneos."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "aggregates": [], "conversations": [], "items": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("requests.Session.get", return_value=mock_resp), \
         patch("requests.Session.post", return_value=mock_resp), \
         patch("requests.get", return_value=mock_resp), \
         patch("requests.post", return_value=mock_resp):
        yield


@pytest.fixture
def mock_dashboard_config():
    return {
        "url": "http://127.0.0.1:8000",
        "api_key": "test_key",
        "keyword": "alfonso",
        "device": None,
        "output_device": None,
        "model": "tiny",
        "threshold": None,
        "debug": False,
        "gui": True
    }


def test_dashboard_initialization_and_stack_mapping(qapp, mock_dashboard_config):
    """Verifica que AlfonsoHUDDashboard inicializa todas las vistas en central_stack."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # Verificar que central_stack contiene todas las vistas especializadas
        assert dashboard.central_stack.count() >= 30, "El central_stack debe tener al menos 30 vistas indexadas"
        assert dashboard.sidebar is not None
        assert dashboard.lbl_view_title is not None
        assert "DASHBOARD" in dashboard.lbl_view_title.text() or "PANEL DE CONTROL" in dashboard.lbl_view_title.text()


def test_all_sidebar_categories_switch_views(qapp, mock_dashboard_config):
    """Verifica que cada subcategoría en SIDEBAR_CATEGORIES cambia correctamente la vista en central_stack."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        visited_indices = set()

        for cat in SIDEBAR_CATEGORIES:
            cat_id = cat["id"]
            for subcat in cat["subcategories"]:
                subcat_id = subcat["id"]
                
                # Ejecutar cambio de vista
                dashboard.switch_to_view((cat_id, subcat_id))
                
                cur_idx = dashboard.central_stack.currentIndex()
                assert cur_idx >= 0
                assert cur_idx < dashboard.central_stack.count()
                visited_indices.add(cur_idx)

                # Verificar sincronización del título superior y del sidebar activo
                title_text = dashboard.lbl_view_title.text()
                assert len(title_text) > 5
                assert dashboard.sidebar.current_cat_id == cat_id
                assert dashboard.sidebar.current_subcat_id == subcat_id

        assert len(visited_indices) >= 20, "Deben haberse alcanzado al menos 20 índices distintos en central_stack"


def test_legacy_view_methods_compatibility(qapp, mock_dashboard_config):
    """Verifica que todos los métodos legados de navegación continúan funcionando."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # Métodos legacy
        dashboard.show_dashboard()
        assert dashboard.central_stack.currentIndex() == 0

        dashboard.show_ledger()
        assert dashboard.central_stack.currentIndex() == 3

        dashboard.show_expenses()
        assert dashboard.central_stack.currentIndex() == 6

        dashboard.show_reconcile()
        assert dashboard.central_stack.currentIndex() == 9

        dashboard.show_aeat()
        assert dashboard.central_stack.currentIndex() == 12

        dashboard.show_archive()
        assert dashboard.central_stack.currentIndex() == 19

        dashboard.show_mail()
        assert dashboard.central_stack.currentIndex() == 23

        dashboard.show_calendar()
        assert dashboard.central_stack.currentIndex() == 14

        dashboard.show_compliance()
        assert dashboard.central_stack.currentIndex() == 26

        dashboard.show_config()
        assert dashboard.central_stack.currentIndex() == 29


def test_specialized_cash_flow_widget_integration(qapp):
    """Verifica la integración y carga de datos en AlfonsoCashFlowWidget."""
    cf_widget = AlfonsoCashFlowWidget(embedded=True)
    cf_widget.show()

    assert cf_widget.tbl_inflows.columnCount() == 4
    assert cf_widget.tbl_outflows.columnCount() == 3

    # Cambiar horizonte a 60 días
    cf_widget.cb_horizon.setCurrentIndex(1)
    assert cf_widget.cb_horizon.currentText() == "60 Días"

    # Verificar que las tarjetas tienen valores numéricos
    current_val = cf_widget.card_current.findChild(QLabel, "value_lbl").text()
    assert "€" in current_val


def test_specialized_invoice_emitter_widget_integration(qapp):
    """Verifica el cálculo de bases, IVA y retenciones en AlfonsoInvoiceEmitterWidget."""
    emitter = AlfonsoInvoiceEmitterWidget(embedded=True)
    emitter.show()

    emitter.sp_base.setValue(1000.00)
    emitter.cb_iva.setCurrentIndex(0)   # 21%
    emitter.cb_irpf.setCurrentIndex(0)  # 15%

    emitter.recalc_totals()

    assert "1,000.00" in emitter.lbl_subtotal.text() or "1.000,00" in emitter.lbl_subtotal.text()
    assert "210.00" in emitter.lbl_iva.text() or "210,00" in emitter.lbl_iva.text()
    assert "150.00" in emitter.lbl_irpf.text() or "150,00" in emitter.lbl_irpf.text()
    assert "1,060.00" in emitter.lbl_total.text() or "1.060,00" in emitter.lbl_total.text()


def test_specialized_payroll_and_audit_widgets_integration(qapp):
    """Verifica la carga de registros en los widgets de nóminas y auditoría Veri*Factu."""
    payroll_widget = AlfonsoPayrollWidget(embedded=True)
    payroll_widget.show()
    assert payroll_widget.tbl_employees.columnCount() == 6
    assert payroll_widget.tbl_employees.rowCount() >= 1

    audit_widget = AlfonsoVerifactuAuditWidget(embedded=True)
    audit_widget.show()
    assert audit_widget.tbl_hashes.columnCount() == 5
    assert audit_widget.tbl_hashes.rowCount() >= 1


def test_specialized_auxiliary_widgets_integration(qapp):
    """Verifica la inicialización de BOE, Libros Oficiales, Backups y Panel Asesor."""
    boe = AlfonsoBoeWidget(embedded=True)
    boe.show()
    assert boe.news_table.rowCount() >= 1

    books = AlfonsoOfficialBooksWidget(embedded=True)
    books.show()
    assert "Libros Registro Obligatorios" in books.windowTitle() or books.log_view is not None

    backups = AlfonsoBackupWidget(embedded=True)
    backups.show()
    assert backups.tbl_backups.rowCount() >= 1

    tenant = AlfonsoTenantAdvisorWidget(embedded=True)
    tenant.show()
    assert tenant.cb_tenants.count() >= 1

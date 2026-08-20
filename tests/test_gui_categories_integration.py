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


def test_ai_assistant_and_subscription_routing_integration(qapp, mock_dashboard_config):
    """Verifica que el índice 22 monta AlfonsoAIChatAssistantWidget y la suscripción redirige al índice 32."""
    from client.gui.dialogs.specialized_views import AlfonsoAIChatAssistantWidget
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # Verificar índice 22 es AlfonsoAIChatAssistantWidget
        widget_22 = dashboard.central_stack.widget(22)
        assert isinstance(widget_22, AlfonsoAIChatAssistantWidget)

        # Probar switch_to_view a Asistente IA
        dashboard.switch_to_view(("comunicacion", "asistente_ia"))
        assert dashboard.central_stack.currentIndex() == 22

        # Probar navegación a suscripción
        dashboard.show_subscription_dialog()
        assert dashboard.central_stack.currentIndex() == 32


def test_subview_mode_propagation_integration(qapp, mock_dashboard_config):
    """Verifica que switch_to_view activa los modos y pestañas correspondientes en las vistas compuestas."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. Laboral: empleados (16), nóminas (17), tgss (18)
        dashboard.switch_to_view(("laboral", "empleados_contratos"))
        assert dashboard.central_stack.currentIndex() == 16
        assert dashboard.view_employees.mode == "employees"

        dashboard.switch_to_view(("laboral", "generador_nominas"))
        assert dashboard.central_stack.currentIndex() == 17
        assert dashboard.view_payrolls.mode == "payrolls"

        dashboard.switch_to_view(("laboral", "afiliacion_tgss"))
        assert dashboard.central_stack.currentIndex() == 18
        assert dashboard.view_tgss.mode == "tgss"

        # 2. Impuestos: modelos (12), automatización/sede (13)
        dashboard.switch_to_view(("impuestos", "modelos_trimestrales"))
        assert dashboard.central_stack.currentIndex() == 12
        assert dashboard.view_taxes.stack.currentIndex() == 0

        dashboard.switch_to_view(("impuestos", "automatizacion_aeat"))
        assert dashboard.central_stack.currentIndex() == 13
        assert dashboard.view_aeat_auto.stack.currentIndex() == 1

        # 3. Configuración: perfil fiscal (29), voz/IA (30)
        dashboard.switch_to_view(("sistema", "perfil_fiscal"))
        assert dashboard.central_stack.currentIndex() == 29
        assert dashboard.view_config.stack.currentIndex() == 0

        dashboard.switch_to_view(("sistema", "voz_modelos_ia"))
        assert dashboard.central_stack.currentIndex() == 30
        assert dashboard.view_voice_config.stack.currentIndex() == 1


def test_central_stack_tables_integration(qapp, mock_dashboard_config):
    """Verifica que todas las tablas del panel central están configuradas con cabeceras estilizadas y filas legibles."""
    from PyQt6.QtWidgets import QTableWidget

    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. Tabla de Movimientos Recientes en Dashboard (Índice 0)
        dashboard.switch_to_view(("dashboard", "resumen_ejecutivo"))
        assert dashboard.tbl_recent_invoices.columnCount() == 4
        assert dashboard.tbl_recent_invoices.verticalHeader().isVisible() is False
        assert dashboard.tbl_recent_invoices.horizontalHeader().count() == 4

        # 2. Tablas en CashFlow (Índice 2)
        dashboard.switch_to_view(("dashboard", "cash_flow_prevision"))
        cf_tables = dashboard.view_cashflow.findChildren(QTableWidget)
        assert len(cf_tables) == 2
        for t in cf_tables:
            assert t.alternatingRowColors() is True
            assert t.verticalHeader().isVisible() is False

        # 3. Tablas en Laboral / Nóminas (Índice 16, 17, 18)
        dashboard.switch_to_view(("laboral", "empleados_contratos"))
        assert dashboard.view_employees.tbl_employees.alternatingRowColors() is True
        assert dashboard.view_employees.tbl_employees.columnCount() == 6

        # 4. Tabla en Auditoría Verifactu (Índice 27)
        dashboard.switch_to_view(("auditoria", "huella_verifactu"))
        assert dashboard.view_verifactu_audit.tbl_hashes.alternatingRowColors() is True
        assert dashboard.view_verifactu_audit.tbl_hashes.columnCount() == 5


def test_ledger_navigation_and_mayor_population_integration(qapp, mock_dashboard_config):
    """Verifica la integración completa del Libro Diario y Mayor desde el Dashboard."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # Navegar a Libro Diario / Facturas Emitidas
        dashboard.switch_to_view(("facturacion", "facturas_emitidas"))
        assert dashboard.central_stack.currentIndex() == 3
        ledger = dashboard.view_invoices

        # Verificar que el Libro Diario tiene filas
        assert ledger.table.rowCount() > 0

        # Conmutar al Mayor y comprobar carga de datos
        ledger.switch_view(1)
        assert ledger.table_mayor.rowCount() > 0
        assert "€" in ledger.lbl_mayor_total_debe.text()

        # Conmutar al Diario de nuevo y ejecutar salto interactivo al Mayor
        ledger.switch_view(0)
        target_code = "70500000" if ledger.cmb_mayor_account.findData("70500000") >= 0 else ledger.cmb_mayor_account.itemData(0)
        ledger.jump_to_mayor(target_code)
        assert ledger.main_stack.currentIndex() == 1
        assert ledger.cmb_mayor_account.currentData() == target_code
        assert ledger.table_mayor.rowCount() > 0


def test_help_center_navigation_and_shortcuts_integration(qapp, mock_dashboard_config):
    """Verifica la navegación integral al Centro de Ayuda vía sidebar, método show_help y atajo F1."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. Navegación directa vía switch_to_view tupla
        dashboard.switch_to_view(("sistema", "centro_ayuda"))
        assert dashboard.central_stack.currentIndex() == 33
        assert "CENTRO DE AYUDA" in dashboard.lbl_view_title.text()
        assert dashboard.sidebar.current_subcat_id == "centro_ayuda"

        # 2. Navegación vía método helper show_help
        dashboard.switch_to_view("Dashboard")
        assert dashboard.central_stack.currentIndex() == 0
        dashboard.show_help()
        assert dashboard.central_stack.currentIndex() == 33

        # 3. Navegación vía alias de cadena "Ayuda"
        dashboard.switch_to_view("Ayuda")
        assert dashboard.central_stack.currentIndex() == 33

        # 4. Verificar que el widget interno de ayuda está montado correctamente
        hc = dashboard.view_help_center
        assert hc.tab_stack.count() == 4
        assert len(hc.manual_full_text) > 0


def test_recent_movements_and_quick_access_integration(qapp, mock_dashboard_config):
    """Verifica la integración de los paneles inferiores de movimientos y accesos rápidos."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. Comprobar que la tabla de movimientos está activa en el dashboard (índice 0)
        assert dashboard.central_stack.currentIndex() == 0
        tbl = dashboard.tbl_recent_invoices
        assert tbl.rowCount() >= 4
        assert tbl.columnCount() == 4

        # 2. Comprobar que los datos cargados respetan el alineamiento y colores de importe
        first_amount_item = tbl.item(0, 3)
        assert first_amount_item is not None
        assert first_amount_item.text().startswith("+") or first_amount_item.text().startswith("-")

        # 3. Comprobar que la sección de accesos rápidos está integrada en la vista principal
        dashboard.switch_to_view(("dashboard", "resumen_ejecutivo"))
        assert dashboard.central_stack.currentIndex() == 0








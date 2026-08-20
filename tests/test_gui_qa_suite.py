"""
SUITE DE TESTS QA & ESTRÉS — GUI Alfonso Autónomo
Verifica la estabilidad del conmutador de vistas bajo carga rápida, resiliencia a entradas complejas,
manejo de fallos en servicios y solidez estructural de todos los componentes visuales.
"""

import sys
import os
import random
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

from PyQt6.QtWidgets import QApplication, QTableWidgetItem
from PyQt6.QtCore import Qt

from client.gui.sidebar_widget import SIDEBAR_CATEGORIES, AlfonsoSidebarWidget
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
    """Instancia de QApplication compartida para tests de QA."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(autouse=True)
def mock_api_calls():
    """Mockea las llamadas HTTP de requests para que los tests de QA sean instantáneos."""
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


def test_qa_rapid_view_switching_stress(qapp, mock_dashboard_config):
    """Prueba de estrés QA: Conmutación rápida a través de todas las vistas múltiples veces."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        all_subcategories = []
        for cat in SIDEBAR_CATEGORIES:
            for sub in cat["subcategories"]:
                all_subcategories.append((cat["id"], sub["id"]))

        # Ejecutar 3 pasadas completas a alta velocidad
        for loop_idx in range(3):
            for cat_id, sub_id in all_subcategories:
                dashboard.switch_to_view((cat_id, sub_id))
                assert dashboard.central_stack.currentIndex() >= 0
                assert dashboard.sidebar.current_cat_id == cat_id
                assert dashboard.sidebar.current_subcat_id == sub_id

        # Conmutación aleatoria (saltos no contiguos)
        random.seed(42)
        sample_hops = random.sample(all_subcategories, min(15, len(all_subcategories)))
        for cat_id, sub_id in sample_hops:
            dashboard.switch_to_view((cat_id, sub_id))
            assert dashboard.central_stack.currentIndex() >= 0


def test_qa_search_filter_edge_cases(qapp):
    """Prueba de estrés QA: Entradas extremas y especiales en el buscador del sidebar."""
    sidebar = AlfonsoSidebarWidget()
    sidebar.show()

    test_queries = [
        "",                             # Cadena vacía
        "   ",                          # Espacios en blanco
        "FACTURA",                      # Mayúsculas puras
        "nóminas",                      # Minúsculas con tilde
        "nominas",                      # Sin tilde
        "VERI*FACTU",                   # Caracteres especiales (*, -)
        "303",                          # Números
        "áéíóúÁÉÍÓÚñÑ",                 # Caracteres acentuados y eñes
        "🔍⚡🛡️",                        # Emojis
        "a" * 300,                      # Cadena extraordinariamente larga
        "<script>alert(1)</script>",    # Inyección de texto HTML
        "SELECT * FROM invoices;"       # Inyección de texto SQL
    ]

    for q in test_queries:
        sidebar.search_input.setText(q)
        # La GUI no debe lanzar excepciones y el buscador debe procesar el filtro
        assert sidebar.search_input.text() == q

    # Limpiar y verificar restauración completa
    sidebar.btn_clear_search.click()
    assert sidebar.search_input.text() == ""
    for group in sidebar.groups.values():
        assert group.isHidden() is False


def test_qa_central_stack_widget_validity(qapp, mock_dashboard_config):
    """Verifica que todos los widgets en central_stack están correctamente inicializados."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        count = dashboard.central_stack.count()
        assert count >= 30, f"Se esperaban al menos 30 vistas en central_stack, encontradas {count}"

        for idx in range(count):
            widget = dashboard.central_stack.widget(idx)
            assert widget is not None, f"El widget en el índice {idx} es None"
            assert widget.layout() is not None or widget.findChildren(object), f"El widget en {idx} no tiene layout ni hijos"


def test_qa_defensive_fallbacks_on_empty_db(qapp):
    """Verifica que las vistas especializadas no fallen cuando la base de datos está vacía o inaccesible."""
    with patch("app.adapters.memory.memory._get_connection", side_effect=Exception("DB Unreachable")):
        # Cash Flow debe usar fallbacks seguros sin crashear
        cf = AlfonsoCashFlowWidget(embedded=True)
        cf.show()
        assert cf.tbl_inflows.columnCount() == 4

        # Nóminas debe renderizar la plantilla básica sin crashear
        payroll = AlfonsoPayrollWidget(embedded=True)
        payroll.show()
        assert payroll.tbl_employees.columnCount() == 6

        # Verifactu debe renderizar la auditoría sin crashear
        verif = AlfonsoVerifactuAuditWidget(embedded=True)
        verif.show()
        assert verif.tbl_hashes.columnCount() == 5


def test_qa_telemetry_resilience_and_graceful_shutdown(qapp, mock_dashboard_config):
    """Verifica que update_business_metrics y close_gui se ejecutan limpiamente en condiciones límite."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. Telemetría con DB simulada vacía o con error
        with patch("app.adapters.memory.memory._get_connection", side_effect=Exception("DB Error")):
            dashboard.update_business_metrics()
            assert dashboard.donut_chart.total >= 0
            assert dashboard.bar_chart is not None

        # 2. Cierre limpio
        dashboard.close_gui()


def test_qa_table_widget_resilience_and_no_white_backgrounds(qapp, mock_dashboard_config):
    """QA Stress Test: Verifica que ninguna tabla de central_stack tenga fondo blanco y que soporten datos masivos."""
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        all_tables = dashboard.findChildren(QTableWidget)
        assert len(all_tables) >= 5, f"Se esperaban al menos 5 tablas en el Dashboard, encontradas {len(all_tables)}"

        for table in all_tables:
            # Comprobar que no hay estilos forzados a blanco
            inline_style = table.styleSheet()
            assert "background: #FFFFFF" not in inline_style
            assert "background: white" not in inline_style

            # Inserción masiva de datos (Stress)
            table.setRowCount(100)
            for r in range(100):
                for c in range(table.columnCount()):
                    table.setItem(r, c, QTableWidgetItem(f"Row {r} Col {c}"))
            
            # Limpieza rápida
            table.setRowCount(0)
            assert table.rowCount() == 0
            assert table.horizontalHeader().isHidden() is False


def test_qa_ledger_empty_account_and_toggle_stress(qapp):
    """QA Stress Test: Verifica el manejo de subcuentas sin apuntes y alternancia rápida de filtros en el Mayor."""
    from client.gui.dialogs.widgets import AlfonsoLedgerDialog

    ledger = AlfonsoLedgerDialog(embedded=True)
    ledger.show()

    # 1. Alternancia de filtro de sólo activas
    ledger.chk_only_active.setChecked(True)
    count_active = ledger.cmb_mayor_account.count()
    assert count_active > 0

    ledger.chk_only_active.setChecked(False)
    count_all = ledger.cmb_mayor_account.count()
    assert count_all >= count_active

    # 2. Forzar selección de subcuenta sin apuntes (ej: 10000000)
    ledger.populate_mayor_accounts(preferred_code="10000000", only_active=False)
    ledger.load_mayor_data()
    assert ledger.table_mayor.rowCount() == 1
    info_item = ledger.table_mayor.item(0, 2)
    assert "no tiene apuntes" in info_item.text() or "10000000" in info_item.text()
    assert "0.00 €" in ledger.lbl_mayor_total_debe.text()

    # 3. Caso borde: combobox vacío o sin selección
    ledger.cmb_mayor_account.setCurrentIndex(-1)
    ledger.load_mayor_data()
    assert ledger.table_mayor.rowCount() == 0


def test_qa_help_center_search_and_chapter_stress(qapp):
    """QA Stress Test: Verifica el comportamiento del Centro de Ayuda ante búsquedas complejas, capítulos y fallbacks."""
    from client.gui.dialogs.specialized_views import AlfonsoHelpCenterWidget

    hc = AlfonsoHelpCenterWidget(embedded=True)
    hc.show()

    # 1. Búsquedas de estrés: cadenas inexistentes, caracteres especiales, vacíos
    stress_queries = [
        "xyzabc123nonexistent",
        "!!!@@@###$$$",
        "   ",
        "",
        "VERI*FACTU",
        "hacienda",
        "cuenta 572",
        "modelo 130"
    ]
    for q in stress_queries:
        hc.filter_manual(q)
        assert len(hc.browser_manual.toHtml()) > 0

    # 2. Conmutación rápida a través de todos los capítulos del combobox
    for i in range(hc.cb_chapters.count()):
        hc.cb_chapters.setCurrentIndex(i)
        assert len(hc.browser_manual.toHtml()) > 0

    # 3. Filtrado masivo en preguntas frecuentes (FAQ)
    for q in ["factura", "irpf", "seguridad social", "no_match_xyz", ""]:
        hc.filter_faq(q)

    # 4. Resiliencia ante manual no disponible
    with patch("os.path.exists", return_value=False):
        hc.load_manual_content()
        assert len(hc.manual_full_text) > 0


def test_qa_footer_recent_movements_and_quick_access_stress(qapp, mock_dashboard_config):
    """QA Stress Test: Verifica la resiliencia y estabilidad visual de los paneles inferiores ante redimensionamientos extremos."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. Comprobar estabilidad bajo diferentes resoluciones de pantalla
        resolutions = [
            (800, 600),
            (1024, 768),
            (1366, 768),
            (1920, 1080),
            (2560, 1440)
        ]
        for w, h in resolutions:
            dashboard.resize(w, h)
            qapp.processEvents()
            assert dashboard.tbl_recent_invoices.isVisible() is True
            assert dashboard.tbl_recent_invoices.width() > 0

        # 2. Inyección de datos masivos en la tabla de últimos movimientos
        large_mock_data = [
            (f"01/01/2026", f"Transacción de prueba extendida #{i} - Empresa Cliente Multinacional S.A.", "Factura Emitida", f"+{i * 123.45:,.2f} €")
            for i in range(50)
        ]
        dashboard.tbl_recent_invoices.setRowCount(len(large_mock_data))
        for r, row in enumerate(large_mock_data):
            for c, val in enumerate(row):
                dashboard.tbl_recent_invoices.setItem(r, c, QTableWidgetItem(val))

        qapp.processEvents()
        assert dashboard.tbl_recent_invoices.rowCount() == 50


def test_qa_subscription_dialog_plan_stress_and_switching(qapp, mock_dashboard_config):
    """QA Stress Test: Verifica la resiliencia ante cambios rápidos de plan y redimensionamiento en AlfonsoSubscriptionDialog."""
    from client.gui.dialogs.widgets import AlfonsoSubscriptionDialog
    from app.domain.services.bank_service import BankService

    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):

        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        dialog = AlfonsoSubscriptionDialog(parent=dashboard, embedded=True)
        dialog.show()

        # 1. Ciclo rápido de conmutación de planes
        tiers = ["basic", "pro", "advisor", "basic", "pro"]
        for t in tiers:
            with patch("PyQt6.QtWidgets.QMessageBox.information"):
                dialog.select_plan(t)
                qapp.processEvents()
                assert dialog.cards[t]["button"].text() == "PLAN ACTUAL"
                assert dialog.cards[t]["button"].isEnabled() is False

        # 2. Comprobar que el sidebar del dashboard sincronizó el título de la licencia
        assert "Profesional" in dashboard.sidebar.lbl_plan_title.text() or "Pro" in dashboard.sidebar.lbl_plan_title.text()

        # 3. Prueba de redimensionamiento
        resolutions = [(800, 500), (1024, 700), (1400, 900)]
        for w, h in resolutions:
            dialog.resize(w, h)
            qapp.processEvents()
            assert dialog.width() == w







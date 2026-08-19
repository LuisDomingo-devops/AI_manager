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

from PyQt6.QtWidgets import QApplication
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

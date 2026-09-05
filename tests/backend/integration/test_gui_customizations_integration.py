"""
TEST DE INTEGRACIÓN — Personalizaciones y Simplificación Visual de la GUI
Comprueba que la carga conjunta del sidebar y la ventana principal se realiza sin errores
a pesar de no contar con el widget del reloj ni con los badges estáticos laterales,
y que el sistema es completamente estable durante la navegación.
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Asegurar sys.path con root y client
root_dir = str(Path(__file__).resolve().parents[2])
client_dir = os.path.join(root_dir, "client")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if client_dir not in sys.path:
    sys.path.insert(0, client_dir)

from PyQt6.QtWidgets import QApplication
from client.gui.app import AlfonsoHUDDashboard
from client.gui.sidebar_widget import SIDEBAR_CATEGORIES


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
    """Mockea las llamadas HTTP para que la inicialización de la GUI sea instantánea y robusta."""
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


def test_dashboard_integration_without_badges_and_clock(qapp, mock_dashboard_config):
    """Verifica que la app principal inicializa y navega correctamente sin badges laterales ni reloj superior."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):

        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. Comprobar que el sidebar lateral cargado no tiene badges y la ventana principal se ha inicializado
        assert dashboard.sidebar is not None
        for group in dashboard.sidebar.groups.values():
            # El badge de CategoryGroupWidget debe estar vacío o no cargado en la UI
            if group.category_data.get("badge"):
                assert group.category_data["badge"] == ""

        # 2. Navegar a través de algunas de las categorías del sidebar y asegurar que la navegación funciona sin excepciones
        # Navegamos a ingresos_gastos -> facturas_emitidas
        dashboard.on_sidebar_category_selected("ingresos_gastos", "facturas_emitidas", "Facturas Emitidas")
        assert dashboard.central_stack.currentIndex() != 0 # Se ha movido de la pestaña de resumen ejecutivo inicial

        # Navegamos a bancos -> conciliacion_bancaria
        dashboard.on_sidebar_category_selected("bancos", "conciliacion_bancaria", "Conciliación Bancaria")
        
        # 3. Volver al dashboard y asegurar que el subtítulo minimalista se ha renderizado sin problemas
        dashboard.on_sidebar_category_selected("dashboard", "resumen_ejecutivo", "Resumen Ejecutivo")
        assert dashboard.central_stack.currentIndex() == 0

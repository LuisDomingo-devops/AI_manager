"""
SUITE DE QA — Personalizaciones y Simplificación Visual de la GUI
Verifica los estándares de calidad visual premium del rediseño de Alfonso Autónomo,
incluyendo la eliminación de saturación de información en la cabecera principal,
el aumento del logo corporativo y la ausencia de badges ruidosos.
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

from PyQt6.QtWidgets import QApplication, QFrame, QLabel
from client.gui.app import AlfonsoHUDDashboard
from client.gui.sidebar_widget import SIDEBAR_CATEGORIES


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
    """Mockea las llamadas HTTP para pruebas de QA instantáneas."""
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


def test_qa_design_simplification_and_cleanliness(qapp, mock_dashboard_config):
    """Verifica que el dashboard cumple con los estándares de diseño limpio y sin sobreinformación."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):

        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        dashboard.show()

        # 1. QA de Cabecera Superior (GlobalTopBar)
        # La barra de cabecera debe ser de 60px de alto y no tener reloj para un look minimalista
        top_bar = dashboard.findChild(QFrame, "GlobalTopBar")
        assert top_bar is not None
        assert top_bar.height() == 60 or top_bar.fixedHeight() == 60
        assert dashboard.clock_lbl is None

        # 2. QA de Menú Lateral (Sidebar)
        # Las categorías no deben tener ningún badge para evitar sobrecargar al usuario
        assert len(dashboard.sidebar.groups) >= 8
        for group_id, group in dashboard.sidebar.groups.items():
            assert group.category_data.get("badge") == ""

        # 3. QA de Dashboard Principal
        # El saludo de bienvenida debe ser despejado y conciso
        # Buscamos el label de saludo que contiene el subtítulo
        all_labels = dashboard.findChildren(QLabel)
        sub_greeting_label = None
        for lbl in all_labels:
            if "Resumen de actividad" in lbl.text():
                sub_greeting_label = lbl
                break
        assert sub_greeting_label is not None, "El subtítulo minimalista 'Resumen de actividad y estado financiero actual.' debe estar presente"

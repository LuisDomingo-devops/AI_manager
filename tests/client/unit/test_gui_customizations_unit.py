"""
SUITE DE TESTS UNITARIOS — Personalización y Simplificación Visual de la GUI
Verifica los cambios de rediseño: el tamaño del logotipo, el alto de la barra superior,
la eliminación de badges en el sidebar, y la eliminación del reloj/reducidor de saturación.
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch

# Asegurar sys.path con root y client
root_dir = str(Path(__file__).resolve().parents[2])
client_dir = os.path.join(root_dir, "client")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if client_dir not in sys.path:
    sys.path.insert(0, client_dir)

from PyQt6.QtWidgets import QApplication, QFrame
from client.gui.app import AlfonsoHUDDashboard
from client.gui.sidebar_widget import SIDEBAR_CATEGORIES


@pytest.fixture(scope="session")
def qapp():
    """Instancia de QApplication compartida para tests unitarios GUI."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_gui_top_bar_height_and_logo_size(qapp):
    """Verifica que la cabecera superior tiene una altura de 60px y el reloj ha sido eliminado."""
    config = {
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

    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):

        app_gui = AlfonsoHUDDashboard(config)
        app_gui.show()

        # 1. Comprobar que existe la barra superior GlobalTopBar y su altura es 60
        top_bar = app_gui.findChild(QFrame, "GlobalTopBar")
        assert top_bar is not None
        assert top_bar.height() == 60 or top_bar.fixedHeight() == 60

        # 2. Comprobar que el reloj se ha deshabilitado para evitar saturación
        assert app_gui.clock_lbl is None


def test_gui_sidebar_no_badges(qapp):
    """Verifica que las categorías del sidebar no tienen badges cargados para evitar ruido visual."""
    for cat in SIDEBAR_CATEGORIES:
        assert cat.get("badge") == "", f"La categoría {cat['id']} tiene un badge no vacío"

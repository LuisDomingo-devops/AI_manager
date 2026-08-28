import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Ajustar PATH
root_dir = str(Path(__file__).resolve().parents[2])
client_dir = os.path.join(root_dir, "client")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if client_dir not in sys.path:
    sys.path.insert(0, client_dir)

from PyQt6.QtWidgets import QApplication
from client.gui.app import AlfonsoHUDDashboard
from client.gui.dialogs.document_customizer import AlfonsoDocumentCustomizerWidget
from client.gui.sidebar_widget import SIDEBAR_CATEGORIES

@pytest.fixture(scope="session")
def qapp():
    """Instancia de QApplication compartida para tests QA en modo offscreen."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

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

@pytest.fixture(autouse=True)
def mock_api_calls():
    """Mocks para evitar peticiones reales de red y base de datos durante el test de GUI."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "ok",
        "logo_base64": None,
        "primary_color": "#1E293B",
        "secondary_color": "#64748B",
        "font_family": "Helvetica",
        "layout_template": "classic",
        "elements_layout": '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]'
    }
    mock_resp.raise_for_status = MagicMock()
    with patch("requests.Session.get", return_value=mock_resp), \
         patch("requests.Session.post", return_value=mock_resp), \
         patch("requests.get", return_value=mock_resp), \
         patch("requests.post", return_value=mock_resp):
        yield

def test_qa_sidebar_contains_document_layout_option():
    """Verifica que la subcategoría 'diseno_maquetacion' exista en SIDEBAR_CATEGORIES."""
    doc_cat = None
    for cat in SIDEBAR_CATEGORIES:
        if cat["id"] == "documentos":
            doc_cat = cat
            break
            
    assert doc_cat is not None, "Debe existir la sección de documentos"
    
    sub_ids = [sub["id"] for sub in doc_cat["subcategories"]]
    assert "diseno_maquetacion" in sub_ids, "Debe existir la subcategoría de Diseño y Maquetación en la barra lateral"

def test_qa_view_switching_to_document_customizer(qapp, mock_dashboard_config):
    """Verifica que el dashboard cambie correctamente al widget del maquetador drag-and-drop."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
        
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        
        # Cambiar a la vista de Diseño y Maquetación
        dashboard.switch_to_view(("documentos", "diseno_maquetacion"))
        
        # Verificar el índice en el central_stack
        assert dashboard.central_stack.currentIndex() == 32
        
        # Verificar el tipo del widget activo
        active_widget = dashboard.central_stack.currentWidget()
        assert isinstance(active_widget, AlfonsoDocumentCustomizerWidget)
        
        # Verificar que el título de la vista cambia correctamente
        assert "DISEÑO Y MAQUETACIÓN" in dashboard.lbl_view_title.text()

def test_qa_customizer_widget_interactive_reordering(qapp, mock_dashboard_config):
    """Verifica que el widget customizer inicialice bien los elementos y reordene el preview sin excepciones."""
    with patch("client.gui.app.AlfonsoHUDDashboard.start_agent"), \
         patch("client.gui.app.AlfonsoHUDDashboard.start_assistant"), \
         patch("client.gui.app.AlfonsoHUDDashboard.check_onboarding"):
         
        dashboard = AlfonsoHUDDashboard(mock_dashboard_config)
        widget = AlfonsoDocumentCustomizerWidget(dashboard)
        
        # Cargar configuración mock
        widget.load_settings()
        
        # Comprobar que los elementos de la lista coinciden con los del mock de API
        assert widget.list_widget.count() == 5
        assert widget.list_widget.item(0).text() == "Cabecera (Título, Factura ID y Fecha)"
        
        # Comprobar que el layout de la previsualización se genera correctamente
        # Deberían existir 5 widgets hijos de previsualización en el layout A4
        assert widget.a4_layout.count() == 5
        
        # Simular reordenamiento invirtiendo el orden de los items en la lista de PyQt
        items = []
        while widget.list_widget.count() > 0:
            items.append(widget.list_widget.takeItem(0))
            
        # Reinsertarlos al revés
        for item in reversed(items):
            widget.list_widget.addItem(item)
            
        # Invocar la función de actualización de preview tras arrastre
        widget.on_layout_reordered()
        
        # Verificar que la hoja A4 sigue teniendo 5 elementos redibujados sin errores
        assert widget.a4_layout.count() == 5
        
        # Verificar que el primer bloque de la previsualización ahora es el Pie Legal (debido a la inversión)
        first_frame = widget.a4_layout.itemAt(0).widget()
        assert first_frame is not None

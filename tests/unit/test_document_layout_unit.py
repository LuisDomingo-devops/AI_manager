import pytest
import sqlite3
import json
from app.domain.services.document_customization_service import DocumentCustomizationService
from app.infrastructure.database.document_customization_db import SqliteDocumentCustomizationAdapter
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def init_db():
    # Asegurar que la tabla existe y está limpia para el cliente por defecto y test-client
    for client_id in [None, "test-client"]:
        with _get_connection(client_id) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_customization (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL DEFAULT 'default',
                    logo_base64 TEXT,
                    primary_color TEXT DEFAULT '#1E293B',
                    secondary_color TEXT DEFAULT '#64748B',
                    font_family TEXT DEFAULT 'Helvetica',
                    layout_template TEXT DEFAULT 'classic',
                    elements_layout TEXT DEFAULT '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            # Si la columna elements_layout no existe (por ser base de datos de test vieja), la creamos
            try:
                conn.execute("ALTER TABLE document_customization ADD COLUMN elements_layout TEXT DEFAULT '[\"cabecera\", \"emisor_receptor\", \"detalles\", \"totales\", \"pie_verifactu\"]'")
            except sqlite3.OperationalError:
                pass
                
            conn.execute("DELETE FROM document_customization")
            conn.commit()
    yield

def test_get_customization_default_values():
    """Verifica que se retornen valores por defecto si no hay registro para el cliente."""
    adapter = SqliteDocumentCustomizationAdapter()
    service = DocumentCustomizationService(adapter)
    
    custom = service.get_customization("test-client")
    assert custom["primary_color"] == "#1E293B"
    assert custom["secondary_color"] == "#64748B"
    assert custom["font_family"] == "Helvetica"
    assert custom["layout_template"] == "classic"
    
    # Comprobar el nuevo campo de maquetación por defecto
    layout = json.loads(custom["elements_layout"])
    assert len(layout) == 5
    assert layout == ["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]

def test_save_and_retrieve_customization_with_elements_layout():
    """Verifica que se pueda guardar y recuperar la personalización completa, incluyendo el layout."""
    adapter = SqliteDocumentCustomizationAdapter()
    service = DocumentCustomizationService(adapter)
    
    test_layout = ["cabecera", "detalles", "emisor_receptor", "totales", "pie_verifactu"]
    data = {
        "logo_base64": "dummy-base64",
        "primary_color": "#FF0000",
        "secondary_color": "#00FF00",
        "font_family": "Courier",
        "layout_template": "modern",
        "elements_layout": json.dumps(test_layout)
    }
    
    service.save_customization("test-client", data)
    
    custom = service.get_customization("test-client")
    assert custom["logo_base64"] == "dummy-base64"
    assert custom["primary_color"] == "#FF0000"
    assert custom["secondary_color"] == "#00FF00"
    assert custom["font_family"] == "Courier"
    assert custom["layout_template"] == "modern"
    
    # Comprobar el campo reordenado
    layout = json.loads(custom["elements_layout"])
    assert layout == test_layout

def test_save_customization_invalid_color_validation():
    """Verifica que el servicio lance ValueError si se intenta guardar colores hexadecimales inválidos."""
    adapter = SqliteDocumentCustomizationAdapter()
    service = DocumentCustomizationService(adapter)
    
    invalid_data = {
        "logo_base64": None,
        "primary_color": "rojo",
        "secondary_color": "#64748B",
        "font_family": "Helvetica",
        "layout_template": "classic"
    }
    
    with pytest.raises(ValueError) as excinfo:
        service.save_customization("test-client", invalid_data)
    assert "primary_color debe ser un color hexadecimal válido" in str(excinfo.value)

def test_hex_to_rgb_conversion():
    """Verifica la conversión estática de color hexadecimal a tupla RGB normalizada de ReportLab."""
    service = DocumentCustomizationService(None)
    
    # Color #1E293B
    r, g, b = service.hex_to_rgb("#1E293B")
    assert pytest.approx(r, 0.01) == 0.117  # 30/255
    assert pytest.approx(g, 0.01) == 0.160  # 41/255
    assert pytest.approx(b, 0.01) == 0.231  # 59/255
    
    # Color inválido usa fallback por defecto
    r, g, b = service.hex_to_rgb("color_invalido", default=(1.0, 1.0, 1.0))
    assert r == 1.0
    assert g == 1.0
    assert b == 1.0

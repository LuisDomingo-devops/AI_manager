"""
TESTS UNITARIOS — Alfonso Sidebar Widget & Navegación Jerárquica
Verifica la estructura de datos, botones, grupos colapsables, filtrado en tiempo real y señales.
"""

import sys
import os
from pathlib import Path
import pytest

# Asegurar sys.path con root y client
root_dir = str(Path(__file__).resolve().parents[1])
client_dir = os.path.join(root_dir, "client")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if client_dir not in sys.path:
    sys.path.insert(0, client_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from client.gui.sidebar_widget import (
    SIDEBAR_CATEGORIES,
    SubcategoryButton,
    CategoryGroupWidget,
    AlfonsoSidebarWidget
)


@pytest.fixture(scope="session")
def qapp():
    """Instancia de QApplication compartida para tests de GUI en modo offscreen."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_sidebar_categories_structure_integrity():
    """Valida la integridad y exhaustividad de la estructura de categorías."""
    assert len(SIDEBAR_CATEGORIES) >= 10, "Deben existir al menos 10 categorías principales"
    
    category_ids = set()
    subcategory_ids = set()
    total_subcategories = 0

    for cat in SIDEBAR_CATEGORIES:
        assert "id" in cat and cat["id"], "Cada categoría debe tener un ID no vacío"
        assert "title" in cat and cat["title"], "Cada categoría debe tener un título"
        assert "icon" in cat, "Cada categoría debe contener la clave icon"
        assert "subcategories" in cat and isinstance(cat["subcategories"], list), "Debe contener subcategorías"
        assert len(cat["subcategories"]) >= 2, f"La categoría {cat['id']} debe tener al menos 2 subcategorías"

        assert cat["id"] not in category_ids, f"ID de categoría duplicado: {cat['id']}"
        category_ids.add(cat["id"])

        for subcat in cat["subcategories"]:
            assert "id" in subcat and subcat["id"], "Cada subcategoría debe tener un ID"
            assert "title" in subcat and subcat["title"], "Cada subcategoría debe tener un título"
            assert "icon" in subcat, "Cada subcategoría debe contener la clave icon"
            assert "desc" in subcat, "Cada subcategoría debe tener una descripción de tooltip"
            
            full_sub_key = (cat["id"], subcat["id"])
            assert full_sub_key not in subcategory_ids, f"Subcategoría duplicada: {full_sub_key}"
            subcategory_ids.add(full_sub_key)
            total_subcategories += 1

    assert total_subcategories >= 25, "El sistema debe exponer al menos 25 subcategorías especializadas"


def test_subcategory_button_unit(qapp):
    """Verifica la inicialización, tooltip y cambio de estado activo del botón de subcategoría."""
    subcat_data = {
        "id": "test_sub",
        "title": "Subcategoría Test",
        "icon": "",
        "desc": "Descripción de prueba para el tooltip"
    }
    btn = SubcategoryButton(subcat_data, "test_cat")
    assert "Subcategoría Test" in btn.text()
    assert "Descripción de prueba para el tooltip" in btn.toolTip()
    assert "Subcategoría Test" in btn.toolTip()
    assert btn.is_active is False

    btn.set_active_state(True)
    assert btn.is_active is True

    btn.set_active_state(False)
    assert btn.is_active is False


def test_category_group_widget_unit(qapp):
    """Verifica la inicialización, colapso y filtrado de CategoryGroupWidget."""
    cat_data = {
        "id": "facturacion",
        "title": "FACTURACIÓN",
        "icon": "💼",
        "badge": "Veri*Factu",
        "subcategories": [
            {"id": "facturas_emitidas", "title": "Facturas Emitidas", "icon": "📄", "desc": "Libro de ingresos"},
            {"id": "nueva_factura", "title": "Nueva Factura", "icon": "⚡", "desc": "Emisión rápida"}
        ]
    }
    group = CategoryGroupWidget(cat_data)
    group.show()
    assert group.category_id == "facturacion"
    assert len(group.buttons) == 2
    # Por defecto los desplegables deben aparecer cerrados
    assert group.is_expanded is False
    assert group.subcat_container.isHidden() is True
    assert group.lbl_chevron.text() == "▸"

    # Test despliegue
    group.set_expanded(True)
    assert group.is_expanded is True
    assert group.subcat_container.isHidden() is False
    assert group.lbl_chevron.text() == "▾"

    # Test colapso
    group.set_expanded(False)
    assert group.is_expanded is False
    assert group.subcat_container.isHidden() is True
    assert group.lbl_chevron.text() == "▸"

    # Test filtrado de items
    # 1. Búsqueda que coincide con una subcategoría
    match = group.filter_items("Emitidas")
    assert match is True
    assert group.buttons["facturas_emitidas"].isHidden() is False
    assert group.buttons["nueva_factura"].isHidden() is True

    # 2. Búsqueda que no coincide
    match_none = group.filter_items("PalabraInexistente123")
    assert match_none is False
    assert group.isHidden() is True

    # 3. Búsqueda vacía (resetea todo)
    match_empty = group.filter_items("")
    assert match_empty is True
    assert group.isHidden() is False
    assert group.buttons["facturas_emitidas"].isHidden() is False
    assert group.buttons["nueva_factura"].isHidden() is False


def test_sidebar_widget_search_and_selection(qapp):
    """Verifica el filtrado en tiempo real y la emisión de señales en AlfonsoSidebarWidget."""
    sidebar = AlfonsoSidebarWidget()
    sidebar.show()
    assert len(sidebar.groups) >= 10
    assert len(sidebar.all_buttons) >= 25

    # Captura de señales
    selected_signals = []
    sidebar.category_selected.connect(lambda c, s, t: selected_signals.append((c, s, t)))

    # Test activación programática
    sidebar.set_active("bancos", "conciliacion_bancaria")
    assert sidebar.current_cat_id == "bancos"
    assert sidebar.current_subcat_id == "conciliacion_bancaria"
    assert sidebar.all_buttons[("bancos", "conciliacion_bancaria")].is_active is True
    assert sidebar.all_buttons[("dashboard", "resumen_ejecutivo")].is_active is False

    # Test click en subcategoría emite señal
    sidebar.groups["bancos"].subcategory_clicked.emit("bancos", "conexiones_psd2", "Cuentas Conectadas")
    assert len(selected_signals) == 1
    assert selected_signals[0] == ("bancos", "conexiones_psd2", "Cuentas Conectadas")
    assert sidebar.current_subcat_id == "conexiones_psd2"

    # Test filtrado con búsqueda
    sidebar.search_input.setText("Nóminas")
    assert sidebar.btn_clear_search.isHidden() is False
    assert sidebar.groups["laboral"].isHidden() is False

    # Test limpieza de búsqueda
    sidebar.btn_clear_search.click()
    assert sidebar.search_input.text() == ""
    assert sidebar.btn_clear_search.isHidden() is True

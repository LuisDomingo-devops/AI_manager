"""
SUITE DE TESTS UNITARIOS — Consistencia Visual, Widgets y Modos GUI de Alfonso Autónomo
Verifica individualmente el comportamiento de AlfonsoAIChatAssistantWidget, AlfonsoPayrollWidget,
QuarterlyBarChartWidget, DonutChartWidget y AlfonsoBaseDialog.
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

from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from PyQt6.QtCore import Qt

from client.gui.dialogs.specialized_views import (
    AlfonsoAIChatAssistantWidget,
    AlfonsoPayrollWidget,
    AlfonsoCashFlowWidget,
    AlfonsoInvoiceEmitterWidget,
    AlfonsoVerifactuAuditWidget,
    AlfonsoHelpCenterWidget
)
from client.gui.app import QuarterlyBarChartWidget
from client.gui.widgets import DonutChartWidget, SparklineWidget
from client.gui.dialogs.base import AlfonsoBaseDialog, AlfonsoComplianceDialog


@pytest.fixture(scope="session")
def qapp():
    """Instancia de QApplication compartida para tests unitarios GUI."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_ai_chat_assistant_widget_unit(qapp):
    """Verifica la inicialización, tarjetas y despacho de órdenes de AlfonsoAIChatAssistantWidget."""
    parent_widget = QWidget()
    parent_widget.text_input = MagicMock()
    parent_widget.send_text_message = MagicMock()

    widget = AlfonsoAIChatAssistantWidget(parent=parent_widget, embedded=True)
    widget.show()

    assert widget.windowTitle() == "ASISTENTE IA & VOZ ALFONSO"
    assert widget.findChild(QLabel) is not None

    # Simular despacho de acción rápida al chat
    widget.dispatch_prompt_to_chat("Emite una factura")
    parent_widget.text_input.setPlainText.assert_called_with("Emite una factura")
    parent_widget.send_text_message.assert_called_once()


def test_payroll_widget_modes_unit(qapp):
    """Verifica la conmutación entre los 3 modos de AlfonsoPayrollWidget (empleados, nóminas, tgss)."""
    payroll = AlfonsoPayrollWidget(embedded=True)
    payroll.show()

    # 1. Modo por defecto: Empleados
    assert payroll.mode == "employees"
    assert "Plantilla" in payroll.lbl_title.text() or "Contratos" in payroll.lbl_title.text()
    assert payroll.tbl_employees.columnCount() == 6

    # 2. Modo Nóminas
    payroll.set_mode("payrolls")
    assert payroll.mode == "payrolls"
    assert "Nóminas" in payroll.lbl_title.text()
    assert payroll.sim_frame.isVisible() is True

    # 3. Modo TGSS
    payroll.set_mode("tgss")
    assert payroll.mode == "tgss"
    assert "TGSS" in payroll.lbl_title.text()
    assert payroll.sim_frame.isVisible() is False


def test_quarterly_bar_chart_widget_unit(qapp):
    """Verifica el cálculo de proporciones, altura ampliada y etiquetas en QuarterlyBarChartWidget."""
    chart = QuarterlyBarChartWidget()
    chart.show()
    assert chart.minimumHeight() >= 300, "QuarterlyBarChartWidget debe tener altura ampliada >= 300"

    chart.update_data(10000.0, 5000.0)
    assert "10.000,00 €" in chart.lbl_ing_val.text() or "10,000.00 €" in chart.lbl_ing_val.text()
    assert "5.000,00 €" in chart.lbl_gast_val.text() or "5,000.00 €" in chart.lbl_gast_val.text()
    assert chart.bar_ing.value() == 100
    assert chart.bar_gast.value() == 50

    # Caso borde: Cero ingresos y gastos
    chart.update_data(0.0, 0.0)
    assert chart.bar_ing.value() == 0
    assert chart.bar_gast.value() == 0


def test_donut_chart_widget_unit(qapp):
    """Verifica los cálculos porcentuales y dimensiones proporcionadas en DonutChartWidget."""
    donut = DonutChartWidget()
    donut.show()
    assert donut.height() == 140 and donut.width() == 140, "DonutChartWidget debe mantener un tamaño limpio de 140x140 px"

    donut.set_values(total=20, pagadas=10, pendientes=8, rechazadas=2)
    assert donut.total == 20
    assert donut.pagadas == 10
    assert donut.pendientes == 8
    assert donut.rechazadas == 2

    # Caso borde: total 0
    donut.set_values(total=0, pagadas=0, pendientes=0, rechazadas=0)
    assert donut.total == 0


def test_base_dialog_embedded_mode_unit(qapp):
    """Verifica que AlfonsoBaseDialog oculta barra de título y controles al estar embebido."""
    diag_embedded = AlfonsoBaseDialog(title="TEST EMBEDDED", embedded=True)
    diag_embedded.show()
    assert diag_embedded.title_bar.isHidden() is True
    assert diag_embedded.btn_minimize.isHidden() is True
    assert diag_embedded.btn_close.isHidden() is True

    diag_window = AlfonsoBaseDialog(title="TEST WINDOW", embedded=False)
    diag_window.show()
    assert diag_window.title_bar.isVisible() is True


def test_table_widget_visual_styling_unit(qapp):
    """Verifica que las tablas heredan estilos oscuros con cabeceras cian y filas alternas."""
    from client.gui.dialogs.widgets import AlfonsoLedgerDialog, AlfonsoBankReconciliationDialog
    
    # 1. Verificar stylesheet en AlfonsoBaseDialog embedded
    diag_embedded = AlfonsoBaseDialog(title="TEST TABLE STYLES", embedded=True)
    sheet = diag_embedded.styleSheet()
    assert "QTableWidget" in sheet
    assert "#0B111E" in sheet or "#0F172A" in sheet
    assert "#00F0FF" in sheet

    # 2. Verificar alternancia de filas en Specialized Views
    cf = AlfonsoCashFlowWidget(embedded=True)
    assert cf.tbl_inflows.alternatingRowColors() is True
    assert cf.tbl_outflows.alternatingRowColors() is True

    payroll = AlfonsoPayrollWidget(embedded=True)
    assert payroll.tbl_employees.alternatingRowColors() is True

    audit = AlfonsoVerifactuAuditWidget(embedded=True)
    assert audit.tbl_hashes.alternatingRowColors() is True

    # 3. Verificar alternancia en Diálogos de Contabilidad y Bancos
    ledger = AlfonsoLedgerDialog(embedded=True)
    assert ledger.table.alternatingRowColors() is True
    assert ledger.table_mayor.alternatingRowColors() is True

    bank = AlfonsoBankReconciliationDialog(embedded=True)
    assert bank.table.alternatingRowColors() is True


def test_ledger_dialog_mayor_and_diario_synchronization_unit(qapp):
    """Verifica que AlfonsoLedgerDialog puebla el Mayor con cuentas activas y permite navegación interactiva."""
    from client.gui.dialogs.widgets import AlfonsoLedgerDialog

    ledger = AlfonsoLedgerDialog(embedded=True)
    ledger.show()

    # 1. El combobox del Mayor contiene cuentas con recuento de apuntes
    assert ledger.cmb_mayor_account.count() > 0
    first_text = ledger.cmb_mayor_account.itemText(0)
    assert "apuntes" in first_text

    # 2. Conmutar a la vista Mayor y comprobar que se carga la cuenta activa por defecto
    ledger.switch_view(1)
    assert ledger.main_stack.currentIndex() == 1
    assert ledger.table_mayor.rowCount() > 0
    assert "Total Debe:" in ledger.lbl_mayor_total_debe.text()

    # 3. Salto interactivo jump_to_mayor a una cuenta específica activa (ej: 70500000 o la primera cuenta)
    target_code = "70500000" if ledger.cmb_mayor_account.findData("70500000") >= 0 else ledger.cmb_mayor_account.itemData(0)
    ledger.jump_to_mayor(target_code)
    assert ledger.main_stack.currentIndex() == 1
    assert ledger.cmb_mayor_account.currentData() == target_code
    assert ledger.table_mayor.rowCount() > 0

    # 4. Doble clic simulado en celda de Diario
    ledger.switch_view(0)
    if ledger.table.rowCount() > 0:
        ledger.on_diario_cell_double_clicked(0, 2)
        assert ledger.main_stack.currentIndex() == 1


def test_help_center_widget_unit(qapp):
    """Verifica que AlfonsoHelpCenterWidget carga el manual, permite filtrar por texto y alternar pestañas."""
    hc = AlfonsoHelpCenterWidget(embedded=True)
    hc.show()

    # 1. Comprobar que contiene 4 pestañas y el texto del manual
    assert hc.tab_stack.count() == 4
    assert len(hc.manual_full_text) > 0
    assert "LIBRO DE INSTRUCCIONES" in hc.manual_full_text or "Manual de Operativa" in hc.manual_full_text

    # 2. Filtrado interactivo en el manual
    hc.filter_manual("verifactu")
    assert "Resultados de búsqueda" in hc.browser_manual.toHtml() or "verifactu" in hc.browser_manual.toHtml().lower()

    # Limpiar filtro
    hc.filter_manual("")
    assert len(hc.browser_manual.toHtml()) > 100

    # 3. Selector de capítulos
    hc.cb_chapters.setCurrentIndex(3) # 3. Facturación & Ventas
    assert len(hc.browser_manual.toHtml()) > 50

    # 4. Alternancia de pestañas: FAQ, Glosario, Atajos
    hc.switch_tab(1)
    assert hc.tab_stack.currentIndex() == 1
    assert len(hc.faq_cards) >= 5

    # Filtrar FAQ
    hc.filter_faq("suministros")
    # Al menos una tarjeta debe seguir visible
    visible_cards = [card for _, card in hc.faq_cards if not card.isHidden()]
    assert len(visible_cards) >= 1

    hc.switch_tab(2)
    assert hc.tab_stack.currentIndex() == 2

    hc.switch_tab(3)
    assert hc.tab_stack.currentIndex() == 3


def test_dashboard_recent_movements_and_quick_access_headers_unit(qapp):
    """Verifica que las cabeceras de columnas y títulos de la sección inferior ajustan su tamaño al texto."""
    from PyQt6.QtWidgets import QHeaderView
    from client.gui.app import AlfonsoHUDDashboard

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

        # 1. Comprobar tabla de últimos movimientos y modos de redimensionado de cabeceras
        tbl = app_gui.tbl_recent_invoices
        assert tbl is not None
        assert tbl.columnCount() == 4
        
        header = tbl.horizontalHeader()
        assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.ResizeToContents, "Fecha debe ajustarse a su contenido"
        assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch, "Concepto/Cliente debe estirarse para aprovechar el espacio"
        assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.ResizeToContents, "Tipo debe ajustarse a su contenido"
        assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.ResizeToContents, "Importe debe ajustarse a su contenido"

        # 2. Comprobar que los títulos de cabecera de las columnas no están vacíos y tienen etiquetas correctas
        headers = [tbl.horizontalHeaderItem(i).text() for i in range(4)]
        assert headers == ["Fecha", "Concepto / Cliente", "Tipo", "Importe"]


def test_professional_icons_and_quick_access_buttons_unit(qapp):
    """Verifica la generación de iconos vectoriales profesionales sin emoticonos y que los botones de accesos rápidos sean cuadrados."""
    from client.gui.widgets import create_professional_icon
    from client.gui.app import AlfonsoHUDDashboard
    from PyQt6.QtGui import QIcon

    for icon_type, color in [("invoice", "#00F0FF"), ("bank", "#10B981"), ("tax", "#6366F1"), ("archive", "#F59E0B"), ("help", "#00F0FF")]:
        icon = create_professional_icon(icon_type, color, 36)
        assert isinstance(icon, QIcon)
        assert not icon.isNull(), f"El icono {icon_type} debe ser válido y no nulo"

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

        # Buscar los botones dentro del dashboard y comprobar que sus dimensiones fijas son cuadradas (ancho == alto, 70x70)
        from PyQt6.QtWidgets import QPushButton
        buttons = app_gui.findChildren(QPushButton)
        square_buttons = [b for b in buttons if b.maximumWidth() == b.maximumHeight() and b.maximumWidth() == 70]
        assert len(square_buttons) == 5, f"Deben encontrarse los 5 botones cuadrados en accesos rápidos, encontrados: {len(square_buttons)}"
        for b in square_buttons:
            assert b.width() == b.height() or b.maximumWidth() == b.maximumHeight()
            assert not b.icon().isNull(), "Cada botón cuadrado debe tener un icono válido"
            assert len(b.toolTip()) > 0, "Cada botón cuadrado debe poseer un tooltip explicativo"


def test_subscription_dialog_and_plan_cards_unit(qapp):
    """Verifica que AlfonsoSubscriptionDialog renderiza las 3 tarjetas de planes con sus precios, características y cambio interactivo."""
    from client.gui.dialogs.widgets import AlfonsoSubscriptionDialog
    from app.domain.services.bank_service import BankService

    # Forzar un tier inicial para test
    BankService.update_subscription_tier("premium_10") # equivale a basic

    dialog = AlfonsoSubscriptionDialog(embedded=True)
    dialog.show()

    # 1. Comprobar que existen las 3 tarjetas de planes
    assert len(dialog.cards) == 3
    assert "basic" in dialog.cards
    assert "pro" in dialog.cards
    assert "advisor" in dialog.cards

    # 2. Comprobar datos de cada tarjeta
    card_basic = dialog.cards["basic"]
    card_pro = dialog.cards["pro"]
    card_advisor = dialog.cards["advisor"]

    assert card_pro["is_popular"] is True
    assert card_basic["is_popular"] is False
    assert card_advisor["is_popular"] is False

    # 3. Comprobar estado de botones según el tier inicial
    assert card_basic["button"].text() == "PLAN ACTUAL"
    assert card_basic["button"].isEnabled() is False

    assert card_pro["button"].text() == "CONTRATAR PRO"
    assert card_pro["button"].isEnabled() is True

    assert card_advisor["button"].text() == "SELECCIONAR ASESORÍA"
    assert card_advisor["button"].isEnabled() is True

    # 4. Probar selección interactiva de Plan Pro
    with patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info:
        dialog.select_plan("pro")
        assert card_pro["button"].text() == "PLAN ACTUAL"
        assert card_pro["button"].isEnabled() is False
        assert card_basic["button"].isEnabled() is True
        assert card_basic["button"].text() == "SELECCIONAR BASIC"
        assert mock_info.called

    # 5. Probar selección interactiva de Plan Advisor
    with patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info:
        dialog.select_plan("advisor")
        assert card_advisor["button"].text() == "PLAN ACTUAL"
        assert card_advisor["button"].isEnabled() is False
        assert card_pro["button"].isEnabled() is True
        assert card_pro["button"].text() == "CONTRATAR PRO"
        assert mock_info.called

    # 6. Probar conmutador de facturación anual / mensual
    dialog.set_billing_period(False)
    assert dialog.is_annual_billing is False
    assert "19 €" in dialog.cards["basic"]["price_label"].text()
    assert "39 €" in dialog.cards["pro"]["price_label"].text()
    assert "79 €" in dialog.cards["advisor"]["price_label"].text()

    dialog.set_billing_period(True)
    assert dialog.is_annual_billing is True
    assert "15 €" in dialog.cards["basic"]["price_label"].text()
    assert "32 €" in dialog.cards["pro"]["price_label"].text()
    assert "65 €" in dialog.cards["advisor"]["price_label"].text()










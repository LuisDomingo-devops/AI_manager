"""
panels/dashboard_panel.py -- Panel central del dashboard de Alfonso.
Sin setStyleSheet() inline: hereda todo del GLOBAL_QSS de theme.py.
Las tarjetas KPI usan setProperty("class", "KPICard"),
los paneles de graficos usan setProperty("class", "ChartPanel"),
las alertas usan setProperty("class", "AlertBtnCyan/Success/Warning").
"""
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QSizePolicy, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from client.gui.theme import AlfonsoStyledWidget, HoverAnimationFilter
from client.gui.widgets import QuarterlyBarChartWidget, DonutChartWidget, SparklineWidget


class KPICard(QFrame, AlfonsoStyledWidget):
    """
    Tarjeta KPI reutilizable.
    Aplica la clase QSS "KPICard" al crearse.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_qss_class("KPICard")
        HoverAnimationFilter(self)


class ChartPanel(QFrame, AlfonsoStyledWidget):
    """
    Panel de grafico (donut, barras, alertas).
    Aplica la clase QSS "ChartPanel" al crearse.
    """
    def __init__(self, parent=None, min_height=0):
        super().__init__(parent)
        self.apply_qss_class("ChartPanel")
        HoverAnimationFilter(self)
        if min_height:
            self.setMinimumHeight(min_height)


class AlfonsoDashboardPanel(QWidget, AlfonsoStyledWidget):
    """
    Panel central del dashboard con:
      - Saludo personalizado
      - 4 tarjetas KPI (Ingresos, Gastos, Beneficio, IVA)
      - Grafico donut de facturas del mes
      - Rendimiento trimestral (barras)
      - Ultimos movimientos (tabla)
      - Alertas AEAT y avisos
      - Accesos rapidos

    Ningun widget llama a setStyleSheet(); todo hereda del GLOBAL_QSS.
    """

    # Senal para abrir un modulo desde los accesos rapidos
    quick_access_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # ---------------------------------------------------------------
        # 1. Saludo
        # ---------------------------------------------------------------
        greeting_row = QHBoxLayout()
        greeting_col = QVBoxLayout()

        self.lbl_greeting = QLabel("Buenos dias, Luis")
        self.lbl_greeting.setProperty("class", "LblTitle")

        self.lbl_subgreeting = QLabel("Resumen de actividad y estado financiero actual.")
        self.lbl_subgreeting.setProperty("class", "LblSubtitle")

        greeting_col.addWidget(self.lbl_greeting)
        greeting_col.addWidget(self.lbl_subgreeting)
        greeting_row.addLayout(greeting_col)
        greeting_row.addStretch()
        layout.addLayout(greeting_row)

        # ---------------------------------------------------------------
        # 2. Fila de tarjetas KPI
        # ---------------------------------------------------------------
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        # Tarjeta Ingresos
        card1 = KPICard()
        c1_lay = QVBoxLayout(card1)
        c1_lay.setContentsMargins(14, 10, 14, 0)
        self.lbl_kpi_ingresos_title = QLabel("Ingresos")
        self.lbl_kpi_ingresos_title.setProperty("class", "LblKpiTitle")
        self.lbl_kpi_ingresos = QLabel("0,00 €")
        self.lbl_kpi_ingresos.setProperty("class", "LblKpiValue")
        self.c1_spark = SparklineWidget("#00F0FF", [0]*9)
        c1_lay.addWidget(self.lbl_kpi_ingresos_title)
        c1_lay.addWidget(self.lbl_kpi_ingresos)
        c1_lay.addWidget(self.c1_spark)
        kpi_row.addWidget(card1)

        # Tarjeta Gastos
        card2 = KPICard()
        c2_lay = QVBoxLayout(card2)
        c2_lay.setContentsMargins(14, 10, 14, 0)
        self.lbl_kpi_gastos_title = QLabel("Gastos")
        self.lbl_kpi_gastos_title.setProperty("class", "LblKpiTitle")
        self.lbl_kpi_gastos = QLabel("0,00 €")
        self.lbl_kpi_gastos.setProperty("class", "LblKpiValue")
        self.c2_spark = SparklineWidget("#F59E0B", [0]*9)
        c2_lay.addWidget(self.lbl_kpi_gastos_title)
        c2_lay.addWidget(self.lbl_kpi_gastos)
        c2_lay.addWidget(self.c2_spark)
        kpi_row.addWidget(card2)

        # Tarjeta Beneficio Neto
        card3 = KPICard()
        c3_lay = QVBoxLayout(card3)
        c3_lay.setContentsMargins(14, 10, 14, 0)
        self.lbl_kpi_beneficio_title = QLabel("Beneficio Neto")
        self.lbl_kpi_beneficio_title.setProperty("class", "LblKpiTitle")
        self.lbl_kpi_beneficio = QLabel("0,00 €")
        self.lbl_kpi_beneficio.setProperty("class", "LblKpiValue")
        self.c3_spark = SparklineWidget("#10B981", [0]*9)
        c3_lay.addWidget(self.lbl_kpi_beneficio_title)
        c3_lay.addWidget(self.lbl_kpi_beneficio)
        c3_lay.addWidget(self.c3_spark)
        kpi_row.addWidget(card3)

        # Tarjeta IVA Soportado
        card4 = KPICard()
        c4_lay = QVBoxLayout(card4)
        c4_lay.setContentsMargins(14, 10, 14, 0)
        self.lbl_kpi_iva_title = QLabel("IVA Soportado")
        self.lbl_kpi_iva_title.setProperty("class", "LblKpiTitle")
        self.lbl_kpi_iva = QLabel("0,00 €")
        self.lbl_kpi_iva.setProperty("class", "LblKpiValue")
        self.c4_spark = SparklineWidget("#8B5CF6", [0]*9, is_bar=True)
        c4_lay.addWidget(self.lbl_kpi_iva_title)
        c4_lay.addWidget(self.lbl_kpi_iva)
        c4_lay.addWidget(self.c4_spark)
        kpi_row.addWidget(card4)

        layout.addLayout(kpi_row)

        # ---------------------------------------------------------------
        # 3. Fila central: donut + trimestral + alertas
        # ---------------------------------------------------------------
        middle_row = QHBoxLayout()
        middle_row.setSpacing(12)

        # -- Columna izquierda: Donut de facturas --
        donut_panel = ChartPanel(min_height=300)
        dp_lay = QVBoxLayout(donut_panel)
        dp_lay.setContentsMargins(16, 16, 16, 16)
        dp_lay.setSpacing(10)

        dp_title = QLabel("Facturas del Mes")
        dp_title.setProperty("class", "LblPanelTitle")
        dp_lay.addWidget(dp_title)

        self.donut_chart = DonutChartWidget()
        self.donut_chart.setFixedHeight(140)
        dp_lay.addWidget(self.donut_chart)

        # Leyenda del donut
        for attr, text, color in [
            ("leg1", "Pagadas (0)",    "#10B981"),
            ("leg2", "Pendientes (0)", "#F59E0B"),
            ("leg3", "Rechazadas (0)", "#EF4444"),
        ]:
            lbl = QLabel(f"● {text}")
            # NOTE: color dinamico justificado: cada elemento de leyenda
            # tiene un color semantico fijo que identifica su categoria.
            lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
            dp_lay.addWidget(lbl)
            setattr(self, attr, lbl)

        dp_lay.addStretch()
        middle_row.addWidget(donut_panel, 1)

        # -- Columna central: Rendimiento trimestral --
        bar_panel = ChartPanel(min_height=300)
        bp_lay = QVBoxLayout(bar_panel)
        bp_lay.setContentsMargins(16, 16, 16, 16)
        bp_lay.setSpacing(10)

        bp_title = QLabel("Rendimiento Trimestral")
        bp_title.setProperty("class", "LblPanelTitle")
        bp_lay.addWidget(bp_title)

        self.bar_chart = QuarterlyBarChartWidget()
        bp_lay.addWidget(self.bar_chart, 1)
        middle_row.addWidget(bar_panel, 2)

        # -- Columna derecha: Alertas y avisos --
        alert_panel = ChartPanel(min_height=300)
        ap_lay = QVBoxLayout(alert_panel)
        ap_lay.setContentsMargins(16, 16, 16, 16)
        ap_lay.setSpacing(8)

        ap_title = QLabel("Alertas y Avisos")
        ap_title.setProperty("class", "LblPanelTitle")
        ap_lay.addWidget(ap_title)

        self.alert_aeat = QPushButton("Modelo 303 - cargando...")
        self.alert_aeat.setProperty("class", "AlertBtnWarning")

        self.alert_reconcile = QPushButton("Calculando conciliacion...")
        self.alert_reconcile.setProperty("class", "AlertBtnCyan")

        ap_lay.addWidget(self.alert_aeat)
        ap_lay.addWidget(self.alert_reconcile)
        ap_lay.addStretch()
        middle_row.addWidget(alert_panel, 1)

        layout.addLayout(middle_row)

        # ---------------------------------------------------------------
        # 4. Fila inferior: tabla de movimientos + accesos rapidos
        # ---------------------------------------------------------------
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        # -- Tabla de ultimos movimientos --
        table_panel = ChartPanel()
        tp_lay = QVBoxLayout(table_panel)
        tp_lay.setContentsMargins(16, 16, 16, 16)
        tp_lay.setSpacing(10)

        tp_title = QLabel("Ultimos Movimientos")
        tp_title.setProperty("class", "LblPanelTitle")
        tp_lay.addWidget(tp_title)

        self.tbl_recent_invoices = QTableWidget(0, 4)
        self.tbl_recent_invoices.setHorizontalHeaderLabels(["Fecha", "Concepto", "Estado", "Importe"])
        self.tbl_recent_invoices.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_recent_invoices.verticalHeader().setVisible(False)
        self.tbl_recent_invoices.setAlternatingRowColors(True)
        self.tbl_recent_invoices.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_recent_invoices.setFixedHeight(130)
        tp_lay.addWidget(self.tbl_recent_invoices)
        bottom_row.addWidget(table_panel, 2)

        # -- Accesos rapidos --
        quick_panel = ChartPanel()
        qp_lay = QVBoxLayout(quick_panel)
        qp_lay.setContentsMargins(16, 16, 16, 16)
        qp_lay.setSpacing(8)

        qp_title = QLabel("Accesos Rapidos")
        qp_title.setProperty("class", "LblPanelTitle")
        qp_lay.addWidget(qp_title)

        quick_buttons = [
            ("Registro de Gastos",   "QuickBtnCyan",   "gastos"),
            ("Nueva Factura",        "QuickBtnGreen",  "facturas"),
            ("Calendario Fiscal",    "QuickBtnIndigo", "calendario"),
            ("Informe Trimestral",   "QuickBtnAmber",  "informes"),
        ]
        for label, css_class, key in quick_buttons:
            btn = QPushButton(label)
            btn.setProperty("class", css_class)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda _, k=key: self.quick_access_requested.emit(k))
            qp_lay.addWidget(btn)

        bottom_row.addWidget(quick_panel, 1)
        layout.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # API publica: actualizar metricas
    # ------------------------------------------------------------------
    def update_metrics(self, data: dict):
        """
        Actualiza todos los valores del dashboard con los datos calculados
        por main_window. Ningun widget aqui llama a setStyleSheet();
        los colores semanticos de leyenda son la unica excepcion justificada.
        """
        fmt = lambda v: f"{v:,.2f} \u20ac".replace(",", "X").replace(".", ",").replace("X", ".")

        # KPIs
        self.lbl_kpi_ingresos.setText(fmt(data.get("ingresos", 0)))
        self.lbl_kpi_gastos.setText(fmt(data.get("gastos", 0)))
        self.lbl_kpi_beneficio.setText(fmt(data.get("beneficio", 0)))
        self.lbl_kpi_iva.setText(fmt(data.get("iva_soportado", 0)))

        self.lbl_kpi_ingresos_title.setText(data.get("title_ingresos", "Ingresos"))
        self.lbl_kpi_gastos_title.setText(data.get("title_gastos", "Gastos"))
        self.lbl_kpi_beneficio_title.setText(data.get("title_beneficio", "Beneficio Neto"))
        self.lbl_kpi_iva_title.setText(data.get("title_iva", "IVA Soportado"))

        # Sparklines
        self.c1_spark.set_points(data.get("monthly_incomes", [0]*12)[-9:])
        self.c2_spark.set_points(data.get("monthly_expenses", [0]*12)[-9:])
        profits = [i - g for i, g in zip(
            data.get("monthly_incomes", [0]*12),
            data.get("monthly_expenses", [0]*12)
        )]
        self.c3_spark.set_points(profits[-9:])
        self.c4_spark.set_points(data.get("monthly_iva", [0]*12)[-9:])

        # Donut
        total = data.get("total_facturas", 0)
        pagadas = data.get("pagadas", 0)
        pendientes = data.get("pendientes", 0)
        rechazadas = data.get("rechazadas", 0)
        self.donut_chart.set_values(total, pagadas, pendientes, rechazadas)
        self.donut_chart.update()
        self.leg1.setText(f"\u25cf Pagadas ({pagadas})")
        self.leg2.setText(f"\u25cf Pendientes ({pendientes})")
        self.leg3.setText(f"\u25cf Rechazadas ({rechazadas})")

        # Barchart trimestral
        self.bar_chart.update_data(
            data.get("ingresos_trim", [0, 0, 0]),
            data.get("gastos_trim", [0, 0, 0])
        )
        self.bar_chart.update()

        # Alertas AEAT
        if "alert_aeat_text" in data:
            self.alert_aeat.setText(data["alert_aeat_text"])

        # Alerta de conciliacion: clase QSS cambia segun estado
        # (unico uso dinamico de setProperty justificado: estado calculado en runtime)
        unreconciled = data.get("unreconciled_count", 0)
        if unreconciled > 0:
            self.alert_reconcile.setText(f"{unreconciled} movimientos bancarios sin conciliar")
            self.alert_reconcile.setProperty("class", "AlertBtnCyan")
        else:
            self.alert_reconcile.setText("Cuentas bancarias totalmente conciliadas")
            self.alert_reconcile.setProperty("class", "AlertBtnSuccess")
        self.alert_reconcile.style().unpolish(self.alert_reconcile)
        self.alert_reconcile.style().polish(self.alert_reconcile)

        # Tabla de movimientos recientes
        recent = data.get("recent_invoices", [])
        recent.sort(key=lambda x: x[0], reverse=True)
        self.tbl_recent_invoices.setRowCount(min(4, len(recent)))
        for row_i, row in enumerate(recent[:4]):
            for col_i, text in enumerate(row):
                item = QTableWidgetItem(text)
                if col_i == 3:
                    if text.startswith("+"):
                        item.setForeground(QColor("#10B981"))
                    else:
                        item.setForeground(QColor("#EF4444"))
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.tbl_recent_invoices.setItem(row_i, col_i, item)

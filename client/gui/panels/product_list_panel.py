"""
panels/product_list_panel.py
Panel dinámico de Productos & Servicios.

Muestra el catálogo de productos usando la API REST, con métricas de ventas.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QFrame, QSizePolicy, QAbstractItemView,
    QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont


# ---------------------------------------------------------------------------
# Worker – carga datos en background para no bloquear la UI
# ---------------------------------------------------------------------------
class _ProductDataWorker(QThread):
    data_ready = pyqtSignal(list)
    error      = pyqtSignal(str)
    
    def __init__(self, api_client, filter_type=None):
        super().__init__()
        self.api = api_client
        self.filter_type = filter_type

    def run(self):
        try:
            if not self.api:
                self.error.emit("API Client no disponible")
                return
            
            res = self.api.get_products()
            if res.get("status") == "ok":
                products = res.get("products", [])
                if self.filter_type:
                    products = [p for p in products if p.get("item_type", "product") == self.filter_type]
                self.data_ready.emit(products)
            else:
                self.error.emit(res.get("message", "Error desconocido de API"))
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Panel principal
# ---------------------------------------------------------------------------
class AlfonsoProductListPanel(QWidget):
    """Panel dinámico que muestra el catálogo de productos con métricas de ventas."""

    def __init__(self, parent=None, filter_type="product"):
        super().__init__(parent)
        self.filter_type = filter_type
        self._worker: _ProductDataWorker | None = None
        self.setup_ui()
        # No llamamos a load_data aquí porque la API podría no estar lista todavía.
        # Se llamará cuando se muestre el panel o externamente.

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Cabecera ──────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("📦  PRODUCTOS & SERVICIOS")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #E2E8F0; letter-spacing: 0.5px;"
        )
        header.addWidget(title)
        header.addStretch()

        self.lbl_status = QLabel("Listo")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #64748B;")
        header.addWidget(self.lbl_status)
        
        btn_refresh = QPushButton("↻  Actualizar")
        btn_refresh.setFixedHeight(28)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background: rgba(99,102,241,0.18);
                border: 1px solid rgba(99,102,241,0.5);
                border-radius: 6px;
                color: #818CF8;
                font-size: 12px;
                font-weight: bold;
                padding: 0 12px;
            }
            QPushButton:hover { background: rgba(99,102,241,0.30); }
        """)
        btn_refresh.clicked.connect(self.load_data)
        header.addWidget(btn_refresh)
        root.addLayout(header)

        # ── Separador ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(99,102,241,0.2);")
        root.addWidget(sep)

        # ── Tabla de productos ────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "SKU", "Nombre", "Descripción",
            "Precio (€)", "IVA (%)", "Stock",
            "Uds. vendidas", "Ingresos (€)", "Acciones"
        ])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setStyleSheet("""
            QTableWidget {
                background: rgba(15,23,42,0.6);
                alternate-background-color: rgba(30,41,59,0.5);
                border: 1px solid rgba(99,102,241,0.2);
                border-radius: 8px;
                color: #CBD5E1;
                font-size: 12px;
                gridline-color: transparent;
                selection-background-color: rgba(99,102,241,0.25);
            }
            QHeaderView::section {
                background: rgba(30,27,75,0.8);
                color: #818CF8;
                font-weight: bold;
                font-size: 11px;
                border: none;
                padding: 6px 8px;
            }
        """)
        root.addWidget(self.table)
        
        if self.filter_type == "service":
            self.table.setColumnHidden(5, True)

        # ── Pie de página ─────────────────────────────────────────────
        self.lbl_footer = QLabel("")
        self.lbl_footer.setStyleSheet("font-size: 10px; color: #475569;")
        root.addWidget(self.lbl_footer)

    def _get_api(self):
        p = self.parent()
        while p:
            if hasattr(p, 'api'):
                return p.api
            p = p.parent()
        return None

    def _open_new_product_form(self):
        p = self.parent()
        while p:
            if hasattr(p, 'content_stack') and hasattr(p, 'view_product_form'):
                p.view_product_form.clear_form()
                p.content_stack.setCurrentWidget(p.view_product_form)
                break
            p = p.parent()

    def _edit_product(self, product_data):
        p = self.parent()
        while p:
            if hasattr(p, 'content_stack') and hasattr(p, 'view_product_form'):
                p.view_product_form.load_for_edit(product_data)
                p.content_stack.setCurrentWidget(p.view_product_form)
                break
            p = p.parent()
            
    def _delete_product(self, sku: str):
        reply = QMessageBox.question(self, 'Confirmar Borrado',
                                     f'¿Estás seguro de que deseas desactivar el producto {sku}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            api = self._get_api()
            if api:
                res = api.delete_product(sku, confirmed=True)
                if res.get("status") == "ok":
                    QMessageBox.information(self, "Eliminado", res.get("message"))
                    self.load_data()
                else:
                    QMessageBox.critical(self, "Error", res.get("message"))

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def load_data(self):
        if self._worker and self._worker.isRunning():
            return
        
        api = self._get_api()
        if not api:
            self.lbl_status.setText("API no lista aún...")
            return

        self.lbl_status.setText("Cargando…")
        self._worker = _ProductDataWorker(api, filter_type=self.filter_type)
        self._worker.data_ready.connect(self._populate_table)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_error(self, msg: str):
        self.lbl_status.setText(f"Error: {msg}")

    def _populate_table(self, products: list):
        self.table.setRowCount(0)

        total_revenue = 0.0
        for p in products:
            row = self.table.rowCount()
            self.table.insertRow(row)

            def cell(val, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(align)
                return item

            RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

            self.table.setItem(row, 0, cell(p.get("sku") or "—"))
            
            item_type = p.get("item_type", "product")
            icon = "🛠️ " if item_type == "service" else "📦 "
            self.table.setItem(row, 1, cell(icon + (p.get("name") or "—")))

            self.table.setItem(row, 2, cell(p.get("description") or "—"))

            price_item = cell(f"{float(p.get('price') or 0):,.2f}", RIGHT)
            self.table.setItem(row, 3, price_item)

            iva_item = cell(f"{float(p.get('iva_rate') or 21):g} %", RIGHT)
            self.table.setItem(row, 4, iva_item)

            if item_type == "service":
                stock_item = cell("—", RIGHT)
                stock_item.setForeground(QBrush(QColor("#94A3B8"))) # Slate 400
            else:
                stock = int(p.get("stock") or 0)
                stock_item = cell(str(stock), RIGHT)
                if stock == 0:
                    stock_item.setForeground(QBrush(QColor("#EF4444"))) # Rojo
                elif stock < 5:
                    stock_item.setForeground(QBrush(QColor("#F59E0B"))) # Naranja
                else:
                    stock_item.setForeground(QBrush(QColor("#10B981"))) # Verde
            self.table.setItem(row, 5, stock_item)

            sold = int(p.get("sold_units") or 0)
            sold_item = cell(str(sold), RIGHT)
            if sold > 0:
                sold_item.setForeground(QBrush(QColor("#10B981")))
            self.table.setItem(row, 6, sold_item)

            rev = float(p.get("revenue") or 0)
            rev_item = cell(f"{rev:,.2f}", RIGHT)
            if rev > 0:
                rev_item.setForeground(QBrush(QColor("#10B981")))
                font = QFont()
                font.setBold(True)
                rev_item.setFont(font)
            self.table.setItem(row, 7, rev_item)

            total_revenue += rev
            
            # Botones de Acción
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            
            btn_edit = QPushButton("✏️")
            btn_edit.setToolTip("Editar")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.setStyleSheet("background: transparent; border: none; font-size: 14px;")
            btn_edit.clicked.connect(lambda checked, pd=p: self._edit_product(pd))
            
            btn_delete = QPushButton("🗑️")
            btn_delete.setToolTip("Eliminar")
            btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_delete.setStyleSheet("background: transparent; border: none; font-size: 14px;")
            btn_delete.clicked.connect(lambda checked, sku=p.get("sku"): self._delete_product(sku))
            
            actions_layout.addWidget(btn_edit)
            actions_layout.addWidget(btn_delete)
            actions_layout.addStretch()
            
            self.table.setCellWidget(row, 8, actions_widget)

        count = len(products)
        self.lbl_status.setText(f"{count} producto{'s' if count != 1 else ''}")
        self.lbl_footer.setText(
            f"Total ingresos por ventas de productos: {total_revenue:,.2f} € "
            f"(presupuestos aceptados / albaranes firmados)"
        )

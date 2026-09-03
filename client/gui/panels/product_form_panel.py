import traceback
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QDoubleSpinBox, QPushButton, QMessageBox, QFrame, QSizePolicy, QComboBox
)
from PyQt6.QtCore import Qt

class AlfonsoProductFormPanel(QWidget):
    """Panel para crear un nuevo producto o servicio."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit_sku = None
        self.setup_ui()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("🆕 NUEVO PRODUCTO O SERVICIO")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #E2E8F0; letter-spacing: 0.5px;")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(99,102,241,0.2);")
        root.addWidget(sep)

        # Form Container
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)

        # Tipo (Producto / Servicio)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Producto Físico (product)", "Servicio (service)"])
        self.type_combo.setStyleSheet("padding: 8px; border-radius: 4px; background: rgba(30,41,59,0.5); color: white; border: 1px solid rgba(99,102,241,0.3);")
        form_layout.addWidget(QLabel("Tipo de Elemento:"))
        form_layout.addWidget(self.type_combo)

        # SKU
        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Automático (o escribe uno)")
        self.sku_input.setStyleSheet("padding: 8px; border-radius: 4px; background: rgba(30,41,59,0.5); color: white; border: 1px solid rgba(99,102,241,0.3);")
        form_layout.addWidget(QLabel("SKU (Código único):"))
        form_layout.addWidget(self.sku_input)

        # Nombre
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre del producto o servicio")
        self.name_input.setStyleSheet("padding: 8px; border-radius: 4px; background: rgba(30,41,59,0.5); color: white; border: 1px solid rgba(99,102,241,0.3);")
        form_layout.addWidget(QLabel("Nombre:"))
        form_layout.addWidget(self.name_input)

        # Descripción
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Descripción detallada...")
        self.desc_input.setFixedHeight(80)
        self.desc_input.setStyleSheet("padding: 8px; border-radius: 4px; background: rgba(30,41,59,0.5); color: white; border: 1px solid rgba(99,102,241,0.3);")
        form_layout.addWidget(QLabel("Descripción:"))
        form_layout.addWidget(self.desc_input)

        # Precios y Tasas (HBox)
        prices_layout = QHBoxLayout()
        
        # Precio
        price_vbox = QVBoxLayout()
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0.0, 999999.99)
        self.price_input.setDecimals(2)
        self.price_input.setSuffix(" €")
        self.price_input.setStyleSheet("padding: 8px; border-radius: 4px; background: rgba(30,41,59,0.5); color: white; border: 1px solid rgba(99,102,241,0.3);")
        price_vbox.addWidget(QLabel("Precio Base (sin IVA):"))
        price_vbox.addWidget(self.price_input)
        prices_layout.addLayout(price_vbox)

        # IVA
        iva_vbox = QVBoxLayout()
        self.iva_input = QDoubleSpinBox()
        self.iva_input.setRange(0.0, 100.0)
        self.iva_input.setDecimals(2)
        self.iva_input.setValue(21.0)
        self.iva_input.setSuffix(" %")
        self.iva_input.setStyleSheet("padding: 8px; border-radius: 4px; background: rgba(30,41,59,0.5); color: white; border: 1px solid rgba(99,102,241,0.3);")
        iva_vbox.addWidget(QLabel("Tipo de IVA:"))
        iva_vbox.addWidget(self.iva_input)
        prices_layout.addLayout(iva_vbox)

        form_layout.addLayout(prices_layout)
        
        root.addLayout(form_layout)
        root.addStretch()

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("💾 Guardar Producto")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setFixedSize(160, 36)
        self.btn_save.setStyleSheet('''
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #4338CA; }
        ''')
        self.btn_save.clicked.connect(self.on_save)
        btn_layout.addWidget(self.btn_save)
        
        root.addLayout(btn_layout)

    def on_save(self):
        sku = self.sku_input.text().strip()
        name = self.name_input.text().strip()
        desc = self.desc_input.toPlainText().strip()
        price = self.price_input.value()
        iva = self.iva_input.value()
        item_type = "service" if "service" in self.type_combo.currentText() else "product"

        if not name:
            QMessageBox.warning(self, "Campos incompletos", "Por favor, indica al menos un Nombre para el producto o servicio.")
            return

        data = {
            "name": name,
            "price": price,
            "description": desc,
            "iva_rate": iva,
            "item_type": item_type
        }
        if sku:
            data["sku"] = sku

        # Parent should be AlfonsoHUDDashboard which has api_client as self.api
        api = None
        p = self.parent()
        while p:
            if hasattr(p, 'api'):
                api = p.api
                break
            p = p.parent()

        if api:
            if self.edit_sku:
                res = api.update_product(self.edit_sku, data)
                success_msg = "Producto actualizado exitosamente."
            else:
                res = api.create_product(data)
                success_msg = "Producto creado exitosamente."

            if res.get("status") == "ok":
                QMessageBox.information(self, "Éxito", res.get("message", success_msg))
                self.clear_form()
                
                # Intentar actualizar la lista y volver a ella si existe
                if hasattr(p, 'view_product_list'):
                    p.view_product_list.load_data()
                if hasattr(p, 'content_stack') and hasattr(p, 'view_product_list'):
                    p.content_stack.setCurrentWidget(p.view_product_list)
            else:
                QMessageBox.critical(self, "Error", f"No se pudo guardar el producto:\n{res.get('message')}")
        else:
            QMessageBox.critical(self, "Error Interno", "No se encontró cliente de API.")

    def load_for_edit(self, product_data: dict):
        self.edit_sku = product_data.get("sku")
        self.sku_input.setText(self.edit_sku or "")
        self.sku_input.setEnabled(False) # No permitir cambiar el SKU en edición
        self.name_input.setText(product_data.get("name") or "")
        self.desc_input.setText(product_data.get("description") or "")
        self.price_input.setValue(float(product_data.get("price", 0)))
        self.iva_input.setValue(float(product_data.get("iva_rate", 21)))
        
        item_type = product_data.get("item_type", "product")
        if item_type == "service":
            self.type_combo.setCurrentIndex(1)
        else:
            self.type_combo.setCurrentIndex(0)
            
        self.btn_save.setText("💾 Guardar Cambios")

    def clear_form(self):
        self.edit_sku = None
        self.sku_input.setEnabled(True)
        self.sku_input.clear()
        self.name_input.clear()
        self.desc_input.clear()
        self.price_input.setValue(0.0)
        self.iva_input.setValue(21.0)
        self.btn_save.setText("💾 Guardar Producto")

import base64
import json
import os
import io
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QListWidget, QListWidgetItem, QFrame, QColorDialog, QFileDialog, 
    QMessageBox, QScrollArea, QAbstractItemView, QSizePolicy, QGroupBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QSize, QByteArray
from PyQt6.QtGui import QColor, QPixmap, QFont, QPainter, QBrush, QPen

# Mapeo de nombres descriptivos a identificadores internos de los bloques
BLOCK_NAMES = {
    "cabecera": "Cabecera (Título, Factura ID y Fecha)",
    "emisor_receptor": "Datos de Emisor y Cliente",
    "detalles": "Líneas de Detalle y Conceptos",
    "totales": "Cuadro de Totales e Impuestos",
    "pie_verifactu": "Pie Legal y Código QR Veri*Factu"
}

BLOCK_IDS = {v: k for k, v in BLOCK_NAMES.items()}

class DragListWidget(QListWidget):
    """Lista especializada que emite una señal o ejecuta un callback tras reordenarse."""
    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setStyleSheet("""
            QListWidget {
                background-color: rgba(30, 41, 59, 0.5);
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 8px;
                padding: 6px;
                color: #F8FAFC;
                font-size: 12px;
            }
            QListWidget::item {
                background-color: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                margin: 4px 2px;
                padding: 10px;
            }
            QListWidget::item:hover {
                background-color: rgba(99, 102, 241, 0.15);
                border-color: rgba(99, 102, 241, 0.4);
            }
            QListWidget::item:selected {
                background-color: rgba(99, 102, 241, 0.35);
                border-color: #6366F1;
                color: #FFFFFF;
                font-weight: bold;
            }
        """)

    def dropEvent(self, event):
        super().dropEvent(event)
        if self.callback:
            self.callback()


class AlfonsoDocumentCustomizerWidget(QWidget):
    """Editor avanzado de maquetación interactiva Drag-and-Drop con preview en tiempo real."""
    def __init__(self, parent_dashboard, embedded=True):
        super().__init__(parent_dashboard)
        self.dashboard = parent_dashboard
        self.logo_base64 = None
        self.primary_color = "#1E293B"
        self.secondary_color = "#64748B"
        self.elements_layout = ["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]
        self.quote_elements_layout = ["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]
        self.logo_width = 110
        
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        # Layout principal de la vista
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(20)

        # ── COLUMNA IZQUIERDA: CONTROLES Y EDICIÓN ──
        left_panel = QFrame()
        left_panel.setObjectName("LeftPanel")
        left_panel.setStyleSheet("""
            #LeftPanel {
                background-color: #0E1626;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
            }
            QLabel {
                color: #E2E8F0;
                font-weight: 500;
            }
            QLineEdit, QComboBox {
                background-color: rgba(15, 23, 42, 0.8);
                color: #F8FAFC;
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
            }
            QGroupBox {
                border: 1px solid rgba(99, 102, 241, 0.2);
                border-radius: 8px;
                margin-top: 14px;
                font-size: 11px;
                font-weight: bold;
                color: #00F0FF;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 4px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        # Título de la vista
        title_lbl = QLabel("DISEÑO Y MAQUETACIÓN DE DOCUMENTOS")
        title_lbl.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #00F0FF;
            letter-spacing: 0.5px;
        """)
        desc_lbl = QLabel("Organiza las secciones del PDF arrastrándolas en la lista y ajusta la identidad visual corporativa en tiempo real.")
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        left_layout.addWidget(title_lbl)
        left_layout.addWidget(desc_lbl)

        # Selector de Tipo de Documento
        type_lay = QHBoxLayout()
        type_lay.setContentsMargins(0, 4, 0, 4)
        type_lbl = QLabel("Personalizar para:")
        type_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #FFFFFF;")
        self.combo_doc_type = QComboBox()
        self.combo_doc_type.addItems(["Facturas", "Presupuestos", "Nóminas (Oficiales)"])
        self.combo_doc_type.setStyleSheet("font-size: 11px; padding: 4px; color: #FFFFFF; background-color: #1E293B; border-radius: 4px;")
        self.combo_doc_type.currentIndexChanged.connect(self.on_doc_type_changed)
        self.last_doc_type_index = 0
        type_lay.addWidget(type_lbl)
        type_lay.addWidget(self.combo_doc_type)
        type_lay.addStretch()
        left_layout.addLayout(type_lay)

        # Cartel informativo para Nóminas
        self.info_nominas = QFrame()
        self.info_nominas.setVisible(False)
        self.info_nominas.setStyleSheet("""
            background-color: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 8px;
        """)
        info_lay = QVBoxLayout(self.info_nominas)
        info_title = QLabel("NÓMINA REGULADA (FORMATO OFICIAL)")
        info_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px;")
        info_desc = QLabel(
            "Por imperativo legal (Orden ESS/2098/2014), el formato y disposición del Recibo de Salarios "
            "es estricto y no puede ser reordenado libremente por el usuario.\n\n"
            "Sin embargo, el sistema aplica automáticamente tu logotipo corporativo, colores primarios/secundarios "
            "y tipografía elegidos a las secciones del documento oficial al generarlo."
        )
        info_desc.setWordWrap(True)
        info_desc.setStyleSheet("color: #E2E8F0; font-size: 10px; line-height: 14px;")
        info_lay.addWidget(info_title)
        info_lay.addWidget(info_desc)
        left_layout.addWidget(self.info_nominas)

        # 1. Grupo Drag-and-Drop
        self.layout_group = QGroupBox("ORGANIZAR ELEMENTOS (DRAG & DROP)")
        layout_group_layout = QVBoxLayout(self.layout_group)
        layout_group_layout.setContentsMargins(10, 10, 10, 10)
        
        drag_lbl = QLabel("Arrastra hacia arriba o abajo para reordenar las secciones del documento:")
        drag_lbl.setStyleSheet("font-size: 10px; color: #94A3B8; font-style: italic;")
        layout_group_layout.addWidget(drag_lbl)

        self.list_widget = DragListWidget(callback=self.on_layout_reordered)
        # Añadir elementos por defecto
        self.default_order = ["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]
        for block_id in self.default_order:
            item = QListWidgetItem(BLOCK_NAMES[block_id])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.list_widget.addItem(item)
            
        layout_group_layout.addWidget(self.list_widget)
        left_layout.addWidget(self.layout_group)

        # 2. Grupo Apariencia y Colores
        style_group = QGroupBox("COLORES Y TIPOGRAFÍA")
        style_group_layout = QVBoxLayout(style_group)
        style_group_layout.setContentsMargins(10, 10, 10, 10)
        style_group_layout.setSpacing(8)

        # Color Principal
        primary_lay = QHBoxLayout()
        self.lbl_color_primary_indicator = QFrame()
        self.lbl_color_primary_indicator.setFixedSize(18, 18)
        self.lbl_color_primary_indicator.setStyleSheet("border-radius: 4px; border: 1px solid rgba(255,255,255,0.2);")
        self.btn_pick_primary = QPushButton("Elegir Principal...")
        self.btn_pick_primary.clicked.connect(self.pick_primary_color)
        self.btn_pick_primary.setStyleSheet("font-size: 10px; padding: 4px 8px;")
        primary_lay.addWidget(self.lbl_color_primary_indicator)
        primary_lay.addWidget(self.btn_pick_primary)
        primary_lay.addStretch()
        style_group_layout.addLayout(primary_lay)

        # Color Secundario
        secondary_lay = QHBoxLayout()
        self.lbl_color_secondary_indicator = QFrame()
        self.lbl_color_secondary_indicator.setFixedSize(18, 18)
        self.lbl_color_secondary_indicator.setStyleSheet("border-radius: 4px; border: 1px solid rgba(255,255,255,0.2);")
        self.btn_pick_secondary = QPushButton("Elegir Secundario...")
        self.btn_pick_secondary.clicked.connect(self.pick_secondary_color)
        self.btn_pick_secondary.setStyleSheet("font-size: 10px; padding: 4px 8px;")
        secondary_lay.addWidget(self.lbl_color_secondary_indicator)
        secondary_lay.addWidget(self.btn_pick_secondary)
        secondary_lay.addStretch()
        style_group_layout.addLayout(secondary_lay)

        # Tipografía y Plantilla
        combo_lay = QHBoxLayout()
        self.combo_font = QComboBox()
        self.combo_font.addItems(["Helvetica", "Times-Roman", "Courier"])
        self.combo_font.currentIndexChanged.connect(self.update_live_preview)
        combo_lay.addWidget(QLabel("Fuente:"))
        combo_lay.addWidget(self.combo_font)

        self.combo_template = QComboBox()
        self.combo_template.addItems(["classic", "modern", "minimalist"])
        self.combo_template.currentIndexChanged.connect(self.update_live_preview)
        combo_lay.addWidget(QLabel("Estilo:"))
        combo_lay.addWidget(self.combo_template)
        style_group_layout.addLayout(combo_lay)

        left_layout.addWidget(style_group)

        # 3. Logotipo Comercial
        logo_group = QGroupBox("LOGOTIPO COMERCIAL")
        logo_group_layout = QVBoxLayout(logo_group)
        logo_group_layout.setContentsMargins(10, 10, 10, 10)
        logo_group_layout.setSpacing(8)

        logo_top_lay = QHBoxLayout()
        self.lbl_logo_preview = QLabel("Sin Logo")
        self.lbl_logo_preview.setFixedSize(80, 40)
        self.lbl_logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_logo_preview.setStyleSheet("border: 1px dashed rgba(255, 255, 255, 0.2); background-color: rgba(255, 255, 255, 0.02); color: #64748B; font-size: 9px; border-radius: 4px;")
        logo_top_lay.addWidget(self.lbl_logo_preview)

        logo_btns = QVBoxLayout()
        self.btn_select_logo = QPushButton("Subir...")
        self.btn_select_logo.clicked.connect(self.select_logo)
        self.btn_select_logo.setStyleSheet("font-size: 9px; padding: 3px;")
        self.btn_remove_logo = QPushButton("Quitar")
        self.btn_remove_logo.clicked.connect(self.remove_logo)
        self.btn_remove_logo.setStyleSheet("font-size: 9px; padding: 3px;")
        logo_btns.addWidget(self.btn_select_logo)
        logo_btns.addWidget(self.btn_remove_logo)
        logo_top_lay.addLayout(logo_btns)
        logo_group_layout.addLayout(logo_top_lay)

        # Control del tamaño del logo (Slider)
        size_lay = QHBoxLayout()
        self.lbl_logo_size = QLabel("Ancho: 110px")
        self.lbl_logo_size.setStyleSheet("font-size: 9px; color: #94A3B8;")
        
        from PyQt6.QtWidgets import QSlider
        self.slider_logo_width = QSlider(Qt.Orientation.Horizontal)
        self.slider_logo_width.setRange(50, 200)
        self.slider_logo_width.setValue(110)
        self.slider_logo_width.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #6366F1;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self.slider_logo_width.valueChanged.connect(self.on_logo_width_slider_changed)
        size_lay.addWidget(QLabel("Tamaño:"))
        size_lay.addWidget(self.slider_logo_width)
        size_lay.addWidget(self.lbl_logo_size)
        logo_group_layout.addLayout(size_lay)

        left_layout.addWidget(logo_group)

        # Botón Guardar
        self.btn_save = QPushButton("GUARDAR PREFERENCIAS Y MAQUETACIÓN")
        self.btn_save.setFixedHeight(38)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
            QPushButton:pressed {
                background-color: #3730A3;
            }
        """)
        self.btn_save.clicked.connect(self.save_settings)
        left_layout.addWidget(self.btn_save)

        main_layout.addWidget(left_panel, 4)

        # ── COLUMNA DERECHA: PREVISUALIZACIÓN EN VIVO ──
        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")
        right_panel.setStyleSheet("""
            #RightPanel {
                background-color: #0E1626;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        
        preview_header = QHBoxLayout()
        preview_badge = QLabel("● PREVISUALIZACIÓN DE MAQUETA EN VIVO")
        preview_badge.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; letter-spacing: 0.5px;")
        preview_header.addWidget(preview_badge)
        preview_header.addStretch()
        right_layout.addLayout(preview_header)

        # ScrollArea para la hoja A4 simulada
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Hoja A4 simulada
        self.a4_sheet = QFrame()
        self.a4_sheet.setFixedSize(380, 520)
        self.a4_sheet.setStyleSheet("""
            background-color: #FFFFFF;
            border-radius: 6px;
        """)
        
        # Efecto de sombra premium nativo (reemplaza box-shadow de CSS no soportado por Qt)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80)) # Opacidad elegante para simular papel
        self.a4_sheet.setGraphicsEffect(shadow)
        
        self.a4_layout = QVBoxLayout(self.a4_sheet)
        self.a4_layout.setContentsMargins(20, 20, 20, 20)
        self.a4_layout.setSpacing(10)
        scroll_layout.addWidget(self.a4_sheet)
        scroll.setWidget(scroll_content)
        right_layout.addWidget(scroll)

        main_layout.addWidget(right_panel, 5)

    def load_settings(self):
        """Carga la configuración guardada del backend."""
        try:
            custom = self.dashboard.api.get_document_customization()
            
            # Cargar colores
            self.primary_color = custom.get("primary_color", "#1E293B")
            self.secondary_color = custom.get("secondary_color", "#64748B")
            self.update_color_indicators()

            # Tipografía
            idx_font = self.combo_font.findText(custom.get("font_family", "Helvetica"))
            if idx_font >= 0:
                self.combo_font.setCurrentIndex(idx_font)
                
            # Estilo / plantilla
            idx_template = self.combo_template.findText(custom.get("layout_template", "classic"))
            if idx_template >= 0:
                self.combo_template.setCurrentIndex(idx_template)

            # Logo
            self.logo_base64 = custom.get("logo_base64")
            self.update_logo_preview()
            
            # Ancho de logo
            self.logo_width = custom.get("logo_width", 110)
            self.slider_logo_width.setValue(self.logo_width)
            self.lbl_logo_size.setText(f"Ancho: {self.logo_width}px")

            # Layouts independientes (con fallback a lista inicial si no existe)
            try:
                self.elements_layout = json.loads(custom.get("elements_layout", '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]'))
            except Exception:
                self.elements_layout = ["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]

            try:
                self.quote_elements_layout = json.loads(custom.get("quote_elements_layout", '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]'))
            except Exception:
                self.quote_elements_layout = ["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]

            # Inicializar lista según el combo
            self.list_widget.clear()
            idx = self.combo_doc_type.currentIndex()
            self.last_doc_type_index = idx
            
            if idx == 0:
                target_layout = self.elements_layout
            elif idx == 1:
                target_layout = self.quote_elements_layout
            else:
                target_layout = []
                
            for block_id in target_layout:
                item = QListWidgetItem(BLOCK_NAMES[block_id])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.list_widget.addItem(item)

            self.update_live_preview()
        except Exception as e:
            print(f"[ERROR] No se pudo cargar la personalización en el editor: {e}")

    def save_settings(self):
        """Envía el orden y la configuración al backend."""
        # Primero, guardar el orden actual de la lista de UI en el atributo correspondiente
        current_order = []
        for i in range(self.list_widget.count()):
            item_text = self.list_widget.item(i).text()
            block_id = BLOCK_IDS.get(item_text)
            if block_id:
                current_order.append(block_id)
                
        idx = self.combo_doc_type.currentIndex()
        if idx == 0:
            self.elements_layout = current_order
        elif idx == 1:
            self.quote_elements_layout = current_order

        custom_data = {
            "logo_base64": self.logo_base64,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "font_family": self.combo_font.currentText(),
            "layout_template": self.combo_template.currentText(),
            "elements_layout": json.dumps(self.elements_layout),
            "quote_elements_layout": json.dumps(self.quote_elements_layout),
            "logo_width": self.logo_width
        }

        try:
            res = self.dashboard.api.save_document_customization(custom_data)
            if res.get("status") == "ok":
                QMessageBox.information(
                    self, 
                    "Configuración Guardada", 
                    "La maqueta predeterminada y el diseño corporativo han sido actualizados y guardados en tu perfil."
                )
                if hasattr(self.dashboard, 'update_business_metrics'):
                    self.dashboard.update_business_metrics()
            else:
                QMessageBox.warning(self, "Error", f"No se pudo guardar: {res.get('message')}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error en la conexión con el servidor: {e}")

    def on_logo_width_slider_changed(self, value):
        """Maneja el redimensionamiento del logotipo comercial."""
        self.logo_width = value
        self.lbl_logo_size.setText(f"Ancho: {value}px")
        self.update_live_preview()

    def on_layout_reordered(self):
        """Callback invocado cuando el usuario arrastra y suelta un elemento para cambiar el orden."""
        self.update_live_preview()

    def update_color_indicators(self):
        self.lbl_color_primary_indicator.setStyleSheet(f"background-color: {self.primary_color}; border-radius: 4px; border: 1px solid rgba(255,255,255,0.2);")
        self.lbl_color_secondary_indicator.setStyleSheet(f"background-color: {self.secondary_color}; border-radius: 4px; border: 1px solid rgba(255,255,255,0.2);")

    def pick_primary_color(self):
        col = QColorDialog.getColor(QColor(self.primary_color), self, "Seleccionar Color Principal")
        if col.isValid():
            self.primary_color = col.name()
            self.update_color_indicators()
            self.update_live_preview()

    def pick_secondary_color(self):
        col = QColorDialog.getColor(QColor(self.secondary_color), self, "Seleccionar Color Secundario")
        if col.isValid():
            self.secondary_color = col.name()
            self.update_color_indicators()
            self.update_live_preview()

    def select_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Logotipo", "", "Imágenes (*.png *.jpg *.jpeg)")
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    data = f.read()
                    self.logo_base64 = base64.b64encode(data).decode("utf-8")
                self.update_logo_preview()
                self.update_live_preview()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo cargar la imagen: {e}")

    def remove_logo(self):
        self.logo_base64 = None
        self.update_logo_preview()
        self.update_live_preview()

    def update_logo_preview(self):
        if self.logo_base64:
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray.fromBase64(self.logo_base64.encode("utf-8")))
                scaled = pixmap.scaled(self.lbl_logo_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_logo_preview.setPixmap(scaled)
            except Exception:
                self.lbl_logo_preview.setText("Logo Error")
        else:
            self.lbl_logo_preview.clear()
            self.lbl_logo_preview.setText("Sin Logo")

    def on_doc_type_changed(self, index):
        """Maneja el cambio del tipo de documento en el selector."""
        # 1. Guardar el orden actual de la lista de UI en el atributo correspondiente
        current_order = []
        for i in range(self.list_widget.count()):
            item_text = self.list_widget.item(i).text()
            block_id = BLOCK_IDS.get(item_text)
            if block_id:
                current_order.append(block_id)
                
        if self.last_doc_type_index == 0:
            self.elements_layout = current_order
        elif self.last_doc_type_index == 1:
            self.quote_elements_layout = current_order

        self.last_doc_type_index = index

        # 2. Configurar controles según el tipo seleccionado
        if index in (0, 1):  # Facturas (0) o Presupuestos (1)
            self.layout_group.setVisible(True)
            self.info_nominas.setVisible(False)
            self.btn_save.setEnabled(True)
            self.btn_save.setText("GUARDAR PREFERENCIAS Y MAQUETACIÓN")
            
            # Cargar los bloques correspondientes en el list widget
            self.list_widget.clear()
            target_layout = self.elements_layout if index == 0 else self.quote_elements_layout
            for block_id in target_layout:
                item = QListWidgetItem(BLOCK_NAMES[block_id])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.list_widget.addItem(item)
        else:  # Nóminas (2)
            self.layout_group.setVisible(False)
            self.info_nominas.setVisible(True)
            self.btn_save.setEnabled(True)
            self.btn_save.setText("GUARDAR APARIENCIA CORPORATIVA")
            
        self.update_live_preview()

    def update_live_preview(self):
        """Reconstruye dinámicamente la previsualización en la hoja A4 según el orden y estilo."""
        # Limpiar layout
        while self.a4_layout.count() > 0:
            item = self.a4_layout.takeAt(0)
            if item:
                w = item.widget()
                if w:
                    w.deleteLater()

        template_style = self.combo_template.currentText()
        font_family = self.combo_font.currentText()

        # Determinar el tipo de documento seleccionado
        idx = self.combo_doc_type.currentIndex()
        if idx == 2:
            # Nóminas oficiales (Orden ESS/2098/2014)
            blocks = ["nomina_cabecera", "nomina_devengos", "nomina_deducciones", "nomina_totales", "nomina_firmas"]
            for block_id in blocks:
                widget = self.create_block_preview_widget(block_id, template_style, font_family)
                if widget:
                    self.a4_layout.addWidget(widget)
        else:
            # Facturas o Presupuestos (ordenables)
            order = []
            for i in range(self.list_widget.count()):
                item_text = self.list_widget.item(i).text()
                block_id = BLOCK_IDS.get(item_text)
                if block_id:
                    order.append(block_id)

            for block_id in order:
                widget = self.create_block_preview_widget(block_id, template_style, font_family)
                if widget:
                    self.a4_layout.addWidget(widget)

    def create_block_preview_widget(self, block_id: str, template_style: str, font_family: str) -> QWidget:
        """Crea un widget simulado estilizado para una sección específica de la factura, presupuesto o nómina."""
        frame = QFrame()
        frame.setObjectName("BlockPreviewFrame")
        
        # Color base del borde según el color secundario
        sec_color = self.secondary_color
        prim_color = self.primary_color
        
        frame.setStyleSheet(f"""
            #BlockPreviewFrame {{
                background-color: #F8FAFC;
                border: 1.5px dashed {sec_color};
                border-radius: 6px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        if block_id == "cabecera":
            frame.setFixedHeight(85)
            # Dibujar la cabecera simulada
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            # Título dinámico
            doc_idx = self.combo_doc_type.currentIndex()
            title_text = "PRESUPUESTO" if doc_idx == 1 else "FACTURA"
            title_lbl = QLabel(title_text)
            title_font = QFont(font_family, 11, QFont.Weight.Bold)
            title_lbl.setFont(title_font)
            
            # Estilos de cabecera
            if template_style == "classic":
                title_lbl.setStyleSheet(f"color: #FFFFFF; background-color: {prim_color}; padding: 4px 8px; border-radius: 2px;")
            elif template_style == "modern":
                title_lbl.setStyleSheet(f"color: {prim_color}; border-top: 3px solid {prim_color}; padding-top: 2px;")
            else: # minimalist
                title_lbl.setStyleSheet(f"color: {prim_color};")
                
            h_layout.addWidget(title_lbl)
            h_layout.addStretch()
            
            # Logo si existe con ancho dinámico según el slider
            if self.logo_base64:
                logo_preview = QLabel()
                disp_w = int(self.logo_width / 1.5)
                disp_h = int(disp_w * 25.0 / 73.0)
                logo_preview.setFixedSize(disp_w, disp_h)
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray.fromBase64(self.logo_base64.encode("utf-8")))
                scaled = pixmap.scaled(logo_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_preview.setPixmap(scaled)
                h_layout.addWidget(logo_preview)
            else:
                logo_placeholder = QLabel("[LOGO]")
                logo_placeholder.setStyleSheet("color: #94A3B8; font-size: 8px; font-weight: bold; border: 1px dotted #CBD5E1; padding: 2px;")
                h_layout.addWidget(logo_placeholder)
                
            layout.addLayout(h_layout)
            
            # Metadatos
            meta_pref = "PRE" if doc_idx == 1 else "FAC"
            meta_lbl = QLabel(f"Doc Nro: {meta_pref}-2026-0042   |   Fecha: {self.get_current_date_str()}")
            meta_lbl.setStyleSheet("color: #475569; font-size: 8px; font-family: monospace;")
            layout.addWidget(meta_lbl)

        elif block_id == "emisor_receptor":
            frame.setFixedHeight(95)
            # Dos columnas para Emisor y Cliente
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            # Emisor
            emisor_box = QVBoxLayout()
            em_title = QLabel("EMISOR:")
            em_title.setStyleSheet(f"color: {prim_color}; font-size: 8px; font-weight: bold;")
            em_name = QLabel("Luis Domingo (Autónomo)\nNIF: 12345678Z\nDir: Madrid, España")
            em_name.setStyleSheet("color: #475569; font-size: 7px;")
            emisor_box.addWidget(em_title)
            emisor_box.addWidget(em_name)
            emisor_box.addStretch()
            
            # Receptor
            receptor_box = QVBoxLayout()
            rec_title = QLabel("CLIENTE:")
            rec_title.setStyleSheet(f"color: {prim_color}; font-size: 8px; font-weight: bold;")
            rec_name = QLabel("InnoTech Solutions S.L.\nNIF: B98765432\nDir: Barcelona, España")
            rec_name.setStyleSheet("color: #475569; font-size: 7px;")
            receptor_box.addWidget(rec_title)
            receptor_box.addWidget(rec_name)
            receptor_box.addStretch()
            
            h_layout.addLayout(emisor_box)
            h_layout.addLayout(receptor_box)
            layout.addLayout(h_layout)

        elif block_id == "detalles":
            frame.setFixedHeight(85)
            # Cabecera de tabla
            header_lbl = QLabel("Descripción / Concepto                                              Importe")
            header_lbl.setStyleSheet(f"background-color: #E2E8F0; color: #1E293B; font-size: 8px; font-weight: bold; padding: 2px;")
            layout.addWidget(header_lbl)
            
            # Línea de detalle
            det_lbl = QLabel("Servicios de desarrollo de software - Módulo IA                 1.200,00 EUR")
            det_lbl.setStyleSheet("color: #334155; font-size: 8px;")
            layout.addWidget(det_lbl)
            
            line_f = QFrame()
            line_f.setFrameShape(QFrame.Shape.HLine)
            line_f.setStyleSheet(f"color: {sec_color}; background-color: {sec_color}; max-height: 1px;")
            layout.addWidget(line_f)

        elif block_id == "totales":
            frame.setFixedHeight(85)
            layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            # Resumen de importes
            txt = "Base Imponible:  1.200,00 EUR\n"
            txt += "IVA (+21%):    252,00 EUR\n"
            txt += "Retención IRPF (-15%):   -180,00 EUR"
            total_lbl = QLabel(txt)
            total_lbl.setStyleSheet("color: #475569; font-size: 7px; text-align: right;")
            total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(total_lbl)
            
            final_total_lbl = QLabel("Total a Percibir/Pagar:  1.272,00 EUR")
            final_total_lbl.setStyleSheet(f"color: {prim_color}; font-size: 9px; font-weight: bold;")
            final_total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(final_total_lbl)

        elif block_id == "pie_verifactu":
            frame.setFixedHeight(105)
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            # QR
            qr_sim = QLabel()
            qr_sim.setFixedSize(55, 55)
            qr_sim.setStyleSheet("background-color: #000000; border: 1px solid #E2E8F0;")
            
            # Dibujar un patrón simulado de QR en un pixmap
            qr_pix = QPixmap(55, 55)
            qr_pix.fill(Qt.GlobalColor.white)
            painter = QPainter(qr_pix)
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.setBrush(QBrush(Qt.GlobalColor.black))
            # Dibujar marcadores de esquina
            painter.drawRect(2, 2, 14, 14)
            painter.drawRect(6, 6, 6, 6)
            painter.drawRect(39, 2, 14, 14)
            painter.drawRect(43, 6, 6, 6)
            painter.drawRect(2, 39, 14, 14)
            painter.drawRect(6, 43, 6, 6)
            # Algunos puntos random
            painter.drawRect(20, 20, 4, 4)
            painter.drawRect(30, 25, 4, 4)
            painter.drawRect(22, 32, 4, 4)
            painter.drawRect(32, 40, 4, 4)
            painter.drawRect(40, 30, 4, 4)
            painter.end()
            qr_sim.setPixmap(qr_pix)
            
            h_layout.addWidget(qr_sim)
            
            # Texto legal
            txt_box = QVBoxLayout()
            txt_title = QLabel("VERIFACTU - FACTURA / DOCUMENTO SEGURO")
            txt_title.setStyleSheet(f"color: {prim_color}; font-size: 8px; font-weight: bold;")
            txt_body = QLabel("Factura verificable en la Sede electrónica de la AEAT.\nEste registro de facturación ha sido firmado digitalmente y enviado a la AEAT.")
            txt_body.setWordWrap(True)
            txt_body.setStyleSheet("color: #64748B; font-size: 6px;")
            txt_box.addWidget(txt_title)
            txt_box.addWidget(txt_body)
            txt_box.addStretch()
            h_layout.addLayout(txt_box)
            
            layout.addLayout(h_layout)
            
            footer_lbl = QLabel("Forma de pago: Transferencia bancaria a la cuenta indicada. Presupuesto válido por 30 días.")
            footer_lbl.setStyleSheet("color: #94A3B8; font-size: 6px; font-style: italic;")
            layout.addWidget(footer_lbl)

        # Bloques simulados de Nómina Oficial
        elif block_id == "nomina_cabecera":
            frame.setFixedHeight(95)
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            # Datos del Emisor y Trabajador
            datos_box = QVBoxLayout()
            datos_emp = QLabel("EMPRESA: Luis Domingo S.L.\nTRABAJADOR: Juan Pérez Pérez\nNIF: 87654321A  |  Nro. SS: 28/1234567/89")
            datos_emp.setStyleSheet("color: #475569; font-size: 7px; line-height: 10px;")
            datos_box.addWidget(datos_emp)
            datos_box.addStretch()
            h_layout.addLayout(datos_box)
            
            # Logo si existe con ancho dinámico según el slider
            if self.logo_base64:
                logo_preview = QLabel()
                disp_w = int(self.logo_width / 1.5)
                disp_h = int(disp_w * 25.0 / 73.0)
                logo_preview.setFixedSize(disp_w, disp_h)
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray.fromBase64(self.logo_base64.encode("utf-8")))
                scaled = pixmap.scaled(logo_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_preview.setPixmap(scaled)
                h_layout.addWidget(logo_preview)
            else:
                logo_placeholder = QLabel("[LOGO]")
                logo_placeholder.setStyleSheet("color: #94A3B8; font-size: 8px; font-weight: bold; border: 1px dotted #CBD5E1; padding: 2px;")
                h_layout.addWidget(logo_placeholder)
                
            layout.addLayout(h_layout)
            
            # Título de nómina oficial
            title_font = QFont(font_family, 10, QFont.Weight.Bold)
            title_lbl = QLabel("RECIBO INDIVIDUAL DE SALARIOS (Orden ESS/2098/2014)")
            title_lbl.setFont(title_font)
            title_lbl.setStyleSheet(f"color: {prim_color}; border-top: 1.5px solid {sec_color}; padding-top: 3px;")
            layout.addWidget(title_lbl)

        elif block_id == "nomina_devengos":
            frame.setFixedHeight(85)
            header_lbl = QLabel("I. DEVENGOS (Percepciones Salariales y No Salariales)              Importe")
            header_lbl.setStyleSheet(f"background-color: #E2E8F0; color: #1E293B; font-size: 8px; font-weight: bold; padding: 2px;")
            layout.addWidget(header_lbl)
            
            det_lbl = QLabel("Salario Base                                                      1.500,00 EUR\nPlus de Convenio                                                    120,00 EUR")
            det_lbl.setStyleSheet("color: #334155; font-size: 8px; line-height: 11px;")
            layout.addWidget(det_lbl)
            
            line_f = QFrame()
            line_f.setFrameShape(QFrame.Shape.HLine)
            line_f.setStyleSheet(f"color: {sec_color}; background-color: {sec_color}; max-height: 1px;")
            layout.addWidget(line_f)

        elif block_id == "nomina_deducciones":
            frame.setFixedHeight(85)
            header_lbl = QLabel("II. DEDUCCIONES (Aportaciones del Trabajador e IRPF)               Importe")
            header_lbl.setStyleSheet(f"background-color: #E2E8F0; color: #1E293B; font-size: 8px; font-weight: bold; padding: 2px;")
            layout.addWidget(header_lbl)
            
            det_lbl = QLabel("Cotizaciones por Contingencias Comunes                              -70,50 EUR\nRetención IRPF (15%)                                               -243,00 EUR")
            det_lbl.setStyleSheet("color: #334155; font-size: 8px; line-height: 11px;")
            layout.addWidget(det_lbl)

        elif block_id == "nomina_totales":
            frame.setFixedHeight(75)
            layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            txt = "Total Devengado:  1.620,00 EUR\nTotal Deducciones:  -313,50 EUR"
            total_lbl = QLabel(txt)
            total_lbl.setStyleSheet("color: #475569; font-size: 7px; text-align: right;")
            total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(total_lbl)
            
            final_total_lbl = QLabel("LÍQUIDO A PERCIBIR:  1.306,50 EUR")
            final_total_lbl.setStyleSheet(f"color: {prim_color}; font-size: 9px; font-weight: bold;")
            final_total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(final_total_lbl)

        elif block_id == "nomina_firmas":
            frame.setFixedHeight(75)
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            f_emp = QVBoxLayout()
            lbl_f_emp = QLabel("FIRMA EMPRESA / SELLO:")
            lbl_f_emp.setStyleSheet(f"color: {prim_color}; font-size: 7px; font-weight: bold;")
            line_f_emp = QFrame()
            line_f_emp.setStyleSheet(f"border-top: 1px dashed {sec_color}; max-height: 1px; margin-top: 25px;")
            f_emp.addWidget(lbl_f_emp)
            f_emp.addWidget(line_f_emp)
            
            f_tra = QVBoxLayout()
            lbl_f_tra = QLabel("RECIBÍ TRABAJADOR:")
            lbl_f_tra.setStyleSheet(f"color: {prim_color}; font-size: 7px; font-weight: bold;")
            line_f_tra = QFrame()
            line_f_tra.setStyleSheet(f"border-top: 1px dashed {sec_color}; max-height: 1px; margin-top: 25px;")
            f_tra.addWidget(lbl_f_tra)
            f_tra.addWidget(line_f_tra)
            
            h_layout.addLayout(f_emp)
            h_layout.addLayout(f_tra)
            layout.addLayout(h_layout)

        return frame

    def get_current_date_str(self) -> str:
        import datetime
        return datetime.date.today().strftime("%d/%m/%Y")

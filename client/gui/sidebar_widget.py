"""
ALFONSO SIDEBAR WIDGET — Panel Lateral Jerárquico por Categorías y Subcategorías
Proporciona navegación estructurada para todas las funcionalidades de Alfonso Autónomo.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QScrollArea, QSizePolicy, QApplication, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QCursor, QIcon
from client.gui.theme import HoverAnimationFilter

# Definición completa de la arquitectura de navegación de Alfonso Autónomo
SVG_ICONS = {
    "dashboard": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>""",
    "ingresos_gastos": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/></svg>""",
    "bancos": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M4 10h3v7H4zm6.5 0h3v7h-3zM2 19h20v3H2zm15-9h3v7h-3zm-5-9L2 6v2h20V6z"/></svg>""",
    "catalogos": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>""",
    "fiscal_contable": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm2 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>""",
    "laboral": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>""",
    "espacio_trabajo": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M21 2H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h7v2H8v2h8v-2h-2v-2h7c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H3V4h18v12z"/></svg>""",
    "configuracion": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00F0FF"><path d="M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.06-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.73,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.06,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 C9.65,21.83,9.86,22,10.1,22h3.84c0.24,0,0.43-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.49-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z"/></svg>""",
}

SIDEBAR_CATEGORIES = [
    {
        "id": "dashboard",
        "title": "INICIO",
        "icon": SVG_ICONS["dashboard"],
        "badge": "",
        "subcategories": [
            {"id": "resumen_ejecutivo", "title": "Resumen Ejecutivo", "icon": "", "desc": "KPIs en tiempo real, Donut Chart y alertas AEAT"},
            {"id": "kpis_analitica", "title": "Analítica & KPIs", "icon": "", "desc": "Métricas avanzadas, márgenes y evolución trimestral"},
            {"id": "prevision_cashflow", "title": "Previsión Tesorería", "icon": "", "desc": "Cash Flow a 30/60/90 días y cobros previstos"}
        ]
    },
    {
        "id": "ingresos_gastos",
        "title": "INGRESOS Y GASTOS",
        "icon": SVG_ICONS["ingresos_gastos"],
        "badge": "",
        "subcategories": [
            {"id": "nueva_factura_b2b", "title": "Nueva Factura / FacturaE", "icon": "", "desc": "Emisión rápida, FacturaE B2B XML y Ley Crea y Crece"},
            {"id": "facturas_emitidas", "title": "Facturas Emitidas", "icon": "", "desc": "Libro de ingresos (7XX), estados de cobro y exportación"},
            {"id": "ocr_extraccion", "title": "Captura & OCR IA", "icon": "", "desc": "Extracción automática de tickets y facturas recibidas"},
            {"id": "libro_gastos", "title": "Libro de Gastos", "icon": "", "desc": "Libro de compras (6XX) y partidas deducibles"},
            {"id": "registro_manual", "title": "Registro Manual", "icon": "", "desc": "Inserción directa de gastos y cuota de autónomo RETA"}
        ]
    },
    {
        "id": "bancos",
        "title": "TESORERÍA",
        "icon": SVG_ICONS["bancos"],
        "badge": "",
        "subcategories": [
            {"id": "conciliacion_bancaria", "title": "Conciliación Bancaria", "icon": "", "desc": "Emparejamiento inteligente de apuntes y facturas"},
            {"id": "conexiones_psd2", "title": "Cuentas Conectadas", "icon": "", "desc": "Banca abierta Open Banking y sincronización de saldos"},
            {"id": "transferencias_pagos", "title": "Realizar Pagos", "icon": "", "desc": "Transferencias a proveedores y remesas SEPA"}
        ]
    },
    {
        "id": "catalogos",
        "title": "CATÁLOGOS",
        "icon": SVG_ICONS["catalogos"],
        "badge": "",
        "subcategories": [
            {"id": "clientes_proveedores", "title": "Clientes & Proveedores", "icon": "", "desc": "CRM básico, deudas, retenciones y mandatos SEPA"},
            {"id": "productos_servicios", "title": "Productos & Servicios", "icon": "", "desc": "Gestión de catálogo, control de stock y precios"},
            {"id": "bienes_inversion", "title": "Bienes de Inversión", "icon": "", "desc": "Activos fijos, tabla de amortización y bajas"}
        ]
    },
    {
        "id": "fiscal_contable",
        "title": "FISCAL Y CONTABLE",
        "icon": SVG_ICONS["fiscal_contable"],
        "badge": "",
        "subcategories": [
            {"id": "modelos_trimestrales", "title": "Modelos 303 y 130", "icon": "", "desc": "Autoliquidación trimestral de IVA e IRPF en tiempo real"},
            {"id": "automatizacion_aeat", "title": "Sede Electrónica AEAT", "icon": "", "desc": "Asistente de presentación telemática con Playwright"},
            {"id": "calendario_fiscal", "title": "Calendario Fiscal", "icon": "", "desc": "Vencimientos oficiales, plazos tributarios y alarmas"},
            {"id": "balance_situacion", "title": "Balance de Situación", "icon": "", "desc": "Estado de Activo, Pasivo y Patrimonio Netos (PGC)"},
            {"id": "gestion_activos", "title": "Gestión de Activos", "icon": "", "desc": "Bienes de inversión y cuadro de amortizaciones"},
            {"id": "libros_oficiales_aeat", "title": "Libros Registro Oficiales", "icon": "", "desc": "Exportador Excel/CSV normalizado para la AEAT"}
        ]
    },
    {
        "id": "laboral",
        "title": "LABORAL & NÓMINAS",
        "icon": SVG_ICONS["laboral"],
        "badge": "",
        "subcategories": [
            {"id": "empleados_contratos", "title": "Empleados & Contratos", "icon": "", "desc": "Gestión de plantilla, altas y contratos de trabajo"},
            {"id": "generador_nominas", "title": "Generador de Nóminas", "icon": "", "desc": "Cálculo de IRPF/SS y generación de nóminas PDF"},
            {"id": "afiliacion_tgss", "title": "Seguridad Social TGSS", "icon": "", "desc": "Ficheros AFI/CRA, cotizaciones y cuota RETA"}
        ]
    },
    {
        "id": "espacio_trabajo",
        "title": "ESPACIO DE TRABAJO",
        "icon": SVG_ICONS["espacio_trabajo"],
        "badge": "",
        "subcategories": [
            {"id": "correo_inteligente", "title": "Alfonso Mail", "icon": "", "desc": "Bandeja de correo, extracción de facturas y respuestas"},
            {"id": "agenda_citas", "title": "Agenda & Citas", "icon": "", "desc": "Citas previas en Administraciones y recordatorios"},
            {"id": "archivo_fiscal", "title": "Archivo Digital", "icon": "", "desc": "Explorador organizado por ejercicios y trimestres"},
            {"id": "visor_documental", "title": "Visor Documental IA", "icon": "", "desc": "Previsualización con metadatos contables extraídos"},
            {"id": "proyectos_sesiones", "title": "Libro de Actas (Registro)", "icon": "", "desc": "Registro inmutable y soporte documental de conversaciones"}
        ]
    },
    {
        "id": "configuracion",
        "title": "CONFIGURACIÓN Y AUDITORÍA",
        "icon": SVG_ICONS["configuracion"],
        "badge": "",
        "subcategories": [
            {"id": "perfil_fiscal", "title": "Perfil del Autónomo", "icon": "", "desc": "NIF, actividad IAE, tipo IRPF y domicilio fiscal"},
            {"id": "suscripcion_licencia", "title": "Suscripción & Licencia", "icon": "", "desc": "Detalles del plan activo y ampliación de licencia"},
            {"id": "panel_asesor", "title": "Panel Gestoría / Advisor", "icon": "", "desc": "Gestión multi-empresa y multi-inquilino"},
            {"id": "verifactu_sif", "title": "Veri*Factu & Huella Hash", "icon": "", "desc": "Registro inalterable RD 1007/2023 y QR de cotejo AEAT"},
            {"id": "auditoria_inmutabilidad", "title": "Auditoría de Inmutabilidad", "icon": "", "desc": "Verificación criptográfica y registro inalterable"},
            {"id": "declaracion_sif", "title": "Declaración SIF", "icon": "", "desc": "Acreditación y declaración responsable RD 1007/2023"},
            {"id": "diseno_maquetacion", "title": "Diseño y Maquetación", "icon": "", "desc": "Editor Drag-and-Drop de plantillas y personalización"},
            {"id": "copias_seguridad", "title": "Copias de Seguridad", "icon": "", "desc": "Snapshots locales, exportación y restauración de datos"},
            {"id": "centro_ayuda", "title": "Centro de Ayuda & Manual", "icon": "", "desc": "Manual de usuario, preguntas frecuentes (FAQ), glosario y atajos"},
            {"id": "novedades_boe", "title": "Monitor BOE & Leyes", "icon": "", "desc": "Novedades fiscales, deducciones y normativa estatal"}
        ]
    }
]


class SubcategoryButton(QPushButton):
    """Botón estéticamente refinado para una subcategoría."""
    
    # Señal personalizada para evitar lambdas/partials
    custom_clicked = pyqtSignal(str, str, str)

    def __init__(self, subcat_data, category_id, parent=None):
        super().__init__(parent)
        self.subcat_data = subcat_data
        self.category_id = category_id
        self.subcat_id = subcat_data["id"]
        self.is_active = False
        
        self.setText(f"  {subcat_data['title']}")
        
        desc = subcat_data.get("desc", "")
        title = subcat_data.get("title", "")
        if desc:
            tooltip_html = f"<div style='padding: 2px;'><b style='color: #00F0FF; font-size: 11px;'>{title}</b><br/><span style='color: #CBD5E1; font-size: 10px;'>{desc}</span></div>"
            self.setToolTip(tooltip_html)
        else:
            self.setToolTip(f"{title}")

        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.update_style()
        
        # Conectar el clic nativo a nuestra emisión controlada
        self.clicked.connect(self._on_internal_click)

    def _on_internal_click(self, checked=False):
        # Emitimos nuestra señal fuerte con los datos de esta instancia
        self.custom_clicked.emit(self.category_id, self.subcat_id, self.subcat_data.get("title", ""))

    def set_active_state(self, active: bool):
        self.is_active = active
        self.update_style()

    def update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(0, 240, 255, 0.22),
                        stop:1 rgba(99, 102, 241, 0.12));
                    border: 1px solid rgba(0, 240, 255, 0.5);
                    border-left: 3px solid #00F0FF;
                    border-radius: 6px;
                    color: #FFFFFF;
                    text-align: left;
                    font-weight: bold;
                    font-size: 13px;
                    padding-left: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    color: #94A3B8;
                    text-align: left;
                    font-size: 13px;
                    padding-left: 8px;
                }
            """)


class CategoryGroupWidget(QWidget):
    """Grupo de categoría colapsable con cabecera interactiva y lista de subcategorías."""
    subcategory_clicked = pyqtSignal(str, str, str)  # cat_id, subcat_id, title
    request_expand_sidebar = pyqtSignal(str) # category_id

    def __init__(self, category_data, parent=None, default_expanded: bool = False):
        super().__init__(parent)
        self.category_data = category_data
        self.category_id = category_data["id"]
        self.is_expanded = default_expanded
        self.is_sidebar_collapsed = True # By default according to new requirements
        self.buttons = {}

        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 2, 0, 4)
        self.main_layout.setSpacing(2)

        # Cabecera de Categoría (botón desplegable)
        self.header_btn = QPushButton()
        self.header_btn.setFixedHeight(44)
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.clicked.connect(self.toggle_expanded)
        
        header_layout = QHBoxLayout(self.header_btn)
        header_layout.setContentsMargins(6, 0, 6, 0)
        header_layout.setSpacing(6)

        self.lbl_icon = QLabel()
        self.lbl_icon.setStyleSheet("background: rgba(0, 240, 255, 0.05); border-radius: 6px;")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setFixedSize(36, 36)
        
        svg_data = SVG_ICONS.get(self.category_id)
        if svg_data:
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtGui import QPainter, QPixmap
            
            renderer = QSvgRenderer(svg_data.encode("utf-8"))
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            self.lbl_icon.setPixmap(pixmap)

        self.lbl_chevron = QLabel("▾" if self.is_expanded else "▸")
        self.lbl_chevron.setStyleSheet("color: #6366F1; font-size: 12px; font-weight: bold;")

        self.lbl_title = QLabel(self.category_data["title"])
        self.lbl_title.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: bold; letter-spacing: 0.5px;")

        header_layout.addWidget(self.lbl_icon)
        header_layout.addWidget(self.lbl_chevron)
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        if self.category_data.get("badge"):
            self.badge = QLabel(self.category_data["badge"])
            self.badge.setProperty("class", "SidebarBadge")
            header_layout.addWidget(self.badge)

        self.header_btn.setProperty("class", "SidebarCategory")
        self.main_layout.addWidget(self.header_btn)

        # Contenedor de subcategorías
        self.subcat_container = QWidget()
        self.subcat_container.setVisible(self.is_expanded)
        self.subcat_layout = QVBoxLayout(self.subcat_container)
        self.subcat_layout.setContentsMargins(10, 2, 0, 2)
        self.subcat_layout.setSpacing(2)

        for subcat in self.category_data["subcategories"]:
            btn = SubcategoryButton(subcat, self.category_id, self.subcat_container)
            btn.custom_clicked.connect(self._forward_click)
            self.subcat_layout.addWidget(btn)
            self.buttons[subcat["id"]] = btn

        self.main_layout.addWidget(self.subcat_container)

    def _forward_click(self, cat_id, sub_id, title):
        self.subcategory_clicked.emit(cat_id, sub_id, title)

    def toggle_expanded(self):
        if self.is_sidebar_collapsed:
            self.request_expand_sidebar.emit(self.category_id)
        else:
            self.set_expanded(not self.is_expanded)

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        if not self.is_sidebar_collapsed:
            self.subcat_container.setVisible(expanded)
        self.lbl_chevron.setText("▾" if expanded else "▸")

    def set_sidebar_collapsed(self, collapsed: bool):
        self.is_sidebar_collapsed = collapsed
        self.lbl_title.setVisible(not collapsed)
        self.lbl_chevron.setVisible(not collapsed)
        if hasattr(self, "badge"):
            self.badge.setVisible(not collapsed)
            
        if collapsed:
            self.subcat_container.setVisible(False)
            self.header_btn.setToolTip(self.category_data["title"])
        else:
            self.subcat_container.setVisible(self.is_expanded)
            self.header_btn.setToolTip("")

    def filter_items(self, query: str) -> bool:
        """Filtra las subcategorías por texto. Retorna True si coincide algo."""
        query = query.strip().lower()
        if not query:
            for btn in self.buttons.values():
                btn.setVisible(True)
            self.setVisible(True)
            self.set_expanded(False)
            return True

        cat_match = (
            query in self.category_data["title"].lower() or
            query in self.category_id.lower()
        )

        any_subcat_match = False
        for subcat in self.category_data["subcategories"]:
            sub_id = subcat["id"]
            btn = self.buttons.get(sub_id)
            if not btn:
                continue

            sub_match = (
                cat_match or
                query in subcat["title"].lower() or
                query in subcat.get("desc", "").lower() or
                query in sub_id.lower()
            )
            btn.setVisible(sub_match)
            if sub_match:
                any_subcat_match = True

        self.setVisible(any_subcat_match)
        if any_subcat_match:
            self.set_expanded(True)

        return any_subcat_match


class AlfonsoSidebarWidget(QFrame):
    """Panel lateral completo con buscador, categorías organizadas y tarjeta de licencia."""
    category_selected = pyqtSignal(str, str, str)  # cat_id, subcat_id, title
    plan_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.current_cat_id = "dashboard"
        self.current_subcat_id = "resumen_ejecutivo"
        self.groups = {}
        self.all_buttons = {}
        self.is_collapsed = True # Default state

        self.setup_ui()

    def setup_ui(self):
        # El estilo principal está en theme.py
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        # Botón de Toggle
        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(4, 0, 4, 12)
        top_layout.setSpacing(12)
        
        self.btn_toggle = QPushButton("》")
        self.btn_toggle.setFixedHeight(36)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle_sidebar)
        self.btn_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.15); 
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 6px; 
                color: #00F0FF; 
                font-weight: bold;
                font-size: 13px;
                padding-left: 8px;
                padding-right: 8px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 0.3); }
        """)
        
        toggle_wrapper = QHBoxLayout()
        toggle_wrapper.addWidget(self.btn_toggle)
        top_layout.addLayout(toggle_wrapper)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: rgba(99, 102, 241, 0.3);")
        top_layout.addWidget(separator)
        
        layout.addLayout(top_layout)

        # 1. Buscador rápido de módulos
        self.search_box = QFrame()
        self.search_box.setProperty("class", "SearchBox")
        
        search_layout = QHBoxLayout(self.search_box)
        search_layout.setContentsMargins(8, 4, 8, 4)
        search_layout.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar módulo o función...")
        self.search_input.setProperty("class", "SearchInput")
        
        self.search_input.textChanged.connect(self.on_search_text_changed)

        self.btn_clear_search = QPushButton("X")
        self.btn_clear_search.setFixedSize(16, 16)
        self.btn_clear_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_search.setVisible(False)
        self.btn_clear_search.setProperty("class", "ClearSearchBtn")
        
        self.btn_clear_search.clicked.connect(self.search_input.clear)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.btn_clear_search)
        layout.addWidget(self.search_box)

        # 2. Área de scroll con las categorías
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Scrollbars are managed by global QSS
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 4, 4)
        container_layout.setSpacing(4)

        for cat_data in SIDEBAR_CATEGORIES:
            if cat_data["id"] == "configuracion":
                container_layout.addStretch()
                
            group = CategoryGroupWidget(cat_data, container, default_expanded=False)
            group.subcategory_clicked.connect(self.on_subcategory_selected)
            group.request_expand_sidebar.connect(self.expand_and_open_category)
            container_layout.addWidget(group)
            self.groups[cat_data["id"]] = group
            for s_id, btn in group.buttons.items():
                self.all_buttons[(cat_data["id"], s_id)] = btn
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # 3. Tarjeta inferior de Plan y Licencia Dinámica
        tier_title = "Plan Profesional"
        tier_sub = "Verifactu SIF + PSD2"
        try:
            from app.utils.license_validator import get_active_license_tier
            t = get_active_license_tier()
            if t == "advisor":
                tier_title = "Plan Gestoría / Advisor"
                tier_sub = "Multi-inquilino + FacturaE B2B"
            elif t == "pro":
                tier_title = "Plan Profesional"
                tier_sub = "Conciliación + Verifactu SIF"
            else:
                tier_title = "Plan Autónomo Basic"
                tier_sub = "Verifactu + Modelos AEAT"
        except Exception:
            pass

        self.plan_card = QFrame()
        self.plan_card.setProperty("class", "PlanCard")
        
        plan_layout = QVBoxLayout(self.plan_card)
        plan_layout.setContentsMargins(6, 6, 6, 6)
        plan_layout.setSpacing(2)

        self.lbl_plan_title = QLabel(tier_title)
        self.lbl_plan_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFB800;")
        self.lbl_plan_sub = QLabel(tier_sub)
        self.lbl_plan_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")

        btn_plan = QPushButton("Gestionar Licencia")
        btn_plan.setFixedHeight(22)
        btn_plan.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_plan.clicked.connect(self.plan_clicked.emit)
        btn_plan.setProperty("class", "PlanButton")

        plan_layout.addWidget(self.lbl_plan_title)
        plan_layout.addWidget(self.lbl_plan_sub)
        plan_layout.addWidget(btn_plan)
        layout.addWidget(self.plan_card)

        # Aplicar el estado inicial
        self.apply_collapsed_state()

        # Establecer selección inicial por defecto sin expandir grupos
        self.set_active("dashboard", "resumen_ejecutivo", expand_group=False)

    def toggle_sidebar(self):
        self.is_collapsed = not self.is_collapsed
        self.apply_collapsed_state()
        
    def expand_and_open_category(self, cat_id: str):
        if self.is_collapsed:
            self.is_collapsed = False
            self.apply_collapsed_state()
        if cat_id in self.groups:
            self.groups[cat_id].set_expanded(True)

    def apply_collapsed_state(self):
        if self.is_collapsed:
            self.setFixedWidth(64)
            self.btn_toggle.setText("》")
            self.btn_toggle.setMaximumWidth(36)
            self.search_box.setVisible(False)
            self.plan_card.setVisible(False)
        else:
            self.setFixedWidth(240)
            self.btn_toggle.setText("《 Contraer Panel")
            self.btn_toggle.setMaximumWidth(16777215)
            self.btn_toggle.setMinimumWidth(0)
            self.search_box.setVisible(True)
            self.plan_card.setVisible(True)
            
        for group in self.groups.values():
            group.set_sidebar_collapsed(self.is_collapsed)

    def on_search_text_changed(self, text: str):
        self.btn_clear_search.setVisible(bool(text))
        for group in self.groups.values():
            group.filter_items(text)

    def on_subcategory_selected(self, cat_id: str, subcat_id: str, title: str):
        print(f"[SIDEBAR EMIT] cat_id={cat_id!r}  subcat_id={subcat_id!r}  title={title!r}")
        self.set_active(cat_id, subcat_id, expand_group=True)
        self.category_selected.emit(cat_id, subcat_id, title)

    def set_active(self, cat_id: str, subcat_id: str, expand_group: bool = False):
        """Marca una subcategoría como activa visualmente."""
        self.current_cat_id = cat_id
        self.current_subcat_id = subcat_id

        for (c_id, s_id), btn in self.all_buttons.items():
            is_match = (c_id == cat_id and s_id == subcat_id)
            btn.set_active_state(is_match)

        # Si se solicita explícitamente, asegurar que el grupo esté expandido
        if expand_group and cat_id in self.groups:
            self.groups[cat_id].set_expanded(True)

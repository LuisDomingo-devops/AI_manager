"""
ALFONSO SIDEBAR WIDGET — Panel Lateral Jerárquico por Categorías y Subcategorías
Proporciona navegación estructurada para todas las funcionalidades de Alfonso Autónomo.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QCursor, QIcon


# Definición completa de la arquitectura de navegación de Alfonso Autónomo
SIDEBAR_CATEGORIES = [
    {
        "id": "dashboard",
        "title": "PANEL DE CONTROL",
        "icon": "",
        "badge": "En Vivo",
        "subcategories": [
            {
                "id": "resumen_ejecutivo",
                "title": "Resumen Ejecutivo",
                "icon": "",
                "desc": "KPIs en tiempo real, Donut Chart y alertas AEAT"
            },
            {
                "id": "kpis_analitica",
                "title": "Analítica & KPIs",
                "icon": "",
                "desc": "Métricas avanzadas, márgenes y evolución trimestral"
            },
            {
                "id": "prevision_cashflow",
                "title": "Previsión Tesorería",
                "icon": "",
                "desc": "Cash Flow a 30/60/90 días y cobros previstos"
            }
        ]
    },
    {
        "id": "facturacion",
        "title": "FACTURACIÓN & VENTAS",
        "icon": "",
        "badge": "Veri*Factu",
        "subcategories": [
            {
                "id": "facturas_emitidas",
                "title": "Facturas Emitidas",
                "icon": "",
                "desc": "Libro de ingresos (7XX), estados de cobro y exportación"
            },
            {
                "id": "nueva_factura_b2b",
                "title": "Nueva Factura / FacturaE",
                "icon": "",
                "desc": "Emisión rápida, FacturaE B2B XML y Ley Crea y Crece"
            },
            {
                "id": "verifactu_sif",
                "title": "Veri*Factu & Huella Hash",
                "icon": "",
                "desc": "Registro inalterable RD 1007/2023 y QR de cotejo AEAT"
            }
        ]
    },
    {
        "id": "gastos",
        "title": "GASTOS & COMPRAS",
        "icon": "",
        "badge": "Deducible",
        "subcategories": [
            {
                "id": "libro_gastos",
                "title": "Libro de Gastos",
                "icon": "",
                "desc": "Libro de compras (6XX) y partidas deducibles"
            },
            {
                "id": "ocr_extraccion",
                "title": "Captura & OCR IA",
                "icon": "",
                "desc": "Extracción automática de tickets y facturas recibidas"
            },
            {
                "id": "registro_manual",
                "title": "Registro Manual",
                "icon": "",
                "desc": "Inserción directa de gastos y cuota de autónomo RETA"
            }
        ]
    },
    {
        "id": "bancos",
        "title": "BANCA & TESORERÍA",
        "icon": "",
        "badge": "PSD2",
        "subcategories": [
            {
                "id": "conciliacion_bancaria",
                "title": "Conciliación Bancaria",
                "icon": "",
                "desc": "Emparejamiento inteligente de apuntes y facturas"
            },
            {
                "id": "conexiones_psd2",
                "title": "Cuentas Conectadas",
                "icon": "",
                "desc": "Banca abierta Open Banking y sincronización de saldos"
            },
            {
                "id": "transferencias_pagos",
                "title": "Emisión de Pagos",
                "icon": "",
                "desc": "Transferencias a proveedores y remesas SEPA"
            }
        ]
    },
    {
        "id": "impuestos",
        "title": "FISCALIDAD & AEAT",
        "icon": "",
        "badge": "Oficial",
        "subcategories": [
            {
                "id": "modelos_trimestrales",
                "title": "Modelos 303 y 130",
                "icon": "",
                "desc": "Autoliquidación trimestral de IVA e IRPF en tiempo real"
            },
            {
                "id": "automatizacion_aeat",
                "title": "Sede Electrónica AEAT",
                "icon": "",
                "desc": "Asistente de presentación telemática con Playwright"
            },
            {
                "id": "calendario_fiscal",
                "title": "Calendario Fiscal",
                "icon": "",
                "desc": "Vencimientos oficiales, plazos tributarios y alarmas"
            },
            {
                "id": "novedades_boe",
                "title": "Monitor BOE & Leyes",
                "icon": "",
                "desc": "Novedades fiscales, deducciones y normativa estatal"
            }
        ]
    },
    {
        "id": "laboral",
        "title": "LABORAL & NÓMINAS",
        "icon": "",
        "badge": "TGSS",
        "subcategories": [
            {
                "id": "empleados_contratos",
                "title": "Empleados & Contratos",
                "icon": "",
                "desc": "Gestión de plantilla, altas y contratos de trabajo"
            },
            {
                "id": "generador_nominas",
                "title": "Generador de Nóminas",
                "icon": "",
                "desc": "Cálculo de IRPF/SS y generación de nóminas PDF"
            },
            {
                "id": "afiliacion_tgss",
                "title": "Seguridad Social TGSS",
                "icon": "",
                "desc": "Ficheros AFI/CRA, cotizaciones y cuota RETA"
            }
        ]
    },
    {
        "id": "documentos",
        "title": "DOCUMENTOS & ARCHIVO",
        "icon": "",
        "badge": "Custodia",
        "subcategories": [
            {
                "id": "archivo_fiscal",
                "title": "Archivo Digital",
                "icon": "",
                "desc": "Explorador organizado por ejercicios y trimestres"
            },
            {
                "id": "visor_documental",
                "title": "Visor Documental IA",
                "icon": "",
                "desc": "Previsualización con metadatos contables extraídos"
            },
            {
                "id": "libros_oficiales_aeat",
                "title": "Libros Registro Oficiales",
                "icon": "",
                "desc": "Exportador Excel/CSV normalizado para la AEAT"
            }
        ]
    },
    {
        "id": "comunicacion",
        "title": "ASISTENTE & COMUNICACIÓN",
        "icon": "",
        "badge": "AI 2.0",
        "subcategories": [
            {
                "id": "asistente_ia",
                "title": "Chat IA & Voz Alfonso",
                "icon": "",
                "desc": "Asistente conversacional, órdenes y comandos"
            },
            {
                "id": "correo_inteligente",
                "title": "Alfonso Mail",
                "icon": "",
                "desc": "Bandeja de correo, extracción de facturas y respuestas"
            },
            {
                "id": "agenda_citas",
                "title": "Agenda & Citas",
                "icon": "",
                "desc": "Citas previas en Administraciones y recordatorios"
            },
            {
                "id": "proyectos_sesiones",
                "title": "Proyectos & Sesiones",
                "icon": "",
                "desc": "Gestor multi-sesión de proyectos de trabajo"
            }
        ]
    },
    {
        "id": "cumplimiento",
        "title": "AUDITORÍA & ASESORÍA",
        "icon": "",
        "badge": "Audit",
        "subcategories": [
            {
                "id": "declaracion_sif",
                "title": "Declaración SIF",
                "icon": "",
                "desc": "Acreditación y declaración responsable RD 1007/2023"
            },
            {
                "id": "auditoria_inmutabilidad",
                "title": "Auditoría de Inmutabilidad",
                "icon": "",
                "desc": "Verificación criptográfica y registro inalterable"
            },
            {
                "id": "panel_asesor",
                "title": "Panel Gestoría / Advisor",
                "icon": "",
                "desc": "Gestión multi-empresa y multi-inquilino"
            }
        ]
    },
    {
        "id": "sistema",
        "title": "SISTEMA & CONFIGURACIÓN",
        "icon": "",
        "badge": "Ajustes",
        "subcategories": [
            {
                "id": "perfil_fiscal",
                "title": "Perfil del Autónomo",
                "icon": "",
                "desc": "NIF, actividad IAE, tipo IRPF y domicilio fiscal"
            },
            {
                "id": "voz_modelos_ia",
                "title": "IA & Dispositivos",
                "icon": "",
                "desc": "Configuración de audio, Whisper y modelo de IA"
            },
            {
                "id": "copias_seguridad",
                "title": "Copias de Seguridad",
                "icon": "",
                "desc": "Snapshots locales, exportación y restauración de datos"
            },
            {
                "id": "suscripcion_licencia",
                "title": "Suscripción & Licencia",
                "icon": "",
                "desc": "Detalles del plan activo y ampliación de licencia"
            },
            {
                "id": "centro_ayuda",
                "title": "Centro de Ayuda & Manual",
                "icon": "",
                "desc": "Manual de usuario, preguntas frecuentes (FAQ), glosario y atajos"
            }
        ]
    }
]


class SubcategoryButton(QPushButton):
    """Botón estéticamente refinado para una subcategoría."""
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
            tooltip_html = f"<div style='font-family: Segoe UI, sans-serif; padding: 2px;'><b style='color: #00F0FF; font-size: 11px;'>{title}</b><br/><span style='color: #CBD5E1; font-size: 10px;'>{desc}</span></div>"
            self.setToolTip(tooltip_html)
        else:
            self.setToolTip(f"{title}")

        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()

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
                    font-size: 11px;
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
                    font-size: 11px;
                    padding-left: 8px;
                }
                QPushButton:hover {
                    color: #F1F5F9;
                    background-color: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                }
            """)


class CategoryGroupWidget(QWidget):
    """Grupo de categoría colapsable con cabecera interactiva y lista de subcategorías."""
    subcategory_clicked = pyqtSignal(str, str, str)  # cat_id, subcat_id, title

    def __init__(self, category_data, parent=None, default_expanded: bool = False):
        super().__init__(parent)
        self.category_data = category_data
        self.category_id = category_data["id"]
        self.is_expanded = default_expanded
        self.buttons = {}

        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 2, 0, 4)
        self.main_layout.setSpacing(2)

        # Cabecera de Categoría (botón desplegable)
        self.header_btn = QPushButton()
        self.header_btn.setFixedHeight(28)
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.clicked.connect(self.toggle_expanded)

        header_layout = QHBoxLayout(self.header_btn)
        header_layout.setContentsMargins(6, 0, 6, 0)
        header_layout.setSpacing(6)

        self.lbl_chevron = QLabel("▾" if self.is_expanded else "▸")
        self.lbl_chevron.setStyleSheet("color: #6366F1; font-size: 10px; font-weight: bold;")

        self.lbl_title = QLabel(self.category_data["title"])
        self.lbl_title.setStyleSheet("color: #E2E8F0; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")

        header_layout.addWidget(self.lbl_chevron)
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        if self.category_data.get("badge"):
            badge = QLabel(self.category_data["badge"])
            badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(99, 102, 241, 0.15);
                    color: #818CF8;
                    border: 1px solid rgba(99, 102, 241, 0.3);
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 8px;
                    font-weight: bold;
                }
            """)
            header_layout.addWidget(badge)

        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(99, 102, 241, 0.08);
                border-color: rgba(99, 102, 241, 0.2);
            }
        """)

        self.main_layout.addWidget(self.header_btn)

        # Contenedor de subcategorías (cerrado/oculto por defecto)
        self.subcat_container = QWidget()
        self.subcat_container.setVisible(self.is_expanded)
        self.subcat_layout = QVBoxLayout(self.subcat_container)
        self.subcat_layout.setContentsMargins(10, 2, 0, 2)
        self.subcat_layout.setSpacing(2)

        for subcat in self.category_data["subcategories"]:
            btn = SubcategoryButton(subcat, self.category_id, self.subcat_container)
            btn.clicked.connect(
                lambda checked=False, s_id=subcat["id"], s_title=subcat["title"]:
                self.subcategory_clicked.emit(self.category_id, s_id, s_title)
            )
            self.subcat_layout.addWidget(btn)
            self.buttons[subcat["id"]] = btn

        self.main_layout.addWidget(self.subcat_container)

    def toggle_expanded(self):
        self.set_expanded(not self.is_expanded)

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        self.subcat_container.setVisible(expanded)
        self.lbl_chevron.setText("▾" if expanded else "▸")

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
        self.setFixedWidth(240)
        self.current_cat_id = "dashboard"
        self.current_subcat_id = "resumen_ejecutivo"
        self.groups = {}
        self.all_buttons = {}

        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            #Sidebar {
                background-color: #070B14;
                border-right: 1px solid rgba(255, 255, 255, 0.06);
            }
            QToolTip {
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid rgba(0, 240, 255, 0.5);
                border-radius: 6px;
                padding: 6px 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        # 1. Buscador rápido de módulos
        search_box = QFrame()
        search_box.setStyleSheet("""
            QFrame {
                background-color: #0F172A;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
            QFrame:focus-within {
                border: 1px solid #00F0FF;
            }
        """)
        search_layout = QHBoxLayout(search_box)
        search_layout.setContentsMargins(8, 4, 8, 4)
        search_layout.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar módulo o función...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 11px;
                padding: 2px 6px;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_text_changed)

        self.btn_clear_search = QPushButton("X")
        self.btn_clear_search.setFixedSize(16, 16)
        self.btn_clear_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_search.setVisible(False)
        self.btn_clear_search.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 8px;
                color: #94A3B8;
                font-size: 9px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
                color: #FFFFFF;
            }
        """)
        self.btn_clear_search.clicked.connect(self.search_input.clear)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.btn_clear_search)
        layout.addWidget(search_box)

        # 2. Área de scroll con las categorías
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(15, 23, 42, 0.3);
                width: 5px;
                margin: 0px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(99, 102, 241, 0.4);
                min-height: 15px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00F0FF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 4, 4)
        container_layout.setSpacing(4)

        for cat_data in SIDEBAR_CATEGORIES:
            group = CategoryGroupWidget(cat_data, container, default_expanded=False)
            group.subcategory_clicked.connect(self.on_subcategory_selected)
            container_layout.addWidget(group)
            self.groups[cat_data["id"]] = group
            for s_id, btn in group.buttons.items():
                self.all_buttons[(cat_data["id"], s_id)] = btn

        container_layout.addStretch()
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

        plan_card = QFrame()
        plan_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(245, 158, 11, 0.08),
                    stop:1 rgba(99, 102, 241, 0.08));
                border: 1px solid rgba(245, 158, 11, 0.25);
                border-radius: 8px;
                padding: 6px;
            }
        """)
        plan_layout = QVBoxLayout(plan_card)
        plan_layout.setContentsMargins(6, 6, 6, 6)
        plan_layout.setSpacing(2)

        self.lbl_plan_title = QLabel(tier_title)
        self.lbl_plan_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #FFB800;")
        self.lbl_plan_sub = QLabel(tier_sub)
        self.lbl_plan_sub.setStyleSheet("font-size: 9px; color: #94A3B8;")

        btn_plan = QPushButton("Gestionar Licencia")
        btn_plan.setFixedHeight(22)
        btn_plan.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_plan.clicked.connect(self.plan_clicked.emit)
        btn_plan.setStyleSheet("""
            QPushButton {
                background: rgba(245, 158, 11, 0.15);
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 4px;
                color: #FFB800;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(245, 158, 11, 0.25);
                color: #FFFFFF;
            }
        """)
        plan_layout.addWidget(self.lbl_plan_title)
        plan_layout.addWidget(self.lbl_plan_sub)
        plan_layout.addWidget(btn_plan)
        layout.addWidget(plan_card)

        # Establecer selección inicial por defecto sin expandir grupos
        self.set_active("dashboard", "resumen_ejecutivo", expand_group=False)

    def on_search_text_changed(self, text: str):
        self.btn_clear_search.setVisible(bool(text))
        for group in self.groups.values():
            group.filter_items(text)

    def on_subcategory_selected(self, cat_id: str, subcat_id: str, title: str):
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

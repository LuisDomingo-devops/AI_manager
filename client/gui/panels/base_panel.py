from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt
from client.gui.theme import HoverAnimationFilter

class AlfonsoBasePanel(QFrame):
    """
    Clase base unificada para todos los paneles centrales.
    Proporciona un diseño consistente con márgenes, colores (heredados por clase)
    y una cabecera opcional estandarizada.
    
    Uso:
    - Heredar de esta clase.
    - Los widgets específicos del panel deben agregarse a `self.content_layout`.
    """
    def __init__(self, parent=None, title="", subtitle="", min_height=0):
        super().__init__(parent)
        self.setProperty("class", "HUDPanel") # Usa la clase estándar de panel
        HoverAnimationFilter(self) # Añade el efecto de profundidad

        if min_height:
            self.setMinimumHeight(min_height)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 16, 18, 16)
        self.main_layout.setSpacing(14)

        if title or subtitle:
            self._build_header(title, subtitle)

        # Contenedor para el contenido del panel hijo
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        
        self.main_layout.addWidget(self.content_container, 1)

    def _build_header(self, title, subtitle):
        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        header_col.setSpacing(4)

        if title:
            lbl_title = QLabel(title)
            lbl_title.setProperty("class", "LblTitle")
            header_col.addWidget(lbl_title)

        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setProperty("class", "LblSubtitle")
            header_col.addWidget(lbl_sub)

        header_row.addLayout(header_col)
        header_row.addStretch()
        self.main_layout.addLayout(header_row)

    def add_widget(self, widget, stretch=0, alignment=Qt.AlignmentFlag.AlignTop):
        """Método de conveniencia para añadir widgets al contenido."""
        self.content_layout.addWidget(widget, stretch, alignment)

    def add_layout(self, layout, stretch=0):
        """Método de conveniencia para añadir layouts al contenido."""
        self.content_layout.addLayout(layout, stretch)

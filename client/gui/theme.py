from PyQt6.QtGui import QFont, QFontDatabase, QColor
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect
from PyQt6.QtCore import QObject, QEvent, QPropertyAnimation, QEasingCurve

# Paleta de colores principal (Glassmorphism Dark)
COLOR_BACKGROUND = "rgba(15, 23, 42, 1.0)"  # Slate 900
COLOR_PANEL_BG = "rgba(30, 41, 59, 0.95)" # Slate 800 (transparente)
COLOR_BORDER = "rgba(255, 255, 255, 0.1)"
COLOR_PRIMARY = "#6366F1"    # Indigo 500
COLOR_SUCCESS = "#10B981"    # Emerald 500
COLOR_DANGER = "#EF4444"     # Red 500
COLOR_TEXT_MAIN = "#F1F5F9"  # Slate 100
COLOR_TEXT_MUTED = "#94A3B8" # Slate 400
COLOR_ACCENT_CYAN = "#00F0FF"

# Definición del estilo global (QSS)
GLOBAL_QSS = f"""
/* ===== ESTILOS GLOBALES ===== */
QWidget {{
    color: {COLOR_TEXT_MAIN};
    font-family: "Segoe UI", "Roboto", "Inter", sans-serif;
}}

/* Paneles y Tarjetas (HUDPanel) */
QFrame#HUDPanel {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
}}

/* Botones principales */
QPushButton {{
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px 16px;
    color: {COLOR_TEXT_MAIN};
}}

QPushButton:hover {{
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
}}

QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 0.02);
}}

/* Botones Primarios */
QPushButton.PrimaryButton {{
    background-color: rgba(99, 102, 241, 0.2);
    border: 1px solid {COLOR_PRIMARY};
    color: {COLOR_PRIMARY};
    font-weight: bold;
}}
QPushButton.PrimaryButton:hover {{
    background-color: rgba(99, 102, 241, 0.3);
}}

/* Botones de Alerta/Peligro */
QPushButton.DangerButton {{
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: {COLOR_DANGER};
}}
QPushButton.DangerButton:hover {{
    background-color: rgba(239, 68, 68, 0.2);
}}

/* Campos de Texto (QLineEdit, QTextEdit) */
QLineEdit, QTextEdit {{
    background-color: rgba(15, 23, 42, 0.6);
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px;
    color: {COLOR_TEXT_MAIN};
    selection-background-color: {COLOR_PRIMARY};
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {COLOR_PRIMARY};
    background-color: rgba(15, 23, 42, 0.8);
}}

/* Títulos y Subtítulos */
QLabel.TitleLabel {{
    font-size: 16px;
    font-weight: bold;
    color: {COLOR_PRIMARY};
    letter-spacing: 0.5px;
}}

QLabel.SubtitleLabel {{
    font-size: 11px;
    color: {COLOR_TEXT_MUTED};
}}

/* Splitters (Divisores) */
QSplitter::handle {{
    background-color: rgba(99, 102, 241, 0.2);
}}
QSplitter::handle:hover {{
    background-color: rgba(99, 102, 241, 0.5);
}}

/* Barras de Desplazamiento (Scrollbars) */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px 0px 0px 0px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.2);
    min-height: 20px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.4);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ===== ESTILOS ESPECÍFICOS: SIDEBAR ===== */
QFrame#Sidebar {{
    background-color: #070B14;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}}

QToolTip {{
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1px solid rgba(0, 240, 255, 0.5);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}}

QLabel.SidebarBadge {{
    background-color: rgba(99, 102, 241, 0.15);
    color: #818CF8;
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 3px;
    padding: 1px 4px;
    font-size: 9px;
    font-weight: bold;
}}

QPushButton.SidebarCategory {{
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 6px;
    text-align: left;
    padding: 4px;
}}
QPushButton.SidebarCategory:hover {{
    background-color: rgba(99, 102, 241, 0.08);
    border-color: rgba(99, 102, 241, 0.2);
}}

QFrame.SearchBox {{
    background-color: #0F172A;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
}}
QFrame.SearchBox:focus-within {{
    border: 1px solid #00F0FF;
}}

QLineEdit.SearchInput {{
    background: transparent;
    border: none;
    color: #FFFFFF;
    font-size: 13px;
    padding: 2px 6px;
}}

QPushButton.ClearSearchBtn {{
    background: rgba(255, 255, 255, 0.1);
    border: none;
    border-radius: 8px;
    color: #94A3B8;
    font-size: 11px;
    font-weight: bold;
    padding: 0;
}}
QPushButton.ClearSearchBtn:hover {{
    background: rgba(239, 68, 68, 0.3);
    color: #FFFFFF;
}}

QFrame.PlanCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(245, 158, 11, 0.08),
        stop:1 rgba(99, 102, 241, 0.08));
    border: 1px solid rgba(245, 158, 11, 0.25);
    border-radius: 8px;
}}

QPushButton.PlanButton {{
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 4px;
    color: #FFB800;
    font-size: 11px;
    font-weight: bold;
    padding: 4px;
}}
QPushButton.PlanButton:hover {{
    background-color: rgba(245, 158, 11, 0.25);
    color: #FFFFFF;
}}

/* ===== ESTILOS ESPECÍFICOS: DEV STUDIO (MUTHUR) ===== */
QWidget#DevStudio {{
    background-color: #030406;
    color: #00F0FF;
}}
QWidget#DevStudio QLabel {{
    color: #00F0FF;
}}
QWidget#DevStudio QPushButton {{
    background-color: rgba(255, 184, 0, 15);
    color: #FFB800;
    border: 1px solid rgba(255, 184, 0, 50);
    border-radius: 3px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: bold;
}}
QWidget#DevStudio QPushButton:hover {{
    background-color: rgba(255, 184, 0, 40);
    color: #FFFFFF;
    border-color: #FFB800;
}}
QWidget#DevStudio QPushButton:pressed {{
    background-color: #FFB800;
    color: #000000;
}}
QWidget#DevStudio QListWidget {{
    border: 1px solid rgba(0, 240, 255, 30);
    background-color: rgba(5, 7, 10, 200);
    color: #FFFFFF;
}}
QWidget#DevStudio QListWidget::item {{
    border-bottom: 1px solid rgba(0, 240, 255, 15);
    padding: 8px;
}}
QWidget#DevStudio QListWidget::item:selected {{
    background-color: rgba(0, 240, 255, 25);
    color: #FFFFFF;
    border: 1px solid #00F0FF;
}}
QWidget#DevStudio QTabWidget::pane {{
    border: 1px solid rgba(0, 240, 255, 30);
    background-color: #030406;
}}
QWidget#DevStudio QTabBar::tab {{
    background-color: rgba(5, 7, 10, 255);
    border: 1px solid rgba(0, 240, 255, 30);
    color: #00F0FF;
    padding: 6px 15px;
    font-size: 11px;
}}
QWidget#DevStudio QTabBar::tab:selected {{
    background-color: #00F0FF;
    color: #000000;
    font-weight: bold;
}}
QWidget#DevStudio QPlainTextEdit {{
    background-color: #05070a;
    color: #00FF66;
    border: none;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}}
QWidget#DevStudio QLineEdit {{
    background-color: #05070a;
    color: #00FF66;
    border: 1px solid rgba(0, 240, 255, 30);
    padding: 6px;
    font-size: 11px;
}}
QFrame#EditorContainer {{
    border: 2px solid #00F0FF;
    background-color: #030406;
}}
QLabel.DevHeaderTitle {{
    font-size: 13px;
    font-weight: bold;
    color: #00F0FF;
    letter-spacing: 1px;
}}
QLabel.DevPanelTitle {{
    font-weight: bold;
    font-size: 10px;
    color: rgba(0, 240, 255, 70);
}}
QLabel.DevTerminalTitle {{
    font-weight: bold;
    font-size: 10px;
    color: #FFB800;
}}
QPushButton.DevDangerBtn {{
    color: #FF0055;
    border-color: rgba(255, 0, 85, 40);
}}
QPushButton.DevSuccessBtn {{
    color: #00FF66;
    border-color: rgba(0, 255, 102, 50);
}}
QSplitter.DevSplitter::handle {{
    background-color: rgba(0, 240, 255, 30);
}}
QFrame#Separator {{
    border: 1px solid rgba(0, 240, 255, 30);
}}
"""

def apply_theme(app: QApplication):
    """Aplica la tipografía y el QSS global a la aplicación."""
    # Tipografía base (Segoe UI estandarizada para todos)
    # En el futuro, aquí se puede cargar 'Inter.ttf' con QFontDatabase
    base_font = QFont("Segoe UI", 12)
    app.setFont(base_font)
    
    app.setStyleSheet(GLOBAL_QSS)

def apply_glass_shadow(widget, blur_radius=20, y_offset=2, alpha=150):
    """Aplica un efecto de sombra sutil estilo glassmorphism a un widget."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setXOffset(0)
    shadow.setYOffset(y_offset)
    # Glow cian/indigo para que destaque en fondo oscuro (Muthur/Glassmorphism)
    shadow.setColor(QColor(0, 240, 255, alpha))
    widget.setGraphicsEffect(shadow)
    return shadow

class HoverAnimationFilter(QObject):
    """
    Filtro de eventos que anima la sombra de un widget al pasar el ratón.
    Aumenta el desenfoque para dar un efecto de elevación (depth).
    """
    def __init__(self, target_widget, base_blur=15, hover_blur=40, duration=250):
        super().__init__(target_widget)
        self.widget = target_widget
        self.base_blur = base_blur
        self.hover_blur = hover_blur
        
        # Obtenemos o creamos el efecto de sombra
        self.shadow = target_widget.graphicsEffect()
        if not isinstance(self.shadow, QGraphicsDropShadowEffect):
            self.shadow = apply_glass_shadow(target_widget, blur_radius=self.base_blur)
            
        self.animation = QPropertyAnimation(self.shadow, b"blurRadius")
        self.animation.setDuration(duration)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # Instalamos el filtro en el widget objetivo
        self.widget.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if obj is self.widget:
            if event.type() == QEvent.Type.Enter:
                self.animation.stop()
                self.animation.setStartValue(self.shadow.blurRadius())
                self.animation.setEndValue(self.hover_blur)
                self.animation.start()
            elif event.type() == QEvent.Type.Leave:
                self.animation.stop()
                self.animation.setStartValue(self.shadow.blurRadius())
                self.animation.setEndValue(self.base_blur)
                self.animation.start()
        return super().eventFilter(obj, event)


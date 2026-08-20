import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient, QPixmap, QPainterPath, QIcon
from PyQt6.QtCore import Qt, QRectF, QSize

class DonutChartWidget(QWidget):
    """Gráfico circular estilo Donut para el Estado de Facturas."""
    def __init__(self, total=128, pagadas=108, pendientes=15, rechazadas=5, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self.total = total
        self.pagadas = pagadas
        self.pendientes = pendientes
        self.rechazadas = rechazadas

    def set_values(self, total, pagadas, pendientes, rechazadas):
        self.total = total
        self.pagadas = pagadas
        self.pendientes = pendientes
        self.rechazadas = rechazadas
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        side = min(width, height) - 20
        rect = QRectF((width - side) / 2.0, (height - side) / 2.0, side, side)
        
        # Donut dimensions
        pen_width = 14
        
        # Draw background ring
        painter.setPen(QPen(QColor(30, 41, 59, 100), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
        
        # Calculate angles (16ths of a degree for QPainter.drawArc)
        if self.total <= 0:
            return
            
        angle_pagadas = int((self.pagadas / self.total) * 360 * 16)
        angle_pendientes = int((self.pendientes / self.total) * 360 * 16)
        angle_rechazadas = int((self.rechazadas / self.total) * 360 * 16)
        
        start_angle = 90 * 16  # start at 12 o'clock
        
        # 1. Pagadas (Green/Emerald: #10B981)
        if angle_pagadas > 0:
            pen = QPen(QColor("#10B981"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, start_angle, -angle_pagadas)
            start_angle -= angle_pagadas
            
        # 2. Pendientes (Yellow/Amber: #F59E0B)
        if angle_pendientes > 0:
            pen = QPen(QColor("#F59E0B"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, start_angle, -angle_pendientes)
            start_angle -= angle_pendientes
            
        # 3. Rechazadas (Red/Rose: #EF4444)
        if angle_rechazadas > 0:
            pen = QPen(QColor("#EF4444"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, start_angle, -angle_rechazadas)
            
        # Central text
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self.total))
        
        font_sub = QFont("Segoe UI", 8, QFont.Weight.Normal)
        painter.setFont(font_sub)
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom, "\n\nTotal")


class SparklineWidget(QWidget):
    """Gráfico de línea de tendencia simple para meter en la base de las tarjetas KPI."""
    def __init__(self, color_hex="#10B981", points=None, is_bar=False, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.points = points or [10, 15, 8, 12, 20, 16, 25, 22, 30]
        self.is_bar = is_bar
        self.setFixedHeight(30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        if not self.points:
            return
            
        max_val = max(self.points) or 1.0
        min_val = min(self.points)
        val_range = (max_val - min_val) or 1.0
        
        color = QColor(self.color_hex)
        
        if self.is_bar:
            # Draw tiny bars like in the references
            num_bars = len(self.points)
            bar_w = max(2, (width - (num_bars * 2)) // num_bars)
            for i, val in enumerate(self.points):
                bar_h = int((val / max_val) * (height - 4))
                x = i * (bar_w + 2)
                y = height - bar_h
                painter.fillRect(x, y, bar_w, bar_h, QBrush(color))
        else:
            # Draw line with gradient area underneath
            from PyQt6.QtGui import QPainterPath, QLinearGradient
            path = QPainterPath()
            step_x = width / (len(self.points) - 1)
            
            for i, val in enumerate(self.points):
                # normalize value to fit height
                y = height - 2 - int(((val - min_val) / val_range) * (height - 6))
                x = i * step_x
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            
            # Area underneath
            area_path = QPainterPath(path)
            area_path.lineTo(width, height)
            area_path.lineTo(0, height)
            area_path.closeSubpath()
            
            grad = QLinearGradient(0, 0, 0, height)
            grad.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 50))
            grad.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            
            painter.fillPath(area_path, QBrush(grad))
            
            # Line stroke
            painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(path)


def create_professional_icon(icon_type: str, color_hex: str, size: int = 36) -> QIcon:
    """Genera un QIcon vectorial profesional y nítido para acciones de la interfaz sin utilizar emojis."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    color = QColor(color_hex)
    pen = QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    w, h = size, size
    pad = 6.0

    if icon_type == "invoice":
        # Documento contable con esquina doblada y signo más (+)
        path = QPainterPath()
        path.moveTo(pad + 3, pad)
        path.lineTo(w - pad - 6, pad)
        path.lineTo(w - pad, pad + 6)
        path.lineTo(w - pad, h - pad)
        path.lineTo(pad + 3, h - pad)
        path.closeSubpath()
        painter.drawPath(path)
        # Pliegue
        painter.drawLine(int(w - pad - 6), int(pad), int(w - pad - 6), int(pad + 6))
        painter.drawLine(int(w - pad - 6), int(pad + 6), int(w - pad), int(pad + 6))
        # Signo + en el centro
        cx, cy = w / 2.0, h / 2.0 + 2
        painter.drawLine(int(cx - 4), int(cy), int(cx + 4), int(cy))
        painter.drawLine(int(cx), int(cy - 4), int(cx), int(cy + 4))

    elif icon_type == "bank":
        # Fachada bancaria clásica con frontón y 3 columnas
        roof = QPainterPath()
        roof.moveTo(pad + 2, pad + 6)
        roof.lineTo(w / 2.0, pad + 1)
        roof.lineTo(w - pad - 2, pad + 6)
        roof.closeSubpath()
        painter.drawPath(roof)
        # Columnas
        top_y = int(pad + 9)
        bot_y = int(h - pad - 4)
        c1 = int(pad + 5)
        c2 = int(w / 2.0)
        c3 = int(w - pad - 5)
        painter.drawLine(c1, top_y, c1, bot_y)
        painter.drawLine(c2, top_y, c2, bot_y)
        painter.drawLine(c3, top_y, c3, bot_y)
        # Base
        painter.drawLine(int(pad + 2), bot_y, int(w - pad - 2), bot_y)
        painter.drawLine(int(pad), int(h - pad), int(w - pad), int(h - pad))

    elif icon_type == "tax":
        # Formulario fiscal AEAT con símbolo %
        rect = QRectF(pad + 1, pad, w - 2*pad - 2, h - 2*pad)
        painter.drawRoundedRect(rect, 4, 4)
        painter.drawLine(int(pad + 6), int(h - pad - 5), int(w - pad - 6), int(pad + 5))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QRectF(pad + 5, pad + 4, 3.5, 3.5))
        painter.drawEllipse(QRectF(w - pad - 8.5, h - pad - 7.5, 3.5, 3.5))

    elif icon_type == "archive":
        # Carpeta / Archivo documental
        path = QPainterPath()
        path.moveTo(pad, pad + 5)
        path.lineTo(pad + 7, pad + 5)
        path.lineTo(pad + 10, pad + 8)
        path.lineTo(w - pad, pad + 8)
        path.lineTo(w - pad, h - pad)
        path.lineTo(pad, h - pad)
        path.closeSubpath()
        painter.drawPath(path)
        mid_y = int(h / 2.0 + 3)
        painter.drawLine(int(pad + 5), mid_y, int(w - pad - 5), mid_y)
        painter.drawLine(int(w / 2.0 - 3), mid_y + 4, int(w / 2.0 + 3), mid_y + 4)

    elif icon_type == "help":
        # Símbolo de ayuda circular con '?'
        rect = QRectF(pad, pad, w - 2*pad, h - 2*pad)
        painter.drawEllipse(rect)
        font = QFont("Segoe UI", int(size * 0.38), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")

    painter.end()
    return QIcon(pixmap)

import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient
from PyQt6.QtCore import Qt, QRectF

class DonutChartWidget(QWidget):
    """Gráfico circular estilo Donut para el Estado de Facturas."""
    def __init__(self, total=128, pagadas=108, pendientes=15, rechazadas=5, parent=None):
        super().__init__(parent)
        self.setMinimumSize(140, 140)
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

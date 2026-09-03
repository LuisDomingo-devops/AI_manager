from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt
from client.gui.theme import AlfonsoStyledWidget


class AlfonsoSystemButton(QPushButton, AlfonsoStyledWidget):
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)


class AlfonsoWindowCloseButton(AlfonsoSystemButton):
    def __init__(self, parent=None):
        super().__init__('X', parent)
        self.setObjectName('BtnClose')
        self.setFixedSize(14, 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class AlfonsoWindowMinimizeButton(AlfonsoSystemButton):
    def __init__(self, parent=None):
        super().__init__('-', parent)
        self.setObjectName('BtnMinimize')
        self.setFixedSize(14, 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class AlfonsoWindowMaximizeButton(AlfonsoSystemButton):
    def __init__(self, parent=None):
        super().__init__('+', parent)
        self.setObjectName('BtnMaximize')
        self.setFixedSize(14, 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class AlfonsoDashboardModuleButton(AlfonsoSystemButton):
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.is_open = False
        self._update_style()

    def set_module_open(self, is_open):
        self.is_open = is_open
        self._update_style()

    def _update_style(self):
        self.apply_qss_class('ModuleBtnOpen' if self.is_open else 'ModuleBtn')

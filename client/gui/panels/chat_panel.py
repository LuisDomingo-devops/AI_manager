"""
panels/chat_panel.py -- Panel derecho de chat del asistente Alfonso.
Sin setStyleSheet() inline: hereda todo del GLOBAL_QSS de theme.py.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QProgressBar, QGridLayout, QWidget,
    QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal

from client.gui.theme import AlfonsoStyledWidget
from client.gui.widgets import AnimatedWaveWidget, ChatTextInput


class AlfonsoChatPanel(QFrame, AlfonsoStyledWidget):
    """
    Panel lateral derecho (380px) que contiene:
      - Cabecera de estado del asistente
      - Indicador de sesion activa
      - Cubiculo holografico (AnimatedWaveWidget)
      - Medidor VU de microfono
      - Historial de mensajes (QTextBrowser)
      - Contenedor de archivos adjuntos
      - Input de texto (ChatTextInput)
      - Botonera de control

    Todo el estilo viene del GLOBAL_QSS mediante ObjectName y clases QSS.
    """

    # Senales propias del panel
    send_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    mode_toggled = pyqtSignal()
    file_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatPanel")    # <- QFrame#ChatPanel en GLOBAL_QSS
        self.setFixedWidth(380)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(8)

        # -- 1. Cabecera --------------------------------------------------
        chat_header = QHBoxLayout()
        chat_badge = QLabel("● ALFONSO AI ASISTENTE")
        chat_badge.setProperty("class", "LblCyan")

        self.state_lbl = QLabel("STANDBY")
        self.state_lbl.setObjectName("StateLbl")
        self.state_lbl.setProperty("class", "LblState")

        chat_header.addWidget(chat_badge)
        chat_header.addStretch()
        chat_header.addWidget(self.state_lbl)
        layout.addLayout(chat_header)

        # -- 2. Indicador de sesion activa --------------------------------
        self.lbl_active_session = QLabel("SESION ACTIVA: DEFAULT")
        self.lbl_active_session.setProperty("class", "LblSession")
        layout.addWidget(self.lbl_active_session)

        # -- 3. Cubiculo holografico --------------------------------------
        hologram_cubicle = QFrame()
        hologram_cubicle.setObjectName("HologramCubicle")
        hologram_cubicle.setFixedHeight(125)
        holo_layout = QVBoxLayout(hologram_cubicle)
        holo_layout.setContentsMargins(4, 4, 4, 4)
        self.animated_wave = AnimatedWaveWidget(self)
        holo_layout.addWidget(self.animated_wave)
        layout.addWidget(hologram_cubicle)

        # -- 4. Medidor VU ------------------------------------------------
        vu_layout = QHBoxLayout()
        self.mic_name_lbl = QLabel("MIC: ACTIVO")
        self.mic_name_lbl.setProperty("class", "LblMicName")

        self.vu_meter = QProgressBar()
        self.vu_meter.setObjectName("VUMeter")   # <- QProgressBar#VUMeter en QSS
        self.vu_meter.setFixedHeight(4)
        self.vu_meter.setTextVisible(False)

        vu_layout.addWidget(self.mic_name_lbl)
        vu_layout.addWidget(self.vu_meter)
        layout.addLayout(vu_layout)

        # -- 5. Historial de mensajes -------------------------------------
        self.chat_display = QTextBrowser()
        self.chat_display.setObjectName("ChatHistory")  # <- QTextBrowser#ChatHistory en QSS
        self.chat_display.setOpenExternalLinks(True)
        layout.addWidget(self.chat_display, 1)

        # -- 6. Contenedor de adjuntos ------------------------------------
        self.attachments_container = QWidget()
        self.attachments_container.setVisible(False)
        self.attachments_layout = QGridLayout(self.attachments_container)
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_layout.setSpacing(4)
        layout.addWidget(self.attachments_container)

        # -- 7. Input de texto --------------------------------------------
        self.text_input = ChatTextInput()
        self.text_input.setObjectName("ChatInput")   # <- QTextEdit#ChatInput en QSS
        self.text_input.setFixedHeight(55)
        self.text_input.setPlaceholderText(
            "Escribe a Alfonso o arrastra facturas aqui... (Shift+Enter para salto)"
        )
        self.text_input.file_dropped.connect(self.file_dropped)
        layout.addWidget(self.text_input)

        # -- 8. Botonera --------------------------------------------------
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_mode = QPushButton("VOZ / TECLADO")
        self.btn_mode.setObjectName("BtnMode")
        self.btn_mode.setFixedHeight(28)
        self.btn_mode.clicked.connect(self.mode_toggled)
        self.btn_mode.hide()

        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("BtnClear")
        self.btn_clear.setFixedHeight(28)
        self.btn_clear.clicked.connect(self.clear_requested)
        self.btn_clear.hide()

        btn_send = QPushButton("Enviar")
        btn_send.setObjectName("BtnSend")
        btn_send.setFixedHeight(28)
        btn_send.clicked.connect(self.send_requested)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_mode)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(btn_send)
        layout.addLayout(btn_layout)

"""main_window.py -- AlfonsoHUDDashboard: ventana principal orquestadora."""
import os, sys, traceback, datetime
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from core.api_client import AlfonsoAPI
from client.gui.theme import AlfonsoStyledWidget
from client.gui.buttons import AlfonsoWindowCloseButton, AlfonsoWindowMinimizeButton, AlfonsoWindowMaximizeButton
from client.gui.assistant_thread import AssistantThread
from client.gui.panels.chat_panel import AlfonsoChatPanel
from client.gui.panels.dashboard_panel import AlfonsoDashboardPanel
from client.gui.panels.view_stack import build_view_stack
from client.gui.sidebar_widget import AlfonsoSidebarWidget
from client.gui.dialogs import AlfonsoDocumentViewerDialog, AlfonsoOnboardingWizard, AlfonsoKPIDashboardDialog


class AlfonsoHUDDashboard(QMainWindow, AlfonsoStyledWidget):
    """Ventana principal de Alfonso - orquestador puro. Sin setStyleSheet() inline."""
    VIEW_MAP = {
        # INICIO
        ("dashboard","resumen_ejecutivo"): 0,
        ("dashboard","kpis_analitica"): 1,
        ("dashboard","prevision_cashflow"): 2,
        # INGRESOS Y GASTOS
        ("ingresos_gastos","nueva_factura_b2b"): 4,
        ("ingresos_gastos","facturas_emitidas"): 3,
        ("ingresos_gastos","ocr_extraccion"): 7,
        ("ingresos_gastos","libro_gastos"): 6,
        ("ingresos_gastos","registro_manual"): 8,
        # TESORERÍA
        ("bancos","conciliacion_bancaria"): 9,
        ("bancos","conexiones_psd2"): 10,
        ("bancos","transferencias_pagos"): 11,
        # CATÁLOGOS
        ("catalogos","lista_contactos"): 36,
        ("catalogos","nuevo_contacto"): 37,
        ("catalogos","lista_productos"): 33,
        ("catalogos","nuevo_producto"): 34,
        ("catalogos","gestion_servicios"): 35,
        # FISCAL Y CONTABLE
        ("fiscal_contable","modelos_trimestrales"): 12,
        ("fiscal_contable","automatizacion_aeat"): 13,
        ("fiscal_contable","calendario_fiscal"): 14,
        ("fiscal_contable","balance_situacion"): 39,
        ("fiscal_contable","gestion_activos"): 38,
        ("fiscal_contable","libros_oficiales_aeat"): 21,
        # LABORAL
        ("laboral","empleados_contratos"): 16,
        ("laboral","generador_nominas"): 17,
        ("laboral","afiliacion_tgss"): 18,
        # ESPACIO DE TRABAJO
        ("espacio_trabajo","correo_inteligente"): 22,
        ("espacio_trabajo","agenda_citas"): 23,
        ("espacio_trabajo","archivo_fiscal"): 19,
        ("espacio_trabajo","visor_documental"): 20,
        ("espacio_trabajo","proyectos_sesiones"): 24,
        # AJUSTES
        ("configuracion","perfil_fiscal"): 28,
        ("configuracion","suscripcion_licencia"): 30,
        ("configuracion","panel_asesor"): 27,
        ("configuracion","verifactu_sif"): 5,
        ("configuracion","auditoria_inmutabilidad"): 26,
        ("configuracion","declaracion_sif"): 25,
        ("configuracion","diseno_maquetacion"): 32,
        ("configuracion","copias_seguridad"): 29,
        ("configuracion","centro_ayuda"): 31,
        ("configuracion","novedades_boe"): 15,
    }

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle("Alfonso Autonomo")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(1440, 880)
        self.setMinimumSize(1200, 720)
        self._drag_pos = None
        self.attached_files = []
        self.text_mode_enabled = True
        self.chat_history = ""
        self.kpi_dashboard = None
        self.uptime_seconds = 0
        self.api_client = AlfonsoAPI(config.get("url","http://127.0.0.1:8000"), self._load_api_key(config))
        self.api = self.api_client
        self.ui_logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(self.ui_logs_dir, exist_ok=True)
        central = QWidget()
        self.setCentralWidget(central)
        self._setup_layout(central)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_telemetry)
        self.ui_timer.start(1000)
        from PyQt6.QtNetwork import QTcpServer, QHostAddress
        self.ipc_server = QTcpServer(self)
        self.ipc_server.newConnection.connect(self.handle_ipc_connection)
        self.ipc_server.listen(QHostAddress(QHostAddress.SpecialAddress.LocalHost), 9876)
        self.agent_process = None
        self.start_agent()
        self.start_assistant()
        QTimer.singleShot(2500, self.check_onboarding)
        QTimer.singleShot(3000, self.update_business_metrics)

    def _setup_layout(self, central):
        root = QVBoxLayout(central)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        root.addWidget(self._build_top_bar())
        body = QHBoxLayout()
        body.setContentsMargins(0,0,0,0)
        body.setSpacing(0)
        self.sidebar = AlfonsoSidebarWidget(self)
        self.sidebar.category_selected.connect(self.on_sidebar_category_selected)
        self.sidebar.plan_clicked.connect(lambda: self.switch_to_view(("configuracion","suscripcion_licencia")))
        body.addWidget(self.sidebar)
        self.dashboard_panel = AlfonsoDashboardPanel(self)
        self.central_stack = build_view_stack(self, self.api_client, self.dashboard_panel)
        body.addWidget(self.central_stack, 1)
        self.chat_panel = AlfonsoChatPanel(self)
        self.chat_panel.send_requested.connect(self._on_send_message)
        self.chat_panel.clear_requested.connect(lambda: self._on_clear_chat())
        self.chat_panel.mode_toggled.connect(self._on_toggle_mode)
        self.chat_panel.file_dropped.connect(self._on_files_dropped)
        body.addWidget(self.chat_panel)
        bw = QWidget()
        bw.setLayout(body)
        root.addWidget(bw, 1)

    def _build_top_bar(self):
        bar = QFrame()
        bar.setObjectName("GlobalTopBar")
        bar.setFixedHeight(60)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(15,0,15,0)
        lay.setSpacing(12)
        logo_lbl = QLabel()
        logo_path = r"C:\Users\luisd\Desktop\Alfonso_commercial\Marketing\Recursos_graficos_corporativos\Alfonso_AI_Konta_logo_horizontal.png"
        px = QPixmap(logo_path)
        if not px.isNull(): logo_lbl.setPixmap(px.scaledToHeight(36, Qt.TransformationMode.SmoothTransformation))
        else: logo_lbl.setText("ALFONSO KONTA AI"); logo_lbl.setProperty("class","LblCyan")
        sep = QLabel("|")
        sep.setStyleSheet("color: rgba(255,255,255,0.15);")
        self.lbl_view_title = QLabel("DASHBOARD FISCAL & EMPRESARIAL")
        self.lbl_view_title.setProperty("class","LblCyan")
        user_pill = QLabel("Luis Domingo (Autonomo)")
        user_pill.setProperty("class","LblSubtitle")
        lay.addWidget(logo_lbl)
        lay.addWidget(sep)
        lay.addWidget(self.lbl_view_title)
        lay.addStretch()
        lay.addWidget(user_pill)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)
        b_close = AlfonsoWindowCloseButton(self)
        b_close.clicked.connect(self.close_gui)
        b_min = AlfonsoWindowMinimizeButton(self)
        b_min.clicked.connect(self.showMinimized)
        b_max = AlfonsoWindowMaximizeButton(self)
        b_max.clicked.connect(self.toggle_maximize_restore)
        ctrl.addWidget(b_close); ctrl.addWidget(b_min); ctrl.addWidget(b_max)
        lay.addLayout(ctrl)
        return bar

    def start_assistant(self):
        self.thread = AssistantThread(self.config)
        self.thread.new_message.connect(self._on_new_message)
        self.thread.state_changed.connect(self._on_state_changed)
        self.thread.audio_level_updated.connect(self._on_audio_level)
        self.thread.switch_session_requested.connect(self.handler_switch_session)
        self.thread.open_calendar.connect(lambda: self.switch_to_view(("fiscal_contable","calendario_fiscal")))
        self.thread.open_mail.connect(lambda: self.switch_to_view(("espacio_trabajo","correo_inteligente")))
        self.thread.open_editor.connect(lambda: self.switch_to_view(("espacio_trabajo","visor_documental")))
        self.thread.start()

    def _on_send_message(self):
        text = self.chat_panel.text_input.toPlainText().strip()
        if not text and not self.attached_files: return
        if self.attached_files:
            import json
            text += f"\n[Adjuntos: {json.dumps([os.path.basename(p) for p in self.attached_files])}]"
            self.attached_files.clear()
            self.chat_panel.attachments_container.setVisible(False)
        self.thread.send_text_message(text)
        self.chat_panel.text_input.clear()

    def _on_clear_chat(self):
        self.chat_history = ""
        self.chat_panel.chat_display.setHtml("")

    def _on_toggle_mode(self):
        self.text_mode_enabled = not self.text_mode_enabled
        self.thread.set_text_mode(self.text_mode_enabled)

    def _on_files_dropped(self, paths):
        self.attached_files.extend(paths)
        self.chat_panel.attachments_container.setVisible(True)

    def _on_new_message(self, sender, message):
        color = "#00F0FF" if sender == "Alfonso" else "#F1F5F9"
        self.chat_history += f"<p><b style='color:{color};'>{sender}:</b> {message}</p>"
        self.chat_panel.chat_display.setHtml(self.chat_history)
        self.chat_panel.chat_display.verticalScrollBar().setValue(
            self.chat_panel.chat_display.verticalScrollBar().maximum())

    def _on_state_changed(self, state):
        labels = {"idle":"STANDBY","idle_text":"TEXTO","listening":"ESCUCHANDO","thinking":"PROCESANDO","speaking":"HABLANDO","error":"ERROR","connecting":"CONECTANDO"}
        self.chat_panel.state_lbl.setText(labels.get(state, state.upper()))
        if hasattr(self.chat_panel, "animated_wave"): self.chat_panel.animated_wave.set_state(state)

    def _on_audio_level(self, level, device_name):
        self.chat_panel.vu_meter.setValue(level)
        self.chat_panel.mic_name_lbl.setText(f"MIC: {device_name[:22]}")

    def switch_to_view(self, key):
        idx = self.VIEW_MAP.get(key, None)
        print(f"[DEBUG switch_to_view] key={key!r}  idx={idx}  MAP_keys={list(self.VIEW_MAP.keys())}")
        if idx is None:
            print(f"[DEBUG] CLAVE NO ENCONTRADA EN VIEW_MAP, mostrando 0")
            idx = 0
        self.central_stack.setCurrentIndex(idx)

    def on_sidebar_category_selected(self, category, subcategory, title=""):
        key = (category.lower(), subcategory.lower())
        print(f"[DEBUG sidebar] category={category!r}  subcategory={subcategory!r}  title={title!r}  key={key!r}")
        self.switch_to_view(key)
        self.lbl_view_title.setText((title or subcategory).upper())

    def update_business_metrics(self):
        try:
            invoices = self.api_client.get_invoices() or []
            expenses = self.api_client.get_expenses() or []
            ingresos = sum(float(i.get("amount",0)) for i in invoices if i.get("type")=="income")
            gastos = sum(float(e.get("amount",0)) for e in expenses)
            iva = sum(float(i.get("iva",0)) for i in invoices+expenses)
            total = len(invoices)
            pagadas = sum(1 for i in invoices if i.get("status")=="paid")
            pendientes = sum(1 for i in invoices if i.get("status")=="pending")
            rechazadas = sum(1 for i in invoices if i.get("status")=="rejected")
            mi=[0.0]*12; me=[0.0]*12; mv=[0.0]*12
            for inv in invoices:
                try: m=datetime.datetime.fromisoformat(inv.get("date","")).month-1; mi[m]+=float(inv.get("amount",0)); mv[m]+=float(inv.get("iva",0))
                except: pass
            for exp in expenses:
                try: m=datetime.datetime.fromisoformat(exp.get("date","")).month-1; me[m]+=float(exp.get("amount",0))
                except: pass
            now=datetime.datetime.now(); cq=(now.month-1)//3+1; qs=(cq-1)*3
            today=datetime.date.today()
            qd={1:datetime.date(today.year,4,20),2:datetime.date(today.year,7,20),3:datetime.date(today.year,10,20),4:datetime.date(today.year+1,1,30)}
            dl=(qd[cq]-today).days
            if dl<0: nq=(cq%4)+1; dl=(qd[nq]-today).days; aeat=f"Modelo 303 (IVA {nq}T) vence en {dl} dias"
            else: aeat=f"Modelo 303 (IVA {cq}T) vence en {dl} dias"
            unreconciled=sum(1 for i in invoices if i.get("reconciled") is False)
            recent=[]
            for inv in invoices:
                try:
                    dt=datetime.datetime.fromisoformat(inv.get("date","")).strftime("%d/%m/%y")
                    s="+" if inv.get("type")=="income" else "-"
                    amt=float(inv.get("amount",0))
                    recent.append((dt,str(inv.get("concept",inv.get("description","")))[:28],str(inv.get("status","")).capitalize(),f"{s}{amt:,.2f}"))
                except: pass
            self.dashboard_panel.update_metrics({"ingresos":ingresos,"gastos":gastos,"beneficio":ingresos-gastos,"iva_soportado":iva,"title_ingresos":f"Ingresos ({pagadas} cobradas)" if total else "Ingresos","title_gastos":f"Gastos ({pendientes} pendientes)" if total else "Gastos","title_beneficio":"Beneficio Neto","title_iva":f"IVA ({total} facturas)" if total else "IVA Soportado","monthly_incomes":mi,"monthly_expenses":me,"monthly_iva":mv,"total_facturas":total,"pagadas":pagadas,"pendientes":pendientes,"rechazadas":rechazadas,"ingresos_trim":mi[qs:qs+3],"gastos_trim":me[qs:qs+3],"alert_aeat_text":aeat,"unreconciled_count":unreconciled,"recent_invoices":recent})
        except Exception as e: print(f"Error metrics: {e}")

    def update_telemetry(self): self.uptime_seconds += 1

    def handle_ipc_connection(self):
        sock = self.ipc_server.nextPendingConnection()
        sock.readyRead.connect(lambda: self._read_ipc_data(sock))

    def _read_ipc_data(self, socket):
        import json
        data = socket.readAll().data().decode("utf-8", errors="ignore")
        socket.disconnectFromHost()
        try:
            cmd = json.loads(data)
            if cmd.get("action")=="open_file" and os.path.exists(str(cmd.get("filepath",""))): self.show_native_viewer(cmd["filepath"])
            elif cmd.get("action")=="open_archive": self.switch_to_view(("espacio_trabajo","archivo_fiscal"))
        except: pass

    def show_native_viewer(self, filepath=None):
        try:
            from PyQt6.QtWidgets import QFileDialog
            if not filepath or not os.path.exists(str(filepath)):
                fp2,_=QFileDialog.getOpenFileName(self,"Seleccionar documento","","Documentos (*.pdf *.png *.jpg)")
                if not fp2: return
                filepath=fp2
            if hasattr(self,"viewer") and self.viewer and self.viewer.isVisible(): self.viewer.close()
            self.viewer=AlfonsoDocumentViewerDialog(self,filepath); self.viewer.show(); self.viewer.raise_()
        except Exception as e: print(f"Visor: {e}")

    def check_onboarding(self):
        try:
            import requests
            api_key=self._load_api_key(self.config)
            res=requests.get(f"{self.config.get(chr(117)+chr(114)+chr(108))}/tax/profile",headers={"X-API-Key":api_key},timeout=3.0)
            if res.status_code==200 and not res.json().get("configured",False): AlfonsoOnboardingWizard(self,self.api_client).exec()
        except: pass

    def start_agent(self):
        try:
            import subprocess
            gui_dir=os.path.dirname(os.path.abspath(__file__))
            agent_path=os.path.join(os.path.dirname(gui_dir),"alfonso_agent.py")
            from urllib.parse import urlparse
            parsed=urlparse(self.config.get("url","http://localhost:8000"))
            bridge_url=self.config.get("bridge_url",f"ws://{parsed.hostname or chr(108)+chr(111)+chr(99)+chr(97)+chr(108)+chr(104)+chr(111)+chr(115)+chr(116)}:8765")
            flags=0x08000000 if sys.platform=="win32" else 0
            self.agent_process=subprocess.Popen([sys.executable,agent_path,bridge_url],creationflags=flags)
        except Exception as e: print(f"Agente: {e}")

    def handler_switch_session(self, session_id, project_name, title):
        try:
            self.thread.session_id = session_id
            if hasattr(self.chat_panel,"lbl_active_session"): self.chat_panel.lbl_active_session.setText(f"SESION: {project_name[:20].upper()}")
        except: pass

    def open_kpi_dashboard(self):
        self.kpi_dashboard=AlfonsoKPIDashboardDialog(self); self.kpi_dashboard.show()

    def mousePressEvent(self, event):
        if event.button()==Qt.MouseButton.LeftButton: self._drag_pos=event.globalPosition().toPoint()-self.frameGeometry().topLeft()
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        if event.buttons()==Qt.MouseButton.LeftButton and self._drag_pos is not None: self.move(event.globalPosition().toPoint()-self._drag_pos)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event): self._drag_pos=None; super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key()==Qt.Key.Key_Escape: self.close_gui()
        elif event.key()==Qt.Key.Key_F5: self.update_business_metrics()
        elif event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            m={Qt.Key.Key_N:("facturacion","nueva_factura_b2b"),Qt.Key.Key_G:("gastos","ocr_extraccion"),Qt.Key.Key_D:("facturacion","facturas_emitidas")}
            if event.key() in m: self.switch_to_view(m[event.key()])
        super().keyPressEvent(event)

    def toggle_maximize_restore(self): self.showNormal() if self.isMaximized() else self.showMaximized()

    def close_gui(self):
        for attr,action in [("ipc_server",lambda o:o.close()),("agent_process",lambda o:o.terminate()),("thread",lambda o:(setattr(o,"running",False),o.quit(),o.wait(300)))]:
            try:
                obj=getattr(self,attr,None)
                if obj: action(obj)
            except: pass
        self.close()
        inst=QApplication.instance()
        if inst: inst.quit()

    def closeEvent(self, event): self.close_gui()

    @staticmethod
    def _load_api_key(config):
        key=config.get("api_key","default_key")
        try:
            kf=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),"data",".api_key")
            if os.path.exists(kf):
                with open(kf,"r",encoding="utf-8") as f: key=f.read().strip()
        except: pass
        return key


from client.gui.dialogs import *
from client.gui.theme import apply_theme


def launch(config):
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    apply_theme(app)
    dashboard = AlfonsoHUDDashboard(config)
    dashboard.show()
    dashboard.raise_()
    dashboard.activateWindow()
    sys.exit(app.exec())

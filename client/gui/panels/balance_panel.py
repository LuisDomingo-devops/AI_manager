import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QComboBox, QPushButton
)
from PyQt6.QtCore import Qt
from client.core.api_client import api_client

class BalancePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Balance de Situación (PGC)")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        header.addWidget(title)
        
        header.addStretch()
        
        self.year_combo = QComboBox()
        current_year = datetime.datetime.now().year
        for y in range(current_year - 5, current_year + 2):
            self.year_combo.addItem(str(y), y)
        self.year_combo.setCurrentText(str(current_year))
        
        btn_refresh = QPushButton("Calcular Balance")
        btn_refresh.clicked.connect(self.load_data)
        
        header.addWidget(QLabel("Ejercicio:"))
        header.addWidget(self.year_combo)
        header.addWidget(btn_refresh)
        self.layout.addLayout(header)
        
        # Tables for Activo and Pasivo
        tables_layout = QHBoxLayout()
        
        # Activo Table
        act_layout = QVBoxLayout()
        act_lbl = QLabel("ACTIVO")
        act_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #00F0FF;")
        act_layout.addWidget(act_lbl)
        self.table_activo = QTableWidget(0, 3)
        self.table_activo.setHorizontalHeaderLabels(["Cuenta", "Nombre", "Saldo (€)"])
        self.table_activo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        act_layout.addWidget(self.table_activo)
        self.lbl_total_activo = QLabel("Total Activo: 0.00 €")
        self.lbl_total_activo.setStyleSheet("font-weight: bold;")
        act_layout.addWidget(self.lbl_total_activo)
        tables_layout.addLayout(act_layout)
        
        # Pasivo Table
        pas_layout = QVBoxLayout()
        pas_lbl = QLabel("PASIVO Y PATRIMONIO NETO")
        pas_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #FF0055;")
        pas_layout.addWidget(pas_lbl)
        self.table_pasivo = QTableWidget(0, 3)
        self.table_pasivo.setHorizontalHeaderLabels(["Cuenta", "Nombre", "Saldo (€)"])
        self.table_pasivo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        pas_layout.addWidget(self.table_pasivo)
        self.lbl_total_pasivo = QLabel("Total Pasivo + PN: 0.00 €")
        self.lbl_total_pasivo.setStyleSheet("font-weight: bold;")
        pas_layout.addWidget(self.lbl_total_pasivo)
        tables_layout.addLayout(pas_layout)
        
        self.layout.addLayout(tables_layout)

    def load_data(self):
        year = self.year_combo.currentData()
        try:
            res = api_client.execute_tool("get_balance_situacion", {"year": year})
            if res.get("status") == "ok":
                balance = res.get("balance", {})
                
                # Cargar Activo
                activo_items = balance.get("activo", [])
                self.table_activo.setRowCount(len(activo_items))
                tot_act = 0.0
                for i, item in enumerate(activo_items):
                    self.table_activo.setItem(i, 0, QTableWidgetItem(item["cuenta"]))
                    self.table_activo.setItem(i, 1, QTableWidgetItem(item["nombre"]))
                    self.table_activo.setItem(i, 2, QTableWidgetItem(f"{item['saldo']:.2f} €"))
                    tot_act += item['saldo']
                self.lbl_total_activo.setText(f"Total Activo: {tot_act:.2f} €")
                
                # Cargar Pasivo y Patrimonio Neto
                pasivo_items = balance.get("pasivo_patrimonio", [])
                self.table_pasivo.setRowCount(len(pasivo_items))
                tot_pas = 0.0
                for i, item in enumerate(pasivo_items):
                    self.table_pasivo.setItem(i, 0, QTableWidgetItem(item["cuenta"]))
                    self.table_pasivo.setItem(i, 1, QTableWidgetItem(item["nombre"]))
                    self.table_pasivo.setItem(i, 2, QTableWidgetItem(f"{item['saldo']:.2f} €"))
                    tot_pas += item['saldo']
                self.lbl_total_pasivo.setText(f"Total Pasivo + PN: {tot_pas:.2f} €")
                
                if abs(tot_act - tot_pas) > 0.01:
                    QMessageBox.warning(self, "Descuadre", f"Atención: El balance está descuadrado por {abs(tot_act - tot_pas):.2f} €")
                    
            else:
                QMessageBox.warning(self, "Error", res.get("message", "Error al cargar balance"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error de conexión: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()

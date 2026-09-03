import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QLineEdit, QFormLayout, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from client.core.api_client import api_client

class AddAssetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Bien de Inversión")
        self.setFixedSize(400, 300)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit()
        self.date_input = QLineEdit()
        self.date_input.setText(datetime.datetime.now().strftime("%Y-%m-%d"))
        
        self.cost_input = QDoubleSpinBox()
        self.cost_input.setMaximum(99999999.0)
        self.cost_input.setDecimals(2)
        
        self.salvage_input = QDoubleSpinBox()
        self.salvage_input.setMaximum(99999999.0)
        self.salvage_input.setDecimals(2)
        
        self.life_input = QSpinBox()
        self.life_input.setMinimum(1)
        self.life_input.setMaximum(100)
        self.life_input.setValue(4)
        
        layout.addRow("Nombre/Concepto:", self.name_input)
        layout.addRow("Fecha Compra (YYYY-MM-DD):", self.date_input)
        layout.addRow("Coste Adquisición (€):", self.cost_input)
        layout.addRow("Valor Residual (€):", self.salvage_input)
        layout.addRow("Vida Útil (Años):", self.life_input)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def get_data(self):
        return {
            "name": self.name_input.text(),
            "purchase_date": self.date_input.text(),
            "cost": self.cost_input.value(),
            "salvage_value": self.salvage_input.value(),
            "useful_life_years": self.life_input.value()
        }

class AmortizationDialog(QDialog):
    def __init__(self, year, proposal, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Cuadro de Amortización - {year}")
        self.setFixedSize(600, 400)
        self.year = year
        self.proposal = proposal
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        lbl = QLabel(f"<b>Propuesta de Amortización para el Ejercicio {self.year}</b>")
        layout.addWidget(lbl)
        
        table = QTableWidget(len(self.proposal), 3)
        table.setHorizontalHeaderLabels(["Activo (ID)", "Cuota Anual", "Cuenta Debe"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        total = 0.0
        for i, p in enumerate(self.proposal):
            table.setItem(i, 0, QTableWidgetItem(f"{p['asset_name']} (ID: {p['asset_id']})"))
            table.setItem(i, 1, QTableWidgetItem(f"{p['amount']:.2f} €"))
            table.setItem(i, 2, QTableWidgetItem(p['account_debe']))
            total += p['amount']
            
        layout.addWidget(table)
        
        tot_lbl = QLabel(f"<b>Total a Amortizar: {total:.2f} €</b>")
        tot_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(tot_lbl)
        
        btn_layout = QHBoxLayout()
        exec_btn = QPushButton("Contabilizar Amortización")
        exec_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cerrar")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(exec_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

class AssetsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Gestión de Activos Fijos")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        btn_add = QPushButton("+ Añadir Bien de Inversión")
        btn_add.clicked.connect(self.add_asset)
        btn_amortize = QPushButton("Ver Cuadro Amortización Actual")
        btn_amortize.clicked.connect(self.view_amortization)
        
        header.addWidget(btn_amortize)
        header.addWidget(btn_add)
        self.layout.addLayout(header)
        
        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Fecha Compra", "Coste", "Valor Residual", "Años Vida Útil"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)
        
    def load_data(self):
        try:
            res = api_client.execute_tool("list_assets", {})
            if res.get("status") == "ok":
                assets = res.get("assets", [])
                self.table.setRowCount(len(assets))
                for i, asset in enumerate(assets):
                    self.table.setItem(i, 0, QTableWidgetItem(str(asset["id"])))
                    self.table.setItem(i, 1, QTableWidgetItem(asset["name"]))
                    self.table.setItem(i, 2, QTableWidgetItem(asset["purchase_date"]))
                    self.table.setItem(i, 3, QTableWidgetItem(f"{asset['cost']:.2f} €"))
                    self.table.setItem(i, 4, QTableWidgetItem(f"{asset['salvage_value']:.2f} €"))
                    self.table.setItem(i, 5, QTableWidgetItem(str(asset["useful_life_years"])))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando activos: {e}")

    def add_asset(self):
        dialog = AddAssetDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                res = api_client.execute_tool("add_asset", data)
                if res.get("status") == "ok":
                    QMessageBox.information(self, "Éxito", res.get("message", "Guardado"))
                    self.load_data()
                else:
                    QMessageBox.warning(self, "Error", res.get("message", "Error al guardar"))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error: {e}")

    def view_amortization(self):
        year = datetime.datetime.now().year
        try:
            res = api_client.execute_tool("get_amortization_table", {"year": year})
            if res.get("status") == "ok":
                proposal = res.get("proposal", [])
                if not proposal:
                    QMessageBox.information(self, "Info", "No hay activos para amortizar o cuota es 0.")
                    return
                dialog = AmortizationDialog(year, proposal, self)
                if dialog.exec():
                    exec_res = api_client.execute_tool("execute_amortization", {"year": year})
                    if exec_res.get("status") == "ok":
                        QMessageBox.information(self, "Éxito", exec_res.get("message", "Contabilizado"))
                    else:
                        QMessageBox.warning(self, "Aviso", exec_res.get("message", "Error al contabilizar"))
            else:
                QMessageBox.warning(self, "Error", res.get("message", "Error"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()

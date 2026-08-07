import os
import re

dialogs_file = 'client/gui/dialogs.py'
output_dir = 'client/gui/dialogs'
os.makedirs(output_dir, exist_ok=True)

with open(dialogs_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Vamos a extraer los bloques de código basándonos en las definiciones de clases.
# Primero definimos las importaciones comunes que necesitarán los submódulos.
imports_common = """import sys
import os
import uuid
import datetime
import shutil
import csv
import json
import collections
from pathlib import Path

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QFrame, QPushButton, QLineEdit, QTextEdit, QTextBrowser, 
                             QScrollArea, QSplitter, QGroupBox, QFormLayout, QMessageBox,
                             QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QComboBox, QFileDialog, QStackedWidget, QSpinBox, 
                             QDoubleSpinBox, QButtonGroup, QProgressBar, QListView, QStyle)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QEvent
from PyQt6.QtGui import QColor, QFont, QPixmap, QDesktopServices, QPainter, QPen, QBrush, QLinearGradient, QPainterPath
from core.api_client import AlfonsoAPI
"""

# 1. base.py (AlfonsoBaseDialog, AlfonsoWindowMinimizeButton, AlfonsoWindowCloseButton)
base_pattern = r"(class AlfonsoBaseDialog.*?)(?=class AlfonsoLedgerDialog)"
base_match = re.search(base_pattern, content, re.DOTALL)
if base_match:
    with open(os.path.join(output_dir, 'base.py'), 'w', encoding='utf-8') as f:
        f.write(imports_common + "\n" + base_match.group(1).strip() + "\n")

# 2. ledger.py (AlfonsoLedgerDialog)
ledger_pattern = r"(class AlfonsoLedgerDialog.*?)(?=class AlfonsoSubscriptionDialog)"
ledger_match = re.search(ledger_pattern, content, re.DOTALL)
if ledger_match:
    with open(os.path.join(output_dir, 'ledger.py'), 'w', encoding='utf-8') as f:
        f.write(imports_common + "from client.gui.dialogs.base import AlfonsoBaseDialog\n\n" + ledger_match.group(1).strip() + "\n")

# 3. subscription.py (AlfonsoSubscriptionDialog) (Se incluye en ledger o por separado, hagamos base + subscription/compliance)
# 4. compliance.py (AlfonsoComplianceDialog)
compliance_pattern = r"(class AlfonsoSubscriptionDialog.*?)(?=class AlfonsoOnboardingWizard)"
compliance_match = re.search(compliance_pattern, content, re.DOTALL)
if compliance_match:
    # Contiene AlfonsoSubscriptionDialog y AlfonsoComplianceDialog ya que están juntos antes de AlfonsoOnboardingWizard
    with open(os.path.join(output_dir, 'compliance.py'), 'w', encoding='utf-8') as f:
        f.write(imports_common + "from client.gui.dialogs.base import AlfonsoBaseDialog\n\n" + compliance_match.group(1).strip() + "\n")

# 5. onboarding.py (AlfonsoOnboardingWizard)
onboarding_pattern = r"(class AlfonsoOnboardingWizard.*?)(?=class AlfonsoInvoiceConfirmDialog)"
onboarding_match = re.search(onboarding_pattern, content, re.DOTALL)
if onboarding_match:
    with open(os.path.join(output_dir, 'onboarding.py'), 'w', encoding='utf-8') as f:
        f.write(imports_common + "from client.gui.dialogs.base import AlfonsoBaseDialog\n\n" + onboarding_match.group(1).strip() + "\n")

# 6. invoice.py (AlfonsoInvoiceConfirmDialog)
invoice_pattern = r"(class AlfonsoInvoiceConfirmDialog.*?)(?=class MailWidget)"
invoice_match = re.search(invoice_pattern, content, re.DOTALL)
if invoice_match:
    with open(os.path.join(output_dir, 'invoice.py'), 'w', encoding='utf-8') as f:
        f.write(imports_common + "from client.gui.dialogs.base import AlfonsoBaseDialog\n\n" + invoice_match.group(1).strip() + "\n")

# 7. widgets.py (MailWidget, CalendarWidget y lo que quede al final)
widgets_pattern = r"(class MailWidget.*)"
widgets_match = re.search(widgets_pattern, content, re.DOTALL)
if widgets_match:
    with open(os.path.join(output_dir, 'widgets.py'), 'w', encoding='utf-8') as f:
        f.write(imports_common + "\n" + widgets_match.group(1).strip() + "\n")

# Crear el archivo __init__.py en client/gui/dialogs/ para exponer todas las clases
init_content = """from client.gui.dialogs.base import AlfonsoBaseDialog, AlfonsoWindowMinimizeButton, AlfonsoWindowCloseButton
from client.gui.dialogs.ledger import AlfonsoLedgerDialog
from client.gui.dialogs.compliance import AlfonsoSubscriptionDialog, AlfonsoComplianceDialog
from client.gui.dialogs.onboarding import AlfonsoOnboardingWizard
from client.gui.dialogs.invoice import AlfonsoInvoiceConfirmDialog
from client.gui.dialogs.widgets import MailWidget, CalendarWidget
"""

with open(os.path.join(output_dir, '__init__.py'), 'w', encoding='utf-8') as f:
    f.write(init_content)

print("Modularización del script de diálogos completada con éxito.")

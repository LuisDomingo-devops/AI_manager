import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from PyQt6.QtWidgets import QApplication
from client.gui.main_window import AlfonsoHUDDashboard

app = QApplication([])
config = {'app_name': 'Test', 'version': '1.0'}
window = AlfonsoHUDDashboard(config)

sidebar = window.sidebar

print('STARTING CLICK TEST')
for (cat, sub), btn in sidebar.all_buttons.items():
    print(f'Clicking: {cat} / {sub}')
    # manually trigger the signal with False
    btn.clicked.emit(False)
    idx = window.central_stack.currentIndex()
    print(f' -> New Index: {idx}')

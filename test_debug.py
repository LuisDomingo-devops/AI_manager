import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('app'))

from PyQt6.QtWidgets import QApplication
from client.gui.sidebar_widget import AlfonsoSidebarWidget

app = QApplication([])
sidebar = AlfonsoSidebarWidget()

with open('debug_output.txt', 'w', encoding='utf-8') as f:
    f.write('START DEBUG\n')
    for (cat_id, sub_id), btn in sidebar.all_buttons.items():
        f.write(f'{cat_id} -> {sub_id} | btn text: {btn.text().strip()} | is_active: {btn.is_active}\n')


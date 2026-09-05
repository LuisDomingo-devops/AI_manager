import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('app'))

from PyQt6.QtWidgets import QApplication
from client.gui.sidebar_widget import AlfonsoSidebarWidget

app = QApplication([])
sidebar = AlfonsoSidebarWidget()

with open('debug_output2.txt', 'w', encoding='utf-8') as f:
    def on_sel(cat, sub, title):
        f.write(f'SIGNAL CAUGHT: cat={cat}, sub={sub}, title={title}\n')
    
    sidebar.category_selected.connect(on_sel)
    
    btn = sidebar.all_buttons[('ingresos_gastos', 'nueva_factura_b2b')]
    
    f.write('Clicking btn...\n')
    btn.clicked.emit(False)
    
    f.write(f'btn is_active: {btn.is_active}\n')

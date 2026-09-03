from PyQt6.QtWidgets import QLabel
from client.gui.panels.product_list_panel import AlfonsoProductListPanel

class AlfonsoProductServicePanel(AlfonsoProductListPanel):
    """
    Panel para la gestión de servicios.
    Hereda del panel de productos ya que ambos comparten la misma tabla
    y las mismas métricas (API: get_products, create_product, etc).
    """
    def __init__(self, parent=None):
        super().__init__(parent, filter_type="service")
        
    def setup_ui(self):
        super().setup_ui()
        # Sobrescribimos el título para esta vista en particular
        for child in self.findChildren(QLabel):
            if "PRODUCTOS" in child.text():
                child.setText("🛠️  GESTIÓN DE SERVICIOS")
                break

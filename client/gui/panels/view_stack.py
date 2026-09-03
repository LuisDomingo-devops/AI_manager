"""
panels/view_stack.py -- Construccion del QStackedWidget de 33 vistas.
Todas las instancias se crean con embedded=True para integrarse
en el layout principal sin abrir dialogs independientes.
"""
from PyQt6.QtWidgets import QStackedWidget

from client.gui.dialogs import (
    AlfonsoKPIDashboardDialog,
    AlfonsoCashFlowWidget,
    AlfonsoLedgerDialog,
    AlfonsoInvoiceEmitterWidget,
    AlfonsoVerifactuAuditWidget,
    AlfonsoDocumentViewerDialog,
    AlfonsoManualEntryDialog,
    AlfonsoBankReconciliationDialog,
    AlfonsoBankConnectionsDialog,
    AlfonsoInitiateTransferDialog,
    AeatAutofillWidget,
    AlfonsoBoeWidget,
    AlfonsoPayrollWidget,
    AlfonsoArchiveBrowserDialog,
    AlfonsoOfficialBooksWidget,
    AlfonsoComplianceDialog,
    AlfonsoTenantAdvisorWidget,
    AlfonsoBackupWidget,
    AlfonsoSubscriptionDialog,
    AlfonsoHelpCenterWidget,
    AlfonsoDocumentCustomizerWidget,
    ProjectNavigatorDialog,
    ConfigWidget,
)
from client.gui.widgets import CalendarWidget, MailWidget
from client.gui.panels.product_list_panel import AlfonsoProductListPanel
from client.gui.panels.product_form_panel import AlfonsoProductFormPanel
from client.gui.panels.product_service_panel import AlfonsoProductServicePanel
from client.gui.panels.assets_panel import AssetsPanel
from client.gui.panels.balance_panel import BalancePanel
from client.gui.panels.contacts_list_panel import AlfonsoContactsListPanel
from client.gui.panels.contact_form_panel import AlfonsoContactFormPanel

def build_view_stack(parent, api_client, dashboard_widget) -> QStackedWidget:
    """
    Construye y devuelve el QStackedWidget con todas las vistas del sistema.

    Args:
        parent:           La ventana principal (AlfonsoHUDDashboard).
        api_client:       Instancia de AlfonsoAPI.
        dashboard_widget: El AlfonsoDashboardPanel ya construido (index 0).

    Returns:
        QStackedWidget configurado con las 33 vistas.
        Las referencias a cada vista se almacenan como atributos en `parent`.
    """
    stack = QStackedWidget()

    # 0: Dashboard > Resumen Ejecutivo
    stack.addWidget(dashboard_widget)

    # 1: Dashboard > Analitica & KPIs
    parent.view_kpis = AlfonsoKPIDashboardDialog(parent, embedded=True)
    stack.addWidget(parent.view_kpis)

    # 2: Dashboard > Prevision Cash Flow
    parent.view_cashflow = AlfonsoCashFlowWidget(parent, embedded=True)
    stack.addWidget(parent.view_cashflow)

    # 3: Facturacion > Facturas Emitidas (7XX)
    parent.view_invoices = AlfonsoLedgerDialog(parent, api_client, embedded=True)
    stack.addWidget(parent.view_invoices)

    # 4: Facturacion > Nueva Factura / FacturaE B2B
    parent.view_invoice_emitter = AlfonsoInvoiceEmitterWidget(parent, embedded=True)
    stack.addWidget(parent.view_invoice_emitter)

    # 5: Facturacion > Veri*Factu & Huella Hash
    parent.view_verifactu_audit = AlfonsoVerifactuAuditWidget(parent, embedded=True)
    stack.addWidget(parent.view_verifactu_audit)

    # 6: Gastos > Libro de Gastos (6XX)
    parent.view_expenses = AlfonsoLedgerDialog(parent, api_client, embedded=True)
    stack.addWidget(parent.view_expenses)

    # 7: Gastos > Captura & Extraccion OCR
    parent.view_ocr = AlfonsoDocumentViewerDialog(parent, embedded=True)
    stack.addWidget(parent.view_ocr)

    # 8: Gastos > Registro Manual de Gasto
    parent.view_manual_entry = AlfonsoManualEntryDialog(parent, embedded=True)
    stack.addWidget(parent.view_manual_entry)

    # 9: Bancos > Conciliacion Bancaria PSD2
    parent.view_banks = AlfonsoBankReconciliationDialog(parent, api_client, embedded=True)
    stack.addWidget(parent.view_banks)

    # 10: Bancos > Cuentas Conectadas Open Banking
    parent.view_bank_connections = AlfonsoBankConnectionsDialog(parent, embedded=True)
    stack.addWidget(parent.view_bank_connections)

    # 11: Bancos > Emision de Transferencias SEPA
    parent.view_transfers = AlfonsoInitiateTransferDialog(parent, embedded=True)
    stack.addWidget(parent.view_transfers)

    # 12: Impuestos > Modelos Trimestrales (303, 130)
    parent.view_taxes = AeatAutofillWidget(parent, embedded=True)
    stack.addWidget(parent.view_taxes)

    # 13: Impuestos > Sede Electronica & Playwright
    parent.view_aeat_auto = AeatAutofillWidget(parent, embedded=True)
    stack.addWidget(parent.view_aeat_auto)

    # 14: Impuestos > Calendario Fiscal & Vencimientos
    parent.view_calendar = CalendarWidget(api_client, parent, embedded=True)
    stack.addWidget(parent.view_calendar)

    # 15: Impuestos > Monitor BOE & Leyes
    parent.view_boe = AlfonsoBoeWidget(parent, embedded=True)
    stack.addWidget(parent.view_boe)

    # 16: Laboral > Empleados & Contratos
    parent.view_employees = AlfonsoPayrollWidget(parent, embedded=True)
    stack.addWidget(parent.view_employees)

    # 17: Laboral > Generador de Nominas PDF
    parent.view_payrolls = AlfonsoPayrollWidget(parent, embedded=True)
    stack.addWidget(parent.view_payrolls)

    # 18: Laboral > Seguridad Social & TGSS
    parent.view_tgss = AlfonsoPayrollWidget(parent, embedded=True)
    stack.addWidget(parent.view_tgss)

    # 19: Documentos > Archivo Fiscal Digital
    parent.view_docs = AlfonsoArchiveBrowserDialog(parent, embedded=True)
    stack.addWidget(parent.view_docs)

    # 20: Documentos > Visor Documental con IA
    parent.view_doc_viewer = AlfonsoDocumentViewerDialog(parent, embedded=True)
    stack.addWidget(parent.view_doc_viewer)

    # 21: Documentos > Libros Oficiales AEAT (Excel/CSV)
    parent.view_official_books = AlfonsoOfficialBooksWidget(parent, embedded=True)
    stack.addWidget(parent.view_official_books)

    # 22: Asistente > Alfonso Mail Inteligente
    parent.view_mail = MailWidget(api_client, parent, embedded=True)
    stack.addWidget(parent.view_mail)

    # 23: Asistente > Agenda & Citas Previas
    parent.view_agenda = CalendarWidget(api_client, parent, embedded=True)
    stack.addWidget(parent.view_agenda)

    # 24: Asistente > Navegador de Proyectos
    parent.view_projects = ProjectNavigatorDialog(parent, embedded=True)
    stack.addWidget(parent.view_projects)

    # 25: Cumplimiento > Declaracion Responsable SIF (RD 1007/2023)
    parent.view_advisor = AlfonsoComplianceDialog(parent, embedded=True)
    stack.addWidget(parent.view_advisor)

    # 26: Cumplimiento > Auditoria de Inmutabilidad
    parent.view_audit_ledger = AlfonsoVerifactuAuditWidget(parent, embedded=True)
    stack.addWidget(parent.view_audit_ledger)

    # 27: Cumplimiento > Panel Asesor / Gestoria
    parent.view_tenant_advisor = AlfonsoTenantAdvisorWidget(parent, embedded=True)
    stack.addWidget(parent.view_tenant_advisor)

    # 28: Sistema > Perfil Fiscal del Autonomo
    parent.view_config = ConfigWidget(parent, embedded=True)
    stack.addWidget(parent.view_config)

    # 29: Sistema > Copias de Seguridad & Restauracion
    parent.view_backups = AlfonsoBackupWidget(parent, embedded=True)
    stack.addWidget(parent.view_backups)

    # 30: Sistema > Suscripcion & Licencia
    parent.view_subscription = AlfonsoSubscriptionDialog(parent, embedded=True)
    stack.addWidget(parent.view_subscription)

    # 31: Sistema > Centro de Ayuda & Manual
    parent.view_help_center = AlfonsoHelpCenterWidget(parent, embedded=True)
    stack.addWidget(parent.view_help_center)

    # 32: Documentos > Diseno y Maquetacion Drag and Drop
    parent.view_document_customizer = AlfonsoDocumentCustomizerWidget(parent, embedded=True)
    stack.addWidget(parent.view_document_customizer)
    # Product panels
    parent.view_product_list = AlfonsoProductListPanel(parent)
    stack.addWidget(parent.view_product_list)
    parent.view_new_product = AlfonsoProductFormPanel(parent)
    stack.addWidget(parent.view_new_product)
    parent.view_service_management = AlfonsoProductServicePanel(parent)
    stack.addWidget(parent.view_service_management)
    # Contact panels
    parent.view_contacts_list = AlfonsoContactsListPanel(parent)
    stack.addWidget(parent.view_contacts_list)
    parent.view_new_contact = AlfonsoContactFormPanel(parent)
    stack.addWidget(parent.view_new_contact)
    
    # Contabilidad panels
    parent.view_assets = AssetsPanel(parent)
    stack.addWidget(parent.view_assets)
    parent.view_balance = BalancePanel(parent)
    stack.addWidget(parent.view_balance)

    return stack

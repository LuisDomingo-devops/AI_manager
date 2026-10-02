"""
Componente visual para la revisión humana interactiva de facturas recibidas.
Presenta los metadatos extraídos por OCR, semáforo de confianza, editor de cuenta PGC
y botones de aprobación/contabilización o descarte.
"""

from typing import Optional
from decimal import Decimal

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import pyqtSignal, Qt

from app.domain.schemas import InvoiceApprovalProposalDTO
from app.domain.services.received_invoice_accounting_service import (
    ReceivedInvoiceAccountingService,
)


class PendingInvoiceCardWidget(QFrame):
    """Tarjeta interactiva para aprobación humana de factura recibida."""

    proposal_approved = pyqtSignal(str)
    proposal_rejected = pyqtSignal(str)

    def __init__(
        self,
        proposal: InvoiceApprovalProposalDTO,
        accounting_service: Optional[ReceivedInvoiceAccountingService] = None,
        parent=None
    ):
        super().__init__(parent)
        self.proposal = proposal
        self.accounting_service = accounting_service or ReceivedInvoiceAccountingService()
        self.meta = proposal.metadata

        score = float(self.meta.confidence_score)
        self.is_high_confidence = score >= 0.85

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 1. Cabecera con Emisor y Semáforo de Confianza
        header_layout = QHBoxLayout()
        self.lbl_sender = QLabel(f"<b>{self.meta.sender_name}</b> ({self.meta.sender_nif})")
        
        # Badge de confianza
        score_pct = int(float(self.meta.confidence_score) * 100)
        self.lbl_confidence = QLabel(f"Confianza: {score_pct}%")
        if self.is_high_confidence:
            self.lbl_confidence.setStyleSheet(
                "background-color: #2e7d32; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;"
            )
        else:
            self.lbl_confidence.setStyleSheet(
                "background-color: #e65100; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;"
            )

        header_layout.addWidget(self.lbl_sender)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_confidence)
        layout.addLayout(header_layout)

        # 2. Datos de Factura: Número, Fecha, Importe
        info_layout = QHBoxLayout()
        self.lbl_invoice = QLabel(f"Fra: <b>{self.meta.invoice_number}</b> | Fecha: {self.meta.issue_date}")
        self.lbl_total = QLabel(f"Total: <b>{self.meta.total_amount:.2f} €</b>")
        self.lbl_total.setStyleSheet("font-size: 13px; color: #1565c0; font-weight: bold;")

        info_layout.addWidget(self.lbl_invoice)
        info_layout.addStretch()
        info_layout.addWidget(self.lbl_total)
        layout.addLayout(info_layout)

        # 3. Cuenta contable PGC sugerida y editable
        account_layout = QHBoxLayout()
        account_lbl = QLabel("Cuenta PGC Gasto:")
        self.txt_account = QLineEdit(self.meta.suggested_pgc_account)
        self.txt_account.setMaximumWidth(120)
        self.txt_account.setToolTip("Subgrupo 60 (compras) o 62 (servicios exteriores)")

        account_name_lbl = QLabel(f"({self.meta.suggested_pgc_account_name})")
        account_name_lbl.setStyleSheet("color: #666; font-size: 11px;")

        account_layout.addWidget(account_lbl)
        account_layout.addWidget(self.txt_account)
        account_layout.addWidget(account_name_lbl)
        account_layout.addStretch()
        layout.addLayout(account_layout)

        # 4. Botones de acción [Aprobar y Contabilizar] y [Descartar]
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.btn_reject = QPushButton("Descartar")
        self.btn_reject.setStyleSheet("background-color: #f5f5f5; color: #c62828; border: 1px solid #c62828; padding: 4px 10px; border-radius: 4px;")
        self.btn_reject.clicked.connect(self._handle_reject)

        self.btn_approve = QPushButton("Aprobar y Contabilizar")
        self.btn_approve.setStyleSheet("background-color: #1976d2; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;")
        self.btn_approve.clicked.connect(self._handle_approve)

        action_layout.addWidget(self.btn_reject)
        action_layout.addWidget(self.btn_approve)
        layout.addLayout(action_layout)

    def _handle_approve(self):
        """Aprueba la propuesta con la cuenta PGC editada por el usuario."""
        confirmed_acc = self.txt_account.text().strip() or self.meta.suggested_pgc_account
        try:
            res = self.accounting_service.approve_proposal(
                proposal_id=self.proposal.proposal_id,
                confirmed_pgc_account=confirmed_acc
            )
            self.setEnabled(False)
            self.proposal_approved.emit(self.proposal.proposal_id)
        except Exception as e:
            QMessageBox.critical(self, "Error al aprobar", f"No se pudo contabilizar la factura: {e}")

    def _handle_reject(self):
        """Rechaza y descarta la propuesta."""
        try:
            self.accounting_service.reject_proposal(
                proposal_id=self.proposal.proposal_id,
                reason="Descartada manualmente por el usuario"
            )
            self.setEnabled(False)
            self.proposal_rejected.emit(self.proposal.proposal_id)
        except Exception as e:
            QMessageBox.critical(self, "Error al descartar", f"No se pudo descartar la propuesta: {e}")

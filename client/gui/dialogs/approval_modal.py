"""
Modal visual interactivo de Aprobación Humana (Human-in-the-Loop) en PyQt6.
Conforme al protocolo de gobernanza y requisitos de Alfonso AI Konta.
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QTextBrowser, QWidget
)
from PyQt6.QtCore import Qt
from client.gui.dialogs.base import AlfonsoBaseDialog


class ApprovalModalDialog(AlfonsoBaseDialog):
    """
    Diálogo modal de confirmación obligatoria para operaciones críticas
    (emisión fiscal Veri*Factu, liquidación de modelos, rectificativas, anulación, etc.).
    """
    def __init__(
        self,
        action_id: str,
        action_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
        api_base_url: Optional[str] = None
    ):
        super().__init__(parent=parent, title="APROBACIÓN HUMANA REQUERIDA (HITL)", modal=True)
        self.action_id = action_id
        self.action_type = action_type
        self.summary = summary
        self.details = details or {}
        self.api_base_url = api_base_url
        self.is_approved = False
        self.user_notes = ""

        self._build_content()

    def _build_content(self):
        # Título y tipo de acción
        header_lbl = QLabel(f"<b>Operación Crítica:</b> <span style='color: #38BDF8;'>{self.action_type}</span>")
        header_lbl.setStyleSheet("font-size: 14px; margin-bottom: 4px;")
        self.content_layout.addWidget(header_lbl)

        summary_lbl = QLabel(f"<b>Resumen:</b> {self.summary}")
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet("font-size: 13px; color: #E2E8F0; margin-bottom: 8px;")
        self.content_layout.addWidget(summary_lbl)

        # Advertencia de inmutabilidad fiscal / trazabilidad
        warning_box = QFrame()
        warning_box.setStyleSheet(
            "background-color: #1E293B; border: 1px solid #F59E0B; "
            "border-radius: 6px; padding: 8px;"
        )
        w_layout = QVBoxLayout(warning_box)
        w_layout.setContentsMargins(6, 6, 6, 6)
        w_lbl = QLabel("⚠️ <b>Aviso Legal:</b> Esta operación genera registros inmutables auditables según RD 1007/2023 y normativa tributaria.")
        w_lbl.setStyleSheet("color: #FCD34D; font-size: 11px;")
        w_lbl.setWordWrap(True)
        w_layout.addWidget(w_lbl)
        self.content_layout.addWidget(warning_box)

        # Desglose de detalles
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        details_html = "<div style='font-size: 12px; color: #CBD5E1; line-height: 1.5;'>"
        for k, v in self.details.items():
            formatted_key = k.replace("_", " ").capitalize()
            details_html += f"<b>{formatted_key}:</b> {v}<br/>"
        details_html += "</div>"
        self.details_label.setText(details_html)
        self.details_label.setStyleSheet("background-color: #0F172A; border-radius: 4px; padding: 8px; margin-top: 8px;")
        self.content_layout.addWidget(self.details_label)

        # Botones de Acción
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        buttons_layout.setContentsMargins(0, 12, 0, 4)

        self.btn_reject = QPushButton("✖ Rechazar / Editar")
        self.btn_reject.setStyleSheet(
            "background-color: #DC2626; color: white; font-weight: bold; "
            "padding: 8px 16px; border-radius: 6px; border: none;"
        )
        self.btn_reject.clicked.connect(self._on_reject_clicked)

        self.btn_approve = QPushButton("✔ Aprobar y Emitir")
        self.btn_approve.setStyleSheet(
            "background-color: #16A34A; color: white; font-weight: bold; "
            "padding: 8px 16px; border-radius: 6px; border: none;"
        )
        self.btn_approve.clicked.connect(self._on_approve_clicked)

        buttons_layout.addWidget(self.btn_reject)
        buttons_layout.addWidget(self.btn_approve)
        self.content_layout.addLayout(buttons_layout)

    def _on_approve_clicked(self):
        self.is_approved = True
        self._notify_api(True)
        self.accept()

    def _on_reject_clicked(self):
        self.is_approved = False
        self._notify_api(False)
        self.reject()

    def _notify_api(self, approved: bool):
        if not self.api_base_url or not self.action_id:
            return
        import requests
        try:
            url = f"{self.api_base_url.rstrip('/')}/api/v1/approvals/{self.action_id}/resolve"
            requests.post(
                url,
                json={"approved": approved, "user_notes": self.user_notes},
                timeout=5.0
            )
        except Exception:
            # Fallback sin prefijo v1
            try:
                url_fallback = f"{self.api_base_url.rstrip('/')}/approvals/{self.action_id}/resolve"
                requests.post(
                    url_fallback,
                    json={"approved": approved, "user_notes": self.user_notes},
                    timeout=5.0
                )
            except Exception:
                pass

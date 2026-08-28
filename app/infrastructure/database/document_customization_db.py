import sqlite3
from typing import Dict, Any
from app.domain.ports.document_customization_port import DocumentCustomizationPort
from app.adapters.memory.memory import _get_connection

class SqliteDocumentCustomizationAdapter(DocumentCustomizationPort):
    def get_customization(self, client_id: str) -> Dict[str, Any]:
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT logo_base64, primary_color, secondary_color, font_family, layout_template, elements_layout, quote_elements_layout, logo_width
                FROM document_customization WHERE client_id = ?
                """,
                (client_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "logo_base64": row["logo_base64"],
                    "primary_color": row["primary_color"],
                    "secondary_color": row["secondary_color"],
                    "font_family": row["font_family"],
                    "layout_template": row["layout_template"],
                    "elements_layout": row["elements_layout"] or '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]',
                    "quote_elements_layout": row["quote_elements_layout"] or '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]',
                    "logo_width": row["logo_width"] if row["logo_width"] is not None else 110
                }
            return {
                "logo_base64": None,
                "primary_color": "#1E293B",
                "secondary_color": "#64748B",
                "font_family": "Helvetica",
                "layout_template": "classic",
                "elements_layout": '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]',
                "quote_elements_layout": '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]',
                "logo_width": 110
            }

    def save_customization(self, client_id: str, data: Dict[str, Any]) -> None:
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO document_customization (
                    client_id, logo_base64, primary_color, secondary_color, font_family, layout_template, elements_layout, quote_elements_layout, logo_width, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(client_id) DO UPDATE SET
                    logo_base64 = excluded.logo_base64,
                    primary_color = excluded.primary_color,
                    secondary_color = excluded.secondary_color,
                    font_family = excluded.font_family,
                    layout_template = excluded.layout_template,
                    elements_layout = excluded.elements_layout,
                    quote_elements_layout = excluded.quote_elements_layout,
                    logo_width = excluded.logo_width,
                    updated_at = datetime('now')
                """,
                (
                    client_id,
                    data.get("logo_base64"),
                    data.get("primary_color", "#1E293B"),
                    data.get("secondary_color", "#64748B"),
                    data.get("font_family", "Helvetica"),
                    data.get("layout_template", "classic"),
                    data.get("elements_layout", '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]'),
                    data.get("quote_elements_layout", '["cabecera", "emisor_receptor", "detalles", "totales", "pie_verifactu"]'),
                    data.get("logo_width", 110)
                )
            )
            conn.commit()

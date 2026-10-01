"""
Servicio generador de Libros Registro Oficiales en formato Excel normalizado.
Conforme a los requisitos de la Orden HAC/773/2019 de la AEAT para autónomos y pymes.
"""

import io
from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


class TaxBooksService:
    """
    Genera los Libros Registro Obligatorios para la Agencia Tributaria en formato .xlsx:
    - Libro Registro de Facturas Expedidas.
    - Libro Registro de Facturas Recibidas.
    - Libro Registro de Bienes de Inversión.
    - Libro Registro de Ingresos y Gastos (Estimación Directa IRPF).
    """

    def __init__(self):
        self._header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        self._header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        self._alignment_center = Alignment(horizontal="center", vertical="center")
        self._alignment_right = Alignment(horizontal="right", vertical="center")

    def _create_styled_workbook(self, title: str, headers: List[str]) -> (openpyxl.Workbook, Any):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = title[:31]

        # Fila 1: Cabeceras
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = self._header_font
            cell.fill = self._header_fill
            cell.alignment = self._alignment_center

        return wb, ws

    def generate_invoices_issued_book(self, fiscal_year: int, invoices: List[Dict[str, Any]]) -> bytes:
        """
        Libro Registro de Facturas Expedidas (HAC/773/2019).
        Columnas: Fecha Expedición, Fecha Operación, Número Factura, Tipo Factura, NIF Destinatario, Nombre Destinatario, Base Imponible, Tipo IVA, Cuota IVA, Retención IRPF, Total Factura.
        """
        headers = [
            "Fecha Expedición", "Fecha Operación", "Número Factura", "Tipo Factura",
            "NIF Destinatario", "Nombre Destinatario", "Base Imponible", "Tipo IVA",
            "Cuota IVA", "Retención IRPF", "Total Factura"
        ]
        wb, ws = self._create_styled_workbook(f"Expedidas_{fiscal_year}", headers)

        for row_idx, inv in enumerate(invoices, start=2):
            series = inv.get("series", "")
            num = inv.get("number", "")
            invoice_num = f"{series}-{num}" if series else str(num)
            
            ws.cell(row=row_idx, column=1, value=str(inv.get("issue_date", "")))
            ws.cell(row=row_idx, column=2, value=str(inv.get("operation_date", "")))
            ws.cell(row=row_idx, column=3, value=invoice_num)
            ws.cell(row=row_idx, column=4, value=str(inv.get("invoice_type", "F1")))
            ws.cell(row=row_idx, column=5, value=str(inv.get("recipient_nif", "")))
            ws.cell(row=row_idx, column=6, value=str(inv.get("recipient_name", "")))
            ws.cell(row=row_idx, column=7, value=float(inv.get("base_amount", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=8, value=float(inv.get("vat_rate", 21.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=9, value=float(inv.get("tax_amount", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=10, value=float(inv.get("retention_amount", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=11, value=float(inv.get("total_amount", 0.0))).alignment = self._alignment_right

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def generate_invoices_received_book(self, fiscal_year: int, expenses: List[Dict[str, Any]]) -> bytes:
        """
        Libro Registro de Facturas Recibidas (HAC/773/2019).
        Columnas: Número Recepción, Fecha Expedición, Número Factura, NIF Proveedor, Nombre Proveedor, Base Imponible, Tipo IVA, Cuota IVA, Cuota Deducible, Total Factura.
        """
        headers = [
            "Número Recepción", "Fecha Expedición", "Número Factura",
            "NIF Proveedor", "Nombre Proveedor", "Base Imponible", "Tipo IVA",
            "Cuota IVA", "Cuota Deducible", "Total Factura"
        ]
        wb, ws = self._create_styled_workbook(f"Recibidas_{fiscal_year}", headers)

        for row_idx, exp in enumerate(expenses, start=2):
            ws.cell(row=row_idx, column=1, value=exp.get("reception_number", row_idx - 1))
            ws.cell(row=row_idx, column=2, value=str(exp.get("issue_date", "")))
            ws.cell(row=row_idx, column=3, value=str(exp.get("invoice_number", "")))
            ws.cell(row=row_idx, column=4, value=str(exp.get("supplier_nif", "")))
            ws.cell(row=row_idx, column=5, value=str(exp.get("supplier_name", "")))
            ws.cell(row=row_idx, column=6, value=float(exp.get("base_amount", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=7, value=float(exp.get("vat_rate", 21.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=8, value=float(exp.get("tax_amount", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=9, value=float(exp.get("deductible_tax_amount", exp.get("tax_amount", 0.0)))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=10, value=float(exp.get("total_amount", 0.0))).alignment = self._alignment_right

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def generate_investment_goods_book(self, fiscal_year: int, assets: List[Dict[str, Any]]) -> bytes:
        """
        Libro Registro de Bienes de Inversión (HAC/773/2019).
        Columnas: Código Elemento, Descripción, Fecha Adquisición, Valor Adquisición, Coeficiente Amortización (%), Amortización Ejercicio.
        """
        headers = [
            "Código Elemento", "Descripción", "Fecha Adquisición",
            "Valor Adquisición", "Coeficiente Amortización (%)", "Amortización Ejercicio"
        ]
        wb, ws = self._create_styled_workbook(f"Inversiones_{fiscal_year}", headers)

        for row_idx, ast in enumerate(assets, start=2):
            ws.cell(row=row_idx, column=1, value=str(ast.get("code", "")))
            ws.cell(row=row_idx, column=2, value=str(ast.get("description", "")))
            ws.cell(row=row_idx, column=3, value=str(ast.get("acquisition_date", "")))
            ws.cell(row=row_idx, column=4, value=float(ast.get("acquisition_value", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=5, value=float(ast.get("depreciation_rate", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=6, value=float(ast.get("annual_depreciation", 0.0))).alignment = self._alignment_right

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def generate_expenses_and_income_book(self, fiscal_year: int, incomes: List[Dict[str, Any]], expenses: List[Dict[str, Any]]) -> bytes:
        """
        Libro Registro de Ingresos y Gastos (Estimación Directa IRPF).
        """
        headers = ["Tipo Registro", "Fecha", "Concepto", "NIF Contraparte", "Importe Ingreso", "Importe Gasto"]
        wb, ws = self._create_styled_workbook(f"Ingresos_Gastos_{fiscal_year}", headers)

        row_idx = 2
        for inc in incomes:
            ws.cell(row=row_idx, column=1, value="INGRESO")
            ws.cell(row=row_idx, column=2, value=str(inc.get("date", "")))
            ws.cell(row=row_idx, column=3, value=str(inc.get("concept", "")))
            ws.cell(row=row_idx, column=4, value=str(inc.get("nif", "")))
            ws.cell(row=row_idx, column=5, value=float(inc.get("amount", 0.0))).alignment = self._alignment_right
            ws.cell(row=row_idx, column=6, value=0.0).alignment = self._alignment_right
            row_idx += 1

        for exp in expenses:
            ws.cell(row=row_idx, column=1, value="GASTO")
            ws.cell(row=row_idx, column=2, value=str(exp.get("date", "")))
            ws.cell(row=row_idx, column=3, value=str(exp.get("concept", "")))
            ws.cell(row=row_idx, column=4, value=str(exp.get("nif", "")))
            ws.cell(row=row_idx, column=5, value=0.0).alignment = self._alignment_right
            ws.cell(row=row_idx, column=6, value=float(exp.get("amount", 0.0))).alignment = self._alignment_right
            row_idx += 1

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

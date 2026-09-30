import os
import openpyxl
import pytest
from app.domain.services.excel_sync import ExcelSyncService
from app.infrastructure.database.connection_manager import _get_connection, write_transaction
from app.utils.encryption import encryptor

def test_excel_sync_canonical_flow(tmp_path):
    """Prueba de integración para la sincronización de facturas a Excel usando infraestructura canónica."""
    excel_file = str(tmp_path / "facturas_test.xlsx")

    # Insertar una factura de ingreso y una de gasto en la base de datos de test
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (
                invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount,
                category, quarter, year, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'firmada')
        """, (
            encryptor.encrypt("FAC-CANON-01"),
            encryptor.encrypt("2026-09-30"),
            encryptor.encrypt("Emisor SL"),
            encryptor.encrypt("B11111111"),
            encryptor.encrypt("Receptor SA"),
            encryptor.encrypt("A22222222"),
            encryptor.encrypt("1000.0"),
            encryptor.encrypt("21.0"),
            encryptor.encrypt("210.0"),
            encryptor.encrypt("0.0"),
            encryptor.encrypt("0.0"),
            encryptor.encrypt("1210.0"),
            "ingreso",
            3,
            2026
        ))

    # Sincronizar a Excel
    result_path = ExcelSyncService.sync_invoices_to_excel(output_path=excel_file)
    assert os.path.exists(result_path)

    # Validar el contenido del Excel generado
    wb = openpyxl.load_workbook(result_path)
    assert "Ingresos" in wb.sheetnames
    assert "Gastos" in wb.sheetnames

    ws_ingresos = wb["Ingresos"]
    assert ws_ingresos.max_row >= 2  # Encabezado + al menos 1 fila
    # Comprobar que el ID de factura fue desencriptado y guardado
    row_values = [cell.value for cell in ws_ingresos[2]]
    assert "FAC-CANON-01" in row_values

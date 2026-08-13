import os
import pytest
from pathlib import Path
from app.adapters.memory.memory import tenant_context, _get_connection
from app.domain.services.backup_service import BackupService
from app.tools.server.backup_tools import export_tenant_backup, import_tenant_backup

@pytest.mark.asyncio
async def test_backup_and_restore_cycle():
    # 1. Setup inicial de datos en el inquilino 'tenant_backup'
    token = tenant_context.set("tenant_backup")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products")
        cursor.execute("INSERT INTO products (sku, name, price, description, iva_rate) VALUES ('TEST-BKP', 'Producto Backup', 10.0, 'Desc', 21.0)")
        conn.commit()
    finally:
        conn.close()

    # 2. Exportar backup
    backup_dir = "data/test_backups"
    res_export = await export_tenant_backup(backup_dir=backup_dir)
    assert res_export["status"] == "ok"
    backup_file_path = res_export["file_path"]
    assert Path(backup_file_path).exists()

    # 3. Modificar la base de datos (simular cambios posteriores o borrado accidental)
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE sku = 'TEST-BKP'")
        conn.commit()
        # Verificar que el producto ya no existe
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku = 'TEST-BKP'")
        assert cursor.fetchone()[0] == 0
    finally:
        conn.close()

    # 4. Intentar restaurar un backup alterado (firma inválida)
    raw_backup_bytes = Path(backup_file_path).read_bytes()
    # Cambiar un byte del cuerpo cifrado (después de la cabecera "ALFONSO_BACKUP_v1" (17 bytes) y la firma (32 bytes))
    tampered_bytes = bytearray(raw_backup_bytes)
    tampered_bytes[60] = (tampered_bytes[60] + 1) % 256
    
    # Escribir temporalmente
    tampered_file = Path(backup_dir) / "backup_tampered.enc"
    tampered_file.write_bytes(tampered_bytes)
    
    res_restore_fail = await import_tenant_backup(str(tampered_file))
    assert res_restore_fail["status"] == "error"
    assert "Firma del backup inválida" in res_restore_fail["message"]

    # 5. Restaurar el backup original correcto
    res_restore_ok = await import_tenant_backup(backup_file_path)
    assert res_restore_ok["status"] == "ok"

    # 6. Validar que los datos originales se recuperaron con éxito
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products WHERE sku = 'TEST-BKP'")
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "Producto Backup"
    finally:
        conn.close()
        tenant_context.reset(token)

    # Limpieza de archivos físicos de prueba creados
    for f in (Path(backup_file_path), tampered_file):
        if f.exists():
            try:
                os.remove(f)
            except OSError:
                pass
                
    # Borrar archivo db de prueba del tenant
    db_file = BackupService.get_db_path("tenant_backup")
    if db_file.exists():
        try:
            os.remove(db_file)
        except OSError:
            pass

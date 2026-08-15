import os
from datetime import datetime
from pathlib import Path
from app.domain.services.backup_service import BackupService
from app.adapters.memory.memory import tenant_context
from app.utils.logger import tool_logger

async def export_tenant_backup(backup_dir: str = "data/backups") -> dict:
    """
    Exporta un backup cifrado y firmado digitalmente (.enc) de la base de datos del inquilino activo.
    """
    try:
        cid = tenant_context.get()
        backup_data = BackupService.export_backup()
        
        # Guardar en el directorio indicado
        out_dir = Path(backup_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = out_dir / f"backup_{cid}_{timestamp}.enc"
        backup_file.write_bytes(backup_data)
        
        # Registrar en el Ledger de Auditoría
        from app.domain.services.audit_ledger import AuditLedgerService
        AuditLedgerService.log_audit_event(
            event_type="EXPORT_BACKUP",
            description=f"Exportación de backup contable cifrada y firmada en: {backup_file.name}.",
            client_id=cid
        )
        
        tool_logger.info("Backup exportado correctamente: %s", backup_file)
        return {
            "status": "ok",
            "message": f"Backup exportado correctamente en: {backup_file.name}",
            "file_path": str(backup_file.resolve()).replace("\\", "/")
        }
    except Exception as e:
        tool_logger.exception("Error al exportar el backup")
        return {"status": "error", "message": str(e)}

async def import_tenant_backup(file_path: str) -> dict:
    """
    Importa y restaura un backup cifrado (.enc) a partir de su ruta de archivo, verificando su firma digital.
    """
    try:
        backup_file = Path(file_path)
        if not backup_file.exists():
            return {"status": "error", "message": f"El archivo de backup indicado no existe: {file_path}"}
            
        backup_bytes = backup_file.read_bytes()
        BackupService.restore_backup(backup_bytes)
        
        # Registrar en el Ledger de Auditoría
        from app.domain.services.audit_ledger import AuditLedgerService
        cid = tenant_context.get()
        AuditLedgerService.log_audit_event(
            event_type="IMPORT_BACKUP",
            description=f"Restauración de backup contable verificada e importada desde: {backup_file.name}.",
            client_id=cid
        )
        
        tool_logger.info("Backup restaurado correctamente: %s", file_path)
        return {
            "status": "ok",
            "message": "Copia de seguridad restaurada correctamente con éxito."
        }
    except Exception as e:
        tool_logger.exception("Error al restaurar el backup")
        return {"status": "error", "message": str(e)}

TOOLS = {
    "export_tenant_backup": export_tenant_backup,
    "import_tenant_backup": import_tenant_backup,
}

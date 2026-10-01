"""
Servicio de Backup y Restauración en Caliente para SQLite en modo WAL.
Utiliza la API nativa sqlite3.Connection.backup() para garantizar consistencia atómica sin bloqueo.
"""

import os
import sqlite3
import shutil
from pathlib import Path
from typing import Optional
from app.infrastructure.database.connection_manager import _get_connection, _resolve_target_path


class BackupService:
    """Gestiona copias de seguridad de la base de datos única local memory.db."""

    def create_backup(
        self,
        source_conn: Optional[sqlite3.Connection] = None,
        destination_path: Optional[str] = None,
        client_id: str = "default"
    ) -> str:
        """
        Copia atómicamente la base de datos origen a un archivo de destino en caliente.
        """
        conn = source_conn or _get_connection(client_id)
        
        if not destination_path:
            backup_dir = Path("data/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            destination_path = str(backup_dir / f"backup_{client_id}.db")
        else:
            Path(destination_path).parent.mkdir(parents=True, exist_ok=True)

        dst_conn = sqlite3.connect(destination_path)
        try:
            # Transferencia atómica página a página con la API nativa de SQLite
            conn.backup(dst_conn, pages=250)
        finally:
            dst_conn.close()

        return destination_path

    def restore_backup(self, backup_path: str, target_conn: sqlite3.Connection) -> None:
        """
        Restaura un fichero de copia sobre una conexión de base de datos activa.
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Fichero de backup no encontrado: {backup_path}")

        src_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(target_conn, pages=250)
        finally:
            src_conn.close()

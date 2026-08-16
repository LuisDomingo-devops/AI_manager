import sqlite3
import importlib
import pkgutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Callable
import logging

logger = logging.getLogger("migrations")

class Migration:
    def __init__(self, version: str, description: str, upgrade_fn: Callable[[sqlite3.Connection], None]):
        self.version = version
        self.description = description
        self.upgrade = upgrade_fn


class MigrationRunner:
    """
    Motor de migraciones versionadas y reproducibles para SQLite.
    Garantiza la evolución del esquema de base de datos sin pérdida de datos y de forma transaccional.
    """

    MIGRATIONS_TABLE = "schema_migrations"

    @classmethod
    def init_migrations_table(cls, conn: sqlite3.Connection):
        """Crea la tabla de control de versiones de esquema si no existe."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls.MIGRATIONS_TABLE} (
                version     TEXT PRIMARY KEY,
                description TEXT,
                applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    @classmethod
    def get_applied_migrations(cls, conn: sqlite3.Connection) -> List[str]:
        """Obtiene la lista de identificadores de migraciones ya aplicadas."""
        cls.init_migrations_table(conn)
        cursor = conn.cursor()
        cursor.execute(f"SELECT version FROM {cls.MIGRATIONS_TABLE} ORDER BY version ASC")
        return [row[0] for row in cursor.fetchall()]

    @classmethod
    def apply_migration(cls, conn: sqlite3.Connection, migration: Migration) -> bool:
        """Ejecuta una migración individual dentro de una transacción atómica."""
        logger.info("Aplicando migración: %s - %s", migration.version, migration.description)
        try:
            migration.upgrade(conn)
            now_str = datetime.now().isoformat()
            conn.execute(
                f"INSERT INTO {cls.MIGRATIONS_TABLE} (version, description, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.description, now_str)
            )
            conn.commit()
            logger.info("Migración %s aplicada con éxito.", migration.version)
            return True
        except Exception as e:
            conn.rollback()
            logger.exception("Error al aplicar la migración %s: %s", migration.version, str(e))
            raise

    @classmethod
    def load_available_migrations(cls) -> List[Migration]:
        """Carga dinámicamente los módulos de migración del directorio migrations/versions/."""
        migrations = []
        versions_dir = Path(__file__).resolve().parents[3] / "migrations" / "versions"
        if not versions_dir.exists():
            return migrations

        for file in sorted(versions_dir.glob("*.py")):
            if file.name.startswith("__"):
                continue
            module_name = f"migrations.versions.{file.stem}"
            try:
                mod = importlib.import_module(module_name)
                version = getattr(mod, "VERSION", file.stem.split("_")[0])
                description = getattr(mod, "DESCRIPTION", file.stem)
                upgrade_fn = getattr(mod, "upgrade", None)
                if upgrade_fn:
                    migrations.append(Migration(version=str(version), description=description, upgrade_fn=upgrade_fn))
            except Exception as e:
                logger.warning("No se pudo cargar la migración %s: %s", file.name, str(e))

        migrations.sort(key=lambda m: m.version)
        return migrations

    @classmethod
    def run_pending_migrations(cls, conn: sqlite3.Connection) -> List[str]:
        """Ejecuta todas las migraciones pendientes en orden secuencial."""
        cls.init_migrations_table(conn)
        applied = set(cls.get_applied_migrations(conn))
        available = cls.load_available_migrations()

        applied_now = []
        for migration in available:
            if migration.version not in applied:
                cls.apply_migration(conn, migration)
                applied_now.append(migration.version)

        return applied_now

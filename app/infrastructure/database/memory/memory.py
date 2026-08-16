"""
MEMORY — Memoria de diálogo y almacenamiento de historial.

¿QUÉ HACE?
Mantiene el historial de la conversación actual por sesión en memoria volátil (RAM).

¿CUÁNDO LO HACE?
Durante el procesamiento de consultas para recuperar mensajes previos del usuario y el asistente e inyectarlos en el prompt.

¿CÓMO LO HACE?
Almacenando listas de mensajes estructurados en un diccionario indexado por `session_id` con hilos seguros.

¿CON QUÉ OTROS SCRIPTS ESTÁ RELACIONADO?
- app/domain/planner_orchestrator.py (consulta el historial para contextualizar al modelo)
- app/api/routes.py (ofrece endpoints para leer, listar y borrar historiales por sesión)
"""

import json
import os
import sqlite3
import sys
import contextvars
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List
from app.domain.ports.memory_port import MemoryPort

tenant_context = contextvars.ContextVar("tenant_context", default="default")

# 1. DETECCIÓN DE ENTORNO DE PRUEBAS
# Si se detecta pytest, usamos una base de datos temporal diferente (memory_test.db)
# para evitar colisiones con la base de datos de desarrollo y prevenir bloqueos.
IS_TESTING = "pytest" in sys.modules or os.getenv("TESTING") == "true"

if os.getenv("ALFONSO_DB_PATH"):
    DB_PATH = Path(os.getenv("ALFONSO_DB_PATH"))
elif IS_TESTING:
    DB_PATH = Path(__file__).resolve().parents[3] / "data" / "memory_test.db"
else:
    DB_PATH = Path(__file__).resolve().parents[3] / "data" / "memory.db"

# Variable de control para la inicialización perezosa (Lazy Initialization)
_db_initialized = False


def _init_db_schema(conn: sqlite3.Connection) -> None:
    """Crea las tablas e índices necesarios si no existen."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            client_id   TEXT    NOT NULL DEFAULT 'default',
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_metadata (
            session_id   TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            discipline   TEXT NOT NULL DEFAULT 'general',
            project_name TEXT DEFAULT 'default',
            is_persistent INTEGER DEFAULT 1,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id      TEXT,
            date            TEXT,
            issuer_name     TEXT,
            issuer_nif      TEXT,
            receiver_name   TEXT,
            receiver_nif    TEXT,
            base_imponible  REAL,
            iva_rate        REAL,
            iva_amount      REAL,
            irpf_rate       REAL,
            irpf_amount     REAL,
            total_amount    REAL,
            category        TEXT,
            quarter         INTEGER,
            year            INTEGER,
            file_path       TEXT,
            status          TEXT DEFAULT 'firmada',
            concept         TEXT,
            blind_index     TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id        TEXT NOT NULL UNIQUE,
            date            TEXT NOT NULL,
            client_name     TEXT NOT NULL,
            client_nif      TEXT NOT NULL,
            base_imponible  TEXT NOT NULL,
            iva_rate        TEXT NOT NULL,
            iva_amount      TEXT NOT NULL,
            irpf_rate       TEXT NOT NULL,
            irpf_amount     TEXT NOT NULL,
            total_amount    TEXT NOT NULL,
            concept         TEXT NOT NULL,
            file_path       TEXT,
            status          TEXT DEFAULT 'borrador',
            signature       TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sku           TEXT NOT NULL UNIQUE,
            name          TEXT NOT NULL,
            description   TEXT,
            price         REAL NOT NULL,
            iva_rate      REAL NOT NULL DEFAULT 21.0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id      TEXT NOT NULL UNIQUE,
            invoice_id      TEXT NOT NULL,
            date            TEXT NOT NULL,
            amount          REAL NOT NULL,
            payment_method  TEXT NOT NULL,
            notes           TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN client_id TEXT NOT NULL DEFAULT 'default'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN status TEXT DEFAULT 'firmada'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN concept TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN blind_index TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE quotes ADD COLUMN signature TEXT")
    except sqlite3.OperationalError:
        pass

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_session
        ON messages (session_id, client_id, id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_invoices_blind_index
        ON invoices (blind_index)
    """)
    
    # --- PLAN GENERAL CONTABLE (PGC) PARA PYMES ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pgc_accounts (
            code        TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date  TEXT NOT NULL,
            concept     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL,
            account_code     TEXT NOT NULL,
            debe             TEXT NOT NULL,
            haber            TEXT NOT NULL,
            FOREIGN KEY(journal_entry_id) REFERENCES journal_entries(id),
            FOREIGN KEY(account_code) REFERENCES pgc_accounts(code)
        )
    """)
    
    # --- CIERRE DE EJERCICIO Y ESTADO FISCAL ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_year_status (
            year        INTEGER PRIMARY KEY,
            is_closed   INTEGER NOT NULL DEFAULT 0,
            closed_at   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- ESTADOS FACTURA B2B (LEY CREA Y CRECE 18/2022) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS b2b_invoice_status_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id     TEXT NOT NULL,
            status         TEXT NOT NULL,
            status_date    TEXT NOT NULL,
            reason         TEXT,
            payment_method TEXT,
            payment_date   TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Inicializar catálogo contable básico del PGC
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pgc_accounts")
    if cursor.fetchone()[0] == 0:
        default_accounts = [
            ("10000000", "Capital Social", "patrimonio"),
            ("12900000", "Resultado del ejercicio", "patrimonio"),
            ("21700000", "Equipos para procesos de información", "activo"),
            ("40000000", "Proveedores (Acreedores comerciales)", "pasivo"),
            ("43000000", "Clientes", "activo"),
            ("47200021", "Hacienda Pública, IVA soportado al 21%", "activo"),
            ("47300000", "Hacienda Pública, retenciones y pagos a cuenta", "activo"),
            ("47510000", "Hacienda Pública, acreedora por retenciones practicadas", "pasivo"),
            ("47700021", "Hacienda Pública, IVA repercutido al 21%", "pasivo"),
            ("57000000", "Caja, euros (efectivo)", "activo"),
            ("57200001", "Banco de la empresa (cuenta corriente)", "activo"),
            ("60000000", "Compras de mercaderías / suministros", "gasto"),
            ("62900000", "Otros servicios / Gastos diversos", "gasto"),
            ("70000000", "Ventas de mercaderías", "ingreso"),
            ("70500000", "Prestación de servicios de consultoría/desarrollo", "ingreso"),
        ]
        cursor.executemany("INSERT INTO pgc_accounts (code, name, type) VALUES (?, ?, ?)", default_accounts)
    else:
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('12900000', 'Resultado del ejercicio', 'patrimonio')")
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47300000', 'Hacienda Pública, retenciones y pagos a cuenta', 'activo')")
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47510000', 'Hacienda Pública, acreedora por retenciones practicadas', 'pasivo')")
        conn.commit()
        
    # --- CONCILIACIÓN BANCARIA ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_connections (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            alias          TEXT NOT NULL,
            provider       TEXT NOT NULL,
            bank_name      TEXT,
            iban           TEXT,
            credentials    TEXT,
            status         TEXT DEFAULT 'active',
            last_sync_at   TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_movements (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_date TEXT NOT NULL,
            concept       TEXT NOT NULL,
            amount        REAL NOT NULL,
            reference     TEXT,
            invoice_id    TEXT,
            reconciled    INTEGER DEFAULT 0,
            connection_id INTEGER REFERENCES bank_connections(id),
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    try:
        conn.execute("ALTER TABLE bank_movements ADD COLUMN connection_id INTEGER REFERENCES bank_connections(id)")
    except sqlite3.OperationalError:
        pass

    # --- SUSCRIPCIÓN PREMIUM Y TRANSFERENCIAS ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscription_status (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            tier                  TEXT NOT NULL DEFAULT 'free',
            billing_cycle_start   TEXT NOT NULL,
            extra_transfer_fee    REAL NOT NULL DEFAULT 0.50
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_transfers (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_date       TEXT NOT NULL,
            recipient_name      TEXT NOT NULL,
            recipient_iban      TEXT NOT NULL,
            amount              REAL NOT NULL,
            concept             TEXT,
            status              TEXT DEFAULT 'initiated',
            extra_charge        REAL DEFAULT 0.00,
            connection_id       INTEGER REFERENCES bank_connections(id)
        )
    """)
    
    # Insertar suscripción por defecto si no existe
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM subscription_status")
    if cursor.fetchone()[0] == 0:
        import datetime
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO subscription_status (tier, billing_cycle_start, extra_transfer_fee) VALUES ('free', ?, 0.50)", (today_str,))
        
    # --- CONFIGURACIÓN DE PERFIL CONTABLE Y CERTIFICADOS ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type     TEXT NOT NULL,
            nif           TEXT NOT NULL,
            razon_social  TEXT NOT NULL,
            direccion     TEXT,
            cert_path     TEXT,
            cert_password TEXT,
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- PROYECTOS Y TRABAJOS EN CURSO (WIP) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            client_name   TEXT NOT NULL,
            client_nif    TEXT NOT NULL,
            budget        REAL NOT NULL,
            status        TEXT NOT NULL DEFAULT 'en_progreso',
            description   TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- BASE DE DATOS DE CLIENTES ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            nif           TEXT NOT NULL,
            email         TEXT NOT NULL,
            address       TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    # --- DIARIO DE SESIONES ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_diary (
            date          TEXT PRIMARY KEY,
            summary       TEXT,
            messages      TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # --- EJECUCIÓN DE MIGRACIONES VERSIONADAS ---
    try:
        from app.infrastructure.database.migrations import MigrationRunner
        MigrationRunner.run_pending_migrations(conn)
    except Exception:
        pass

    conn.commit()


# Registro global de esquemas inicializados por archivo de base de datos
_initialized_dbs = set()
# Inquilino activo (por defecto 'default' en modo de licencia básico para proteger el negocio y ventas)
_active_tenant = None

def _get_connection(client_id: str = None) -> sqlite3.Connection:
    global _active_tenant
    
    # Resolver client_id: usar tenant_context si no se pasa de forma explícita
    cid = (client_id or tenant_context.get()).strip().lower()
    
    # 1. Determinar el archivo de base de datos del Tenant
    if IS_TESTING:
        if cid == "default":
            target_path = DB_PATH
        else:
            target_path = DB_PATH.parent / f"test_memory_{cid}.db"
    else:
        target_path = DB_PATH.parent / f"memory_{cid}.db"
        
    if str(target_path) != ":memory:":
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # 2. Inicializar el esquema si es la primera vez que abrimos este archivo concreto
    db_key = str(target_path)
    if db_key not in _initialized_dbs:
        _init_db_schema(conn)
        _initialized_dbs.add(db_key)
        
    return conn


class SessionMemory(MemoryPort):
    """
    Gestiona el historial de conversación por sesión.

    - Persiste en SQLite para sobrevivir reinicios.
    - Mantiene una caché en RAM (deque) para lecturas rápidas.
    - Aplica un límite max_messages: solo se guardan los N mensajes más recientes.
    """

    def __init__(self, max_messages: int = 20, is_testing: bool | None = None):
        self.max_messages = max_messages
        # Caché en RAM: session_id:client_id → deque de dicts {role, content}
        self._cache: Dict[str, Deque[Dict[str, str]]] = {}
        self.is_testing = is_testing if is_testing is not None else IS_TESTING

    def _resolve_session_id(self, session_id: str) -> str:
        if not session_id:
            return session_id
        if self.is_testing:
            return session_id
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        return f"daily_{today_str}"

    # ------------------------------------------------------------------
    # Caché
    # ------------------------------------------------------------------

    def _ensure_loaded(self, session_id: str, client_id: str | None = None) -> None:
        """Carga el historial desde SQLite si no está en caché."""
        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        if cache_key in self._cache:
            return

        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ? AND client_id = ?
                ORDER BY id ASC
                """,
                (session_id, cid),
            ).fetchall()

        from app.utils.encryption import encryptor
        self._cache[cache_key] = deque(
            [{"role": r["role"], "content": encryptor.decrypt(r["content"])} for r in rows],
            maxlen=self.max_messages,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def add_message(self, session_id: str, role: str, content: str, client_id: str | None = None) -> None:
        if not session_id:
            return

        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        self._ensure_loaded(session_id, client_id)
        self._cache[cache_key].append({"role": role, "content": content})

        from app.utils.encryption import encryptor
        encrypted_content = encryptor.encrypt(content)

        with _get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, client_id, role, content) VALUES (?, ?, ?, ?)",
                (session_id, cid, role, encrypted_content),
            )
            # Borrar mensajes viejos que superen el límite
            conn.execute(
                """
                DELETE FROM messages
                WHERE session_id = ? AND client_id = ?
                AND id NOT IN (
                    SELECT id FROM messages
                    WHERE session_id = ? AND client_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (session_id, cid, session_id, cid, self.max_messages),
            )
            
            # --- ARCHIVADO EN DIARIO DE SESIONES ---
            from datetime import datetime
            import json
            if self.is_testing:
                date_str = session_id
            else:
                date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
            
            row = conn.execute("SELECT messages FROM session_diary WHERE date = ?", (date_str,)).fetchone()
            if row and row["messages"]:
                try:
                    archived = json.loads(row["messages"])
                except Exception:
                    archived = []
            else:
                archived = []
                
            archived.append({
                "role": role,
                "content": content,
                "created_at": datetime.now().isoformat()
            })
            
            conn.execute(
                """
                INSERT INTO session_diary (date, summary, messages, updated_at)
                VALUES (?, '', ?, datetime('now'))
                ON CONFLICT(date) DO UPDATE SET
                    messages = ?,
                    updated_at = datetime('now')
                """,
                (date_str, json.dumps(archived, ensure_ascii=False), json.dumps(archived, ensure_ascii=False))
            )
            conn.commit()

    def get_history(self, session_id: str, client_id: str | None = None) -> List[Dict[str, str]]:
        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        self._ensure_loaded(session_id, client_id)
        return list(self._cache.get(cache_key, []))

    def get_summary(self, session_id: str, client_id: str | None = None) -> str:
        history = self.get_history(session_id, client_id)
        if not history:
            return ""
        return "\n".join(f"{entry['role']}: {entry['content']}" for entry in history)

    def clear(self, session_id: str, client_id: str | None = None) -> None:
        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        self._cache.pop(cache_key, None)
        with _get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ? AND client_id = ?", (session_id, cid))
            from datetime import datetime
            if self.is_testing:
                date_str = session_id
            else:
                date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
            conn.execute("DELETE FROM session_diary WHERE date = ?", (date_str,))
            conn.commit()

    def update_summary(self, session_id: str, summary: str) -> None:
        session_id = self._resolve_session_id(session_id)
        from datetime import datetime
        if self.is_testing:
            date_str = session_id
        else:
            date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO session_diary (date, summary, messages, updated_at)
                VALUES (?, ?, '[]', datetime('now'))
                ON CONFLICT(date) DO UPDATE SET
                    summary = ?,
                    updated_at = datetime('now')
                """,
                (date_str, summary, summary)
            )
            conn.commit()

    def get_diary_entry(self, session_id: str) -> dict | None:
        session_id = self._resolve_session_id(session_id)
        from datetime import datetime
        if self.is_testing:
            date_str = session_id
        else:
            date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT date, summary, messages, created_at, updated_at FROM session_diary WHERE date = ?",
                (date_str,)
            ).fetchone()
        if row:
            return {
                "date": row["date"],
                "summary": row["summary"],
                "messages": row["messages"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None

    def list_sessions(self, client_id: str | None = None) -> List[str]:
        """Devuelve todos los session_id con historial guardado."""
        cid = client_id or "default"
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT session_id FROM messages WHERE client_id = ? ORDER BY session_id",
                (cid,)
                ).fetchall()
        return [r["session_id"] for r in rows]

    def upsert_metadata(self, session_id: str, title: str, discipline: str = "general", project_name: str = "default", is_persistent: bool = True) -> None:
        """Crea o actualiza los metadatos de una conversación."""
        persistent_val = 1 if is_persistent else 0
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversation_metadata (session_id, title, discipline, project_name, is_persistent, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(session_id) DO UPDATE SET
                    title = excluded.title,
                    discipline = excluded.discipline,
                    project_name = excluded.project_name,
                    is_persistent = excluded.is_persistent,
                    updated_at = datetime('now')
                """,
                (session_id, title, discipline, project_name, persistent_val)
            )
            conn.commit()

    def get_metadata(self, session_id: str) -> dict | None:
        """Recupera los metadatos de una conversación."""
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT session_id, title, discipline, project_name, is_persistent, created_at, updated_at FROM conversation_metadata WHERE session_id = ?",
                (session_id,)
            ).fetchone()
        if row:
            return {
                "session_id": row["session_id"],
                "title": row["title"],
                "discipline": row["discipline"],
                "project_name": row["project_name"],
                "is_persistent": bool(row["is_persistent"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None

    def list_persistent_conversations(self) -> List[dict]:
        """Devuelve todas las conversaciones marcadas como persistentes."""
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT session_id, title, discipline, project_name, created_at, updated_at FROM conversation_metadata WHERE is_persistent = 1 ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


# Instancia global compartida por toda la aplicación
memory = SessionMemory()

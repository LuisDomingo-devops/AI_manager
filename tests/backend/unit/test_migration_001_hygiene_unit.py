import re
from pathlib import Path
import pytest

def test_migration_001_has_no_duplicate_table_definitions():
    """Valida que cada tabla tenga una única definición CREATE TABLE en 001_initial_core_schema.py."""
    migration_path = Path("migrations/versions/001_initial_core_schema.py")
    assert migration_path.exists(), "El archivo de migración 001 no existe"
    
    content = migration_path.read_text(encoding="utf-8")
    
    # Patrón para detectar CREATE TABLE (IF NOT EXISTS)? table_name
    pattern = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)", re.IGNORECASE)
    matches = pattern.findall(content)
    
    # Contar ocurrencias por tabla
    table_counts = {}
    for table in matches:
        table_counts[table] = table_counts.get(table, 0) + 1
        
    duplicated_tables = {tbl: count for tbl, count in table_counts.items() if count > 1}
    
    # Las tablas críticas identificadas no deben estar duplicadas
    critical_tables = [
        "invoices",
        "contacts",
        "payments",
        "bank_transfers",
        "messages",
        "subscription_status",
        "conversation_metadata",
        "session_diary",
        "invoice_items",
    ]
    
    for table in critical_tables:
        assert table_counts.get(table, 0) == 1, (
            f"La tabla '{table}' debe tener exactamente 1 definición CREATE TABLE, pero tiene {table_counts.get(table, 0)}"
        )
        
    assert not duplicated_tables, f"Tablas duplicadas detectadas en la migración 001: {duplicated_tables}"


def test_migration_001_has_no_pasted_fix_blocks():
    """Valida que los comentarios de parches copiados/pegados de IA hayan sido eliminados."""
    migration_path = Path("migrations/versions/001_initial_core_schema.py")
    content = migration_path.read_text(encoding="utf-8")
    
    assert "From 015_qa_schema_fixes.py" not in content, "Persiste el bloque parcheado de 015_qa_schema_fixes.py"
    assert "From 017_missing_core_tables.py" not in content, "Persiste el bloque parcheado de 017_missing_core_tables.py"

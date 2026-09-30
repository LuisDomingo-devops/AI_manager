import sqlite3
import importlib
import pytest

migration_001 = importlib.import_module("migrations.versions.001_initial_core_schema")
upgrade = migration_001.upgrade

def test_schema_idempotency_and_constraints_qa(clean_db_conn):
    """Prueba QA de idempotencia estricta y restricciones de integridad del esquema consolidado."""
    # Primera ejecución
    upgrade(clean_db_conn)
    cursor = clean_db_conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM pgc_accounts")
    count_pgc_first = cursor.fetchone()[0]
    
    # Segunda ejecución (debe ser completamente idempotente)
    upgrade(clean_db_conn)
    cursor.execute("SELECT COUNT(*) FROM pgc_accounts")
    count_pgc_second = cursor.fetchone()[0]
    
    assert count_pgc_first == count_pgc_second, "La re-ejecución del esquema 001 alteró el conteo de cuentas PGC"
    
    cursor.execute("SELECT COUNT(*) FROM subscription_status")
    count_sub = cursor.fetchone()[0]
    assert count_sub == 1, f"El estado de suscripción debe ser único, pero hay {count_sub} registros"


def test_schema_foreign_keys_and_bulk_inserts_qa(clean_db_conn):
    """Prueba QA de claves foráneas e inserción volumétrica en esquema aprovisionado."""
    upgrade(clean_db_conn)
    cursor = clean_db_conn.cursor()

    # 1. Verificar violación de FK en invoice_items
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO invoice_items (invoice_id, description_override, quantity, unit_price, subtotal)
            VALUES ('999999', 'Producto Fantasma', 1.0, 100.0, 100.0)
        """)
        clean_db_conn.commit()

    # 2. Inserción volumétrica de 50 contactos y 50 facturas
    for i in range(50):
        cursor.execute(f"""
            INSERT INTO contacts (name, nif, email, contact_type)
            VALUES ('Empresa QA {i}', 'B999999{i:02d}', 'qa_{i}@test.com', 'Cliente')
        """)
        c_id = cursor.lastrowid
        cursor.execute(f"""
            INSERT INTO invoices (
                invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, total_amount, quarter, year, contact_id
            ) VALUES (
                'QA-FAC-{i:04d}', '2026-09-30', 'Alfonso', '12345678Z',
                'Empresa QA {i}', 'B999999{i:02d}', 100.0, 21.0, 21.0, 121.0, 3, 2026, ?
            )
        """, (c_id,))
    clean_db_conn.commit()

    cursor.execute("SELECT COUNT(*) FROM invoices")
    assert cursor.fetchone()[0] == 50
    cursor.execute("SELECT COUNT(*) FROM contacts")
    assert cursor.fetchone()[0] == 50

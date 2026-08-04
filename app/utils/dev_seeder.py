import sqlite3
from datetime import datetime
from app.adapters.memory.memory import _get_connection, _init_db_schema
from app.utils.encryption import encryptor

def seed_database():
    print("Iniciando la siembra de la base de datos (Seeder) con datos de prueba realistas para 2026...")
    
    # Asegurar que el esquema existe
    with _get_connection() as conn:
        _init_db_schema(conn)
        cursor = conn.cursor()
        
        # Limpiar facturas existentes para evitar duplicados en la demo
        cursor.execute("DELETE FROM invoices")
        conn.commit()
        print("✓ Tabla 'invoices' limpiada.")
        
        # Datos de prueba (5 ingresos, 5 gastos del Q1 2026)
        invoices_data = [
            # --- INGRESOS (Emitidas por LUIS DOMINGO NIF 12345678Z) ---
            {
                "invoice_id": "F-2026-001",
                "date": "15/01/2026",
                "issuer_name": "LUIS DOMINGO",
                "issuer_nif": "12345678Z",
                "receiver_name": "ACME CORP S.L.",
                "receiver_nif": "B12345678",
                "base_imponible": 1500.0,
                "iva_rate": 21.0,
                "iva_amount": 315.0,
                "irpf_rate": 15.0,
                "irpf_amount": 225.0,
                "total_amount": 1590.0,
                "category": "ingreso",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/facturas/F-2026-001.pdf"
            },
            {
                "invoice_id": "F-2026-002",
                "date": "28/01/2026",
                "issuer_name": "LUIS DOMINGO",
                "issuer_nif": "12345678Z",
                "receiver_name": "GLOBAL TECH SPAIN",
                "receiver_nif": "B87654321",
                "base_imponible": 2500.0,
                "iva_rate": 21.0,
                "iva_amount": 525.0,
                "irpf_rate": 15.0,
                "irpf_amount": 375.0,
                "total_amount": 2650.0,
                "category": "ingreso",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/facturas/F-2026-002.pdf"
            },
            {
                "invoice_id": "F-2026-003",
                "date": "10/02/2026",
                "issuer_name": "LUIS DOMINGO",
                "issuer_nif": "12345678Z",
                "receiver_name": "SERVICIOS LOGISTICOS MADRID",
                "receiver_nif": "B11223344",
                "base_imponible": 800.0,
                "iva_rate": 21.0,
                "iva_amount": 168.0,
                "irpf_rate": 15.0,
                "irpf_amount": 120.0,
                "total_amount": 848.0,
                "category": "ingreso",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/facturas/F-2026-003.pdf"
            },
            {
                "invoice_id": "F-2026-004",
                "date": "20/02/2026",
                "issuer_name": "LUIS DOMINGO",
                "issuer_nif": "12345678Z",
                "receiver_name": "ACME CORP S.L.",
                "receiver_nif": "B12345678",
                "base_imponible": 1500.0,
                "iva_rate": 21.0,
                "iva_amount": 315.0,
                "irpf_rate": 15.0,
                "irpf_amount": 225.0,
                "total_amount": 1590.0,
                "category": "ingreso",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/facturas/F-2026-004.pdf"
            },
            {
                "invoice_id": "F-2026-005",
                "date": "05/03/2026",
                "issuer_name": "LUIS DOMINGO",
                "issuer_nif": "12345678Z",
                "receiver_name": "GLOBAL TECH SPAIN",
                "receiver_nif": "B87654321",
                "base_imponible": 1200.0,
                "iva_rate": 21.0,
                "iva_amount": 252.0,
                "irpf_rate": 15.0,
                "irpf_amount": 180.0,
                "total_amount": 1272.0,
                "category": "ingreso",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/facturas/F-2026-005.pdf"
            },
            
            # --- GASTOS (Recibidas por LUIS DOMINGO de varios proveedores) ---
            {
                "invoice_id": "G-2026-001",
                "date": "03/01/2026",
                "issuer_name": "TELEFONICA DE ESPAÑA S.A.",
                "issuer_nif": "A88776655",
                "receiver_name": "LUIS DOMINGO",
                "receiver_nif": "12345678Z",
                "base_imponible": 60.0,
                "iva_rate": 21.0,
                "iva_amount": 12.6,
                "irpf_rate": 0.0,
                "irpf_amount": 0.0,
                "total_amount": 72.6,
                "category": "gasto",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/gastos/G-2026-001.pdf"
            },
            {
                "invoice_id": "G-2026-002",
                "date": "15/01/2026",
                "issuer_name": "COWORKING MADRID CENTRO",
                "issuer_nif": "B99887766",
                "receiver_name": "LUIS DOMINGO",
                "receiver_nif": "12345678Z",
                "base_imponible": 250.0,
                "iva_rate": 21.0,
                "iva_amount": 52.5,
                "irpf_rate": 0.0,
                "irpf_amount": 0.0,
                "total_amount": 302.5,
                "category": "gasto",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/gastos/G-2026-002.pdf"
            },
            {
                "invoice_id": "G-2026-003",
                "date": "02/02/2026",
                "issuer_name": "AMAZON WEB SERVICES",
                "issuer_nif": "N0011223F",
                "receiver_name": "LUIS DOMINGO",
                "receiver_nif": "12345678Z",
                "base_imponible": 120.0,
                "iva_rate": 21.0,
                "iva_amount": 25.2,
                "irpf_rate": 0.0,
                "irpf_amount": 0.0,
                "total_amount": 145.2,
                "category": "gasto",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/gastos/G-2026-003.pdf"
            },
            {
                "invoice_id": "G-2026-004",
                "date": "04/02/2026",
                "issuer_name": "TELEFONICA DE ESPAÑA S.A.",
                "issuer_nif": "A88776655",
                "receiver_name": "LUIS DOMINGO",
                "receiver_nif": "12345678Z",
                "base_imponible": 60.0,
                "iva_rate": 21.0,
                "iva_amount": 12.6,
                "irpf_rate": 0.0,
                "irpf_amount": 0.0,
                "total_amount": 72.6,
                "category": "gasto",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/gastos/G-2026-004.pdf"
            },
            {
                "invoice_id": "G-2026-005",
                "date": "10/03/2026",
                "issuer_name": "ASESORIA FISCAL RAPIDA S.L.",
                "issuer_nif": "B55667788",
                "receiver_name": "LUIS DOMINGO",
                "receiver_nif": "12345678Z",
                "base_imponible": 90.0,
                "iva_rate": 21.0,
                "iva_amount": 18.9,
                "irpf_rate": 0.0,
                "irpf_amount": 0.0,
                "total_amount": 108.9,
                "category": "gasto",
                "quarter": 1,
                "year": 2026,
                "file_path": "c:/Users/luisd/Desktop/Alfonso_Autonomo/gastos/G-2026-005.pdf"
            }
        ]
        
        # Limpiar tablas PGC
        cursor.execute("DELETE FROM ledger_entries")
        cursor.execute("DELETE FROM journal_entries")
        conn.commit()
        print("✓ Tablas PGC ('journal_entries', 'ledger_entries') limpiadas.")

        # Insertar registros cifrados
        from app.domain.services.ledger_service import LedgerService
        
        for data in invoices_data:
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                    base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount,
                    category, quarter, year, file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                encryptor.encrypt(data["invoice_id"]),
                encryptor.encrypt(data["date"]),
                encryptor.encrypt(data["issuer_name"]),
                encryptor.encrypt(data["issuer_nif"]),
                encryptor.encrypt(data["receiver_name"]),
                encryptor.encrypt(data["receiver_nif"]),
                encryptor.encrypt(str(data["base_imponible"])),
                encryptor.encrypt(str(data["iva_rate"])),
                encryptor.encrypt(str(data["iva_amount"])),
                encryptor.encrypt(str(data["irpf_rate"])),
                encryptor.encrypt(str(data["irpf_amount"])),
                encryptor.encrypt(str(data["total_amount"])),
                data["category"],
                data["quarter"],
                data["year"],
                encryptor.encrypt(data["file_path"])
            ))
            
            # Registrar asiento contable PGC por partida doble
            LedgerService.record_invoice_asiento(data)
            
        conn.commit()
        print(f"✓ {len(invoices_data)} facturas insertadas y contabilizadas bajo partida doble PGC en la base de datos.")

        # --- SEMBRAR PROYECTOS MOCK ---
        cursor.execute("DELETE FROM projects")
        projects_data = [
            ("Desarrollo de App Contable", "ACME CORP S.L.", "B12345678", 5000.0, "en_progreso", "Desarrollo del backend y front-end de la aplicación de contabilidad."),
            ("Auditoría de Sistemas de Seguridad", "GLOBAL TECH SPAIN", "B87654321", 3000.0, "pendiente_facturar", "Auditoría completa e informes de penetración."),
            ("Consultoría Estratégica de IA", "BETA PARTNERS S.L.", "B11223344", 1500.0, "facturado", "Asesoramiento en la implantación de modelos LLM locales.")
        ]
        for name, client_name, client_nif, budget, status, desc in projects_data:
            cursor.execute("""
                INSERT INTO projects (name, client_name, client_nif, budget, status, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, client_name, client_nif, budget, status, desc))
        conn.commit()
        print("✓ Tabla 'projects' sembrada con 3 proyectos mock.")

        # --- SEMBRAR CLIENTES MOCK ---
        cursor.execute("DELETE FROM clients")
        clients_data = [
            ("ACME CORP S.L.", "B12345678", "finance@acme.com", "Avenida de la Industria 45, Madrid, España"),
            ("GLOBAL TECH SPAIN", "B87654321", "billing@globaltech.es", "Paseo de la Castellana 100, Madrid, España"),
            ("BETA PARTNERS S.L.", "B11223344", "admin@betapartners.com", "Calle Gran Vía 12, Madrid, España")
        ]
        for name, nif, email, address in clients_data:
            cursor.execute("""
                INSERT INTO clients (name, nif, email, address)
                VALUES (?, ?, ?, ?)
            """, (name, nif, email, address))
        conn.commit()
        print("✓ Tabla 'clients' sembrada con 3 clientes mock.")

if __name__ == "__main__":
    seed_database()

import pytest
import sys
from unittest.mock import patch, MagicMock
from app.utils.encryption import DatabaseEncryptor
from app.utils.anonymizer import DataAnonymizer
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.tax_parser_service import TaxParserService
from app.adapters.memory.memory import _get_connection

def test_encryption_fallback_explicitly():
    """Verifica que la ausencia de cryptography lanza un ImportError de forma controlada."""
    with patch.dict(sys.modules, {'cryptography': None, 'cryptography.fernet': None}):
        with pytest.raises(ImportError):
            DatabaseEncryptor()


def test_encryption_errors_and_invalid_inputs():
    """Verifica la robustez ante entradas inválidas u orígenes no cifrados en decripción."""
    encryptor = DatabaseEncryptor()
    
    # Entradas None
    assert encryptor.encrypt(None) is None
    assert encryptor.decrypt(None) is None
    
    # Decodificación de texto que no está en base64
    with pytest.raises(ValueError):
        encryptor.decrypt("fallback_no_base64_valido!")
    with pytest.raises(ValueError):
        encryptor.decrypt("texto_plano_normal")
    
    # Decodificación de base64 demasiado corto
    with pytest.raises(ValueError):
        encryptor.decrypt("fallback_aaaa")

def test_anonymizer_empty_and_edge_cases():
    """Prueba el anonimizador con valores vacíos o nulos."""
    anonymizer = DataAnonymizer()
    
    assert anonymizer.anonymize(None) == (None, {})
    assert anonymizer.anonymize("") == ("", {})
    assert anonymizer.detokenize(None, {}) is None
    assert anonymizer.detokenize("texto", {}) == "texto"
    assert anonymizer.detokenize("texto", None) == "texto"

def test_tax_parser_aggregation_decryption_exception():
    """
    Fuerza una excepción en la decripción durante la agregación trimestral de facturas
    para cubrir el bloque try/except y asegurar la robustez de TaxParserService.
    """
    with _get_connection() as conn:
        conn.execute("DELETE FROM invoices")
        # Inicializar esquema
        from app.adapters.memory.memory import _init_db_schema
        _init_db_schema(conn)
        
        # Insertar una factura con datos de importes corruptos (no desencriptables)
        conn.execute("""
            INSERT INTO invoices (
                invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount,
                category, quarter, year, file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "INV-CORRUPT", "2026-08-02", "Issuer", "NIF", "Receiver", "NIF",
            "texto_corrupto_no_cifrado", "rate", "iva", "irpf_rate", "irpf", "total",
            "income", 3, 2026, "file"
        ))
        conn.commit()
        
    # Llamar agregados trimestrales: debe capturar la excepción de descifrado/float y devolver 0.0 sin romper la ejecución
    aggregates = TaxParserService.get_quarterly_aggregates(year=2026)
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg["income"]["base"] == 0.0
    assert agg["income"]["total"] == 0.0

def test_verifactu_integrity_verification_empty(monkeypatch):
    """
    Verifica que la auditoría Verifactu sea válida si no hay facturas registradas
    usando una base de datos aislada en memoria sin destruir los triggers del esquema real.
    """
    import sqlite3
    
    mem_conn = sqlite3.connect(":memory:")
    mem_conn.row_factory = sqlite3.Row
    mem_conn.execute("""
        CREATE TABLE verifactu_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            date_of_issue TEXT,
            issuer_nif TEXT,
            receiver_nif TEXT,
            base_imponible REAL,
            iva_amount REAL,
            total_amount REAL,
            prev_hash TEXT,
            current_hash TEXT
        )
    """)
    mem_conn.execute("""
        CREATE TRIGGER trg_prevent_delete_verifactu
        BEFORE DELETE ON verifactu_invoices
        BEGIN
            SELECT RAISE(ABORT, 'Inalterabilidad fiscal Veri*Factu: no se permite eliminar registros');
        END;
    """)
    mem_conn.commit()

    class MockContext:
        def __enter__(self):
            return mem_conn
        def __exit__(self, *args):
            return False

    monkeypatch.setattr("app.domain.services.verifactu_service._get_connection", lambda: MockContext())

    audit = VerifactuService.verify_chain_integrity()
    mem_conn.close()

    assert audit["status"] == "valid"
    assert "0 facturas" in audit["message"]

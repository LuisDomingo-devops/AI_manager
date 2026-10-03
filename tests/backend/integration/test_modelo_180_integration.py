"""
Pruebas de integración sobre base de datos SQLite para el Modelo 180 y su conciliación con el Modelo 115.
"""

import sqlite3
import pytest
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.domain.models.billing import Model115ResultDTO
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService, AnnualTaxService


@pytest.fixture
def setup_fiscal_180_database():
    """Configura tablas en memoria o SQLite para facturas de alquiler y declaraciones del Modelo 115."""
    with _get_connection() as conn:
        inv_cols = [c[1] for c in conn.execute("PRAGMA table_info(invoices)").fetchall()]
        for cname, ctype in [
            ("inmueble_situacion", "INTEGER DEFAULT 1"),
            ("inmueble_ref_catastral", "TEXT"),
            ("inmueble_via", "TEXT DEFAULT 'CL'"),
            ("inmueble_nombre_via", "TEXT DEFAULT 'CALLE MAYOR'"),
            ("inmueble_numero", "TEXT DEFAULT '1'"),
            ("inmueble_municipio", "TEXT DEFAULT 'MADRID'"),
            ("inmueble_codigo_postal", "TEXT DEFAULT '28013'"),
            ("inmueble_provincia", "TEXT DEFAULT '28'")
        ]:
            if cname not in inv_cols:
                conn.execute(f"ALTER TABLE invoices ADD COLUMN {cname} {ctype}")

        # Limpiar datos previos del año 2026
        conn.execute("DELETE FROM invoices WHERE year = 2026 AND category IN ('alquiler', 'arrendamiento')")
        conn.execute("DELETE FROM tax_declarations_ledger WHERE fiscal_year = 2026 AND model_code IN ('115', '180')")

        # Insertar 4 facturas trimestrales de alquiler del mismo arrendador para el año 2026
        for q, month in enumerate([2, 5, 8, 11], start=1):
            inv_number = f"ALQ-2026-Q{q}"
            base = 2500.0
            irpf = 475.0  # 19% de 2500
            total = base - irpf + (base * 0.21)

            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, year, quarter, category,
                    issuer_nif, issuer_name, receiver_nif, receiver_name,
                    base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount,
                    total_amount, date, created_at,
                    inmueble_situacion, inmueble_ref_catastral,
                    inmueble_via, inmueble_nombre_via, inmueble_numero,
                    inmueble_municipio, inmueble_codigo_postal, inmueble_provincia
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inv_number, 2026, q, "alquiler",
                    encryptor.encrypt("B88888888"),
                    encryptor.encrypt("ARRENDAMIENTOS URBANOS SA"),
                    encryptor.encrypt("B87654321"),
                    encryptor.encrypt("EMPRESA DECLARANTE SL"),
                    encryptor.encrypt(str(base)),
                    encryptor.encrypt("21.0"),
                    encryptor.encrypt("525.0"),
                    encryptor.encrypt("19.0"),
                    encryptor.encrypt(str(irpf)),
                    str(total),
                    f"2026-0{month}-15",
                    "2026-01-01 00:00:00",
                    1,
                    "9872023VH5797S0001WX",
                    "CL",
                    "PASEO DE LA CASTELLANA",
                    "100",
                    "MADRID",
                    "28046",
                    "28"
                )
            )

        # Insertar las 4 autoliquidaciones trimestrales del Modelo 115 en tax_declarations_ledger
        for q in [1, 2, 3, 4]:
            conn.execute(
                """
                INSERT INTO tax_declarations_ledger (
                    tenant_id, model_code, fiscal_year, period,
                    declarant_nif, declarant_name, casillas_json,
                    boe_file_content, sha256_hash, filing_status,
                    filing_date, retention_until_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "default", "115", 2026, f"{q}T",
                    "B87654321", "EMPRESA DECLARANTE SL",
                    '{"01": 1, "02": 2500.0, "03": 475.0, "05": 475.0}',
                    "DUMMY_BOE_115", "dummyhash", "CALCULATED",
                    "2026-04-20 12:00:00", "2031-04-20 12:00:00", "2026-04-20 12:00:00"
                )
            )
        conn.commit()


def test_modelo_180_integration_database_aggregation_and_reconciliation(setup_fiscal_180_database):
    """Verifica la agregación desde BD real y conciliación exacta contra las autoliquidaciones del Modelo 115."""
    aggregator = AnnualTaxAggregatorService()
    
    # 1. Calcular Modelo 180 desde base de datos
    model_180 = aggregator.calculate_model_180(fiscal_year=2026, tenant_id="default")
    
    assert model_180.fiscal_year == 2026
    assert model_180.total_perceptores == 1
    assert model_180.total_base_retenciones == 10000.0  # 4 * 2500.0
    assert model_180.total_retenciones_practicadas == 1900.0  # 4 * 475.0
    
    perceptor = model_180.perceptores[0]
    assert perceptor.nif == "B88888888"
    assert perceptor.name == "ARRENDAMIENTOS URBANOS SA"
    assert perceptor.inmueble.situacion_inmueble == 1
    assert perceptor.inmueble.referencia_catastral == "9872023VH5797S0001WX"
    assert perceptor.inmueble.codigo_postal == "28046"

    # 2. Conciliación automática contra el Modelo 115
    reconciliation = aggregator.reconcile_with_model_115(
        fiscal_year=2026,
        model_180_result=model_180,
        tenant_id="default"
    )

    assert reconciliation.is_cuadrado is True
    assert reconciliation.diferencia_total == 0.0
    assert reconciliation.total_retenciones_180 == 1900.0
    assert reconciliation.total_retenciones_115_anual == 1900.0
    assert reconciliation.total_retenciones_115_1t == 475.0
    assert reconciliation.total_retenciones_115_2t == 475.0
    assert reconciliation.total_retenciones_115_3t == 475.0
    assert reconciliation.total_retenciones_115_4t == 475.0
    assert len(reconciliation.discrepancias_detectadas) == 0


def test_modelo_180_api_endpoints(setup_fiscal_180_database):
    """Valida los endpoints POST /models/180/calculate y POST /models/180/reconcile-115."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    headers = {"X-API-Key": "test_api_key_default"}

    # 1. Calcular Modelo 180 vía API
    calc_res = client.post(
        "/api/v1/tax/models/180/calculate",
        json={"fiscal_year": 2026, "tenant_id": "default"},
        headers=headers
    )
    assert calc_res.status_code == 200, calc_res.text
    calc_data = calc_res.json()
    assert calc_data["fiscal_year"] == 2026
    assert calc_data["total_perceptores"] == 1
    assert calc_data["total_base_retenciones"] == 10000.0
    assert calc_data["total_retenciones_practicadas"] == 1900.0

    # 2. Reconciliar con Modelo 115 vía API
    rec_res = client.post(
        "/api/v1/tax/models/180/reconcile-115",
        json={
            "fiscal_year": 2026,
            "tenant_id": "default",
            "model_180_data": calc_data
        },
        headers=headers
    )
    assert rec_res.status_code == 200, rec_res.text
    rec_data = rec_res.json()
    assert rec_data["is_cuadrado"] is True
    assert rec_data["diferencia_total"] == 0.0
    assert rec_data["total_retenciones_180"] == 1900.0
    assert rec_data["total_retenciones_115_anual"] == 1900.0


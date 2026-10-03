"""
Pruebas de integración sobre base de datos SQLite real para el Modelo 347.
Verifica la agregación anual de facturas de compras (Clave A) y ventas (Clave B),
el filtrado por umbral (> 3.005,06 €) y los cobros acumulados en metálico (> 6.000 €).
"""

import sqlite3
import pytest
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService


@pytest.fixture
def setup_fiscal_347_database():
    """Configura facturas de ventas y compras en la base de datos para el año 2026."""
    with _get_connection() as conn:
        inv_cols = [c[1] for c in conn.execute("PRAGMA table_info(invoices)").fetchall()]
        if "payment_method" not in inv_cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN payment_method TEXT DEFAULT 'transfer'")

        # Limpiar datos previos del año 2026
        conn.execute("DELETE FROM invoices WHERE year = 2026")
        conn.execute("DELETE FROM tax_declarations_ledger WHERE fiscal_year = 2026 AND model_code = '347'")

        # 1. Proveedor GRANDE (> 3.005,06 €): 4 facturas trimestrales de 1.500 € + 21% IVA = 1.815 € cada una (Total = 7.260 €) -> Clave A
        for q, month in enumerate([2, 5, 8, 11], start=1):
            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, year, quarter, category,
                    issuer_nif, issuer_name, receiver_nif, receiver_name,
                    base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount,
                    total_amount, date, created_at, payment_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"PROV-BIG-Q{q}", 2026, q, "gasto",
                    encryptor.encrypt("A11111111"),
                    encryptor.encrypt("PROVEEDOR PRINCIPAL SA"),
                    encryptor.encrypt("B87654321"),
                    encryptor.encrypt("INNOVACIONES SL"),
                    encryptor.encrypt("1500.00"),
                    encryptor.encrypt("21.0"),
                    encryptor.encrypt("315.00"),
                    encryptor.encrypt("0.0"),
                    encryptor.encrypt("0.0"),
                    "1815.00",
                    f"2026-0{month}-10",
                    "2026-01-01 00:00:00",
                    "transfer"
                )
            )

        # 2. Proveedor PEQUEÑO (<= 3.005,06 €): 2 facturas de 500 € + 21% IVA = 605 € (Total = 1.210 €) -> Debe ser descartado
        for q, month in enumerate([1, 3], start=1):
            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, year, quarter, category,
                    issuer_nif, issuer_name, receiver_nif, receiver_name,
                    base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount,
                    total_amount, date, created_at, payment_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"PROV-SMALL-Q{q}", 2026, q, "gasto",
                    encryptor.encrypt("B22222222"),
                    encryptor.encrypt("PROVEEDOR MENOR SL"),
                    encryptor.encrypt("B87654321"),
                    encryptor.encrypt("INNOVACIONES SL"),
                    encryptor.encrypt("500.00"),
                    encryptor.encrypt("21.0"),
                    encryptor.encrypt("105.00"),
                    encryptor.encrypt("0.0"),
                    encryptor.encrypt("0.0"),
                    "605.00",
                    f"2026-0{month}-15",
                    "2026-01-01 00:00:00",
                    "transfer"
                )
            )

        # 3. Cliente VIP (> 3.005,06 € con cobros en metálico > 6.000 €):
        # 1T: 5.000 € + 21% IVA = 6.050 € (metálico)
        # 2T: 3.000 € + 21% IVA = 3.630 € (metálico) -> Total metálico = 9.680 € (> 6.000 €)
        # Total anual = 9.680 € -> Clave B
        conn.execute(
            """
            INSERT INTO invoices (
                invoice_id, year, quarter, category,
                issuer_nif, issuer_name, receiver_nif, receiver_name,
                base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount,
                total_amount, date, created_at, payment_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CLI-VIP-01", 2026, 1, "ingreso",
                encryptor.encrypt("B87654321"),
                encryptor.encrypt("INNOVACIONES SL"),
                encryptor.encrypt("12345678Z"),
                encryptor.encrypt("CLIENTE VIP ANTONIO"),
                encryptor.encrypt("5000.00"),
                encryptor.encrypt("21.0"),
                encryptor.encrypt("1050.00"),
                encryptor.encrypt("0.0"),
                encryptor.encrypt("0.0"),
                "6050.00",
                "2026-02-20",
                "2026-01-01 00:00:00",
                "cash"
            )
        )
        conn.execute(
            """
            INSERT INTO invoices (
                invoice_id, year, quarter, category,
                issuer_nif, issuer_name, receiver_nif, receiver_name,
                base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount,
                total_amount, date, created_at, payment_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CLI-VIP-02", 2026, 2, "ingreso",
                encryptor.encrypt("B87654321"),
                encryptor.encrypt("INNOVACIONES SL"),
                encryptor.encrypt("12345678Z"),
                encryptor.encrypt("CLIENTE VIP ANTONIO"),
                encryptor.encrypt("3000.00"),
                encryptor.encrypt("21.0"),
                encryptor.encrypt("630.00"),
                encryptor.encrypt("0.0"),
                encryptor.encrypt("0.0"),
                "3630.00",
                "2026-05-18",
                "2026-01-01 00:00:00",
                "cash"
            )
        )
        conn.commit()


def test_modelo_347_integration_flow(setup_fiscal_347_database):
    """
    Verifica que calculate_model_347 extraiga los datos de la base de datos SQLite real,
    filtre los terceros <= 3.005,06 €, asigne claves A y B, y desglose los 4 trimestres.
    """
    model_347 = AnnualTaxAggregatorService.calculate_model_347(
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="INNOVACIONES SL"
    )

    assert model_347.fiscal_year == 2026
    assert model_347.declarant_nif == "B87654321"
    # Debe haber exactamente 2 declarados: PROVEEDOR PRINCIPAL (Clave A) y CLIENTE VIP (Clave B)
    # PROVEEDOR MENOR quedó excluido por tener 1.210 € <= 3.005,06 €
    assert model_347.total_declared_records == 2
    assert len(model_347.declared_records) == 2

    declared_by_nif = {d.nif: d for d in model_347.declared_records}

    # 1. Verificación Proveedor Clave A
    prov = declared_by_nif["A11111111"]
    assert prov.operation_key == "A"
    assert prov.total_annual_amount == 7260.00
    assert prov.quarter_1_amount == 1815.00
    assert prov.quarter_2_amount == 1815.00
    assert prov.quarter_3_amount == 1815.00
    assert prov.quarter_4_amount == 1815.00
    assert prov.cash_amount == 0.0

    # 2. Verificación Cliente Clave B
    cli = declared_by_nif["12345678Z"]
    assert cli.operation_key == "B"
    assert cli.total_annual_amount == 9680.00
    assert cli.quarter_1_amount == 6050.00
    assert cli.quarter_2_amount == 3630.00
    assert cli.quarter_3_amount == 0.00
    assert cli.quarter_4_amount == 0.00
    assert cli.cash_amount == 9680.00  # Cobros en metálico > 6.000 €

    # 3. Verificación de reconciliación
    reconciliation = AnnualTaxAggregatorService.audit_and_reconcile_model_347(
        fiscal_year=2026,
        model_347_result=model_347
    )
    assert reconciliation.is_mathematically_reconciled is True
    assert reconciliation.quarterly_difference == 0.0

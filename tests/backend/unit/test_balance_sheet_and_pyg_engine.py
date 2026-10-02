"""
Tests Unitarios para el Motor de Balance de Situación y Cuenta de Pérdidas y Ganancias (PyG).
Conforme a la estructura del Plan General de Contabilidad de PYMES (RD 1515/2007).
Valida agrupación reglamentaria en epígrafes, cuadre estricto Decimal('0.00') y márgenes escalonados.
"""

from decimal import Decimal
import pytest
from app.domain.services.balance_sheet_pymes_service import BalanceSheetPymesService
from app.domain.services.income_statement_service import IncomeStatementService
from app.domain.schemas import BalanceSheetDTO, IncomeStatementDTO
from app.infrastructure.database.legal_connection import legal_write_transaction


@pytest.fixture
def accounting_db_setup():
    """Configura un tenant de prueba con asientos contables en legal_journal_entries."""
    tenant_id = "test_tenant_statements"
    fiscal_year = 2026

    with legal_write_transaction(client_id=tenant_id) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM legal_journal_lines WHERE entry_id IN (SELECT id FROM legal_journal_entries WHERE tenant_id = ?)", (tenant_id,))
        cursor.execute("DELETE FROM legal_journal_entries WHERE tenant_id = ?", (tenant_id,))
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS legal_fiscal_years (
                tenant_id TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,
                is_closed INTEGER NOT NULL DEFAULT 0,
                closed_at TEXT,
                closed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, fiscal_year)
            )
        """)
        cursor.execute("DELETE FROM legal_fiscal_years WHERE tenant_id = ?", (tenant_id,))

        # 1. Asiento de Constitución / Capital: 57200000 (Debe: 3.000,00 €) / 10000000 (Haber: 3.000,00 €)
        e1_id = "entry-001"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e1_id, tenant_id, 1, "2026-01-01", fiscal_year, "Constitución de sociedad")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l1-1", e1_id, "57200000", "3000.00", "0.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l1-2", e1_id, "10000000", "0.00", "3000.00")
        )

        # 2. Asiento de Compra de Equipo Informático: 21700000 (Debe: 1.200,00 €), 47200021 (Debe: 252,00 €) / 40000000 (Haber: 1.452,00 €)
        e2_id = "entry-002"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e2_id, tenant_id, 2, "2026-01-15", fiscal_year, "Factura Equipo Informático")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l2-1", e2_id, "21700000", "1200.00", "0.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l2-2", e2_id, "47200021", "252.00", "0.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l2-3", e2_id, "40000000", "0.00", "1452.00")
        )

        # 3. Asiento de Venta de Servicios: 43000000 (Debe: 2.420,00 €) / 70500000 (Haber: 2.000,00 €), 47700021 (Haber: 420,00 €)
        e3_id = "entry-003"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e3_id, tenant_id, 3, "2026-02-10", fiscal_year, "Factura Venta Servicios")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l3-1", e3_id, "43000000", "2420.00", "0.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l3-2", e3_id, "70500000", "0.00", "2000.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l3-3", e3_id, "47700021", "0.00", "420.00")
        )

        # 4. Asiento de Gastos Generales: 62900000 (Debe: 500,00 €) / 57200000 (Haber: 500,00 €)
        e4_id = "entry-004"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e4_id, tenant_id, 4, "2026-03-01", fiscal_year, "Gastos diversos")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l4-1", e4_id, "62900000", "500.00", "0.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l4-2", e4_id, "57200000", "0.00", "500.00")
        )

        # 5. Asiento de Amortización Anual: 68100000 (Debe: 300,00 €) / 28100000 (Haber: 300,00 €)
        e5_id = "entry-005"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e5_id, tenant_id, 5, "2026-12-31", fiscal_year, "Amortización inmovilizado")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l5-1", e5_id, "68100000", "300.00", "0.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("l5-2", e5_id, "28100000", "0.00", "300.00")
        )

        cursor.close()

    return tenant_id, fiscal_year


def test_balance_sheet_quadration_and_pymes_grouping(accounting_db_setup):
    """Valida que el Balance de Situación clasifique correctamente las cuentas y cumpla Total Activo == Total Pasivo + PN."""
    tenant_id, fiscal_year = accounting_db_setup
    service = BalanceSheetPymesService()

    balance = service.calculate_balance_sheet(tenant_id, fiscal_year)

    assert isinstance(balance, BalanceSheetDTO)
    assert balance.is_balanced is True
    assert balance.total_activo == balance.total_pasivo_y_patrimonio_neto

    # Verificación estricta de la ecuación con Decimal('0.00')
    diff = abs(balance.total_activo - balance.total_pasivo_y_patrimonio_neto)
    assert diff == Decimal("0.00")

    # Verificar epígrafe Inmovilizado Material A.II (21700000 minorado por 28100000): 1.200 - 300 = 900,00 €
    anc_mat = next((line for line in balance.activo_no_corriente if line.epigrafe_codigo == "A.II"), None)
    assert anc_mat is not None
    assert anc_mat.saldo_ejercicio_actual == Decimal("900.00")

    # Verificar Deudores B.II (43000000 + 47200021): 2.420,00 + 252,00 = 2.672,00 €
    ac_deud = next((line for line in balance.activo_corriente if line.epigrafe_codigo == "B.II"), None)
    assert ac_deud is not None
    assert ac_deud.saldo_ejercicio_actual == Decimal("2672.00")

    # Verificar Tesorería B.V (57200000): 3.000,00 - 500,00 = 2.500,00 €
    ac_tes = next((line for line in balance.activo_corriente if line.epigrafe_codigo == "B.V"), None)
    assert ac_tes is not None
    assert ac_tes.saldo_ejercicio_actual == Decimal("2500.00")

    # Total Activo esperado = 900 + 2.672 + 2.500 = 6.072,00 €
    assert balance.total_activo == Decimal("6072.00")


def test_balance_sheet_unbalanced_forensic_detection():
    """Valida que si existe descuadre contable, is_balanced sea False y se reporte el detalle forense."""
    tenant_id = "tenant_unbalanced_forensic"
    fiscal_year = 2026

    with legal_write_transaction(client_id=tenant_id) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM legal_journal_lines WHERE entry_id IN (SELECT id FROM legal_journal_entries WHERE tenant_id = ?)", (tenant_id,))
        cursor.execute("DELETE FROM legal_journal_entries WHERE tenant_id = ?", (tenant_id,))

        # Asiento corrupto / forzado directamente en BD con descuadre de 100€
        e_id = "corrupt-entry"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e_id, tenant_id, 1, "2026-01-01", fiscal_year, "Asiento descuadrado")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("cl-1", e_id, "57200000", "1000.00", "0.00")
        )
        cursor.execute(
            "INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)",
            ("cl-2", e_id, "10000000", "0.00", "900.00")
        )
        cursor.close()

    service = BalanceSheetPymesService()
    balance = service.calculate_balance_sheet(tenant_id, fiscal_year)

    assert balance.is_balanced is False
    assert balance.descuadre_forense is not None
    assert "diferencia" in balance.descuadre_forense
    assert abs(balance.descuadre_forense["diferencia"]) == Decimal("100.00")


def test_income_statement_tiered_margins_and_tax_provision(accounting_db_setup):
    """Valida la Cuenta de Pérdidas y Ganancias escalonada: EBITDA, EBIT, BAI e Impuesto sobre Sociedades."""
    tenant_id, fiscal_year = accounting_db_setup
    service = IncomeStatementService()

    pyg = service.calculate_income_statement(tenant_id, fiscal_year, corporate_tax_rate=0.25)

    assert isinstance(pyg, IncomeStatementDTO)
    # Ingresos: 70500000 = 2.000,00 €
    assert pyg.cifra_negocios == Decimal("2000.00")
    # Gastos de explotación: 62900000 = 500,00 €
    assert pyg.otros_gastos_explotacion == Decimal("500.00")
    # Amortizaciones: 68100000 = 300,00 €
    assert pyg.amortizaciones_dotacion == Decimal("300.00")
    # EBITDA = 2.000 - 500 = 1.500,00 €
    assert pyg.ebitda == Decimal("1500.00")
    # Resultado Explotación (EBIT) = EBITDA - Amortizaciones = 1.500 - 300 = 1.200,00 €
    assert pyg.resultado_explotacion == Decimal("1200.00")
    # Resultado Financiero = 0.00 €
    assert pyg.resultado_financiero == Decimal("0.00")
    # BAI = 1.200,00 €
    assert pyg.resultado_antes_impuestos == Decimal("1200.00")
    # Gasto por Impuesto sobre Sociedades (25% sobre 1.200) = 300,00 €
    assert pyg.impuesto_sociedades == Decimal("300.00")
    # Resultado Neto = 1.200 - 300 = 900,00 €
    assert pyg.resultado_neto_ejercicio == Decimal("900.00")

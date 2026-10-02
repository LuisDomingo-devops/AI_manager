"""
Tests de Integración para el Motor de Amortizaciones y Cierre Contable Normalizado (PGC PYMES).
Valida:
1. Cálculo de cuotas de amortización anual y mensual con prorrata y límite de valor residual.
2. Contabilización idempotente en el Libro Diario legal (cuentas 681/281).
3. Simulación y ejecución atómica del cierre contable (asiento de regularización a cuenta 129,
   asiento de cierre de balance a cero, inmutabilidad en legal_fiscal_years y asiento de apertura N+1).
"""

from decimal import Decimal
import pytest
from app.infrastructure.database.legal_connection import legal_write_transaction, get_legal_readonly_connection
from app.domain.services.asset_depreciation_engine import AssetDepreciationEngine
from app.domain.services.fiscal_year_closing_service import FiscalYearClosingService
from app.infrastructure.database.asset_repository_db import SqliteAssetRepositoryAdapter


@pytest.fixture
def closing_and_depreciation_db_setup():
    """Configura el esquema y datos de prueba para amortizaciones y cierre contable."""
    tenant_id = "test_closing_tenant"
    fiscal_year = 2026

    # 1. Configurar tabla assets si no existe
    from app.adapters.memory.memory import _get_connection
    with _get_connection(tenant_id) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                purchase_date TEXT NOT NULL,
                cost REAL NOT NULL,
                useful_life_years INTEGER NOT NULL,
                depreciation_method TEXT NOT NULL DEFAULT 'lineal',
                salvage_value REAL DEFAULT 0.0,
                category TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("DELETE FROM assets WHERE client_id = ?", (tenant_id,))

        # Insertar 2 activos:
        # Activo 1: Ordenador 1200€, vida útil 4 años, comprado el 2026-07-01 (6 meses de prorrata en 2026), valor residual 100€
        # Base amortizable = 1100€. Cuota anual = 275€. Cuota 2026 (6 meses) = 137.50€
        cursor.execute(
            """
            INSERT INTO assets (client_id, name, purchase_date, cost, useful_life_years, salvage_value, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, "Servidor Serv-01", "2026-07-01", 1200.0, 4, 100.0, "MATERIAL")
        )
        # Activo 2: Maquinaria 10000€, vida útil 5 años, comprado el 2025-01-01 (año completo en 2026), valor residual 0€
        # Base amortizable = 10000€. Cuota anual = 2000€.
        cursor.execute(
            """
            INSERT INTO assets (client_id, name, purchase_date, cost, useful_life_years, salvage_value, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, "Fresadora CNC", "2025-01-01", 10000.0, 5, 0.0, "MATERIAL")
        )

    # 2. Configurar diario legal
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

        # Asiento 1: Capital social (572 Debe: 20000 / 100 Haber: 20000)
        e1 = "entry-close-001"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e1, tenant_id, 1, "2026-01-01", fiscal_year, "Apertura Capital")
        )
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-1", e1, "57200000", "20000.00", "0.00"))
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-2", e1, "10000000", "0.00", "20000.00"))

        # Asiento 2: Venta de servicios (430 Debe: 12100 / 705 Haber: 10000, 477 Haber: 2100)
        e2 = "entry-close-002"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e2, tenant_id, 2, "2026-03-10", fiscal_year, "Factura emitida 2026-01")
        )
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-3", e2, "43000000", "12100.00", "0.00"))
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-4", e2, "70500000", "0.00", "10000.00"))
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-5", e2, "47700000", "0.00", "2100.00"))

        # Asiento 3: Gasto de suministros (628 Debe: 2000, 472 Debe: 420 / 410 Haber: 2420)
        e3 = "entry-close-003"
        cursor.execute(
            "INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept) VALUES (?, ?, ?, ?, ?, ?)",
            (e3, tenant_id, 3, "2026-04-15", fiscal_year, "Factura Electricidad")
        )
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-6", e3, "62800000", "2000.00", "0.00"))
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-7", e3, "47200000", "420.00", "0.00"))
        cursor.execute("INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit) VALUES (?, ?, ?, ?, ?)", ("cl-8", e3, "41000000", "0.00", "2420.00"))

    return {"tenant_id": tenant_id, "fiscal_year": fiscal_year}


def test_asset_depreciation_calculation_and_recording(closing_and_depreciation_db_setup):
    """Verifica el cálculo de cuotas prorrateadas y su contabilización en el libro legal."""
    tenant_id = closing_and_depreciation_db_setup["tenant_id"]
    fiscal_year = closing_and_depreciation_db_setup["fiscal_year"]

    engine = AssetDepreciationEngine()
    proposals = engine.calculate_depreciation_proposal(client_id=tenant_id, year=fiscal_year)

    assert len(proposals) == 2

    # Verificar activo con prorrata (julio a diciembre = 6 meses)
    servidor_prop = next(p for p in proposals if "Servidor" in p.asset_name)
    assert servidor_prop.depreciation_quota == Decimal("137.50")
    assert servidor_prop.account_debit == "68100000"
    assert servidor_prop.account_credit == "28100000"

    # Verificar activo año completo (Fresadora: 10000 / 5 = 2000)
    cnc_prop = next(p for p in proposals if "Fresadora" in p.asset_name)
    assert cnc_prop.depreciation_quota == Decimal("2000.00")

    # Contabilizar amortizaciones en Libro Diario legal
    run_result = engine.record_depreciation_entries(client_id=tenant_id, year=fiscal_year)
    assert run_result.is_posted is True
    assert run_result.total_depreciation_amount == Decimal("2137.50")

    # Verificar idempotencia: una segunda ejecución no debe duplicar el asiento
    repeat_run = engine.record_depreciation_entries(client_id=tenant_id, year=fiscal_year)
    assert repeat_run.is_posted is False
    assert "ya estaban contabilizadas" in repeat_run.message


def test_fiscal_year_closing_simulation_and_execution(closing_and_depreciation_db_setup):
    """Verifica la simulación y posterior ejecución atómica del cierre fiscal contable."""
    tenant_id = closing_and_depreciation_db_setup["tenant_id"]
    fiscal_year = closing_and_depreciation_db_setup["fiscal_year"]

    closing_service = FiscalYearClosingService()

    # 1. Simular cierre
    simulation = closing_service.simulate_year_end_closing(
        tenant_id=tenant_id,
        fiscal_year=fiscal_year,
        corporate_tax_rate=0.25
    )

    # Beneficio antes de regularización: Ingresos 705 (10.000€) - Gastos 628 (2.000€) = 8.000€
    # Impuesto estimado IS (25% de 8.000€) = 2.000€
    # Resultado neto a cuenta 129 = 6.000€
    assert simulation.resultado_antes_impuestos == Decimal("8000.00")
    assert simulation.impuesto_sociedades_estimado == Decimal("2000.00")
    assert simulation.resultado_neto_ejercicio == Decimal("6000.00")

    # Verificar asientos simulados
    assert simulation.asiento_regularizacion is not None
    assert simulation.asiento_cierre is not None
    assert simulation.asiento_apertura_siguiente is not None

    # Verificar que el asiento de cierre cuadra exactamente
    debe_cierre = sum(l.debit for l in simulation.asiento_cierre.lines)
    haber_cierre = sum(l.credit for l in simulation.asiento_cierre.lines)
    assert debe_cierre == haber_cierre

    # 2. Ejecutar cierre formalmente
    exec_result = closing_service.execute_year_end_closing(
        tenant_id=tenant_id,
        fiscal_year=fiscal_year,
        corporate_tax_rate=0.25,
        closed_by="auditor_test"
    )

    assert exec_result.is_success is True
    assert exec_result.is_closed is True
    assert exec_result.entries_created >= 2

    # 3. Comprobar que legal_fiscal_years tiene is_closed = 1
    conn = get_legal_readonly_connection(client_id=tenant_id)
    cursor = conn.cursor()
    cursor.execute("SELECT is_closed, closed_by FROM legal_fiscal_years WHERE tenant_id = ? AND fiscal_year = ?", (tenant_id, fiscal_year))
    row = cursor.fetchone()
    cursor.close()

    assert row is not None
    assert row[0] == 1
    assert row[1] == "auditor_test"

    # 4. Verificar que tras el cierre, las cuentas patrimoniales del año cerrado tienen saldo neto CERO
    # (porque el asiento de cierre las ha saldado por completo)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT l.account_code, SUM(l.debit) - SUM(l.credit) as saldo
        FROM legal_journal_lines l
        JOIN legal_journal_entries e ON l.entry_id = e.id
        WHERE e.tenant_id = ? AND e.fiscal_year = ?
        GROUP BY l.account_code
        """,
        (tenant_id, fiscal_year)
    )
    saldos_post_cierre = cursor.fetchall()
    cursor.close()

    for acc, saldo in saldos_post_cierre:
        saldo_dec = Decimal(str(saldo)).quantize(Decimal("0.01"))
        assert saldo_dec == Decimal("0.00"), f"La cuenta {acc} no quedó saldada a cero tras el cierre: {saldo_dec}"

    # 5. Verificar que el asiento de apertura para fiscal_year + 1 existe a 01/01/2027
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, entry_date, concept FROM legal_journal_entries WHERE tenant_id = ? AND fiscal_year = ?",
        (tenant_id, fiscal_year + 1)
    )
    apertura = cursor.fetchone()
    cursor.close()
    assert apertura is not None
    assert apertura[1] == f"{fiscal_year + 1}-01-01"

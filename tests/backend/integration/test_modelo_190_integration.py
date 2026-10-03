"""
Pruebas de integración sobre base de datos SQLite para el Modelo 190 y su conciliación con el Modelo 111.
"""

import sqlite3
import pytest
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.domain.models.billing import Model111ResultDTO
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService, AnnualTaxService
from tests.backend.fixtures.fiscal_190_fixtures import create_mock_fiscal_190_dataset


@pytest.fixture
def setup_fiscal_190_database():
    """Configura tablas en memoria o SQLite temporal para empleados, nóminas y facturas."""
    dataset = create_mock_fiscal_190_dataset(year=2026)
    
    with _get_connection() as conn:
        # 1. Asegurar columnas en employees
        emp_cols = [c[1] for c in conn.execute("PRAGMA table_info(employees)").fetchall()]
        for cname, ctype in [
            ("birth_year", "INTEGER DEFAULT 1985"),
            ("family_situation", "INTEGER DEFAULT 3"),
            ("spouse_nif_encrypted", "TEXT"),
            ("num_descendants", "INTEGER DEFAULT 0"),
            ("disability_grade", "INTEGER DEFAULT 0")
        ]:
            if cname not in emp_cols:
                conn.execute(f"ALTER TABLE employees ADD COLUMN {cname} {ctype}")

        # 2. Asegurar columnas en payrolls
        pay_cols = [c[1] for c in conn.execute("PRAGMA table_info(payrolls)").fetchall()]
        for cname, ctype in [
            ("in_kind_valuation", "REAL DEFAULT 0.0"),
            ("in_kind_on_account", "REAL DEFAULT 0.0")
        ]:
            if cname not in pay_cols:
                conn.execute(f"ALTER TABLE payrolls ADD COLUMN {cname} {ctype}")

        # 3. Asegurar columnas en invoices
        inv_cols = [c[1] for c in conn.execute("PRAGMA table_info(invoices)").fetchall()]
        for cname, ctype in [
            ("retention_clave", "TEXT DEFAULT 'G'"),
            ("retention_subclave", "TEXT DEFAULT '01'")
        ]:
            if cname not in inv_cols:
                conn.execute(f"ALTER TABLE invoices ADD COLUMN {cname} {ctype}")

        # Limpiar datos previos
        conn.execute("DELETE FROM payrolls WHERE year = 2026")
        conn.execute("DELETE FROM invoices WHERE year = 2026")
        conn.execute("DELETE FROM employees WHERE id IN (101, 102)")

        # Insertar empleados cifrados
        for emp in dataset["employees"]:
            conn.execute(
                """
                INSERT INTO employees (
                    id, nif_encrypted, nss_encrypted, full_name_encrypted, birth_year,
                    family_situation, spouse_nif_encrypted, num_descendants, disability_grade,
                    gross_annual_salary, monthly_base_salary, start_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    emp["id"],
                    encryptor.encrypt(emp["nif"]),
                    encryptor.encrypt("281234567890"),
                    encryptor.encrypt(emp["name"]),
                    emp["birth_year"],
                    emp["family_situation"],
                    encryptor.encrypt(emp["spouse_nif"]) if emp["spouse_nif"] else None,
                    emp["num_descendants"],
                    emp["disability"],
                    30000.0,
                    2500.0,
                    "2026-01-01",
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:00:00"
                )
            )

        # Insertar nóminas
        for pay in dataset["payrolls"]:
            payroll_code = f"NOM-{pay['year']}-{str(pay['month']).zfill(2)}-{pay['employee_id']}"
            gross = pay["gross_total"]
            irpf = pay["irpf_amount"]
            net = gross - irpf
            conn.execute(
                """
                INSERT INTO payrolls (
                    payroll_code, employee_id, year, month, salary_base, extra_pay_prorata,
                    gross_total, bccc, bccp, ss_worker_total, ss_employer_total,
                    irpf_rate, irpf_amount, net_salary, in_kind_valuation, in_kind_on_account, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payroll_code,
                    pay["employee_id"], pay["year"], pay["month"],
                    gross, 0.0,
                    gross, gross, gross, gross * 0.0635, gross * 0.315,
                    15.0, irpf, net,
                    pay.get("in_kind_valuation", 0.0), pay.get("in_kind_on_account", 0.0),
                    "2026-01-01 00:00:00"
                )
            )

        # Insertar facturas profesionales
        for idx, inv in enumerate(dataset["invoices"]):
            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, date, year, quarter, category,
                    issuer_nif, issuer_name, receiver_nif, receiver_name,
                    base_imponible, iva_amount, iva_rate, irpf_amount, irpf_rate,
                    total_amount, status,
                    retention_clave, retention_subclave
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"INV-2026-{inv['quarter']}-{idx}",
                    f"2026-0{inv['quarter']}-15",
                    inv["year"],
                    inv["quarter"],
                    inv["category"],
                    encryptor.encrypt(inv["issuer_nif"]),
                    encryptor.encrypt(inv["issuer_name"]),
                    encryptor.encrypt("B88888888"),
                    encryptor.encrypt("Empresa Receptora SL"),
                    encryptor.encrypt(str(inv["base_imponible"])),
                    encryptor.encrypt("0.0"),
                    encryptor.encrypt("21.0"),
                    encryptor.encrypt(str(inv["irpf_amount"])),
                    encryptor.encrypt(str(inv["irpf_rate"])),
                    inv["base_imponible"] - inv["irpf_amount"],
                    "pagada",
                    inv.get("retention_clave", "G"),
                    inv.get("retention_subclave", "01")
                )
            )
        conn.commit()

    yield dataset

    with _get_connection() as conn:
        conn.execute("DELETE FROM payrolls WHERE year = 2026")
        conn.execute("DELETE FROM invoices WHERE year = 2026")
        conn.execute("DELETE FROM employees WHERE id IN (101, 102)")
        conn.commit()


def test_aggregation_and_reconciliation_integration(setup_fiscal_190_database):
    """Verifica la agregación real en base de datos y la conciliación contra los 4 trimestres del Modelo 111."""
    dataset = setup_fiscal_190_database
    service = AnnualTaxService()

    # 1. Ejecutar agregación del Modelo 190
    model_190 = service.calculate_model_190(fiscal_year=2026)
    
    assert model_190.fiscal_year == 2026
    assert model_190.total_perceptores == 4  # 2 trabajadores + 2 profesionales
    assert model_190.total_retenciones_practicadas == 7540.0  # 6660 (nóminas) + 880 (profesionales)
    assert model_190.total_percepciones_especie == 600.0  # 50 * 12 meses de Juan

    # Comprobar desglose de Juan (Clave A)
    juan = next(p for p in model_190.perceptores if p.nif == "12345678Z")
    assert juan.clave == "A"
    assert juan.percepciones_dinerarias == 30000.0
    assert juan.retenciones_practicadas == 4500.0
    assert juan.percepciones_especie_valoracion == 600.0
    assert juan.situacion_familiar == 2
    assert juan.num_hijos == 2

    # Comprobar profesionales (Clave G)
    prof_general = next(p for p in model_190.perceptores if p.nif == "34567890D")
    assert prof_general.clave == "G"
    assert prof_general.subclave == "01"
    assert prof_general.retenciones_practicadas == 600.0

    prof_reducido = next(p for p in model_190.perceptores if p.nif == "45678901E")
    assert prof_reducido.clave == "G"
    assert prof_reducido.subclave == "02"
    assert prof_reducido.retenciones_practicadas == 280.0

    # 2. Conciliación cuadrada exacta con 4 trimestres de Modelo 111
    # Total anual 111 = 7.540,00 €
    q1 = Model111ResultDTO(fiscal_year=2026, quarter=1, resultado_total=1885.0)
    q2 = Model111ResultDTO(fiscal_year=2026, quarter=2, resultado_total=1885.0)
    q3 = Model111ResultDTO(fiscal_year=2026, quarter=3, resultado_total=1885.0)
    q4 = Model111ResultDTO(fiscal_year=2026, quarter=4, resultado_total=1885.0)

    reconciliation = service.reconcile_with_model_111(
        fiscal_year=2026,
        model_190_result=model_190,
        quarterly_111_declarations=[q1, q2, q3, q4]
    )
    assert reconciliation.is_cuadrado is True
    assert reconciliation.diferencia_total == 0.0
    assert len(reconciliation.discrepancias_detectadas) == 0

    # 3. Conciliación con tolerancia de redondeo (diferencia de 0.03 €)
    q4_redondeo = Model111ResultDTO(fiscal_year=2026, quarter=4, resultado_total=1885.03)
    reconcil_redondeo = service.reconcile_with_model_111(
        fiscal_year=2026,
        model_190_result=model_190,
        quarterly_111_declarations=[q1, q2, q3, q4_redondeo]
    )
    assert reconcil_redondeo.is_cuadrado is True
    assert reconcil_redondeo.is_tolerancia_redondeo is True
    assert abs(reconcil_redondeo.diferencia_total - 0.03) < 0.001

    # 4. Conciliación con descuadre estructural (diferencia de 100.00 €)
    q4_error = Model111ResultDTO(fiscal_year=2026, quarter=4, resultado_total=1985.0)
    reconcil_error = service.reconcile_with_model_111(
        fiscal_year=2026,
        model_190_result=model_190,
        quarterly_111_declarations=[q1, q2, q3, q4_error]
    )
    assert reconcil_error.is_cuadrado is False
    assert reconcil_error.diferencia_total == 100.0
    assert len(reconcil_error.discrepancias_detectadas) > 0

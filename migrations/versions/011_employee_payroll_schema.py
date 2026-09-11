"""
011_employee_payroll_schema.py
==============================
Migra la definicion canonica de las tablas de RRHH al MigrationRunner.
Antes era responsabilidad de EmployeeService.init_schema() en el constructor.
"""
import sqlite3

VERSION = "011"
DESCRIPTION = "Esquema RRHH: employees, payrolls, settlements, tgss_afi_records"


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            nif_encrypted           TEXT NOT NULL,
            nss_encrypted           TEXT NOT NULL,
            full_name_encrypted     TEXT NOT NULL,
            email_encrypted         TEXT,
            iban_encrypted          TEXT,
            contract_type           TEXT NOT NULL DEFAULT '100',
            contribution_group      INTEGER NOT NULL DEFAULT 1,
            start_date              TEXT NOT NULL,
            end_date                TEXT,
            gross_annual_salary     REAL NOT NULL,
            monthly_base_salary     REAL NOT NULL,
            num_paychecks           INTEGER NOT NULL DEFAULT 12,
            irpf_rate               REAL NOT NULL DEFAULT 10.0,
            vacation_days_per_year  INTEGER NOT NULL DEFAULT 30,
            vacation_days_taken     REAL NOT NULL DEFAULT 0.0,
            status                  TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at              TEXT NOT NULL,
            updated_at              TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payrolls (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_code        TEXT UNIQUE NOT NULL,
            employee_id         INTEGER NOT NULL,
            month               INTEGER NOT NULL,
            year                INTEGER NOT NULL,
            salary_base         REAL NOT NULL,
            extra_pay_prorata   REAL NOT NULL DEFAULT 0.0,
            gross_total         REAL NOT NULL,
            bccc                REAL NOT NULL,
            bccp                REAL NOT NULL,
            ss_worker_total     REAL NOT NULL,
            ss_employer_total   REAL NOT NULL,
            irpf_rate           REAL NOT NULL,
            irpf_amount         REAL NOT NULL,
            net_salary          REAL NOT NULL,
            pdf_path            TEXT,
            journal_entry_id    INTEGER,
            created_at          TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settlements (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            settlement_code         TEXT UNIQUE NOT NULL,
            employee_id             INTEGER NOT NULL,
            termination_type        TEXT NOT NULL,
            termination_date        TEXT NOT NULL,
            worked_days_amount      REAL NOT NULL,
            extra_pays_pending      REAL NOT NULL,
            vacation_pending_days   REAL NOT NULL,
            vacation_pending_amount REAL NOT NULL,
            indemnity_days          REAL NOT NULL DEFAULT 0.0,
            indemnity_amount        REAL NOT NULL DEFAULT 0.0,
            total_settlement        REAL NOT NULL,
            pdf_path                TEXT,
            journal_entry_id        INTEGER,
            created_at              TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tgss_afi_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            action_code TEXT NOT NULL,
            real_date   TEXT NOT NULL,
            cause_code  TEXT,
            afi_payload TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'GENERATED',
            created_at  TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('64000000', 'Sueldos y Salarios', 'gasto')")
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('64100000', 'Indemnizaciones por despido', 'gasto')")
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('64200000', 'Seguridad Social a cargo de la empresa', 'gasto')")
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47600000', 'Organismos de la Seguridad Social acreedores', 'pasivo')")
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47511100', 'H.P. Acreedora por retenciones de trabajo (Modelo 111)', 'pasivo')")

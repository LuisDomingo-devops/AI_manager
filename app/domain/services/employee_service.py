"""
EMPLOYEE SERVICE — Gestión y custodia cifrada de empleados y contratos (AES-256).
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.utils.logger import app_logger
from app.domain.schemas import EmployeeCreateSchema


class EmployeeService:

    @classmethod
    def init_schema(cls) -> None:
        """Inicializa las tablas de empleados, nóminas, finiquitos y afiliación TGSS."""
        with _get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nif_encrypted TEXT NOT NULL,
                    nss_encrypted TEXT NOT NULL,
                    full_name_encrypted TEXT NOT NULL,
                    email_encrypted TEXT,
                    iban_encrypted TEXT,
                    contract_type TEXT NOT NULL DEFAULT '100',
                    contribution_group INTEGER NOT NULL DEFAULT 1,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    gross_annual_salary REAL NOT NULL,
                    monthly_base_salary REAL NOT NULL,
                    num_paychecks INTEGER NOT NULL DEFAULT 12,
                    irpf_rate REAL NOT NULL DEFAULT 10.0,
                    vacation_days_per_year INTEGER NOT NULL DEFAULT 30,
                    vacation_days_taken REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS payrolls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payroll_code TEXT UNIQUE NOT NULL,
                    employee_id INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    salary_base REAL NOT NULL,
                    extra_pay_prorata REAL NOT NULL DEFAULT 0.0,
                    gross_total REAL NOT NULL,
                    bccc REAL NOT NULL,
                    bccp REAL NOT NULL,
                    ss_worker_total REAL NOT NULL,
                    ss_employer_total REAL NOT NULL,
                    irpf_rate REAL NOT NULL,
                    irpf_amount REAL NOT NULL,
                    net_salary REAL NOT NULL,
                    pdf_path TEXT,
                    journal_entry_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS settlements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    settlement_code TEXT UNIQUE NOT NULL,
                    employee_id INTEGER NOT NULL,
                    termination_type TEXT NOT NULL,
                    termination_date TEXT NOT NULL,
                    worked_days_amount REAL NOT NULL,
                    extra_pays_pending REAL NOT NULL,
                    vacation_pending_days REAL NOT NULL,
                    vacation_pending_amount REAL NOT NULL,
                    indemnity_days REAL NOT NULL DEFAULT 0.0,
                    indemnity_amount REAL NOT NULL DEFAULT 0.0,
                    total_settlement REAL NOT NULL,
                    pdf_path TEXT,
                    journal_entry_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS tgss_afi_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    action_code TEXT NOT NULL,
                    real_date TEXT NOT NULL,
                    cause_code TEXT,
                    afi_payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'GENERATED',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                )
            """)

            # Asegurar cuentas laborales en el PGC
            conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('64000000', 'Sueldos y Salarios', 'gasto')")
            conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('64100000', 'Indemnizaciones por despido', 'gasto')")
            conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('64200000', 'Seguridad Social a cargo de la empresa', 'gasto')")
            conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47600000', 'Organismos de la Seguridad Social acreedores', 'pasivo')")
            conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47511100', 'H.P. Acreedora por retenciones de trabajo (Modelo 111)', 'pasivo')")

            conn.commit()

    @classmethod
    def create_employee(cls, data: Dict[str, Any]) -> int:
        """Valida, cifra e inserta un nuevo empleado en la base de datos."""
        cls.init_schema()
        schema = EmployeeCreateSchema(**data)
        
        monthly_salary = round(schema.gross_annual_salary / schema.num_paychecks, 2)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO employees (
                    nif_encrypted, nss_encrypted, full_name_encrypted, email_encrypted, iban_encrypted,
                    contract_type, contribution_group, start_date, gross_annual_salary, monthly_base_salary,
                    num_paychecks, irpf_rate, vacation_days_per_year, vacation_days_taken, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 'ACTIVE', ?, ?)
            """, (
                encryptor.encrypt(schema.nif),
                encryptor.encrypt(schema.nss),
                encryptor.encrypt(schema.full_name),
                encryptor.encrypt(schema.email or ""),
                encryptor.encrypt(schema.iban or ""),
                schema.contract_type,
                schema.contribution_group,
                schema.start_date,
                schema.gross_annual_salary,
                monthly_salary,
                schema.num_paychecks,
                schema.irpf_rate,
                schema.vacation_days_per_year,
                now_str,
                now_str
            ))
            emp_id = cursor.lastrowid
            conn.commit()
            app_logger.info(f"Empleado creado exitosamente con ID {emp_id}")
            return emp_id

    @classmethod
    def get_employee(cls, employee_id: int) -> Optional[Dict[str, Any]]:
        """Recupera y descifra los datos de un empleado por su ID."""
        cls.init_schema()
        with _get_connection() as conn:
            row = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
            if not row:
                return None
            return cls._row_to_dict(row)

    @classmethod
    def list_employees(cls, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todos los empleados descifrados (filtrado opcional por status)."""
        cls.init_schema()
        query = "SELECT * FROM employees"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status.upper())
        query += " ORDER BY id ASC"

        with _get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [cls._row_to_dict(r) for r in rows]

    @classmethod
    def update_employee_status(cls, employee_id: int, status: str, end_date: Optional[str] = None) -> bool:
        """Actualiza el estado de un empleado (ACTIVE, DISMISSED, RESIGNED)."""
        cls.init_schema()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _get_connection() as conn:
            conn.execute("""
                UPDATE employees
                SET status = ?, end_date = COALESCE(?, end_date), updated_at = ?
                WHERE id = ?
            """, (status.upper(), end_date, now_str, employee_id))
            conn.commit()
            return True

    @classmethod
    def _row_to_dict(cls, row) -> Dict[str, Any]:
        """Descifra los campos protegidos de una fila de la base de datos."""
        return {
            "id": row["id"],
            "nif": encryptor.decrypt(row["nif_encrypted"]),
            "nss": encryptor.decrypt(row["nss_encrypted"]),
            "full_name": encryptor.decrypt(row["full_name_encrypted"]),
            "email": encryptor.decrypt(row["email_encrypted"]) if row["email_encrypted"] else "",
            "iban": encryptor.decrypt(row["iban_encrypted"]) if row["iban_encrypted"] else "",
            "contract_type": row["contract_type"],
            "contribution_group": row["contribution_group"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "gross_annual_salary": row["gross_annual_salary"],
            "monthly_base_salary": row["monthly_base_salary"],
            "num_paychecks": row["num_paychecks"],
            "irpf_rate": row["irpf_rate"],
            "vacation_days_per_year": row["vacation_days_per_year"],
            "vacation_days_taken": row["vacation_days_taken"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

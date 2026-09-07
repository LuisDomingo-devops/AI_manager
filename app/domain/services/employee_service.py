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
        """
        DELEGADO A MIGRACIÓN 011.
        El DDL de employees, payrolls, settlements y tgss_afi_records está
        gestionado por migrations/versions/011_employee_payroll_schema.py,
        que se aplica automáticamente en el arranque vía MigrationRunner.
        Se mantienen únicamente los seeds de cuentas PGC necesarios para nóminas.
        """
        with _get_connection() as conn:
            # Seeds de cuentas PGC para nóminas (datos, no schema)
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

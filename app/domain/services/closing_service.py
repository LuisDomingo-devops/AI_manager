import datetime
from app.adapters.memory.memory import _get_connection
from app.utils.logger import tool_logger
from app.domain.services.ledger_service import LedgerService

class ClosingService:
    @staticmethod
    def close_fiscal_year(year: int) -> dict:
        """
        Realiza el cierre del ejercicio fiscal:
        1. Verifica que no esté cerrado ya.
        2. Calcula los totales de ingresos y gastos de las cuentas 6 y 7.
        3. Genera un asiento de regularización hacia la cuenta 12900000.
        4. Bloquea el año en la base de datos (fiscal_year_status).
        """
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # 1. Verificar estado
            cursor.execute("SELECT is_closed FROM fiscal_year_status WHERE year = ?", (year,))
            row = cursor.fetchone()
            if row and row["is_closed"]:
                return {"status": "error", "message": f"El ejercicio fiscal {year} ya se encuentra cerrado."}
                
            # 2. Calcular saldos de cuentas de gastos (6*) e ingresos (7*)
            # En SQLite de la app, ledger_entries tiene cuenta, debe, haber.
            # Sumamos todo para ese año.
            cursor.execute("""
                SELECT l.account_code, SUM(CAST(l.debe AS REAL)) as total_debe, SUM(CAST(l.haber AS REAL)) as total_haber
                FROM ledger_entries l
                JOIN journal_entries j ON l.journal_entry_id = j.id
                WHERE j.entry_date LIKE ? AND (l.account_code LIKE '6%' OR l.account_code LIKE '7%')
                GROUP BY l.account_code
            """, (f"{year}-%",))
            
            saldos = cursor.fetchall()
            
            if not saldos:
                return {"status": "error", "message": f"No hay movimientos de ingresos/gastos para el año {year}."}
                
            # 3. Generar asiento de regularización
            # Para cerrar: las de gastos (saldo deudor) se abonan con cargo a la 129, y las de ingresos (saldo acreedor) se cargan con abono a la 129.
            entries = []
            resultado = 0.0 # Positivo = Beneficio, Negativo = Pérdida
            
            for s in saldos:
                cuenta = s["account_code"]
                saldo = float(s["total_debe"]) - float(s["total_haber"])
                
                if saldo > 0:
                    # Cuenta deudora (Ej. Gastos). Se abona para dejarla a cero.
                    entries.append({"account": cuenta, "debe": 0, "haber": saldo})
                    resultado -= saldo
                elif saldo < 0:
                    # Cuenta acreedora (Ej. Ingresos). Se carga para dejarla a cero.
                    entries.append({"account": cuenta, "debe": abs(saldo), "haber": 0})
                    resultado += abs(saldo)
                    
            if resultado > 0:
                entries.append({"account": "12900000", "debe": 0, "haber": resultado})
            elif resultado < 0:
                entries.append({"account": "12900000", "debe": abs(resultado), "haber": 0})
                
            # Asiento con fecha 31 de Diciembre del año a cerrar
            closing_date = f"{year}-12-31 23:59:59"
            
            # Forzar la creación usando LedgerService
            ledger_entry = {
                "date": closing_date,
                "concept": f"Asiento de regularización cierre {year}",
                "entries": entries
            }
            
            # Nota: LedgerService podría bloquear si el año está cerrado, así que el asiento se debe hacer antes del bloqueo
            try:
                LedgerService.record_journal_entry(ledger_entry)
            except Exception as e:
                tool_logger.warning(f"Error al generar asiento de regularización: {e}")
                return {"status": "error", "message": f"Fallo al registrar asiento de cierre: {e}"}
                
            # 4. Bloquear el año
            now = datetime.datetime.now().isoformat()
            if row:
                cursor.execute("UPDATE fiscal_year_status SET is_closed = 1, closed_at = ? WHERE year = ?", (now, year))
            else:
                cursor.execute("INSERT INTO fiscal_year_status (year, is_closed, closed_at) VALUES (?, 1, ?)", (year, now))
                
            conn.commit()
            
            return {
                "status": "ok",
                "message": f"Ejercicio fiscal {year} cerrado exitosamente. Resultado: {resultado:.2f} EUR.",
                "resultado": round(resultado, 2)
            }
            
        except Exception as e:
            conn.rollback()
            tool_logger.exception(f"Error en cierre de ejercicio {year}")
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

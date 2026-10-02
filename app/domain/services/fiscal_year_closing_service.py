"""
Servicio Orquestador de Cierre Contable y Regularización del Ejercicio (PGC PYMES / Código de Comercio).
Ejecuta la regularización de cuentas de gestión (Grupos 6 y 7 contra la cuenta 129),
el asiento de cierre de balance a cero, la inmutabilidad legal en legal_fiscal_years
y la generación automática del asiento de apertura del ejercicio siguiente.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import uuid
from typing import Dict, List, Any, Optional

from app.domain.schemas import (
    YearEndClosingSimulationDTO,
    CloseFiscalYearExecutionResultDTO,
    SimulatedJournalEntryDTO,
    SimulatedJournalLineDTO,
)
from app.infrastructure.database.legal_connection import (
    legal_write_transaction,
    get_legal_readonly_connection,
)


class FiscalYearClosingService:
    """Gestiona el ciclo de cierre contable y regularización del ejercicio fiscal."""

    def is_fiscal_year_closed(self, tenant_id: str, fiscal_year: int) -> bool:
        """Comprueba si el ejercicio contable está cerrado en legal_fiscal_years."""
        try:
            conn = get_legal_readonly_connection(client_id=tenant_id)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT is_closed FROM legal_fiscal_years
                WHERE tenant_id = ? AND fiscal_year = ?
                """,
                (tenant_id, fiscal_year)
            )
            row = cursor.fetchone()
            cursor.close()
            return bool(row[0]) if row else False
        except Exception:
            return False

    def simulate_year_end_closing(
        self,
        tenant_id: str,
        fiscal_year: int,
        corporate_tax_rate: float = 0.25
    ) -> YearEndClosingSimulationDTO:
        """
        Simula los asientos de regularización, cierre y apertura sin persistir cambios en BD.
        Calcula el resultado neto, la cuota estimada de IS (si procede) y el saldado patrimonial.
        """
        if self.is_fiscal_year_closed(tenant_id, fiscal_year):
            raise ValueError(f"El ejercicio fiscal {fiscal_year} ya se encuentra cerrado. No se puede simular el cierre.")

        conn = get_legal_readonly_connection(client_id=tenant_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT l.account_code, l.debit, l.credit
            FROM legal_journal_lines l
            JOIN legal_journal_entries e ON l.entry_id = e.id
            WHERE e.tenant_id = ? AND e.fiscal_year = ?
            """,
            (tenant_id, fiscal_year)
        )
        rows = cursor.fetchall()
        cursor.close()

        # Acumular saldos deudores y acreedores por cuenta
        saldos: Dict[str, Dict[str, Decimal]] = {}
        for code, deb_raw, cred_raw in rows:
            deb = Decimal(str(deb_raw or "0.00")).quantize(Decimal("0.01"))
            cred = Decimal(str(cred_raw or "0.00")).quantize(Decimal("0.01"))
            if code not in saldos:
                saldos[code] = {"debe": Decimal("0.00"), "haber": Decimal("0.00")}
            saldos[code]["debe"] += deb
            saldos[code]["haber"] += cred

        total_ingresos = Decimal("0.00")
        total_gastos = Decimal("0.00")
        tiene_gasto_630 = False

        for code, s in saldos.items():
            if code.startswith("7"):
                saldo_acreedor = s["haber"] - s["debe"]
                total_ingresos += saldo_acreedor
            elif code.startswith("6"):
                saldo_deudor = s["debe"] - s["haber"]
                total_gastos += saldo_deudor
                if code.startswith("630"):
                    tiene_gasto_630 = True

        resultado_antes_is = (total_ingresos - total_gastos).quantize(Decimal("0.01"))

        # Cálculo de cuota de IS estimada
        tasa_dec = Decimal(str(corporate_tax_rate)).quantize(Decimal("0.0001"))
        if not tiene_gasto_630 and resultado_antes_is > Decimal("0.00"):
            cuota_is_estimada = (resultado_antes_is * tasa_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            cuota_is_estimada = Decimal("0.00")

        resultado_neto = (resultado_antes_is - cuota_is_estimada).quantize(Decimal("0.01"))

        # 1. Asiento de Regularización (Grupos 6 y 7 a cuenta 12900000)
        lineas_reg: List[SimulatedJournalLineDTO] = []
        # Saldar cuentas del Grupo 7 (al Debe)
        for code in sorted(saldos.keys()):
            if code.startswith("7"):
                saldo_7 = saldos[code]["haber"] - saldos[code]["debe"]
                if saldo_7 > Decimal("0.00"):
                    lineas_reg.append(SimulatedJournalLineDTO(account_code=code, debit=saldo_7, credit=Decimal("0.00"), concept="Regularización Grupo 7"))
                elif saldo_7 < Decimal("0.00"):
                    lineas_reg.append(SimulatedJournalLineDTO(account_code=code, debit=Decimal("0.00"), credit=abs(saldo_7), concept="Regularización Grupo 7"))

        # Saldar cuentas del Grupo 6 (al Haber)
        for code in sorted(saldos.keys()):
            if code.startswith("6"):
                saldo_6 = saldos[code]["debe"] - saldos[code]["haber"]
                if saldo_6 > Decimal("0.00"):
                    lineas_reg.append(SimulatedJournalLineDTO(account_code=code, debit=Decimal("0.00"), credit=saldo_6, concept="Regularización Grupo 6"))
                elif saldo_6 < Decimal("0.00"):
                    lineas_reg.append(SimulatedJournalLineDTO(account_code=code, debit=abs(saldo_6), credit=Decimal("0.00"), concept="Regularización Grupo 6"))

        if cuota_is_estimada > Decimal("0.00"):
            lineas_reg.append(SimulatedJournalLineDTO(account_code="63000000", debit=Decimal("0.00"), credit=cuota_is_estimada, concept="Impuesto Sociedades Estimado"))

        # Resultado neto a la cuenta 12900000
        if resultado_neto > Decimal("0.00"):
            # Beneficio -> Saldo acreedor en la 129 (va al Haber de la regularización)
            lineas_reg.append(SimulatedJournalLineDTO(account_code="12900000", debit=Decimal("0.00"), credit=resultado_neto, concept="Resultado del Ejercicio (Beneficio)"))
        elif resultado_neto < Decimal("0.00"):
            # Pérdida -> Saldo deudor en la 129 (va al Debe de la regularización)
            lineas_reg.append(SimulatedJournalLineDTO(account_code="12900000", debit=abs(resultado_neto), credit=Decimal("0.00"), concept="Resultado del Ejercicio (Pérdidas)"))

        asiento_reg = SimulatedJournalEntryDTO(
            entry_date=f"{fiscal_year}-12-31",
            concept=f"Regularización de Ingresos y Gastos - Ejercicio {fiscal_year}",
            lines=lineas_reg
        )

        # 2. Asiento de Cierre (Saldado a cero de cuentas de balance Grupos 1 al 5 + 12900000)
        # Calculamos los saldos de balance incorporando el resultado y el pasivo fiscal de IS
        lineas_cierre: List[SimulatedJournalLineDTO] = []
        for code in sorted(saldos.keys()):
            if code.startswith(("1", "2", "3", "4", "5")):
                saldo_neto = saldos[code]["debe"] - saldos[code]["haber"]
                if saldo_neto > Decimal("0.00"):
                    # Tenía saldo deudor -> se cancela al Haber
                    lineas_cierre.append(SimulatedJournalLineDTO(account_code=code, debit=Decimal("0.00"), credit=saldo_neto, concept="Cierre de cuenta de balance"))
                elif saldo_neto < Decimal("0.00"):
                    # Tenía saldo acreedor -> se cancela al Debe
                    lineas_cierre.append(SimulatedJournalLineDTO(account_code=code, debit=abs(saldo_neto), credit=Decimal("0.00"), concept="Cierre de cuenta de balance"))

        # Incorporar pasivo fiscal por IS si no estaba contabilizado
        if cuota_is_estimada > Decimal("0.00"):
            lineas_cierre.append(SimulatedJournalLineDTO(account_code="47520000", debit=cuota_is_estimada, credit=Decimal("0.00"), concept="Cierre Pasivo H.P. Acreedora por IS"))

        # Incorporar saldo de la 12900000 al asiento de cierre
        if resultado_neto > Decimal("0.00"):
            # Tenía saldo acreedor -> se cancela al Debe
            lineas_cierre.append(SimulatedJournalLineDTO(account_code="12900000", debit=resultado_neto, credit=Decimal("0.00"), concept="Cierre Cuenta 129 (Beneficio)"))
        elif resultado_neto < Decimal("0.00"):
            # Tenía saldo deudor -> se cancela al Haber
            lineas_cierre.append(SimulatedJournalLineDTO(account_code="12900000", debit=Decimal("0.00"), credit=abs(resultado_neto), concept="Cierre Cuenta 129 (Pérdidas)"))

        asiento_cierre = SimulatedJournalEntryDTO(
            entry_date=f"{fiscal_year}-12-31",
            concept=f"Asiento de Cierre - Ejercicio {fiscal_year}",
            lines=lineas_cierre
        )

        # 3. Asiento de Apertura para el ejercicio siguiente (Inversión exacta del asiento de cierre)
        lineas_apertura: List[SimulatedJournalLineDTO] = []
        for l in lineas_cierre:
            lineas_apertura.append(
                SimulatedJournalLineDTO(
                    account_code=l.account_code,
                    debit=l.credit,
                    credit=l.debit,
                    concept=f"Apertura ejercicio {fiscal_year + 1}"
                )
            )

        asiento_apertura = SimulatedJournalEntryDTO(
            entry_date=f"{fiscal_year + 1}-01-01",
            concept=f"Asiento de Apertura - Ejercicio {fiscal_year + 1}",
            lines=lineas_apertura
        )

        return YearEndClosingSimulationDTO(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            resultado_antes_impuestos=resultado_antes_is,
            tipo_is_aplicado=tasa_dec,
            cuota_is_estimada=cuota_is_estimada,
            resultado_neto=resultado_neto,
            apuntes_regularizacion_cuentas_6_y_7=[l.model_dump() for l in lineas_reg],
            apuntes_cierre_cuentas_balance=[l.model_dump() for l in lineas_cierre],
            apuntes_apertura_ejercicio_siguiente=[l.model_dump() for l in lineas_apertura],
            asiento_regularizacion=asiento_reg,
            asiento_cierre=asiento_cierre,
            asiento_apertura_siguiente=asiento_apertura
        )

    def execute_year_end_closing(
        self,
        tenant_id: str,
        fiscal_year: int,
        corporate_tax_rate: float = 0.25,
        closed_by: str = "system"
    ) -> CloseFiscalYearExecutionResultDTO:
        """
        Ejecuta de manera atómica e irrevocable el cierre contable del ejercicio:
        1. Asiento de Impuesto de Sociedades (si procede y no existía).
        2. Asiento de Regularización (cuentas 6 y 7 a cuenta 12900000).
        3. Asiento de Cierre (todas las cuentas patrimoniales a cero).
        4. Bloqueo en legal_fiscal_years (is_closed = 1).
        5. Asiento de Apertura del ejercicio fiscal_year + 1.
        """
        simulation = self.simulate_year_end_closing(tenant_id, fiscal_year, corporate_tax_rate)

        next_year = fiscal_year + 1
        reg_id = f"entry-reg-{fiscal_year}-{uuid.uuid4().hex[:8]}"
        cierre_id = f"entry-cierre-{fiscal_year}-{uuid.uuid4().hex[:8]}"
        apertura_id = f"entry-apertura-{next_year}-{uuid.uuid4().hex[:8]}"

        with legal_write_transaction(client_id=tenant_id) as write_conn:
            w_cursor = write_conn.cursor()

            # Asegurar tabla legal_fiscal_years
            w_cursor.execute("""
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

            # Obtener número de asiento correlativo para el año cerrado
            w_cursor.execute(
                "SELECT COALESCE(MAX(entry_number), 0) FROM legal_journal_entries WHERE tenant_id = ? AND fiscal_year = ?",
                (tenant_id, fiscal_year)
            )
            last_entry_num = w_cursor.fetchone()[0]

            # 0. Asiento previo de Provisión del Impuesto sobre Sociedades si procede
            if simulation.cuota_is_estimada > Decimal("0.00"):
                is_entry_num = last_entry_num + 1
                is_id = f"entry-is-{fiscal_year}-{uuid.uuid4().hex[:8]}"
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (is_id, tenant_id, is_entry_num, f"{fiscal_year}-12-31", fiscal_year, f"Gasto Impuesto sobre Sociedades Estimado (Cuenta 630) - Ejercicio {fiscal_year}")
                )
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{is_id}-l1", is_id, "63000000", str(simulation.cuota_is_estimada), "0.00")
                )
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{is_id}-l2", is_id, "47520000", "0.00", str(simulation.cuota_is_estimada))
                )
                last_entry_num = is_entry_num

            # 1. Asiento de Regularización
            reg_entry_num = last_entry_num + 1
            w_cursor.execute(
                """
                INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (reg_id, tenant_id, reg_entry_num, f"{fiscal_year}-12-31", fiscal_year, f"Regularización de Ingresos y Gastos - Ejercicio {fiscal_year}")
            )

            idx = 1
            for l in simulation.asiento_regularizacion.lines:
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{reg_id}-l{idx}", reg_id, l.account_code, str(l.debit), str(l.credit))
                )
                idx += 1

            # 2. Asiento de Cierre
            cierre_entry_num = reg_entry_num + 1
            w_cursor.execute(
                """
                INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cierre_id, tenant_id, cierre_entry_num, f"{fiscal_year}-12-31", fiscal_year, f"Cierre de Ejercicio Contable {fiscal_year}")
            )

            idx = 1
            for l in simulation.asiento_cierre.lines:
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{cierre_id}-l{idx}", cierre_id, l.account_code, str(l.debit), str(l.credit))
                )
                idx += 1

            # 3. Marcar ejercicio como cerrado e inmutable
            now_iso = datetime.now().isoformat()
            w_cursor.execute(
                """
                INSERT OR REPLACE INTO legal_fiscal_years (tenant_id, fiscal_year, is_closed, closed_at, closed_by)
                VALUES (?, ?, 1, ?, ?)
                """,
                (tenant_id, fiscal_year, now_iso, closed_by)
            )

            # 4. Asiento de Apertura para el año siguiente (next_year)
            w_cursor.execute(
                "SELECT COALESCE(MAX(entry_number), 0) + 1 FROM legal_journal_entries WHERE tenant_id = ? AND fiscal_year = ?",
                (tenant_id, next_year)
            )
            apertura_entry_num = w_cursor.fetchone()[0]

            w_cursor.execute(
                """
                INSERT INTO legal_journal_entries (id, tenant_id, entry_number, entry_date, fiscal_year, concept)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (apertura_id, tenant_id, apertura_entry_num, f"{next_year}-01-01", next_year, f"Asiento de Apertura - Ejercicio {next_year}")
            )

            idx = 1
            for l in simulation.asiento_apertura_siguiente.lines:
                w_cursor.execute(
                    """
                    INSERT INTO legal_journal_lines (id, entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"{apertura_id}-l{idx}", apertura_id, l.account_code, str(l.debit), str(l.credit))
                )
                idx += 1

        return CloseFiscalYearExecutionResultDTO(
            status="ok",
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            next_fiscal_year=next_year,
            resultado_ejercicio=simulation.resultado_neto,
            asiento_regularizacion_id=reg_id,
            asiento_cierre_id=cierre_id,
            asiento_apertura_id=apertura_id,
            closed_at=datetime.now(),
            is_locked=True,
            message=f"Ejercicio contable {fiscal_year} cerrado con éxito. Asiento de apertura generado para {next_year}.",
            is_success=True,
            is_closed=True,
            entries_created=3
        )

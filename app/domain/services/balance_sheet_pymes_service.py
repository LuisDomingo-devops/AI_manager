"""
Servicio clasificador y generador del Balance de Situación normalizado para PYMES (RD 1515/2007).
Garantiza el cuadre exacto en Decimal (Total Activo == Total Pasivo + Patrimonio Neto al céntimo)
y genera informe forense en caso de descuadre contable.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional
from datetime import date

from app.domain.schemas import BalanceSheetDTO, FinancialStatementLineDTO
from app.domain.services.pymes_taxonomic_catalog import PymesTaxonomicCatalog
from app.infrastructure.database.legal_connection import get_legal_readonly_connection


class BalanceSheetPymesService:
    """Motor de cálculo y clasificación del Balance de Situación según el PGC PYMES."""

    def calculate_balance_sheet(
        self,
        tenant_id: str,
        fiscal_year: int,
        closing_date: Optional[str] = None
    ) -> BalanceSheetDTO:
        """
        Calcula el Balance de Situación para el ejercicio y tenant indicados.
        Clasifica todas las cuentas del Libro Mayor en sus epígrafes oficiales.
        """
        fecha_cierre_str = closing_date or f"{fiscal_year}-12-31"

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

        # Acumular saldos por cuenta en Decimal
        cuentas_saldos: Dict[str, Dict[str, Decimal]] = {}
        total_ingresos_g7 = Decimal("0.00")
        total_gastos_g6 = Decimal("0.00")

        for code, debit_raw, credit_raw in rows:
            debit = Decimal(str(debit_raw if debit_raw is not None else "0.00")).quantize(Decimal("0.01"))
            credit = Decimal(str(credit_raw if credit_raw is not None else "0.00")).quantize(Decimal("0.01"))

            if code not in cuentas_saldos:
                cuentas_saldos[code] = {"debe": Decimal("0.00"), "haber": Decimal("0.00")}

            cuentas_saldos[code]["debe"] += debit
            cuentas_saldos[code]["haber"] += credit

            # Registrar ingresos y gastos para el resultado provisional si la 129 no está saldada
            if code.startswith("7"):
                total_ingresos_g7 += (credit - debit)
            elif code.startswith("6"):
                total_gastos_g6 += (debit - credit)

        resultado_ejercicio_provisional = (total_ingresos_g7 - total_gastos_g6).quantize(Decimal("0.01"))

        # Preparar estructuras de epígrafes
        epigrafes_acum: Dict[str, Dict[str, Any]] = {}
        for key, meta in PymesTaxonomicCatalog.BALANCE_EPIGRAFES.items():
            epigrafes_acum[key] = {
                "codigo": meta["codigo"],
                "nombre": meta["nombre"],
                "tipo_masa": meta["tipo_masa"],
                "cuentas": [],
                "saldo": Decimal("0.00")
            }

        cuentas_no_asignadas: Dict[str, Decimal] = {}

        for code, saldos in cuentas_saldos.items():
            debe = saldos["debe"]
            haber = saldos["haber"]

            # Si es cuenta del Grupo 6 o 7, su resultado se integra en Fondos Propios (129)
            if code.startswith("6") or code.startswith("7"):
                continue

            # Buscar epígrafe correspondiente
            asignado = False
            for key, meta in PymesTaxonomicCatalog.BALANCE_EPIGRAFES.items():
                # Comprobar si es cuenta positiva directa
                if any(code.startswith(pref) for pref in meta["prefijos_positivos"]):
                    # Naturaleza del saldo según tipo de masa
                    if meta["tipo_masa"] in ("ACTIVO_NO_CORRIENTE", "ACTIVO_CORRIENTE"):
                        saldo_cuenta = debe - haber
                    else:
                        saldo_cuenta = haber - debe

                    epigrafes_acum[key]["cuentas"].append(code)
                    epigrafes_acum[key]["saldo"] += saldo_cuenta
                    asignado = True
                    break

                # Comprobar si es cuenta compensatoria (resta en su masa)
                elif any(code.startswith(pref) for pref in meta["prefijos_compensatorios"]):
                    if meta["tipo_masa"] in ("ACTIVO_NO_CORRIENTE", "ACTIVO_CORRIENTE"):
                        # Cuenta de amortización o deterioro de activo: saldo acreedor resta al activo
                        saldo_compensatorio = haber - debe
                        epigrafes_acum[key]["cuentas"].append(code)
                        epigrafes_acum[key]["saldo"] -= saldo_compensatorio
                    else:
                        # Acciones propias o dividendo a cuenta: resta en patrimonio neto
                        saldo_compensatorio = debe - haber
                        epigrafes_acum[key]["cuentas"].append(code)
                        epigrafes_acum[key]["saldo"] -= saldo_compensatorio

                    asignado = True
                    break

            if not asignado:
                cuentas_no_asignadas[code] = (debe - haber).quantize(Decimal("0.01"))

        # Si no existe saldo explícito en la cuenta 12900000, reflejar el resultado provisional de PyG
        cuenta_129_presente = any(c.startswith("129") for c in cuentas_saldos.keys())
        if not cuenta_129_presente and resultado_ejercicio_provisional != Decimal("0.00"):
            epigrafes_acum["PN_RESULTADO_EJERCICIO"]["cuentas"].append("12900000 (PyG provisional)")
            epigrafes_acum["PN_RESULTADO_EJERCICIO"]["saldo"] += resultado_ejercicio_provisional

        # Clasificar en listas de FinancialStatementLineDTO
        activo_no_corriente: List[FinancialStatementLineDTO] = []
        activo_corriente: List[FinancialStatementLineDTO] = []
        patrimonio_neto: List[FinancialStatementLineDTO] = []
        pasivo_no_corriente: List[FinancialStatementLineDTO] = []
        pasivo_corriente: List[FinancialStatementLineDTO] = []

        total_anc = Decimal("0.00")
        total_ac = Decimal("0.00")
        total_pn = Decimal("0.00")
        total_pnc = Decimal("0.00")
        total_pc = Decimal("0.00")

        for key, data in epigrafes_acum.items():
            saldo = data["saldo"].quantize(Decimal("0.01"))
            # Incluir epígrafe si tiene movimientos o cuentas asociadas
            if saldo != Decimal("0.00") or data["cuentas"]:
                line_dto = FinancialStatementLineDTO(
                    epigrafe_codigo=data["codigo"],
                    epigrafe_nombre=data["nombre"],
                    cuentas_asociadas=sorted(list(set(data["cuentas"]))),
                    saldo_ejercicio_actual=saldo,
                    saldo_ejercicio_anterior=Decimal("0.00")
                )
                tipo = data["tipo_masa"]
                if tipo == "ACTIVO_NO_CORRIENTE":
                    activo_no_corriente.append(line_dto)
                    total_anc += saldo
                elif tipo == "ACTIVO_CORRIENTE":
                    activo_corriente.append(line_dto)
                    total_ac += saldo
                elif tipo == "PATRIMONIO_NETO":
                    patrimonio_neto.append(line_dto)
                    total_pn += saldo
                elif tipo == "PASIVO_NO_CORRIENTE":
                    pasivo_no_corriente.append(line_dto)
                    total_pnc += saldo
                elif tipo == "PASIVO_CORRIENTE":
                    pasivo_corriente.append(line_dto)
                    total_pc += saldo

        total_activo = (total_anc + total_ac).quantize(Decimal("0.01"))
        total_pasivo_pn = (total_pn + total_pnc + total_pc).quantize(Decimal("0.01"))

        diferencia = (total_activo - total_pasivo_pn).quantize(Decimal("0.01"))
        is_balanced = (diferencia == Decimal("0.00"))

        descuadre_forense: Optional[Dict[str, Decimal]] = None
        if not is_balanced:
            descuadre_forense = {
                "diferencia": diferencia,
                "total_activo": total_activo,
                "total_pasivo_y_patrimonio_neto": total_pasivo_pn,
            }
            if cuentas_no_asignadas:
                for k, v in cuentas_no_asignadas.items():
                    descuadre_forense[f"cuenta_no_asignada_{k}"] = v

        return BalanceSheetDTO(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            fecha_cierre=fecha_cierre_str,
            activo_no_corriente=activo_no_corriente,
            activo_corriente=activo_corriente,
            total_activo=total_activo,
            patrimonio_neto=patrimonio_neto,
            pasivo_no_corriente=pasivo_no_corriente,
            pasivo_corriente=pasivo_corriente,
            total_pasivo_y_patrimonio_neto=total_pasivo_pn,
            is_balanced=is_balanced,
            descuadre_forense=descuadre_forense
        )

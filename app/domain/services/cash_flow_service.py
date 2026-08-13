import re
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

class CashFlowService:

    @classmethod
    def get_current_balance(cls) -> float:
        """Obtiene el saldo bancario actual."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(amount) FROM bank_movements")
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
        finally:
            conn.close()

    @classmethod
    def get_pending_inflows(cls) -> List[Dict[str, Any]]:
        """Obtiene los cobros previstos basados en facturas de venta emitidas pendientes."""
        conn = _get_connection()
        inflows = []
        try:
            cursor = conn.cursor()
            # Leer todas las facturas de tipo ingreso que no estén cobradas
            cursor.execute("SELECT invoice_id, date, receiver_name, total_amount, status, category FROM invoices")
            rows = cursor.fetchall()
            for r in rows:
                status = r["status"]
                category = r["category"]
                if category in ("income", "ingreso") and status != "cobrada":
                    try:
                        inv_id = encryptor.decrypt(r["invoice_id"])
                        date_str = encryptor.decrypt(r["date"])
                        client_name = encryptor.decrypt(r["receiver_name"])
                        total = float(encryptor.decrypt(r["total_amount"]))
                        
                        # Vencimiento estimado a 30 días del registro de la factura
                        issue_dt = datetime.strptime(date_str, "%Y-%m-%d")
                        due_dt = issue_dt + timedelta(days=30)
                        
                        inflows.append({
                            "type": "invoice",
                            "id": inv_id,
                            "client_name": client_name,
                            "amount": total,
                            "due_date": due_dt.strftime("%Y-%m-%d"),
                            "description": f"Cobro Factura {inv_id} — {client_name}"
                        })
                    except Exception:
                        pass
            return inflows
        finally:
            conn.close()

    @classmethod
    def detect_recurring_expenses(cls) -> List[Dict[str, Any]]:
        """
        Analiza movimientos bancarios pasados de gastos (amount < 0)
        e identifica conceptos recurrentes mensuales proyectándolos a futuro.
        """
        conn = _get_connection()
        expenses = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT movement_date, concept, amount FROM bank_movements WHERE amount < 0")
            rows = cursor.fetchall()
            
            # Agrupar por concepto
            by_concept = {}
            for r in rows:
                concept = r["concept"]
                date_str = r["movement_date"]
                amt = float(r["amount"])
                
                # Normalizar concepto para agrupar (ej. "Autónomos Julio" o "Autónomos Jun" -> "autónomos")
                norm_concept = re.sub(
                    r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|jan|apr|aug|dec)\b',
                    '',
                    concept,
                    flags=re.IGNORECASE
                )
                norm_concept = re.sub(r'\d+', '', norm_concept).strip().lower()
                if not norm_concept:
                    norm_concept = concept.lower()

                if norm_concept not in by_concept:
                    by_concept[norm_concept] = []
                by_concept[norm_concept].append({"date": date_str, "amount": amt, "original_concept": concept})

            # Identificar recurrentes (aparecen al menos 2 veces con intervalo de ~30 días o mensual)
            for norm, items in by_concept.items():
                if len(items) >= 2:
                    # Ordenar por fecha
                    items.sort(key=lambda x: x["date"])
                    
                    # Calcular importes promedio
                    avg_amt = sum(x["amount"] for x in items) / len(items)
                    
                    # Tomar la última fecha
                    last_date_str = items[-1]["date"]
                    last_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
                    
                    expenses.append({
                        "concept": items[-1]["original_concept"],
                        "normalized_concept": norm,
                        "amount": abs(avg_amt),  # Guardar como valor positivo para el flujo
                        "last_date": last_date_str,
                        "next_date": (last_dt + timedelta(days=30)).strftime("%Y-%m-%d")
                    })
            return expenses
        finally:
            conn.close()

    @classmethod
    def estimate_quarterly_taxes(cls, year: int, quarter: int) -> float:
        """
        Estima el volumen de impuestos (Modelo 303 de IVA + Modelo 130 de IRPF)
        acumulados para el trimestre fiscal indicado.
        """
        conn = _get_connection()
        income_iva = 0.0
        income_base = 0.0
        expense_iva = 0.0
        expense_base = 0.0
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT total_amount, base_imponible, iva_amount, category FROM invoices WHERE year = ? AND quarter = ?", (year, quarter))
            rows = cursor.fetchall()
            for r in rows:
                try:
                    cat = r["category"]
                    base = float(encryptor.decrypt(r["base_imponible"]))
                    iva = float(encryptor.decrypt(r["iva_amount"]))
                    if cat in ("income", "ingreso"):
                        income_base += base
                        income_iva += iva
                    else:
                        expense_base += base
                        expense_iva += iva
                except Exception:
                    pass

            vat_estimate = max(0.0, income_iva - expense_iva)
            irpf_estimate = max(0.0, (income_base - expense_base) * 0.20)
            return round(vat_estimate + irpf_estimate, 2)
        finally:
            conn.close()

    @classmethod
    def get_forecast(cls, days_horizon: int = 90, safe_threshold: float = 1000.0) -> Dict[str, Any]:
        """
        Genera la previsión diaria de tesorería y alertas de liquidez.
        """
        start_date = datetime.now()
        current_balance = cls.get_current_balance()
        
        inflows = cls.get_pending_inflows()
        recurring_expenses = cls.detect_recurring_expenses()
        
        # Estructurar eventos a futuro
        future_events = []
        
        # 1. Añadir cobros previstos
        for inf in inflows:
            due_dt = datetime.strptime(inf["due_date"], "%Y-%m-%d")
            if start_date <= due_dt <= start_date + timedelta(days=days_horizon):
                future_events.append({
                    "date": inf["due_date"],
                    "type": "inflow",
                    "amount": inf["amount"],
                    "description": inf["description"]
                })

        # 2. Proyectar gastos recurrentes
        for exp in recurring_expenses:
            next_dt = datetime.strptime(exp["next_date"], "%Y-%m-%d")
            # Seguir proyectando sumando 30 días mientras esté en el horizonte
            while next_dt <= start_date + timedelta(days=days_horizon):
                if next_dt >= start_date:
                    future_events.append({
                        "date": next_dt.strftime("%Y-%m-%d"),
                        "type": "outflow",
                        "amount": exp["amount"],
                        "description": f"Gasto Recurrente: {exp['concept']}"
                    })
                next_dt += timedelta(days=30)

        # 3. Estimar y añadir impuestos de fin de trimestre si aplica
        # Identificar trimestres que se cruzan en el horizonte
        # Los pagos de impuestos ocurren del 1 al 20 de Ene (Q4), Abr (Q1), Jul (Q2), Oct (Q3)
        for d in range(1, days_horizon + 1):
            target_dt = start_date + timedelta(days=d)
            # Si el día es el 20 y es mes de liquidación
            if target_dt.day == 20 and target_dt.month in (1, 4, 7, 10):
                # Determinar qué trimestre se liquida
                if target_dt.month == 1:
                    tax_q, tax_yr = 4, target_dt.year - 1
                elif target_dt.month == 4:
                    tax_q, tax_yr = 1, target_dt.year
                elif target_dt.month == 7:
                    tax_q, tax_yr = 2, target_dt.year
                else:
                    tax_q, tax_yr = 3, target_dt.year
                
                tax_amount = cls.estimate_quarterly_taxes(tax_yr, tax_q)
                if tax_amount > 0.0:
                    future_events.append({
                        "date": target_dt.strftime("%Y-%m-%d"),
                        "type": "tax_outflow",
                        "amount": tax_amount,
                        "description": f"Liquidación de Impuestos Estimada Q{tax_q} {tax_yr}"
                    })

        # Ordenar eventos por fecha
        future_events.sort(key=lambda x: x["date"])

        # Simular trayectoria diaria
        daily_balances = {}
        running_balance = current_balance
        
        # Mapear eventos por fecha
        events_by_date = {}
        for ev in future_events:
            dt_str = ev["date"]
            if dt_str not in events_by_date:
                events_by_date[dt_str] = []
            events_by_date[dt_str].append(ev)

        alerts = []
        for d in range(days_horizon + 1):
            curr_dt = start_date + timedelta(days=d)
            curr_str = curr_dt.strftime("%Y-%m-%d")
            
            # Aplicar eventos del día
            if curr_str in events_by_date:
                for ev in events_by_date[curr_str]:
                    if ev["type"] == "inflow":
                        running_balance += ev["amount"]
                    else:
                        running_balance -= ev["amount"]

            running_balance = round(running_balance, 2)
            daily_balances[curr_str] = running_balance
            
            # Generar alerta de liquidez si cae por debajo del umbral seguro
            if running_balance < safe_threshold:
                # Comprobar si ya alertamos para evitar redundancia
                if not alerts or alerts[-1]["type"] != "threshold_breach":
                    alerts.append({
                        "type": "threshold_breach",
                        "date": curr_str,
                        "balance": running_balance,
                        "threshold": safe_threshold,
                        "message": f"¡Alerta de Liquidez! El saldo previsto caerá a {running_balance:.2f} € el {curr_dt.strftime('%d/%m/%Y')} (por debajo del umbral de {safe_threshold:.2f} €)."
                    })

        # Calcular puntos clave
        forecast_7d = daily_balances.get((start_date + timedelta(days=7)).strftime("%Y-%m-%d"), current_balance)
        forecast_30d = daily_balances.get((start_date + timedelta(days=30)).strftime("%Y-%m-%d"), current_balance)
        forecast_90d = daily_balances.get((start_date + timedelta(days=90)).strftime("%Y-%m-%d"), current_balance)

        return {
            "status": "ok",
            "horizon_days": days_horizon,
            "current_balance": current_balance,
            "forecast_7d": forecast_7d,
            "forecast_30d": forecast_30d,
            "forecast_90d": forecast_90d,
            "safe_threshold": safe_threshold,
            "events_projected": future_events,
            "alerts": alerts
        }

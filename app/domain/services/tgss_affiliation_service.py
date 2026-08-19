"""
TGSS AFFILIATION SERVICE — Generador de Ficheros de Afiliación (AFI) para Sistema RED / SILTRA.
Comunica Altas (MA), Bajas (MB) y Modificaciones de contratos ante la Seguridad Social.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from app.adapters.memory.memory import _get_connection
from app.config import settings

AFI_DIR = Path(__file__).resolve().parents[3] / "data" / "tgss_ficheros_afi"
AFI_DIR.mkdir(parents=True, exist_ok=True)


class TgssAffiliationService:

    # Códigos oficiales de causa de baja de la TGSS
    CAUSE_CODES = {
        "OBJECTIVE_DISMISSAL": "51",       # Despido por causas objetivas / procedente
        "VOLUNTARY_RESIGNATION": "53",     # Baja voluntaria del trabajador (dimisión)
        "DISCIPLINARY_DISMISSAL": "54",    # Despido disciplinario procedente
        "END_OF_CONTRACT": "93",           # Fin de contrato temporal
    }

    @classmethod
    def generate_alta_afi(cls, employee: Dict[str, Any], ccc: str = "28123456789") -> Dict[str, Any]:
        """
        Genera la acción MA (Alta de Trabajador) para el Sistema RED / SILTRA.
        """
        date_str = employee["start_date"].replace("-", "") # YYYYMMDD
        nss_clean = employee["nss"].replace(" ", "").replace("/", "").replace("-", "")
        nif_clean = employee["nif"].strip().upper()
        contract_type = str(employee.get("contract_type", "100"))
        group = str(employee.get("contribution_group", 1)).zfill(2)

        # Estructura del registro AFI de Alta (Acción MA)
        record = {
            "action": "MA",
            "action_desc": "Alta de Trabajador",
            "regimen": "0111", # Régimen General
            "ccc": ccc,
            "naf": nss_clean,
            "nif": nif_clean,
            "employee_name": employee["full_name"],
            "real_date": employee["start_date"],
            "contract_type": contract_type,
            "contribution_group": group,
            "coefficient": "1000", # 100% jornada completa
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Formato de texto estándar estructurado para transmisión SILTRA
        afi_text_line = f"EMP*0111*{ccc}*TRA*{nss_clean}*{nif_clean}*MA*{date_str}*CON*{contract_type}*GRP*{group}*1000"
        
        filename = f"AFI_ALTA_{employee['id']}_{date_str}.afi"
        file_path = AFI_DIR / filename
        file_path.write_text(afi_text_line, encoding="utf-8")

        # Persistir en base de datos
        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO tgss_afi_records (employee_id, action_code, real_date, cause_code, afi_payload, status, created_at)
                VALUES (?, 'MA', ?, NULL, ?, 'GENERATED', ?)
            """, (employee["id"], employee["start_date"], json.dumps(record), record["created_at"]))
            conn.commit()

        return {
            "status": "ok",
            "action": "MA",
            "file_path": str(file_path),
            "record": record,
            "afi_raw": afi_text_line
        }

    @classmethod
    def generate_baja_afi(
        cls,
        employee: Dict[str, Any],
        termination_type: str,
        termination_date: str,
        vacation_days_pending: float = 0.0,
        ccc: str = "28123456789"
    ) -> Dict[str, Any]:
        """
        Genera la acción MB (Baja de Trabajador) para el Sistema RED / SILTRA.
        Incluye la clave legal de baja y la liquidación L13 de días de vacaciones retribuidas y no disfrutadas.
        """
        cause_code = cls.CAUSE_CODES.get(termination_type.upper(), "51")
        date_str = termination_date.replace("-", "")[:8]
        nss_clean = employee["nss"].replace(" ", "").replace("/", "").replace("-", "")
        nif_clean = employee["nif"].strip().upper()
        vacation_days_int = int(round(vacation_days_pending))

        record = {
            "action": "MB",
            "action_desc": "Baja de Trabajador",
            "regimen": "0111",
            "ccc": ccc,
            "naf": nss_clean,
            "nif": nif_clean,
            "employee_name": employee["full_name"],
            "real_date": termination_date,
            "cause_code": cause_code,
            "termination_type": termination_type,
            "vacation_days_l13": vacation_days_int,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        afi_text_line = f"EMP*0111*{ccc}*TRA*{nss_clean}*{nif_clean}*MB*{date_str}*CAU*{cause_code}*L13*{vacation_days_int}"

        filename = f"AFI_BAJA_{employee['id']}_{date_str}.afi"
        file_path = AFI_DIR / filename
        file_path.write_text(afi_text_line, encoding="utf-8")

        # Persistir en base de datos
        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO tgss_afi_records (employee_id, action_code, real_date, cause_code, afi_payload, status, created_at)
                VALUES (?, 'MB', ?, ?, ?, 'GENERATED', ?)
            """, (employee["id"], termination_date, cause_code, json.dumps(record), record["created_at"]))
            conn.commit()

        return {
            "status": "ok",
            "action": "MB",
            "cause_code": cause_code,
            "file_path": str(file_path),
            "record": record,
            "afi_raw": afi_text_line
        }

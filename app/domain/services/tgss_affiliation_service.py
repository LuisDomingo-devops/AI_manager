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
    def _clean_nss(cls, raw_val: Any) -> str:
        clean = str(raw_val).replace(" ", "").replace("/", "").replace("-", "").replace(".", "").strip()
        if len(clean) != 12 or not clean.isdigit():
            raise ValueError(f"El NAF/NSS debe contener exactamente 12 dígitos numéricos: '{raw_val}'")
        return clean

    @classmethod
    def _clean_ccc(cls, raw_val: str) -> str:
        clean = str(raw_val).replace(" ", "").replace("/", "").replace("-", "").strip()
        if len(clean) != 11 or not clean.isdigit():
            raise ValueError(f"El Código de Cuenta de Cotización (CCC) debe tener 11 dígitos numéricos: '{raw_val}'")
        return clean

    @classmethod
    def generate_alta_afi(cls, employee: Dict[str, Any], ccc: str = "28123456789") -> Dict[str, Any]:
        """
        Genera la acción MA (Alta de Trabajador) para el Sistema RED / SILTRA conforme al formato técnico oficial.
        """
        ccc_clean = cls._clean_ccc(ccc)
        date_str = employee["start_date"].replace("-", "")[:8] # YYYYMMDD
        raw_nss = employee.get("naf") or employee.get("nss")
        if not raw_nss:
            raise ValueError("Falta el identificador de afiliación (NAF o NSS) del trabajador.")
        nss_clean = cls._clean_nss(raw_nss)
        nif_clean = employee["nif"].strip().upper()
        contract_type = str(employee.get("contract_code", employee.get("contract_type", "100")))
        group = str(employee.get("contribution_group", 1)).zfill(2)

        # Estructura del registro AFI de Alta (Acción MA)
        record = {
            "action": "MA",
            "action_desc": "Alta de Trabajador",
            "regimen": "0111", # Régimen General
            "ccc": ccc_clean,
            "naf": nss_clean,
            "nif": nif_clean,
            "employee_name": employee["full_name"],
            "real_date": employee["start_date"],
            "contract_type": contract_type,
            "contribution_group": group,
            "coefficient": "1000", # 100% jornada completa
            "regulatory_status": "UNVERIFIED",
            "warning": "Fichero AFI generado conforme a especificaciones técnicas pero no transmitido telemáticamente. Requiere homologación formal SILTRA con certificado digital ante la TGSS.",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Formato de texto estructurado estándar Sistema RED para transmisión SILTRA
        afi_text_line = f"EMP*0111*{ccc_clean}*TRA*{nss_clean}*{nif_clean}*MA*{date_str}*CON*{contract_type}*GRP*{group}*1000"
        
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
            "regulatory_status": "UNVERIFIED",
            "warning": record["warning"],
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
        ccc_clean = cls._clean_ccc(ccc)
        cause_code = cls.CAUSE_CODES.get(termination_type.upper(), "51")
        date_str = termination_date.replace("-", "")[:8]
        raw_nss = employee.get("naf") or employee.get("nss")
        if not raw_nss:
            raise ValueError("Falta el identificador de afiliación (NAF o NSS) del trabajador.")
        nss_clean = cls._clean_nss(raw_nss)
        nif_clean = employee["nif"].strip().upper()
        vacation_days_int = int(round(vacation_days_pending))

        record = {
            "action": "MB",
            "action_desc": "Baja de Trabajador",
            "regimen": "0111",
            "ccc": ccc_clean,
            "naf": nss_clean,
            "nif": nif_clean,
            "employee_name": employee["full_name"],
            "real_date": termination_date,
            "cause_code": cause_code,
            "termination_type": termination_type,
            "vacation_days_l13": vacation_days_int,
            "regulatory_status": "UNVERIFIED",
            "warning": "Fichero AFI generado conforme a especificaciones técnicas pero no transmitido telemáticamente. Requiere homologación formal SILTRA con certificado digital ante la TGSS.",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        afi_text_line = f"EMP*0111*{ccc_clean}*TRA*{nss_clean}*{nif_clean}*MB*{date_str}*CAU*{cause_code}*L13*{vacation_days_int}"

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
            "regulatory_status": "UNVERIFIED",
            "warning": record["warning"],
            "action": "MB",
            "cause_code": cause_code,
            "file_path": str(file_path),
            "record": record,
            "afi_raw": afi_text_line
        }

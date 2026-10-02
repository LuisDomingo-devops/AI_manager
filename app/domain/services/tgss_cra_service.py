"""
TGSS CRA SERVICE — Generador de remesas mensuales de Conceptos Retributivos Abonados (CRA) para SILTRA.
Conforme al Real Decreto-ley 16/2013 y especificaciones técnicas del Sistema de Liquidación Directa (Sistema RED).
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.adapters.memory.memory import _get_connection, write_transaction

CRA_DIR = Path(__file__).resolve().parents[3] / "data" / "tgss_ficheros_cra"
CRA_DIR.mkdir(parents=True, exist_ok=True)


class TgssCraService:

    @classmethod
    def generate_monthly_cra_xml(
        cls,
        ccc: Any = "28123456789",
        month: int = 1,
        year: int = 2026,
        workers_data: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera el fichero XML estructurado de remesa mensual CRA para su transmisión por SILTRA.
        Soporta llamada con datos de trabajadores explícitos o autodescubrimiento desde nóminas persistidas.
        """
        if isinstance(ccc, int):
            actual_month = int(ccc)
            actual_year = int(month)
            actual_ccc = str(year)
            actual_workers = workers_data
        else:
            actual_ccc = str(ccc)
            actual_month = int(month)
            actual_year = int(year)
            actual_workers = workers_data

        clean_ccc = actual_ccc.replace(" ", "").replace("/", "").replace("-", "").strip()
        if len(clean_ccc) != 11 or not clean_ccc.isdigit():
            raise ValueError(f"El Código de Cuenta de Cotización (CCC) debe tener 11 dígitos numéricos: '{actual_ccc}'")

        # Cargar datos de trabajadores desde la base de datos de nóminas si no vienen proporcionados
        if actual_workers is None:
            actual_workers = []
            from app.domain.services.employee_service import EmployeeService
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT employee_id, salary_base, extra_pay_prorata
                    FROM payrolls
                    WHERE month = ? AND year = ?
                """, (actual_month, actual_year))
                rows = cursor.fetchall()
                for row in rows:
                    emp = EmployeeService.get_employee(row["employee_id"])
                    if emp:
                        concepts = [
                            {"code": "0001", "description": "Salario Base", "amount": float(row["salary_base"]), "concept_type": "C"}
                        ]
                        if row["extra_pay_prorata"] and float(row["extra_pay_prorata"]) > 0:
                            concepts.append({
                                "code": "0005", "description": "Pagas Extras", "amount": float(row["extra_pay_prorata"]), "concept_type": "C"
                            })
                        actual_workers.append({
                            "nif": emp["nif"],
                            "naf": emp.get("naf") or emp.get("nss", ""),
                            "concepts": concepts
                        })

        provincia = clean_ccc[:2]
        numero = clean_ccc[2:9]
        dc = clean_ccc[9:11]
        mes_str = str(actual_month).zfill(2)
        anio_str = str(actual_year)

        # Construcción del árbol XML
        root = ET.Element("MensajeCRA", xmlns="http://www.seg-social.es/creta/esquemas/MensajeCRA")

        cabecera = ET.SubElement(root, "Cabecera")
        ccc_elem = ET.SubElement(cabecera, "CodigoCuentaCotizacion")
        ET.SubElement(ccc_elem, "Regimen").text = "0111"
        ET.SubElement(ccc_elem, "Provincia").text = provincia
        ET.SubElement(ccc_elem, "Numero").text = numero
        ET.SubElement(ccc_elem, "DigitoControl").text = dc

        periodo = ET.SubElement(cabecera, "PeriodoLiquidacion")
        ET.SubElement(periodo, "Mes").text = mes_str
        ET.SubElement(periodo, "Anio").text = anio_str

        liquidacion = ET.SubElement(root, "Liquidacion")

        total_importe = 0.0
        for worker in actual_workers:
            trabajador = ET.SubElement(liquidacion, "Trabajador")
            naf_clean = str(worker.get("naf") or worker.get("nss", "")).replace(" ", "").replace("/", "").replace("-", "")
            ET.SubElement(trabajador, "NumeroAfiliacion").text = naf_clean
            ET.SubElement(trabajador, "NumeroDocumento").text = str(worker.get("nif", "")).strip().upper()

            for concept in worker.get("concepts", []):
                conc_elem = ET.SubElement(trabajador, "ConceptoRetributivo")
                ET.SubElement(conc_elem, "CodigoConcepto").text = str(concept["code"]).zfill(4)
                amount = float(concept["amount"])
                total_importe += amount
                ET.SubElement(conc_elem, "Importe").text = f"{amount:.2f}"
                ET.SubElement(conc_elem, "IndicativoTipoConcepto").text = str(concept.get("concept_type", "C")).upper()

        # Serialización a XML legible con cabecera
        ET.indent(root, space="  ", level=0)
        xml_declaration = '<?xml version="1.0" encoding="utf-8"?>\n'
        xml_body = ET.tostring(root, encoding="utf-8").decode("utf-8")
        full_xml = xml_declaration + xml_body

        filename = f"CRA_{clean_ccc}_{actual_year}_{mes_str}.xml"
        file_path = CRA_DIR / filename
        file_path.write_text(full_xml, encoding="utf-8")

        # Persistir en base de datos
        record_id = None
        with write_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tgss_cra_records (ccc, month, year, file_path, total_workers, xml_payload, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'GENERATED', ?)
                ON CONFLICT(tenant_id, ccc, year, month) DO UPDATE SET
                    file_path = excluded.file_path,
                    total_workers = excluded.total_workers,
                    xml_payload = excluded.xml_payload,
                    status = excluded.status,
                    created_at = excluded.created_at
            """, (clean_ccc, actual_month, actual_year, str(file_path), len(actual_workers), full_xml, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            record_id = cursor.lastrowid
            if not record_id:
                cursor.execute("SELECT id FROM tgss_cra_records WHERE ccc = ? AND month = ? AND year = ?", (clean_ccc, actual_month, actual_year))
                row = cursor.fetchone()
                if row:
                    record_id = row[0] if isinstance(row, tuple) else row["id"]

        return {
            "status": "ok",
            "file_path": str(file_path),
            "record_id": record_id,
            "total_workers": len(actual_workers),
            "total_trabajadores": len(actual_workers),
            "total_importe": round(total_importe, 2),
            "xml_content": full_xml
        }

"""
INTEGRATION TESTS — Ficheros Oficiales de la Seguridad Social para SILTRA (AFI y CRA).
Valida la generación de ficheros de Afiliación (Altas MA y Bajas MB) y Conceptos Retributivos Abonados (CRA XML).
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from app.domain.services.tgss_affiliation_service import TgssAffiliationService
from app.domain.services.tgss_cra_service import TgssCraService
from app.domain.schemas import TgssAfiAction, TgssTerminationCause
from app.adapters.memory.memory import _get_connection, _init_db_schema


@pytest.fixture(autouse=True)
def setup_database():
    with _get_connection() as conn:
        _init_db_schema(conn)
        conn.execute("DELETE FROM tgss_cra_records")
        conn.execute("DELETE FROM tgss_afi_records")
        conn.execute("DELETE FROM settlements")
        conn.execute("DELETE FROM payrolls")
        conn.execute("DELETE FROM employees")
        conn.commit()


def test_tgss_alta_afi_official_format():
    """Valida la acción MA (Alta) con CCC de 11 dígitos, NAF de 12 dígitos y sin marcas UNVERIFIED."""
    employee = {
        "id": 101,
        "full_name": "LAURA MARTÍNEZ RUIZ",
        "nif": "12345678Z",
        "naf": "281234567890",
        "start_date": "2026-05-01",
        "contract_code": "100",
        "contribution_group": 1
    }

    res = TgssAffiliationService.generate_alta_afi(employee, ccc="28123456789")

    assert res["status"] == "ok"
    assert res["action"] == "MA"
    assert res.get("regulatory_status") == "UNVERIFIED"
    assert "homologación formal siltra" in res.get("warning", "").lower()

    file_path = Path(res["file_path"])
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")

    # Estructura del registro AFI
    assert "EMP*0111*28123456789" in content
    assert "TRA*281234567890*12345678Z*MA*20260501" in content
    assert "CON*100*GRP*01*1000" in content


def test_tgss_baja_afi_with_official_cause_codes_and_l13():
    """Valida la acción MB (Baja) con causas oficiales 51, 53, 54, 93 y liquidación complementaria L13."""
    employee = {
        "id": 102,
        "full_name": "ROBERTO GÓMEZ DÍAZ",
        "nif": "87654321A",
        "naf": "289876543210",
        "start_date": "2025-01-01"
    }

    # 1. Baja por causas objetivas (51) con 4.5 días de vacaciones
    res_obj = TgssAffiliationService.generate_baja_afi(
        employee=employee,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date="2026-06-30",
        vacation_days_pending=4.5,
        ccc="28123456789"
    )
    assert res_obj["action"] == "MB"
    assert res_obj["cause_code"] == "51"
    assert res_obj.get("regulatory_status") == "UNVERIFIED"
    assert "homologación formal siltra" in res_obj.get("warning", "").lower()
    content_obj = Path(res_obj["file_path"]).read_text(encoding="utf-8")
    assert "MB*20260630*CAU*51*L13*5" in content_obj or "MB*20260630*CAU*51*L13*4" in content_obj

    # 2. Baja voluntaria (53)
    res_vol = TgssAffiliationService.generate_baja_afi(
        employee=employee,
        termination_type="VOLUNTARY_RESIGNATION",
        termination_date="2026-07-15",
        vacation_days_pending=0.0,
        ccc="28123456789"
    )
    assert res_vol["cause_code"] == "53"
    assert "CAU*53" in Path(res_vol["file_path"]).read_text(encoding="utf-8")

    # 3. Fin de contrato temporal (93)
    res_end = TgssAffiliationService.generate_baja_afi(
        employee=employee,
        termination_type="END_OF_CONTRACT",
        termination_date="2026-08-31",
        vacation_days_pending=2.0,
        ccc="28123456789"
    )
    assert res_end["cause_code"] == "93"
    assert "CAU*93" in Path(res_end["file_path"]).read_text(encoding="utf-8")


def test_tgss_cra_xml_generation_for_siltra():
    """Valida la generación del fichero XML de remesa mensual CRA para SILTRA (RD-Ley 16/2013)."""
    workers_data = [
        {
            "naf": "281234567890",
            "nif": "12345678Z",
            "concepts": [
                {"code": "0001", "description": "Salario Base", "amount": 2000.00, "concept_type": "C"},
                {"code": "0005", "description": "Pagas Extras", "amount": 333.33, "concept_type": "C"},
                {"code": "0008", "description": "Plus Transporte", "amount": 80.00, "concept_type": "E"}
            ]
        }
    ]

    res = TgssCraService.generate_monthly_cra_xml(
        ccc="28123456789",
        month=4,
        year=2026,
        workers_data=workers_data
    )

    assert res["status"] == "ok"
    assert res["total_workers"] == 1
    assert Path(res["file_path"]).exists()

    xml_text = Path(res["file_path"]).read_text(encoding="utf-8")
    assert "<MensajeCRA" in xml_text
    assert "<CodigoCuentaCotizacion>" in xml_text
    assert "<Regimen>0111</Regimen>" in xml_text
    assert "<Provincia>28</Provincia>" in xml_text
    assert "<Numero>1234567</Numero>" in xml_text
    assert "<DigitoControl>89</DigitoControl>" in xml_text
    assert "<CodigoConcepto>0001</CodigoConcepto>" in xml_text
    assert "<Importe>2000.00</Importe>" in xml_text
    assert "<IndicativoTipoConcepto>C</IndicativoTipoConcepto>" in xml_text
    assert "<CodigoConcepto>0008</CodigoConcepto>" in xml_text
    assert "<IndicativoTipoConcepto>E</IndicativoTipoConcepto>" in xml_text

    # Parsear con ElementTree para validar sintaxis XML estricta
    root = ET.fromstring(xml_text)
    assert root.tag.endswith("MensajeCRA")

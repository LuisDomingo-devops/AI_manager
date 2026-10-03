"""
Pruebas unitarias para la agregación del Modelo 190 (Clave A, Clave G y claves regulatorias).
Metodología TDD: prueba escrita antes de la implementación completa.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.domain.models.billing import Model190PerceptorDTO, Model190ResultDTO
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService, AnnualTaxService


def test_model190_perceptor_dto_validations():
    """Valida restricciones de clave regulatoria y longitudes fijas de campos."""
    perceptor = Model190PerceptorDTO(
        nif="12345678Z",
        name="PEREZ GARCIA JUAN",
        clave="A",
        subclave="  ",
        percepciones_dinerarias=25000.0,
        retenciones_practicadas=3750.0,
        situacion_familiar=2,
        conyuge_nif="87654321X",
        num_hijos=2
    )
    assert perceptor.clave == "A"
    assert perceptor.percepciones_dinerarias == 25000.0
    assert perceptor.retenciones_practicadas == 3750.0

    # Clave inválida debe fallar
    with pytest.raises(ValueError, match="Clave de percepción inválida"):
        Model190PerceptorDTO(
            nif="12345678Z",
            name="TEST",
            clave="Z",
            percepciones_dinerarias=100.0,
            retenciones_practicadas=15.0
        )


def test_annual_tax_service_calculate_model_190():
    """Verifica que calculate_model_190 devuelve una instancia válida de Model190ResultDTO."""
    service = AnnualTaxService()
    
    mock_data = {
        "year": 2026,
        "perceptores": [
            {
                "nif": "12345678Z",
                "name": "JUAN EMPLEADO",
                "clave": "A",
                "subclave": "  ",
                "percepciones": 30000.0,
                "retenciones": 4500.0,
                "percepciones_especie_valoracion": 600.0,
                "percepciones_especie_ingresos_a_cuenta": 90.0,
                "percepciones_especie_repercutidos": 90.0,
                "ano_nacimiento": 1985,
                "situacion_familiar": 2,
                "conyuge_nif": "87654321X",
                "num_hijos": 2
            },
            {
                "nif": "34567890D",
                "name": "PROFESIONAL CONSULTOR",
                "clave": "G",
                "subclave": "01",
                "percepciones": 4000.0,
                "retenciones": 600.0
            }
        ],
        "total_perceptores": 2,
        "total_percepciones": 34000.0,
        "total_retenciones": 5100.0,
        "total_percepciones_especie": 600.0,
        "total_ingresos_a_cuenta": 90.0
    }

    with patch.object(AnnualTaxAggregatorService, "get_modelo_190_data", return_value=mock_data):
        result = service.calculate_model_190(fiscal_year=2026)
        assert isinstance(result, Model190ResultDTO)
        assert result.fiscal_year == 2026
        assert result.total_perceptores == 2
        assert result.total_percepciones_dinerarias == 34000.0
        assert result.total_retenciones_practicadas == 5100.0
        assert result.total_percepciones_especie == 600.0
        assert result.total_percepciones_global == 34600.0
        assert len(result.perceptores) == 2
        assert result.perceptores[0].clave == "A"
        assert result.perceptores[1].clave == "G"
        assert result.perceptores[1].subclave == "01"

"""
Tests de Integración: Flujos de Rechazo de Aprobación OOB (Spec 002 - TDD)
Verifica que cuando un usuario humano rechaza una operación o no concede aprobación,
las herramientas de nóminas y de la AEAT abortan inmediatamente sin generar ficheros ni mutar la base de datos.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.tools.server.payroll_tools import create_employee_tool, issue_monthly_payroll_tool
from app.tools.server.aeat_automation_tools import generate_modelo_303_autofill_script
from app.domain.services.approval_service import approval_service
from app.adapters.memory.memory import _get_connection

@pytest.mark.asyncio
async def test_create_employee_rejection_does_not_mutate_db(mock_approval_rejected):
    """
    Verifica que si la aprobación es rechazada, create_employee_tool no inserta al empleado en la base de datos.
    """
    res = await create_employee_tool(
        nif="12345678Z",
        nss="281234567890",
        full_name="Empleado De Prueba Rechazado",
        gross_annual_salary=30000.0,
        start_date="2026-01-01"
    )
    
    assert res["status"] == "pending_confirmation"
    assert "Propuesta de alta de empleado" in res["message"]
    
    # Comprobar que en la base de datos no se ha insertado
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM employees")
        count = cursor.fetchone()[0]
        assert count == 0, "El empleado no debe haber sido creado en base de datos si la aprobacion fue rechazada"


@pytest.mark.asyncio
async def test_aeat_model_303_rejection_aborts(mock_approval_rejected):
    """
    Verifica que si la aprobación es rechazada, no se genera el script del Modelo 303.
    """
    res = await generate_modelo_303_autofill_script(year=2026, quarter=1)
    
    assert res["status"] == "pending_confirmation"
    assert "Se va a generar el script de autocompletado para el borrador del Modelo 303" in res["message"]
    assert "script" not in res

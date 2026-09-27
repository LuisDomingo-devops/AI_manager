"""
TESTS UNITARIOS: Domain Error Contract (Spec 016)
TDD — Estos tests deben FALLAR hasta que se complete la implementación.

Cubre:
- US1: Parseo de ValidationError a DomainErrorContract
- US1: Los technical_details no deben aparecer en la serialización para LLM
- US1: El ErrorManager atrapa excepciones y devuelve un DomainErrorContract
"""
import pytest
from pydantic import ValidationError
from app.domain.schemas import DomainErrorContract, InvoiceSchema


class TestDomainErrorContractModel:
    """Pruebas del modelo DomainErrorContract."""

    def test_contrato_campos_requeridos(self):
        """Verifica que el contrato se puede instanciar con los campos obligatorios."""
        contrato = DomainErrorContract(
            status="needs_user_validation",
            reason_code="INVALID_EXTRACTED_PERCENTAGE",
            affected_fields=["iva_rate"],
            extracted_values={"base_imponible": 1000.0},
            missing_values={"iva_rate": None},
        )
        assert contrato.status == "needs_user_validation"
        assert contrato.reason_code == "INVALID_EXTRACTED_PERCENTAGE"
        assert "iva_rate" in contrato.affected_fields
        assert contrato.technical_details is None

    def test_technical_details_excluidos_de_serializacion_llm(self):
        """
        CRÍTICO (FR-002): technical_details debe excluirse al serializar
        el contrato para el contexto del LLM.
        """
        contrato = DomainErrorContract(
            status="needs_user_validation",
            reason_code="TEST",
            technical_details="Traceback (most recent call last): ...",
        )
        # El contrato no debe exponer datos técnicos en la representación para el LLM
        serializado_llm = contrato.model_dump(exclude={"technical_details"})
        assert "technical_details" not in serializado_llm
        assert "Traceback" not in str(serializado_llm)

    def test_contrato_status_validos(self):
        """Solo los status definidos en el contrato son válidos."""
        for status in ["needs_user_validation", "fatal_error", "system_error"]:
            contrato = DomainErrorContract(status=status, reason_code="X")
            assert contrato.status == status

    def test_contrato_status_invalido_lanza_error(self):
        """Un status inválido debe lanzar ValidationError de Pydantic."""
        with pytest.raises(ValidationError):
            DomainErrorContract(status="estado_inventado", reason_code="X")


class TestErrorManagerFromValidationError:
    """Pruebas de la conversión de ValidationError al contrato de dominio."""

    def test_error_manager_atrapa_validation_error(self):
        """
        T004: El ErrorManager debe capturar un ValidationError y devolver
        un DomainErrorContract con los campos afectados identificados.
        """
        from app.domain.services.error_manager import ErrorManager

        def funcion_que_falla():
            # iva_rate = 150 supera le=100 → ValidationError de Pydantic
            InvoiceSchema(
                invoice_id="F001",
                date="2024-01-15",
                issuer_name="Emisor",
                issuer_nif="B12345678",
                receiver_name="Receptor",
                receiver_nif="A87654321",
                base_imponible=1000.0,
                iva_rate=150.0,   # INVÁLIDO: supera le=100
                iva_amount=210.0,
                total_amount=1210.0,
                category="ingreso",
                quarter=1,
                year=2024,
            )

        contrato = ErrorManager.ejecutar_con_contrato(funcion_que_falla)

        assert isinstance(contrato, DomainErrorContract)
        assert contrato.status == "needs_user_validation"
        assert "iva_rate" in contrato.affected_fields
        assert contrato.technical_details is not None
        assert "iva_rate" in contrato.technical_details

    def test_error_manager_funcion_exitosa_devuelve_resultado(self):
        """
        Si la función no lanza ninguna excepción, el ErrorManager
        debe devolver el resultado directamente (sin envolver en contrato).
        """
        from app.domain.services.error_manager import ErrorManager

        def funcion_exitosa():
            return {"resultado": "ok"}

        resultado = ErrorManager.ejecutar_con_contrato(funcion_exitosa)
        assert resultado == {"resultado": "ok"}

    def test_error_manager_registra_technical_details(self):
        """
        T005 (FR-004): El ErrorManager debe almacenar el stack trace
        en technical_details para diagnóstico backend.
        """
        from app.domain.services.error_manager import ErrorManager

        def funcion_con_error_generico():
            raise ValueError("Error de sistema interno XYZ")

        contrato = ErrorManager.ejecutar_con_contrato(funcion_con_error_generico)

        assert isinstance(contrato, DomainErrorContract)
        assert contrato.status == "system_error"
        assert contrato.technical_details is not None
        assert "XYZ" in contrato.technical_details or "ValueError" in contrato.technical_details

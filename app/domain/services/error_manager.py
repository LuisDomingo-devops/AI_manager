"""
ERROR MANAGER — Gestor de errores orientado a dominio (Spec 016)

¿QUÉ HACE?
Proporciona un punto de intercepción central para las ejecuciones de herramientas.
Convierte excepciones técnicas (ValidationError, ValueError, etc.) en un
DomainErrorContract estructurado antes de que alcancen al orquestador o al usuario.

¿QUÉ NO HACE?
No lanza excepciones al exterior. No filtra datos técnicos al LLM o al usuario.

Cumple:
- FR-001: Define el contrato de error de dominio.
- FR-002: Las excepciones técnicas nunca cruzan hacia la respuesta del usuario.
- FR-004: Los detalles técnicos se registran internamente en los logs.
"""
import traceback
import logging
from typing import Any, Callable, TypeVar
from pydantic import ValidationError

from app.domain.schemas import DomainErrorContract

logger = logging.getLogger("error_manager")

T = TypeVar("T")


class ErrorManager:
    """
    Gestor de errores de dominio. Intercepta excepciones en la ejecución
    de herramientas y las convierte en un DomainErrorContract estructurado.
    """

    @staticmethod
    def ejecutar_con_contrato(funcion: Callable[[], T]) -> T | DomainErrorContract:
        """
        Ejecuta la función proporcionada y la devuelve su resultado si tiene éxito.
        Si lanza un ValidationError de Pydantic, devuelve un DomainErrorContract
        con status='needs_user_validation' y los campos afectados identificados.
        Si lanza cualquier otro tipo de excepción, devuelve un DomainErrorContract
        con status='system_error'.

        El technical_details (stack trace) se registra en los logs internos
        y se adjunta al contrato para diagnóstico backend, pero NUNCA debe
        enviarse al LLM ni al usuario.
        """
        try:
            return funcion()
        except ValidationError as exc:
            tb = traceback.format_exc()
            # (FR-004) Registrar el error técnico en los logs internos
            logger.error("ValidationError interceptado por ErrorManager: %s", tb)

            # Extraer los campos afectados desde los errores de Pydantic
            affected_fields = []
            missing_values: dict[str, Any] = {}
            extracted_values: dict[str, Any] = {}

            for error in exc.errors():
                # La localización puede ser una tupla de niveles de campos
                loc = error.get("loc", ())
                if loc:
                    field_name = ".".join(str(l) for l in loc)
                    affected_fields.append(field_name)
                    missing_values[field_name] = error.get("input")

            # (FR-002) El technical_details solo se adjunta para logging interno
            return DomainErrorContract(
                status="needs_user_validation",
                reason_code="PYDANTIC_VALIDATION_FAILED",
                affected_fields=affected_fields,
                extracted_values=extracted_values,
                missing_values=missing_values,
                technical_details=tb,
            )

        except Exception as exc:
            tb = traceback.format_exc()
            # (FR-004) Registrar cualquier otra excepción genérica
            logger.error("Excepción genérica interceptada por ErrorManager: %s", tb)

            return DomainErrorContract(
                status="system_error",
                reason_code="UNEXPECTED_SYSTEM_ERROR",
                affected_fields=[],
                extracted_values={},
                missing_values={},
                technical_details=tb,
            )

    @staticmethod
    def serializar_para_llm(contrato: DomainErrorContract) -> dict[str, Any]:
        """
        (FR-002) Serializa el DomainErrorContract para su uso como contexto del LLM.
        El campo 'technical_details' queda EXCLUIDO de la serialización para
        garantizar que los datos técnicos internos nunca lleguen al LLM.
        """
        return contrato.model_dump(exclude={"technical_details"})

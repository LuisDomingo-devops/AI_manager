"""
Validador de Esquema XML oficial de Veri*Factu (AEAT).
Valida documentos XML contra app/schemas/verifactu.xsd según la Orden HAC/1177/2024.
"""

from pathlib import Path
from typing import Tuple, List
from lxml import etree
from app.domain.exceptions import XSDValidationError


class VerifactuValidator:
    """Valida documentos XML de facturación contra el esquema oficial verifactu.xsd."""

    _schema_path = Path(__file__).resolve().parents[2] / "schemas" / "verifactu.xsd"
    _schema: etree.XMLSchema | None = None

    @classmethod
    def get_schema(cls) -> etree.XMLSchema:
        if cls._schema is None:
            if not cls._schema_path.exists():
                raise FileNotFoundError(f"Esquema verifactu.xsd no encontrado en {cls._schema_path}")
            with open(cls._schema_path, "rb") as f:
                schema_doc = etree.parse(f)
                cls._schema = etree.XMLSchema(schema_doc)
        return cls._schema

    def validate_xml(self, xml_bytes: bytes) -> Tuple[bool, List[str]]:
        """
        Valida el XML binario contra verifactu.xsd.
        Devuelve (True, []) si es válido, o (False, [errores]) si no supera la validación.
        """
        try:
            doc = etree.fromstring(xml_bytes)
            schema = self.get_schema()
            is_valid = schema.validate(doc)
            if is_valid:
                return True, []
            errors = [str(err.message) for err in schema.error_log]
            return False, errors
        except etree.XMLSyntaxError as e:
            return False, [f"Error sintáctico de XML: {e}"]
        except Exception as e:
            return False, [f"Error durante validación XSD: {e}"]

    def assert_valid_xml(self, xml_bytes: bytes) -> None:
        """Lanza XSDValidationError si el documento no es conforme al esquema."""
        is_valid, errors = self.validate_xml(xml_bytes)
        if not is_valid:
            raise XSDValidationError(
                message=f"El XML no cumple el esquema verifactu.xsd oficial: {'; '.join(errors)}",
                errors=errors
            )

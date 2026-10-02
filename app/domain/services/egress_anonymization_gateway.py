"""
egress_anonymization_gateway.py
===============================
Gateway e interceptor de seguridad para prospección externa web (RGPD / LOPDGDD).
Garantiza que ninguna consulta, URL o scraping contenga NIF, NIE, CIF, IBAN,
razones sociales o datos nominativos de clientes y proveedores.
"""

import re
import logging
from typing import Tuple, List, Optional
from app.domain.services.fiscal_validator import validate_spanish_id

logger = logging.getLogger(__name__)


class RGPDViolationError(ValueError):
    """Excepción lanzada cuando una consulta saliente contiene datos personales o identificadores fiscales."""
    def __init__(self, message: str, detected_entities: List[str]):
        super().__init__(message)
        self.detected_entities = detected_entities


class EgressAnonymizationGateway:
    """
    Pasarela de auditoría y anonimización de tráfico saliente para prospección de mercado.
    Aplica filtros deterministas y rechaza cualquier consulta que vulnere el principio de minimización.
    """

    # Expresión regular para NIF / NIE / CIF
    ID_PATTERN = re.compile(
        r"\b(?:[0-9]{8}[A-Za-z]|[XYZxyz][0-9]{7}[A-Za-z]|[ABCDEFGHJNPQRSUVWabcdefghjnpqrsuvw][0-9]{7}[0-9A-Ja-j])\b"
    )

    # Expresión regular para IBAN español
    IBAN_PATTERN = re.compile(
        r"\bES\d{2}[ -]?(?:\d{4}[ -]?){4}\d{2,4}\b",
        re.IGNORECASE
    )

    @classmethod
    def audit_outgoing_query(
        cls,
        query: str,
        forbidden_terms: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Analiza una cadena de búsqueda saliente en busca de identificadores sensibles.
        Retorna (is_safe, lista_de_violaciones).
        """
        if not query:
            return True, []

        violations: List[str] = []

        # 1. Detección de NIF / NIE / CIF
        for match in cls.ID_PATTERN.finditer(query):
            raw_id = match.group()
            is_valid, id_type = validate_spanish_id(raw_id)
            if is_valid:
                violations.append(f"Identificador fiscal detectado ({id_type}): {raw_id}")

        # 2. Detección de IBAN
        for match in cls.IBAN_PATTERN.finditer(query):
            violations.append(f"Cuenta bancaria IBAN detectada: {match.group()}")

        # 3. Detección de términos restringidos específicos (razón social, nombres propios)
        if forbidden_terms:
            for term in forbidden_terms:
                if term and len(term.strip()) >= 3:
                    pattern = re.compile(r"\b" + re.escape(term.strip()) + r"\b", re.IGNORECASE)
                    if pattern.search(query):
                        violations.append(f"Término restringido de cliente/usuario detectado: {term}")

        is_safe = len(violations) == 0
        return is_safe, violations

    @classmethod
    def enforce_safe_query(
        cls,
        query: str,
        forbidden_terms: Optional[List[str]] = None
    ) -> str:
        """
        Valida que la consulta sea 100% segura. Si detecta violaciones del RGPD,
        lanza RGPDViolationError interrumpiendo la petición saliente.
        """
        is_safe, violations = cls.audit_outgoing_query(query, forbidden_terms)
        if not is_safe:
            msg = f"Violación del RGPD: La consulta externa contiene datos protegidos: {'; '.join(violations)}"
            logger.error(msg)
            raise RGPDViolationError(msg, detected_entities=violations)
        return query

    @classmethod
    def build_anonymized_market_query(
        cls,
        cnae_code: str,
        sector_name: str,
        region: str,
        service_keyword: Optional[str] = None
    ) -> str:
        """
        Construye una cadena de prospección sectorial canónica y abstracta,
        totalmente desprovista de identificadores personales.
        """
        clean_cnae = re.sub(r"[^\d]", "", cnae_code or "")
        clean_sector = re.sub(r"[^\w\s]", "", sector_name or "").strip()
        clean_region = re.sub(r"[^\w\s]", "", region or "España").strip()
        clean_keyword = re.sub(r"[^\w\s]", "", service_keyword or "").strip()

        base_terms = [f"tarifas sectoriales", clean_sector]
        if clean_keyword:
            base_terms.append(clean_keyword)
        if clean_region:
            base_terms.append(clean_region)
        if clean_cnae:
            base_terms.append(f"CNAE {clean_cnae}")

        canonical_query = " ".join([t for t in base_terms if t])
        return cls.enforce_safe_query(canonical_query)

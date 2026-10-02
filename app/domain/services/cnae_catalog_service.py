"""
cnae_catalog_service.py
=======================
Servicio del catálogo de actividades económicas (CNAE-2009) y benchmark sectorial:
- Consulta y filtrado por código CNAE o término de búsqueda.
- Extracción de datos de referencia (márgenes típicos, tarifas medianas, inflación del INE).
"""

import json
import logging
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CNAECatalogService:
    """Catálogo de referencia oficial de actividades CNAE-2009 e indicadores sectoriales."""

    _DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cnae_market_benchmarks.json"

    @classmethod
    def load_catalog(cls) -> List[Dict[str, Any]]:
        """Carga el catálogo JSON de actividades y benchmarks sectoriales."""
        if not cls._DATA_PATH.exists():
            return []
        try:
            with open(cls._DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando catálogo CNAE: {e}")
            return []

    @classmethod
    def list_activities(cls, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retorna la lista de actividades CNAE, filtrando opcionalmente por código o texto.
        """
        catalog = cls.load_catalog()
        if not query:
            return catalog

        q = query.strip().lower()
        results = []
        for item in catalog:
            cnae = item.get("cnae_code", "").lower()
            name = item.get("sector_name", "").lower()
            region = item.get("region", "").lower()
            if q in cnae or q in name or q in region:
                results.append(item)
        return results

    @classmethod
    def get_by_cnae(cls, cnae_code: str, region: str = "Comunidad de Madrid") -> Optional[Dict[str, Any]]:
        """
        Obtiene el benchmark de referencia para un código CNAE y región dados.
        """
        catalog = cls.load_catalog()
        cnae = cnae_code.strip()
        reg = region.strip().lower()

        # Coincidencia exacta de CNAE y región
        for item in catalog:
            if item.get("cnae_code") == cnae and item.get("region", "").lower() == reg:
                return item

        # Fallback a ámbito nacional "España"
        for item in catalog:
            if item.get("cnae_code") == cnae and item.get("region") == "España":
                return item

        # Fallback si coincide el código
        for item in catalog:
            if item.get("cnae_code") == cnae:
                return item

        return None

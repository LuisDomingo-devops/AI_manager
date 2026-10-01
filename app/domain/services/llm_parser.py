"""
Parser robusto de respuestas JSON generadas por LLMs locales y remotos.
Elimina ProtocolError gestionando bloques markdown y ruido perimetral.
"""

import json
import re
from typing import Dict, Any


class LlmParser:
    """Extrae y valida estructuras JSON a partir de respuestas de modelos de lenguaje."""

    @staticmethod
    def extract_json_robust(text: str) -> Dict[str, Any]:
        """
        Extrae un objeto JSON válido eliminando bloques ```json ... ``` y texto explicativo adyacente.
        """
        if not text:
            raise ValueError("El texto de respuesta está vacío.")

        cleaned = text.strip()

        # 1. Intentar extraer de bloque de código markdown ```json ... ```
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
        if code_block_match:
            candidate = code_block_match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # 2. Intentar buscar el primer '{' y el último '}'
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = cleaned[start_idx : end_idx + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # 3. Intentar parseo directo
        try:
            return json.loads(cleaned)
        except Exception as e:
            raise ValueError(f"No se pudo extraer una estructura JSON válida de la respuesta del LLM: {str(e)}")

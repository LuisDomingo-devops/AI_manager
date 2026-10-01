"""
Generador de Prompts del Sistema para el Asistente IA.
Asegura deduplicación estricta de herramientas disponibles y un esquema JSON predecible.
"""

from typing import List, Dict, Any


class PromptGenerator:
    """Construye prompts para los agentes orquestadores evitando redundancias."""

    def format_tools_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """
        Formatea el catálogo de herramientas deduplicando aquellas con el mismo nombre.
        """
        seen_tools = set()
        unique_tools: List[Dict[str, Any]] = []

        for tool in tools:
            name = tool.get("name", "")
            if name and name not in seen_tools:
                seen_tools.add(name)
                unique_tools.append(tool)

        lines = ["Herramientas disponibles para invocar:"]
        for t in unique_tools:
            name = t.get("name")
            desc = t.get("description", "Sin descripción")
            lines.append(f"- `{name}`: {desc}")

        lines.append("\nResponde obligatoriamente en formato JSON con la siguiente estructura:")
        lines.append('```json\n{"action": "<nombre_herramienta>", "params": { ... }}\n```')

        return "\n".join(lines)

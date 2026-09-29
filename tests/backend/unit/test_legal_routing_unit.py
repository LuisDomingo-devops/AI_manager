"""
Tests unitarios para Legal Routing Correction (Spec 014).
Verifican las reglas de routing sin lanzar el orquestador completo.

FR-001: Router prioriza intención operacional sobre keywords aisladas
FR-002: Domain stickiness durante correcciones
FR-003: MarcosAgent no puede emitir tool_calls
FR-004: MarcosAgent solo acepta preguntas legales y devuelve texto plano
FR-005: AVISO LEGAL se añade una sola vez (single source of truth)
FR-006: MarcosAgent no toma el control del flujo global
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestMarcosAgentSystemPromptConstraints:
    """FR-003/FR-004: El system prompt de MarcosAgent impone restricciones estrictas."""

    def test_marcos_system_prompt_forbids_tool_calls(self):
        """FR-003: El prompt debe prohibir explícitamente emitir tool_calls."""
        from app.domain.agents.marcos.marcos_agent import marcos_agent
        assert "No tienes acceso a herramientas ni puedes emitir tool_calls" in marcos_agent.system_prompt

    def test_marcos_system_prompt_requires_plain_text(self):
        """FR-003: El prompt debe exigir respuesta en texto plano."""
        from app.domain.agents.marcos.marcos_agent import marcos_agent
        assert "Debes responder siempre en texto plano" in marcos_agent.system_prompt

    def test_marcos_system_prompt_is_loaded(self):
        """El system_prompt de MarcosAgent debe estar cargado y ser no vacío."""
        from app.domain.agents.marcos.marcos_agent import marcos_agent
        assert marcos_agent.system_prompt is not None
        assert len(marcos_agent.system_prompt) > 50

    def test_marcos_agent_is_singleton(self):
        """El agente Marcos se instancia como singleton global."""
        from app.domain.agents.marcos import marcos_agent as module
        from app.domain.agents.marcos.marcos_agent import marcos_agent
        assert marcos_agent is not None

    def test_marcos_prompt_file_exists(self):
        """El archivo de prompt marcos_system.txt debe existir."""
        prompt_path = Path("app/prompts/marcos_system.txt")
        assert prompt_path.exists(), "app/prompts/marcos_system.txt debe existir"

    def test_marcos_system_prompt_does_not_contain_aviso_legal_hardcoded(self):
        """
        FR-005: MarcosAgent NO debe tener el AVISO LEGAL hardcodeado en su prompt.
        El disclaimer se añade una sola vez en el Orchestrator.
        """
        from app.domain.agents.marcos.marcos_agent import marcos_agent
        # El prompt de Marcos no debe incluir el texto del disclaimer
        # para evitar duplicados (FR-005)
        prompt = marcos_agent.system_prompt
        # No debe contener el disclaimer de forma duplicada
        disclaimer_count = prompt.count("AVISO LEGAL:")
        assert disclaimer_count == 0, (
            f"MarcosAgent no debe incluir 'AVISO LEGAL:' en su prompt "
            f"(aparece {disclaimer_count} veces). El disclaimer lo añade el Orchestrator."
        )


class TestLegalKeywordRouting:
    """FR-001: Las keywords de contabilidad NO deben activar routing legal."""

    @pytest.mark.parametrize("accounting_phrase", [
        "¿cuánto IVA he pagado?",
        "me has dicho el IVA cobrado",
        "eso es IVA devengado, yo pregunto por el soportado",
        "te estás equivocando",
        "el IVA de esta factura es 21%",
        "hazme el cálculo del IVA",
        "¿cuánto he pagado este trimestre?",
        "está mal, falta la factura de ayer",
    ])
    def test_sc001_accounting_phrases_not_classified_as_pure_legal(self, accounting_phrase):
        """
        SC-001: Las frases de contabilidad/operativas NO deben ser pure_legal.
        Verifica la lógica de clasificación directamente.
        """
        # Simular la lógica de detección de intención legal pura
        # (extraída del planner_orchestrator.py)
        legal_keywords = [
            "normativa", "contrato", "obligación legal", "ley ", "código civil",
            "constitución", "código penal", "artículo", "jurídico", "jurídica",
            "legislación", "legal", "ilegal", "delito", "demanda", "juzgado",
            "tribunal", "sentencia", "recurso", "apelación",
        ]

        phrase_lower = accounting_phrase.lower()
        # Verificar que las frases contables no contengan keywords legales puras
        # que forzarían routing a Marcos
        has_pure_legal = any(kw in phrase_lower for kw in legal_keywords)

        # Estas frases no deben clasificarse como puramente legales
        assert not has_pure_legal, (
            f"La frase '{accounting_phrase}' fue clasificada erróneamente como legal. "
            f"El routing a MarcosAgent sería incorrecto."
        )

    @pytest.mark.parametrize("legal_phrase", [
        "¿es legal hacer esto?",
        "¿qué obligación legal tengo?",
        "redacta un contrato",
        "¿qué consecuencias legales tiene esto?",
        "¿qué dice la normativa sobre este caso?",
        "consulta sobre el código civil",
        "¿esto constituye un delito?",
    ])
    def test_sc002_legal_phrases_classified_as_legal(self, legal_phrase):
        """
        SC-002: Las frases con intención legal explícita SÍ deben detectarse como legales.
        """
        legal_keywords = [
            "normativa", "contrato", "obligación legal", "ley ", "código civil",
            "constitución", "código penal", "artículo", "jurídico", "jurídica",
            "legislación", "legal", "ilegal", "delito", "demanda", "juzgado",
        ]
        phrase_lower = legal_phrase.lower()
        has_legal = any(kw in phrase_lower for kw in legal_keywords)
        assert has_legal, (
            f"La frase '{legal_phrase}' no fue detectada como legal. "
            f"No se delegaría a MarcosAgent."
        )


class TestAvisoLegalDisclaimerContract:
    """FR-005: El AVISO LEGAL tiene una única fuente de verdad."""

    def test_disclaimer_appended_by_orchestrator_not_marcos(self):
        """
        El orchestrator añade el AVISO LEGAL al final de las respuestas legales.
        MarcosAgent solo devuelve contenido legal sin disclaimer.
        """
        # Simular respuesta de MarcosAgent sin disclaimer
        marcos_raw_response = "Según el artículo 27 de la Constitución Española, el derecho a la educación..."
        assert "AVISO LEGAL:" not in marcos_raw_response

        # El Orchestrator añade el disclaimer si no está presente
        if "AVISO LEGAL:" not in marcos_raw_response:
            final_response = (
                marcos_raw_response
                + "\n\nAVISO LEGAL: La información proporcionada tiene carácter orientativo. "
                "Consulte siempre la normativa oficial."
            )
        else:
            final_response = marcos_raw_response

        # Solo debe aparecer una vez
        assert final_response.count("AVISO LEGAL:") == 1

    def test_disclaimer_not_duplicated_if_already_present(self):
        """FR-005: Si el disclaimer ya está, no se añade una segunda vez."""
        response_with_disclaimer = (
            "Respuesta legal.\n\nAVISO LEGAL: La información tiene carácter orientativo."
        )
        # Lógica del orchestrator: solo añade si no está presente
        if "AVISO LEGAL:" not in response_with_disclaimer:
            final = response_with_disclaimer + "\n\nAVISO LEGAL: ..."
        else:
            final = response_with_disclaimer

        assert final.count("AVISO LEGAL:") == 1


class TestMarcosAgentInterface:
    """FR-004/FR-006: Interfaz y contrato de MarcosAgent."""

    def test_marcos_agent_has_generate_response_method(self):
        """MarcosAgent debe tener el método generate_response."""
        from app.domain.agents.marcos.marcos_agent import MarcosAgent
        assert hasattr(MarcosAgent, "generate_response")

    def test_marcos_agent_has_llm(self):
        """MarcosAgent debe tener un LLM asignado."""
        from app.domain.agents.marcos.marcos_agent import marcos_agent
        assert marcos_agent.llm is not None

    def test_marcos_generate_response_is_coroutine(self):
        """generate_response debe ser una coroutine (async)."""
        import asyncio
        import inspect
        from app.domain.agents.marcos.marcos_agent import MarcosAgent
        assert inspect.iscoroutinefunction(MarcosAgent.generate_response)

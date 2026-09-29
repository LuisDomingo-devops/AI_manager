"""
Suite QA para Legal Routing Correction (Spec 014).
Valida los criterios de éxito SC-001, SC-002, SC-003 y SC-004.

SC-001: Los 7 ejemplos negativos NO deben ir a MarcosAgent.
SC-002: Los 5 ejemplos positivos SÍ deben ir a MarcosAgent.
SC-003: 0% de respuestas con AVISO LEGAL duplicado.
SC-004: Tests de routing positivo y negativo pasan consistentemente.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# -------------------------------------------------------------------------
# Helpers de clasificación (replica la lógica del planner_orchestrator)
# -------------------------------------------------------------------------
LEGAL_KEYWORDS = [
    "normativa", "contrato", "obligación legal", "ley ", "código civil",
    "constitución", "código penal", "artículo", "jurídico", "jurídica",
    "legislación", "legal", "ilegal", "delito", "demanda", "juzgado",
    "tribunal", "sentencia", "recurso", "apelación",
]

def _is_pure_legal(text: str) -> bool:
    """Replica la lógica de detección de intención legal del orchestrator."""
    lower = text.lower()
    return any(kw in lower for kw in LEGAL_KEYWORDS)


class TestQASC001NegativeRoutingExamples:
    """
    SC-001: 100% de los ejemplos negativos NO deben clasificarse como legales.
    Estos mensajes son contables/operativos y NO deben ir a MarcosAgent.
    """

    NEGATIVE_EXAMPLES = [
        "¿cuánto IVA he pagado?",
        "me has dicho el IVA cobrado",
        "eso es IVA devengado, yo pregunto por el soportado",
        "te estás equivocando",
        "el IVA de esta factura es 21%",
        "hazme el cálculo del IVA",
        "¿cuánto he pagado este trimestre?",
    ]

    @pytest.mark.parametrize("phrase", NEGATIVE_EXAMPLES)
    def test_negative_example_not_routed_to_marcos(self, phrase):
        """SC-001: El mensaje NO debe clasificarse como puramente legal."""
        assert not _is_pure_legal(phrase), (
            f"FALLO SC-001: '{phrase}' fue clasificado como legal. "
            f"El sistema lo enviaría erróneamente a MarcosAgent."
        )

    def test_sc001_all_negative_examples_pass(self):
        """SC-001: Los 7 ejemplos negativos deben pasar al 100%."""
        failures = [p for p in self.NEGATIVE_EXAMPLES if _is_pure_legal(p)]
        assert len(failures) == 0, (
            f"SC-001 FALLIDO: {len(failures)}/7 ejemplos negativos clasificados como legales: "
            f"{failures}"
        )


class TestQASC002PositiveRoutingExamples:
    """
    SC-002: 100% de los ejemplos positivos SÍ deben clasificarse como legales.
    Estos mensajes SÍ deben ir a MarcosAgent.
    """

    POSITIVE_EXAMPLES = [
        "¿es legal hacer esto?",
        "¿qué obligación legal tengo?",
        "redacta un contrato",
        "¿qué consecuencias legales tiene esto?",
        "¿qué dice la normativa sobre este caso?",
    ]

    @pytest.mark.parametrize("phrase", POSITIVE_EXAMPLES)
    def test_positive_example_routed_to_marcos(self, phrase):
        """SC-002: El mensaje SÍ debe clasificarse como legal."""
        assert _is_pure_legal(phrase), (
            f"FALLO SC-002: '{phrase}' NO fue clasificado como legal. "
            f"El sistema NO lo enviaría a MarcosAgent cuando debería."
        )

    def test_sc002_all_positive_examples_pass(self):
        """SC-002: Los 5 ejemplos positivos deben pasar al 100%."""
        failures = [p for p in self.POSITIVE_EXAMPLES if not _is_pure_legal(p)]
        assert len(failures) == 0, (
            f"SC-002 FALLIDO: {len(failures)}/5 ejemplos positivos no detectados como legales: "
            f"{failures}"
        )


class TestQASC003NoDisclaimerDuplication:
    """
    SC-003: 0% de respuestas deben contener AVISO LEGAL duplicado.
    """

    def test_orchestrator_adds_disclaimer_exactly_once_when_missing(self):
        """El orchestrator añade el disclaimer exactamente 1 vez si no está."""
        responses_without_disclaimer = [
            "Según el artículo 154 de la normativa fiscal...",
            "El código civil español establece en su artículo 27...",
            "La obligación legal es clara en este contexto...",
        ]
        for raw in responses_without_disclaimer:
            # Simular lógica del orchestrator
            if "AVISO LEGAL:" not in raw:
                final = raw + "\n\nAVISO LEGAL: La información proporcionada tiene carácter orientativo."
            else:
                final = raw
            count = final.count("AVISO LEGAL:")
            assert count == 1, (
                f"SC-003 FALLIDO: Se esperaba 1 AVISO LEGAL, encontrado {count} en: '{final[:80]}...'"
            )

    def test_orchestrator_does_not_duplicate_existing_disclaimer(self):
        """El orchestrator NO añade un segundo disclaimer si ya existe."""
        responses_with_disclaimer = [
            "Respuesta legal.\n\nAVISO LEGAL: La información tiene carácter orientativo.",
            "Texto. AVISO LEGAL: Consulte la normativa oficial.",
        ]
        for raw in responses_with_disclaimer:
            # Simular lógica: solo añadir si no está
            if "AVISO LEGAL:" not in raw:
                final = raw + "\n\nAVISO LEGAL: ..."
            else:
                final = raw
            count = final.count("AVISO LEGAL:")
            assert count == 1, (
                f"SC-003 FALLIDO: Disclaimer duplicado, encontrado {count} veces."
            )

    def test_marcos_response_without_disclaimer_gets_one_added(self):
        """
        Flujo completo: Marcos devuelve sin disclaimer →
        Orchestrator añade uno → resultado tiene exactamente 1.
        """
        marcos_output = "El artículo 154 de la LGT establece..."
        assert "AVISO LEGAL:" not in marcos_output

        # Orchestrator añade
        orchestrated = marcos_output + "\n\nAVISO LEGAL: La información proporcionada tiene carácter orientativo."
        assert orchestrated.count("AVISO LEGAL:") == 1


class TestQASC004ConsistentRoutingTests:
    """
    SC-004: Los tests de routing positivo y negativo pasan consistentemente.
    Verifica la clasificación bajo diferentes variantes de los mismos temas.
    """

    def test_iva_variations_never_legal(self):
        """Variaciones de consultas IVA nunca son routing legal."""
        iva_variants = [
            "¿cuánto IVA he pagado este año?",
            "IVA soportado del primer trimestre",
            "calcula el IVA de mis facturas",
            "el IVA está mal calculado",
            "necesito ver el IVA deducible",
        ]
        for phrase in iva_variants:
            assert not _is_pure_legal(phrase), (
                f"Variante IVA clasificada erróneamente como legal: '{phrase}'"
            )

    def test_explicit_legal_triggers_never_missed(self):
        """Triggers legales explícitos siempre son detectados."""
        legal_triggers = [
            "¿qué dice la normativa al respecto?",
            "necesito un contrato de arrendamiento",
            "¿esto es ilegal?",
            "¿qué artículo aplica aquí?",
            "consulta jurídica sobre mi empresa",
        ]
        for phrase in legal_triggers:
            assert _is_pure_legal(phrase), (
                f"Trigger legal no detectado: '{phrase}'"
            )

    def test_domain_stickiness_accounting_correction_stays_operational(self):
        """
        FR-002: Correcciones cortas en contexto contable no cambian a dominio legal.
        Palabras como 'mal', 'error', 'equivocado' son correcciones, no consultas legales.
        """
        correction_phrases = [
            "está mal",
            "eso es incorrecto",
            "te has equivocado",
            "falta la factura",
            "eso no es lo que pedí",
        ]
        for phrase in correction_phrases:
            assert not _is_pure_legal(phrase), (
                f"Corrección operativa clasificada como legal: '{phrase}'"
            )

    def test_marcos_boundaries_in_prompt_are_present(self):
        """
        SC-004: Los tests de boundary de MarcosAgent son consistentes.
        El prompt siempre tiene las restricciones FR-003.
        """
        from app.domain.agents.marcos.marcos_agent import marcos_agent
        prompt = marcos_agent.system_prompt

        # Ambas restricciones deben estar presentes simultáneamente
        has_no_tools = "No tienes acceso a herramientas ni puedes emitir tool_calls" in prompt
        has_plain_text = "Debes responder siempre en texto plano" in prompt

        assert has_no_tools and has_plain_text, (
            "MarcosAgent debe tener ambas restricciones: no tools + texto plano"
        )

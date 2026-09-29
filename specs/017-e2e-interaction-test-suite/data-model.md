# Data Model: End-to-End Interaction Test Suite

## Entidades del Test

### `E2ETestFixture` (fixture compartida de pytest)
Fixture que proporciona mocks reutilizables en todos los escenarios.

**Componentes**:
- `mock_llm`: `MagicMock` con `generate = AsyncMock()`
- `e2e_memory`: `DummyMemory` en RAM (sin BD, sin persistencia)
- `mock_vector`: `MagicMock` con `query_facts.return_value = []`

---

### `E2EScenario` (concepto de test)
Cada test sigue la misma estructura:

| Campo | Descripción |
|-------|-------------|
| `user_message` | El mensaje que envía el usuario |
| `llm_responses` | Lista ordenada de respuestas JSON simuladas del LLM |
| `expected_type` | Tipo esperado en la respuesta (`"chat"`, `"tool"`) |
| `expected_response_keywords` | Palabras que DEBEN aparecer en la respuesta |
| `forbidden_keywords` | Palabras que NO DEBEN aparecer (FR-006) |
| `expected_tool_calls_count` | Número esperado de llamadas a tools (FR-002) |
| `expected_agent` | Agente esperado que procesa la petición (`None`, `"marcos"`, etc.) (FR-003) |
| `workflow_paused` | Si el workflow debe pausarse tras el escenario (FR-005) |

---

## Mapeo de Escenarios → Tests

| Escenario | User Story | Fixture clave | Verificación principal |
|-----------|-----------|---------------|----------------------|
| SC1: "hola" | US1 | `_classify_intent` → `conversational` | `tool_calls == 0`, no MarcosAgent |
| SC2: "no saludas?" | US1 | `_classify_intent` → `conversational` | `tool_calls == 0`, no confirmación implícita |
| SC3: "tiempo en Bilbao" | US1 | `_classify_intent` → `operational` | No `JSONDecodeError` en respuesta |
| SC4: "¿cuánto IVA...?" | US2 | no ruta a Marcos; `accounting` domain | No MarcosAgent, respuesta sobre IVA |
| SC5: corrección IVA | US2 | `accounting` domain persistente | No MarcosAgent, corrección procesada |
| SC6: "te estás inventando..." | US2 | `accounting` domain persistente | No MarcosAgent |
| SC7: factura ilegible | US3 | `DomainErrorContract` devuelto | No `ValidationError` en respuesta, `workflow_paused=True` |
| SC8: extracción exacta | US3 | tool `parse_invoice` mock correcto | `iva_rate=21`, `base=34.51`, etc. |
| SC9: consulta legal explícita | US4 | ruta a MarcosAgent | MarcosAgent llamado, disclaimer añadido |

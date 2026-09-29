# Research: End-to-End Interaction Test Suite

## Decisiones Técnicas

### DECISIÓN 1: Estrategia de Mocking del LLM

**Elección**: `unittest.mock.AsyncMock` + `side_effect` de lista de respuestas JSON.

**Justificación**: La arquitectura existente ya usa este patrón en `test_planner_orchestrator.py` y `test_intent_gate.py`. El LLM real no debe llamarse en los tests E2E. Cada respuesta del LLM se simula como una cadena JSON válida que el `extract_json_robust` del orquestador puede parsear.

**Alternativa descartada**: Patch directo del método `_classify_intent` con valor retornado fijo. Descartado porque los tests E2E deben validar el flujo completo incluyendo la clasificación de intent, no saltársela.

---

### DECISIÓN 2: Fixture `session_memory_fixture` 

**Elección**: Definir una `DummyMemory` en el propio archivo de test. El `conftest.py` del proyecto ya define `session_memory_fixture` en el scope de backend, pero como queremos un fichero de test autónomo sin dependencias externas frágiles, usaremos una fixture local `e2e_memory`.

**Justificación**: Permite que el archivo de test sea completamente aislado y ejecutable de forma independiente.

---

### DECISIÓN 3: Verificación de Efectos Secundarios

**Elección**: Inspeccionar los `call_args_list` de los mocks para verificar:
- Cuántas veces se llamó al LLM (`mock_llm.generate.call_count`)
- Si MarcosAgent fue invocado (`mock_marcos_agent.generate_response.called`)
- Si alguna tool concreta fue llamada o no

**Justificación**: Cumple los requisitos FR-002, FR-003 y FR-004 de la spec. Keyword matching puro en el texto de respuesta no es suficiente.

---

### DECISIÓN 4: Agentes especializados (MarcosAgent, SecurityAgent)

**Elección**: Mock via `patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response", new_callable=AsyncMock)`.

**Justificación**: Verificar que el enrutador del orquestador decide invocar o no invocar al agente es exactamente lo que las User Stories 2 y 4 requieren. El mock permite hacer `assert_called` / `assert_not_called`.

---

### DECISIÓN 5: Escenario 7 — Factura ilegible con DomainErrorContract

**Elección**: Mockear la tool `parse_invoice` para que devuelva un `DomainErrorContract` con `status="needs_user_validation"`. El test verifica que el orquestador llama a `manejar_domain_error_contract` (implementado en spec 016) y que la respuesta final no contiene strings técnicos.

**Justificación**: La spec 016 ya implementó `ErrorManager` y `manejar_domain_error_contract`. Los tests E2E de la spec 017 simplemente ejercitan ese flujo de extremo a extremo.

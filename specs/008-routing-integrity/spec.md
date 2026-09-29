# Especificación: 008-routing-integrity

## 1. Contexto y Hallazgo en Discovery (Sección 11 del Contrato)

En la sección 11 de `docs/audit/discovery-contract.md` se estipula la auditoría rigurosa de los enrutamientos semánticos en el orquestador:
> Audita `"word" in msg_lower`.
> Este patrón NO debe provocar que `"password"` se interprete como Word.
> Busca también otros falsos positivos de routing.
> Los tests deben incluir palabras que contengan accidentalmente keywords.
> Ejemplo conceptual: `word`, `password`, `password reset`, `Microsoft Word`, `document`.

### Evidencia Técnica en el Código Fuente:
1. En `app/domain/planner_orchestrator.py` (Líneas 293-294), `SpecializedAgentRouter.route_if_applicable()` evalúa:
   ```python
   is_word_query = "word" in msg_lower or "docx" in msg_lower or "redacta" in msg_lower or "informe financiero" in msg_lower or "documento" in msg_lower
   if is_word_query and ("genera" in msg_lower or "crea" in msg_lower or "redacta" in msg_lower or "word" in msg_lower):
   ```
2. La comprobación `"word" in msg_lower` mediante subcadena pura provoca que cualquier mensaje que contenga la palabra `"password"` (ej. *"crea una password segura"*, *"genera mi password"*, *"password reset"*) active accidentalmente `is_word_query = True` y delegue en `WordAgent` en lugar de en los agentes de seguridad/credenciales o el flujo principal.
3. Lo mismo ocurre si se evalúan subcadenas sueltas sin límites de frontera de palabra (`\bword\b`).

---

## 2. Requisitos Funcionales

1. **Uso Estricto de Límites de Frontera de Palabra (`\b`)**:
   - En `SpecializedAgentRouter`:
     - Reemplazar subcadenas `"word" in msg_lower` por expresiones regulares con límites de palabra: `re.search(r"\bword\b", msg_lower)` o `re.search(r"\bdocx\b", msg_lower)`.
     - Garantizar que términos como `"password"`, `"passwords"`, `"sword"`, `"crossword"` o `"forward"` **NUNCA** activen el enrutador hacia `WordAgent`.
2. **Preservación del Enrutamiento Legítimo de Documentos**:
   - Mensajes como *"genera un documento Word"*, *"redacta un informe en Word"*, *"crea un archivo docx"* deben seguir enrutándose a `WordAgent`.
   - Mensajes como *"genera una password"*, *"crea un password"*, *"password reset"* deben devolver `None` o delegar en el flujo correspondiente, sin secuestro por parte de `WordAgent`.

---

## 3. Plan de Pruebas (TDD)

1. **Unitario**:
   - `tests/backend/unit/test_routing_word_agent_boundaries.py`:
     - Verificar que `re.search(r"\bword\b", "genera un password")` es `None`.
     - Verificar que `SpecializedAgentRouter` devuelve `None` (o no enruta a `WordAgent`) ante `"genera un password"`, `"crea un password seguro"`, etc.

2. **Integración**:
   - `tests/backend/integration/test_orchestrator_routing_integrity_integration.py`:
     - Ejecutar `route_if_applicable` con mensajes trampa: `"genera un password"`, `"resetea mi password"`, `"password"`.
     - Verificar que NO se invoca a `word_agent`.
     - Verificar que con `"genera un documento en Word"` o `"crea un informe Word"` SÍ se delega a `word_agent`.

3. **QA**:
   - `tests/backend/qa/test_routing_integrity_qa_suite.py`:
     - Batería de pruebas con palabras compuestas, falsos amigos y homónimos accidentales (`sword`, `passwords`, `foreword`, `word`).

---

## 4. Archivos Afectados

- `app/domain/planner_orchestrator.py`
- `tests/backend/unit/test_routing_word_agent_boundaries.py`
- `tests/backend/integration/test_orchestrator_routing_integrity_integration.py`
- `tests/backend/qa/test_routing_integrity_qa_suite.py`

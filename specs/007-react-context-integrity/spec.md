# Especificación: 007-react-context-integrity

## 1. Contexto y Hallazgo en Discovery (Sección 10 del Contrato)

En la sección 10 de `docs/audit/discovery-contract.md` se estipula la auditoría rigurosa de ReAct y el contexto semántico:
> Audita:
> `build_context`
> `_check_and_store_fact`
> Comprueba si: `_check_and_store_fact(...)` se ejecuta dentro de cada iteración ReAct.
> Si un mismo hecho se almacena varias veces, define una estrategia explícita de:
> - deduplicación;
> - identidad del hecho;
> - persistencia;
> - actualización.
> Crea tests que demuestren:
> `same fact + multiple iterations = one logical fact`

### Evidencia Técnica en el Código Fuente:
1. En `app/domain/planner_orchestrator.py`, `ConversationContextService.build_context()` ejecuta `_check_and_store_fact(...)` en cada construcción de contexto.
2. `_check_and_store_fact` delega en `vector_memory.add_fact(session_id, cleaned_fact, client_id=client_id)`.
3. En `app/infrastructure/database/memory/vector_memory.py`, `add_fact()` genera un identificador aleatorio con `uuid.uuid4()`:
   ```python
   fact_id = str(uuid.uuid4())
   self.collection.add(
       documents=[fact.strip()],
       metadatas=[{"session_id": session_id or "global", "client_id": cid}],
       ids=[fact_id]
   )
   ```
4. Consecuencia: cada llamada genera un nuevo UUID aleatorio e inserta un documento duplicado en ChromaDB. Si el orquestador ReAct reintenta o construye contexto varias veces con el mismo hecho, se multiplican copias redundantes en la base vectorial, contaminando la memoria semántica con recuerdos duplicados.

---

## 2. Requisitos Funcionales y Estrategia de Deduplicación

1. **Identidad Determinista del Hecho**:
   - Todo hecho semántico tendrá una identidad unívoca derivada de su contenido normalizado y el tenant/cliente:
     - Normalización: `cleaned = " ".join(fact.strip().lower().split())`.
     - ID determinista: `fact_id = f"fact_{cid}_{hashlib.sha256(cleaned.encode('utf-8')).hexdigest()[:16]}"` (o UUIDv5).

2. **Deduplicación y Upsert en `VectorMemory.add_fact`**:
   - En lugar de insertar ciegamente con un nuevo UUID4 en cada llamada, `add_fact` debe:
     - Utilizar el ID determinista del hecho.
     - Utilizar `self.collection.upsert(...)` (o verificar existencia previa si la versión de ChromaDB lo requiere).
     - Si el hecho ya existe para ese cliente, actualizar metadatos (`updated_at`, `session_id`) sin generar un nuevo registro físico ni duplicar el vector.
     - Retornar el `fact_id` consistente.

3. **Invariante ReAct / Context**:
   - `same fact + multiple iterations = one logical fact`: si `_check_and_store_fact` o `build_context` se ejecuta N veces en un loop con el mismo mensaje que expresa un hecho, la colección vectorial contendrá exactamente 1 único registro con ese hecho, y `query_facts` devolverá una única instancia.

---

## 3. Plan de Pruebas (TDD)

1. **Unitario**:
   - `tests/backend/unit/test_vector_memory_fact_deduplication.py`:
     - Invocar `add_fact` dos o más veces con el mismo hecho (ej. `"mi lenguaje favorito es Python"`).
     - Comprobar que devuelve el mismo `fact_id` determinista.
     - Comprobar que en la colección sólo existe 1 documento para ese hecho.

2. **Integración**:
   - `tests/backend/integration/test_react_context_fact_deduplication_integration.py`:
     - Simular múltiples iteraciones invocando `build_context` con el mismo mensaje que contiene un hecho.
     - Verificar que `_check_and_store_fact` no duplica los recuerdos en memoria semántica.
     - Comprobar que `vector_memory.query_facts(...)` devuelve una única ocurrencia del hecho.

3. **QA**:
   - `tests/backend/qa/test_react_context_integrity_qa_suite.py`:
     - Comprobar el comportamiento con múltiples hechos distintos en varias sesiones, verificando que hechos distintos coexisten pacíficamente mientras que hechos idénticos (incluso con variaciones mínimas de mayúsculas/espacios) se deduplican lógicamente.

---

## 4. Archivos Afectados

- `app/infrastructure/database/memory/vector_memory.py`
- `app/domain/planner_orchestrator.py`
- `tests/backend/unit/test_vector_memory_fact_deduplication.py`
- `tests/backend/integration/test_react_context_fact_deduplication_integration.py`
- `tests/backend/qa/test_react_context_integrity_qa_suite.py`

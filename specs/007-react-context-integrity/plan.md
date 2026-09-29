# Plan de Implementación: 007-react-context-integrity

## 1. Arquitectura y Enfoque

El objetivo es cumplir con la sección 10 del Discovery Contract ("REACT / CONTEXT"):
- `_check_and_store_fact` se ejecuta dentro de `build_context` en el flujo del orquestador.
- Actualmente, `VectorMemory.add_fact` genera un `uuid.uuid4()` aleatorio en cada llamada e inserta con `self.collection.add()`, provocando que hechos idénticos se dupliquen infinitamente en la base vectorial si `build_context` se ejecuta en múltiples iteraciones.
- Implementaremos una estrategia explícita de:
  - **Identidad del hecho**: ID determinista basado en el hash del contenido normalizado y el tenant/cliente.
  - **Deduplicación**: Uso de `self.collection.upsert()` con el ID determinista.
  - **Persistencia y Actualización**: Si el hecho ya existe, se actualizan metadatos sin duplicar entradas.
  - **Invariante**: `same fact + multiple iterations = one logical fact`.

## 2. Fases de Ejecución

- **Fase 1 (Setup)**:
  - Crear directorio para logs en `tests/logs/spec007/`.

- **Fase 2 (TDD Red)**:
  - Crear test unitario `tests/backend/unit/test_vector_memory_fact_deduplication.py` que demuestre que al llamar `add_fact` dos veces con el mismo hecho, actualmente se generan dos IDs distintos y se duplican documentos.
  - Crear test de integración `tests/backend/integration/test_react_context_fact_deduplication_integration.py` que demuestre la duplicación en `build_context`.
  - Ejecutar tests y guardar log de fallo en `tests/logs/spec007/us1_red.log`.

- **Fase 3 (TDD Green)**:
  - En `app/infrastructure/database/memory/vector_memory.py`: implementar generación de ID determinista y método `upsert` para deduplicar hechos.
  - Ejecutar tests unitario e integración para verificar pase a verde y registrar en `tests/logs/spec007/us2_green.log`.

- **Fase 4 (QA y Resiliencia)**:
  - Crear `tests/backend/qa/test_react_context_integrity_qa_suite.py` auditando el ciclo completo con múltiples hechos, normalización de espacios y mayúsculas, y consultas semánticas.
  - Ejecutar suite de QA y guardar log en `tests/logs/spec007/us3_green.log`.

- **Fase 5 (Validación Completa y Certificación)**:
  - Ejecutar suite completa de backend (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar cero regresiones.
  - Consolidar commit formal en Git.

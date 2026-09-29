# Implementation Plan: End-to-End Interaction Test Suite

**Branch**: `017-e2e-interaction-test-suite` | **Date**: 2026-09-27 | **Spec**: [spec.md](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/specs/017-e2e-interaction-test-suite/spec.md)

**Input**: Feature specification from `/specs/017-e2e-interaction-test-suite/spec.md`

## Summary

Crear una suite de pruebas E2E (end-to-end) con 9 escenarios automatizados en pytest que reproduzcan el ciclo completo Frontend → API → Orchestrator → LLM → Tool. Los tests verifican tanto la respuesta textual como los efectos secundarios internos del sistema (tool_calls, agente seleccionado, ausencia de strings técnicos en la respuesta). No se modifica ningún código de producción.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: pytest, pytest-asyncio, unittest.mock (AsyncMock, MagicMock, patch)

**Storage**: N/A — Los tests usan memoria en RAM (DummyMemory / session_memory_fixture)

**Testing**: pytest con modo asyncio. Los tests viven en `tests/backend/integration/`.

**Target Platform**: Backend agentic Python

**Project Type**: Suite de tests de integración E2E — NO modifica código de producción

**Performance Goals**: Cada test individual debe ejecutarse en < 2 s (sin LLM real)

**Constraints**:
- No se puede modificar el código fuente de producción
- El LLM se mockeará completamente en todos los escenarios
- Los agentes (MarcosAgent, SecurityAgent) se mockearán vía `unittest.mock.patch`
- La fixture `session_memory_fixture` ya existe en conftest o se define localmente

**Scale/Scope**: 9 escenarios → 9 tests en un único archivo `test_e2e_interaction_suite.py`

## Constitution Check

- [x] I. Desarrollo en Español: Toda documentación y respuestas en castellano.
- [x] II. TDD: Los tests E2E son la propia especificación ejecutable; deben existir antes de cualquier corrección futura.
- [x] III. Cobertura Completa: La suite cubre unitario (comportamiento del orquestador), integración (ciclo E2E) y QA (escenarios de borde).
- [x] IV. Ejecución y Log: Tras la implementación se ejecuta toda la suite y se guarda el log.
- [x] V. Navegador: N/A (no hay automatización web).

## Project Structure

### Documentation (this feature)

```text
specs/017-e2e-interaction-test-suite/
├── plan.md              # Este archivo
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (a generar)
```

### Source Code (repository root — SOLO TESTS, sin tocar producción)

```text
tests/
└── backend/
    └── integration/
        └── test_e2e_interaction_suite.py   # NUEVO — Los 9 escenarios E2E
```

**Structure Decision**: Archivo único de integración. Los 9 escenarios están cohesionados y comparten las mismas fixtures de mock, por lo que un único archivo es preferible a 9 archivos separados.

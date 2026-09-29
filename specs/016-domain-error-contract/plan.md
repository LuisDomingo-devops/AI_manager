# Implementation Plan: Domain Error & UX Contract

**Branch**: `016-domain-error-contract` | **Date**: 2026-09-27 | **Spec**: [spec.md](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/specs/016-domain-error-contract/spec.md)

**Input**: Feature specification from `/specs/016-domain-error-contract/spec.md`

## Summary

Implementar un contrato estructurado (DomainErrorContract) para que los errores de las herramientas (como fallos de validación o extracción) se devuelvan al orquestador en un formato controlado en lugar de excepciones puras, previniendo fugas técnicas (como los Pydantic ValidationErrors) a la respuesta del usuario (P-03). El flujo además debe pausarse si requiere confirmación.

## Technical Context

**Language/Version**: Python 3.12 (as per project norm)

**Primary Dependencies**: Pydantic, LLM Orchestrator (PlannerOrchestrator)

**Storage**: SQLite (for logging errors in system tables/logs)

**Testing**: Pytest (asyncio)

**Target Platform**: Backend API / CLI 

**Project Type**: Agentic System / Backend

**Performance Goals**: N/A - Error handling should not add noticeable latency

**Constraints**: Errors must not leak technical details to LLM prompts or UI.

**Scale/Scope**: Impacts all tools and orchestration logic.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] I. Desarrollo en Español: All documentation and user responses will be in Spanish.
- [x] II. Test-Driven Development (TDD) Estricto: TDD will be enforced in the task generation.
- [x] III. Cobertura de Pruebas Completa: Unit and integration tests are required for the new error contract and orchestration handling.
- [x] IV. Ejecución Continua y Registro de Tests: A log file will be generated after test execution.
- [x] V. Navegador Estándar: N/A (no browser automation).

## Project Structure

### Documentation (this feature)

```text
specs/016-domain-error-contract/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (to be generated)
```

### Source Code (repository root)

```text
app/
├── domain/
│   ├── schemas.py              # Update with DomainErrorContract and ToolException structures
│   └── services/               # Update orchestrator to handle DomainErrorContract
├── infrastructure/
│   └── database/               # Logging for the stack traces
tests/
├── backend/
│   ├── unit/                   # Unit tests for DomainErrorContract serialization and tool interception
│   └── integration/            # Integration tests for orchestrator paused workflow and clean UX
```

**Structure Decision**: Standard single project agentic Python architecture.

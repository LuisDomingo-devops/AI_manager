# Quickstart: End-to-End Interaction Test Suite

## Propósito
Esta guía valida que los 9 escenarios E2E de Alfonso se ejecutan de forma fiable sin llamadas al LLM real.

## Prerrequisitos
- Entorno Python configurado con `uv`
- Dependencias instaladas (`uv sync`)

## Validación rápida: Ejecutar los 9 escenarios

```bash
uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -v
```

**Resultado esperado**: 9 tests pasando, 0 fallando.

## Validación por User Story

### US1 — Límites conversacionales (Escenarios 1, 2, 3)
```bash
uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc1 or sc2 or sc3" -v
```
- SC1: "hola" → early return conversacional, 0 tools
- SC2: "no saludas?" → early return, 0 tools
- SC3: "tiempo en Bilbao" → responde sin JSONDecodeError

### US2 — Stickiness de dominio contable (Escenarios 4, 5, 6)
```bash
uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc4 or sc5 or sc6" -v
```
- Verificar que MarcosAgent NO fue llamado en ninguno de los 3

### US3 — Extracción robusta de documentos (Escenarios 7, 8)
```bash
uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc7 or sc8" -v
```
- SC7: workflow_paused=True, sin "ValidationError" en respuesta
- SC8: valores exactos iva_rate=21, base=34.51

### US4 — Consultas legales explícitas (Escenario 9)
```bash
uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc9" -v
```
- MarcosAgent fue llamado exactamente 1 vez
- Disclaimer legal presente en la respuesta
- MarcosAgent NO llamó a ninguna tool adicional

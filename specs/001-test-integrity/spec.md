# Feature Specification: Saneamiento Integral de Tests e Integridad de Aserciones (Spec 001)

**Feature Branch**: `001-test-integrity`  
**Created**: 2026-09-28  
**Status**: Ready for Planning  
**Input**: Saneamiento de tests inválidos, eliminación de reliquias `pass` de debug eliminado a medias, erradicación de retornos silenciosos ante excepciones (`if crashed: return`), sustitución de aserciones placebo y limpieza de scripts de soporte (`dev_seeder.py`, `legal_seeder.py`), en estricto cumplimiento del Contrato de Discovery.

---

## 1. Contexto y Problema

Durante el descubrimiento técnico y la auditoría forense del proyecto Alfonso AI Konta, se identificó un problema crítico que invalida la confiabilidad de la suite de pruebas:

1. **Tests que enmascaran colapsos mediante `return`**:
   En `tests/backend/qa/test_qa_stress.py:L254-261`, cuando ocurre una excepción durante la emisión o procesamiento masivo de facturas, el bloque `except` captura el error y ejecuta un `return` directo. Para el ejecutor de pruebas `pytest`, un test que finaliza con `return` sin lanzar una excepción se marca como **`PASSED` (Verde)**, dando una falsa sensación de que el sistema resiste el estrés cuando en realidad ha colapsado.
2. **Proliferación masiva de sentencias `pass` huérfanas**:
   Se identificaron **107 sentencias `pass` en 40 archivos de tests** (con **44 `pass`** concentrados únicamente en `test_qa_stress.py`), y **78 sentencias `pass` en 29 archivos de `app/`** (11 en `legal_seeder.py` y 6 en `dev_seeder.py`). Estas líneas son cicatrices de scripts o prompts que eliminaron llamadas a `print()` o logs de depuración sustituyéndolas indiscriminadamente por `pass`, dejando ramas de control vacías (`if broken: pass; continue`).
3. **Aserciones débiles ("Placebo Asserts")**:
   En `tests/backend/integration/test_integration_stress.py:L132`, se valida `assert len(successful_calls) > 0`. En una prueba concurrente de 10 peticiones, si 9 explotan con HTTP 500 y solo 1 responde 200, el test pasa como exitoso.
4. **Desactivación de protecciones regulatorias en tests**:
   En `tests/backend/integration/test_coverage_booster.py:L80`, se ejecuta `DROP TRIGGER IF EXISTS trg_prevent_delete_verifactu` para poder borrar la tabla de Veri*Factu y forzar un resultado vacío "válido", violando el contrato de integridad contable y fiscal.

---

## 2. Mapa de Archivos Afectados

| # | Archivo | Problema Detectado | Categoría | Severidad |
|---|---|---|---|:---:|
| 1 | `tests/backend/qa/test_qa_stress.py` | 44 `pass`, `if crashed: return` y ausencia de assert final | Test Swallowing / False Green | P1 |
| 2 | `tests/backend/integration/test_integration_stress.py` | 6 `pass`, aserción débil `len(successful_calls) > 0` | Placebo Assertion | P1 |
| 3 | `tests/backend/integration/test_coverage_booster.py` | `DROP TRIGGER` destructivo sobre Veri*Factu | Tampering de Seguridad | P1 |
| 4 | `app/utils/dev_seeder.py` | 6 `pass` sueltos entre bloques de inserción | Código Muerto / Reliquia | P2 |
| 5 | `app/utils/legal_seeder.py` | 11 `pass` sueltos en parsing XML e ingestión ChromaDB | Código Muerto / Reliquia | P2 |
| 6 | `tests/conftest.py` | 7 `pass` en fixtures y teardown ciegos | Fixture Swallowing | P2 |

---

## 3. User Scenarios y Criterios de Aceptación

### User Story 1 (P1): Erradicación de Falsos Positivos en Tests de Estrés y QA
Como equipo de ingeniería y auditoría,  
quiero que las pruebas de estrés (`test_qa_stress.py` y `test_integration_stress.py`) fallen de forma ruidosa e inmediata ante cualquier excepción no controlada,  
para que ningún colapso del sistema pase desapercibido bajo un falso color verde.

**Criterios de Aceptación**:
1. Eliminar todos los bloques `if crashed: return` y `pass` de silenciado en `test_qa_stress.py`.
2. Añadir aserciones deterministas: si `crashed` es `True`, el test debe fallar con `pytest.fail(f"Colapso durante el estrés: {crash_exception}")`.
3. Validar de forma estricta los resultados de concurrencia: la tasa de fallos permitida no debe superar los límites de contrato definidos, y deben comprobarse explícitamente los códigos HTTP y los estados de base de datos.
4. Las pruebas de concurrencia en SQLite deben verificar formalmente el manejo de reintentos o el error específico `database is locked` sin ocultar errores de sintaxis o de esquema.

---

### User Story 2 (P1): Blindaje de Triggers e Inalterabilidad de Veri*Factu en Tests
Como responsable legal y contable,  
quiero que ningún test desactive ni elimine triggers de inalterabilidad (`trg_prevent_delete_verifactu`),  
para que las pruebas garanticen el cumplimiento de la Ley Antifraude 11/2021 tanto en producción como en entornos de prueba.

**Criterios de Aceptación**:
1. Eliminar la instrucción `DROP TRIGGER IF EXISTS trg_prevent_delete_verifactu` en `test_coverage_booster.py`.
2. Las pruebas que verifiquen el estado inicial de Veri*Factu deben hacerlo en bases de datos aisladas en memoria o mediante transacciones con rollback, sin destruir las salvaguardas del motor SQLite.

---

### User Story 3 (P2): Limpieza e Integración de Logging Estructurado en Seeders
Como desarrollador y operador del sistema,  
quiero que los seeders (`dev_seeder.py` y `legal_seeder.py`) sustituyan las sentencias `pass` residuales por logs estructurados trazables con `app_logger`,  
para disponer de visibilidad exacta de los registros, facturas y artículos sembrados sin código muerto.

**Criterios de Aceptación**:
1. En `app/utils/dev_seeder.py`, eliminar los 6 `pass` y reemplazarlos por `app_logger.info` con el conteo de facturas, proyectos y clientes inicializados.
2. En `app/utils/legal_seeder.py`, eliminar los 11 `pass` y registrar con `app_logger.info` el progreso de descarga de BOE, extracción de artículos e indexación en ChromaDB.
3. No debe quedar ninguna sentencia `pass` huérfana en estos archivos.

---

## 4. Invariantes Constitucionales y Requisitos No Funcionales

- **NFR-001 (TDD Estricto)**: Toda corrección de test debe ser precedida por un caso de prueba que evidencie el fallo antes de sanear.
- **NFR-002 (Preservación de la Suite)**: Las pruebas corregidas deben reflejar el comportamiento real del sistema sin mocks espurios.
- **NFR-003 (0 Reliquias `pass`)**: Reducir a 0 los `pass` residuales en los archivos objetivos.
- **NFR-004 (Registro de Logs)**: Toda ejecución de test registrará su correspondiente archivo de log.
- **NFR-005 (Idioma Castellano)**: Documentación, aserciones y mensajes de log estrictamente en castellano.

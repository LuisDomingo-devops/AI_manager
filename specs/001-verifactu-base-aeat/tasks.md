# Tasks: Consolidación Arquitectura y Conformidad VeriFactu (AEAT)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Insertar certificados de prueba en la base de datos (tabla `certificates`) desde `data/certificados_prueba` para su consumo por el servicio de firma.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 [P] Refactorizar `app/utils/signature.py` para usar `signxml` garantizando el estándar XMLDSig y cargar certificados desde la base de datos de manera segura (`DatabaseEncryptor`).
- [x] T003 Refactorizar `app/domain/services/verifactu_service.py` para instanciar correctamente el cliente HTTP/SOAP real contra la AEAT y abandonar los simuladores.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Verificación de Conformidad con AEAT (Priority: P1) 🏆 MVP

**Goal**: Asegurar que las facturas emitidas por el sistema cumplen con todos los requisitos del formato y protocolo de envío de la AEAT para el sistema VeriFactu.

**Independent Test**: Puede probarse enviando facturas de prueba al entorno de validación/sandbox de la AEAT y verificando que son aceptadas sin errores de estructura o firma.

### Tests for User Story 1 (OPTIONAL)
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**
- [x] T004 [US1] Añadir test de integración en `tests/backend/integration/test_verifactu_real_soap.py` para probar la construcción del XML y firma (se mockeará la respuesta HTTP).

### Implementation for User Story 1
- [x] T005 [P] [US1] Implementar construcción del XML payload de `RegistroFacturacion` en `verifactu_service.py`.
- [x] T006 [P] [US1] Implementar cálculo riguroso del `prev_event_hash` y `current_hash` (SHA-256 en UTF-8) en `verifactu_service.py`.
- [x] T007 [US1] Implementar método real `send_to_aeat_sif` en `verifactu_service.py` para realizar POST a `prewww10.aeat.es`.
- [x] T008 [US1] Parsear y gestionar correctamente las respuestas de la AEAT (`RespuestaAEAT`) incluyendo código CSV y estado `accepted`/`rejected`.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Ejecución de Suite de Tests de Integración (Priority: P2)

**Goal**: Ejecutar una suite de tests de integración completa para el módulo VeriFactu que valide el flujo entero.

**Independent Test**: Ejecutando el comando de test y verificando que todos pasan y generan el log de resultados correspondiente.

### Implementation for User Story 2
- [x] T009 [P] [US2] Escribir tests en `tests/backend/integration/test_verifactu.py` para validar los códigos HTTP y CSV esperados usando respuestas mockeadas de la AEAT.
- [x] T010 [P] [US2] Escribir tests en `tests/backend/integration/test_verifactu_integrity.py` para validar el hash chaining secuencial en múltiples facturas insertadas.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Resolución de Deuda Técnica y Seguridad (Priority: P1)

**Goal**: Eliminar la deuda técnica crítica y vulnerabilidades antes del paso a producción (API keys en disco, fallbacks inseguros de VeriFactu, excepciones silenciosas y tests no deterministas).

**Independent Test**: Auditoría de código, ejecución aislada de tests en CI sin fixtures compartidas en disco, y pruebas de inyección de errores para asegurar que no hay fallos silenciosos.

### Implementation for User Story 3
- [x] T011 [P] [US3] En `verifactu_service.py`, lanzar `NotImplementedError` si se intenta usar `offline_simulated` en entorno de producción.
- [x] T012 [P] [US3] Eliminar silencios inseguros `except Exception: pass` en `app/domain/services/bank_service.py` y levantar excepción correspondiente o loguear como warning.
- [x] T013 [P] [US3] Eliminar silencios inseguros `except Exception: pass` en `app/domain/services/mail_tools.py` (y `gmail_sync.py` si los hay) levantando excepción correspondiente.
- [x] T014 [US3] Refactorizar la obtención de configuraciones y contraseñas de modo que no se escriban logs ni variables sin cifrado en disco en producción (revisar `app/config.py`).

**Checkpoint**: All user stories should now be independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T015 [P] Actualizar `readme.md` para documentar cómo configurar VeriFactu, variables de entorno y carga de certificados.
- [x] T016 Ejecutar todos los tests para asegurar que no hay regresiones.

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### Parallel Opportunities
- T002 y T003 pueden desarrollarse en paralelo.
- Los tests T004, T009 y T010 pueden escribirse en paralelo.
- Las tareas de deuda técnica de la Phase 5 (T011, T012, T013, T014) pueden ser implementadas por desarrolladores independientes y en paralelo al resto de US.

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently y comprobar con la AEAT.

## Notes
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

# AI Manager — Roadmap de Refactorización Arquitectónica

> Objetivo: evolucionar AI Manager hacia una arquitectura limpia, mantenible y alineada con **SOLID + Arquitectura Hexagonal**, sin reescribir el sistema desde cero ni romper las funcionalidades existentes.

---

# Estado actual

* [ ] Arquitectura hexagonal completamente aplicada
* [ ] Dependencias del dominio aisladas de infraestructura
* [ ] Capa `Application` claramente separada
* [ ] API dividida por casos de uso
* [ ] Orquestador reducido y especializado
* [ ] Sistema de agentes extensible mediante registro
* [ ] Sistema de herramientas desacoplado mediante Ports
* [ ] Cobertura de tests suficiente para refactorizar con seguridad

---

# FASE 0 — Preparación y protección contra regresiones

## Auditoría

* [ ] Generar mapa de dependencias del proyecto.
* [ ] Identificar todos los imports `domain -> adapters`.
* [ ] Identificar todos los imports `domain -> infrastructure`.
* [ ] Identificar accesos directos a SQLite/Filesystem desde dominio o API.
* [ ] Identificar ciclos de imports.
* [ ] Identificar usos de `LazyAdapterProxy`.
* [ ] Identificar módulos con múltiples responsabilidades.
* [ ] Identificar globals y singletons que dificulten los tests.

## Tests

* [ ] Ejecutar toda la suite actual y registrar el estado inicial.
* [ ] Añadir tests de caracterización para los flujos críticos antes de refactorizar.
* [ ] Cubrir como mínimo:

  * [ ] Chat
  * [ ] Memoria
  * [ ] Herramientas
  * [ ] Agentes

* [ ] Configurar tests rápidos para Domain y Application sin infraestructura real.

---

# FASE 1 — Separar la API

## Dividir `routes.py`

Crear:

```text
app/api/routes/
            ├── chat.py
            ├── calendar.py
            ├── mail.py
            ├── browser.py
            ├── computer.py
            ├── memory.py
            └── security.py
```

Tareas:

* [ ] Crear `app/api/routes/chat.py`.
* [ ] Crear `app/api/routes/calendar.py`.
* [ ] Crear `app/api/routes/mail.py`.
* [ ] Crear `app/api/routes/browser.py`.
* [ ] Crear `app/api/routes/computer.py`.
* [ ] Crear `app/api/routes/memory.py`.
* [ ] Crear `app/api/routes/security.py`.
* [ ] Mantener cada endpoint centrado únicamente en HTTP.
* [ ] Eliminar lógica de negocio de los endpoints.
* [ ] Eliminar acceso directo a SQLite desde las rutas.
* [ ] Eliminar imports directos de adapters desde las rutas cuando exista un caso de uso equivalente.
* [ ] Reducir progresivamente `routes.py` hasta eliminarlo o convertirlo en un agregador mínimo.

## Objetivo

Cada endpoint debería seguir aproximadamente:

```text
HTTP Request
     ↓
Controller / Route
     ↓
Application Use Case
     ↓
Domain
     ↓
Port
     ↓
Adapter
```

---

# FASE 2 — Crear Application Layer

Crear:

```text
app/application/
            ├── chat/
            ├── memory/
            ├── tools/
            ├── agents/
            ├── calendar/
            └── mail/
```

Tareas:

* [ ] Crear `app/application/`.
* [ ] Crear `app/application/chat/`.
* [ ] Crear `app/application/memory/`.
* [ ] Crear `app/application/tools/`.
* [ ] Crear `app/application/agents/`.
* [ ] Crear `app/application/calendar/`.
* [ ] Crear `app/application/mail/`.
* [ ] Mover la coordinación de casos de uso desde `planner_orchestrator.py`.
* [ ] Definir claramente qué pertenece a Application.
* [ ] Definir claramente qué pertenece a Domain.
* [ ] Evitar que Application dependa de implementaciones concretas cuando exista un Port.

## Casos de uso iniciales

* [ ] `ChatUseCase`
* [ ] `ExecuteToolUseCase`
* [ ] `RouteAgentUseCase`
* [ ] `GetMemoryUseCase`
* [ ] `ClearMemoryUseCase`
* [ ] `CreateCalendarEventUseCase`
* [ ] `DeleteCalendarEventUseCase`
* [ ] `ListCalendarEventsUseCase`

---

# FASE 3 — Limpiar Domain Layer

## Regla principal

> El dominio no debe conocer FastAPI, Ollama, SQLite, filesystem, Chroma, Gmail ni ningún otro detalle de infraestructura.

Tareas:

* [ ] Eliminar todos los `from app.adapters ...` dentro de `app/domain/`.
* [ ] Eliminar accesos a filesystem desde Domain.
* [ ] Eliminar accesos directos a bases de datos desde Domain.
* [ ] Eliminar dependencias directas de Ollama desde Domain.
* [ ] Eliminar dependencias directas de FastAPI desde Domain.
* [ ] Sustituir cada dependencia externa por un Port.
* [ ] Mantener entidades independientes de infraestructura.
* [ ] Mantener Value Objects independientes de infraestructura.
* [ ] Mantener reglas de negocio independientes de infraestructura.
* [ ] Mantener servicios de dominio independientes de infraestructura.

## Ports

Revisar los existentes:

* [ ] `LLMPort`
* [ ] `MemoryPort`
* [ ] `VectorMemoryPort`
* [ ] `BridgePort`
* [ ] `CalendarPort`

Crear cuando corresponda:

* [ ] `ToolExecutorPort`
* [ ] `ToolRegistryPort`
* [ ] `AgentPort`
* [ ] `AgentRouterPort`
* [ ] `CorrectionLogPort`

## Principio

Los Ports deben ser:

* pequeños
* específicos
* independientes de infraestructura
* fáciles de implementar
* fáciles de mockear/fakear en tests

---

# FASE 4 — Refactorizar `PlannerOrchestrator`

## Objetivo

Reducir `PlannerOrchestrator` hasta convertirlo en una pieza de coordinación pequeña o eliminarlo progresivamente en favor de casos de uso específicos.

Actualmente contiene demasiadas responsabilidades.

### Separar

* [ ] `ConversationContextService`
* [ ] `SpecializedAgentRouter`
* [ ] `ToolExecutionEngine`
* [ ] Gestión de memoria.
* [ ] Construcción de contexto.
* [ ] Construcción de prompts.
* [ ] Registro de correcciones.
* [ ] Gestión de errores.
* [ ] Ejecución de herramientas.
* [ ] Routing de agentes.

### Además

* [ ] Eliminar imports directos de adapters.
* [ ] Inyectar dependencias mediante Ports.
* [ ] Reducir el tamaño del orquestador.
* [ ] Evitar métodos que hagan demasiadas cosas.
* [ ] Añadir tests unitarios independientes para cada servicio resultante.

---

# FASE 5 — Eliminar `Domain → Adapters`

Esta es una de las tareas arquitectónicas más importantes.

## Auditoría

* [ ] Buscar todos los imports `app.adapters` dentro de `app/domain`.
* [ ] Clasificar cada dependencia.
* [ ] Determinar si pertenece al dominio, Application o infraestructura.
* [ ] Crear un Port cuando represente una dependencia externa.
* [ ] Implementar el Port en `app/adapters`.
* [ ] Inyectar la implementación desde el Composition Root.
* [ ] Eliminar el import concreto del Domain.

## Objetivo

Conseguir:

```text
app/domain/
    ↓
Ports
    ↑
Adapters
```

y nunca:

```text
app/domain/
    ↓
Adapters
```

## Criterio de aceptación

El Domain debe poder ejecutarse en tests sin iniciar:

* [ ] Ollama
* [ ] FastAPI
* [ ] SQLite
* [ ] navegador
* [ ] filesystem externo
* [ ] servicios cloud
* [ ] Internet

---

# FASE 6 — Dependency Injection y Composition Root

* [ ] Definir un único punto de composición de dependencias.
* [ ] Instanciar adapters fuera del Domain.
* [ ] Inyectar `LLMPort`.
* [ ] Inyectar `MemoryPort`.
* [ ] Inyectar `VectorMemoryPort`.
* [ ] Inyectar `ToolExecutorPort`.
* [ ] Inyectar `BridgePort`.
* [ ] Inyectar `CalendarPort`.
* [ ] Reducir globals y singletons.
* [ ] Eliminar progresivamente `LazyAdapterProxy`.
* [ ] Evitar imports dinámicos salvo casos técnicamente justificados.
* [ ] Crear factories/providers para infraestructura.

## Arquitectura objetivo

```python
planner = Planner(
    llm=OllamaLLMAdapter(...),
    memory=SQLiteMemoryAdapter(...),
    vector_memory=VectorMemoryAdapter(...),
    tool_executor=ToolExecutorAdapter(...),
)
```

El `Planner` no debería saber qué implementaciones concretas utiliza.

---

# FASE 7 — Refactorizar el sistema de agentes

## Problema actual

Evitar un router basado en una cadena creciente de:

```python
if is_marcos_query:
    ...

if is_security_query:
    ...

if is_excel_query:
    ...

if is_word_query:
    ...
```

Esto obliga a modificar el código central cada vez que se añade un agente.

## Objetivo

Crear:

```text
AgentPort
    ↓
AgentRegistry
    ↓
Agents
```

## Tareas

* [ ] Crear `AgentPort`.
* [ ] Definir `can_handle(request)`.
* [ ] Definir `execute(request)`.
* [ ] Crear `AgentRegistry`.
* [ ] Registrar agentes mediante configuración/composición.
* [ ] Eliminar imports directos de agentes concretos desde el orquestador.
* [ ] Eliminar progresivamente lógica específica de cada agente del router.
* [ ] Añadir tests de routing.

## Agentes

* [ ] Marcos / agente legal-fiscal
* [ ] Security Agent
* [ ] Excel Agent
* [ ] Word Agent
* [ ] Agentes especializados futuros

## Criterio SOLID

Añadir un agente nuevo **no debería requerir modificar el código central del router**.

---

# FASE 8 — Refactorizar el sistema de herramientas

* [ ] Crear `ToolExecutorPort`.
* [ ] Crear `ToolRegistryPort` si es necesario.
* [ ] Separar registro de herramientas de ejecución.
* [ ] Mover la introspección de herramientas fuera del Domain.
* [ ] Separar autorización/RBAC de ejecución.
* [ ] Separar herramientas de cliente y servidor mediante contratos claros.
* [ ] Evitar que Domain conozca:

  * [ ] `get_tool`
  * [ ] `prepare_tool_args`
  * [ ] `inspect.signature`
  * [ ] detalles del registry
* [ ] Crear adapters concretos para filesystem.
* [ ] Crear adapters concretos para browser.
* [ ] Crear adapters concretos para computer.
* [ ] Crear adapters concretos para shell.
* [ ] Crear adapters concretos para otras herramientas.
* [ ] Añadir tests unitarios del executor.
* [ ] Añadir tests de permisos/RBAC.

---

# FASE 9 — Refactorizar LLM

## Objetivo

Separar completamente la lógica del proveedor LLM de la lógica de negocio.

Crear:

```text
app/adapters/outbound/llm/
└── ollama_adapter.py
```

Tareas:

* [ ] Mantener `LLMPort` como abstracción.
* [ ] Crear `OllamaLLMAdapter`.
* [ ] Separar comunicación HTTP con Ollama.
* [ ] Separar parsing de respuestas.
* [ ] Separar gestión de prompts.
* [ ] Separar extracción de JSON.
* [ ] Separar regex relacionadas con respuestas del LLM.
* [ ] Evitar que Domain conozca Ollama.
* [ ] Preparar soporte futuro para otros proveedores.

Proveedores potenciales:

* [ ] Ollama
* [ ] OpenAI
* [ ] Anthropic
* [ ] Gemini
* [ ] Otros

## Criterio

Cambiar Ollama por otro proveedor no debería obligar a modificar Domain.

---

# FASE 10 — Refactorizar memoria y persistencia

* [ ] Mantener `MemoryPort`.
* [ ] Crear/normalizar `SQLiteMemoryAdapter`.
* [ ] Mantener `VectorMemoryPort`.
* [ ] Crear/normalizar adapter vectorial.
* [ ] Eliminar `DB_PATH` del Domain.
* [ ] Eliminar SQL directo de casos de uso.
* [ ] Mantener SQL únicamente dentro de adapters de persistencia.
* [ ] Separar memoria conversacional de memoria vectorial.
* [ ] Separar preferencias del usuario.
* [ ] Separar correcciones.
* [ ] Separar contexto de conversación.
* [ ] Añadir tests usando adapters fake/in-memory.

---

# FASE 11 — Auditoría SOLID

## S — Single Responsibility Principle

* [ ] Dividir `routes.py`.
* [ ] Dividir `planner_orchestrator.py`.
* [ ] Separar parsing.
* [ ] Separar prompts.
* [ ] Separar memoria.
* [ ] Separar routing.
* [ ] Separar ejecución.
* [ ] Revisar módulos con múltiples razones de cambio.

## O — Open/Closed Principle

* [ ] Sustituir routing basado en `if` por Registry.
* [ ] Hacer extensibles los agentes.
* [ ] Hacer extensibles las herramientas.
* [ ] Hacer extensibles los proveedores LLM.
* [ ] Evitar modificar el core para añadir nuevas capacidades.

## L — Liskov Substitution Principle

* [ ] Verificar que las implementaciones cumplen los Ports.
* [ ] Crear tests de contrato para adapters.
* [ ] Comprobar sustitución entre implementaciones.
* [ ] Comprobar comportamiento consistente entre adapters.

## I — Interface Segregation Principle

* [ ] Revisar todos los Ports.
* [ ] Dividir interfaces grandes.
* [ ] Evitar métodos que una implementación no necesita.
* [ ] Mantener contratos específicos.

## D — Dependency Inversion Principle

* [ ] Domain depende de abstracciones.
* [ ] Application depende de abstracciones.
* [ ] Adapters implementan Ports.
* [ ] Eliminar dependencias Domain → Infrastructure.
* [ ] Centralizar composición de dependencias.

---

# FASE 12 — Tests y calidad

## Unit Tests

* [ ] Tests del Domain sin infraestructura.
* [ ] Tests de Application usando mocks/fakes.
* [ ] Tests de routing.
* [ ] Tests de agentes.
* [ ] Tests de herramientas.
* [ ] Tests de memoria.
* [ ] Tests de permisos.

## Contract Tests

* [ ] Tests de `LLMPort`.
* [ ] Tests de `MemoryPort`.
* [ ] Tests de `VectorMemoryPort`.
* [ ] Tests de `ToolExecutorPort`.
* [ ] Tests de `AgentPort`.
* [ ] Tests de `CalendarPort`.

## Integration Tests

* [ ] SQLite.
* [ ] Ollama.
* [ ] Vector DB.
* [ ] Browser.
* [ ] Bridge.
* [ ] Calendar.
* [ ] Mail.

## API Tests

* [ ] Chat.
* [ ] Memory.
* [ ] Tools.
* [ ] Agents.
* [ ] Calendar.
* [ ] Mail.
* [ ] Security.

## Calidad

* [ ] Configurar Ruff/Flake8.
* [ ] Configurar Black o equivalente.
* [ ] Configurar MyPy/Pyright.
* [ ] Configurar pytest.
* [ ] Medir cobertura.
* [ ] Establecer cobertura mínima.
* [ ] Integrar linting en CI.
* [ ] Integrar type checking en CI.
* [ ] Integrar tests en CI.

---

# FASE 13 — Estructura arquitectónica objetivo

La estructura final aproximada debería ser:

```text
app/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   ├── services/
│   ├── agents/
│   └── ports/
│       ├── llm_port.py
│       ├── memory_port.py
│       ├── vector_memory_port.py
│       ├── tool_executor_port.py
│       ├── tool_registry_port.py
│       ├── agent_port.py
│       ├── calendar_port.py
│       ├── bridge_port.py
│       └── correction_log_port.py
│
├── application/
│   ├── chat/
│   ├── agents/
│   ├── tools/
│   ├── memory/
│   ├── calendar/
│   └── mail/
│
├── adapters/
│   ├── inbound/
│   │   └── http/
│   │       ├── chat.py
│   │       ├── agents.py
│   │       ├── tools.py
│   │       ├── memory.py
│   │       ├── calendar.py
│   │       └── mail.py
│   │
│   └── outbound/
│       ├── llm/
│       ├── memory/
│       ├── vector_memory/
│       ├── tools/
│       ├── calendar/
│       ├── mail/
│       └── filesystem/
│
├── infrastructure/
│   ├── config/
│   ├── database/
│   ├── logging/
│   └── dependency_injection/
│
└── main.py
```

---

# FASE 14 — Criterios finales de aceptación

La refactorización se considerará terminada cuando:

* [ ] `app/domain/` no importe `app.adapters`.
* [ ] `app/domain/` no dependa de FastAPI.
* [ ] `app/domain/` no dependa de Ollama.
* [ ] `app/domain/` no dependa de SQLite.
* [ ] Los endpoints HTTP no contengan lógica de negocio.
* [ ] Los casos de uso puedan probarse sin infraestructura real.
* [ ] Los adapters implementen Ports definidos por el núcleo.
* [ ] Añadir un nuevo proveedor LLM no requiera modificar Domain.
* [ ] Añadir un nuevo agente no requiera modificar el core del router.
* [ ] Añadir una nueva herramienta no requiera modificar Domain.
* [ ] Cambiar la persistencia no requiera modificar los casos de uso.
* [ ] La suite completa de tests pase.
* [ ] CI ejecute lint.
* [ ] CI ejecute type checking.
* [ ] CI ejecute tests.
* [ ] No existan ciclos arquitectónicos relevantes.
* [ ] La documentación refleje la arquitectura real.

---

# Orden recomendado de ejecución

No realizar una reescritura completa.

Cada fase debe mantener la funcionalidad existente y producir cambios pequeños, verificables y reversibles.

1. [ ] **FASE 0** — Tests y mapa de dependencias.
2. [ ] **FASE 1** — Dividir API.
3. [ ] **FASE 2** — Crear Application Layer.
4. [ ] **FASE 3** — Limpiar Domain.
5. [ ] **FASE 5** — Eliminar `Domain → Adapters`.
6. [ ] **FASE 6** — Dependency Injection.
7. [ ] **FASE 4** — Reducir `PlannerOrchestrator`.
8. [ ] **FASE 7** — Agent Registry.
9. [ ] **FASE 8** — Tool System.
10. [ ] **FASE 9** — LLM Adapter.
11. [ ] **FASE 10** — Memory/Persistence.
12. [ ] **FASE 11** — Auditoría SOLID.
13. [ ] **FASE 12** — Tests y CI.
14. [ ] **FASE 13** — Consolidar estructura.
15. [ ] **FASE 14** — Auditoría final.

---

# Regla de oro

> **No añadir nuevas funcionalidades grandes mientras se esté eliminando el acoplamiento arquitectónico.**

La prioridad es convertir AI Manager de:

```text
Prototipo avanzado
        ↓
Sistema modular
        ↓
Arquitectura Hexagonal
        ↓
Código SOLID
        ↓
Producto mantenible
```

La refactorización debe ser **incremental**, conservando la funcionalidad existente en cada etapa.

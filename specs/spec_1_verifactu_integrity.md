# SPEC 1 — Integridad del flujo crítico Veri*Factu

## Problem
Se han detectado dos vulnerabilidades críticas en el manejo de excepciones del servicio `verifactu_service.py` que comprometen la integridad fiscal:
1. **Identidad del Emisor (EXC-01):** El bloque que recupera la razón social del emisor captura todas las excepciones genéricas (`except Exception: pass`). Si falla la base de datos, se asume un emisor vacío o nulo.
2. **Registro de Eventos SIF (EXC-02):** El registro de auditoría (`log_sif_event`), utilizado durante la detección de manipulaciones criptográficas (tampering), suprime los fallos al escribir en BBDD.

## Evidence
- **EXC-01:** `app/domain/services/verifactu_service.py`, líneas 152-153.
- **EXC-02:** `app/domain/services/verifactu_service.py`, líneas 835-836 y 851-852.

## Scope
- `app/domain/services/verifactu_service.py` (método `validate_integrity` y generador de XML).

## Non-goals
- Introducir mecanismos nuevos de retries, background workers o colas que no estén ya presentes.
- Modificar el flujo asíncrono actual.
- Modificar tablas de base de datos.

## Current behavior
- Si la lectura de identidad (`razon_social`) falla, el sistema ignora el error, generando y enviando una factura a la AEAT que es inválida o pertenece a otro contexto.
- Si el registro de detección de alteraciones (SIF) falla al escribir en la BD, la validación se completa silenciosamente omitiendo el log legal.

## Expected behavior
- **Identidad (EXC-01):** La operación debe fallar ruidosamente si la identidad fiscal no se puede recuperar. No se genera XML, no se envía nada a la AEAT y no se altera el estado financiero/fiscal.
- **Contrato de fallo de auditoría SIF (EXC-02):**
  - *Contexto:* `log_sif_event` se ejecuta durante la auditoría de encadenamiento (`validate_integrity`), es decir, tras la generación y fuera del flujo de envío normal AEAT.
  - *Reejecución:* tras un fallo de escritura en la auditoría, la operación podrá reintentarse cuando la BBDD vuelva a estar disponible. La idempotencia de la reejecución NO se considera garantizada por este contrato y deberá verificarse mediante el comportamiento existente y tests específicos antes de declararla.

## Requirements
- Modificar `verifactu_service.py` para levantar `IssuerIdentityError` (EXC-01) si falla la obtención del `user_profile`.
- Modificar `verifactu_service.py` para levantar `SIFAuditWriteError` (EXC-02) si falla `log_sif_event`.
- Ninguno de los dos errores debe ser suprimido con un `pass`.

## Invariants
- NO se puede generar/enviar Veri*Factu si no se ha podido determinar de forma válida la identidad fiscal requerida (identidad es pre-requisito estricto).
- El error de escritura de un evento de tampering en el SIF no puede ocultarse; debe interrumpir el proceso que lo invocó.

## Acceptance criteria
- **EXC-01:** Si `_get_connection()` falla al inicio de la emisión:
  1. No se genera el archivo XML.
  2. No se envía petición a AEAT.
  3. No se cambian estados financieros.
  4. Se levanta la excepción trazable.
- **EXC-02:** Si falla el almacenamiento durante `validate_integrity`:
  1. La validación aborta con excepción.
  2. El error queda expuesto a los niveles superiores sin generar estados inconsistentes.

## Required tests
- Test de comportamiento observable para EXC-01 verificando que (a) lanza la excepción, (b) el payload XML no se construye, (c) el estado de la factura no cambia.
- Test de fallo para EXC-02 verificando que si la BD lanza error durante `log_sif_event`, la validación de integridad lanza `SIFAuditWriteError`.

## Dependencies
- Ninguna.

## Risks
- La facturación podría frenarse momentáneamente ante inestabilidades de BD, lo cual es el comportamiento fiscalmente responsable.

## Open questions
- Si `log_sif_event` aborta la auditoría de integridad, ¿quién recoge este error a nivel de aplicación (Cron, Worker) para alertar al administrador del sistema?

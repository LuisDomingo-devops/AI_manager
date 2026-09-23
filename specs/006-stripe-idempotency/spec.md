# Especificación: 006-stripe-idempotency

## Contexto

El sistema requiere saneamiento para asegurar que los tests reflejen la realidad y los fallos se reporten correctamente.

## Problema

Garantizar idempotencia en el webhook de Stripe y asegurar que no hay duplicación de eventos.

## Comportamiento actual

[Por definir durante la ejecución de la fase]

## Comportamiento esperado

[Fallar correctamente si la operación es inválida; testear funcionalidad real sin mockear el core si no es necesario]

## Requisitos funcionales

- Corregir producción.
- Añadir aserciones significativas a los tests asociados.

## Tests requeridos

- Tests de integración que fallen si la corrección se revierte.

## Archivos afectados

- [Por llenar]

# Especificación: 009-regulatory-verification

## Contexto

El sistema requiere saneamiento para asegurar que los tests reflejen la realidad y los fallos se reporten correctamente.

## Problema

Marcar funcionalidades Veri*Factu, AFI TGSS y AEAT sin probar contra fuentes oficiales reales como UNVERIFIED.

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

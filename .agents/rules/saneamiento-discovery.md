---
trigger: always_on
---

# Alfonso AI Konta — Saneamiento Discovery

Esta regla se aplica durante la fase de Discovery técnico del proyecto.

## Fuente de verdad

El contrato completo de Discovery está en:

@../../docs/audit/discovery-contract.md

Debe seguirse íntegramente.

## Restricciones críticas

- Durante Discovery NO modificar código de producción.
- Durante Discovery NO modificar tests.
- No inventar normativa, APIs, formatos fiscales ni comportamiento.
- No convertir incertidumbre en código.
- Todo hallazgo debe tener evidencia verificable.
- Los tests deben evaluarse por assertions reales, no por coverage.
- Los mocks globales que puedan ocultar bugs deben identificarse.
- Los proveedores que devuelvan datos ficticios deben identificarse.
- Los claims regulatorios deben clasificarse como VERIFIED, UNVERIFIED,
  CONFLICTING, INCORRECT o NOT_IMPLEMENTED.
- Las migraciones históricas no deben modificarse destructivamente sin
  determinar previamente su estado.
- Discovery termina con un informe auditable y especificaciones SpecKit.
- NO comenzar implementación hasta que Discovery esté aprobado.

## Regla principal

Durante Discovery:

REGISTER BUG → DO NOT FIX → DOCUMENT EVIDENCE

El objetivo no es mejorar el código todavía.

El objetivo es determinar con evidencia:

1. qué funciona;
2. qué no funciona;
3. qué está falsamente testeado;
4. qué está oculto por mocks;
5. qué está inventado o sin implementar;
6. qué no puede verificarse;
7. qué contratos están indefinidos;
8. qué debe corregirse y en qué orden.
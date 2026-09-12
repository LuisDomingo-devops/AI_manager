

# Implementation Plan: Consolidación Arquitectura y Conformidad VeriFactu (AEAT)

**Branch**: `001-verifactu-base-aeat` | **Date**: 2026-09-12 | **Spec**: [spec.md](file:///C:/Users/luisd/Desktop/Alfonso_Autonomo/specs/001-verifactu-base-aeat/spec.md)

**Input**: Feature specification from `/specs/001-verifactu-base-aeat/spec.md`

## Summary

Consolidación de la arquitectura base y tests de integración para implementar y verificar el sistema VeriFactu contra la AEAT utilizando TDD.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `lxml` (XML y C14N), `signxml` o `cryptography` (Firma XMLDSig), `httpx` (HTTP Client)

**Storage**: N/A (el almacenamiento se abordará en capas superiores, aquí se gestiona la lógica de serialización y envío).

**Testing**: `pytest`, `pytest-cov`, `responses` o `httpretty`

**Target Platform**: Linux/Windows/macOS (Multiplataforma)

**Project Type**: Python Library / CLI

**Performance Goals**: <500ms serialización y firma por factura.

**Constraints**: El entorno sandbox de AEAT debe ser contactable, certificado digital requerido.

**Scale/Scope**: Módulo núcleo (Core) para firma y envío.

## Constitution Check

*GATE: Passed.*
- **Desarrollo en Español**: Cumplido en la especificación y el plan.
- **TDD Estricto**: Abordado mediante `pytest` como eje del desarrollo.
- **Cobertura Completa**: Planificado en los tests unitarios e integración.
- **Registro de Tests**: Se usará el output de pytest para logs tras cada ejecución.

## Project Structure

### Documentation (this feature)

```text
specs/001-verifactu-base-aeat/
├── plan.md              # This file
├── research.md          # Decisiones de diseño y entorno
├── data-model.md        # Estructuras de datos
├── quickstart.md        # Guía de validación
└── tasks.md             # Tareas a implementar (fase 2)
```

### Source Code (repository root)

```text
app/
└── domain/
    └── services/
        ├── verifactu_service.py                      # Servicio principal e integración SIF
        └── ... (otros módulos del backend)

migrations/
└── versions/
    └── 012_verifactu_sif_canonical.py                 # Migración de base de datos canónica

tests/
└── backend/
    ├── integration/
    │   ├── test_verifactu.py                         # Test de integración VeriFactu
    │   ├── test_verifactu_anulacion.py               # Test de anulación de facturas
    │   ├── test_verifactu_integrity.py               # Test de integridad del ledger
    │   ├── test_verifactu_real_soap.py               # Test de conexión SOAP AEAT real
    │   ├── test_verifactu_sif_migration_integration.py # Test de migración SIF
    │   └── ... (resto de tests de integración del sistema)
    ├── qa/
    │   └── ... (suites avanzadas y de estrés de VeriFactu)
    └── unit/
        └── test_verifactu_schema_and_endpoint_unit.py # Test unitario de esquemas y endpoints
```

**Structure Decision**: Integración limpia en la arquitectura hexagonal/capas del proyecto existente, reutilizando `app/domain/services/verifactu_service.py` como núcleo SIF canónico y expandiendo la suite robusta en `tests/backend/`.

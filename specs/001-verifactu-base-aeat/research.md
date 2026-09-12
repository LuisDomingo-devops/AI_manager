# Research & Technical Decisions: VeriFactu Base

## Decision 1: Lenguaje y Entorno
- **Decision**: Python 3.11+
- **Rationale**: Es el lenguaje estándar de facto para herramientas AI Manager y scripts de este tipo.
- **Alternatives considered**: N/A (el entorno local asume Python para scripts).

## Decision 2: Librería XML y Firma
- **Decision**: `lxml` para XML y `signxml` (o `cryptography` directa) para XMLDSig/Hash.
- **Rationale**: VeriFactu requiere firmar y generar XML estricto. `lxml` soporta canonicalización requerida por firmas XML.
- **Alternatives considered**: `xml.etree` (rechazado por no soportar bien canonicalización C14N out-of-the-box).

## Decision 3: Framework de Testing (TDD)
- **Decision**: `pytest` con `pytest-cov` y `responses` o `httpretty`.
- **Rationale**: Cumple la Constitución del proyecto (TDD, tests unitarios y de integración, reporte de logs). `pytest` permite fixtures para certificados de prueba y simular la AEAT fácilmente.
- **Alternatives considered**: `unittest` (rechazado por ser más verboso y tener ecosistema de plugins más pequeño).

## Decision 4: Cliente HTTP
- **Decision**: `httpx`
- **Rationale**: Permite cargar certificados cliente fácilmente y tiene una API asíncrona por si escala, aunque síncrona basta de momento.
- **Alternatives considered**: `requests` (válido, pero `httpx` es más moderno).

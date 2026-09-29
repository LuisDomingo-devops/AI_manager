# Plan de Implementación: 011-security-and-credential-hygiene

## Arquitectura y Componentes Afectados

1. **Configuración Global (`app/config.py`)**:
   - Asignar `Field(default="", repr=False)` al atributo `ALFONSO_CLIENT_TOKENS`.
2. **Sistema de Logging (`app/utils/logger.py`)**:
   - Implementar `CredentialSanitizingFilter(logging.Filter)`.
   - Añadir expresiones regulares para enmascarar `Bearer ...`, `password=...`, `api_key=...`, `secret=...`.
   - Adjuntar el filtro a todos los handlers en `build_logger`.
3. **Servicio de Autenticación (`app/domain/services/auth_service.py`)**:
   - Actualizar `_create_access_token` usando `datetime.now(timezone.utc)`.

## Fases TDD
- **Fase 1 (RED)**: Tests unitarios e integrados que demuestran que `repr(settings)` expone tokens y que logs sin filtrar exponen secretos.
- **Fase 2 (GREEN)**: Corrección en `app/config.py`, `app/utils/logger.py` y `app/domain/services/auth_service.py`.
- **Fase 3 (QA)**: Suite de auditoría de seguridad y sanitización de credenciales.
- **Fase 4 (Regresión)**: Suite completa de backend y commit.

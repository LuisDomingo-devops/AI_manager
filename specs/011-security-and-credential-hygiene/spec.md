# Especificación de Requisitos: 011-security-and-credential-hygiene

## Resumen Ejecutivo

Conforme a las directrices de seguridad y pentesting (`docs/security_audit_report.md` y `docs/INFORME_AUDITORIA_SEGURIDAD_Y_PENTEST.md`):
1. **Ocultación de Secretos en Configuración**: Todos los campos que contengan credenciales o tokens en `app/config.py` (`ALFONSO_CLIENT_TOKENS`, `ALFONSO_API_KEY`, etc.) deben tener `repr=False` para evitar fugas inadvertidas en trazas y volcados de configuración.
2. **Sanitización de Logs**: Ningún logger del sistema debe volcar en texto claro contraseñas, tokens JWT, cabeceras `Authorization: Bearer` o secretos de API. Se implementará `CredentialSanitizingFilter` en `app/utils/logger.py`.
3. **Hardening de Tiempos y Criptografía**: Reemplazar métodos deprecados como `datetime.utcnow()` por `datetime.now(timezone.utc)` para garantizar precisión temporal y compatibilidad futura con Python 3.12+.

---

## Criterios de Aceptación (Gherkin)

### Escenario 1: Ocultación de tokens en la representación de Settings
**Dado** un objeto `Settings` con `ALFONSO_CLIENT_TOKENS` configurado con tokens sensibles,  
**Cuando** se obtiene la representación de texto `repr(settings)`,  
**Entonces** el contenido de los tokens no debe aparecer en claro en la cadena devuelta.

### Escenario 2: Sanitización automática de credenciales en logs
**Dado** un mensaje de log que contiene un token `Bearer secret-token-1234` o un parámetro `password=supersecret`,  
**Cuando** el mensaje es procesado por los handlers del logger,  
**Entonces** el texto emitido debe enmascarar los valores confidenciales con `[REDACTED]`.

### Escenario 3: Generación de tokens JWT sin advertencias horarias
**Dado** el servicio `AuthService`,  
**Cuando** se crea un access token para un usuario,  
**Entonces** la fecha de expiración debe ser generada con `timezone.utc` sin emitir `DeprecationWarning`.

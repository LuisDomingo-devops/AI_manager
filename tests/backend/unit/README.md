# Pruebas Unitarias (Unit Tests)

Este directorio contiene las pruebas unitarias de Alfonso Autónomo. El objetivo principal de las pruebas unitarias es verificar el correcto funcionamiento de las funciones, clases, utilidades y componentes del sistema de forma **completamente aislada**, abstrayendo cualquier tipo de entrada/salida externa (como bases de datos físicas, llamadas de red reales o interacción directa con el sistema operativo) mediante el uso de mocks y stubs.

## ¿Qué se testea en esta carpeta?

Las pruebas unitarias de este directorio cubren los siguientes módulos esenciales:

1. **Configuración y Rutas del Sistema**:
   - [`test_config.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_config.py): Validación del tipado, carga y consistencia de las variables de entorno configuradas a través de Pydantic Settings.
   - [`test_paths.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_paths.py): Comprobación del correcto mapeo e integridad de las rutas físicas del sistema y los directorios de datos.

2. **Seguridad y Criptografía**:
   - [`test_anonymizer.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_anonymizer.py): Verificación del procesador de anonimización de datos sensibles y personales (GDPR).
   - [`test_encryption_keyring.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_encryption_keyring.py): Pruebas de la capa criptográfica para el almacenamiento cifrado de datos sensibles mediante claves simétricas y asimétricas locales.
   - [`test_cloudflare_proxy.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_cloudflare_proxy.py): Pruebas unitarias de las reglas y cabeceras de proxy seguro.

3. **Arquitectura y Mecanismos de Alfonso**:
   - [`test_tool_base.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_tool_base.py) y [`test_tool_registry.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_tool_registry.py): Verificación del ciclo de registro, tipado y parámetros de las herramientas del agente AI.
   - [`test_optimizations.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_optimizations.py) y [`test_production_failfast.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_production_failfast.py): Pruebas unitarias sobre mecanismos de parada temprana (*fail-fast*) y optimizaciones de rendimiento y caché.
   - [`test_metrics.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_metrics.py) y [`test_logger_safe_rotation.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_logger_safe_rotation.py): Validación de la rotación segura de logs y almacenamiento de telemetría sin fuga de descriptores.

4. **Lógica de Integridad de Facturas (Veri*Factu)**:
   - [`test_verifactu_schema_and_endpoint_unit.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_verifactu_schema_and_endpoint_unit.py): Comprobación del formato XML y el esquema SOAP requerido por la AEAT antes de la firma.

5. **Pruebas de Estrés Unitarias**:
   - [`test_unit_stress.py`](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/tests/unit/test_unit_stress.py): Validación aislada del comportamiento de las clases utilitarias de estrés (`StressPerformanceMonitor` y `StressDataGenerator`).

---

## Cómo ejecutar las pruebas unitarias

Para ejecutar únicamente los tests de este directorio:
```powershell
pytest tests/unit/
```

# 🔒 CARPETA PRIVADA DEL FABRICANTE (NO DISTRIBUIR)

Esta carpeta contiene las herramientas exclusivas del desarrollador / empresa comercializadora para la emisión de licencias criptográficas y el control de suscripciones.

## ⚠️ Regla de Seguridad Absoluta
**ESTA CARPETA NUNCA DEBE INCLUIRSE EN EL INSTALADOR (.EXE) NI EN EL PAQUETE ENTREGADO AL CLIENTE.**

El script de compilación [build_executable.py](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/build_executable.py) ignora y excluye automáticamente `admin_tools_private/` del binario compilado.

---

## 🛠️ Herramientas Incluidas

1. **`license_issuer.py`**:
   * Generador con la clave privada RSA maestra (`DEFAULT_MASTER_PRIVATE_KEY_PEM`).
   * Emite licencias de pago mensuales y pruebas gratuitas de 14 días ligadas al `machine_fingerprint` del usuario.

2. **`license_admin_cli.py`**:
   * Herramienta de línea de comandos para emitir licencias de forma manual:
   ```bash
   python license_admin_cli.py issue --holder "Pedro Perez" --client-id "pedro_01" --machine-fp "ALF-MACH-XXXX" --months 1
   python license_admin_cli.py trial --holder "Ana Gomez" --machine-fp "ALF-MACH-YYYY" --days 14
   python license_admin_cli.py transfer --license-file "license.lic" --new-machine-fp "ALF-MACH-ZZZZ"
   ```

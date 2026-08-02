# CONTEXTO DEL PROYECTO Y REGLAS DE DESARROLLO: ALFONSO AUTÓNOMO

Este documento define la base, la arquitectura, el enfoque de negocio y las reglas de ingeniería para llevar a cabo de manera eficiente la ramificación **Alfonso Autónomo**.

---

## 1. Misión y Foco del Producto
*   **Qué es Alfonso Autónomo:** Un asistente virtual de IA local que ayuda a autónomos y freelances en España a preparar y automatizar sus trámites fiscales y facturación de forma asíncrona y segura.
*   **El Enfoque "One-Click / Pre-Trámite":** Alfonso NO presenta impuestos por sí solo ni firma documentos finales sin el usuario. Alfonso hace todo el trabajo pesado en segundo plano (leer facturas, rellenar borradores de modelos del portal de Hacienda) y el usuario realiza el último click de aprobación en el navegador. Esto evita responsabilidades legales directas de la IA y zonas grises regulatorias.
*   **Verifactu (AEAT 2027):** El software debe orientarse a cumplir técnicamente con la nueva legislación de facturación electrónica inalterable y encadenamiento criptográfico local.

---

## 2. Arquitectura de Privacidad (Local-First)
*   **Despliegue Local:** Alfonso corre en local en la máquina del autónomo (GUI en PyQt/PySide + backend local y bases de datos SQLite/ChromaDB).
*   **Manejo de Credenciales:** Los certificados digitales e inicios de sesión del portal de la AEAT nunca salen del equipo del usuario. Alfonso interactúa localmente con la sesión del navegador abierta del usuario.
*   **Inferencia Híbrida Inteligente:** 
    *   La extracción de datos y el parseo de PDFs sensibles se realiza localmente usando modelos ligeros de visión/OCR o parsers estructurados.
    *   Para la inferencia compleja de razonamiento (tool-calls) con APIs externas, se implementa una **tokenización/anonimización local** (sustituir NIFs, nombres e importes por tokens como `NIF_CLIENTE_1`) antes de enviar el payload al LLM central en la nube.

---

## 3. Criterios de Código (SOLID & Clean Architecture)
1.  **Responsabilidad Única (SRP):** Mantener el orquestador (`PlannerOrchestrator`) como un coordinador limpio. Los módulos específicos (Marcos para legislación, conectores a AEAT, WAF de seguridad) deben ser clases aisladas y autocontenidas.
2.  **Inversión de Dependencias (DIP):** Las conexiones con bases de datos y clientes de APIs deben depender de interfaces/puertos abstractos en `app.domain.ports`, facilitando la transición entre Ollama local y APIs externas.
3.  **Seguridad Sandboxing:** La ejecución del software se restringe obligatoriamente a directorios permitidos. Las llamadas a comandos del sistema del `DevAgent` deben migrar a listas blancas de ejecución en contenedores aislados.

---

## 4. Reglas de Desarrollo y Workflow en Antigravity
*   **Pruebas unitarias estrictas:** Validar localmente los parsers de modelos de IVA (Modelo 303, Modelo 130) con conjuntos de datos de prueba inalterables en `tests/`.
*   **Campañas en Público (LinkedIn):** Documentar la evolución técnica del "Build in Public" con pequeñas demostraciones sin datos personales (usando datos ficticios en las demos en vídeo del navegador).

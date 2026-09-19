---
title: Alfonso Ai Konta
---

# Alfonso Autónomo 

> **"El asistente inteligente definitivo para el autónomo español: Privado, Seguro y Legal."**

## 1. Filosofía y Postulados del Proyecto

Alfonso nace bajo una premisa clara: **liberar al autónomo de la carga burocrática y tecnológica**, ofreciendo un sistema inteligente que opera de manera autónoma pero bajo el control total del usuario. Los postulados que rigen su diseño son:

1. **Soberanía y Privacidad del Dato (Privacy by Design):** Los datos financieros de un autónomo son críticos. El sistema está diseñado para funcionar en entornos **On-Premise** (locales) mediante un modelo *multi-tenant* aislado. Cada cliente tiene su propia base de datos SQLite independiente, garantizando que no haya fuga de información entre cuentas.
2. **Seguridad Proactiva y Robusta:** No basta con proteger el perímetro; el sistema debe autodefenderse. Alfonso integra un agente de ciberseguridad autónomo que monitoriza en tiempo real anomalías, bloquea atacantes e inspecciona el propio código del sistema.
3. **Cumplimiento Normativo sin Fricción:** El marco legal español (AEAT, Veri*Factu, LGT) es complejo. Alfonso encapsula esta complejidad generando facturas inmutables, firmadas digitalmente y listas para ser reportadas, asegurando que el usuario esté siempre dentro de la legalidad sin tener que ser un experto fiscal.
4. **Minimalismo Arquitectónico:** Menos es más. En lugar de depender de pesados frameworks orquestadores de memoria, Alfonso utiliza un modelo de estado efímero (Stateless Tool Engine) y delegación asíncrona mediante FastAPI, haciéndolo extremadamente rápido y fácil de desplegar.

---

## 2. Intención del Proyecto

La intención detrás de Alfonso no es ser un simple "chatbot". Es un **sistema de automatización fiscal y empresarial** con una interfaz conversacional (voz y texto). El objetivo es que el usuario pueda decir: *"Alfonso, emite una factura a este cliente por 500 euros"* y el sistema se encargue de:
- Verificar el estado de la licencia.
- Identificar la base de datos del usuario.
- Generar el XML de la factura.
- Calcular y encadenar el hash SHA-256 previo (requisito antifraude).
- Firmar el documento electrónicamente (XAdES-BES).
- Generar el código QR de Veri*Factu.

---

## 3. Arquitectura y Descripción Técnica Profunda

El sistema sigue los principios de la **Arquitectura Hexagonal (Puertos y Adaptadores)**, separando estrictamente la lógica de dominio de las interfaces externas.

### 3.1 Diagrama de Flujo

                ┌─────────────────────┐
                │   FASTAPI CORE      │
                │  (ligero, async)    │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ PLANNER ORCHESTRATOR│
                │  (Enrutador y RAG)  │
                └─────────┬───────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ TOOL ENGINE  │  │ MEMORY LITE  │  │ EVENT QUEUE  │
│ (Stateless)  │  │ SQLite Tenant│  │ (Asyncio)    │
└──────────────┘  └──────────────┘  └──────────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │  LLM CLIENT LAYER   │
                │    (Gemini API)     │
                └─────────┬───────────┘

### 3.2 Componentes a Bajo Nivel

#### A. Core API (FastAPI)
- **Middleware WAF:** Un firewall de aplicación web nativo inspecciona cada petición HTTP entrante. Decodifica las URLs (hasta 3 niveles) y limpia comentarios nulos para evitar técnicas de evasión.
- **Rutas Aisladas:** Divididas lógicamente (`/audio`, `/security`, `/webhook`, `/ws`). 

#### B. Orquestador Lógico (`PlannerOrchestrator`)
- No retiene estado en memoria para evitar cuellos de botella y fugas de memoria.
- Actúa como un evaluador semántico: analiza la intención del texto o comando del usuario y lo deriva al Agente Especialista adecuado (por ejemplo, si detecta la palabra "ciberseguridad", delega el control al `CyberSecurityAgent`).

#### C. Agente de Ciberseguridad (`CyberSecurityAgent`)
- **Protección Activa (WAF):** Emplea expresiones regulares compiladas para abortar en tiempo real inyecciones SQL (`UNION SELECT`, `DROP TABLE`), Command Injection (`&& bash`, `subprocess`) y Path Traversal (`../../`).
- **Rate Limiting (Anti-DDoS):** Control en memoria (máx. 100 peticiones por minuto por IP); excederlo provoca la adición inmediata de la IP a una `blocked_ips` de lista negra en caliente.
- **Monitoreo en Segundo Plano:** Tarea de `asyncio` que se ejecuta cada 120 segundos escaneando:
  - Archivos de configuración (`.env`) en busca de contraseñas débiles o valores por defecto.
  - Entornos de desarrollo (`sandbox`) detectando funciones peligrosas habilitadas (`eval()`, `exec()`).
  - Logs del sistema para identificar picos anómalos de errores (ej. `Exception`).

#### D. Motor de Cumplimiento Legal y Veri*Factu
- **Inmutabilidad y Antifraude:** Implementa el estándar técnico de la AEAT (Orden HAC/1177/2024). Cada factura genera una huella criptográfica exacta (ID, Fecha, Tipo, Cuotas) encadenada a la anterior, creando una cadena criptográfica irrompible (blockchain local).
- **Firma Electrónica (XAdES-BES):** Integración de bibliotecas de bajo nivel para generar firmas XML avanzadas (XAdES-BES) que certifican la autenticidad del documento con un certificado X.509/FNMT, cumpliendo estrictamente con el formato oficial de la AEAT.
- **Declaraciones Dinámicas:** Generador en tiempo real de la "Declaración Responsable" en formato PDF requerido por la normativa de Sistemas Informáticos de Facturación (SIF).

#### E. Motor de Memoria (`Memory Lite`)
- **Aislamiento Multi-Tenant:** Basado en SQLite. Al momento del login, el sistema monta la base de datos específica del cliente (`memory_{tenant_id}.db`).
- Las migraciones y estructuras de tablas se gestionan de manera programática, preparadas para un entorno sin concurrencia masiva cruzada.

#### F. Capacidades de Audio y Procesamiento Multimedia
- **TTS (Text-to-Speech):** Utiliza `edge-tts` como backend principal asíncrono, con retroceso automático (fallback) a `pyttsx3` para operar completamente offline si no hay red.
- **STT (Speech-to-Text):** Transcripción de comandos de voz mediante el motor `Whisper`, garantizando alta fidelidad.
- **Wakeword:** Motor de detección continua para permitir al usuario iniciar comandos con la voz (manos libres).

#### G. Licenciamiento y Facturación Integrada
- **Modelo On-Premise:** Utiliza criptografía asimétrica (RSA). El cliente provee una licencia que se descifra contra una clave pública, validando caducidad y módulos contratados de manera offline.
- **Modelo Híbrido (Stripe):** Endpoint específico de webhooks (`/webhook/stripe`) que verifica las firmas criptográficas de Stripe (`stripe-signature`) e implementa llaves de idempotencia para procesar altas, bajas o impagos de suscripciones.

#### H. Módulos de Negocio Avanzados Integrados
- **Contabilidad PGC:** Motor contable completo adaptado al Plan General Contable (PGC) español, con generación automática de asientos y conciliación.
- **Nóminas y TGSS:** Gestión de recursos humanos con generación de nóminas, seguros sociales (ficheros AFI/CRA para TGSS) y modelos fiscales.
- **Open Banking PSD2:** Sincronización bancaria automatizada con soporte multi-proveedor para reconciliación de movimientos bancarios en tiempo real.
- **Presupuestos y Cotizaciones:** Ciclo completo de ventas desde la cotización y presupuesto hasta la conversión en factura firme.
- **Facturae B2B:** Integración completa para el intercambio electrónico de facturas estructuradas B2B (Facturae) entre empresas según la Ley Crea y Crece.
- **Cliente Gráfico (PyQt6):** Interfaz gráfica de usuario multiplataforma desarrollada en PyQt6 que permite una interacción visual rica y robusta.

---

## 4. Estructura de Observabilidad (Logs)

Alfonso implementa un trazado exhaustivo diseñado para la depuración y auditoría forense:
- `app.log`: Flujo de red general y operaciones de la API.
- `orchestrator.log`: Registro de decisiones de inferencia del LLM y derivaciones entre agentes.
- `cybersecurity.log`: Alertas, detecciones heurísticas e intentos de intrusión documentados por IP y payload.
- `errors.log`: Recolección centralizada de excepciones para que el Agente de Seguridad las evalúe en segundo plano.
- *Traceability:* Se asigna un UUID a cada transacción HTTP, el cual se propaga por todo el sistema y archivos de registro.

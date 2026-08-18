# 🛣️ Roadmap: SES Core

## 🧭 Visión del Producto (Product North Star)
**SES Core** persigue una operación offline-first para aplicaciones de
inteligencia artificial privadas y controladas por el operador. La meta es un
motor RAG modular, trazable y rápido; las garantías de aislamiento, escala y
disponibilidad deben demostrarse con pruebas reales antes de tratarlas como
propiedades de producción.

---

## 🎯 Fase 1: Estabilización del Núcleo RAG (En validación)
- [x] Migración hacia una arquitectura pura de librería (`ses-core`).
- [x] Desacoplamiento total de dependencias web (FastAPI/Uvicorn pasan a ser opcionales `[server]`).
- [x] Integración de `SentenceTransformers` y soporte estricto para modelos locales (Ollama).
- [x] Pruebas de rendimiento y automatización CI/CD de benchmarks en GitHub Actions.
- [x] Aceleración híbrida en Rust (`jas_vector_core`) con wheel CPython 3.12, pruebas unitarias y ruta NumPy sin copia.
- [x] CI verde para Portal, Python, Rust, wheel, Pytest y smoke sintético.
- [ ] Cerrar pruebas de integración reales y paridad local/Docker antes de declarar estable el núcleo.

## 🗂️ Fase 2: Mount Mode & Filesystem (Actual)
- [x] Implementación de **Mount Mode**: Indexación asíncrona de grandes repositorios en modo de solo lectura.
- [x] Watcher robusto basado en `watchdog` con debounce y checkpoints incrementales.
- [x] Soporte para múltiples formatos: PDF, DOCX, XLSX, TXT, MD, CSV.
- [x] Hacer recuperable el reindexado conservando y reintentando limpiezas pendientes.
- [ ] Optimización de memoria para el escaneo inicial de repositorios masivos (> 60 GB).
- [ ] Conectores para orígenes de datos locales y compartidos (e.g., SMB/CIFS).

## 🧠 Fase 3: RAG Cognitivo & Enterprise Features (En Desarrollo)
- [x] **Cognitive Re-Ranking:** Sistema de scoring híbrido integrado (similitud + recencia + uso).
- [x] **Caching Asíncrono:** TTL Caching con Redis para evitar re-cómputos de inferencia innecesarios.
- [x] **Generación de Reportes PDF:** Módulo exportable de auditoría técnica.
- [x] **Multi-Agent Orchestration:** Abstracciones para conectar SES Core con frameworks de agentes (LangGraph, CrewAI).
- [x] **RBAC Interno:** Controles de acceso basados en roles inyectados directamente en los metadatos de Qdrant.

## 🌍 Fase 4: Ecosistema y Adopción (Productización en curso)
- [x] Portal administrativo Next.js conectado a los contratos reales del Gateway y validado con lint/build.
- [x] Workflow manual que construye y verifica sdist/wheel sin publicar.
- [ ] Automatizar pruebas E2E del portal contra un stack local reproducible.
- [ ] Configurar PyPI Trusted Publisher y validar una publicación pública antes de declarar distribución continua.
- [ ] **Bindings Oficiales:** Wrappers para Node.js y Go consumiendo el núcleo de alto rendimiento.
- [ ] **SES Enterprise:** Oferta corporativa con SLAs garantizados y cumplimiento de cumplimiento normativo (HIPAA / GDPR).

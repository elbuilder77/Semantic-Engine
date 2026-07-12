# 🛣️ Roadmap: SES Core

## 🧭 Visión del Producto (Product North Star)
**SES Core** se posiciona como el estándar de oro para la creación de aplicaciones **100% Offline-First de Inteligencia Artificial**.
Nuestro objetivo es proveer a la comunidad de desarrolladores de un motor RAG (*Retrieval-Augmented Generation*) extremadamente rápido, modular y con garantías absolutas de privacidad (Zero Data Leakage).

---

## 🎯 Fase 1: Estabilización del Núcleo RAG (Completado ✅)
- [x] Migración hacia una arquitectura pura de librería (`ses-core`).
- [x] Desacoplamiento total de dependencias web (FastAPI/Uvicorn pasan a ser opcionales `[server]`).
- [x] Integración de `SentenceTransformers` y soporte estricto para modelos locales (Ollama).
- [x] Pruebas de rendimiento y automatización CI/CD de benchmarks en GitHub Actions.
- [x] Aceleración híbrida en Rust (`jas_vector_core`) para búsqueda por similitud de coseno.

## 🗂️ Fase 2: Mount Mode & Filesystem (Actual)
- [x] Implementación de **Mount Mode**: Indexación asíncrona de grandes repositorios en modo de solo lectura.
- [x] Watcher robusto basado en `watchdog` con debounce y checkpoints incrementales.
- [x] Soporte para múltiples formatos: PDF, DOCX, XLSX, TXT, MD, CSV.
- [ ] Optimización de memoria para el escaneo inicial de repositorios masivos (> 60 GB).
- [ ] Conectores para orígenes de datos locales y compartidos (e.g., SMB/CIFS).

## 🧠 Fase 3: RAG Cognitivo & Enterprise Features (En Desarrollo)
- [x] **Cognitive Re-Ranking:** Sistema de scoring híbrido integrado (similitud + recencia + uso).
- [x] **Caching Asíncrono:** TTL Caching con Redis para evitar re-cómputos de inferencia innecesarios.
- [x] **Generación de Reportes PDF:** Módulo exportable de auditoría técnica.
- [ ] **Multi-Agent Orchestration:** Abstracciones para conectar SES Core con frameworks de agentes (LangGraph, CrewAI).
- [ ] **RBAC Interno:** Controles de acceso basados en roles inyectados directamente en los metadatos de Qdrant.

## 🌍 Fase 4: Ecosistema y Adopción (Futuro)
- [ ] **Publicación Continua en PyPI** y gestión de releases automatizadas con Trusted Publishers.
- [ ] **Bindings Oficiales:** Wrappers para Node.js y Go consumiendo el núcleo de alto rendimiento.
- [ ] **SES Enterprise:** Oferta corporativa con SLAs garantizados y cumplimiento de cumplimiento normativo (HIPAA / GDPR).

<div align="center">
  <h1>🧠 SES Core: Semantic Engine</h1>
  <p><strong>La librería RAG definitiva para aplicaciones de Inteligencia Artificial 100% Offline y Privadas.</strong></p>
  
  [![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
  [![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
  [![Offline First](https://img.shields.io/badge/Network-0%20Dependencies-red.svg)](#)
  
  [![SES Core](https://img.shields.io/badge/🧠_SES_CORE-SEMANTIC_ENGINE-00D9FF?style=for-the-badge&labelColor=0F1B3C)](https://github.com/JPatronC92/SES)
  
  *Read this in [English](README_en.md)*
</div>

---

## 🌟 ¿Por qué SES Core?

Si estás construyendo aplicaciones de **Inteligencia Artificial Local** (con Ollama, LM Studio o Llama.cpp) y necesitas un motor RAG (*Retrieval-Augmented Generation*) que garantice **cero fugas [...]

Las librerías tradicionales (LangChain, LlamaIndex) están diseñadas pensando en la nube (OpenAI, Pinecone), haciéndolas pesadas y difíciles de aislar. **SES Core nace con una filosofía diame[...]

* 🔒 **Privacidad Total:** Cero llamadas a internet. Todo el procesamiento de embeddings y LLM ocurre en tu hardware local.
* ⚡ **Ultra Rápido:** Optimizada para baja latencia (Búsqueda vectorial en `~1.5 ms`).
* 📁 **Mount Mode Automático:** Incluye un *Watcher* que vigila tus carpetas locales (PDFs, DOCX, XLSX) y las indexa incrementalmente en segundo plano.
* 🧩 **Extremadamente Modular:** Úsala en scripts de CLI, aplicaciones de escritorio (PyQt) o como el motor interno de tu propia API.
* 🚀 **Re-Ranking y Batch Search:** Capacidades avanzadas integradas listas para producción.

---

## 🚀 Benchmarks de Rendimiento

SES Core está construido para ser rápido, utilizando procesamiento matricial optimizado y operaciones asíncronas para no bloquear tus aplicaciones.

| Operación | Rendimiento Promedio | Notas |
|-----------|----------------------|-------|
| **Throughput de Chunking Semántico** | `> 190,000 KB/s` | Capaz de segmentar miles de páginas de texto en milisegundos. |
| **Búsqueda Vectorial (1,000 Docs)** | `~ 1.5 ms` | Medido usando Qdrant en memoria o Numpy puro. |
| **Aceleración Híbrida Rust** | `Opcional` | El núcleo base puede extenderse mediante un módulo PyO3 (C++) para cargas empresariales. |

---

## 🔒 Privacidad y Seguridad

Construir con SES Core significa **Garantía de Cero Fugas (Zero Data Leakage)**:
- **Procesamiento de Embeddings Local:** Utilizamos `SentenceTransformers` ejecutándose en tu propia CPU/GPU. Tus documentos nunca viajan a servidores de HuggingFace.
- **Lógica LLM Aislada:** El `LocalLLMProvider` se conecta mediante sockets locales (`localhost:11434`) a Ollama. 
- **Filtrado de Metadatos:** En fase de almacenamiento, todo texto o metadato excluido no se almacena en variables indexadas para prevenir fugas accidentales durante búsquedas.

---

## 📦 Instalación

**Paso 1:** Instalar la librería base (incluye dependencias de Qdrant y Redis)
```bash
pip install ses-core
```

*(Opcional)* Si necesitas construir una API web encima de SES Core, instala las dependencias de servidor (FastAPI, Uvicorn):
```bash
pip install ses-core[server]
```

---

## ⚙️ Configuración y Requisitos de Producción

SES Core requiere que configures ciertas variables de entorno para funcionar en producción. Puedes usar un archivo `.env` o exportarlas en tu terminal:

```env
# MODO DEBUG (True deshabilita verificaciones de contraseñas, ideal para dev local)
DEBUG=True

# QDRANT (Obligatorio en producción para persistencia de vectores)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=tu_api_key_secreta

# REDIS (Obligatorio para caching asíncrono y rate limiting en producción)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=tu_password_secreto
```

**Nota Importante:** Si `DEBUG=True`, SES intentará conectarse a instancias locales de Qdrant y Redis sin contraseña.

---

## 💻 Guía Rápida (Quickstart)

Construir una aplicación de conocimiento en 3 pasos:

### 1. Requisitos Previos e Inicialización

**¡Importante!** Aunque SES Core es 100% offline y no llama a APIs en la nube, la librería delega el almacenamiento vectorial y el rate limiting en servicios altamente optimizados. **Debes tener[...]

Ejemplo con Docker para arrancar la infraestructura requerida:
```bash
docker run -d -p 6333:6333 qdrant/qdrant
docker run -d -p 6379:6379 redis
```

Luego, puedes iniciar tu aplicación de Python:

```python
import asyncio
from ses.core.rag import OfflineRAGEngine
from ses.core.llm import LocalLLMProvider

async def main():
    # Inicializa el motor vectorial local (Qdrant + Redis caching)
    engine = OfflineRAGEngine()
    
    # Inicializa la conexión con Ollama (100% offline)
    llm = LocalLLMProvider(model_override="llama3")
```

### 2. Indexación "Drop-in" de Documentos

SES Core soporta extracción automática de `PDF`, `DOCX`, `TXT` y `XLSX`.

```python
    # Ingestar un documento confidencial
    with open("contrato_confidencial.pdf", "rb") as f:
        resultado = await engine.ingest_file(
            namespace="legal", 
            file_obj=f, 
            filename="contrato_confidencial.pdf", 
            metadata={"autor": "Abogado"}
        )
    print(f"Indexado exitosamente: {resultado['chunks_count']} fragmentos semánticos.")
```

### 3. Búsqueda y Generación de Respuestas

```python
    # Recupera los fragmentos con mayor similitud de coseno
    resultados = await engine.search(
        namespace="legal", 
        query="¿Cuáles son las cláusulas de rescisión del contrato?"
    )

    # Genera una respuesta sintética usando la IA local
    respuesta = llm.generate_answer(
        query="Explica las cláusulas de rescisión en base al documento.", 
        context_docs=resultados["results"]
    )

    print(respuesta)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🏗️ Arquitectura y Componentes Avanzados

SES Core es altamente hackeable e incluye características Enterprise de fábrica:
- **PDF Report Generation:** Usa `ses.core.reports` para exportar analíticas.
- **Cognitive Re-Ranking:** Reevaluación de scores en el motor `rag.py`.
- **TTL Caching:** Caché a nivel de método (Redis) para respuestas instantáneas.

```text
ses/
├── core/
│   ├── parsers.py       # Algoritmos de extracción (PDF, DOCX, XLSX, TXT)
│   ├── chunking.py      # Segmentación semántica inteligente
│   ├── embeddings.py    # Envoltura de modelos HuggingFace locales
│   ├── vector_store.py  # Abstracción asíncrona (Qdrant)
│   ├── llm.py           # Proveedores sin conexión (Ollama)
│   ├── reports.py       # Generación de reportes PDF avanzados
│   └── rag.py           # El orquestador principal con Re-ranking
├── watcher/
│   └── monitor.py       # Observabilidad de sistemas de archivos (Watchdog)
└── config.py            # Variables de entorno estáticas y secret management
```

---

## 📚 Documentación Adicional

Para integraciones más complejas, guías paso a paso de despliegue y documentación de la API interna, por favor visita nuestra [Wiki Oficial en GitHub](https://github.com/JPatronC92/SES/wiki).

---

## 📈 Monetización y Enterprise

SES opera bajo un modelo **Open Core**. 
Esta librería (`ses-core`) representa nuestro "Nivel 1" y siempre será **gratuita, open-source y libre de tracking** (GPLv3) para la comunidad de desarrolladores de IA local.

Para corporativos o infraestructuras masivas que requieran **SaaS Managed, Despliegues On-Premise con controles RBAC, o SLAs garantizados**, ofrecemos paquetes *SES Enterprise*. Contáctanos para[...]

<div align="center">
  <h1>🧠 SES Core: Semantic Engine</h1>
  <p><strong>The definitive RAG library for 100% Offline and Private Artificial Intelligence applications.</strong></p>
  
  [![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
  [![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
  [![Offline First](https://img.shields.io/badge/Network-0%20Dependencies-red.svg)](#)
  
  *Read this in [Spanish (Español)](README.md)*
</div>

---

## 🌟 Why SES Core?

If you are building **Local Artificial Intelligence** applications (with Ollama, LM Studio, or Llama.cpp) and need a RAG (*Retrieval-Augmented Generation*) engine that guarantees **zero data leaks**, you are in the right place.

Traditional libraries (LangChain, LlamaIndex) are designed with the cloud in mind (OpenAI, Pinecone), making them heavy and hard to isolate. **SES Core is born with a diametrically opposite philosophy: Offline-First.**

* 🔒 **Total Privacy:** Zero internet calls. All embeddings and LLM processing happen on your local hardware.
* ⚡ **Ultra Fast:** Optimized for low latency (Vector search in `~1.5 ms`).
* 📁 **Automatic Mount Mode:** Includes a *Watcher* that monitors your local folders (PDFs, DOCX, XLSX) and incrementally indexes them in the background.
* 🧩 **Extremely Modular:** Use it in CLI scripts, desktop apps (PyQt), or as the internal engine for your own API.
* 🚀 **Re-Ranking and Batch Search:** Advanced built-in capabilities ready for production.

---

## ⚡ Performance (Validated)

SES Core measures and validates its performance automatically:

| Metric | Value | Method |
|---------|-------|--------|
| **Chunking Throughput** | > 190,000 KB/s | `tests/performance/benchmark.py` |
| **Vector Search (1K docs)** | `~ 1.5 ms` | Cosine similarity (Python + Rust) |
| **Rust Core Acceleration** | 2-10x faster | `jas_vector_core` vs Python |

📊 **Benchmarks executed on every commit** → [View history in Actions](https://github.com/JPatronC92/SES/actions)

---

## 🔒 Privacy and Security

Building with SES Core means **Zero Data Leakage Guarantee**:
- **Local Embeddings Processing:** We use `SentenceTransformers` running on your own CPU/GPU. Your documents never travel to HuggingFace servers.
- **Isolated LLM Logic:** The `LocalLLMProvider` connects via local sockets (`localhost:11434`) to Ollama. 
- **Metadata Filtering:** During the storage phase, any excluded text or metadata is not stored in indexed variables to prevent accidental leaks during searches.

---

## 📦 Installation

**Step 1:** Install the base library (includes Qdrant and Redis dependencies)
```bash
pip install ses-core
```

*(Optional)* If you need to build a web API on top of SES Core, install the server dependencies (FastAPI, Uvicorn):
```bash
pip install ses-core[server]
```

---

## ⚙️ Configuration and Production Requirements

SES Core requires you to configure certain environment variables to work in production. You can use a `.env` file or export them in your terminal:

```env
# DEBUG MODE (True disables password checks, ideal for local dev)
DEBUG=True

# QDRANT (Mandatory in production for vector persistence)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_secret_api_key

# REDIS (Mandatory for async caching and rate limiting in production)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_secret_password
```

**Important Note:** If `DEBUG=True`, SES will attempt to connect to local Qdrant and Redis instances without a password.

---

## 💻 Quickstart

Build a knowledge application in 3 steps:

### 1. Prerequisites and Initialization

**Important!** Although SES Core is 100% offline and does not call cloud APIs, the library delegates vector storage and rate limiting to highly optimized services. **You must have Qdrant, Redis, and [Ollama](https://ollama.com/) running locally.**

Example using Docker to start the required infrastructure:
```bash
docker run -d -p 6333:6333 qdrant/qdrant
docker run -d -p 6379:6379 redis
```

Then, you can start your Python application:

```python
import asyncio
from ses.core.rag import OfflineRAGEngine
from ses.core.llm import LocalLLMProvider

async def main():
    # Initialize the local vector engine (Qdrant + Redis caching)
    engine = OfflineRAGEngine()
    
    # Initialize the connection with Ollama (100% offline)
    llm = LocalLLMProvider(model_override="llama3")
```

### 2. "Drop-in" Document Indexing

SES Core supports automatic extraction of `PDF`, `DOCX`, `TXT`, and `XLSX`.

```python
    # Ingest a confidential document
    with open("confidential_contract.pdf", "rb") as f:
        result = await engine.ingest_file(
            namespace="legal", 
            file_obj=f, 
            filename="confidential_contract.pdf", 
            metadata={"author": "Lawyer"}
        )
    print(f"Successfully indexed: {result['chunks_count']} semantic chunks.")
```

### 3. Search and Answer Generation

```python
    # Retrieve the chunks with the highest cosine similarity
    results = await engine.search(
        namespace="legal", 
        query="What are the termination clauses of the contract?"
    )

    # Generate a synthetic answer using the local AI
    answer = llm.generate_answer(
        query="Explain the termination clauses based on the document.", 
        context_docs=results["results"]
    )

    print(answer)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🏗️ Architecture and Advanced Components

SES Core is highly hackable and includes Enterprise features out of the box:
- **PDF Report Generation:** Use `ses.core.reports` to export analytics.
- **Cognitive Re-Ranking:** Score re-evaluation in the `rag.py` engine.
- **TTL Caching:** Method-level caching (Redis) for instant responses.

```text
ses/
├── core/
│   ├── parsers.py       # Extraction algorithms (PDF, DOCX, XLSX, TXT)
│   ├── chunking.py      # Smart semantic segmentation
│   ├── embeddings.py    # Local HuggingFace models wrapper
│   ├── vector_store.py  # Async abstraction (Qdrant)
│   ├── llm.py           # Offline providers (Ollama)
│   ├── reports.py       # Advanced PDF report generation
│   └── rag.py           # Main orchestrator with Re-ranking
├── watcher/
│   └── monitor.py       # File system observability (Watchdog)
└── config.py            # Static environment variables and secret management
```

---

## 📚 Additional Documentation

For more complex integrations, step-by-step deployment guides, and internal API documentation, please visit our [Official GitHub Wiki](https://github.com/JPatronC92/SES/wiki).

---

## 📈 Monetization and Enterprise

SES operates under an **Open Core** model. 
This library (`ses-core`) represents our "Tier 1" and will always be **free, open-source, and tracking-free** (GPLv3) for the local AI developer community.

For corporations or massive infrastructures requiring **SaaS Managed, On-Premise deployments with RBAC controls, or guaranteed SLAs**, we offer *SES Enterprise* packages. Contact us for enterprise AI solutions that are HIPAA and GDPR compliant from day 1.

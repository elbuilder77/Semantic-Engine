<div align="center">
  <h1>🧠 SES Core: Semantic Engine</h1>
  <p><strong>An offline-first RAG library for private, locally operated AI applications.</strong></p>
  
  [![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
  [![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
  [![Offline First](https://img.shields.io/badge/Runtime-Local--First-red.svg)](#)
  
  *Read this in [Spanish (Español)](README.md)*
</div>

---

## 🌟 Why SES Core?

If you are building **Local Artificial Intelligence** applications (with Ollama, LM Studio, or Llama.cpp) and need a RAG (*Retrieval-Augmented Generation*) engine that guarantees **zero data leaks**, you are in the right place.

Traditional libraries (LangChain, LlamaIndex) are designed with the cloud in mind (OpenAI, Pinecone), making them heavy and hard to isolate. **SES Core is born with a diametrically opposite philosophy: Offline-First.**

* 🔒 **Local operation:** Documents, embeddings, and queries stay in your infrastructure. Provision the embedding model locally before operating without network access.
* ⚡ **Hybrid vector path:** Qdrant retrieves candidates and an optional Rust module can recompute similarity for large batches.
* 📁 **Automatic Mount Mode:** Includes a *Watcher* that monitors your local folders (PDFs, DOCX, XLSX) and incrementally indexes them in the background.
* 🧩 **Extremely Modular:** Use it in CLI scripts, desktop apps (PyQt), or as the internal engine for your own API.
* 🚀 **Re-Ranking and Batch Search:** Advanced built-in capabilities ready for production.

---

## ⚡ Performance Evidence

The repository contains a reproducible synthetic-vector microbenchmark. It does
not measure end-to-end Qdrant, ingestion, disk, or LLM latency.

| Metric | Value | Method |
|---------|-------|--------|
| **Python, 1,000 × 384** | `47.60 ms/search` | 3 iterations, normalized synthetic vectors |
| **Rust/NumPy, 1,000 × 384** | `0.97 ms/search` | CPython 3.12 wheel, contiguous zero-copy ndarray |
| **Scope** | `local microbenchmark` | Windows AMD64 (16 logical CPUs), CPython 3.12, July 15, 2026; not an SLA |

CI runs the same bounded workload as a performance smoke, without treating a
single runner result as an SLA.

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

The Rust extension is packaged as a separate wheel:

```powershell
python -m pip install "maturin>=1,<2"
python -m maturin build --release --manifest-path core_rs/Cargo.toml --interpreter python --out core_rs/target/wheels
$wheel = Get-ChildItem core_rs/target/wheels/*.whl | Select-Object -First 1
python -m pip install --force-reinstall $wheel.FullName
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

### Agent execution rules

Repository-wide operating rules live in [`AGENTS.md`](AGENTS.md), validated work
is tracked in [`TASKS.md`](TASKS.md), and SES-specific SOPs live under
[`ses-agent-system/`](ses-agent-system/README.md). These files govern engineering
work; they are not a standalone multi-agent runtime.

Generate and rotate ignored local Gateway and signing secrets with:

```bash
pip install -e .[server,security]
python scripts/rotate_local_secrets.py
```

The command never prints secret values. Production deployments must inject
equivalent values through a secret manager.

### Web portal

The administration frontend under [`portal/`](portal/README.md) consumes the
live Gateway contracts and stores its URL/key only in the browser. Its minimum
gate is `npm ci --prefix portal`, `npm --prefix portal run lint`, and
`npm --prefix portal run build`.

### GitHub Actions automation

[`ci.yml`](.github/workflows/ci.yml) validates the portal, Python code, and Rust
wheel on every push/PR to `main`, and supports manual runs. It uses read-only
permissions and cancels superseded runs for the same branch.

[`publish.yml`](.github/workflows/publish.yml) always builds and verifies the
distribution artifacts. A manual run **does not publish**; PyPI publication is
only enabled for a published GitHub Release and requires a PyPI Trusted
Publisher configured for the `pypi` environment.

For more complex integrations, step-by-step deployment guides, and internal API documentation, please visit our [Official GitHub Wiki](https://github.com/JPatronC92/SES/wiki).

---

## 📈 Monetization and Enterprise

SES operates under an **Open Core** model. 
This library (`ses-core`) represents our "Tier 1" and will always be **free, open-source, and tracking-free** (GPLv3) for the local AI developer community.

Managed SaaS, on-premise RBAC, SLAs, and regulated-industry compliance remain
productization targets; this repository alone is not evidence of HIPAA or GDPR
certification.

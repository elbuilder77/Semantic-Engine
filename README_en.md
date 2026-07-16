<div align="center">
  <h1>SES Core: Semantic Engine</h1>
  <p><strong>An offline-first RAG engine for private documents, with a Gateway, Portal, and optional Rust acceleration.</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.9--3.12-blue.svg)](https://www.python.org)
  [![Status](https://img.shields.io/badge/Status-Beta-orange.svg)](#verified-status)
  [![CI](https://github.com/JPatronC92/Semantic-Engine/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JPatronC92/Semantic-Engine/actions/workflows/ci.yml)
  [![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

  *[Versión en español](README.md)*
</div>

---

## What SES is

SES turns local documents into a searchable semantic index. The Python core
extracts, chunks, embeds, and queries through Qdrant; Redis provides caching and
distributed controls; Ollama generates local answers; the FastAPI Gateway
exposes HTTP contracts; and the Next.js Portal provides the administration UI.

Offline-first means documents and queries can stay in operator-controlled
infrastructure. It does not mean that installation has zero network
dependencies: packages, images, and models must be provisioned before running
without a network.

## Verified status

This repository is a technical beta. Live code and executable validation are
the source of truth.

| Surface | Verified state | Current boundary |
|---|---|---|
| Python core | 32 tests pass on CPython 3.12 | Real Qdrant/Redis/Ollama integration remains open |
| Gateway | Auth, key rotation, CORS, and rate limiting are hardened | Persistent telemetry and Docker parity remain open |
| Portal | Next.js 16; lint, build, and eight administration routes validated | Real-service E2E remains open |
| Rust | CPython 3.12 wheel, tests, Clippy, and NumPy API | Optional and used for candidate batches larger than 50 |
| CI | Portal, Python, Rust, wheel, Pytest, and synthetic smoke in GitHub Actions | Does not replace end-to-end testing |
| Packaging | Python wheel and sdist build and pass Twine checks | PyPI Trusted Publisher still requires configuration |
| Mount Mode | Scan, SHA-256, debounce, manifest, and path traceability | Changed-file reindexing is not atomic yet |

## Architecture

~~~text
Read-only documents
        |
        v
Watcher / Scanner ---> Parsing and chunking ---> Local embeddings
                                                |
                                                v
Next.js Portal ---> FastAPI Gateway ---> Qdrant / Redis / Ollama
                           |
                           +-- PDF reports
                           +-- keys and analytics
                           +-- optional Rust reranking
~~~

Main directories:

- <code>ses/</code>: RAG library, providers, reports, and watcher.
- <code>gateway/</code>: FastAPI, static dashboard, and local SQLite state.
- <code>portal/</code>: Next.js administration client.
- <code>core_rs/</code>: the <code>jas_vector_core</code> PyO3 extension.
- <code>tests/</code>: Python tests and a synthetic microbenchmark.
- <code>ses-agent-system/</code>: repository engineering rules and SOPs.

## Install from source

The currently validated route is installation from this repository. Do not
assume that <code>pip install ses-core</code> matches <code>main</code> until a
public release has been verified.

~~~powershell
git clone https://github.com/JPatronC92/Semantic-Engine.git
cd Semantic-Engine
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,server,security]"
~~~

Package metadata declares Python 3.9–3.12 compatibility; CI currently validates
CPython 3.12.

### Optional Rust extension

~~~powershell
python -m pip install "maturin>=1,<2"
python -m maturin build --release --manifest-path core_rs/Cargo.toml --interpreter python --out core_rs/target/wheels
$wheel = Get-ChildItem core_rs/target/wheels/*.whl | Select-Object -First 1
python -m pip install --force-reinstall $wheel.FullName
~~~

The Rust wheel is separate from the base Python package. SES keeps the Python
path when the module is missing or cannot be used.

## Secure configuration

Use <code>.env.example</code> as the variable inventory. Generate unique local
keys without printing them:

~~~powershell
Copy-Item .env.example .env
python scripts/rotate_local_secrets.py
~~~

The command rotates:

- <code>GATEWAY_ADMIN_KEY</code> in <code>.env</code>;
- the Ed25519 pair in <code>ses-agent-system/keys.json</code>;
- previous local administrative SQLite keys when present.

Both secret files and local databases are ignored by Git. In production, use a
secret manager, keep <code>DEBUG=false</code>, and configure non-placeholder
Qdrant and Redis credentials. A Redis outage blocks protected production routes;
the in-memory fallback exists only with <code>DEBUG=true</code>.

The Portal stores the Gateway URL and key in browser <code>localStorage</code>.
Never place an API key in a <code>NEXT_PUBLIC_*</code> variable.

## Local services

The repository does not yet contain a reviewed Compose stack. For development,
Qdrant and Redis can be started explicitly:

~~~powershell
docker run --name ses-qdrant -p 6333:6333 -d qdrant/qdrant
docker run --name ses-redis -p 6379:6379 -d redis:7.4-alpine
~~~

Ollama must run separately with the model named by <code>OLLAMA_MODEL</code>.
The SentenceTransformers embedding model must also be provisioned locally
before network-free operation.

## Run the Gateway and Portal

Gateway:

~~~powershell
python gateway/run.py
~~~

The Gateway listens on <http://127.0.0.1:8000>. Main routes include:

- <code>POST /api/v1/search</code>
- <code>POST /api/v1/ingest/file</code>
- <code>POST /api/v1/ingest/text</code>
- <code>GET /api/v1/documents</code>
- <code>DELETE /api/v1/documents/{doc_id}</code>
- <code>GET /api/v1/health</code> and <code>/api/v1/stats</code>
- key, analytics, and report administration under <code>/api/v1/admin</code>

Portal:

~~~powershell
npm ci --prefix portal
npm --prefix portal run dev -- --hostname 127.0.0.1 --port 3000
~~~

Open <http://127.0.0.1:3000/settings>, enter the Gateway URL and a rotated
administrator key, and use **Test Connection**. Implemented routes are
<code>/dashboard</code>, <code>/search</code>, <code>/documents</code>,
<code>/keys</code>, <code>/analytics</code>, <code>/reports</code>, and
<code>/settings</code>.

## Direct library usage

~~~python
import asyncio

from ses.core.llm import LocalLLMProvider
from ses.core.rag import OfflineRAGEngine


async def main():
    engine = OfflineRAGEngine()

    with open("contract.pdf", "rb") as source:
        await engine.ingest_file(
            namespace="legal",
            file_obj=source,
            filename="contract.pdf",
            metadata={"source_path": "contract.pdf"},
        )

    search = await engine.search(
        namespace="legal",
        query="What are the termination conditions?",
        top_k=5,
    )

    answer = LocalLLMProvider().generate_answer(
        query="Summarize the termination conditions.",
        context_docs=search["results"],
    )
    print(answer)


asyncio.run(main())
~~~

## Mount Mode

The watcher treats observed directories as read-only sources. It performs an
initial scan, filters PDF/DOCX/XLSX/CSV/TXT/MD files, calculates SHA-256, stores
<code>source_path</code>, and skips insertion when content is unchanged.
Filesystem events are grouped with per-path debounce.

Replacing a changed file currently deletes the previous indexed version before
the new ingestion finishes. The manifest makes recovery possible, but the
operation is not atomic yet. See [docs/MOUNT_MODE.md](docs/MOUNT_MODE.md).

## Validation

Local gates corresponding to CI:

~~~powershell
pytest -q -p no:cacheprovider
npm --prefix portal run lint
npm --prefix portal run build
cargo fmt --manifest-path core_rs/Cargo.toml -- --check
cargo test --manifest-path core_rs/Cargo.toml
cargo clippy --manifest-path core_rs/Cargo.toml --all-targets -- -D warnings
~~~

[GitHub Actions](https://github.com/JPatronC92/Semantic-Engine/actions) also
builds and installs the CPython 3.12 Rust wheel. The manual packaging workflow
builds and verifies the sdist/wheel but skips publication. Only a published
GitHub Release can activate the PyPI OIDC job.

The microbenchmark in <code>tests/performance/benchmark.py</code> uses synthetic
vectors. It is a reproducible smoke, not end-to-end ingestion, disk, Qdrant, or
LLM latency, and its numbers are not an SLA.

## Production gaps

- No reproducible Compose stack or proven local/Docker parity.
- Real SQLite, Qdrant, Redis, and Ollama failure-path tests remain open.
- Persistent Gateway telemetry still needs hardening.
- No named 40–60 GB ingestion/retrieval workload has been executed.
- Changed-file reindexing is not atomic.
- PyPI Trusted Publishing and a public release remain pending.
- The repository does not prove corporate SLAs, complete RBAC, or HIPAA/GDPR
  certification.

## Documentation and rules

- [AGENTS.md](AGENTS.md): canonical execution rules.
- [ROADMAP.md](ROADMAP.md): product phases and gates.
- [TASKS.md](TASKS.md): gaps confirmed against live code.
- [gateway/README.md](gateway/README.md): Gateway operation and contracts.
- [portal/README.md](portal/README.md): Portal routes and validation.
- [docs/MOUNT_MODE.md](docs/MOUNT_MODE.md): watcher contract and limits.

## License

SES Core is distributed under GPLv3. Managed offerings, SLAs, and regulatory
certifications are future commercial objectives, not properties demonstrated
by the current repository state.

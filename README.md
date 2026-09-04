<div align="center">
  <h1>SES Core: Semantic Engine</h1>
  <p><strong>Motor RAG offline-first para documentos privados, con Gateway, Portal y aceleración Rust opcional.</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.9--3.12-blue.svg)](https://www.python.org)
  [![Estado](https://img.shields.io/badge/Estado-Beta-orange.svg)](#estado-verificado)
  [![CI](https://github.com/elbuilder77/Semantic-Engine/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/elbuilder77/Semantic-Engine/actions/workflows/ci.yml)
  [![Licencia](https://img.shields.io/badge/Licencia-GPLv3-blue.svg)](LICENSE)

  *[English version](README_en.md)*
</div>

---

## Qué es SES

SES convierte documentos locales en un índice semántico consultable. El núcleo
Python extrae, segmenta, genera embeddings y consulta Qdrant; Redis aporta caché
y control distribuido; Ollama genera respuestas locales; el Gateway FastAPI
expone los contratos HTTP y el Portal Next.js ofrece la superficie
administrativa.

Offline-first significa que los documentos y consultas pueden permanecer en la
infraestructura del operador. No significa cero dependencias de red durante la
instalación: paquetes, imágenes y modelos deben aprovisionarse antes de operar
sin conexión.

## Estado verificado

Este repositorio está en beta técnica. El código y la validación ejecutable son
la fuente de verdad.

| Superficie | Estado comprobado | Límite actual |
|---|---|---|
| Núcleo Python | Pytest valida núcleo, SQLite y fallos de red controlados | E2E exitoso con Qdrant/Redis/Ollama reales pendiente |
| Gateway | Auth, telemetría SQLite, CORS y rate limiting endurecidos | Validación PostgreSQL y paridad Docker completa pendientes |
| Portal | Next.js 16; lint, build y ocho rutas administrativas validadas | E2E contra servicios reales pendiente |
| Rust | Wheel CPython 3.12, pruebas, Clippy y API NumPy | Es opcional y se activa en lotes de más de 50 candidatos |
| CI | Portal, Python, Rust, wheel, Pytest y smoke sintético en GitHub Actions | No sustituye pruebas end-to-end |
| Publicación | `ses-core` 2.0.3 en PyPI y `jas_vector_core` 0.1.0 en crates.io; cinco wheels ABI3, sdist y checksums verificados | Las versiones publicadas son inmutables; cada corrección requiere una versión nueva |
| Mount Mode | Reindexado primero ingiere y conserva limpiezas pendientes en el manifiesto | No existe una transacción distribuida con Qdrant |

## Arquitectura

~~~text
Documentos de solo lectura
        |
        v
Watcher / Scanner ---> Parser y chunking ---> Embeddings locales
                                                |
                                                v
Portal Next.js ---> Gateway FastAPI ---> Qdrant / Redis / Ollama
                            |
                            +-- reportes PDF
                            +-- llaves y analítica
                            +-- reranking Rust opcional
~~~

Directorios principales:

- <code>ses/</code>: librería RAG, proveedores, reportes y watcher.
- <code>gateway/</code>: API FastAPI, dashboard estático y SQLite local.
- <code>portal/</code>: cliente administrativo Next.js.
- <code>core_rs/</code>: extensión PyO3 <code>jas_vector_core</code>.
- <code>sdk/</code>: SDKs oficiales para TypeScript (`@ses-ai/client`) y Go (`ses-go`).
- <code>tests/</code>: pruebas Python y microbenchmark sintético.

## 🚀 Despliegue Empresarial Llave en Mano (Docker 1-Click)

Para desplegar la plataforma completa de Semantic Engine (Gateway FastAPI + Portal Next.js + Qdrant + Redis + Ollama) en producción:

~~~powershell
# 1. Generar configuración criptográfica de producción (.env.prod)
python scripts/deploy_production.py

# 2. Levantar el stack completo en segundo plano
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
~~~

Servicios disponibles:
- **Portal Administrativo:** <http://127.0.0.1:3000>
- **Enterprise Gateway:** <http://127.0.0.1:8000> (Documentación OpenAPI en `/docs`)
- **Base Vectorial Qdrant:** `:6333` (Red interna aislada)
- **Caché Redis:** `:6379` (Red interna aislada con autenticación obligatoria)
- **Servidor LLM Ollama:** `:11434` (Red interna aislada)

---

## 📦 SDKs Oficiales de Integración

### TypeScript / JavaScript (`@ses-ai/client`)
Consulte la documentación completa en [sdk/typescript/README.md](sdk/typescript/README.md).

~~~typescript
import { SemanticEngineClient } from "@ses-ai/client";

const client = new SemanticEngineClient({
  baseUrl: "http://localhost:8000",
  apiKey: process.env.SES_API_KEY!,
});

const result = await client.search({
  namespace: "legal",
  query: "cláusula de rescisión",
  generateAnswer: true,
});
console.log("Respuesta RAG:", result.answer);
~~~

### Go (`ses-go`)
Consulte la documentación completa en [sdk/go/README.md](sdk/go/README.md).

~~~go
import ses "github.com/elbuilder77/Semantic-Engine/sdk/go"

client, _ := ses.NewClient(ses.ClientConfig{
    BaseURL: "http://localhost:8000",
    APIKey:  "tu_llave_api",
})

resp, _ := client.Search(ctx, ses.SearchRequest{
    Namespace: "legal",
    Query:     "cláusula de rescisión",
})
~~~

---

## Instalación desde PyPI

~~~powershell
python -m pip install "ses-core==2.0.3"
~~~

La versión 2.0.3 está publicada mediante Trusted Publishing (OIDC) con wheels
ABI3 para Windows, Linux y macOS, además del sdist. Los artefactos y sus
checksums también están disponibles en la
[GitHub Release v2.0.3](https://github.com/elbuilder77/Semantic-Engine/releases/tag/v2.0.3).
El crate standalone se publica como
[`jas_vector_core` 0.1.0](https://crates.io/crates/jas_vector_core/0.1.0).

## Instalación desde el código fuente

~~~powershell
git clone https://github.com/elbuilder77/Semantic-Engine.git
cd Semantic-Engine
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,server]"
~~~

### Extensión Rust opcional

~~~powershell
python -m pip install "maturin>=1,<2"
python -m maturin build --release --manifest-path core_rs/Cargo.toml --interpreter python --out core_rs/target/wheels
$wheel = Get-ChildItem core_rs/target/wheels/*.whl | Select-Object -First 1
python -m pip install --force-reinstall $wheel.FullName
~~~

## Servicios locales de desarrollo

El Compose canónico levanta dependencias satélite para desarrollo:

~~~powershell
Copy-Item .env.compose.example .env.compose
# Edite QDRANT_API_KEY y REDIS_PASSWORD en .env.compose
docker compose --env-file .env.compose up -d
docker compose --env-file .env.compose ps
~~~

Gateway:

~~~powershell
python gateway/run.py
~~~

Portal:

~~~powershell
npm ci --prefix portal
npm --prefix portal run dev -- --hostname 127.0.0.1 --port 3000
~~~

## Mount Mode

El watcher trata las carpetas observadas como fuentes de solo lectura. Realiza
un escaneo inicial, filtra PDF/DOCX/XLSX/CSV/TXT/MD, calcula SHA-256, guarda
<code>source_path</code> y evita reinserciones cuando el contenido no cambió.
Los eventos se agrupan mediante debounce.

Consulte [docs/MOUNT_MODE.md](docs/MOUNT_MODE.md).

## Validación

Gates locales equivalentes a CI:

~~~powershell
pytest -q -p no:cacheprovider
npm --prefix portal run lint
npm --prefix portal run test
npm --prefix portal run build
cargo fmt --manifest-path core_rs/Cargo.toml -- --check
cargo test --manifest-path core_rs/Cargo.toml
cargo clippy --manifest-path core_rs/Cargo.toml --all-targets -- -D warnings
~~~

## Licencia

SES Core se distribuye bajo GPLv3.

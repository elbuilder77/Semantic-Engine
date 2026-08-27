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
| Publicación | Wheel y sdist Python se construyen y pasan Twine | PyPI Trusted Publisher aún debe configurarse |
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
- <code>tests/</code>: pruebas Python y microbenchmark sintético.

## Instalación desde el código fuente

La ruta validada actualmente es instalar desde este repositorio. No se debe
asumir que <code>pip install ses-core</code> corresponde al código de
<code>main</code> hasta completar una publicación pública verificada.

~~~powershell
git clone https://github.com/elbuilder77/Semantic-Engine.git
cd Semantic-Engine
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,server]"
~~~

El paquete base declara compatibilidad Python 3.9–3.12; CI valida hoy CPython
3.12.

### Extensión Rust opcional

~~~powershell
python -m pip install "maturin>=1,<2"
python -m maturin build --release --manifest-path core_rs/Cargo.toml --interpreter python --out core_rs/target/wheels
$wheel = Get-ChildItem core_rs/target/wheels/*.whl | Select-Object -First 1
python -m pip install --force-reinstall $wheel.FullName
~~~

El wheel Rust es independiente del paquete Python base. SES conserva la ruta
Python cuando el módulo no está instalado o no puede usarse.

## Configuración segura

Use <code>.env.example</code> como inventario de variables. Para desarrollo
local, genere llaves únicas sin imprimirlas:

~~~powershell
Copy-Item .env.example .env
python scripts/rotate_local_secrets.py
~~~

El comando rota:

- <code>GATEWAY_ADMIN_KEY</code> en <code>.env</code>;
- llaves administrativas locales anteriores en SQLite, cuando existen.

Ambos archivos de secretos y las bases locales están ignorados por Git. En
producción use un gestor de secretos, mantenga <code>DEBUG=false</code> y
configure credenciales no triviales para Qdrant y Redis. La caída de Redis en
producción bloquea las rutas protegidas; el fallback en memoria existe solo con
<code>DEBUG=true</code>.

El Portal guarda URL y llave del Gateway en <code>localStorage</code> del
navegador. No coloque una llave en variables <code>NEXT_PUBLIC_*</code>.

## Servicios locales

El Compose canónico levanta dependencias locales con versiones fijas, volúmenes
nombrados y puertos limitados a loopback. Copie el inventario y configure
valores únicos:

~~~powershell
Copy-Item .env.compose.example .env.compose
# Edite QDRANT_API_KEY y REDIS_PASSWORD en .env.compose
docker compose --env-file .env.compose up -d
docker compose --env-file .env.compose ps
~~~

Este archivo levanta Qdrant, Redis y Ollama; no ejecuta Gateway ni Portal. El
modelo configurado en <code>OLLAMA_MODEL</code> y el modelo de embeddings de
SentenceTransformers deben aprovisionarse antes de operar sin red.

## Ejecutar Gateway y Portal

Gateway:

~~~powershell
python gateway/run.py
~~~

El Gateway queda en <http://127.0.0.1:8000>. Sus rutas principales son:

- <code>POST /api/v1/search</code>
- <code>POST /api/v1/ingest/file</code>
- <code>POST /api/v1/ingest/text</code>
- <code>GET /api/v1/documents</code>
- <code>DELETE /api/v1/documents/{doc_id}</code>
- <code>GET /api/v1/health</code> y <code>/api/v1/stats</code>
- administración de llaves, analítica y reportes bajo <code>/api/v1/admin</code>

Portal:

~~~powershell
npm ci --prefix portal
npm --prefix portal run dev -- --hostname 127.0.0.1 --port 3000
~~~

Abra <http://127.0.0.1:3000/settings>, capture la URL y una llave administrativa
rotada, y use **Test Connection**. Las rutas implementadas son
<code>/dashboard</code>, <code>/search</code>, <code>/documents</code>,
<code>/keys</code>, <code>/analytics</code>, <code>/reports</code> y
<code>/settings</code>.

## Uso directo de la librería

~~~python
import asyncio

from ses.core.llm import LocalLLMProvider
from ses.core.rag import OfflineRAGEngine


async def main():
    engine = OfflineRAGEngine()

    with open("contrato.pdf", "rb") as source:
        await engine.ingest_file(
            namespace="legal",
            file_obj=source,
            filename="contrato.pdf",
            metadata={"source_path": "contrato.pdf"},
        )

    search = await engine.search(
        namespace="legal",
        query="¿Cuáles son las condiciones de rescisión?",
        top_k=5,
    )

    answer = LocalLLMProvider().generate_answer(
        query="Resume las condiciones de rescisión.",
        context_docs=search["results"],
    )
    print(answer)


asyncio.run(main())
~~~

## Mount Mode

El watcher trata las carpetas observadas como fuentes de solo lectura. Realiza
un escaneo inicial, filtra PDF/DOCX/XLSX/CSV/TXT/MD, calcula SHA-256, guarda
<code>source_path</code> y evita reinserciones cuando el contenido no cambió.
Los eventos se agrupan mediante debounce.

La sustitución ingiere primero la versión nueva. Si falla la eliminación de la
versión anterior, su identificador permanece como
<code>pending_delete_document_ids</code> en el manifiesto y se reintenta durante
el siguiente escaneo. El flujo es recuperable, aunque no constituye una
transacción distribuida con Qdrant. Consulte
[docs/MOUNT_MODE.md](docs/MOUNT_MODE.md).

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

La ejecución anterior excluye por defecto las pruebas marcadas como
<code>integration</code>. Con Qdrant y Redis disponibles mediante el Compose
documentado, el gate E2E se ejecuta de forma explícita:

~~~powershell
pytest -q -m integration tests/integration
~~~

[GitHub Actions](https://github.com/elbuilder77/Semantic-Engine/actions) ejecuta
además la construcción e instalación del wheel CPython 3.12. El workflow manual
de empaquetado construye y verifica sdist/wheel, pero omite la publicación. Solo
un GitHub Release publicado puede activar el job OIDC de PyPI.

El microbenchmark de <code>tests/performance/benchmark.py</code> usa vectores
sintéticos. Sirve como smoke reproducible y no representa latencia de ingestión,
disco, Qdrant ni generación LLM; sus números no son un SLA.

## Límites antes de producción

- Existe un Compose reproducible para dependencias; la paridad completa con Gateway y Portal no está demostrada.
- SQLite y los fallos de conexión Qdrant/Redis/Ollama tienen cobertura; falta el E2E exitoso contra servicios reales.
- La telemetría persistente está validada con SQLite; PostgreSQL real sigue pendiente.
- No se han ejecutado cargas nominales de ingestión/recuperación de 40–60 GB.
- El reindexado es recuperable por manifiesto, pero no atómico entre procesos.
- PyPI Trusted Publishing y una publicación pública siguen pendientes.
- No existen todavía SLAs, RBAC corporativo completo ni certificaciones
  HIPAA/GDPR acreditadas por este repositorio.

## Documentación

- [gateway/README.md](gateway/README.md): operación y contratos del Gateway.
- [portal/README.md](portal/README.md): rutas y validación del Portal.
- [docs/MOUNT_MODE.md](docs/MOUNT_MODE.md): contrato y límites del watcher.

## Licencia

SES Core se distribuye bajo GPLv3. Las ofertas administradas, SLAs y
certificaciones regulatorias son objetivos comerciales futuros, no propiedades
demostradas por el estado actual del repositorio.

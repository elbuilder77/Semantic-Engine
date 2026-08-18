# Plan de Implementación Integral para SES Core (Fases 1, 2 y 3)

Este documento describe la estrategia paso a paso para completar el 100% de las tareas pendientes en las Fases 1, 2 y 3 del archivo `ROADMAP.md` del repositorio **SES Core**.

## Estado Actual de Tareas Pendientes

**Fase 1: Estabilización del Núcleo RAG**
*   [ ] Cerrar pruebas de integración reales y paridad local/Docker antes de declarar estable el núcleo.

**Fase 2: Mount Mode & Filesystem**
*   [ ] Optimización de memoria para el escaneo inicial de repositorios masivos (> 60 GB).
*   [ ] Conectores para orígenes de datos locales y compartidos (e.g., SMB/CIFS).

**Fase 3: RAG Cognitivo & Enterprise Features**
*   [ ] Multi-Agent Orchestration: Abstracciones para conectar SES Core con frameworks de agentes (LangGraph, CrewAI).
*   [ ] RBAC Interno: Controles de acceso basados en roles inyectados directamente en los metadatos de Qdrant.

---

## Estrategia de Implementación Detallada

### Paso 1: Completar la Fase 1 (Pruebas de Integración y Paridad)

**Objetivo:** Asegurar que el entorno local (`poetry run`) y el entorno Docker se comporten de manera idéntica frente a fallos y carga, interactuando con instancias reales de los servicios dependientes.

*   **Acciones:**
    1.  **Directorio de Pruebas:** Crear la estructura de carpetas `tests/integration/`.
    2.  **Pruebas End-to-End (E2E):** Crear el archivo `tests/integration/test_e2e.py`. En este archivo, escribir pruebas asíncronas utilizando `pytest-asyncio` que inicialicen `OfflineRAGEngine` e interactúen con instancias vivas de **Qdrant** (puerto 6333), **Redis** (puerto 6379) y **Ollama** (puerto 11434). Las pruebas deben cubrir:
        *   Ingesta completa de un archivo de prueba (PDF/TXT).
        *   Búsqueda de vectores devolviendo resultados relevantes.
        *   Lectura/escritura de cachés desde y hacia Redis.
    3.  **Actualización de CI:** Modificar `.github/workflows/ci.yml`. Añadir un job de validación (o actualizar el existente) para que, antes de correr `pytest`, levante los servicios usando `docker-compose -f docker-compose.yml up -d`, espere a que estén listos (`healthchecks`) y luego ejecute `poetry run pytest tests/integration/`.

### Paso 2: Completar la Fase 2 (Optimización y Conectores de Red)

**Objetivo:** Permitir el indexado de discos duros inmensos sin colapsar la RAM y soportar repositorios en red.

*   **Acciones:**
    1.  **Refactorización de Escaneo (Scanner):**
        *   Modificar `ses/watcher/scanner.py`.
        *   Cambiar la función `scan_directory` para que, en lugar de poblar una lista gigante (`manifest.append(...)`) y retornarla, utilice `yield` para comportarse como un **generador**. Esto evitará cargar un millón de metadatos de archivos en memoria simultáneamente.
    2.  **Modificación del Monitor (Watcher):**
        *   Ir a `ses/watcher/monitor.py` y ubicar el método `_initial_scan` en la clase `SESWatcher`.
        *   Actualizar el bucle `for entry in manifest:` para procesar los elementos emitidos por el generador `scan_directory`. Opcionalmente, agrupar las inserciones asíncronas (`ingest_file`) en **lotes (batches)** controlados por un semáforo (`asyncio.Semaphore`) para no abrumar al event loop ni al motor Qdrant.
    3.  **Implementación de SMB (Connectors):**
        *   Añadir dependencia `smbprotocol` a `pyproject.toml` usando `poetry add smbprotocol`.
        *   Crear `ses/watcher/connectors.py` definiendo una clase base `DataSourceConnector` (con métodos `scan` y `read`).
        *   Crear la clase `SMBDataSourceConnector` que herede de la base, implementando la conexión y el listado de archivos remotos a través del protocolo SMB, para que el `SESWatcher` pueda instanciarla cuando la ruta sea de red (`smb://...`).

### Paso 3: Completar la Fase 3 (RBAC y Agentes)

**Objetivo:** Dotar al sistema de seguridad corporativa a nivel documental e interfaces fáciles para frameworks modernos de orquestación IA.

*   **Acciones:**
    1.  **Implementación de RBAC (Role-Based Access Control):**
        *   Abrir `ses/core/rag.py`.
        *   Modificar la firma de `ingest_file(..., metadata: dict = None, allowed_roles: List[str] = None)`. Inyectar la lista de roles en el payload del documento que va hacia Qdrant. Si no se proveen roles, asumir acceso público o genérico.
        *   Modificar la firma de `search(..., user_roles: List[str] = None)`. Configurar el objeto `qmodels.QueryRequest` para inyectar un filtro condicional. Utilizar un `Filter` de Qdrant que compruebe si existe superposición (`MatchAny`) entre `user_roles` del solicitante y los `allowed_roles` almacenados en los metadatos del punto vectorial. De esta forma, el filtrado es forzoso en la base de datos (seguro) y no a nivel de la aplicación.
    2.  **Adaptadores Multi-Agente (Orchestration):**
        *   Crear el archivo `ses/core/agents.py`.
        *   **LangGraph/LangChain:** Implementar la clase `SESLangChainRetriever(BaseRetriever)` (se requerirá instalar `langchain-core` en `extras`). Sobrescribir `_get_relevant_documents` para que invoque `OfflineRAGEngine.search` asíncronamente y empaquete los resultados en objetos `Document`.
        *   **CrewAI:** Implementar una herramienta `SESCrewAITool(BaseTool)`. Sobrescribir su función `_run` para que admita una consulta, realice el RAG mediante `OfflineRAGEngine.search` y devuelva el string consolidado para el agente.

### Paso 4: Pruebas Globales, Pre-Commit y Envío

**Objetivo:** Garantizar que todas las piezas nuevas encajan sin romper el comportamiento validado actual.

*   **Acciones:**
    1.  Ejecutar el pipeline de pruebas completo (`poetry run pytest`), resolviendo cualquier regresión detectada.
    2.  Completar los pasos de pre-commit.
    3.  Actualizar `ROADMAP.md` marcando los checks pendientes con `[x]`.
    4.  Subir los cambios al control de versiones.
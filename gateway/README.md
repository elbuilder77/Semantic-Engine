# 🌐 SES Enterprise Gateway

**SES Enterprise Gateway** es la capa comercial, segura y escalable que envuelve a **SES Core** para transformarlo en un producto de nivel empresarial y monetizable (SaaS o Despliegues On-Premise administrados). 

Esta capa está diseñada para operar como un servicio satélite del motor RAG, manteniendo el núcleo algorítmico inmutable y agregando controles críticos de seguridad, multi-tenancy, rate limiting y telemetría de facturación.

---

## 🎨 Características Comerciales (Monetización)

1. **Aislamiento Multi-Tenant (Namespaces)**:
   - Los clientes se autentican mediante tokens y quedan aislados estrictamente en sus respectivos namespaces vectoriales de Qdrant. No existe comunicación cruzada de documentos.
2. **Control de Acceso basado en Roles (RBAC)**:
   - **Admin**: Control total sobre el Gateway, generación de tokens, visualización de logs de tráfico global y auditoría.
   - **Client**: Acceso restringido únicamente a operaciones de RAG (búsqueda e ingestión) sobre su propio espacio de nombres asignado.
3. **Control de Cuotas y Rate Limiting (Redis)**:
   - Limita las peticiones por minuto (RPM) de forma granular por cada cliente para proteger la infraestructura offline de sobrecargas de inferencia en CPU/GPU.
4. **Telemetría para Facturación (Consumption Billing)**:
   - Registra contadores agregados por cliente (número de búsquedas, ingestión de documentos y latencias promedio) para habilitar esquemas de cobro por uso.
5. **Dashboard de Operaciones (Developer Portal)**:
   - Una interfaz web interactiva y moderna que permite a los desarrolladores y administradores vigilar la salud del sistema, interactuar con el Playground de RAG, administrar tokens de acceso y subir archivos.

---

## 🏗️ Arquitectura de Servicios

```text
               ┌────────────────────────────────────────┐
               │        SES Enterprise Gateway          │
               │  (FastAPI REST APIs & Web Dashboard)   │
               └────┬──────────────────┬─────────────┬──┘
                    │                  │             │
                    ▼                  ▼             ▼
       ┌──────────────────┐   ┌──────────────┐  ┌──────────────────┐
       │   Ollama (LLM)   │   │  Redis Cache │  │  Qdrant DB (RAG) │
       │  (Offline-First) │   │ & Rate Limit │  │  (Vector Search) │
       └──────────────────┘   └──────────────┘  └──────────────────┘
```

- **Backend**: FastAPI (Python) que sirve tanto la interfaz web estática como las APIs REST.
- **Base de Datos Vectorial**: Qdrant, administrado a través de las abstracciones del core.
- **Caché y Limitador**: Redis, usado para rate limiting dinámico y almacenamiento de contadores. En producción (`DEBUG=false`), una caída de Redis bloquea las rutas protegidas con `503` para evitar operar sin el control distribuido. El fallback en memoria existe únicamente para desarrollo explícito (`DEBUG=true`).

---

## ⚙️ Instalación y Arranque

### Requisitos Previos
Asegúrese de tener la infraestructura base iniciada (Qdrant y Redis). Puede levantarlos usando Docker:
```bash
docker run -d -p 6333:6333 qdrant/qdrant
docker run -d -p 6379:6379 redis
```

### Ejecutar el Gateway
Genere primero secretos locales únicos. El archivo `.env` y las llaves generadas
están excluidos de Git y los valores no se imprimen:

```bash
pip install -e .[server,security]
python scripts/rotate_local_secrets.py
```

Reinicie el Gateway inmediatamente después de la rotación para activar la nueva
llave y descartar cualquier caché de autenticación del proceso anterior.

En producción no use el archivo local: inyecte `GATEWAY_ADMIN_KEY`,
`GATEWAY_CORS_ORIGINS`, las credenciales de Qdrant y Redis mediante su gestor de
secretos. `GATEWAY_ADMIN_KEY` es obligatorio, debe tener al menos 32 caracteres
y no tiene valor predeterminado.

Para iniciar el servidor de desarrollo del Gateway:
```bash
python gateway/run.py
```
El servidor arrancará en `http://localhost:8000`.

---

## 📚 Catálogo de Endpoints (API REST)

Todas las llamadas de clientes deben incluir la cabecera `X-API-Key: <token>`.

### 1. Ingestión y Gestión Documental
- `POST /api/v1/ingest/file`: Sube e indexa un archivo físico (PDF, DOCX, XLSX, TXT) en el espacio del cliente.
- `POST /api/v1/ingest/text`: Indexa texto plano directamente.
- `GET /api/v1/documents`: Lista todos los documentos indexados en el namespace asignado.
- `DELETE /api/v1/documents/{doc_id}`: Elimina un documento por su ID del espacio vectorial.

### 2. Recuperación y Búsqueda (RAG)
- `POST /api/v1/search`: Realiza la búsqueda semántica acelerada en Rust, aplica re-ranking cognitivo y, opcionalmente, sintetiza una respuesta de lenguaje natural usando Ollama.
  ```json
  {
    "query": "¿Cuáles son las condiciones de rescisión?",
    "top_k": 5,
    "threshold": 0.2,
    "generate_answer": true
  }
  ```

### 3. Monitoreo e Infraestructura
- `GET /api/v1/health`: Reporte de estado del Gateway y de la conexión con Qdrant, Redis y Ollama.
- `GET /api/v1/stats`: Obtiene estadísticas de almacenamiento vectorial del namespace activo.

### 4. Administración (Solo para tokens con rol `admin`)
- `GET /api/v1/admin/keys`: Lista todas las llaves comerciales activas.
- `POST /api/v1/admin/keys`: Genera un nuevo token comercial con cuotas y namespace personalizado.
- `DELETE /api/v1/admin/keys/{key_to_delete}`: Revoca y elimina un token del sistema.
- `GET /api/v1/admin/analytics`: Obtiene métricas agregadas del rendimiento global y logs de peticiones recientes.

---

## 🧪 Pruebas Automatizadas
El Gateway cuenta con una suite de pruebas unitarias y de integración que mockea el motor e inferencias pesadas para ejecutarse instantáneamente de forma aislada:
```bash
pytest gateway/test_gateway.py
```
